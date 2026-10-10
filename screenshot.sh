#!/usr/bin/env bash
# Usage: ./screenshot.sh NAME WIDTH HEIGHT [query] [url]
cd "$(dirname "$0")"
NAME=$1; W=${2:-1920}; HH=${3:-1080}; Q=${4:-}; URL=${5:-"http://127.0.0.1:4245/?still=1&$Q"}
D=/tmp/mc-chrome-$$
google-chrome --headless=new --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=$W,$HH --virtual-time-budget=${BUDGET:-4000} --user-data-dir=$D \
  --screenshot="screenshots/$NAME.png" "$URL" 2>/dev/null >/dev/null
rm -rf $D; ls -la "screenshots/$NAME.png" | awk '{print $5, $9}'
