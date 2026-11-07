import json

p = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json'
d = json.load(open(p, encoding='utf-8'))
net = d.get('network') or d
ops = net.get('ops', [])
print('net keys:', list(net.keys()))
outs = net.get('outputs')
print('net.outputs type:', type(outs), str(outs)[:300])
ins = net.get('inputs')
print('net.inputs:', str(ins)[:200])
# ops structure: check if values are inline in ops (v_id objects)
o = ops[1]
print('op1 input obj:', json.dumps(o['inputs'][0])[:300])
print('op1 output obj:', json.dumps(o['outputs'][0])[:300])
