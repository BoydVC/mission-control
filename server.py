#!/usr/bin/env python3
"""Mission Control server: serves web/ and data/mission.json on :4245 and refreshes data in the
background (collector honours per-source TTLs and the LL2 free-tier throttle)."""
import json, os, sys, threading, time, traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect  # noqa: E402

PORT = int(os.environ.get("PORT", 4245))
WEB = os.path.join(HERE, "web")


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/api/mission.json", "/data/mission.json"):
            try:
                body = open(collect.OUT, "rb").read()
            except FileNotFoundError:
                body = json.dumps(collect.build()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/healthz":
            b = b"ok"
            self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b)
            return
        return super().do_GET()


def refresher():
    while True:
        try:
            collect.build()
        except Exception:
            traceback.print_exc()
        time.sleep(300)


if __name__ == "__main__":
    threading.Thread(target=refresher, daemon=True).start()
    print(f"Mission Control on http://127.0.0.1:{PORT}/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
