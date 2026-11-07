#!/bin/sh
set -e
echo "== resident mode test $(date -Is)"
pkill -f "port 18080" 2>/dev/null || true
sleep 2
cd /root/npuserv
(setsid python3 server.py --port 18080 --resident > /tmp/npu_res.log 2>&1 < /dev/null &)
sleep 4
ss -ltn | grep -q 18080 && echo port_up
echo "--- load hifigan (resident)"
curl -s --max-time 120 -XPOST localhost:18080/load -H 'Content-Type: application/json' --data-binary @/tmp/hf_load.json | head -c 300; echo
echo "--- load qwen3 K128 (resident, same worker)"
curl -s --max-time 600 -XPOST localhost:18080/load -H 'Content-Type: application/json' --data-binary @/tmp/q3_load.json | head -c 300; echo
echo "--- gen hifigan"
curl -s --max-time 120 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/hf_gen.json > /tmp/r1.json
head -c 160 /tmp/r1.json; echo
echo "--- gen qwen3"
curl -s --max-time 300 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/q3long.json > /tmp/r2.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/r2.json'))
if 'error' in d: print('q3 ERR', d['error'][:150])
else: print('q3 gen=%s tok/s=%.2f text=%r' % (d.get('gen'), (d.get('gen') or 0)/(d.get('sec') or 1), (d.get('text') or '')[:60]))
PY
echo "--- gen hifigan again (qwen3 resident beside it)"
curl -s --max-time 120 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/hf_gen.json > /tmp/r3.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/r3.json'))
if 'error' in d: print('hf ERR', d['error'][:150])
else: print('hf samples=%s peak=%s apply_s=%s' % (d.get('samples'), d.get('peak'), d.get('apply_s')))
PY
echo "--- status"
curl -s localhost:18080/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('resident',d.get('resident'),'engines',d.get('engines'))"
echo "--- mem"
free -m | awk 'NR==2{print "avail="$7}'
echo done