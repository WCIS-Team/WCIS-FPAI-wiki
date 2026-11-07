#!/bin/sh
# 抢核复现实验：复刻决策记录的条件——ASR 多线程（当年 VAD 4 线程炸的模式）
echo "== 视频（cam+owner）开着，ASR num_threads=4（当年出事配置）"
python3 - <<'PY'
import numpy as np, time, glob, os
import sherpa_onnx
MODEL_DIR = '/mnt/data/lang/asr/models/sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30'
files = {os.path.basename(p): p for p in glob.glob(MODEL_DIR + '/*.onnx')}
for nt in (1, 4):
    asr = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=MODEL_DIR + '/tokens.txt',
        encoder=files.get('encoder.int8.onnx'),
        decoder=files.get('decoder.onnx'),
        joiner=files.get('joiner.int8.onnx'),
        num_threads=nt, sample_rate=16000, feature_dim=80)
    sr = 16000
    t = np.linspace(0, 30, sr*30, dtype=np.float32)
    audio = (0.3*np.sin(2*np.pi*220*t)).astype(np.float32)
    ts = []
    for rep in range(2):
        s = asr.create_stream()
        t0 = time.time()
        s.accept_waveform(sr, audio)
        s.input_finished()
        while asr.is_ready(s):
            asr.decode_stream(s)
        asr.get_result(s)
        ts.append(time.time()-t0)
    print('threads=%d rtf=%.2f/%.2f (30s audio)' % (nt, ts[0]/30, ts[1]/30), flush=True)
# 相机并行健康
import urllib.request
d = json.loads(urllib.request.urlopen('http://127.0.0.1:8092/api/status', timeout=5).read())
print('cam ready', d.get('ready'), 'frame', d.get('frame_id'), 'age', round(d.get('frame_age_s', -1), 2))
PY
echo "== camera realtime during heavy ASR (30s window)"
( sleep 2; for i in 1 2 3 4 5; do curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  cam frame',d.get('frame_id'),'age',round(d.get('frame_age_s',-1),2))"; sleep 6; done ) &
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
t = np.linspace(0, 60, sr*60, dtype=np.float32)
audio = (0.3*np.sin(2*np.pi*220*t)).astype(np.float32)
s = asr.create_stream()
t0 = time.time()
s.accept_waveform(sr, audio)
s.input_finished()
while asr.is_ready(s):
    asr.decode_stream(s)
asr.get_result(s)
print('heavy4t: %.1fs for 60s audio (rtf=%.2f)' % (time.time()-t0, (time.time()-t0)/60), flush=True)
PY
wait
echo done