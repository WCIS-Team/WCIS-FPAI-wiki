#!/bin/sh
set -e
echo "== ERNIE resident test $(date -Is)"
pkill -f "port 18080" 2>/dev/null || true
sleep 2
cd /root/npuserv
(setsid python3 server.py --port 18080 --resident > /tmp/npu_er.log 2>&1 < /dev/null &)
sleep 4
ss -ltn | grep -q 18080 && echo port_up
echo "--- load ernie (resident, shared device)"
curl -s --max-time 300 -XPOST localhost:18080/load -H 'Content-Type: application/json' \
  --data-binary '{"model":"ernie-4.5-0.3b"}' | head -c 260; echo
echo "--- load hifigan beside it"
curl -s --max-time 120 -XPOST localhost:18080/load -H 'Content-Type: application/json' \
  --data-binary @/tmp/hf_load.json | head -c 200; echo
echo "--- gen ernie"
printf '%s' '{"model":"ernie-4.5-0.3b","text":"你好","max_new":16}' > /tmp/er_gen.json
curl -s --max-time 300 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/er_gen.json > /tmp/er_out.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/er_out.json'))
if 'error' in d: print('ernie ERR', d['error'][:160])
else: print('ernie text=%r' % (d.get('text') or '')[:60])
PY
echo "--- gen hifigan after"
curl -s --max-time 120 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/hf_gen.json > /tmp/er_hf.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/er_hf.json'))
print('hf', 'ERR ' + d['error'][:120] if 'error' in d else 'samples=%s' % d.get('samples'))
PY
echo "--- status"
curl -s localhost:18080/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('engines',d.get('engines'))"
echo done