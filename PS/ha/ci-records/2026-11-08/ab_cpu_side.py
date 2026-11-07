import numpy as np
import onnxruntime as ort
import subprocess

# 从板上取两个 npy
subprocess.run(['scp', '-q', 'root@192.168.1.113:/tmp/ab_mel600.npy',
                r'S:\work\WCIS\workenv\migrate-real-preview\ab_mel600.npy'], check=True)
subprocess.run(['scp', '-q', 'root@192.168.1.113:/tmp/ab_npu_wave.npy',
                r'S:\work\WCIS\workenv\migrate-real-preview\ab_npu_wave.npy'], check=True)

mel600 = np.load(r'S:\work\WCIS\workenv\migrate-real-preview\ab_mel600.npy')
npu = np.load(r'S:\work\WCIS\workenv\migrate-real-preview\ab_npu_wave.npy').ravel()
print('mel600', mel600.shape, 'npu', npu.shape, 'npu std %.4f peak %.4f'
      % (npu.std(), np.abs(npu).max()))

so = ort.InferenceSession(r'S:\work\WCIS\workenv\.tmp_matcher\hifigan\hifigan_v2.onnx',
                          providers=['CPUExecutionProvider'])
inp = so.get_inputs()[0]
print('onnx input', inp.name, inp.shape)
cpu = so.run(None, {inp.name: mel600.T[None].astype(np.float32)})[0].ravel()
print('cpu', cpu.shape, 'std %.4f peak %.4f' % (cpu.std(), np.abs(cpu).max()))

n = min(len(npu), len(cpu))
c = float(np.corrcoef(npu[:n], cpu[:n])[0, 1])
print('=== CORR(NPU, CPU) = %.4f  (n=%d)' % (c, n))
# 分段相关系数（避免局部错位掩盖）
segs = []
for i in range(0, n, n // 6):
    s = np.corrcoef(npu[i:i + n // 6], cpu[i:i + n // 6])[0, 1]
    segs.append(round(float(s), 3))
print('segment corrs:', segs)
# 逐位绝对误差
d = np.abs(npu[:n] - cpu[:n])
print('maxabs=%.4f meanabs=%.5f  rel=%.3f%%' % (d.max(), d.mean(), 100 * d.mean() / (np.abs(cpu[:n]).mean() + 1e-9)))
print('PASS' if c >= 0.95 else 'FAIL (threshold 0.95)')
