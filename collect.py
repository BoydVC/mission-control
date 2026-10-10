#!/usr/bin/env python3
"""Mission Control collector.

Pulls real, public data only and writes data/mission.json:
  * Launch Library 2 (The Space Devs) — upcoming SpaceX launches + Starship dashboard
  * Jonathan McDowell's Starlink statistics (planet4589.org)
  * Jim's interest-journal research files (/workspace/ij_*_research.md), SpaceX/Starlink bullets

Every block carries its source URL and fetched-at time. Nothing is invented: coarse NETs
(month / quarter / year) are passed through with their precision so the UI can show NET/TBD.
Read-only: never writes outside this folder. Respects the LL2 free-tier throttle (15 req/h,
shared box IP) with TTL caching; if a fetch fails it keeps the last good cache.
"""
import glob, html, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "cache")
OUT = os.path.join(HERE, "data", "mission.json")
ET = ZoneInfo("America/New_York")
LL2 = "https://ll.thespacedevs.com/2.3.0"
UA = "TokenMax-MissionControl/1.0 (personal wall dashboard)"
SOURCES = {
    "upcoming": (f"{LL2}/launches/upcoming/?limit=15&lsp__id=121&mode=normal", 1800),
    "starship": (f"{LL2}/dashboard/starship/", 5400),
    "previous": (f"{LL2}/launches/previous/?limit=10&lsp__id=121&mode=normal", 3600),
    "mcdowell": ("https://planet4589.org/space/con/star/stats.html", 6 * 3600),
}
# Read-only seed (never modified): the boyd-wall LL2 cache, used only if our own fetch fails
SEED = {"upcoming": None, "previous": "/workspace/tokenmax/boyd-wall/data/cache/ll2_previous.json", "starship": "/workspace/tokenmax/boyd-wall/data/cache/ll2_starship.json"}
RESEARCH_GLOB = "/workspace/ij_*_research.md"


def now_utc():
    return datetime.now(timezone.utc)


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def raw_path(name):
    return os.path.join(CACHE, f"raw_{name}.{'html' if name == 'mcdowell' else 'json'}")


def meta_path(name):
    return os.path.join(CACHE, f"raw_{name}.meta.json")


def ll2_budget_ok():
    try:
        req = urllib.request.Request(f"{LL2}/api-throttle/", headers={"User-Agent": UA})
        t = json.load(urllib.request.urlopen(req, timeout=15))
        # leave headroom for the other wall on this box
        return t.get("current_use", 0) < t.get("your_request_limit", 15) - 2, t
    except Exception as e:  # throttle check failing shouldn't block
        return True, {"error": str(e)}


def fetch(name, force=False):
    """Return (bytes, meta). meta = {url, fetchedAt, status, origin}."""
    url, ttl = SOURCES[name]
    p, mp = raw_path(name), meta_path(name)
    meta = json.load(open(mp)) if os.path.exists(mp) else None
    if meta is None and os.path.exists(p):  # first manual pull: use file mtime as fetched-at
        meta = {"url": url, "fetchedAt": iso(os.path.getmtime(p)), "origin": "live"}
        json.dump(meta, open(mp, "w"))
    age = (now_utc() - datetime.fromisoformat(meta["fetchedAt"].replace("Z", "+00:00"))).total_seconds() if meta else 1e12
    if meta and age < ttl and not force:
        return open(p, "rb").read(), dict(meta, status="cache")
    if url.startswith(LL2):
        ok, info = ll2_budget_ok()
        if not ok:
            print(f"[{name}] LL2 throttle near limit {info}; keeping cache", file=sys.stderr)
            if meta:
                return open(p, "rb").read(), dict(meta, status="stale-throttled")
            return seed(name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        body = urllib.request.urlopen(req, timeout=60).read()
        if name != "mcdowell":
            json.loads(body)  # validate
        tmp = p + ".tmp"
        open(tmp, "wb").write(body)
        os.replace(tmp, p)
        meta = {"url": url, "fetchedAt": iso(time.time()), "origin": "live"}
        json.dump(meta, open(mp, "w"))
        return body, dict(meta, status="fresh")
    except Exception as e:
        print(f"[{name}] fetch failed: {e}", file=sys.stderr)
        if meta:
            return open(p, "rb").read(), dict(meta, status="stale-error")
        return seed(name)


def seed(name):
    sp = SEED.get(name)
    if sp and os.path.exists(sp):
        d = json.load(open(sp))
        return json.dumps(d["data"]).encode(), {"url": d["url"], "fetchedAt": iso(d["fetchedAt"]), "origin": "boyd-wall cache (read-only)", "status": "seed"}
    return None, {"url": SOURCES[name][0], "fetchedAt": None, "status": "missing"}


# ---------------------------------------------------------------- LL2 parsing
def launch(r):
    pad = r.get("pad") or {}
    loc = pad.get("location") or {}
    np_ = r.get("net_precision") or {}
    rc = (r.get("rocket") or {}).get("configuration") or {}
    m = r.get("mission") or {}
    st = r.get("status") or {}
    return {
        "id": r.get("id"),
        "name": r.get("name"),
        "mission": m.get("name") or (r.get("name") or "").split("|")[-1].strip(),
        "missionType": m.get("type"),
        "orbit": (m.get("orbit") or {}).get("name"),
        "missionDesc": (m.get("description") or "")[:400],
        "vehicle": rc.get("full_name") or rc.get("name"),
        "pad": pad.get("name"),
        "padId": pad.get("id"),
        "location": loc.get("name"),
        "lat": _f(pad.get("latitude")),
        "lon": _f(pad.get("longitude")),
        "net": r.get("net"),
        "netPrecision": np_.get("name"),
        "netPrecisionAbbrev": np_.get("abbrev"),
        "windowStart": r.get("window_start"),
        "windowEnd": r.get("window_end"),
        "status": st.get("name"),
        "statusAbbrev": st.get("abbrev"),
        "failreason": (r.get("failreason") or "")[:300],
        "probability": r.get("probability"),
        "apiUrl": r.get("url"),
        "lastUpdated": r.get("last_updated"),
    }


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def flight_label(L):
    n = L["mission"] or L["name"]
    m = re.search(r"\b(SN\d+)\b", L["name"] or "")
    if m:
        return m.group(1)
    if "Hopper" in (L["name"] or ""):
        return "Hopper " + (re.search(r"(\d+m)", L["name"]) or re.search("(.*)", "hop")).group(1)
    m = re.search(r"Flight (\d+)", L["name"] or "")
    if m:
        return f"Flight {m.group(1)}"
    m = re.search(r"Integrated Flight Test ?(\d*)", n)
    if m:
        return f"IFT-{m.group(1) or '1'}"
    return n


# ---------------------------------------------------------------- McDowell parsing
def parse_mcdowell(body):
    t = body.decode("utf-8", "ignore")
    asof = re.search(r"Data last updated:\s*([0-9]{4}\s+\w+\s+\d+\s+[0-9:]+)", t)
    rows = {}
    for m in re.finditer(r"<TR>(.*?)</TR>", t, re.S | re.I):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<T[DH][^>]*>(.*?)</T[DH]>", m.group(1), re.S | re.I)]
        if len(cells) >= 20 and cells[0] in ("Total", "Starlink Gen1", "Starlink Gen2", "Starlink Gen3D", "Starlink Gen3"):
            rows[cells[0]] = cells
    def num(row, i):
        try:
            return int(row[i])
        except Exception:
            return None
    # column order (see table header): 1 launched, 6 total down, 7 in orbit, 11 working, 17 drift, 18 ascent, 19 operational orbit
    def pack(row):
        return {"launched": num(row, 1), "down": num(row, 6), "inOrbit": num(row, 7), "working": num(row, 11),
                "drift": num(row, 17), "ascent": num(row, 18), "operational": num(row, 19)}
    out = {k: pack(v) for k, v in rows.items()}
    return {"total": out.get("Total"), "byGen": {k: v for k, v in out.items() if k != "Total"},
            "dataAsOf": re.sub(r"\s+", " ", asof.group(1)) + " UTC" if asof else None}


# ---------------------------------------------------------------- Jim's journal
KEYS = re.compile(r"spacex|starship|starlink|falcon|dragon|starmind|star mind|starbase|raptor|crew-\d|t1tl|vandenberg|super heavy|spacexai|spacexsi", re.I)
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BARE = re.compile(r"(?<![(\[])(https?://[^\s)>\]]+)")


def _journal_links(body):
    """Prefer markdown [label](url); also keep bare https URLs (Oct 7+ research style)."""
    seen, links = set(), []
    for a, u in LINK.findall(body):
        if u not in seen:
            seen.add(u)
            links.append({"label": a, "url": u})
    for u in BARE.findall(body):
        u = u.rstrip(".,;")
        if u in seen:
            continue
        seen.add(u)
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0]
        links.append({"label": host[:40], "url": u})
    return links


def parse_journal(limit_files=6, limit_items=28):
    files = sorted(glob.glob(RESEARCH_GLOB), reverse=True)[:limit_files]
    items = []
    for f in files:
        m = re.search(r"ij_(\d{4}-\d{2}-\d{2})_research", f)
        day = m.group(1) if m else None
        sub, in_a = None, False
        for line in open(f, encoding="utf-8", errors="ignore"):
            s = line.rstrip("\n")
            if s.startswith("## "):
                # "## A. SpaceX..." (older) or "## 1. SpaceX & Musk..." (Oct 7+)
                in_a = bool(re.match(r"##\s*[A1]\.", s)) or bool(KEYS.search(s))
                sub = None
                continue
            if s.startswith("### "):
                sub = s[4:].strip()
                continue
            mm = re.match(r"^\*\*([^*]+)\*\*\s*$", s.strip())
            if mm:
                sub = mm.group(1)
                continue
            if not (in_a or (sub and KEYS.search(sub))):
                continue
            if not s.startswith("- "):
                continue
            body = s[2:]
            if not (KEYS.search(body) or (sub and re.search(r"spacex|starlink|starship|starmind", sub, re.I))):
                continue
            links = _journal_links(body)
            if not links:
                continue
            tm = re.match(r"\*\*(.+?)\*\*\s*(.*)", body)
            title, rest = (tm.group(1), tm.group(2)) if tm else (body[:120], body[120:])
            # Strip link markup + bare URLs from card body text (keep titles/links verbatim elsewhere)
            text = LINK.sub(lambda x: x.group(1), rest)
            text = BARE.sub("", text)
            text = re.sub(r"\s*·\s*", " ", text).replace("**", "").strip()
            text = re.sub(r"\s{2,}", " ", text)
            items.append({"date": day, "section": sub, "title": title.strip().rstrip(":"), "text": text[:260] + ("…" if len(text) > 260 else ""),
                          "links": links[:3], "file": os.path.basename(f)})
    return items[:limit_items], [os.path.basename(f) for f in files]


# ---------------------------------------------------------------- build
def build(force=False):
    os.makedirs(CACHE, exist_ok=True)
    out = {"generatedAt": iso(time.time()), "timezone": "America/New_York", "sources": {}}

    body, meta = fetch("upcoming", force)
    up = json.loads(body) if body else {"results": []}
    launches = [launch(r) for r in up.get("results", [])]
    launches.sort(key=lambda L: (L["net"] or "9999", L["name"] or ""))
    out["launches"] = launches
    out["sources"]["upcoming"] = dict(meta, label="Launch Library 2 · The Space Devs", home="https://thespacedevs.com/llapi", count=up.get("count"))

    body, meta = fetch("previous", force)
    pv = json.loads(body) if body else {"results": []}
    recent = [launch(r) for r in pv.get("results", [])]
    recent.sort(key=lambda L: L["net"] or "", reverse=True)
    out["recent"] = recent
    out["sources"]["previous"] = dict(meta, label="Launch Library 2 · The Space Devs", home="https://thespacedevs.com/llapi")

    body, meta = fetch("starship", force)
    ss = json.loads(body) if body else {}
    prev = [launch(r) for r in ((ss.get("previous") or {}).get("launches") or [])]
    prev.sort(key=lambda L: L["net"] or "")
    for L in prev:
        L["label"] = flight_label(L)
        L["integrated"] = "Super Heavy" in (L["vehicle"] or "") or bool(re.search(r"Integrated|Flight \d+", L["name"] or "")) and not re.search(r"SN\d+|Hopper", L["name"] or "")
    upc = [launch(r) for r in ((ss.get("upcoming") or {}).get("launches") or [])]
    upc.sort(key=lambda L: L["net"] or "")
    for L in upc:
        L["label"] = flight_label(L)
    integ = [L for L in prev if L["integrated"]]
    vehicles = []
    for v in (ss.get("vehicles") or []) + (ss.get("orbiters") or []):
        stv = v.get("status")
        stn = stv.get("name") if isinstance(stv, dict) else stv
        if (stn or "").lower() == "active" and not v.get("is_placeholder"):
            vehicles.append(v.get("serial_number") or v.get("name"))
    updates = sorted(ss.get("updates") or [], key=lambda u: u.get("created_on") or "", reverse=True)[:4]
    out["starship"] = {
        "flights": prev,
        "upcoming": upc,
        "integratedCount": len(integ),
        "integratedOutcomes": {k: sum(1 for L in integ if L["status"] == k) for k in sorted({L["status"] for L in integ})},
        "activeVehicles": vehicles,
        "updates": [{"text": (u.get("comment") or "")[:240], "date": u.get("created_on"), "url": u.get("info_url")} for u in updates],
    }
    out["sources"]["starship"] = dict(meta, label="Launch Library 2 · Starship dashboard", home="https://thespacedevs.com/llapi")

    body, meta = fetch("mcdowell", force)
    out["starlink"] = parse_mcdowell(body) if body else None
    out["sources"]["starlink"] = dict(meta, label="Jonathan McDowell · Jonathan's Space Report, Starlink statistics", home="https://planet4589.org/space/con/star/stats.html")

    items, files = parse_journal()
    out["journal"] = items
    out["sources"]["journal"] = {"label": "Jim's interest-journal research files", "files": files, "fetchedAt": iso(time.time()),
                                 "fileTimes": {os.path.basename(f): iso(os.path.getmtime(f)) for f in sorted(glob.glob(RESEARCH_GLOB), reverse=True)[:4]}}

    # launch sites for the globe (real pad coordinates from LL2)
    pads = {}
    for L in launches + upc + prev[-6:]:
        if L["lat"] is None or not L["pad"]:
            continue
        key = L["pad"] if L["pad"] != "Unknown Pad" else f"{L['location']} (pad TBD)"
        p = pads.setdefault(key, {"name": key, "location": L["location"], "lat": L["lat"], "lon": L["lon"], "upcoming": 0, "next": None})
        if L in launches or L in upc:
            p["upcoming"] += 1
            if p["next"] is None or (L["net"] or "") < (p["next"] or ""):
                p["next"] = L["net"]
    out["pads"] = sorted(pads.values(), key=lambda p: -p["upcoming"])

    tmp = OUT + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, OUT)
    return out


if __name__ == "__main__":
    o = build(force="--force" in sys.argv)
    print(f"launches={len(o['launches'])} starship_flights={len(o['starship']['flights'])} journal={len(o['journal'])} "
          f"starlink_total={o['starlink'] and o['starlink']['total']} pads={[p['name'] for p in o['pads']]}")
    for L in o["launches"][:3]:
        print(" ", L["net"], L["netPrecisionAbbrev"], L["statusAbbrev"], L["mission"], "|", L["pad"])
