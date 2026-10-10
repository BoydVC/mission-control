#!/usr/bin/env python3
"""Build dist/mission-control-snapshot.html: one self-contained offline file (CSS, JS, coastline,
and the saved mission.json inlined). Countdowns keep ticking offline from the saved NETs."""
import json, os, sys, time
from datetime import datetime, timezone
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect

def main():
    data = json.load(open(collect.OUT)) if os.path.exists(collect.OUT) else collect.build()
    w = lambda n: open(os.path.join(HERE, "web", n), encoding="utf-8").read()
    html = w("index.html")
    safe = lambda s: s.replace("</script", "<\\/script")
    snap = {"savedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "data": data}
    html = html.replace('<link rel="stylesheet" href="style.css">', "<style>\n" + w("style.css") + "\n</style>")
    html = html.replace("<!--INLINE-DATA-->", "<script>window.__MC_SNAPSHOT__=" + safe(json.dumps(snap, separators=(",", ":"))) + ";</script>")
    for js in ("land.js", "globe.js", "app.js"):
        html = html.replace(f'<script src="{js}"></script>', "<script>\n" + safe(w(js)) + "\n</script>")
    assert 'src="' not in html.split("<body")[1].split("</body>")[0].replace('src="${', ''), "external src left"
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", "mission-control-snapshot.html")
    open(out, "w", encoding="utf-8").write(html)
    print(out, f"{os.path.getsize(out)/1024:.0f} KB")

if __name__ == "__main__":
    main()
