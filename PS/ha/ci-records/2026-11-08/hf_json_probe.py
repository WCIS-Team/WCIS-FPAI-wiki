import json

p = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json'
d = json.load(open(p, encoding='utf-8'))
net = d.get('network') or d
ops = net.get('ops', [])
print('total ops', len(ops))
for i, o in enumerate(ops):
    nm = o.get('name', '')
    if nm in ('Output', 'Input') or 'merged_distr' in json.dumps(o)[:400]:
        print(i, nm, 'inputs=', [v.get('v_id') for v in o.get('inputs', [])],
              'outputs=', [v.get('v_id') for v in o.get('outputs', [])])
        if i > 60:
            break
