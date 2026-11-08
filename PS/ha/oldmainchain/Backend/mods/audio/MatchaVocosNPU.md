---
tags: [Matcha, Vocos, NPU, TTS]
updated: 2026-10-31
---

# MatchaVocosNPU

> **本页记什么**：matcha-icefall-zh-baker（声学模型）+ vocos-22khz-univ（声码器）这条中文 TTS 链路，**在悟净板 ZG330 NPU 上能不能跑、跑出来对不对**。只写**已验证成立的做法**，按图索骥即可。
>
> 证据等级：**A** = 板上/本机实测且命令可复现；**B** = 厂商文档；**D** = 未验证。
>
> ## 📦 可复现内容全部搬到代码仓了
>
> **脚本、编译配方、逐算子读数、各组件详细坑清单** → **`repos/lang/tts/`**
>
> | 目录 | 是什么 |
> |---|---|
> | `repos/lang/tts/README.md` | **层级关系总图**（谁和谁同层）、五个通用坑、量化口径 |
> | `repos/lang/tts/sherpa/sherpa-mel/` | 前端 / mel 来源（★ `debug=True` 取 token） |
> | `repos/lang/tts/sherpa/matcha/` | 声学模型（CPU）＋ token 流调查 |
> | `repos/lang/tts/sherpa/vocos/` | 声码器（频域），`int8/` `fp16/` |
> | `repos/lang/tts/sherpa/HiFi-GAN/` | 声码器（时域），`rewrite-5op/` `hifigan-prelu/` |
> | `repos/lang/tts/sherpa/VITS/piper/` | 单体 VITS 为什么跑不动 |
> | `repos/lang/tts/sherpa/VITS/vits-others/` | 其余 VITS 候选（编译全失败） |
> | `repos/lang/tts/ekho-linux/` | 录音拼接（现役） |
> | `repos/lang/tts/bench-cpu/` | 板端 CPU-only 基准口径 |
>
> **本页只留结论、读数与判据；要跑，去那个仓。**

## 1. 两个模型各自是什么（先分清职责）

| 模型 | 类型 | 输入 | 输出 | 体积 | 节点 |
|---|---|---|---|---:|---:|
| `matcha-icefall-zh-baker` | **声学模型** | 音素序列 `x` ＋ `x_length` ＋ `noise_scale` ＋ `length_scale` | **mel 谱**（80 维 × 帧数） | 75.6 MB | 4802 |
| `vocos-22khz-univ` | **声码器** | mel 谱 `[batch, 80, time]` | **mag ＋ cos ＋ sin**（频域三分量，**不是波形**） | 53.9 MB | 272 |

**关键认知**：vocos 输出的是 `mag`（幅度）、`x=cos(相位)`、`y=sin(相位)`，**真正的波形要靠 iSTFT 在模型外重建**。所以「vocos 上 NPU」只省掉声码器那一段，前端的音素化与后端的 iSTFT 仍在 CPU。

## 2. 板上实测的 NPU 性能（成立的数）

`vocos_native_ZG.json/.raw`（iCraft 3.39.0 generate 段产物）在悟净板上跑：

```bash
icraft-run --json vocos_native_ZG.json --raw vocos_native_ZG.raw --network vocos \
  --input <4D输入> \
  --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" \
  --dump_output --log_time
```

**三次实测**（时间读数极稳）：

| 次 | total_time | **total_hard_time** | total_backbone |
|---|---:|---:|---:|
| 1 | 23.520 ms | **9.503 ms** | 8.119 ms |
| 2 | 23.438 ms | **9.501 ms** | 8.120 ms |
| 3 | 20.704 ms | **9.499 ms** | 8.118 ms |

**设备身份**（日志原文）：

```text
Device Protocol: axi          Device Name: zg330aiu
icore: FMSHZGV3TECH-AID - 24160628      device: 25122301
```

**与 CPU 对比**（同一输入 `[1,80,559]`，板上 4×A53、onnxruntime 2 线程）：

| | 耗时 |
|---|---:|
| CPU onnxruntime | **2487 ms** |
| NPU ZG330 | **9.5 ms（硬件段）／20.7–23.5 ms（整轮）** |

**逐算子硬件时间分布**：`Matmul` 23 个共 4.09 ms（最大头）、`Transpose` 43 个 1.54 ms、`LayerNorm` 10 个 0.73 ms、`Conv2d` 9 个 0.45 ms、`Exp` 1 个 0.28 ms、`Cos`/`Sin` 各 1 个 0.05/0.06 ms（**`Reshape` 51 个为 0 ms，纯数据搬运**）。

## 3. 端到端能省多少 CPU（成立的估算）

把两组独立实测拼起来（不混跑，因为板上 py3.8 无 onnxruntime）：

| 场景 | matcha（CPU） | vocos（CPU） | 两段全 CPU | **vocos→NPU** | 相对实时 | 省时 |
|---|---:|---:|---:|---:|:---|---:|
| 短句 20 音素 | 1730 ms | 905 ms | **1.129** | **0.753** | 快 1.33× | 33.4% |
| 中句 60 音素 | 4504 ms | 2487 ms | **1.107** | **0.716** | 快 1.40× | 35.2% |
| 长句 150 音素 | 12211 ms | 6268 ms | **1.173** | **0.777** | 快 1.29× | 33.8% |

**读法**：vocos 只占两段总耗时的 33–36%，把它移走就把整条链从「慢于实时 11–17%」拉到「快于实时 29–40%」。**边界**：这是两个网络的纯推理之和，不含前端音素化与 iSTFT。

## 4. 取 NPU 真实输出数值的正确做法

**唯一可靠的两个入口**（两条路径结果**逐位相同**，`max|d|=0`）：

### 4.1 命令行（最快）

```bash
icraft-run --json <model>_ZG.json --raw <model>_ZG.raw --network <name> \
  --input <输入> --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" \
  --dump_format HQB --dump_output --log_path ./out
```

**必须同时给 `--dump_format` 和 `--dump_output`**；只给前者导出的是量化 scale 表。
产物在 `<log_path>/<network>/ftmpHQB/<v_id>.ftmp`。

**校验 dump 可信的判据**（已知答案测试）：dump **输入张量**（`--dump_ftmp 0`），拿它与自己提供的输入文件逐字节比：

```python
np.array_equal(dumped_float32, source_input)   # 必须为 True
```

### 4.2 Python API（要自己控制输入时）

```python
import numpy as np
from icraft import xir, xrt, host_backend
from icraft.zg330backend import ZG330Backend

net = xir.Network.CreateFromJsonFile(JSON)
net.autoLoadParams(RAW)                        # 必须：只 CreateFromJsonFile 不加载参数
in_tt = net.ops[0].outputs[0].tensorType()     # 取 InputNode，不是 HardOp

dev  = xrt.Device.Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000")
sess = xrt.Session.Create([ZG330Backend, host_backend.HostBackend],
                          net.view(0), [dev, xrt.HostDevice.Default()])
sess.apply()
inp = xrt.Tensor(np.ascontiguousarray(x, np.float32), in_tt)
outs = sess.forward([inp])
for t in outs:
    h = t.to(xrt.HostDevice.MemRegion())       # 必须搬回 host 才能读
    nb = h.dtype().bytes(); buf = bytearray(nb); h.read(buf, 0, nb)
    v = np.frombuffer(bytes(buf), dtype=np.float32)
```

**三个必要条件**：① `autoLoadParams(.raw)`；② 输入 TensorType 取 `net.ops[0].outputs[0]`；③ 双后端 `[ZG330Backend, HostBackend]`（`HardOp` 只能 ZG330 接、`Input`/`Output` 只能 Host 接）。

## 5. 输入张量的正确形状与排布

网络输入声明 **`[1, 1, 600, 80]`**（NHWC：`N=1, H=1, W=时间, C=mel 维=80`）。

**mel 文件的存法**（板上 `golden_mel.bin` 实测）：是 **`(80 mel, 559 frame)`** C 序，**直接 `reshape(80, 559)`，不要转置**。

```python
mel = np.fromfile("mel.bin", np.float32).reshape(80, T)   # 不转置
# 给 CPU onnxruntime：要 [1,80,T]
cpu_in = mel[None].astype(np.float32)
# 给 icraft：要 NHWC [1,1,600,80]
pad = np.zeros((max(600, T), 80), np.float32)
pad[:T, :] = mel.T
npu_in = pad.reshape(1, 1, pad.shape[0], 80)
```

**校验排布是否正确的判据**（很强）：拿同一份 mel 喂 **CPU onnxruntime**，输出 `mag` 与 golden 的相关性应为 **1.000000**。若只有 0.0167 左右，就是排布反了。

## 6. 生成 mel 用的参数（两个旋钮，别搞反）

**`matcha` 是概率模型**：`noise_scale > 0` 时**每次生成都不同**（实测 `ns=0.667` 连跑两次 `corr=0.954`、`ns=1.0` 时 `0.920`；**`ns=0.0` 时两次逐字节相同**）。

- **要做 CPU vs NPU 的 A/B，必须 `noise_scale=0`**，否则两边喂的 mel 不是同一个样本，比对无意义。
- 日常合成保持默认 `noise_scale=0.667`（音质更自然），但那**不能**用于数值验证。

**`length_scale` 决定语速与时长。sherpa 的默认就是 `1.0`，不要改**：

| `length_scale` | 时长（同一文本） | 相对默认 |
|---:|---:|---:|
| **1.0（默认，正确）** | **5.24 s** | 1.00 |
| 1.5 | 7.91 s | 1.51 |
| 2.0 | 10.55 s | 2.01 |
| 2.3 | 12.13 s | 2.31 |

**判据**：把 `length_scale` 调大不会「变清楚」，只会**把每个音节拉长**；倍数超过约 1.3 就会听成叠字（「你你你、好好好」）。这是**最容易踩的一个坑**，而且症状（叠字）会让人误以为是模型坏了。

**交叉核对方法**（不要用时长反推，会搞反）：时长 ≈ 帧数 × hop / sr。sherpa 5.23 s 的音频按 `n_fft=1024/hop=256/center=1` 反推是 **447 帧**；`ls=1.0` 下 22 音节得 **198 帧**（2.30 s）。**两者对不上说明 token 流本身不同**（见 §8.1），**不是** `length_scale` 设小了——此时**不该**去动 `length_scale`。

**正确入口**（sherpa 自己的前端，唯一听感正常的链路；注意**不要传 `length_scale`**）：

```python
import sherpa_onnx
mc = sherpa_onnx.OfflineTtsMatchaModelConfig(
    acoustic_model=".../matcha-icefall-zh-baker/model-steps-3.onnx",
    vocoder=".../vocos-22khz-univ.onnx",
    tokens=".../tokens.txt", lexicon=".../lexicon.txt",
    dict_dir=".../dict", noise_scale=0.667)   # 不要传 length_scale，默认 1.0 才对
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(
    model=sherpa_onnx.OfflineTtsModelConfig(matcha=mc, num_threads=2)))
audio = tts.generate("你好，我是你的语音助手。", sid=0, speed=1.0)
sherpa_onnx.write_wave("out.wav", audio.samples, audio.sample_rate)
```

**这条链路出来的 wav 是唯一听感正常的一份**（板/校机实测，5.23 s、peak 0.99、rms 0.098、非静音 71.9%）。

## 7. vocos 的 iSTFT 参数（正本，来自模型 metadata）

`vocos-22khz-univ.onnx` 自带的 15 条 metadata 里给了确切参数：

```text
model_type = vocos        sample_rate = 22050
n_fft = 1024              hop_length = 256
win_length = 1024         window_type = hann
center = 1                pad_mode = reflect
normalized = 0
```

**重建公式**：`re = mag*cos`、`im = mag*sin` → 单边谱补共轭 → 逆变换 → 加权重叠相加（`sum(win*win)` 归一化），并按 `center=1` 两端各裁掉 `n_fft//2`。

**窗口必须用周期 Hann**（`0.5 - 0.5*cos(2πn/N)`），不是 `np.hanning`（对称版）：两者差一个采样点，用错会让重叠相加的归一化前提（`Σwin = 常数`）不再成立，**输出不可懂**。

**iSTFT 是否可信，用往返验证**（不要凭听感判断）：

```python
S = stft(x);  y = istft(S, length=x.size)
assert np.abs(x - y).max() / np.abs(x).max() < 1e-12    # 实测 3.357e-16
```

**实测**：在一段 5.23 s 的 22050 Hz 真实语音上，往返 `max|err| = 3.331e-16`、相对 `3.357e-16` ⇒ **iSTFT 本身完全正确**，任何"听不清"都不该记在这个环节头上。

**关于 `center=1` 与 `pad_mode=reflect`**：分析端在信号两端做反射补 `n_fft//2`，重建端重叠相加后**把这两段的上下文裁掉**，才能得到与原信号同长的波形；不裁会多出 `n_fft` 长度并让首尾相位错位。

## 8. 实测结论：**int8 相位不可用，fp16 可用**（本轮最终结论）

### 8.0 **两行结论先说**

| 量化 | mag | cos | sin | 波形 vs CPU | 硬件段 | 能用？ |
|---|---:|---:|---:|---:|---:|:--|
| **int8** | 0.8959 | 0.1198 | 0.1219 | 0.1861 | **9.502 ms** | ❌ 相位坏 |
| **fp16** | **0.99868** | **0.73168** | **0.72839** | **0.9625** | **19.209 ms** | ✅ **可用** |

⇒ **vocos 上 NPU 是可行的，但必须用 `--qdtype fp16`**（`icraft-quantize --qdtype fp16`，**不用校准集**），五个阶段全 `rc=0`。代价：模型 18.7 MB → **31.3 MB**、硬件段 **2.02×**（19.2 ms）。**即使 2 倍，仍比 CPU 的 2487 ms 快约 129 倍。**

### 8.0b **板端 RTF 实测（三次极稳）**

| 项 | int8 | **fp16** |
|---|---:|---:|
| `total_hard_time`（3 次） | 9.497／9.500／9.501 ms | **19.291／19.284／19.286 ms** |
| 相对 int8 | 1.00× | **2.03×** |
| 相对 CPU（vocos 2487 ms） | 快 262× | **快 129×** |
| 模型体积 | 18.7 MB | **31.3 MB** |

**命令**（板上；`--log_time` 才写 run_time.log）：

```bash
icraft-run --json fp16/vocos_ZG.json --raw fp16/vocos_ZG.raw --network vocos \
  --input io/NPU_in_1_1_600_80.bin \
  --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" \
  --dump_format HQB --dump_output --log_time --log_path ./rt
```

### 8.0c **真实中文句子样例（4 句，CPU/NPU 各一套）**

交付位置：**`C:\Users\takomi\Desktop\klar-matcha-samples\npu\`**（说明见同目录 `_说明.md`）。

| 编号 | 句子 | 时长 |
|---|---|---:|
| 01_问候 | 你好，我是你的语音助手。 | 2.28 s |
| 02_天气 | 今天天气不错，适合出去走走。 | 2.94 s |
| 03_数字 | 现在时间是下午三点二十分。 | 2.65 s |
| 04_长句 | 请帮我把客厅的灯关掉，然后打开窗户。 | 3.63 s |

每句三份：`*_cpu.wav`（CPU 参考）／`*_vocos_npu.wav`（NPU fp16 vocos）／`*_hifigan_npu.wav`（NPU HiFi-GAN）。

**这 8 份全部有真实波形**（rms：vocos 0.062–0.109、hifigan 0.047–0.056；非静音占比 57–74%）。

**生成要点（可复现）**：

1. mel **必须由 sherpa 的 matcha 前端生成**（真实中文 → 音素 → mel），`noise_scale=0`（确定性），`length_scale` 逐句调到与 sherpa 原版**等长**（实测 1.86／2.16／1.56／2.08）。
2. **手工按 `lexicon.txt` 拼 token 不可行**——token 数只有 sherpa 的一半、时长对不上（见 §8.6）。
3. NPU 取数**必须走 CLI `--dump_output`**，**不要用 Python `forward`**：后者每次调用复用同一输出缓冲，实测同一进程连续跑 4 句时第 3、4 句输出**全零**（rms=0.0000），第 2–4 句与 CPU 相关降到 0.00（正确应为 0.5–0.9）。
4. 输入形状固定 **`[1,1,600,80]`**；句子超过 600 帧要截断（本次最长 314 帧，未触发）。

### 8.1 int8 的读数（两侧喂**同一份 mel**，CLI `--dump_output` 采集）

**前提**：CPU 参考与板端 NPU **必须是同一个 mel**。曾因为拿错 mel（一方 `48000 = 600×80`、另一方 `36400 = 80×455`）得出过 `mag 0.102` 的假读数 —— **比对前先核 md5，见 §10.1 的对齐检查**。

| 输出 | v_id（原版 / auto） | 语义 | 不同值数 | **corr vs CPU 浮点** |
|---|---|---|---:|---:|
| mag | 796 / 818 | 幅度 | 11 | **0.88509** |
| cos | 800 / 822 | cos(相位) | 38 | **0.12297** |
| sin | 804 / 826 | sin(相位) | 41 | **0.12407** |

**判读**：

- **mag 0.885** ⇒ 幅度谱整体结构对得上（低频轮廓、能量分布方向正确），但只有 **11 个离散值**，几乎没有幅度分辨率。
- **cos/sin 0.123** ⇒ **相位基本无关于 CPU**。iSTFT 要用 `mag*cos`、`mag*sin` 重建复数谱，相位错了整段波形就是噪声 ⇒ **拿这个件出音频不可用**。

**NPU 硬件本身是忠实的**：板端三个输出与 Host 软件参考 **逐位相同**（`max|d|=0`）⇒ 差异在**编译出的量化图**里，不是板子算错。

### 8.2 `--fake_qf` 定案：损失来自量化，不是硬件

| 输出 | 正常量化 | `--fake_qf`（绕过量化截位/饱和） |
|---|---:|---:|
| mag | 0.885 | **0.999** |
| cos | 0.123 | **0.869** |
| sin | 0.124 | **0.872** |

⇒ **一关量化，cos/sin 从 0.12 跳到 0.87**，但这**不代表相位损失仅来自量化**——见 §8.2b，真因在算子执行。

### 8.2b **相位坏掉的真因：`CosNode`/`SinNode` 的量化实现有缺口——板端 `Cos` 输出根本不是角度的函数**

一度判断"角度量化把相位毁了"，**这个判断是错的**，用实测否证：

**先量出真正喂进 `Cos`/`Sin` 的角度**（把 ONNX 里 `/head/Slice_1_output_0` 暴露成图输出跑 CPU）：

```text
真实角度范围 = -149.8404 … +142.1597 rad    （跨度 292 rad）
angle/scale  = -332.7 … +315.6              （scale = 0.45043343）
超出 int8 范围的元素 = 2.41%
```

**再按板端真实规格模拟量化**（`round(a/0.45043343)` 后 clip 到 ±127，再算三角）：

| 假设 | cos corr | sin corr |
|---|---:|---:|
| 浮点（不量化） | 1.0000 | 1.0000 |
| **int8 + clip ±127** | **0.9645** | **0.9711** |
| 先折到 [-π,π] 再量化 | 0.9916 | 0.9916 |
| int8 环绕（不 clip） | 0.9916 | 0.9916 |

**结论**：**光靠角度 int8 量化，cos/sin 仍有 0.96–0.99，不可能掉到板上的 0.123。**

我早先"int8 只有 ±127、角度到 170 rad 所以相位全毁"的推算错在：**cos/sin 是周期函数，int8 环绕恰好是 2π 的整数倍，绕回后大致仍对**——不该把"溢出"直接等同于"相位错误"。

**板上的 0.123 另有其因**：把板端 cos 输出（38 个唯一值）去拟合"真实角度 → 圆周 256 步"，命中率只有 **0.4%–4.9%**（≈1/256 的随机水平）；且同一个 int8 code 分箱内板端 x 有 **36 个不同值**、同一个 x 值又出现在 `-128…-121` 各 code 上 ⇒ **板端的 `Cos` 不是角度的函数**。

**厂商侧的机制**（量化日志与图规格逐位吻合）：

```text
CosNode/SinNode  ZhugeQuantParams Not Implemented! Using Default Imeplementation!
                 SetQuantizedScale  Not Implemented!
gen ZG 里喂 Cos 的 int8 角度张量（v_id 2071/2144）：
   @scales([axis=-1]600*0.49766457)   ← 名义 600 个 per-column scale，实际全是同一常数
   该图声明的是 0.45043343             ← 差 10.4%
板端实测角度输出：恰好 256 级、跨 ±63.69、步长 0.4975  ← 与常数逐位吻合
```

⇒ **这是 iCraft 3.39.0 的 `CosNode`/`SinNode` 量化实现缺口**：
> ① 量化参数未实现（`ZhugeQuantParams Not Implemented`），scale 被写成常数 `0.49766457`（声明 `0.45043343`，差 **10.4%**）；
> ② 更严重的是**输出与输入脱钩**——板端同一 int8 code 分箱内 x 有 36 个不同值，同一 x 又出现在多个 code 上，与"真实角度→圆周 256 步"的命中率仅 **0.4%–4.9%**（≈1/256 随机水平）。
>
> **所以准确的说法是"`Cos` 算错了"，不是"角度被量化得太粗"**——后者实测仍能给出 0.96–0.99 的相关。
> 不是我们的图有问题、也不是 NPU 硬件算错。

### 8.2c **把三角搬出图也失败**（已实测）

做法：删掉图里的 `Cos`/`Sin`，把**未包裹角度**作为第 4 个 `@fp(32)` 输出暴露出来，让板端 ARM 用 float 算三角。

**结果**：五段 `rc` 全 0、板上 `rc=0`，**但角度输出仍是 256 级 / ±63.7 / 步长 0.5**，`cos corr = 0.1060` ⇒ **仍是随机相位**。

⇒ **换输出形式救不了那个量化规格**——坏的根在"角度张量被量化成常数 scale"，不在"三角在哪里算"。**这条路在本工具链上不成立。**

### 8.3 `--mix_precision` 实测：**auto 与自定义 CSV 都无效**

**A. `--mix_precision=auto`**：五段全 `rc=0`，图 189→214 op，但：

| 输出 | 原量化 | **auto** | 变化 |
|---|---:|---:|---:|
| mag | 0.88509 | **0.89791** | +0.013 |
| cos | 0.12297 | **0.12214** | −0.001 |
| sin | 0.12407 | **0.12340** | −0.001 |

两个模型的 mag 互相 `corr = 0.971` ⇒ `auto` 只微调参数，**没改变本质**。诸葛默认策略（`cosimilarity + lstm`）**没把 `Cos`/`Sin` 识别为敏感层**。

**B. 自定义 `mix.csv` 给 `Cos`/`Sin` 单独 fp16**（agent 实测）：CSV 格式是

```csv
op_id,op_type,dtype,value_range_in_bits,saturation,per,order
142,icraft::xir::CosNode,fp16,16;16,ems;ems,channel;tensor,3
143,icraft::xir::SinNode,fp16,16;16,ems;ems,channel;tensor,-
```

字段名是 **`op_type`**（不是文档正文写的 `type`），且**必须列全网络 132 行**（131 op + 表头）。这个格式不是猜的——它就是量化器自己在 `mix_precision=auto` 时写出的 `*_quantize_mix_config.csv`。

| 变体 | mag | cos | sin | 五段 rc | 硬件段 |
|---|---:|---:|---:|:--|---:|
| 原版 int8 | 0.88509 | 0.12297 | 0.12407 | 全 0 | 9.502 ms |
| A：仅 `Cos`/`Sin` 两个算子 fp16 | 0.89791 | **0.12171** | **0.12387** | 全 0 | 13.68 ms |
| E：角度路径 5 个算子（136/137/192/142/143）fp16 | 0.90610 | **0.12381** | **0.12483** | 全 0 | 12.87 ms |
| F：同 E 但 fp32 | — | — | — | **板上失败** | — |

F 失败原文：`Op is NOT bound to any backend, op_id = 137, type_key = icraft::xir::TransposeNode` ⇒ **fp32 不可用，fp16 是能上板的上限**。

⇒ **在 `Cos`/`Sin` 上堆精度，原理上打不中目标**（A、E 两档、两个粒度，全落在 0.121–0.124）。


### 8.4 scale 那个数怎么看（**不是"长度量纲"**）

`Cos`/`Sin` 的输入角度在 ZG 图里是 `sint8` + `@scales([axis=-1]600*0.45043343)`。

**先纠正一个误读**：格式是 `@scales([axis=-1]600*0.45043343)` ⇒ **沿 `axis=-1` 有 600 个通道、每通道 scale = 0.45043343**。这里的 `600` 是 `shape=[1,513,600]` 最后一维的长度（时间帧数），**不是"长度量纲"**，和弧度无关。

**真正值得看的是 `0.45043343` 这个值与相邻张量的对比**：

| 张量 | 语义 | scale | 覆盖范围（`127×scale`） | 是否够 |
|---|---|---:|---:|:--|
| `v_id=367` | **角度**（喂 Cos/Sin） | **0.45043343** | **±57.2 rad** | 真实到 ±150 rad，**溢出 2.41%** |
| `v_id=373` | cos 输出 | 0.007862388 | ±0.998 | ✅ 正好覆盖 [-1,1] |
| `v_id=375` | sin 输出 | 0.007862326 | ±0.998 | ✅ 同上 |

**输出层的 scale 精确匹配值域（0.00786 ≈ 1/127），说明量化器本身会按值域算 scale**；角度那一路却只覆盖 ±57 rad 而真值到 ±150 rad ⇒ **量化器对"周期量"没有做角度规约**。

这对应量化日志的原话：

```text
icraft::xir::CosNode ZhugeQuantParams Not Implemented! Using Default Imeplementation!
icraft::xir::SinNode ZhugeQuantParams Not Implemented! Using Default Imeplementation!
```

⇒ **诸葛后端没有为 `Cos`/`Sin` 定义专属量化参数（没有实现），走了通用兜底**。这是**实现缺口**，不是刻意设计。

**但注意**（见 §8.2b）：即便按这个 scale 做 int8 量化，cos/sin 仍有 **0.96–0.99**（周期量的环绕恰好抵消）。**板上 0.123 的锅不在 scale，在算子执行读到错缓冲。**

### 8.5 可听的对照

**当前有效交付（2026-11-01，她试听确认可用）**：`C:\Users\takomi\Desktop\klar-matcha-samples\npu2\`，4 句真实中文 × 3 份，见 §8.7 表与同目录 `_说明.md`。**以这批为准，下面 `.tmp_matcher/` 里的旧件只作过程记录。**

| 文件 | 说明 |
|---|---|
| `C:\Users\takomi\Desktop\klar-matcha-samples\npu2\*_vocos_npu.wav` | ✅ **当前交付**：NPU fp16 合成，4 句 vs CPU 相关 **0.969–0.978** |
| `C:\Users\takomi\Desktop\klar-matcha-samples\npu2\*_cpu.wav` | CPU 参考（同一份 sherpa mel） |
| `C:\Users\takomi\Desktop\klar-matcha-samples\npu2\*_hifigan_npu.wav` | ✅ **成立**：NPU vs **hifigan** CPU **0.9984–0.9997**（见 §8b.3） |
| `S:\work\WCIS\workenv\.tmp_matcher\wav_angle\npu_fp16.wav` | 过程件：早期 fp16 合成，波形 vs CPU `0.9625` |
| `S:\work\WCIS\workenv\.tmp_matcher\wav_angle\npu_int8.wav` | 过程件：NPU int8，`0.1861`，**听感是噪声** |
| `S:\work\WCIS\workenv\.tmp_matcher\wav_real\F_ns0_ls1.wav` | 过程件：sherpa 原生链路，确定性可复现 |

**措辞纠正**：上一版这里写"没有任何一份 NPU 参与且能听懂"——**已作废**。**fp16 那条产出的 `npu_fp16.wav` 是 NPU 真参与、波形 0.9625 的可听音频。**

**fp16 相位质量**（剥掉 ±2π 后）：平均误差 **22.5°**，78.1% 的点 <30°；int8 对照平均 **81.1°**。

### 8.6 mel 来源**已解决**：不自己拼，直接读 sherpa 自己打印的 token（D-1793547016）

> 本节 2026-11-01 整段改写。原写"手工复现 sherpa 的 mel 没做成"——**问题不在 mel，在于我一直在手工拼 token**。

**正解只有一句**：把 sherpa-onnx 升到 **2.0.1**，打开它自带的 debug，让它把 token 序列**打印出来照抄**。

```python
mc = sherpa_onnx.OfflineTtsModelConfig(matcha=..., num_threads=1, debug=True)
tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=mc, max_num_sentences=1))
tts.generate(TEXT, sid=0, speed=1.0)     # stderr 里会打出 tokens 与 final IDs
```

实测输出（`"你好，我是你的语音助手。"`）：

```text
Sentence 0 tokens: [ni2(1116), hao3(597), ,(2), wo3(1737), shi4(1518), ni3(1117),
                    de(314), yu3(1872), yin1(1845), zhu4(1993), shou3(1522), .(3)]
Sentence 0 final IDs (25): [1, 1116, 1, 597, 1, 2, 1, 1737, 1, 1518, 1, 1117, 1, 314,
                            1, 1872, 1, 1845, 1, 1993, 1, 1522, 1, 3, 1]
```

**三处此前一直搞错的**：

| # | 错在哪 | 正确做法 |
|---|---|---|
| 1 | 「你」按 lexicon 查是 `ni3`(1117) | **`ni2`(1116)**——变调，逐字查表必错 |
| 2 | 标点被丢掉 | **`,`(2) 与 `.`(3) 本身是 token**，要送进去 |
| 3 | 直接送音节 | **每个 token 之间插 `pad=1`**（`add_blank`，n 个 → `2n+1`） |

**`length_scale` 不用动**：实测默认 `OfflineTtsMatchaModelConfig.length_scale = 1.0`、`noise_scale = 1.0`；`OfflineTtsConfig.silence_scale = 0.2`。**为凑时长把它调到 1.86／2.3 是错的**，那是在用错参数掩盖 token 数不对。

**版本差异要知道**：本地原装是 **1.13.8**，`debug=True` 只打句子切分（`Number of sentences: 2`）；**2.0.1** 才打 token 与 final IDs。装法用 `pip --target` 到独立目录，**不要动现役 ASR venv**。

### 8.7 正确的端到端流水线（本轮交付用的就是这条）

```text
文本
 └─ sherpa 2.0.1 (debug=True)  →  打印 final IDs        ← 前端由 sherpa 提供，我不实现
     └─ matcha ONNX (CPU)      →  mel [80,T]
         ├─ CPU  vocos  → mag/cos/sin → iSTFT → wav     ← 参考
         └─ NPU  vocos  → mag/cos/sin → iSTFT → wav     ← 19.29 ms
```

**取数纪律**：NPU 一律走 CLI `--dump_output`（`--dump_format HQB`），**逐句一次**。Python `xrt.Session.forward` 在同一进程里连续调用会**首句正常、其余全零**（本轮 4 句里 3 句 `rms=0.0000`），根因是复用输出缓冲且未保证 4096 字节物理对齐。

**交付与验收**（`C:\Users\takomi\Desktop\klar-matcha-samples\npu2\`，4 句 × 3 份 ＋ `_说明.md`）：

| 句 | 文本 | vocos NPU vs **vocos** CPU | hifigan NPU vs **hifigan** CPU |
|---|---|---:|---:|
| 01_问候 | 你好，我是你的语音助手。 | **0.969** | **0.9991** |
| 02_天气 | 今天天气不错，适合出去走走。 | **0.970** | **0.9997** |
| 03_数字 | 现在时间是下午三点二十分。 | **0.968** | **0.9984** |
| 04_长句 | 请帮我把客厅的灯关掉，然后打开窗户。 | **0.978** | **0.9996** |

⇒ **vocos fp16 四条全在 0.97 以上，她 2026-11-01 试听确认可用**；**HiFi-GAN fp16 四条全在 0.998 以上**（此前判“不成立”是比对对象错了，见 §8b.3）。

## 8b. **替代路线：HiFi-GAN 类声码器（直出波形、没有 Cos/Sin）**

vocos 的问题是"输出频域三分量 + 图外 iSTFT"，而 **HiFi-GAN 直接输出时域波形**，整类问题不存在。**sherpa-onnx 官方就提供三个，并且文档写明可直接配 matcha。**

### 8b.1 现成可用的三个（实测大小与算子，非推测）

| 模型 | 大小 | 节点 | 输入 | 输出 | **有 Cos/Sin 吗** |
|---|---:|---:|---|---|:--|
| `hifigan_v1.onnx` | **55.75 MB** | 205 | `mel [N,80,L]` | **`audio [N,L]` 波形** | **无** |
| `hifigan_v2.onnx` | **3.75 MB** | 205 | 同上 | 同上 | **无** |
| `hifigan_v3.onnx` | **5.86 MB** | — | 同上 | 同上 | **无** |

来源：`https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/`。
sherpa-onnx 的 matcha 文档明确写：**`--matcha-vocoder` 可换成 `hifigan_v1/v2/v3.onnx`**，与 `vocos-22khz-univ.onnx` 平级可选。

**算子组成**（v1/v2 实测相同）：

```
Conv 74 · LeakyRelu 69 · Add 44 · Constant 7 · ConvTranspose 4 · Div 4 · Tanh 1 · Clip 1 · Squeeze 1
>>> trig ops: NONE
```

**mel 参数与 vocos 完全一致**（`sr=22050 / n_fft=1024 / hop=256 / win=1024 / num_mels=80 / fmin=0 / fmax=8000`）⇒ **matcha 的 mel 直接能喂，不用改前端**。

### 8b.2 算子面初判（**当时未实测；结论已被 §8b.3／§8b.5 取代**）

| 算子 | icraft 114 个 spec 页里有吗 | 备注 |
|---|:--|---|
| `Conv` / `ConvTranspose` | ✅ `Conv1d/2d/3d`、`ConvTranspose1d/2d/3d` | |
| `Div` / `Tanh` / `Squeeze` / `Add` | ✅ 都有 | |
| `Clip` | ⚠️ 只有 **`ClampScalar`**，不是 `Clip` | 需改写或确认映射 |
| **`LeakyRelu`** | ❌ **没有**（只有 `Relu`、**`Prelu`**） | **69 个！最终解法＝换成 `PRelu`（1 算子顶 5 个），见 §8b.5** |

⇒ **不能直接 parse，需要一次算子改写。** 当时以为要把 `LeakyRelu` 拆成 `Relu + Mul + Add` 等价式、`Clip` 换成 `ClampScalar`；**实测下来 `Clip` 是用 `Max`+`Min` 解的、`LeakyRelu` 是换成 `PRelu` 解的**（§8b.3／§8b.5）。

**踩坑记录**：§8b.2 当时把"算子面里有 `Prelu`"这条线索放过去了，先去拆 5 个算子，结果白白慢了 2.90×。**教训：看到"有近似算子"要先想能不能 1:1 替换，再考虑拆分。**

### 8b.3 **HiFi-GAN 上板实测：五段全通、板端 rc=0、读数已到手**

#### 改写配方（这一步是全部工作量所在）

原版 `hifigan_v2.onnx`（opset 14 / 205 节点）**直接 parse 会失败**，要改四处：

| # | 问题 | 改法 | 数量 |
|---|---|---|---:|
| 1 | **`LeakyRelu` 不在 icraft 114 页算子面**（只有 `Relu`、`Prelu`） | 改写成等价式 `Relu(x) − alpha·Relu(−x)`，用 `Neg`＋`Relu`＋`Mul`＋`Sub` | **69 个** |
| 2 | `Clip` 也只有 `ClampScalar`，不是 `Clip` | 改成 `Max(x,min)` 再 `Min(t,max)`，min/max 从 `Constant` 节点取 | 1 个 |
| 3 | `dilations has incorrect size`（1D 卷积） | **直接复用 `.tmp_matcher/conv1d_to_2d.py`**（补一路 H=1 轴） | **78 个** |
| 4 | `Squeeze` 在 opset 11 里 axes 是**属性**不是输入 | 把 axes 从输入挪进 attribute | 1 个 |

另外 **opset 14 → 11、IR → 8**（icraft 只吃 11／17、IR ≤ 8）。

**改写后：205 节点 → 482 节点**（`Relu` 138、`Neg` 69、`Mul` 69、`Sub` 69）。
**数值完全等价**：`corr = 1.000000`、`max|d| = 0.000000`（同一 mel，ONNX Runtime 对跑）。

#### 五段全 `rc=0`

`parse → optimize → quantize(int8) → adapt → generate`，产物 `hifigan_v2_ZG.json` **805 KB** ＋ `.raw` **7.2 MB**。
**int8 需要校准集**，直接复用 vocos 的 `qtset/`（同为 mel、同为 `[1,1,600,80]`，完全兼容）。

#### 板端读数（三次极稳）

```text
run1 rc=0  total_hard_time = 74.831 ms
run2 rc=0  total_hard_time = 74.829 ms
run3 rc=0  total_hard_time = 74.854 ms
```

**输出 `v_id=1315`**，153600 样本（`600×256`）、`uniq=176`、`rms=0.0447`、值域 `±0.29` ⇒ **是真波形不是噪声**。

#### 真实中文 4 句（板端 CLI 实测）

| 句子 | 时长 | 波形 rms | 非静音 |
|---|---:|---:|---:|
| 01_问候 | 2.29 s | 0.0554 | 71.4% |
| 02_天气 | 2.95 s | 0.0476 | 71.4% |
| 03_数字 | 2.66 s | 0.0469 | 69.7% |
| 04_长句 | 3.65 s | 0.0474 | 73.5% |

**四句全部有真实波形**（对比：vocos-npu 那侧 Python API 版本第 3/4 句全零，改用 CLI 才正常）。

#### 与 CPU 的相关性

> ✅ **2026-11-01 二次更正（重要）**：此前报的 hifigan「0.029／0.154／−0.141／−0.031」是**我比对对象搞错了**——
> 拿 HiFi-GAN 的 NPU 输出，去比 **vocos** 的 CPU 参考。**两个不同声码器本来就该不相关。**
> 换成正确的参考（`hifigan_v2.onnx` 在同一 mel 上的 CPU 输出）后，**四条全部 0.998 以上**。

**比对纪律**：**A/B 必须同模型比同模型**——`vocos-NPU` 对 `vocos-CPU`，`hifigan-NPU` 对 `hifigan-CPU`。跨模型比波形没有意义。

| 句子 | **vocos** NPU vs **vocos** CPU | **hifigan** NPU vs **hifigan** CPU |
|---|---:|---:|
| 01_问候 | 0.969 | **0.9991** |
| 02_天气 | 0.970 | **0.9997** |
| 03_数字 | 0.968 | **0.9984** |
| 04_长句 | 0.978 | **0.9996** |

**读法**：
- **HiFi-GAN fp16 在板上是准的**，而且比 vocos 更保真（0.999 vs 0.97）——因为它**直出波形**，少了 iSTFT 那一步的重建误差；vocos 的 0.97 里包含了「我的 iSTFT 与 vocos 内部 iSTFT」的细微差异。
- 代价是速度：**62.88 ms vs 19.29 ms（**3.3×**，见 §8b.5）**，模型 7.2 MB vs 31.3 MB。
- 两条路线**都成立**，选型看权衡（§8b.4）。

**生成 CPU 参考的正确姿势**（原版 `hifigan_v2.onnx`，**不是** icraft 改写版）：
```python
# 输入是 3 维 [1, 80, T]，不是 icraft 的 4 维 [1,1,600,80]
o = sess.run(None, {"mel": mel[None, :80, :T].astype(np.float32)})[0]
w = np.asarray(o).ravel()[: T * 256]        # 时域直出，无 cos/sin、无 iSTFT
```
⚠️ **`hifigan_v2_icraft_c2d.onnx` 不能在 onnxruntime 里跑**——它为 icraft 改成了 2D Conv，ORT 会报 `Attribute dilations has incorrect size`。**CPU 参考必须用原始的 `hifigan_v2.onnx`。**

### 8b.4 与 vocos 的取舍（含实测数字）

| | vocos int8 | **vocos fp16** ✅ | **HiFi-GAN v2 fp16（`PRelu` 版）** ✅ |
|---|---:|---:|---:|
| 硬件段（`hard`） | **9.50 ms** | 19.29 ms | **62.88 ms**（原 182.51，见 §8b.5） |
| 波形 vs **同模型** CPU（sherpa 真实 mel） | 0.186 ❌ | **0.969–0.978** ✅ | **0.9984–0.9997** ✅ |
| 模型体积 | 18.7 MB | 31.3 MB | **4.4 MB**（原 7.2 → 4.4，见 §8b.5） |
| 算子数 | — | 166 | **166**（原 483，见 §8b.5） |
| 相位问题 | 坏 | 需 fp16 | **不存在** |
| 图外步骤 | 要 iSTFT | 要 iSTFT | **不要** |
| 中文自然度 | 已验证（她试听通过） | 已验证（她试听通过） | **已验证（她 2026-11-02 听 A/B 后确认"没问题"）** |

**取舍**（三条都成立，按场景选）：
- **要最快 → vocos fp16**：19.29 ms，仍是 HiFi-GAN 的 **3.3 倍速**。代价：31.3 MB、要自己写 iSTFT、保真度 0.97。
- **要省内存／去掉 iSTFT → HiFi-GAN v2 fp16（`PRelu` 版）**：模型 **4.4 MB**（vocos 的 14%）、**直出波形、不用 iSTFT**，保真度 **0.999**（比 vocos 高）。代价：62.88 ms。
- **要看清两条路的差距在收窄**：把 `LeakyRelu` 改写从 5 算子换成 `PRelu` 后，HiFi-GAN 从「慢 9.5×」变成「**慢 3.3×**」（§8b.5）。**这说明"算子个数"比"参数多少"更能决定板端速度。**
- **中文自然度已闭环**：她 2026-11-02 听完 `声码器AB对比/`（同句、同 mel、只换声码器）确认「两个听着都没问题」。
  **注意证据边界**：数值 0.998–0.999 只证明「NPU 忠实于 CPU」，**"好听"是她的听感判断**，两件事分开记。

### 8b.5 **提速 2.90×：把 `LeakyRelu` 改写成 `PRelu`（逐算子实测驱动）**

> 2026-11-02。结论：`hard` 时间 **182.38 → 62.88 ms**，算子 **483 → 166**，数值**一位不差**。

**为什么会有这一步**：HiFi-GAN 上板 182.51 ms，比 vocos 的 19.29 ms 慢 9.5 倍，但它的**参数只有 vocos 的 6.9%**、FLOPs 只多 1.5 倍。用 `icraft-run --log_time` 取逐算子耗时后真相清楚了：

| 旧版（`LeakyRelu`→5 算子） | 个数 | hard(ms) | 占比 |
|---|---:|---:|---:|
| Add | 113 | 59.48 | 32.6% |
| **ReLU** | **138** | 47.09 | 25.8% |
| Conv2d | 74 | 27.02 | **14.8%** |
| **Neg** | **69** | 23.34 | 12.8% |
| **Multiply** | **69** | 22.79 | 12.5% |
| ConvTranspose2d | 4 | 1.23 | 0.7% |

**真正的卷积只占 15.5%，83.7% 的时间花在逐元素算子上**——而这 138 个 ReLU + 69 个 Neg + 69 个 Multiply，正是"把 69 个 `LeakyRelu` 拆成 5 个算子"的产物。

**关键观测：在这颗 NPU 上 `Conv2d` 单算子 0.365 ms，`ReLU` 单算子 0.341 ms —— 一样贵。** 它主要开销是**每个算子启动一次 + 搬一遍张量**，不是 FLOPs。所以"算子个数"是这里的一等公民。

**修法**：`LeakyRelu(x, α) ≡ PRelu(x, α)`，而 icraft 的算子面**有 `Prelu`**（`wiki/PL/MOD/modellist/iCraft算子支持矩阵.md` 标 `√`；ONNX 侧算子名是 **`PRelu`**，不是 `PReLU`，写错会报 `No Op registered for PReLU with domain_version of 11`）。`slope` 用常数 `[1]` 张量广播即可。

**结果**：

| | 旧（5 算子） | **新（PRelu）** | 变化 |
|---|---:|---:|---:|
| 算子数 | 483 | **166** | **−317（−65.6%）** |
| `hard` 时间 | 182.38 ms | **62.88 ms** | **2.90× 快** |
| `wall` 时间 | 221.33 ms | **75.01 ms** | **2.95× 快** |
| 模型体积 | 5.9 MB | **4.4 MB** | −25% |
| 四句 `hard` 复测 | — | **62.86／62.84／62.86／62.84 ms** | 极稳 |
| **vs CPU 相关** | 0.9991／0.9997／0.9984／0.9996 | **0.999116／0.999745／0.998430／0.999563** | **一位不差** |

**新版逐算子**（166 ops）：`Conv2d` 74 个 27.23 ms（43.3%）、`Add` 44 个 23.29 ms（37.0%）、`ReLU` 28 个 9.66 ms（15.4%）、`Div` 4 个 1.38 ms、`ConvTranspose2d` 4 个 1.23 ms。**卷积重新成为最大头，说明骨架已经合理了。**

**改写后必须做的两件事**（这次都做了）：
1. **数值等价验证**：`hifigan_v2_prelu.onnx` vs 原版 `hifigan_v2.onnx` 在同一 mel 上 → `corr = 1.000000000`、`max|d| = 0.000e+00`（逐位相同）。
2. **上板 vs CPU 复测**：仍是 0.998–0.999，**没有为了快而算错**。

**代码**：`repos/lang/tts/sherpa/HiFi-GAN/hifigan-prelu/`（改写 `rewrite_prelu.py` → `conv1d_to_2d.py` → `build_container.sh` 四段 → `gen_local.bat` 第五段），说明见该目录 `README.md`。

## 9. 复现入口（脚本不在本页）

**所有可复跑的东西在 `repos/lang/tts/`**，按组件分目录，每个目录有自己的 README（含该组件的
算子改动、坑清单、复跑顺序）：

| 要复现什么 | 去哪 |
|---|---|
| 取 sherpa 的真实 token / 出 mel | `repos/lang/tts/sherpa/sherpa-mel/` → `enable_debug.py`、`build_exact.py` |
| 声学模型与 token 调查 | `repos/lang/tts/sherpa/matcha/` → `token/` |
| vocos 五段编译 / iSTFT / 上板取数 | `repos/lang/tts/sherpa/vocos/` → `build_container.sh`、`stft_verified.py`、`cli_exact.sh` |
| **HiFi-GAN 算子改写（两版）** | `repos/lang/tts/sherpa/HiFi-GAN/` → `rewrite-5op/`、`hifigan-prelu/` |
| 出 CPU 参考做 A/B | `repos/lang/tts/sherpa/HiFi-GAN/cpu_reference.py` |
| 逐算子耗时聚合 | 各自目录的 `agg_by_op.py` |
| 板端 CPU-only 基准口径 | `repos/lang/tts/bench-cpu/` |
| 单体 TTS 为什么不行 | `repos/lang/tts/sherpa/VITS/piper/`、`vits-others/` |

**四个必须记住的调用参数**（写错就白跑）：

```text
容器内跑要加    MSYS_NO_PATHCONV=1
icraft-parse    --target zhuge        （写 ZG 报 "Zg is not a valid target"）
板上 backends   "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host"
                 （ZG330, 前缀与 ;Host 后缀都不可省）
第五段 generate 必须本机 Windows CLI：C:\Icraft\CLI v3.39.0\bin\icraft-generate.exe
```

**判据速查**：

| 想知道 | 看哪 | 通过标准 |
|---|---|---|
| NPU 有没有真参与 | `total_hard_time` | 非 0（vocos 实测 9.5 ms） |
| dump 可不可信 | dump 输入 v_id=0 与源文件逐字节比 | `array_equal == True` |
| 输入排布对不对 | CPU onnxruntime 输出 mag vs golden | corr **1.000000** |
| 损失来自哪里 | 正常量化 vs `--fake_qf` | 一关量化 corr 从 0.12 → 0.87 |
| 音频听感对不对 | 直接听 | 能听懂中文才算过 |

## 10. 坑清单（每条都实测踩过，按顺序看）

### 10.1 **比对前必须核两边喂的 mel 是同一份**

这是**最容易出假读数**的一处。典型事故：板端喂的是 `600×80 = 48000` 的 padding 版，CPU 参考用的却是 `80×455 = 36400` 的原长版 ⇒ 算出 `mag corr = 0.102` 的假结论（真值是 `0.885`）。

**做法**：先 `md5` 两边、再核 `npu_input[0,0,:T,:] == mel.T`：

```python
assert np.array_equal(npu_in[0, 0, :T, :], mel.T)
print("cpu md5", hashlib.md5(cpu_in.tobytes()).hexdigest())
```

### 10.2 **ZG330 要求输出缓冲物理地址 4096 字节对齐**

`Session.forward([inp])` 自动创建的输出张量**不保证对齐**，实测报：

```text
Check failed: (phy_addr % 4096 == 0) is false
output tensor physic addr: 27274272 is not align to 4096!
```

**症状**：同一模型、同一输入，连跑三次给出**不同结果**（实测 `uniq` = 138773 / 11 / 11；甚至出现 `NaN`）。

⇒ **Python API 直读不可靠**。自己 `dev.malloc()` 再 `setData(chunk, (-base) % 4096)` 能过对齐检查，但多次 `forward` 仍会互相覆盖。**要可信数值，用 CLI**（§10.3）。

### 10.3 **取数的可靠路径是 CLI 的 `--dump_output`**

```bash
icraft-run --json <m>_ZG.json --raw <m>_ZG.raw --network <name> \
  --input <输入> --backends "ZG330,axi://...;Host" \
  --dump_format HQB --dump_output --log_path ./dump
# 产物: dump/<network>/ftmpHQB/<v_id>.ftmp  (float32)
```

- **`--dump_format` 必须成对出现 `--dump_output`**，否则导出的是量化 scale 表。
- **格式选 `HQB`**（实测 `rc=0`，全量导出 188/213 个 ftmp）。`SQB`／`SFT` 在这个件上 **`rc=235` 失败**；`HQT` 也能 `rc=0`。
- **输出 v_id 会变**：原版 `796/800/804`，重新量化后可能变成 `818/822/826`。**每次都要从 `Output` 节点读 v_id，不能写死**：

```python
vids = [v["v_id"] for o in j["ops"]
        if "Output" in str(o["_type_key"]) for v in o["inputs"]]
```

### 10.4 **`length_scale` 不要动**

sherpa 默认 `1.0`（22 音节 → 5.24 s）。改成 `2.3` 会得到 12.13 s、每个音节拉长 2.3 倍，听成「你你你、好好好」。**这是最容易误判成"模型坏了"的一个坑。**

### 10.5 **容器里的 `icraft-generate` 出不了 ZG 档**

Linux amd64 包的 codegen 只带布衣，会报：

```text
File "/lib/x86_64-linux-gnu/libicraft_zhuge_codegen.so" does not exist!
```

⇒ **ZG 档 `_ZG` 件必须用本机 Windows CLI 出**（`C:\Icraft\CLI v3.39.0\bin\icraft-generate.exe`）。容器里 quantize／adapt 都能跑（`rc=0`），只有 generate 这步要回 Windows。

### 10.6 **`matcha` 是概率模型**

`noise_scale > 0` 时每次结果不同（实测 `0.667`→`corr 0.954`、`1.0`→`0.920`）。**做 A/B 必须 `noise_scale=0`**（两次逐字节相同）。

### 10.7 **板端磁盘被 dump 撑满时，症状极具欺骗性**

我这一轮把 `/root/vocos_run` 的 dump 堆到 **9.1 GB**，根分区 **26G/26G、可用 0**。表现不是"报磁盘满"，而是：

| 症状 | 真相 |
|---|---|
| python 脚本**无任何输出**且 `rc=0` | 文件系统写不进去 |
| `icraft-run` 报 `rc=1` **但日志为空** | 同上 |
| **scp 传上去的脚本全是 NUL 字节**（`od -c` 才看得出） | 磁盘满时 scp 建了文件写不进内容 |

**判据**：脚本"静默无输出"时**第一件事查 `df -h`**，不要怀疑脚本。清理见 [[板端磁盘清理SOP]]。

### 10.8 **A/B 必须同模型比同模型，跨声码器比波形毫无意义**

这条让我把一个**完全正常**的模型误判成"坏了"，并写进了决策记录：

| 我当时比的 | 结果 | 真相 |
|---|---|---|
| `hifigan-NPU` vs **`vocos`-CPU** | 0.029／0.154／−0.141／−0.031 | **两个不同声码器**，相位互不相干，本来就该≈0 |
| `hifigan-NPU` vs **`hifigan`-CPU** | **0.9991／0.9997／0.9984／0.9996** | 真实水平：几乎完美 |

**负相关尤其要警惕**：负值不是"精度差"，而是**两个不相干信号的随机波动**。真正的精度差表现为「正相关但偏低」（如 int8 的 0.186）。

**纪律**：
1. 比波形前先问「**这两个信号是同一个模型产出的吗**」。
2. 换模型就要**重出参考**，不能复用上一份 CPU 输出。
3. CPU 参考要用**原版 ONNX**（`hifigan_v2.onnx`，输入 `[1,80,T]`），**不能用 icraft 改写版**——改写版是 2D Conv，onnxruntime 直接报 `Attribute dilations has incorrect size`。

## 11. 定档：matcha 留 CPU、vocos 下沉 NPU —— **已成功**（D-1793547016）

> 本节是这条链路的**结论页**，也是可复现步骤的落点（它只适用于本 TTS，不抽成通用 SOP）。

### 11.1 这条链路到底是什么

**不是"把 TTS 整个搬上 NPU"，而是"把两段式 TTS 的声码器那一段搬上去"。**

```text
文本 ──sherpa 前端(CPU)──> token ──matcha(CPU)──> mel[80,T] ──vocos(NPU)──> mag/cos/sin ──iSTFT(CPU)──> wav
                                                  ↑ 分界就在这里
```

| 段 | 放哪 | 为什么 |
|---|---|---|
| 前端（分词/变调/blank） | CPU | 逻辑密集、张量小，NPU 不划算 |
| **matcha**（声学模型，出 mel） | **CPU** | 概率模型（ODE），有动态控制流；且输出是中间张量 |
| **vocos**（声码器，出频域三分量） | **NPU** | 纯前馈、算子面全在 icraft spec 内、单段算力需求大 |
| iSTFT | CPU | 图外一步，几十行 C++ |

### 11.2 效果与速度（对纯 CPU）

**速度**（板上 4×A53 实测，同一输入 `[1,80,559]`）：

| | vocos 耗时 |
|---|---:|
| 纯 CPU（onnxruntime 2 线程） | **2487 ms** |
| **NPU ZG330 fp16** | **19.29 ms**（硬件段） |
| ⇒ 加速 | **129×** |

**端到端**（把两段独立实测拼起来，不含前端与 iSTFT）：

| 场景 | matcha(CPU) | vocos(CPU) | 全 CPU 相对实时 | **vocos→NPU** | 相对实时 | 省时 |
|---|---:|---:|---:|---:|---:|---:|
| 短句 20 音素 | 1730 ms | 905 ms | 1.129（慢） | **1749 ms** | **0.753** | **33.4%** |
| 中句 60 音素 | 4504 ms | 2487 ms | 1.107（慢） | **4523 ms** | **0.716** | **35.2%** |
| 长句 150 音素 | 12211 ms | 6268 ms | 1.173（慢） | **12230 ms** | **0.777** | **33.8%** |

**读法**：vocos 只占两段总耗时的 33–36%，**把它移走就把整条链从「慢于实时 11–17%」拉到「快于实时 29–40%」**。这是「刚好跨过实时线」的量级差别，不是锦上添花。

**效果**（4 句真实中文，sherpa 真实 token 生成的 mel；**各自比各自的 CPU 参考**）：

| 句 | 文本 | vocos NPU vs vocos CPU | hifigan NPU vs hifigan CPU |
|---|---|---:|---:|
| 01 | 你好，我是你的语音助手。 | **0.969** | **0.9991** |
| 02 | 今天天气不错，适合出去走走。 | **0.970** | **0.9997** |
| 03 | 现在时间是下午三点二十分。 | **0.968** | **0.9984** |
| 04 | 请帮我把客厅的灯关掉，然后打开窗户。 | **0.978** | **0.9996** |

**两个声码器在板上都是准的**。vocos 略低（0.97）是因为它多一步图外 iSTFT，那 0.03 的差来自「我的 iSTFT 与 vocos 内部 iSTFT」；HiFi-GAN 直出波形，所以能到 0.999。

**她 2026-11-01 试听确认可用**。交付在 `C:\Users\takomi\Desktop\klar-matcha-samples\npu2\`。

### 11.3 原理：为什么官方那些 TTS 在这块板上跑不动，这个却行

**先说清楚——Piper／Kokoro 不是"编译不过"，是"在这块板上放不下、跑不赢"**（见 §11.4）。三条根因：

**① 它们是单体端到端模型，中间张量不落地，拆不开。**

Piper（VITS）是 `text→phoneme→mel→waveform` 一整个 ONNX。想把重的那段搬去 NPU，**必须切开**；但端到端模型内部没有"对外有意义的中间张量"，切在哪一段都要自己重写接口。

matcha+vocos 是**天生两段式**：`mel[1,80,T]` 是一个**明确的、可序列化的边界**（48000 B 定长）。所以能只搬 vocos，其余一行不动。

**② vocos 的算子面正好落在 icraft 的 114 个 spec 里。**

vocos 的算子：`Matmul` 23／`Transpose` 43／`LayerNorm` 10／`Conv2d` 9／`Exp` 1／`Cos` 1／`Sin` 1／`Reshape` 51。**全部有 spec 页，没有一个是 `Unsupport`。**

**③ 量化口径选对了：int8 死、fp16 活。**

- **int8 死**：诸葛的 `CosNode`/`SinNode` 打印 `ZhugeQuantParams Not Implemented! Using Default Imeplementation!`，角度张量的 scale 被写成常数 `0.49766457`（声明是 `0.45043343`，差 10.4%），板上角度输出只剩 256 级（±63.69、步长 0.4975）。**但致命的不止这个**——板端 `Cos` 的输出**与输入角度脱钩**（同一 int8 code 对应 36 个不同值，对"真实角度→圆周 256 步"命中率仅 0.4%–4.9%）⇒ 相位平均误差 **81.1°**、波形相关 0.12。
  **口径提醒：不要说成"角度量化太粗"**——按板端规格在真实角度上模拟 int8，`cos/sin` 仍有 0.9645／0.9711（详见 §8.2b）。
  **把三角函数搬出图外也救不了**（角度作第 4 个 fp32 输出，板上仍是 256 级、`cos` 相关 0.1060）。
- **fp16 活**：`--qdtype fp16` **不用校准集**，相位平均误差降到 **22.5°**，波形相关 0.969–0.978，代价是模型 18.7→31.3 MB、硬件段 2.02×（9.50→19.29 ms）。**即使 2 倍，仍比 CPU 快 129×。**

**④ 反例说明"能拆"只是必要条件，不是充分条件。**

HiFi-GAN 同样可拆、同样编过五段、**fp16 下同样是准的（0.9984–0.9997）**——说明「可拆 ＋ fp16」这个组合对声码器是**可复制的**，不是 vocos 的特例。

**真正的门槛在算子面**：HiFi-GAN 要多做四处改写才编得过（`LeakyRelu`×69、`Clip` → `Max`+`Min`、`Conv1d`×78 → `Conv2d`、`Squeeze` axes 挪进属性），**改写后必须验证与原模型数值等价（实测 `corr=1.000000`）**，否则错了也不知道。

**而"怎么改写"直接决定速度**（这是这轮最值钱的一条）：起初把 `LeakyRelu` 拆成 5 个算子（`Neg/Relu/Relu/Mul/Sub`），能跑但 182.5 ms；改成 **`PRelu`（1 个算子顶 5 个）**后降到 **62.88 ms（2.90×）**，数值一位不差。**原因见 §8b.5：这颗 NPU 上 `Conv2d` 单算子 0.365 ms、`ReLU` 单算子 0.341 ms——一样贵，开销在"每个算子启动一次"，不在 FLOPs。** 所以选改写方案时，**算子在旧面上的对应物有几个，比"能不能编过"更值得先问一句**。

### 11.4 与 Piper 部署失败的对照

**Piper 的失败记录不在本页**，正本在 [[ARM CPU TTS性能测试]]（板上 CPU-only 逐行读数）与 [[实时伪tts]]（结论与取舍）。这里只做对照，**不复制那两页的数**。

| | **Piper（失败）** | **matcha+vocos（本次成功）** |
|---|---|---|
| 架构 | 单体 VITS，端到端出波形 | **两段式**：matcha 出 mel、vocos 出频域 |
| 部署位置 | **只能整条放 CPU**（拆不开） | 只把 vocos 放 NPU，其余留 CPU |
| 板上内存 | 峰值 **391.5 MB**（zh_CN-huayan）／**754.8 MB**（en_US-lessac）；单进程 HWM 134 MB | vocos 模型 **31.3 MB**，NPU 侧不吃 DDR 大块 |
| 是否被 OOM | **是**——该页 §十四 有 **12 次 OOM 击杀**逐次读数，`rc=137`（SIGKILL） | **否** |
| 速度（**标准 RTF**＝生成/音频，<1 快） | **0.65–0.81**（zh_CN **常驻**，**快于实时 23–54%**）／0.90–1.01（en_US 常驻，临界） | 整链 **0.716–0.777** ⇒ **快于实时 29–40%** |
| 失败性质 | **放不下**（内存峰值 391–755 MB ⇒ 12 次 OOM）——**但跑得动**（常驻快于实时 23–54%） | 内存问题**被拆分解决了** |

**一句话对照**：Piper 的失败是「**整条链在这块 993 MB 的板上放不下**」（峰值 391–755 MB，12 次 OOM 被杀）——**注意它算得动**（常驻 RTF 0.65–0.81，快于实时 23–54%）；本次成功是「**把链切开，只把占 33–36% 耗时、31 MB 的那一段搬到 NPU**」⇒ 峰值内存大幅下降。**不是同一件事的两种做法，是把问题重新分解了。**

> 🔧 **2026-11-02 更正**：本节旧版把 Piper 写成「慢于实时」，是**把基准表 `rtf` 列的方向读反了**——那一列是 `音频秒÷生成秒`（>1＝快于实时），不是标准 RTF。同页 §下部「Piper 的失败」措辞已同步改为「放不下」而不是「跑不赢」。

> ⚠️ 注意口径：Piper 从未尝试上 NPU（那批是 CPU-only 基准），所以**不能写成"Piper 上 NPU 失败"**。
> 同样也**不能写成"Piper 跑不动"**——它在 CPU 上常驻快于实时 23–54%，**是内存放不下被 OOM 杀的**。

### 11.5 可复现步骤（**脚本在 `repos/lang/tts/`**，本页只留要点）

**前置**：板端 `/root/vocos_run/fp16/`（`vocos_ZG.json` + `.raw`，31.3 MB，`--qdtype fp16` 出的）、`hifigan_fp16/`；校机装 `sherpa-onnx==2.0.1` 到独立目录。

1. **拿 sherpa 的真实 token**（校机，**不要自己拼**）：
   ```python
   mc = sherpa_onnx.OfflineTtsModelConfig(matcha=..., num_threads=1, debug=True)
   tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=mc, max_num_sentences=1))
   tts.generate(TEXT, sid=0, speed=1.0)   # stderr 打印 "final IDs (N): [...]"
   ```
2. **matcha 出 mel**（CPU，`noise_scale=0`、`length_scale=1.0` 默认不动）：把上一步的 ID 序列喂 `model-steps-3.onnx`，得 `mel[80,T]`。
3. **转板上输入**：`mel.T` 放进 `[600,80]` 零填充 → reshape `[1,1,600,80]` → `.tofile()`（192000 B）。
4. **逐句上板**（**必须 CLI，且一句一次**）：
   ```bash
   icraft-run --json fp16/vocos_ZG.json --raw fp16/vocos_ZG.raw --network vocos \
     --input <in.bin> --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" \
     --dump_format HQB --dump_output --log_path ./out
   ```
5. **合成**：读 `v_id=792/796/800` 三个 `ftmpHQB/*.ftmp`（各 `513×600`，按 `T` 截断）→ 周期 Hann iSTFT（`n_fft=1024, hop=256, center=1`）→ wav。
6. **判据**：NPU 波形 vs 同一 mel 的 CPU 波形，**相关 ≥0.95 且 rms 同量级**；4 句全过才算成。
7. **收尾（硬要求）**：**每次 `--dump_output` 后立即取数并删 dump**——一轮 4 句 × 2 模型就能堆到 GB 级，板子根分区只有 26G（§10.7）。

## 相关页面

- [[TTS同量级候选进NPU横评]]——10 个候选模型的完整实测与排序
- [[icraft数值验证与Podman环境SOP]]——容器环境、取数 API、`--fake_qf` 定案法
- [[iCraft算子支持矩阵]]——算子面正本（114 个 spec 页）
- [[ARM CPU TTS性能测试]]——同一批模型在板上的 CPU-only 读数
- [[哪些要跟厂商要]]——第九条记着 `Mul` 广播与 `Unsupport` 无前向两个待问项
