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
mel600 = np.tile(mel, (int(np.ceil(600 / T)), 1))[:600]     # [600,80] 时间×频带

intype = net.ops[0].outputs[0].tensorType()
print('declared input type:', intype.shape, str(intype.layout), flush=True)

# 正确喂法：NHWC [1,1,600,80] = mel600 的 C 序连续内存
correct = np.ascontiguousarray(mel600).reshape(1, 1, 600, 80)
inp = xrt.Tensor(correct, intype)
o = s.forward([inp])
for t in o:
    t.waitForReady(datetime.timedelta(milliseconds=20000))
arr = np.zeros((153600,), dtype=np.float32)
o[0].read(arr, o[0].offset(), o[0].chunk().byte_size)
print('NPU(std=%.4f peak=%.3f) first8=%s' % (
    float(arr.std()), float(np.max(np.abs(arr))), np.round(arr[:8], 4).tolist()), flush=True)
np.save('/tmp/hf_correct.npy', arr)

# 对照：错误喂法（adapter 现状 mel.T [80,600] 连续）
wrong = np.ascontiguousarray(mel600.T)
inp2 = xrt.Tensor(wrong, intype)
o2 = s.forward([inp2])
for t in o2:
    t.waitForReady(datetime.timedelta(milliseconds=20000))
arr2 = np.zeros((153600,), dtype=np.float32)
o2[0].read(arr2, o2[0].offset(), o2[0].chunk().byte_size)
print('wrong-feed std=%.4f corr(correct,wrong)=%.4f' % (
    float(arr2.std()), float(np.corrcoef(arr, arr2)[0, 1])), flush=True)
print('DONE', flush=True)
