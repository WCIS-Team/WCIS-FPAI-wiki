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
import q3_infer_board as Q3M
from pyrtutils.icraft_utils import openDevice, initSession

# K128 图
cfg = Q3M.ModelConfig()
cfg.decode_json = '/root/qwen3/jr_path/decode_k128/Q3K128-decoder_ZG.json'
cfg.decode_raw = '/root/qwen3/jr_path/decode_k128/Q3K128-decoder_ZG.raw'

print('== step1: qwen3 K128 session', flush=True)
model = Q3M.IcraftModel(cfg)
model.load_model()
dev = openDevice('zg330', '192.168.125.143', True, False)
model.init_device(dev)
sm = Q3M.DecodeOnlySessionManager.__new__(Q3M.DecodeOnlySessionManager)
sm.model = model
sm.model.device = dev
sm.decode_network = model._load_network(cfg.decode_json, cfg.decode_raw)
sm.decode_session = initSession('zg330', sm.decode_network, dev, 1)
sm.decode_session.apply()
# _init_decode_network 的完整替代：kv_dtype 从 prefill 网络第四输出拿
sm.kv_dtype = sm.decode_network.ops[0].outputs[2].tensorType()
print('qwen3 K128 applied, kv_dtype ok', flush=True)

print('== step2: hifigan session on same device', flush=True)
net = icraft.xir.Network.CreateFromJsonFile('/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.json')
net.lazyLoadParamsFromFile('/mnt/data/lang/tts/models/vocoder/hifigan_v2_ZG/hifigan_v2_ZG.raw')
s2 = initSession('zg330', net, dev, 1)
s2.apply()
print('hifigan applied', flush=True)

print('== step3: qwen3 fwd', flush=True)
kv = sm._prepare_kv_cache(1, cfg.max_decode_length)
out = sm._forward(np.array([[9707]], dtype=np.float32),
                  np.array([[1,1,0]], dtype=np.float32), kv)
print('q3 top=%d' % int(np.argmax(np.asarray(out[0]).reshape(-1))), flush=True)

print('== step4: hifigan fwd', flush=True)
mel = (0.5 + 0.5*np.sin(np.linspace(0,6,600)[:,None]*1.3 + np.linspace(0,1,80)[None,:]*4.0)).astype(np.float32)
inp = xrt.Tensor(np.ascontiguousarray(mel.T), net.ops[0].outputs[0].tensorType())
o = s2.forward([inp])
for t in o: t.waitForReady(datetime.timedelta(milliseconds=20000))
a = np.zeros((153600,), dtype=np.float32)
o[0].read(a, o[0].offset(), o[0].chunk().byte_size)
print('hf std=%.4f' % float(a.std()), flush=True)

print('== step5: qwen3 fwd again', flush=True)
out2 = sm._forward(np.array([[1879]], dtype=np.float32),
                   np.array([[1,2,0]], dtype=np.float32), kv)
print('q3#2 top=%d' % int(np.argmax(np.asarray(out2[0]).reshape(-1))), flush=True)
print('K128_SHARED_OK', flush=True)
