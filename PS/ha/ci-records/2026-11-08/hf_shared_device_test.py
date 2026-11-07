import sys, types, datetime, time
_stub = types.ModuleType('tokenizers')
class _Tok(object):
    @staticmethod
    def from_file(path):
        raise RuntimeError('stub')
_stub.Tokenizer = _Tok
sys.modules['tokenizers'] = _stub
sys.path.insert(0, '/root/icraft39')
sys.path.insert(0, '/root/qwen2/modelzoo_utils')
sys.path.insert(0, '/root/llm/Qwen3-0.6B/patch')
import numpy as np
import icraft
import icraft.xrt as xrt
import icraft.xir as xir
from pyrtutils.icraft_utils import openDevice, initSession

print('== step1: qwen3 (openDevice once)', flush=True)
model = Q3 = None
import q3_infer_board as Q3M
model = Q3M.IcraftModel(Q3M.ModelConfig())
sm = Q3M.DecodeOnlySessionManager(model)     # openDevice + apply
dev = sm.model.device
print('qwen3 ready, device pid-view ok', flush=True)

print('== step2: hifigan session on the SAME device object (no second openDevice)', flush=True)
net = icraft.xir.Network.CreateFromJsonFile('/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json')
net.lazyLoadParamsFromFile('/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.raw')
# 复用 device：直接 initSession(backend, net, dev, 1)——不调 openDevice
s2 = initSession('zg330', net, dev, 1)
t0 = time.time(); s2.apply(); print('hifigan apply %.1fs' % (time.time()-t0), flush=True)

print('== step3: qwen3 forward (survived?)', flush=True)
kv = sm._prepare_kv_cache(1, sm.model.config.max_decode_length)
try:
    out = sm._forward(np.array([[9707]], dtype=np.float32),
                      np.array([[1,1,0]], dtype=np.float32), kv)
    print('qwen3 fwd OK top=%d' % int(np.argmax(np.asarray(out[0]).reshape(-1))), flush=True)
except Exception as e:
    print('qwen3 fwd FAIL', repr(e)[:200], flush=True)
    sys.exit(1)

print('== step4: hifigan forward', flush=True)
mel = (0.5 + 0.5*np.sin(np.linspace(0,6,600)[:,None]*1.3 + np.linspace(0,1,80)[None,:]*4.0)).astype(np.float32)
inp = xrt.Tensor(np.ascontiguousarray(mel.T), net.ops[0].outputs[0].tensorType())
o = s2.forward([inp])
for t in o: t.waitForReady(datetime.timedelta(milliseconds=20000))
arr = np.zeros((153600,), dtype=np.float32)
o[0].read(arr, o[0].offset(), o[0].chunk().byte_size)
print('hifigan fwd std=%.4f' % float(arr.std()), flush=True)

print('== step5: qwen3 again', flush=True)
out2 = sm._forward(np.array([[1879]], dtype=np.float32),
                   np.array([[1,2,0]], dtype=np.float32), kv)
print('qwen3 fwd2 OK top=%d' % int(np.argmax(np.asarray(out2[0]).reshape(-1))), flush=True)
print('SHARED_DEVICE_MULTI_SESSION_OK', flush=True)
