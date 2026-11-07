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
from pyrtutils.icraft_utils import openDevice, initSession

# 与 adapter frames=120 完全相同的确定性 mel
T = 120
t = (np.arange(T)[:, None] / max(1, T - 1))
f = (np.arange(80)[None, :] / 79.0)
mel = (0.5 + 0.5 * np.sin(6.2832 * (t * 3 + f * 2)) * (1 - f) ** 2).astype(np.float32)
mel600 = np.tile(mel, (int(np.ceil(600 / T)), 1))[:600]
np.save('/tmp/ab_mel600.npy', mel600)

G = '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG'
net = icraft.xir.Network.CreateFromJsonFile(G + '/hifigan_v2_ZG.json')
net.lazyLoadParamsFromFile(G + '/hifigan_v2_ZG.raw')
dev = openDevice('zg330', '192.168.125.143', True, False)
s = initSession('zg330', net, dev, 1)
s.apply()
intype = net.ops[0].outputs[0].tensorType()
inp = xrt.Tensor(np.ascontiguousarray(mel600).reshape(1, 1, 600, 80), intype)
o = s.forward([inp])
for tt in o:
    tt.waitForReady(datetime.timedelta(milliseconds=20000))
arr = np.zeros((153600,), dtype=np.float32)
o[0].read(arr, o[0].offset(), o[0].chunk().byte_size)
np.save('/tmp/ab_npu_wave.npy', arr)
print('NPU saved std=%.4f peak=%.4f first6=%s' % (
    float(arr.std()), float(np.max(np.abs(arr))), np.round(arr[:6], 4).tolist()), flush=True)
