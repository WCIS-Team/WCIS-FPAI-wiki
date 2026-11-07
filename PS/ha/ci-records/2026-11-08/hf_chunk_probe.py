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

G = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG'
net = icraft.xir.Network.CreateFromJsonFile(G + '/hifigan_v2_ZG.json')
net.lazyLoadParamsFromFile(G + '/hifigan_v2_ZG.raw')
from pyrtutils.icraft_utils import openDevice, initSession
dev = openDevice('zg330', '192.168.125.143', True, False)
s = initSession('zg330', net, dev, 1)
s.apply()
print('applied', flush=True)

T = 120
mel = (0.5 + 0.5 * np.sin(np.linspace(0, 6.0, T)[:, None] * 1.3
                          + np.linspace(0, 1, 80)[None, :] * 4.0)).astype(np.float32)
mel *= (np.linspace(1, 0.2, 80)[None, :])
mel600 = np.tile(mel, (int(np.ceil(600 / T)), 1))[:600]
intype = net.ops[0].outputs[0].tensorType()
inp = xrt.Tensor(np.ascontiguousarray(mel600.T), intype)
o = s.forward([inp])
for t in o:
    t.waitForReady(datetime.timedelta(milliseconds=20000))
out = o[0]
print('out tensorType:', out.dtype().shape, str(out.dtype().element_dtype), str(out.dtype().layout), flush=True)
print('offset()', out.offset(), 'chunk().byte_size', out.chunk().byte_size, flush=True)
# 列出全部 chunk（如果有复数个）
try:
    chunks = out.chunks()
    print('chunks() n =', len(chunks), flush=True)
    total = 0
    for i, ch in enumerate(chunks[:5]):
        print(' chunk%d byte_size=%d offset=%d' % (i, ch.byte_size, ch.offset), flush=True)
        total += ch.byte_size
    print(' first5_total', total, flush=True)
except Exception as e:
    print('chunks() failed:', repr(e)[:120], flush=True)
# 用 Tensor2Numpy 同款方式读
arr = np.zeros(shape=out.dtype().shape, dtype=np.float32)
out.read(arr, out.offset(), out.chunk().byte_size)
print('read_back first8:', arr.ravel()[:8].tolist(), flush=True)
print('std', round(float(arr.std()), 4), flush=True)
