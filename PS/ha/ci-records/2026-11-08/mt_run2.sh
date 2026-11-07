#!/bin/sh
set -e
echo "== ERNIE multi-turn acceptance $(date -Is)"
pkill -f "port 18080" 2>/dev/null || true
sleep 2
cd /root/npuserv
(setsid python3 server.py --port 18080 --resident > /tmp/npu_mt.log 2>&1 < /dev/null &)
sleep 4
curl -s --max-time 600 -XPOST http://127.0.0.1:18080/load -H 'Content-Type: application/json' \
  --data-binary '{"model":"ernie-4.5-0.3b"}' | head -c 110; echo
python3 /tmp/ernie_mt_board.py 2>&1 | tail -14
echo done