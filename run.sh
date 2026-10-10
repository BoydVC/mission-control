#!/usr/bin/env bash
# Start (or restart) Mission Control on :4245 in the background; stays up after the shell exits.
cd "$(dirname "$0")"
PORT=${PORT:-4245}
if [ -f data/server.pid ] && kill -0 "$(cat data/server.pid)" 2>/dev/null; then kill "$(cat data/server.pid)"; sleep 1; fi
python3 collect.py || echo "collector warning (keeping last cache)"
PORT=$PORT nohup python3 server.py > data/server.log 2>&1 &
echo $! > data/server.pid
sleep 1
curl -fsS "http://127.0.0.1:$PORT/healthz" >/dev/null && echo "Mission Control up: http://127.0.0.1:$PORT/  (kiosk: /?kiosk=1)"
