#!/bin/sh
# 抢核压力测试：视频全开 + ASR(CPU 密集) 并发，测每核与相机影响
echo "== base: camera ready"
curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('ready',d.get('ready'),'frame',d.get('frame_id'))"
echo "== start ASR loop (CPU hog) in background: 4 passes"
python3 - <<'PY' &
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
for i in range(4):
    s = asr.create_stream()
    t0 = time.time()
    s.accept_waveform(sr, audio)
    s.input_finished()
    while asr.is_ready(s):
        asr.decode_stream(s)
    asr.get_result(s)
    print('asr pass %d: %.1fs for 30s audio' % (i, time.time()-t0), flush=True)
print('ASR_LOOP_DONE', flush=True)
PY
ASR_PID=$!
echo "== camera + per-core during ASR (x4 samples)"
for i in 1 2 3 4; do
  sleep 6
  curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  cam frame',d.get('frame_id'),'age',round(d.get('frame_age_s',-1),2))"
done
wait $ASR_PID
echo "== per-core during (retrospective): overall snapshot"
python3 /tmp/percore.py
echo "== camera final"
curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('ready',d.get('ready'),'frame',d.get('frame_id'))"
echo done