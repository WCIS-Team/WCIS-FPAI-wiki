import sys, types, datetime, time, gc
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

dev = openDevice('zg330', '192.168.125.143', True, False)
print('device opened once', flush=True)

def make_session():
    net = icraft.xir.Network.CreateFromJsonFile(
        '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json')
    net.lazyLoadParamsFromFile(
        '/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.raw')
    s = initSession('zg330', net, dev, 1)
    s.apply()
    return net, s

def fwd(net, s):
    mel = (0.5 + 0.5*np.sin(np.linspace(0,6,600)[:,None]*1.3
                           + np.linspace(0,1,80)[None,:]*4.0)).astype(np.float32)
    inp = xrt.Tensor(np.ascontiguousarray(mel.T), net.ops[0].outputs[0].tensorType())
    o = s.forward([inp])
    for t in o: t.waitForReady(datetime.timedelta(milliseconds=20000))
    a = np.zeros((153600,), dtype=np.float32)
    o[0].read(a, o[0].offset(), o[0].chunk().byte_size)
    return a

# 循环：建 session → forward → 释放 → 重建（3 轮），模拟动态 load/unload
for cycle in range(3):
    net, s = make_session()
    a = fwd(net, s)
    print('cycle %d std=%.4f peak=%.3f' % (cycle, float(a.std()), float(np.max(np.abs(a)))), flush=True)
    del s, net
    gc.collect()
    time.sleep(1)
print('RELOAD_CYCLES_OK', flush=True)
