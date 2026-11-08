# tts4fpai

## 定位

**FMSH ZG330（悟净 / FMQL30TAI676H）上中文 TTS 的全部可复现内容**——模型改写脚本、icraft 五段编译配方、板端取数与合成脚本、逐算子读数。作为 `repos/lang/tts/` 目录存在于 `WCIS-FPAI-repos` 内（2026-11-04 由 `repos/tts4fpai/` 改名 `tts/` 并收进 `lang/`，神经系组件再收进 `sherpa/` 子目录；**不是嵌套 git 子模块**，内容直接由父库跟踪；见下方「为什么不建嵌套仓」）。

**叙述性结论不在这个仓里。** 文档正文在 [[MatchaVocosNPU]]、[[TTS同量级候选进NPU横评]]、[[ARM CPU TTS性能测试]]；本仓只放**能重跑的东西**。

## 层级关系（本仓的核心内容）

一条现代神经 TTS **不是一个模型，是两段**：前端 → 声学模型 → mel → 声码器 → 波形。

| 目录 | 是什么 | 位置 | 放哪跑 | 现状 |
|---|---|---|---|---|
| `sherpa/sherpa-mel/` | 前端：文本→token，兼"mel 从哪来"的全部调查 | 第 1 段 | CPU | ✅ sherpa `debug=True` 打印 token |
| `sherpa/matcha/` | 声学模型（icefall matcha-icefall-zh-baker）：token→mel | 第 2 段 | CPU | ⚠️ `rc=71`，上不了 NPU，留 CPU |
| `sherpa/vocos/` | 声码器：mel→mag/cos/sin（频域），iSTFT 在图外 | 第 3 段 | **NPU** | ✅ fp16 19.29 ms，相关 0.969–0.978 |
| `sherpa/HiFi-GAN/` | 声码器：mel→波形（时域直出） | 第 3 段 | **NPU** | ✅ fp16 **PRelu 版 62.88 ms**，相关 0.998–0.999 |

**`vocos/` 与 `HiFi-GAN/` 是同一层（声码器）的两个可互换实现**——同一份 `mel[1,80,T]` 进、同一段音频出。

对照两条不同技术路线：

| 目录 | 是什么 |
|---|---|
| `sherpa/VITS/`（piper/、vits-others/） | **单体端到端 VITS**（前端+声学+声码器打包成一个 ONNX）。中间张量不落地 ⇒ **切不开**，无法只把声码器搬 NPU；且板端 CPU 就过不去（391–755 MB 峰值、12 次 OOM、RTF 1.13–1.51） |
| `ekho-linux/` | **录音拼接**，另一类技术。RTF 0.49、RSS ~20 MB，**现役交付路线**（代码在 [[ekho-linux]]） |
| `bench-cpu/` | 板端 CPU-only 基准口径，上面所有"跑不动"的读数来源 |

## 入口

- `README.md`：**层级关系总图**、五个通用坑、量化口径（int8 死 / fp16 活）、复跑一条完整链路。
- `sherpa/sherpa-mel/SHERPA_FRONTEND_SOURCE.md`：sherpa C++ 前端源码正本（读代码得来，非猜测）。
- `sherpa/HiFi-GAN/README.md`：**算子改动完整配方**（`LeakyRelu`/`Clip`/`Conv1d`/`Squeeze` 四处）、两种 `LeakyRelu` 改法的 2.90× 差距、逐算子真相。
- `sherpa/vocos/int8/README.md`：int8 为什么必坏（`Cos/Sin` 量化参数未实现的根因链）。
- 各目录的 `build_container.sh` / `gen_local.bat`：五段编译（前四段容器、第五段必须本机 Windows CLI）。

## 为什么不建嵌套 git 仓

`repos/` 下若放一个带自己 `.git` 的目录，父库会把它当 **gitlink**，**其内容永远进不了父库**——这正是 2026-10-31 `modrt/` 两颗厂商 clone 踩过的坑（记为 `D-1793459164`）。

所以 `tts/`（原名 tts4fpai）是**普通目录**，全部文件由 `WCIS-FPAI-repos` 直接跟踪。若日后要独立成远程仓，需先把内容按 gitlink 规则摊平并同步更新父库指针。

## 关键读数（速查）

| 项 | 值 |
|---|---|
| vocos int8 | ❌ 9.50 ms，波形 0.186（相位全毁） |
| **vocos fp16** | ✅ **19.29 ms**，0.969–0.978（CPU 2487 ms ⇒ 129×） |
| HiFi-GAN fp16（5 算子版） | ✅ 182.38 ms，0.998–0.999 |
| **HiFi-GAN fp16（PRelu 版）** | ✅ **62.88 ms**，0.9984–0.9997（提速 2.90×） |
| 只搬 vocos 后整链 | 相对实时 **0.716–0.777**（不改则 1.107–1.173，慢于实时） |

## 相关页面

[[repo项目索引]] · [[MatchaVocosNPU]] · [[TTS同量级候选进NPU横评]] · [[ARM CPU TTS性能测试]] · [[iCraft算子支持矩阵]] · [[ekho-linux]] · [[icraft数值验证与Podman环境SOP]]