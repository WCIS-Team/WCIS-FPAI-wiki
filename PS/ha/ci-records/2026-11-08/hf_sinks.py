import json

p = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json'
d = json.load(open(p, encoding='utf-8'))
net = d.get('network') or d
ops = net.get('ops', [])
vals = net.get('values') or net.get('tensors') or []
print('keys of net:', list(net.keys())[:8])
# Output values: find values not consumed as input by anyone (graph outputs)
consumed = set()
for o in ops:
    for v in o.get('inputs', []):
        consumed.add(v.get('v_id'))
produced = {}
for o in ops:
    for v in o.get('outputs', []):
        produced[v.get('v_id')] = (v, o.get('name'), o.get('compile_target'))
sinks = [(vid, produced[vid]) for vid in produced if vid not in consumed and vid != 0]
print('sink values (graph outputs):')
for vid, (v, nm, ct) in sinks[:6]:
    tt = v.get('tensorType') or {}
    print('  v_id', vid, 'from', nm, 'target', ct,
          'dtype', tt.get('element_dtype'), 'layout', tt.get('layout'),
          'shape', tt.get('shape'), 'merged', str(tt.get('merged_distrs'))[:80])
