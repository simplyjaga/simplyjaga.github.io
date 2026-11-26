#!/usr/bin/env bash
# Rebuild the blog preview and (re)start the localhost server on :4000
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pkill -f "http.server 4000" 2>/dev/null
sleep 0.5
python3 "$SCRIPT_DIR/render_preview.py" && \
  cd /tmp/blog_preview_site && \
  nohup python3 -m http.server 4000 --bind 127.0.0.1 >/tmp/blog_preview_server.log 2>&1 &
sleep 1
curl -s -o /dev/null -w "server up: %{http_code}\n" http://127.0.0.1:4000/
