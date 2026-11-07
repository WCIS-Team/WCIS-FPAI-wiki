#!/bin/sh
set -e
echo "== order test: qwen3 FIRST, hifigan SECOND, then alternate"
pkill -f "port 18080" 2>/dev/null || true
sleep 2
cd /root/npuserv
(setsid python3 server.py --port 18080 --resident > /tmp/npu_r2.log 2>&1 < /dev/null &)
sleep 4
echo "--- load qwen3 (first)"
curl -s --max-time 600 -XPOST localhost:18080/load -H 'Content-Type: application/json' --data-binary @/tmp/q3_load.json | head -c 150; echo
echo "--- load hifigan (second)"
curl -s --max-time 120 -XPOST localhost:18080/load -H 'Content-Type: application/json' --data-binary @/tmp/hf_load.json | head -c 150; echo
echo "--- gen qwen3"
curl -s --max-time 300 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/q3long.json > /tmp/o1.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/o1.json'))
print('q3', 'ERR ' + d['error'][:120] if 'error' in d else 'tok/s=%.2f text=%r' % ((d.get('gen') or 0)/(d.get('sec') or 1), (d.get('text') or '')[:50]))
PY
echo "--- gen hifigan"
curl -s --max-time 120 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/hf_gen.json > /tmp/o2.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/o2.json'))
print('hf', 'ERR ' + d['error'][:120] if 'error' in d else 'samples=%s peak=%s' % (d.get('samples'), d.get('peak')))
PY
echo "--- gen qwen3 again"
curl -s --max-time 300 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/q3long.json > /tmp/o3.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/o3.json'))
print('q3#2', 'ERR ' + d['error'][:120] if 'error' in d else 'tok/s=%.2f' % ((d.get('gen') or 0)/(d.get('sec') or 1)))
PY
echo done