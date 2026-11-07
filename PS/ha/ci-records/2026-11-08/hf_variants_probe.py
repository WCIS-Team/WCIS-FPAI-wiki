import sys, types, datetime
_stub = types.ModuleType('tokenizers')
class _Tok(object):
    @staticmethod
    def from_file(path):
        raise RuntimeError('stub')
_stub.Tokenizer = _Tok
sys.modules['tokenizers'] = _stub
sys.path.insert(0, '/root/icraft39')
sys.path.insert(0, '/root/qwen2/modelzoo_utils')
import numpy as np
import icraft
import icraft.xrt as xrt
import icraft.xir as xir
from pyrtutils.icraft_utils import openDevice, initSession

G = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG'
net = icraft.xir.Network.CreateFromJsonFile(G + '/hifigan_v2_ZG.json')
net.lazyLoadParamsFromFile(G + '/hifigan_v2_ZG.raw')
dev = openDevice('zg330', '192.168.125.143', True, False)
s = initSession('zg330', net, dev, 1)
s.apply()
print('applied', flush=True)

T = 120
mel = (0.5 + 0.5 * np.sin(np.linspace(0, 6.0, T)[:, None] * 1.3
                          + np.linspace(0, 1, 80)[None, :] * 4.0)).astype(np.float32)
mel *= (np.linspace(1, 0.2, 80)[None, :])
mel600 = np.tile(mel, (int(np.ceil(600 / T)), 1))[:600]
variants = {
    'T80x600': np.ascontiguousarray(mel600.T),
    'T600x80': np.ascontiguousarray(mel600),
}
intype = net.ops[0].outputs[0].tensorType()
outs = {}
for name, arr in variants.items():
    for run in range(2):
        inp = xrt.Tensor(arr, intype)
        o = s.forward([inp])
        for t in o:
            t.waitForReady(datetime.timedelta(milliseconds=20000))
        w = np.zeros((153600,), dtype=np.float32)
        o[0].read(w, o[0].offset(), o[0].chunk().byte_size)
        outs['%s_r%d' % (name, run)] = w
        del o
print('forward done x4', flush=True)
keys = list(outs)
for i in range(len(keys)):
    for j in range(i + 1, len(keys)):
        c = float(np.corrcoef(outs[keys[i]], outs[keys[j]])[0, 1])
        print('corr(%s,%s)=%.4f' % (keys[i], keys[j], c), flush=True)
np.save('/tmp/hf_probe_T80x600_r0.npy', outs['T80x600_r0'])
print('saved npy', flush=True)