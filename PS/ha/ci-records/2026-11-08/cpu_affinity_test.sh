#!/bin/sh
# 决定性对比：taskset 隔离 vs 自由抢占（同负载 4 线程 ASR + 视频）
echo "== A) 无隔离（自由抢占）基线重测"
python3 - <<'PY'
import numpy as np, time, glob, os
import sherpa_onnx
MODEL_DIR = '/mnt/data/lang/asr/models/sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30'
files = {os.path.basename(p): p for p in glob.glob(MODEL_DIR + '/*.onnx')}
asr = sherpa_onnx.OnlineRecognizer.from_transducer(
    tokens=MODEL_DIR + '/tokens.txt',
    encoder=files.get('encoder.int8.onnx'),
    decoder=files.get('decoder.onnx'),
    joiner=files.get('joiner.int8.onnx'),
    num_threads=4, sample_rate=16000, feature_dim=80)
sr = 16000
t = np.linspace(0, 30, sr*30, dtype=np.float32)
audio = (0.3*np.sin(2*np.pi*220*t)).astype(np.float32)
s = asr.create_stream()
t0 = time.time()
s.accept_waveform(sr, audio); s.input_finished()
while asr.is_ready(s): asr.decode_stream(s)
asr.get_result(s)
print('noAffinity rtf=%.2f' % ((time.time()-t0)/30), flush=True)
PY
echo "== camera during A (5s x3)"
for i in 1 2 3; do sleep 1; curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  age',round(d.get('frame_age_s',-1),2),'frame',d.get('frame_id'))"; sleep 4; done
echo "== B) taskset 隔离：ASR 钉 cpu2-3，视频留给 0-1"
# 找到 serve_photos/camera_owner 当前 pid，绑定到 cpu0-1
for pat in serve_photos camera_owner wcis_camera_own; do
  for p in $(pgrep -f "$pat" | head -1); do taskset -pc 0-1 $p >/dev/null 2>&1 && echo "  pinned $pat($p) -> 0-1"; done
done
echo "--- ASR 钉 2-3 跑同负载"
taskset -c 2-3 python3 - <<'PY'
import numpy as np, time, glob, os
import sherpa_onnx
MODEL_DIR = '/mnt/data/lang/asr/models/sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30'
files = {os.path.basename(p): p for p in glob.glob(MODEL_DIR + '/*.onnx')}
asr = sherpa_onnx.OnlineRecognizer.from_transducer(
    tokens=MODEL_DIR + '/tokens.txt',
    encoder=files.get('encoder.int8.onnx'),
    decoder=files.get('decoder.onnx'),
    joiner=files.get('joiner.int8.onnx'),
    num_threads=2, sample_rate=16000, feature_dim=80)
sr = 16000
t = np.linspace(0, 30, sr*30, dtype=np.float32)
audio = (0.3*np.sin(2*np.pi*220*t)).astype(np.float32)
s = asr.create_stream()
t0 = time.time()
s.accept_waveform(sr, audio); s.input_finished()
while asr.is_ready(s): asr.decode_stream(s)
asr.get_result(s)
print('affinity rtf=%.2f (2threads on cpu2-3)' % ((time.time()-t0)/30), flush=True)
PY
echo "== camera during/after B"
for i in 1 2 3; do sleep 1; curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  age',round(d.get('frame_age_s',-1),2),'frame',d.get('frame_id'))"; sleep 4; done
echo "== 解除视频进程绑定（恢复自由调度）"
for pat in serve_photos camera_owner wcis_camera_own; do
  for p in $(pgrep -f "$pat" | head -1); do taskset -pc 0-3 $p >/dev/null 2>&1 && echo "  unpinned $pat($p)"; done
done
echo done