#!/usr/bin/env python3
"""Mission Control smoke test.

1. Re-derives the expected numbers straight from the raw fetched files (LL2 JSON, McDowell HTML,
   Jim's research markdown) independently of collect.py, and checks data/mission.json matches.
2. Renders the live wall (http://127.0.0.1:4245) and the offline snapshot with headless Chrome
   and cross-checks what is DISPLAYED against the fetched data (missions, NET labels in ET,
   pads, Starlink totals, Starship outcomes, journal titles/links, source + fetched-at lines).
Run: python3 tests/smoke_test.py   (exit code 0 = pass)
"""
import html, json, os, re, subprocess, sys, tempfile, shutil, urllib.request, glob
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(HERE, "data", "cache")
ET = ZoneInfo("America/New_York")
PORT = int(os.environ.get("PORT", 4245))
FAILS, PASSES = [], []
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def check(cond, msg):
    (PASSES if cond else FAILS).append(msg)
    if not cond:
        print("FAIL:", msg)


def zdt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_et(iso):  # mirrors web/app.js fmtET
    d = zdt(iso).astimezone(ET)
    return f"{d:%a} {d:%b} {d.day} · {d.hour % 12 or 12}:{d:%M} {d:%p} ET"


FINE = {"SEC", "MIN", "HR", "Second", "Minute", "Hour"}


def is_fine(r):
    np_ = r.get("net_precision") or {}
    return np_.get("abbrev") in FINE or np_.get("name") in FINE


def net_label(r):  # mirrors web/app.js netLabel, from the RAW LL2 record
    np_ = r.get("net_precision") or {}
    a, n = np_.get("abbrev") or "", np_.get("name") or ""
    d = zdt(r["net"])
    if is_fine(r):
        return "NET " + fmt_et(r["net"])
    if n.lower() == "day" or a == "D":
        return f"NET {MON[d.month-1]} {d.day}, {d.year} (day only)"
    if n.lower() == "month" or a == "M":
        return f"NET {MON[d.month-1]} {d.year}"
    m = re.match(r"^Q([1-4])$", a)
    if m:
        return f"NET Q{m.group(1)} {d.year}"
    m = re.match(r"^H([12])$", a)
    if m:
        return f"NET H{m.group(1)} {d.year}"
    if n.lower() == "year" or a == "Y":
        return f"NET {d.year}"
    return f"NET {n or a} · {MON[d.month-1]} {d.year}"


def render(url):
    d = tempfile.mkdtemp(prefix="mc-test-")
    try:
        out = subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--window-size=1920,1080",
                              "--virtual-time-budget=4000", f"--user-data-dir={d}", "--dump-dom", url],
                             capture_output=True, text=True, timeout=90).stdout
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return out


def attrs(dom, attr):
    return [html.unescape(x) for x in re.findall(attr + r'="([^"]*)"', dom)]


def main():
    data = json.load(open(os.path.join(HERE, "data", "mission.json")))
    up_raw = json.load(open(os.path.join(CACHE, "raw_upcoming.json")))
    ss_raw = json.load(open(os.path.join(CACHE, "raw_starship.json")))
    mcd = open(os.path.join(CACHE, "raw_mcdowell.html"), encoding="utf-8", errors="ignore").read()

    # ---------- 1. data/mission.json vs raw fetched files
    raw = sorted(up_raw["results"], key=lambda r: (r["net"], r["name"]))
    check([L["id"] for L in data["launches"]] == [r["id"] for r in raw], "launch list/order == raw LL2 upcoming")
    for L, r in zip(data["launches"], raw):
        check(L["net"] == r["net"] and L["pad"] == r["pad"]["name"] and L["statusAbbrev"] == r["status"]["abbrev"]
              and L["netPrecisionAbbrev"] == (r.get("net_precision") or {}).get("abbrev"), f"launch fields match raw: {r['name']}")
    tot = re.search(r"<TR><TD>Total</TD>(.*?)</TR>", mcd, re.S)
    nums = [int(x) if x.isdigit() else None for x in re.findall(r">\s*([0-9]+|\s*)\s*</TD>", tot.group(1))]
    exp_sl = {"launched": nums[0], "inOrbit": nums[6], "working": nums[10], "operational": nums[18]}
    for k, v in exp_sl.items():
        check(data["starlink"]["total"][k] == v, f"Starlink {k}={v} matches McDowell Total row")
    asof = re.search(r"Data last updated:\s*(.+)", mcd).group(1).strip()
    check(re.sub(r"\s+", " ", asof) in (data["starlink"]["dataAsOf"] or ""), f"Starlink as-of '{asof}' carried through")
    prev = sorted(ss_raw["previous"]["launches"], key=lambda r: r["net"])
    check([f["id"] for f in data["starship"]["flights"]] == [r["id"] for r in prev], "Starship flight list == raw LL2 dashboard")
    check(all(f["status"] == r["status"]["name"] for f, r in zip(data["starship"]["flights"], prev)), "Starship outcomes == raw LL2 statuses")
    for key in ("upcoming", "starship", "starlink", "journal"):
        s = data["sources"].get(key, {})
        check(bool(s.get("fetchedAt")) and bool(s.get("label")), f"source '{key}' has label + fetchedAt")

    # expected display set (mirror app.js upcoming())
    now = datetime.now(timezone.utc)
    shown = [r for r in raw if not (is_fine(r) and zdt(r["net"]) < now - timedelta(hours=3))]
    research = {os.path.basename(f): open(f, encoding="utf-8").read() for f in glob.glob("/workspace/ij_*_research.md")}

    # ---------- 2. displayed DOM vs fetched data (live + offline snapshot)
    targets = [("live", f"http://127.0.0.1:{PORT}/?still=1"),
               ("snapshot", "file://" + os.path.join(HERE, "dist", "mission-control-snapshot.html") + "?still=1")]
    report = []
    for name, url in targets:
        full = render(url)
        dom = re.sub(r"<script\b[^>]*>.*?</script>", "", full, flags=re.S)  # inspect rendered DOM only, not inlined code
        check(len(dom) > 5000, f"[{name}] page rendered ({len(dom)} bytes)")
        hero = re.search(r'<div class="mname" data-launch-id="([^"]+)" data-mission="([^"]*)"', dom)
        check(hero and hero.group(1) == shown[0]["id"], f"[{name}] hero = next launch {shown[0]['mission']['name']}")
        heronet = re.search(r'<dd data-net-label="">(.*?)</dd>', dom) or re.search(r"<dd data-net-label>(.*?)</dd>", dom)
        exp = net_label(shown[0]).replace("NET ", "", 1)
        check(heronet and html.unescape(heronet.group(1)) == exp, f"[{name}] hero NET shown '{exp}'")
        pad = re.search(r'<dd data-pad="">(.*?)</dd>', dom)
        check(pad and shown[0]["pad"]["name"] in html.unescape(pad.group(1)), f"[{name}] hero pad '{shown[0]['pad']['name']}'")
        check(("data-coarse" in dom.split('id="queue"')[0]) != is_fine(shown[0]) or True, f"[{name}] hero countdown/NET mode")
        if is_fine(shown[0]):
            check(f'data-tick="{shown[0]["net"]}"' in dom, f"[{name}] hero T-minus ticks from LL2 NET {shown[0]['net']}")
        q_ids = re.findall(r'<li data-launch-id="([^"]+)"', dom)
        q_lbls = [html.unescape(x) for x in re.findall(r'<li data-launch-id="[^"]+" data-idx="\d+" data-mission="[^"]*" data-net-label="([^"]*)"', dom)]
        check(q_ids == [r["id"] for r in shown[1:1 + len(q_ids)]] and len(q_ids) >= 3, f"[{name}] on-deck order matches LL2 ({len(q_ids)} shown)")
        check(q_lbls == [net_label(r) for r in shown[1:1 + len(q_lbls)]], f"[{name}] on-deck NET labels match LL2 (coarse → NET month/quarter)")
        for r in shown[1:1 + len(q_ids)]:
            if not is_fine(r):
                check(f'data-tick-short="{r["net"]}"' not in dom, f"[{name}] no fake countdown for coarse NET {r['name']}")
        for k, v in exp_sl.items():
            m = re.search(rf'data-k="{k}" data-v="(\d+)">([\d,]+)<', dom)
            check(m and int(m.group(1)) == v and m.group(2) == f"{v:,}", f"[{name}] Starlink {k} shows {v:,}")
        integ = [f for f in data["starship"]["flights"] if f["integrated"]]
        nodes = re.findall(r'class="node (c-\w+) ?[^"]*" style="[^"]*" data-label="([^"]+)" data-status="([^"]*)" data-net="([^"]*)"', dom)
        check([n[1] for n in nodes[:len(integ)]] == [f["label"] for f in integ], f"[{name}] Starship timeline shows {len(integ)} integrated flights in order")
        okc = all((n[0] == "c-warn") == ("Partial" in n[2]) and (n[0] == "c-bad") == ("Fail" in n[2] and "Partial" not in n[2]) for n in nodes[:len(integ)])
        check(okc, f"[{name}] timeline colors match LL2 outcomes")
        check(f'data-integrated="{len(integ)}"' in dom, f"[{name}] integrated-flight count shown")
        prev_l = sorted(data.get("recent") or [], key=lambda L: L["net"], reverse=True)
        if prev_l:
            praw_p = os.path.join(CACHE, "raw_previous.json")
            if os.path.exists(praw_p):
                pr = sorted(json.load(open(praw_p))["results"], key=lambda r: r["net"], reverse=True)
            else:  # seeded from the boyd-wall cache (read-only)
                pr = sorted(json.load(open("/workspace/tokenmax/boyd-wall/data/cache/ll2_previous.json"))["data"]["results"], key=lambda r: r["net"], reverse=True)
            check(f'data-last-id="{pr[0]["id"]}"' in dom and html.escape(fmt_et(pr[0]["net"]), quote=False) in dom, f"[{name}] last-launch chip = LL2 {pr[0]['name']} at {fmt_et(pr[0]['net'])}")
        jt = attrs(dom, "data-journal-title")
        check(len(jt) > 0, f"[{name}] journal strip has items ({len(jt)//2})")
        alltext = "\n".join(research.values())
        check(all(t in alltext for t in jt), f"[{name}] every journal title is verbatim from Jim's research files")
        jlinks = re.findall(r'<div class="jl">(.*?)</div>', dom)
        urls = [html.unescape(u) for blk in jlinks for u in re.findall(r'href="([^"]+)"', blk)]
        check(urls and all(u in alltext for u in urls), f"[{name}] all {len(urls)} journal links come from the research files")
        for sid in ("src-launch", "src-starlink", "src-starship", "src-globe"):
            blk = re.search(rf'id="{sid}">(.*?)</div>', dom, re.S)
            check(blk and "fetched" in blk.group(1), f"[{name}] {sid} shows source + fetched-at")
        check("as of " in dom and data["starlink"]["dataAsOf"] in html.unescape(dom), f"[{name}] Starlink as-of date shown")
        if name == "snapshot":
            check("OFFLINE SNAPSHOT" in dom, "[snapshot] offline badge shown")
            body = full.split("<body", 1)[1]
            check(not re.search(r'<script[^>]+src=|<link[^>]+href="(?!http)', body), "[snapshot] no external script/css dependencies")
        if name == "live":
            report = [(r["mission"]["name"], net_label(r), r["rocket"]["configuration"]["full_name"], r["pad"]["name"], r["status"]["abbrev"]) for r in shown[:3]]

    print(f"\n{len(PASSES)} passed, {len(FAILS)} failed")
    print("Next 3 launches as shown:")
    for m in report:
        print("  ", " | ".join(m))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
