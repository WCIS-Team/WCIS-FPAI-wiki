#!/bin/sh
P=$(pgrep -f serve_photos | head -1)
OP=$(pgrep -f camera_owner | head -1)
echo "== 配置：视频钉 cpu0（camera_owner 主负载），ASR 4线程钉 cpu1-2"
taskset -pc 0 $P >/dev/null
[ -n "$OP" ] && taskset -pc 0 $OP >/dev/null
f1=$(curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;print(json.load(sys.stdin).get('frame_id'))")
t1=$(date +%s.%N)
echo "== ASR 4线程（钉 cpu1-2）跑 30s 音频，期间测相机"
taskset -c 1-2 python3 - <<'PY'
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
print('ASR rtf=%.2f (4t on cpu1-2, video on cpu0)' % ((time.time()-t0)/30), flush=True)
PY
t2=$(date +%s.%N)
f2=$(curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;print(json.load(sys.stdin).get('frame_id'))")
python3 -c "print('video fps during ASR=%.1f' % (($f2-$f1)/($t2-$t1)))"
curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  age=%.2f'%(d.get('frame_age_s',-1)))"
echo "== 解除绑定"
taskset -pc 0-3 $P >/dev/null
[ -n "$OP" ] && taskset -pc 0-3 $OP >/dev/null
echo done