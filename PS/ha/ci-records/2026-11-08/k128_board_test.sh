#!/bin/sh
pkill -f 18080 2>/dev/null
sleep 2
cd /root/npuserv
(setsid python3 server.py --port 18080 > /tmp/npu8.log 2>&1 < /dev/null &)
sleep 4
ss -ltn | grep -q 18080 && echo port_up
curl -s --max-time 600 -XPOST localhost:18080/load -H 'Content-Type: application/json' --data-binary @/tmp/q3_load.json > /tmp/q3k_load_out.json
head -c 320 /tmp/q3k_load_out.json
echo
echo "== generate max_new=32 (K128)"
curl -s --max-time 300 -XPOST localhost:18080/generate -H 'Content-Type: application/json' --data-binary @/tmp/q3ns_gen.json > /tmp/q3k_gen_out.json
python3 - <<'PY'
import json
d = json.load(open('/tmp/q3k_gen_out.json'))
if 'error' in d:
    print('ERROR', d['error'][:150])
else:
    gen, sec = d.get('gen'), d.get('sec')
    print('pos_rule', d.get('pos_rule'), 'kv_ctx', d.get('info', {}).get('max_decode_length_in_config'))
    print('gen=%s sec=%s tok/s=%.2f' % (gen, sec, (gen or 0) / (sec or 1)))
    print('text:', (d.get('text') or '')[:90])
PY
echo done