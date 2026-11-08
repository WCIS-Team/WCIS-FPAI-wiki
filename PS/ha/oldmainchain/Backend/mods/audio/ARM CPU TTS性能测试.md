# ARM CPU TTS性能测试

> **这一页是"板端 CPU-only 语音链实测数据"的正本登记页**：TTS 三引擎（eSpeak NG／Piper／Kokoro-82M）＋泛 ASR 框架下五族组件替代档（重采样／VAD／图像编码／文本前置／ASR 运行时）的**全部逐行读数**。文件、脚本、模型、夹具的位置与 md5 在 [[板端我方代码与产物台账]]（§十＝TTS，§十二＝组件替代基准，§九／§十三＝ASR 链路），本页只放数与口径。
>
> **口径先说死（这三条决定所有数字能不能用）**：
> 1. **这些是"泛 ASR 框架内"的数，不是引擎标称值**。所有档都跑在同一块 993 MB／4×Cortex-A53@≈1 GHz／**无 swap**（当次为真；**10-11 起 `D-44` 给板加了 1 G swap＋`swappiness=10`，后续读写要按新配置**，2026-10-20 复测 `/proc/swaps` 在档、used 0）／256 MB CMA 的板上，输入是**预生成的固定夹具**（ASR 侧那四支测试语音＝`/root/funasr/testdata/`，见台账 `#122`／`#136`），除被测那一档外**没有任何上游组件在场**。所以：能横比同族替代档，不能拿去和厂商页面上的数比。
> 2. **控制变量＝一替代档＝一进程＝一道闸**。闸门＝`load1 < 1.2` 且 `MemAvailable` 高于该档下限（TTS 用 MB 口径 400／500／600，组件基准 A2～A4 用 kB 口径 300,000～500,000）。线程预算两组完全一致：`OMP_NUM_THREADS=4 ORT_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MALLOC_ARENA_MAX=2`（TTS 那批另带 `NUMEXPR_NUM_THREADS=4`）。
> 3. **全程不出声**。TTS 只生成 wav 落盘（`out/` 144 件，本页第六节逐个列字节与时长），组件基准不碰播放设备。板上 `/proc/asound/cards` 当次实测是 `--- no soundcards ---`（**10-20 复测已变：有 `MCP01` card0 的播放＋录制双设备与 `/dev/snd` 节点，取证见 [[实时伪tts]] 第十四节**——所以"不出声"是当时的测法，不是板子的能力）。
>
> 证据等级：**A**＝板上实测且原始行在本页；**B**＝实测但归属或版本没锁死；**C**＝机制推断／未复跑；**D**＝没有数。错处写在第十六节，不悄悄改。

## 一、`VmHWM`（峰值 RSS）总排序——先看这张

`VmHWM` 取自 `/proc/self/status`（进程级峰值，含解释器＋已 import 的库），`/usr/bin/time -v` 的 `Maximum resident set size` 是另一套口径（整进程树），两套都在下面逐行给出。

| 峰值 MB | 峰值 kB | 出处 | 作业 | `type=case` 行数 |
|---|---|---|---|---|
| 754.8 | 772,948 | TTS 主跑 | `piper_en_US-lessac-medium` | 28 |
| 645.9 | 661,364 | TTS 主跑 | `kokoro_af_alloy` | 3 |
| 645.6 | 661,076 | TTS 主跑 | `kokoro_zf_xiaobei` | 19 |
| 548.0 | 561,192 | 组件基准 | `C5_asr_runtime__onnx_metadata` | 3 |
| 434.3 | 444,732 | TTS 补测（一用例一进程） | `af_zh/kokoro_af_alloy` | 0 |
| 433.3 | 443,692 | TTS 补测（一用例一进程） | `zf_num/kokoro_zf_xiaobei` | 0 |
| 432.8 | 443,232 | TTS 补测（一用例一进程） | `af_num/kokoro_af_alloy` | 0 |
| 432.7 | 443,092 | TTS 补测（一用例一进程） | `zf_longw/kokoro_zf_xiaobei` | 0 |
| 432.7 | 443,080 | TTS 补测（一用例一进程） | `zf_longs/kokoro_zf_xiaobei` | 0 |
| 432.5 | 442,912 | TTS 补测（一用例一进程） | `af_mix2/kokoro_af_alloy` | 0 |
| 431.7 | 442,068 | TTS 补测（一用例一进程） | `af_longw/kokoro_af_alloy` | 0 |
| 431.6 | 441,928 | TTS 补测（一用例一进程） | `af_long/kokoro_af_alloy` | 0 |
| 429.0 | 439,248 | TTS 补测（一用例一进程） | `zf_long/kokoro_zf_xiaobei` | 0 |
| 391.5 | 400,904 | TTS 主跑 | `piper_zh_CN-huayan-medium` | 28 |
| 216.7 | 221,928 | 组件基准 | `C3_jpeg__cv2_png` | 2 |
| 210.4 | 215,492 | 组件基准 | `C3_jpeg__cv2_webp` | 2 |
| 197.8 | 202,544 | 组件基准 | `C1_src__scipy_poly` | 3 |
| 196.1 | 200,836 | 组件基准 | `C3_jpeg__pil_jpeg_q85` | 2 |
| 196.1 | 200,836 | 组件基准 | `C3_jpeg__ffmpeg_mjpeg_q85` | 2 |
| 196.1 | 200,836 | 组件基准 | `C3_jpeg__cv2_jpeg_q95` | 2 |
| 194.3 | 198,980 | 组件基准 | `C3_jpeg__cv2_jpeg_q85` | 2 |
| 164.5 | 168,428 | 组件基准 | `C1_src__numpy_fir` | 2 |
| 122.4 | 125,288 | 组件基准 | `C2_vad__silero` | 3 |
| 94.7 | 96,964 | 组件基准 | `C4_nlp__intent_rules` | 1 |
| 84.3 | 86,360 | 组件基准 | `C2_vad__energy_e-62` | 3 |
| 84.3 | 86,360 | 组件基准 | `C2_vad__energy_e-55` | 3 |
| 83.7 | 85,720 | 组件基准 | `C4_nlp__jieba_exact` | 3 |
| 83.4 | 85,360 | 组件基准 | `C4_nlp__jieba_search` | 2 |
| 76.7 | 78,548 | 组件基准 | `C2_vad__energy_e-45` | 3 |
| 62.7 | 64,232 | 组件基准 | `C1_src__ffmpeg_swr` | 3 |
| 56.7 | 58,104 | 组件基准 | `C1_src__ffmpeg_soxr` | 2 |
| 53.7 | 55,028 | 组件基准 | `C1_src__numpy_linear` | 2 |
| 46.0 | 47,132 | 组件基准 | `C1_src__alsa_plughw` | 1 |
| 39.5 | 40,448 | 组件基准 | `C2_vad__webrtc` | 0（错误行 1） |
| 36.4 | 37,284 | TTS 主跑 | `espeakng_b20` | 28 |
| 36.0 | 36,864 | TTS 主跑 | `espeakng` | 28 |
| 9.2 | 9,384 | 组件基准 | `C4_nlp__regex_only` | 2 |
| — | 0 | 组件基准 | `C5_asr_runtime__sensevoice_zh_itn` | 0 |
| — | 0 | 组件基准 | `C5_asr_runtime__sensevoice_default` | 0 |
| — | 0 | 组件基准 | `C5_asr_runtime__paraformer` | 0 |

**读数注意**：`峰值 kB = 0` 的三行（C5 的 `paraformer`／`sensevoice_default`／`sensevoice_zh_itn`）**不是占 0 MB，是没读到**——它们在建 recognizer 之前就抛（`rc=255`），进程还没长到采样点。`TTS 补测` 那九行里 case 数为 0 的也是同一件事（被 OOM 杀在中途，见第十四节的 12 次击杀表）。

## 二、numpy 是谁在用（逐处点名，含 import 位置）

**结论先给：泛 ASR 的骨架不用 numpy，numpy 只在三个点进场；它在场时的固定成本实测 ≈37 MB。**

| 用在哪 | import 位置 | 是不是必须 |
|---|---|---|
| ASR 链路本体 `asr_chain.py` | **没有 numpy**：import 清单只有 `argparse/json/math/os/queue/re/struct/subprocess/sys/threading/time/wave` | 分段（帧 RMS 双门限）与心跳是纯标准库＋`struct` |
| 后端适配 `asr/backends.py` | **函数内** import，共 5 处（75／97／173／205／235 行） | 是——funasr-onnx 与 sherpa-onnx 的调用界面就收 ndarray／float32 数组 |
| 按句切分器 `asr/vadseg.py` | **函数内** import，2 处（76／90 行） | 是——fvad 的打分器要吃 int16 缓冲，转换用 numpy |
| 组件基准 `c1_src.py`／`c2_vad.py`／`c3_jpeg.py` | **模块级** import（26／24／23 行） | c1 的 `numpy_fir`／`numpy_linear`／`scipy_poly` 三档就是"numpy 自己算"，本来就是被测对象；`ffmpeg_swr`／`ffmpeg_soxr`／`alsa_plughw` 三档不需要数组 |
| 组件基准 `c4_nlp.py` | **不 import numpy**（`compcommon.py` 只在 `read_wav_mono16`／`pct` 两个函数体里 import，77／89 行） | 文本前置链全程可以是纯标准库 |
| TTS 三引擎 | eSpeak 走 ctypes 回调；Piper／Kokoro 的 phonemizer 与 onnxruntime 输入要 numpy | 中 |

**numpy 的固定成本是怎么量出来的（A 级，同一批跑测里的两颗空载探针）**：`C1_src__alsa_plughw` 只跑了一句 `aplay -l`，VmHWM＝**47,132 kB**；`C4_nlp__regex_only` 只跑正则，VmHWM＝**9,384 kB**。差 **37,748 kB ≈ 36.9 MB**＝"解释器＋numpy 1.2x 在场"相对"纯标准库"的净增量。这颗数同时说明：**9.2 MB 那一行不是采样点错，是真的没加载 numpy**（我先前在回复里把这条标成"存疑"，此处公开更正，见第十六节）。

## 三、能不能靠"编译"或"预处理"把 numpy 省掉

分三条路说，每条都挂本页的实测数，没测的明确标未测。

**① 预处理路线（能省，且省得最多的是输入侧）**——重采样这一族里，把降采样交给内核 ALSA 插件或 ffmpeg 子进程，主进程连数组都不需要：

| 档 | 谁在算 | `cpu_per_audio_ms`（0.01＝一个核的 1 %） | VmHWM MB |
|---|---|---|---|
| `ffmpeg_swr` | libswresample 子进程 | 0.005 | 62.7 |
| `ffmpeg_soxr` | soxr 子进程 | 0.0045 | 56.7 |
| `numpy_fir` | numpy＋firwin 自己算 | 0.063 | 164.5 |
| `numpy_linear` | numpy 线性插值 | 0.003 | 53.7 |
| `scipy_poly` | scipy `resample_poly` | 0.093 | 197.8 |

⇒ **结论 1（A）**：输入侧（48k→16k）用 ffmpeg／plughw 预处理比 numpy 自己算便宜 **9～20 倍 CPU**，而且进程里可以不出现 numpy；省下来的就是第二节那 37 MB 固定成本。**代价**是每次多一个子进程（`ffmpeg_swr` 的 `wall_s` 与 `work_s` 差在本页第五节可见），以及 plughw 那条路要把设备枚举留在板上（现在板上没有声卡，`alsa_plughw` 那一档因此只有 `measurable=false`）。

**② 换调用界面（能省一半，但改的是代码不是编译）**：`silero` 那一档 VmHWM＝**122.4 MB**，里面 numpy 只在 `int16→float32／32768` 那一步进场；sherpa-onnx 的 C 接口其实收 float32 指针，若把这一层改成 `array`／`ctypes` 直传（不吃 ndarray），numpy 可以整体不进场。省的上限＝第二节的 36.9 MB，**在这颗板上约等于 MemAvailable 的 5 %**。本轮**没有做这个改造**，只有数（标 B：可行性来自 `accept_waveform()` 签名实测，收益未复跑）。


**③ 编译／静态化路线（本轮一律未测，且板端禁止编译）**：把 VAD＋重采样写成 C、静态链 `libonnxruntime.a`，理论上能连解释器一起砍掉（本进程地板 9.2 MB→几 MB）。但两件事卡着：**(a) 她 10-11 的硬指令＝禁止在开发板上编译**，任何编都要挪到校机（路由见 [[交叉编译主机路由SOP]]）；**(b) 板上 rootfs 零条 `libopencv_*`、OpenCV 只能静态链**（[[板卡镜像实测取证]]），而 c3 那一族的 numpy 是**容器**——`cv2.imencode()` 的输入本身就是 ndarray，图像链去不掉 numpy。⇒ **结论 2**：编译路线**对输入侧与 VAD 有意义、对图像编码没有意义**；本轮**没有产出任何静态件**，这条整体标 D（未测）。

## 四、TTS 主跑逐行读数（6 支作业）

每支作业＝一个进程跑完该引擎的全部用例（补测才改成一用例一进程）。`meta` 行给出引擎自报版本与运行环境，`load` 行给出模型载入耗时与载入完的 VmHWM，`case` 行是每次调用，`phonemes` 行是音位／词表探针，`cli` 行是命令行对照（只有 eSpeak 有）。

**正本选择**：同一支作业有两套 jsonl——`pull/results/`（主跑当场落的）与 `pull/merged/`（10-10 把 `espeak-ng -x` 的事后音位探针追加进去之后的版本）。两边 `case`／`load`／`meta` 行数一致，只有 `phonemes` 行数不同（`kokoro_af_alloy` 2→5、`kokoro_zf_xiaobei` 4→5），所以下面**同名文件一律取 `merged/` 为正本、`results/` 只作对照**；补测九支的单用例文件在第十一小节单独列。

### `espeakng.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `buflength_ms` = 0
  - `engine` = espeakng
  - `env` = {"argv": "bench/bench_espeak.py out results", "python": "3.8.10", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lib` = libespeak-ng.so.1
  - `note` = callback PCM collected in-process, nothing is played; espeakRATE=175
  - `output_mode` = AUDIO_OUTPUT_RETRIEVAL
  - `rate` = 22050
  - `streaming` = true
  - `tool` = eSpeak NG text-to-speech: 1.50  Data at: /usr/lib/aarch64-linux-gnu/espeak-ng-data
  - `voice` = cmn
**load**：`engine`＝espeakng ／ `load_ms`＝294.1 ／ `ts`＝2026-10-09T19:42:29Z ／ `vmhwm_kb`＝32664 ／ `what`＝espeak_Initialize  ＝ **31.9 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T19:42:29Z | mixed1 | whole | 0 | 3.8764 | 2.8 | 63.0 | 61.4843 |  | 1 | 85474 | 22050 | 32.1／32892 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 63.1} |
| 2026-10-09T19:42:29Z | mixed1 | whole | 1 | 3.877 | 0.5 | 40.3 | 96.2897 |  | 1 | 85488 | 22050 | 32.4／33152 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 40.4} |
| 2026-10-09T19:42:29Z | mixed1 | whole | 2 | 3.8764 | 0.5 | 40.3 | 96.2533 |  | 1 | 85475 | 22050 | 32.4／33152 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 40.4} |
| 2026-10-09T19:42:29Z | mixed1 | split | 0 | 3.8772 | 0.5 | 40.3 | 96.1109 |  | 2 | 85493 | 22050 | 32.4／33152 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 40.5} |
| 2026-10-09T19:42:29Z | mixed1 | split | 1 | 3.8764 | 0.5 | 40.4 | 96.0478 |  | 2 | 85475 | 22050 | 32.4／33152 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 40.5} |
| 2026-10-09T19:42:29Z | mixed1 | split | 2 | 3.8767 | 0.5 | 40.4 | 96.0591 |  | 2 | 85481 | 22050 | 32.4／33152 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 40.5} |
| 2026-10-09T19:42:29Z | mixed2 | whole | 0 | 5.9411 | 0.9 | 60.4 | 98.4031 |  | 1 | 131001 | 22050 | 32.5／33292 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 60.6} |
| 2026-10-09T19:42:29Z | mixed2 | whole | 1 | 5.9535 | 0.7 | 60.3 | 98.6658 |  | 1 | 131275 | 22050 | 32.5／33292 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:29Z | mixed2 | whole | 2 | 5.954 | 0.7 | 60.3 | 98.6585 |  | 1 | 131285 | 22050 | 32.5／33292 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:30Z | mixed2 | split | 0 | 5.9405 | 0.7 | 60.3 | 98.4627 |  | 1 | 130988 | 22050 | 32.5／33292 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:30Z | mixed2 | split | 1 | 5.9408 | 0.7 | 60.9 | 97.4992 |  | 1 | 130995 | 22050 | 32.5／33292 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 61.1} |
| 2026-10-09T19:42:30Z | mixed2 | split | 2 | 5.9535 | 0.7 | 60.3 | 98.6543 |  | 1 | 131275 | 22050 | 32.5／33292 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:30Z | zh_only | whole | 0 | 6.1209 | 1.1 | 65.3 | 93.7627 |  | 1 | 134966 | 22050 | 32.7／33508 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 65.6} |
| 2026-10-09T19:42:30Z | zh_only | whole | 1 | 6.121 | 1.0 | 80.4 | 76.1183 |  | 1 | 134968 | 22050 | 32.7／33508 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.18, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:30Z | zh_only | whole | 2 | 6.1209 | 1.0 | 60.3 | 101.4522 |  | 1 | 134966 | 22050 | 32.7／33508 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:30Z | zh_only | split | 0 | 6.121 | 0.9 | 60.3 | 101.447 |  | 1 | 134969 | 22050 | 32.7／33508 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:30Z | zh_only | split | 1 | 6.121 | 1.0 | 60.4 | 101.4071 |  | 1 | 134968 | 22050 | 32.7／33508 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 60.6} |
| 2026-10-09T19:42:30Z | zh_only | split | 2 | 6.121 | 0.9 | 60.3 | 101.4579 |  | 1 | 134967 | 22050 | 32.7／33508 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 60.5} |
| 2026-10-09T19:42:31Z | num_only | whole | 0 | 6.1037 | 0.8 | 80.4 | 75.896 |  | 1 | 134586 | 22050 | 32.8／33540 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.7} |
| 2026-10-09T19:42:31Z | num_only | whole | 1 | 6.103 | 0.6 | 80.4 | 75.9133 |  | 1 | 134572 | 22050 | 32.8／33540 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:31Z | num_only | whole | 2 | 6.1032 | 0.6 | 80.4 | 75.9031 |  | 1 | 134575 | 22050 | 32.8／33540 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:31Z | num_only | split | 0 | 6.1032 | 0.6 | 80.4 | 75.9012 |  | 1 | 134576 | 22050 | 32.8／33540 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:31Z | num_only | split | 1 | 6.1029 | 0.6 | 80.4 | 75.915 |  | 1 | 134570 | 22050 | 32.8／33540 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:31Z | num_only | split | 2 | 6.103 | 0.6 | 80.4 | 75.9128 |  | 1 | 134571 | 22050 | 32.8／33540 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 80.6} |
| 2026-10-09T19:42:32Z | long | whole | 0 | 43.2859 | 0.7 | 445.5 | 97.1677 |  | 1 | 954455 | 22050 | 34.2／35056 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 445.8} |
| 2026-10-09T19:42:32Z | long | whole | 1 | 43.1714 | 0.6 | 441.5 | 97.7781 |  | 1 | 951929 | 22050 | 36.0／36860 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 442.8} |
| 2026-10-09T19:42:33Z | long | split | 0 | 43.1585 | 0.5 | 482.3 | 89.4869 |  | 7 | 951646 | 22050 | 36.0／36864 |  | {"cold": true, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 483.5} |
| 2026-10-09T19:42:33Z | long | split | 1 | 43.1464 | 0.6 | 482.3 | 89.4632 |  | 7 | 951378 | 22050 | 36.0／36864 |  | {"cold": false, "engine": "espeakng", "first_chunk_samples": 1080, "load1": 1.17, "synth_errs": [], "wall_py_ms": 483.5} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/\n_:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/\nphlE55s'o-55_/ (en)r'i:55traI55(zh)_/"} |
| mixed2 |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/\nz.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'iou55_/ (en)steI22t@11s(zh)_/"} |
| zh_only |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "tS;h'i35N_/ p'A21_/ s.'i.35_/ j'iE51n_/ p'Au51_/ k'Au51_/ t@11_/ t'i51_/ s'a55n_/ tS;'iE35_/ ts'ai51_/ ts.'ou55_/ s'a55n_/ ts.'i.55_/ tS;h'iE35n_/ th'i35_/ tS;j'Au55_/ t'Au51_/ kh'o-51_/ ts.h'@35N_/ ph'i35N_/ th'ai35_/"} |
| num_only |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "s.'u55_/ ts.h'u55_/ t'iE51n_/ j'iA55_/ j,i55@r51_!w'u21_/ v'ei55_/\nt'iE51n_/ l'iou35_/ @r53s'i[51_/ 'ei51_/\nS;j'Au51_/ l'y51_/ th'i35_/ s.'@55N_/ t'Au51_/ tS;,iou21sa55n_!tS;h'i55_/ (en)p322sE11nt(zh)_/"} |
| long |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/\n_:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/\nphlE55s'o-55_/ (en)r'i:55traI55(zh)_/\n_:_:_/tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/\nz.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'iou55… |

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "long", "engine": "espeakng", "mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_| ko-11_| ,@55nph,i51s'ei55_| s.w'o55_|\n_:_:_|(en)m'I55S@55n_| f'eI55ld(zh)_|\nphlE55s'o-55_| (en)r'i:55traI55(zh)_|\n_:_:_|tS;h'i21N_| ts'ai51_| s'a55n_| mj'Au21_| x'ou51_| tS;h'i21_| t'ong51_| ,ei35ts.hth,i53th,i53ph'i51_| A11phi11_|\nz.'a35n_| x'ou51_| tS;'iE21n_| ts.h'A35_| ts.,i53ph,i51j'iou55_| (en)steI22t@11s(zh)_|\nS;'i51_| th'ong21_| s.'a51N_| t'iE51n_| ts.'i.55_| x'ou51_| S;'y55_| j'Au51_| S;'iE55n_| tS;'iA55_| ts'ai51_| w'ei51_| l'iou35_|\nz.'a35n_| x'ou51_| t'@21N_| t'ai51_| t,i51,ai35m'ei51_| j'i21n_| tS;h'i35N_| w'A35n_| ts.h'@35N_| f'u51_| w'ei51_|\nts'ai51_| tS;'i51n_| S;'i35N_| tsh'ai21_| tS;'i35_|\nz.'u35_| k'uo21_| xtmi44_| m'ei35_| j'iou21_| S;'i51n_| x'Au51_|\ntS;h'i35N_| tS;'iE21n_| ts.h'A35_| ts.'ei51_| @r53l'iou51_!_| x'o-35_| ts.'ei51_| @r51tS;h'i55_!_| thj'Au51_| S;'iE51n_|\ntS;h'yE51_| z.'@51n_| s.'i.35_| ts.'ong55_| 'y&35n_| S;'y&21n_| ts'o-35_| ts.'@51N_| tS;h'yE51_|\np'@21n_| tsh'i[51_| tsh'o-51_| s.'i.51_| t@11_| tsh'ai21_| j'iA51N_| l'y51_| s.'i.51_| si[51p'A55_!_| l,i35Nli35N_!l'i35N_| ,ei35ts.hz'i51_|\nx'ua21n_| ts.h'ong55_| tS;h'y55_| s.'u51_| l'iA51N_| w'ei51_| l'iou51_|\nm'A21_| l'y51_| s.'a51N_| S;'iE51n_| s.'o-51_| w'ei51_| s'i[51_| ,ai35mp,i53ph,i51'ai35s_|\nthx'o-55_| ,@55ntsho55t'@r55_| (en)rI255p'o@55ts(zh)_| ,@r51ji55_!w'u21_| (en)p344sE11nt(zh)_| s,ei55ph,i51j'iou55_| (en)loU22d_| a11t(zh)_| j,i55li35N_!pA55l'i35N_!_| ph'i51_| sa55nl'i35N_!_| o33n_| 'ei51_| si[11Nl@11_| tsho11z.o-11_|", "ts": "2026-10-09T19:42:34Z", "type": "phonemes", "voice": "cmn"}
```

**命令行对照（`espeak-ng -w`）**

| case | rc | wall_ms | wall_py_ms | VmHWM MB／kB | 其余字段 |
|---|---|---|---|---|---|
| mixed1 | 0 | 68.8 |  |  | {"engine": "espeakng"} |
| mixed2 | 0 | 92.5 |  |  | {"engine": "espeakng"} |
| zh_only | 0 | 91.5 |  |  | {"engine": "espeakng"} |
| num_only | 0 | 96.6 |  |  | {"engine": "espeakng"} |
| long | 0 | 440.5 |  |  | {"engine": "espeakng"} |

### `espeakng_b20.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `buflength_ms` = 20
  - `engine` = espeakng_b20
  - `env` = {"argv": "bench/bench_espeak.py out results", "python": "3.8.10", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lib` = libespeak-ng.so.1
  - `note` = callback PCM collected in-process, nothing is played; espeakRATE=175
  - `output_mode` = AUDIO_OUTPUT_RETRIEVAL
  - `rate` = 22050
  - `streaming` = true
  - `tool` = eSpeak NG text-to-speech: 1.50  Data at: /usr/lib/aarch64-linux-gnu/espeak-ng-data
  - `voice` = cmn
**load**：`engine`＝espeakng_b20 ／ `load_ms`＝29.7 ／ `ts`＝2026-10-09T19:42:35Z ／ `vmhwm_kb`＝32556 ／ `what`＝espeak_Initialize  ＝ **31.8 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T19:42:35Z | mixed1 | whole | 0 | 3.8764 | 0.6 | 40.3 | 96.1581 |  | 1 | 85474 | 22050 | 32.0／32772 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 40.4} |
| 2026-10-09T19:42:35Z | mixed1 | whole | 1 | 3.877 | 0.5 | 40.3 | 96.2793 |  | 1 | 85488 | 22050 | 32.3／33032 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 40.5} |
| 2026-10-09T19:42:35Z | mixed1 | whole | 2 | 3.8764 | 0.5 | 40.3 | 96.2368 |  | 1 | 85475 | 22050 | 32.3／33032 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 40.5} |
| 2026-10-09T19:42:35Z | mixed1 | split | 0 | 3.8772 | 0.5 | 60.4 | 64.1602 |  | 2 | 85493 | 22050 | 32.3／33048 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 60.7} |
| 2026-10-09T19:42:36Z | mixed1 | split | 1 | 3.8764 | 0.5 | 60.4 | 64.1382 |  | 2 | 85475 | 22050 | 32.3／33048 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 60.7} |
| 2026-10-09T19:42:36Z | mixed1 | split | 2 | 3.8767 | 0.5 | 60.4 | 64.1691 |  | 2 | 85481 | 22050 | 32.3／33048 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 60.6} |
| 2026-10-09T19:42:36Z | mixed2 | whole | 0 | 5.9411 | 0.8 | 80.4 | 73.867 |  | 1 | 131001 | 22050 | 32.5／33240 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:36Z | mixed2 | whole | 1 | 5.9535 | 0.7 | 80.4 | 74.0478 |  | 1 | 131275 | 22050 | 32.6／33400 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.7} |
| 2026-10-09T19:42:36Z | mixed2 | whole | 2 | 5.954 | 0.7 | 80.4 | 74.0505 |  | 1 | 131285 | 22050 | 32.6／33400 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:36Z | mixed2 | split | 0 | 5.9405 | 0.7 | 80.4 | 73.8844 |  | 1 | 130988 | 22050 | 32.6／33400 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:36Z | mixed2 | split | 1 | 5.9408 | 0.7 | 80.4 | 73.879 |  | 1 | 130995 | 22050 | 32.6／33400 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:36Z | mixed2 | split | 2 | 5.9535 | 0.7 | 80.4 | 74.0506 |  | 1 | 131275 | 22050 | 32.6／33400 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:37Z | zh_only | whole | 0 | 6.1209 | 1.0 | 80.4 | 76.1036 |  | 1 | 134966 | 22050 | 32.7／33492 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.9} |
| 2026-10-09T19:42:37Z | zh_only | whole | 1 | 6.121 | 1.0 | 80.4 | 76.1234 |  | 1 | 134968 | 22050 | 32.7／33492 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:37Z | zh_only | whole | 2 | 6.1209 | 0.9 | 80.4 | 76.1338 |  | 1 | 134966 | 22050 | 32.7／33492 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.7} |
| 2026-10-09T19:42:37Z | zh_only | split | 0 | 6.121 | 0.9 | 80.4 | 76.1256 |  | 1 | 134969 | 22050 | 32.7／33492 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:37Z | zh_only | split | 1 | 6.121 | 0.9 | 80.4 | 76.1348 |  | 1 | 134968 | 22050 | 32.7／33492 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:37Z | zh_only | split | 2 | 6.121 | 0.9 | 80.4 | 76.1376 |  | 1 | 134967 | 22050 | 32.7／33492 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.7} |
| 2026-10-09T19:42:38Z | num_only | whole | 0 | 6.1037 | 0.7 | 80.4 | 75.8927 |  | 1 | 134586 | 22050 | 32.7／33528 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.9} |
| 2026-10-09T19:42:38Z | num_only | whole | 1 | 6.103 | 0.6 | 80.4 | 75.9059 |  | 1 | 134572 | 22050 | 32.7／33528 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:38Z | num_only | whole | 2 | 6.1032 | 0.6 | 80.4 | 75.9062 |  | 1 | 134575 | 22050 | 32.7／33528 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:38Z | num_only | split | 0 | 6.1032 | 0.6 | 80.4 | 75.8775 |  | 1 | 134576 | 22050 | 32.7／33528 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:38Z | num_only | split | 1 | 6.1029 | 0.6 | 80.4 | 75.8851 |  | 1 | 134570 | 22050 | 32.7／33528 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:38Z | num_only | split | 2 | 6.103 | 0.6 | 80.4 | 75.8984 |  | 1 | 134571 | 22050 | 32.7／33528 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 80.8} |
| 2026-10-09T19:42:39Z | long | whole | 0 | 43.2859 | 0.7 | 487.5 | 88.7953 |  | 1 | 954455 | 22050 | 34.6／35436 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 488.0} |
| 2026-10-09T19:42:40Z | long | whole | 1 | 43.1714 | 0.5 | 488.2 | 88.4257 |  | 1 | 951929 | 22050 | 36.4／37280 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.16, "synth_errs": [], "wall_py_ms": 491.1} |
| 2026-10-09T19:42:40Z | long | split | 0 | 43.1585 | 0.5 | 563.1 | 76.6461 |  | 7 | 951646 | 22050 | 36.4／37284 |  | {"cold": true, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.14, "synth_errs": [], "wall_py_ms": 565.5} |
| 2026-10-09T19:42:41Z | long | split | 1 | 43.1464 | 0.5 | 562.6 | 76.6902 |  | 7 | 951378 | 22050 | 36.4／37284 |  | {"cold": false, "engine": "espeakng_b20", "first_chunk_samples": 441, "load1": 1.14, "synth_errs": [], "wall_py_ms": 565.0} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/\n_:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/\nphlE55s'o-55_/ (en)r'i:55traI55(zh)_/"} |
| mixed2 |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/\nz.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'iou55_/ (en)steI22t@11s(zh)_/"} |
| zh_only |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "tS;h'i35N_/ p'A21_/ s.'i.35_/ j'iE51n_/ p'Au51_/ k'Au51_/ t@11_/ t'i51_/ s'a55n_/ tS;'iE35_/ ts'ai51_/ ts.'ou55_/ s'a55n_/ ts.'i.55_/ tS;h'iE35n_/ th'i35_/ tS;j'Au55_/ t'Au51_/ kh'o-51_/ ts.h'@35N_/ ph'i35N_/ th'ai35_/"} |
| num_only |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "s.'u55_/ ts.h'u55_/ t'iE51n_/ j'iA55_/ j,i55@r51_!w'u21_/ v'ei55_/\nt'iE51n_/ l'iou35_/ @r53s'i[51_/ 'ei51_/\nS;j'Au51_/ l'y51_/ th'i35_/ s.'@55N_/ t'Au51_/ tS;,iou21sa55n_!tS;h'i55_/ (en)p322sE11nt(zh)_/"} |
| long |  |  |  |  |  | {"mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/\n_:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/\nphlE55s'o-55_/ (en)r'i:55traI55(zh)_/\n_:_:_/tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/\nz.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'iou55… |

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "long", "engine": "espeakng_b20", "mode": "split", "post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE", "text": "ts.'o-51_| ko-11_| ,@55nph,i51s'ei55_| s.w'o55_|\n_:_:_|(en)m'I55S@55n_| f'eI55ld(zh)_|\nphlE55s'o-55_| (en)r'i:55traI55(zh)_|\n_:_:_|tS;h'i21N_| ts'ai51_| s'a55n_| mj'Au21_| x'ou51_| tS;h'i21_| t'ong51_| ,ei35ts.hth,i53th,i53ph'i51_| A11phi11_|\nz.'a35n_| x'ou51_| tS;'iE21n_| ts.h'A35_| ts.,i53ph,i51j'iou55_| (en)steI22t@11s(zh)_|\nS;'i51_| th'ong21_| s.'a51N_| t'iE51n_| ts.'i.55_| x'ou51_| S;'y55_| j'Au51_| S;'iE55n_| tS;'iA55_| ts'ai51_| w'ei51_| l'iou35_|\nz.'a35n_| x'ou51_| t'@21N_| t'ai51_| t,i51,ai35m'ei51_| j'i21n_| tS;h'i35N_| w'A35n_| ts.h'@35N_| f'u51_| w'ei51_|\nts'ai51_| tS;'i51n_| S;'i35N_| tsh'ai21_| tS;'i35_|\nz.'u35_| k'uo21_| xtmi44_| m'ei35_| j'iou21_| S;'i51n_| x'Au51_|\ntS;h'i35N_| tS;'iE21n_| ts.h'A35_| ts.'ei51_| @r53l'iou51_!_| x'o-35_| ts.'ei51_| @r51tS;h'i55_!_| thj'Au51_| S;'iE51n_|\ntS;h'yE51_| z.'@51n_| s.'i.35_| ts.'ong55_| 'y&35n_| S;'y&21n_| ts'o-35_| ts.'@51N_| tS;h'yE51_|\np'@21n_| tsh'i[51_| tsh'o-51_| s.'i.51_| t@11_| tsh'ai21_| j'iA51N_| l'y51_| s.'i.51_| si[51p'A55_!_| l,i35Nli35N_!l'i35N_| ,ei35ts.hz'i51_|\nx'ua21n_| ts.h'ong55_| tS;h'y55_| s.'u51_| l'iA51N_| w'ei51_| l'iou51_|\nm'A21_| l'y51_| s.'a51N_| S;'iE51n_| s.'o-51_| w'ei51_| s'i[51_| ,ai35mp,i53ph,i51'ai35s_|\nthx'o-55_| ,@55ntsho55t'@r55_| (en)rI255p'o@55ts(zh)_| ,@r51ji55_!w'u21_| (en)p344sE11nt(zh)_| s,ei55ph,i51j'iou55_| (en)loU22d_| a11t(zh)_| j,i55li35N_!pA55l'i35N_!_| ph'i51_| sa55nl'i35N_!_| o33n_| 'ei51_| si[11Nl@11_| tsho11z.o-11_|", "ts": "2026-10-09T19:42:42Z", "type": "phonemes", "voice": "cmn"}
```

**命令行对照（`espeak-ng -w`）**

| case | rc | wall_ms | wall_py_ms | VmHWM MB／kB | 其余字段 |
|---|---|---|---|---|---|
| mixed1 | 0 | 68.6 |  |  | {"engine": "espeakng_b20"} |
| mixed2 | 0 | 90.7 |  |  | {"engine": "espeakng_b20"} |
| zh_only | 0 | 91.5 |  |  | {"engine": "espeakng_b20"} |
| num_only | 0 | 95.9 |  |  | {"engine": "espeakng_b20"} |
| long | 0 | 438.6 |  |  | {"engine": "espeakng_b20"} |

### `kokoro_af_alloy.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
**load**：`engine`＝kokoro_af_alloy ／ `load_ms`＝24372.9 ／ `ts`＝2026-10-09T20:14:05Z ／ `vmhwm_kb`＝441892 ／ `what`＝onnx_session+voices  ＝ **431.5 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T20:14:40Z | mixed1 | whole | 0 | 5.3547 | 33495.0 | 33495.4 | 0.1599 | 1 | 1 | 128512 | 24000 | 529.9／542664 |  | {"cold": true, "engine": "kokoro_af_alloy", "error": null, "first_chunk_samples": 128512, "load1": 2.51} |
| 2026-10-09T20:15:20Z | mixed1 | split | 0 | 6.3147 | 23409.9 | 40364.0 | 0.1564 | 2 | 2 | 151552 | 24000 | 532.5／545324 |  | {"cold": true, "engine": "kokoro_af_alloy", "error": null, "first_chunk_samples": 89088, "load1": 3.24} |
| 2026-10-09T20:16:22Z | mixed2 | whole | 0 | 10.112 | 61355.1 | 61355.5 | 0.1648 | 1 | 1 | 242688 | 24000 | 645.9／661364 |  | {"cold": true, "engine": "kokoro_af_alloy", "error": null, "first_chunk_samples": 242688, "load1": 3.72} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 | en-us | 95 | tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌɛnpˌiːsˈiː tʃˈaɪniːzlˌɛɾɚ“mˈɪʃən fˈeɪld plˈiːz ɹˈiːtɹaɪ” |  | 0.926 | {} |
| mixed2 | en-us | 221 | tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ θɹˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌ… |  | 0.937 | {} |
| long | en-us | 1200 | tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌɛnpˌiːsˈiː tʃˈaɪniːzlˌɛɾɚ“mˈɪʃən fˈeɪld plˈiːz ɹˈiːtɹaɪ”tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ θɹ… | af_long | 0.935 | {} |
| num_only | en-us | 255 | tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ twˈɛlv pɔɪnt fˈaɪv vˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tˈuː p… | af_num | 0.957 | {} |
| zh_only | en-us | 351 | tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ … | af_zh | 0.937 | {} |

### `kokoro_zf_xiaobei.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `engine` = kokoro_zf_xiaobei
  - `env` = {"argv": "bench/bench_kokoro.py out results", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = cmn
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = zf_xiaobei
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
**load**：`engine`＝kokoro_zf_xiaobei ／ `load_ms`＝23883.5 ／ `ts`＝2026-10-09T19:55:25Z ／ `vmhwm_kb`＝443664 ／ `what`＝onnx_session+voices  ＝ **433.3 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T19:56:01Z | mixed1 | whole | 0 | 4.8 | 35218.1 | 35218.6 | 0.1363 | 1 | 1 | 115200 | 24000 | 562.3／575824 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 115200, "load1": 2.61} |
| 2026-10-09T19:56:36Z | mixed1 | whole | 1 | 4.8 | 34924.2 | 34924.6 | 0.1374 | 1 | 1 | 115200 | 24000 | 643.1／658528 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 115200, "load1": 3.16} |
| 2026-10-09T19:57:14Z | mixed1 | whole | 2 | 4.8 | 37845.7 | 37846.1 | 0.1268 | 1 | 1 | 115200 | 24000 | 643.1／658528 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 115200, "load1": 3.63} |
| 2026-10-09T19:58:00Z | mixed1 | split | 0 | 5.1413 | 20596.7 | 45831.2 | 0.1122 | 2 | 2 | 123392 | 24000 | 643.1／658528 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 50176, "load1": 3.83} |
| 2026-10-09T19:58:45Z | mixed1 | split | 1 | 5.1413 | 20607.9 | 45080.1 | 0.114 | 2 | 2 | 123392 | 24000 | 643.1／658528 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 50176, "load1": 3.92} |
| 2026-10-09T19:59:30Z | mixed1 | split | 2 | 5.1413 | 20434.7 | 44963.1 | 0.1143 | 2 | 2 | 123392 | 24000 | 643.1／658528 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 50176, "load1": 3.96} |
| 2026-10-09T20:00:11Z | mixed2 | whole | 0 | 5.8667 | 40457.7 | 40458.0 | 0.145 | 1 | 1 | 140800 | 24000 | 643.1／658528 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 3.98} |
| 2026-10-09T20:00:51Z | mixed2 | whole | 1 | 5.8667 | 40344.5 | 40344.8 | 0.1454 | 1 | 1 | 140800 | 24000 | 644.4／659900 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 3.99} |
| 2026-10-09T20:01:33Z | mixed2 | whole | 2 | 5.8667 | 41309.5 | 41309.8 | 0.142 | 1 | 1 | 140800 | 24000 | 644.4／659900 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 4.28} |
| 2026-10-09T20:02:18Z | mixed2 | split | 0 | 5.8667 | 45046.3 | 45046.6 | 0.1302 | 1 | 1 | 140800 | 24000 | 644.4／659900 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 4.4} |
| 2026-10-09T20:02:59Z | mixed2 | split | 1 | 5.8667 | 41042.8 | 41043.1 | 0.1429 | 1 | 1 | 140800 | 24000 | 644.7／660208 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 4.21} |
| 2026-10-09T20:03:41Z | mixed2 | split | 2 | 5.8667 | 41637.2 | 41637.6 | 0.1409 | 1 | 1 | 140800 | 24000 | 645.6／661076 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 140800, "load1": 4.1} |
| 2026-10-09T20:04:21Z | zh_only | whole | 0 | 4.3307 | 37033.5 | 37033.8 | 0.1169 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 4.03} |
| 2026-10-09T20:04:54Z | zh_only | whole | 1 | 4.3307 | 32691.0 | 32691.2 | 0.1325 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 3.92} |
| 2026-10-09T20:05:28Z | zh_only | whole | 2 | 4.3307 | 34188.7 | 34189.0 | 0.1267 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 4.01} |
| 2026-10-09T20:06:03Z | zh_only | split | 0 | 4.3307 | 34810.7 | 34811.1 | 0.1244 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 4.0} |
| 2026-10-09T20:06:38Z | zh_only | split | 1 | 4.3307 | 35235.4 | 35235.8 | 0.1229 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 4.07} |
| 2026-10-09T20:07:14Z | zh_only | split | 2 | 4.3307 | 35461.5 | 35461.9 | 0.1221 | 1 | 1 | 103936 | 24000 | 645.6／661076 |  | {"cold": false, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 103936, "load1": 4.32} |
| 2026-10-09T20:08:14Z | num_only | whole | 0 | 7.808 | 55904.3 | 55904.8 | 0.1397 | 1 | 1 | 187392 | 24000 | 645.6／661076 |  | {"cold": true, "engine": "kokoro_zf_xiaobei", "error": null, "first_chunk_samples": 187392, "load1": 4.23} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 | cmn | 124 | phʁɣrɣɣr (en)ˌɛnpˌiːsˈiː(cmn) ʁk“(en)mˈɪʃən fˈeɪld(cmn) (en)plˈiːz ɹˈiːtɹaɪ(cmn)” |  | 0.653 | {"post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE"} |
| mixed2 | cmn | 198 | qɣr phqr qr ʁr qr çɣr (en)ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ(cmn) n ʁr qr ʝʁn (en)dʒˈiː pˈiː jˈuː stˈeɪtəs(cmn) |  | 0.53 | {"post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE"} |
| zh_only | cmn | 218 | qɣr ɕr ʁqn r ɕr ɣr çɣr çqr k qɣn phqr phʁk k phʁqk qn qn qk çr χɣr ʝʁɣɣn qɣn qn |  | 0.362 | {"post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE"} |
| num_only | cmn | 202 | ʁk ʝʁk çqr k (en)wˈɒn tˈuː dˈɒt fˈaɪv(cmn) (en)vˈiː(cmn) çqr qn (en)tˈuː dˈɒt fˈɔː ˈeɪ(cmn) qr r qn ʁɣɣk çr (base)r (en)… |  | 0.653 | {"post_hoc": "espeak-ng -x rerun 2026-10-10 after RUN_ALL_DONE"} |
| long | cmn | 1200 | phʁɣrɣɣr (en)ˌɛnpˌiːsˈiː(cmn) ʁk“(en)mˈɪʃən fˈeɪld(cmn) (en)plˈiːz ɹˈiːtɹaɪ(cmn)”qɣr phqr qr ʁr qr çɣr (en)ˌeɪtʃtˌiːtˌiː… | zf_long | 0.518 | {} |

### `piper_en_US-lessac-medium.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `engine` = piper_en_US-lessac-medium
  - `env` = {"argv": "bench/bench_piper.py out results", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `espeak_version` = 
  - `model` = /root/ttsbench/models/piper/en_US-lessac-medium.onnx
  - `note` = AudioChunk stream collected in-process, nothing is played
  - `phoneme_type` = PhonemeType.ESPEAK
  - `sample_rate` = 22050
  - `streaming` = true
  - `voice` = en_US-lessac-medium
**load**：`engine`＝piper_en_US-lessac-medium ／ `load_ms`＝21769.7 ／ `ts`＝2026-10-09T19:47:32Z ／ `vmhwm_kb`＝135580 ／ `what`＝onnx_session  ＝ **132.4 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T19:47:38Z | mixed1 | whole | 0 | 4.2957 | 5240.3 | 5240.4 | 0.8197 | 1 | 1 | 94720 | 22050 | 216.4／221552 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 94720, "load1": 1.46, "wall_py_ms": 5373.1} |
| 2026-10-09T19:47:42Z | mixed1 | whole | 1 | 4.4002 | 4449.5 | 4449.6 | 0.9889 | 1 | 1 | 97024 | 22050 | 225.3／230736 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 97024, "load1": 1.99, "wall_py_ms": 4452.5} |
| 2026-10-09T19:47:46Z | mixed1 | whole | 2 | 4.2957 | 3875.9 | 3876.0 | 1.1083 | 1 | 1 | 94720 | 22050 | 298.8／306008 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 94720, "load1": 2.23, "wall_py_ms": 3890.5} |
| 2026-10-09T19:47:52Z | mixed1 | split | 0 | 4.5395 | 3355.3 | 5427.9 | 0.8363 | 2 | 2 | 100096 | 22050 | 303.7／310992 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 59392, "load1": 2.45, "wall_py_ms": 5430.4} |
| 2026-10-09T19:47:57Z | mixed1 | split | 1 | 4.5395 | 3326.5 | 5800.4 | 0.7826 | 2 | 2 | 100096 | 22050 | 303.9／311164 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 59904, "load1": 2.82, "wall_py_ms": 5803.0} |
| 2026-10-09T19:48:02Z | mixed1 | split | 2 | 4.3886 | 2928.8 | 4653.0 | 0.9432 | 2 | 2 | 96768 | 22050 | 303.9／311164 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 57344, "load1": 2.99, "wall_py_ms": 4655.4} |
| 2026-10-09T19:48:12Z | mixed2 | whole | 0 | 8.8932 | 10257.8 | 10257.9 | 0.867 | 1 | 1 | 196096 | 22050 | 318.1／325748 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 196096, "load1": 3.38, "wall_py_ms": 10260.4} |
| 2026-10-09T19:48:21Z | mixed2 | whole | 1 | 8.9513 | 8767.8 | 8767.9 | 1.0209 | 1 | 1 | 197376 | 22050 | 338.6／346732 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 197376, "load1": 3.92, "wall_py_ms": 8771.0} |
| 2026-10-09T19:48:31Z | mixed2 | whole | 2 | 9.021 | 10078.8 | 10078.9 | 0.895 | 1 | 1 | 198912 | 22050 | 339.8／347960 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 198912, "load1": 4.32, "wall_py_ms": 10082.2} |
| 2026-10-09T19:48:39Z | mixed2 | split | 0 | 8.9165 | 8236.8 | 8236.9 | 1.0825 | 1 | 1 | 196608 | 22050 | 339.9／348076 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 196608, "load1": 4.37, "wall_py_ms": 8240.3} |
| 2026-10-09T19:48:49Z | mixed2 | split | 1 | 9.0674 | 9879.0 | 9879.1 | 0.9178 | 1 | 1 | 199936 | 22050 | 340.0／348144 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 199936, "load1": 4.63, "wall_py_ms": 9882.1} |
| 2026-10-09T19:48:58Z | mixed2 | split | 2 | 8.9513 | 8747.1 | 8747.2 | 1.0233 | 1 | 1 | 197376 | 22050 | 340.0／348144 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 197376, "load1": 4.69, "wall_py_ms": 8749.7} |
| 2026-10-09T19:49:09Z | zh_only | whole | 0 | 12.4111 | 11389.0 | 11389.1 | 1.0897 | 1 | 1 | 273664 | 22050 | 422.2／432356 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 273664, "load1": 4.88, "wall_py_ms": 11392.1} |
| 2026-10-09T19:49:18Z | zh_only | whole | 1 | 12.8987 | 9018.3 | 9018.4 | 1.4303 | 1 | 1 | 284416 | 22050 | 513.7／525996 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 284416, "load1": 4.75, "wall_py_ms": 9021.5} |
| 2026-10-09T19:49:27Z | zh_only | whole | 2 | 12.6084 | 8553.7 | 8553.8 | 1.474 | 1 | 1 | 278016 | 22050 | 513.7／525996 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 278016, "load1": 4.63, "wall_py_ms": 8556.8} |
| 2026-10-09T19:49:36Z | zh_only | split | 0 | 13.1541 | 8879.2 | 8879.3 | 1.4814 | 1 | 1 | 290048 | 22050 | 519.0／531484 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 290048, "load1": 4.53, "wall_py_ms": 8882.4} |
| 2026-10-09T19:49:44Z | zh_only | split | 1 | 12.4923 | 8584.3 | 8584.4 | 1.4552 | 1 | 1 | 275456 | 22050 | 519.0／531484 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 275456, "load1": 4.49, "wall_py_ms": 8587.4} |
| 2026-10-09T19:49:53Z | zh_only | split | 2 | 12.8639 | 8703.0 | 8703.1 | 1.4781 | 1 | 1 | 283648 | 22050 | 519.0／531484 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 283648, "load1": 4.41, "wall_py_ms": 8706.1} |
| 2026-10-09T19:50:00Z | num_only | whole | 0 | 10.9946 | 6985.8 | 6985.9 | 1.5738 | 1 | 1 | 242432 | 22050 | 530.6／543344 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 242432, "load1": 4.38, "wall_py_ms": 6988.7} |
| 2026-10-09T19:50:07Z | num_only | whole | 1 | 10.7508 | 7023.1 | 7023.1 | 1.5308 | 1 | 1 | 237056 | 22050 | 530.6／543344 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 237056, "load1": 4.32, "wall_py_ms": 7025.8} |
| 2026-10-09T19:50:14Z | num_only | whole | 2 | 10.6347 | 6813.2 | 6813.2 | 1.5609 | 1 | 1 | 234496 | 22050 | 530.6／543344 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 234496, "load1": 4.3, "wall_py_ms": 6815.9} |
| 2026-10-09T19:50:21Z | num_only | split | 0 | 10.8785 | 7190.0 | 7190.1 | 1.513 | 1 | 1 | 239872 | 22050 | 530.6／543344 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 239872, "load1": 4.25, "wall_py_ms": 7192.7} |
| 2026-10-09T19:50:28Z | num_only | split | 1 | 10.9018 | 6924.1 | 6924.1 | 1.5745 | 1 | 1 | 240384 | 22050 | 530.6／543344 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 240384, "load1": 4.23, "wall_py_ms": 6926.9} |
| 2026-10-09T19:50:35Z | num_only | split | 2 | 10.8902 | 7395.2 | 7395.2 | 1.4726 | 1 | 1 | 240128 | 22050 | 530.6／543344 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 240128, "load1": 4.27, "wall_py_ms": 7397.9} |
| 2026-10-09T19:51:20Z | long | whole | 0 | 65.3177 | 2715.8 | 44260.0 | 1.4758 | 6 | 1 | 1440256 | 22050 | 616.2／630980 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 93952, "load1": 4.14, "wall_py_ms": 44271.8} |
| 2026-10-09T19:52:06Z | long | whole | 1 | 65.2713 | 3073.1 | 46599.5 | 1.4007 | 6 | 1 | 1439232 | 22050 | 754.8／772948 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 95744, "load1": 4.14, "wall_py_ms": 46613.5} |
| 2026-10-09T19:52:51Z | long | split | 0 | 65.2249 | 1776.1 | 44709.5 | 1.4589 | 7 | 7 | 1438208 | 22050 | 754.8／772948 |  | {"cold": true, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 58624, "load1": 4.07, "wall_py_ms": 44721.2} |
| 2026-10-09T19:53:36Z | long | split | 1 | 65.3526 | 1860.3 | 44823.3 | 1.458 | 7 | 7 | 1441024 | 22050 | 754.8／772948 |  | {"cold": false, "engine": "piper_en_US-lessac-medium", "error": null, "first_chunk_samples": 64000, "load1": 4.03, "wall_py_ms": 44834.9} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 |  |  |  |  |  | {"text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ ɛ n p ˌ i ː s ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ"} |
| mixed2 |  |  |  |  |  | {"text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   θ ɹ ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː ʲ   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ʒ ˌ i ː p ˌ i … |
| zh_only |  |  |  |  |  | {"text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   … |
| num_only |  |  |  |  |  | {"text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t w ˈ ɛ l v   p ɔ ɪ n t   f ˈ a ɪ v   v ˈ i ː t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ˈ u ː   p ɔ ɪ n t   f ˈ ɔ ː ɹ   ˈ e ɪ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ … |
| long |  |  |  |  |  | {"text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ ɛ n p ˌ i ː s ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ // t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   θ ɹ ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ e ɪ t ʃ t ˌ i ː t ˌ i… |

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "mixed2", "engine": "piper_en_US-lessac-medium", "text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   θ ɹ ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː ʲ   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ʒ ˌ i ː p ˌ i ː j ˈ u ː   s t ˈ æ ɾ ə s", "ts": "2026-10-09T19:48:58Z", "type": "phonemes", "voice": "en_US-lessac-medium"}
```

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "zh_only", "engine": "piper_en_US-lessac-medium", "text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ", "ts": "2026-10-09T19:49:53Z", "type": "phonemes", "voice": "en_US-lessac-medium"}
```

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "num_only", "engine": "piper_en_US-lessac-medium", "text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t w ˈ ɛ l v   p ɔ ɪ n t   f ˈ a ɪ v   v ˈ i ː t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ˈ u ː   p ɔ ɪ n t   f ˈ ɔ ː ɹ   ˈ e ɪ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   n ˈ a ɪ n t i   θ ɹ ˈ i ː   p ɔ ɪ n t   s ˈ ɛ v ə n   p ɚ s ˈ ɛ n t", "ts": "2026-10-09T19:50:35Z", "type": "phonemes", "voice": "en_US-lessac-medium"}
```

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "long", "engine": "piper_en_US-lessac-medium", "text": "t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ ɛ n p ˌ i ː s ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ || t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   θ ɹ ˈ i ː   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː ʲ   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ʒ ˌ i ː p ˌ i ː j ˈ u ː   s t ˈ æ ɾ ə s || t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ˌ i ː ʲ ˌ ɛ m ˈ e ɪ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ || t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ ɹ   ˌ e ɪ t ʃ d ˌ i ː ʲ ˌ ɛ m ˈ a ɪ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ʒ ˈ e ɪ   t w ˈ ɛ n t i   s ˈ ɪ k s   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   d ʒ ˈ e ɪ   t w ˈ ɛ n t i   s ˈ ɛ v ə n   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i ː z l ˌ ɛ ɾ ɚ   t ʃ ˈ a ɪ n i", "ts": "2026-10-09T19:53:36Z", "type": "phonemes", "voice": "en_US-lessac-medium"}
```

### `piper_zh_CN-huayan-medium.jsonl`（正本＝`merged`）
**meta**（起跑时自报）
  - `engine` = piper_zh_CN-huayan-medium
  - `env` = {"argv": "bench/bench_piper.py out results", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `espeak_version` = 
  - `model` = /root/ttsbench/models/piper/zh_CN-huayan-medium.onnx
  - `note` = AudioChunk stream collected in-process, nothing is played
  - `phoneme_type` = PhonemeType.ESPEAK
  - `sample_rate` = 22050
  - `streaming` = true
  - `voice` = zh_CN-huayan-medium
**load**：`engine`＝piper_zh_CN-huayan-medium ／ `load_ms`＝23185.4 ／ `ts`＝2026-10-09T19:43:06Z ／ `vmhwm_kb`＝137276 ／ `what`＝onnx_session  ＝ **134.1 MB**

| 时刻 | case | mode | rep | 音频 s | 首包 ms | 生成 ms | rtf | chunks | segments | samples | rate | VmHWM MB／kB | ctx | 其余字段 |

> ⚠️ **`rtf` 列的口径**（2026-11-02 补，此前多份文档读反过）：本表 `rtf` ＝ **音频毫秒 ÷ 生成毫秒**，**>1 表示快于实时**（与基准大盘页的 `syn_rtf` 同口径）。
> **标准 RTF ＝ 生成÷音频 ＝ 本列的倒数**，<1 才是快。换算示例：本列 `1.4665` ⇒ 标准 RTF `0.682` ⇒ 快于实时 47%。
> `cold: true` ＝ 进程内第一次（含暖机）；`cold: false` ＝ **常驻**，同一 case 的 rep≥1 才是常驻读数。
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T19:43:08Z | mixed1 | whole | 0 | 2.4729 | 1980.4 | 1980.4 | 1.2487 | 1 | 1 | 54528 | 22050 | 182.7／187124 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 54528, "load1": 1.27, "wall_py_ms": 1982.1} |
| 2026-10-09T19:43:10Z | mixed1 | whole | 1 | 2.4729 | 1686.2 | 1686.2 | 1.4665 | 1 | 1 | 54528 | 22050 | 228.3／233748 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 54528, "load1": 1.27, "wall_py_ms": 1687.9} |
| 2026-10-09T19:43:11Z | mixed1 | whole | 2 | 2.0317 | 1392.6 | 1392.6 | 1.4589 | 1 | 1 | 44800 | 22050 | 228.5／233988 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 44800, "load1": 1.49, "wall_py_ms": 1399.3} |
| 2026-10-09T19:43:13Z | mixed1 | split | 0 | 2.9605 | 1135.6 | 1964.5 | 1.507 | 2 | 2 | 65280 | 22050 | 229.5／235048 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 38656, "load1": 1.49, "wall_py_ms": 1966.1} |
| 2026-10-09T19:43:15Z | mixed1 | split | 1 | 3.1811 | 1125.2 | 2060.5 | 1.5439 | 2 | 2 | 70144 | 22050 | 230.7／236276 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 38912, "load1": 1.69, "wall_py_ms": 2062.1} |
| 2026-10-09T19:43:17Z | mixed1 | split | 2 | 2.9722 | 1137.6 | 1974.0 | 1.5057 | 2 | 2 | 65536 | 22050 | 241.3／247100 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 38656, "load1": 1.69, "wall_py_ms": 1975.6} |
| 2026-10-09T19:43:21Z | mixed2 | whole | 0 | 4.702 | 3179.3 | 3179.3 | 1.4789 | 1 | 1 | 103680 | 22050 | 241.8／247620 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 103680, "load1": 2.04, "wall_py_ms": 3181.1} |
| 2026-10-09T19:43:24Z | mixed2 | whole | 1 | 4.5047 | 3650.2 | 3650.3 | 1.2341 | 1 | 1 | 99328 | 22050 | 251.0／257056 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 99328, "load1": 2.04, "wall_py_ms": 3652.1} |
| 2026-10-09T19:43:27Z | mixed2 | whole | 2 | 4.4234 | 3003.7 | 3003.8 | 1.4726 | 1 | 1 | 97536 | 22050 | 251.3／257308 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 97536, "load1": 2.19, "wall_py_ms": 3005.4} |
| 2026-10-09T19:43:30Z | mixed2 | split | 0 | 4.2144 | 2897.0 | 2897.1 | 1.4547 | 1 | 1 | 92928 | 22050 | 251.3／257308 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 92928, "load1": 2.19, "wall_py_ms": 2898.8} |
| 2026-10-09T19:43:33Z | mixed2 | split | 1 | 4.3886 | 2978.9 | 2979.0 | 1.4732 | 1 | 1 | 96768 | 22050 | 251.3／257308 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 96768, "load1": 2.34, "wall_py_ms": 2980.6} |
| 2026-10-09T19:43:36Z | mixed2 | split | 2 | 4.4582 | 3087.5 | 3087.6 | 1.4439 | 1 | 1 | 98304 | 22050 | 251.5／257572 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 98304, "load1": 2.55, "wall_py_ms": 3089.3} |
| 2026-10-09T19:43:40Z | zh_only | whole | 0 | 5.0155 | 3325.7 | 3325.8 | 1.5081 | 1 | 1 | 110592 | 22050 | 252.1／258100 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 110592, "load1": 2.55, "wall_py_ms": 3327.6} |
| 2026-10-09T19:43:43Z | zh_only | whole | 1 | 5.329 | 3545.7 | 3545.8 | 1.5029 | 1 | 1 | 117504 | 22050 | 253.7／259824 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 117504, "load1": 2.67, "wall_py_ms": 3547.6} |
| 2026-10-09T19:43:46Z | zh_only | whole | 2 | 5.1548 | 3383.6 | 3383.6 | 1.5235 | 1 | 1 | 113664 | 22050 | 253.7／259824 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 113664, "load1": 2.77, "wall_py_ms": 3385.4} |
| 2026-10-09T19:43:50Z | zh_only | split | 0 | 4.853 | 3242.8 | 3242.9 | 1.4965 | 1 | 1 | 107008 | 22050 | 253.7／259824 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 107008, "load1": 2.77, "wall_py_ms": 3244.7} |
| 2026-10-09T19:43:53Z | zh_only | split | 1 | 4.8878 | 3260.3 | 3260.4 | 1.4991 | 1 | 1 | 107776 | 22050 | 253.7／259824 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 107776, "load1": 2.87, "wall_py_ms": 3262.1} |
| 2026-10-09T19:43:56Z | zh_only | split | 2 | 5.12 | 3381.5 | 3381.6 | 1.5141 | 1 | 1 | 112896 | 22050 | 254.0／260084 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 112896, "load1": 2.96, "wall_py_ms": 3383.4} |
| 2026-10-09T19:44:00Z | num_only | whole | 0 | 5.0852 | 3360.9 | 3361.0 | 1.513 | 1 | 1 | 112128 | 22050 | 254.0／260084 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 112128, "load1": 2.96, "wall_py_ms": 3362.8} |
| 2026-10-09T19:44:03Z | num_only | whole | 1 | 5.1432 | 3418.8 | 3418.9 | 1.5043 | 1 | 1 | 113408 | 22050 | 254.2／260348 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 113408, "load1": 3.05, "wall_py_ms": 3420.7} |
| 2026-10-09T19:44:07Z | num_only | whole | 2 | 5.0852 | 3443.8 | 3443.8 | 1.4766 | 1 | 1 | 112128 | 22050 | 336.7／344748 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 112128, "load1": 3.12, "wall_py_ms": 3445.8} |
| 2026-10-09T19:44:10Z | num_only | split | 0 | 5.062 | 3578.3 | 3578.3 | 1.4146 | 1 | 1 | 111616 | 22050 | 336.8／344900 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 111616, "load1": 3.19, "wall_py_ms": 3580.1} |
| 2026-10-09T19:44:14Z | num_only | split | 1 | 5.2129 | 3502.3 | 3502.4 | 1.4884 | 1 | 1 | 114944 | 22050 | 336.8／344900 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 114944, "load1": 3.19, "wall_py_ms": 3504.2} |
| 2026-10-09T19:44:17Z | num_only | split | 2 | 4.9226 | 3418.2 | 3418.2 | 1.4401 | 1 | 1 | 108544 | 22050 | 336.8／344900 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 108544, "load1": 3.26, "wall_py_ms": 3420.0} |
| 2026-10-09T19:44:39Z | long | whole | 0 | 30.4065 | 1577.3 | 21733.5 | 1.3991 | 6 | 1 | 670464 | 22050 | 345.1／353344 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 51456, "load1": 3.47, "wall_py_ms": 21739.5} |
| 2026-10-09T19:45:00Z | long | whole | 1 | 30.8477 | 1614.4 | 20948.7 | 1.4725 | 6 | 1 | 680192 | 22050 | 388.4／397696 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 47360, "load1": 3.62, "wall_py_ms": 20954.7} |
| 2026-10-09T19:45:25Z | long | split | 0 | 31.7997 | 1157.0 | 25674.3 | 1.2386 | 7 | 7 | 701184 | 22050 | 391.5／400904 |  | {"cold": true, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 39936, "load1": 4.06, "wall_py_ms": 25680.6} |
| 2026-10-09T19:45:49Z | long | split | 1 | 31.0451 | 1125.8 | 23403.1 | 1.3265 | 7 | 7 | 684544 | 22050 | 391.5／400904 |  | {"cold": false, "engine": "piper_zh_CN-huayan-medium", "error": null, "first_chunk_samples": 38656, "load1": 4.17, "wall_py_ms": 23409.3} |

**音位／词表探针**

| case | 语言 | raw 音位数 | 过滤后 | 进词表 | survival_ratio | 其余字段 |
|---|---|---|---|---|---|---|
| mixed1 |  |  |  |  |  | {"text": "t s . o - 5 k ˈ o - 1   ˌ ɛ n p ˌ i ː s ˈ i ː   s . w ˈ o 5 m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ"} |
| mixed2 |  |  |  |  |  | {"text": "t ɕ h ˈ i 2 ŋ   t s ˈ a i 5   s ˈ a 5 n   m j ˈ ɑ u 2   χ ˈ o u 5   t ɕ h ˈ i 2   t ˈ o n ɡ 5   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ ʐ ˈ a ɜ n   χ ˈ o u 5   t ɕ ˈ i ɛ 2 n   t s . h ˈ ɑ ɜ   d ʒ ˈ i ː   p ˈ i ː   j ˈ u ː   s t ˈ e ɪ t ə s"} |
| zh_only |  |  |  |  |  | {"text": "t ɕ h ˈ i 2 ŋ   p ˈ ɑ 2   s . ˈ i . ɜ   j ˈ i ɛ 5 n   p ˈ ɑ u 5   k ˈ ɑ u 5   t ˈ ə 1   t ˈ i 5   s ˈ a 5 n   t ɕ ˈ i ɛ ɜ   t s ˈ a i 5   t s . ˈ o u 5   s ˈ a 5 n   t s . ˈ i . 5   t ɕ h ˈ i ɛ ɜ n   t h ˈ i ɜ   t ɕ j ˈ ɑ u 5   t ˈ ɑ u 5   k h ˈ o - 5   t s . h ˈ ə ɜ ŋ   p h ˈ i ɜ ŋ   t h ˈ a i ɜ"} |
| num_only |  |  |  |  |  | {"text": "s . ˈ u 5   t s . h ˈ u 5   t ˈ i ɛ 5 n   j ˈ i ɑ 5   s . ˌ i . ɜ ə r 5   t ˈ i ɛ ɜ n   w u 2   v ˈ i ː t ˈ i ɛ 5 n   l ˈ i o u ɜ   ə r 5   t ˈ i ɛ ɜ n   s i ̪ 5   ˈ e ɪ ɕ j ˈ ɑ u 5   l ˈ y 5   t h ˈ i ɜ   s . ˈ ə 5 ŋ   t ˈ ɑ u 5   t ɕ ˈ i o u 2 s . i . ɜ s a 5 n   t ˈ i ɛ ɜ n   t ɕ h i 5   p ə s ˈ ɛ n t"} |
| long |  |  |  |  |  | {"text": "t s . o - 5 k ˈ o - 1   ˌ ɛ n p ˌ i ː s ˈ i ː   s . w ˈ o 5 m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ // t ɕ h ˈ i 2 ŋ   t s ˈ a i 5   s ˈ a 5 n   m j ˈ ɑ u 2   χ ˈ o u 5   t ɕ h ˈ i 2   t ˈ o n ɡ 5   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ ʐ ˈ a ɜ n   χ ˈ o u 5   t ɕ ˈ i ɛ 2 n   t s . h ˈ ɑ ɜ   d ʒ ˈ i ː   p ˈ i ː   j ˈ u ː   s t ˈ e ɪ t ə s // ɕ i 5 t h … |

上面某格的音位串超 400 字被截断，完整原始行（不损）：
```json
{"case": "long", "engine": "piper_zh_CN-huayan-medium", "text": "t s . o - 5 k ˈ o - 1   ˌ ɛ n p ˌ i ː s ˈ i ː   s . w ˈ o 5 m ˈ ɪ ʃ ə n   f ˈ e ɪ l d p l ˈ i ː z   ɹ ˈ i ː t ɹ a ɪ || t ɕ h ˈ i 2 ŋ   t s ˈ a i 5   s ˈ a 5 n   m j ˈ ɑ u 2   χ ˈ o u 5   t ɕ h ˈ i 2   t ˈ o n ɡ 5   ˌ e ɪ t ʃ t ˌ i ː t ˌ i ː p ˈ i ː   ˌ e ɪ p ˌ i ː ʲ ˈ a ɪ ʐ ˈ a ɜ n   χ ˈ o u 5   t ɕ ˈ i ɛ 2 n   t s . h ˈ ɑ ɜ   d ʒ ˈ i ː   p ˈ i ː   j ˈ u ː   s t ˈ e ɪ t ə s || ɕ i 5 t h ˈ o n ɡ 2   s . ˈ ɑ 5 ŋ   t ˈ i ɛ 5 n   t s . ˈ i . 5   χ ˈ o u 5   ɕ ˈ y 5   j ˈ ɑ u 5   ɕ ˈ i ɛ 5 n   t ɕ ˈ i ɑ 5   t s ˈ a i 5   w ˈ e i 5   l ˈ i o u ɜ ʐ ˈ a ɜ n   χ ˈ o u 5   t ˈ ə 2 ŋ   t ˈ a i 5   d ˈ i ː   ˈ ɛ m   ˈ e ɪ   j ˈ i 2 n   t ɕ h ˈ i ɜ ŋ   w ˈ ɑ ɜ n   t s . h ˈ ə ɜ ŋ   f ˈ u 5   w ˈ e i 5 t s ˈ a i 5   t ɕ ˈ i 5 n   ɕ ˈ i ɜ ŋ   t s h ˈ a i 2   t ɕ ˈ i ɜ || ʐ u ɜ k ˈ u o 2   ˌ e ɪ t ʃ d ˌ i ː ʲ ˌ ɛ m ˈ a ɪ   m e i ɜ j ˈ i o u 2   ɕ ˈ i 5 n   χ ˈ ɑ u 5 t ɕ h ˈ i 2 ŋ   t ɕ ˈ i ɛ 2 n   t s . h ˈ ɑ ɜ   d ʒ ˈ e ɪ   ˌ ə r 5 s . i . ɜ l ˈ i o u 5   χ ˈ o - ɜ   d ʒ ˈ e ɪ   ˌ ə r 5 s . i . ɜ t ɕ h ˈ i 5   t h j ˈ ɑ u 5   ɕ ˈ i ɛ 5 n t ɕ h ˈ y ɛ 5   ʐ ˈ ə 5 n   s . ˈ i . ɜ   t s . ˈ o n ɡ 5   j ˈ y æ ɜ n   ɕ ˈ y æ 2 n   t s ˈ o - ɜ   t s . ˈ ə 5 ŋ   t ɕ h ˈ y ɛ 5 || p ˈ ə 2 n   t s h ˈ i ̪ 5   t s h ˈ o - 5   s . ˈ i . 5   t ˈ ə 1   t s h ˈ a i 2   j ˈ i ɑ 5 ŋ   l ˈ y 5   s . ˈ i . 5   s ˈ i ̪ 5 s . i . ɜ p ɑ 5   t ɕ h ˈ i ɛ 5 n   ˌ e ɪ t ʃ z ˈ ɛ d χ ˈ u a 2 n   t s . h ˈ o n ɡ 5   t ɕ h ˈ y 5   s . ˈ u 5   l ˈ i ɑ 5 ŋ   w ˈ e i 5   l ˈ i o u 5 m ˈ ɑ 2   l ˈ y 5   s . ˈ ɑ 5 ŋ   ɕ ˈ i ɛ 5 n   s . ˈ o - 5   w ˈ e i 5   s ˈ i ̪ 5   ˌ ɛ m b ˌ i ː p ˌ i ː ʲ ˈ ɛ s || ð ɪ   ɛ ŋ k ˈ ə ʊ d ə   ɹ ɪ p ˈ ɔ ː t s   ˌ ə r 5 s . i . ɜ j i 5   t ˈ i ɛ ɜ n   w u 2   p ə s ˈ ɛ n t   s ˈ i ː   p ˈ i ː   j ˈ u ː   l ˈ ə ʊ d   a t   j i 5   t ɕ h ˈ i ɛ 5 n   p ˈ ɑ 5 s . i . ɜ   p ˈ i ː   s ˈ a 5 n s . i . ɜ   ˌ ɒ n   ɐ   s ˈ ɪ ŋ ɡ ə l   k ˈ ɔ ː .", "ts": "2026-10-09T19:45:49Z", "type": "phonemes", "voice": "zh_CN-huayan-medium"}
```

### 补测九支（一用例一进程，`pull/results2/*/*.jsonl`）

v4 把长文本与 num 那几档拆成一支作业一个进程各自起跑（台账 §十 结论 15）。**九支的 jsonl 里 `type=case` 行数全是 0**——被杀在 `case` 落盘之前，所以下面只有 `meta`／`load`／`phonemes` 三段；`load` 行的 `vmhwm_kb` 是该进程生前的最后一次采样，整进程口径在第五节。九支的 `.tries`（1 或 2）与前后板况在第十三节。

**`results2/af_long/kokoro_af_alloy.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results2/af_long", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_af_alloy
  - `load_ms` = 25272.6
  - `ts` = 2026-10-09T20:55:01Z
  - `vmhwm_kb` = 441928
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌɛnpˌiːsˈiː tʃˈaɪniːzlˌɛɾɚ“mˈɪʃən fˈeɪld plˈiːz ɹˈiːtɹaɪ”tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ θɹˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ dʒˌiːpˌiːjˈuː stˈæɾəs tʃˈa…
  - `case` = long
  - `engine` = kokoro_af_alloy
  - `lang` = en-us
  - `raw` = tS'aIni:zl,Et#3 tS'aIni:zl,Et#3r- ,Enp,i:s'i: tS'aIni:zl,Et#3 _:_:m'IS@n f'eIld pl'i:z r'i:traI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 Tr'i: tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3r- ,eItSt,i:t,i:p'i:; ,eIp,i:;'aI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 dZ,i:…
  - `survival_ratio` = 0.935
  - `ts` = 2026-10-09T20:55:02Z
  - `voice` = af_alloy

**`results2/af_longw/kokoro_af_alloy.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results2/af_longw", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_af_alloy
  - `load_ms` = 24482.7
  - `ts` = 2026-10-09T21:08:16Z
  - `vmhwm_kb` = 442068
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌɛnpˌiːsˈiː tʃˈaɪniːzlˌɛɾɚ“mˈɪʃən fˈeɪld plˈiːz ɹˈiːtɹaɪ”tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ θɹˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ dʒˌiːpˌiːjˈuː stˈæɾəs tʃˈa…
  - `case` = long
  - `engine` = kokoro_af_alloy
  - `lang` = en-us
  - `raw` = tS'aIni:zl,Et#3 tS'aIni:zl,Et#3r- ,Enp,i:s'i: tS'aIni:zl,Et#3 _:_:m'IS@n f'eIld pl'i:z r'i:traI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 Tr'i: tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3r- ,eItSt,i:t,i:p'i:; ,eIp,i:;'aI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 dZ,i:…
  - `survival_ratio` = 0.935
  - `ts` = 2026-10-09T21:08:17Z
  - `voice` = af_alloy

**`results2/af_mix2/kokoro_af_alloy.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results2/af_mix2", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_af_alloy
  - `load_ms` = 23849.6
  - `ts` = 2026-10-09T21:12:49Z
  - `vmhwm_kb` = 442912
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ θɹˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚɹ ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ dʒˌiːpˌiːjˈuː stˈæɾəs
  - `case` = mixed2
  - `engine` = kokoro_af_alloy
  - `lang` = en-us
  - `raw` = tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 Tr'i: tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3r- ,eItSt,i:t,i:p'i:; ,eIp,i:;'aI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 dZ,i:p,i:j'u: st'at#@s
  - `survival_ratio` = 0.937
  - `ts` = 2026-10-09T21:12:50Z
  - `voice` = af_alloy

**`results2/af_num/kokoro_af_alloy.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results2/af_num", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_af_alloy
  - `load_ms` = 24601.0
  - `ts` = 2026-10-09T21:17:34Z
  - `vmhwm_kb` = 443232
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ twˈɛlv pɔɪnt fˈaɪv vˈiː tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tˈuː pɔɪnt fˈɔːɹ ˈeɪ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ nˈaɪnti θɹˈiː pɔɪnt sˈɛvən pɚsˈɛnt
  - `case` = num_only
  - `engine` = kokoro_af_alloy
  - `lang` = en-us
  - `raw` = tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tw'Elv pOInt f'aIv v'i: tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 t'u: pOInt f'o@r 'eI tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 n'aInti Tr'i: pOInt s'Ev@n p3s'Ent
  - `survival_ratio` = 0.957
  - `ts` = 2026-10-09T21:17:35Z
  - `voice` = af_alloy

**`results2/af_zh/kokoro_af_alloy.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_af_alloy
  - `env` = {"argv": "bench/bench_kokoro.py out results2/af_zh", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = en-us
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = af_alloy
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_af_alloy
  - `load_ms` = 24161.4
  - `ts` = 2026-10-09T21:15:17Z
  - `vmhwm_kb` = 444732
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ tʃˈaɪniːzlˌɛɾɚ …
  - `case` = zh_only
  - `engine` = kokoro_af_alloy
  - `lang` = en-us
  - `raw` = tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,Et#3 tS'aIni:zl,E…
  - `survival_ratio` = 0.937
  - `ts` = 2026-10-09T21:15:18Z
  - `voice` = af_alloy

**`results2/zf_long/kokoro_zf_xiaobei.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `env` = {"argv": "bench/bench_kokoro.py out results2/zf_long", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = cmn
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = zf_xiaobei
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `load_ms` = 28884.8
  - `ts` = 2026-10-09T20:49:19Z
  - `vmhwm_kb` = 439248
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = phʁɣrɣɣr (en)ˌɛnpˌiːsˈiː(cmn) ʁk“(en)mˈɪʃən fˈeɪld(cmn) (en)plˈiːz ɹˈiːtɹaɪ(cmn)”qɣr phqr qr ʁr qr çɣr (en)ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ(cmn) n ʁr qr ʝʁn (en)dʒˈiː pˈiː jˈuː stˈeɪtəs(cmn) qrɣr ʁɣr çqr phʁqk ʁr k r qk qk phqr ɣqr qn n ʁr çɣɣr çqr (en)dˈiː ˈɛm ˈeɪ(cmn) qr qɣn n ʝʁɣɣn xr ɣqr phqr qr qɣn…
  - `case` = long
  - `engine` = kokoro_zf_xiaobei
  - `lang` = cmn
  - `raw` = ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/ _:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/ phlE55s'o-55_/ (en)r'i:55traI55(zh)_/ _:_:_/tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/ z.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'…
  - `survival_ratio` = 0.518
  - `ts` = 2026-10-09T20:49:28Z
  - `voice` = zf_xiaobei

**`results2/zf_longs/kokoro_zf_xiaobei.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `env` = {"argv": "bench/bench_kokoro.py out results2/zf_longs", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = cmn
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = zf_xiaobei
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `load_ms` = 24008.1
  - `ts` = 2026-10-09T21:01:27Z
  - `vmhwm_kb` = 443080
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = phʁɣrɣɣr (en)ˌɛnpˌiːsˈiː(cmn) ʁk“(en)mˈɪʃən fˈeɪld(cmn) (en)plˈiːz ɹˈiːtɹaɪ(cmn)”qɣr phqr qr ʁr qr çɣr (en)ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ(cmn) n ʁr qr ʝʁn (en)dʒˈiː pˈiː jˈuː stˈeɪtəs(cmn) qrɣr ʁɣr çqr phʁqk ʁr k r qk qk phqr ɣqr qn n ʁr çɣɣr çqr (en)dˈiː ˈɛm ˈeɪ(cmn) qr qɣn n ʝʁɣɣn xr ɣqr phqr qr qɣn…
  - `case` = long
  - `engine` = kokoro_zf_xiaobei
  - `lang` = cmn
  - `raw` = ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/ _:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/ phlE55s'o-55_/ (en)r'i:55traI55(zh)_/ _:_:_/tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/ z.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'…
  - `survival_ratio` = 0.518
  - `ts` = 2026-10-09T21:01:29Z
  - `voice` = zf_xiaobei

**`results2/zf_longw/kokoro_zf_xiaobei.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `env` = {"argv": "bench/bench_kokoro.py out results2/zf_longw", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = cmn
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = zf_xiaobei
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `load_ms` = 28214.9
  - `ts` = 2026-10-09T21:20:04Z
  - `vmhwm_kb` = 443092
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = phʁɣrɣɣr (en)ˌɛnpˌiːsˈiː(cmn) ʁk“(en)mˈɪʃən fˈeɪld(cmn) (en)plˈiːz ɹˈiːtɹaɪ(cmn)”qɣr phqr qr ʁr qr çɣr (en)ˌeɪtʃtˌiːtˌiːpˈiː ˌeɪpˌiːˈaɪ(cmn) n ʁr qr ʝʁn (en)dʒˈiː pˈiː jˈuː stˈeɪtəs(cmn) qrɣr ʁɣr çqr phʁqk ʁr k r qk qk phqr ɣqr qn n ʁr çɣɣr çqr (en)dˈiː ˈɛm ˈeɪ(cmn) qr qɣn n ʝʁɣɣn xr ɣqr phqr qr qɣn…
  - `case` = long
  - `engine` = kokoro_zf_xiaobei
  - `lang` = cmn
  - `raw` = ts.'o-51_/ ko-11_/ ,@55nph,i51s'ei55_/ s.w'o55_/ _:_:_/(en)m'I55S@55n_/ f'eI55ld(zh)_/ phlE55s'o-55_/ (en)r'i:55traI55(zh)_/ _:_:_/tS;h'i21N_/ ts'ai51_/ s'a55n_/ mj'Au21_/ x'ou51_/ tS;h'i21_/ t'ong51_/ ,ei35ts.hth,i53th,i53ph'i51_/ A11phi11_/ z.'a35n_/ x'ou51_/ tS;'iE21n_/ ts.h'A35_/ ts.,i53ph,i51j'…
  - `survival_ratio` = 0.518
  - `ts` = 2026-10-09T21:20:05Z
  - `voice` = zf_xiaobei

**`results2/zf_num/kokoro_zf_xiaobei.jsonl`**
  －－以下为 `type=meta` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `env` = {"argv": "bench/bench_kokoro.py out results2/zf_num", "python": "3.11.17", "threads_env": {"HF_ENDPOINT": null, "MKL_NUM_THREADS": "4", "NUMEXPR_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}}
  - `lang` = cmn
  - `model` = /root/ttsbench/models/kokoro/kokoro-v1.0.onnx
  - `n_voices` = 54
  - `note` = create_stream chunks collected in-process, nothing is played
  - `sample_rate` = 24000
  - `streaming` = true
  - `voice` = zf_xiaobei
  - `voices` = ["af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck", "am_santa", "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "…
  - `voices_file` = /root/ttsbench/models/kokoro/voices-v1.0.bin
  －－以下为 `type=load` 行－－
  - `engine` = kokoro_zf_xiaobei
  - `load_ms` = 23974.0
  - `ts` = 2026-10-09T21:10:29Z
  - `vmhwm_kb` = 443692
  - `what` = onnx_session+voices
  －－以下为 `type=phonemes` 行－－
  - `after_vocab_filter` = ʁk ʝʁk çqr k (en)wˈɒn tˈuː dˈɒt fˈaɪv(cmn) (en)vˈiː(cmn) çqr qn (en)tˈuː dˈɒt fˈɔː ˈeɪ(cmn) qr r qn ʁɣɣk çr (base)r (en)pəsˈɛnt(cmn)
  - `case` = num_only
  - `engine` = kokoro_zf_xiaobei
  - `lang` = cmn
  - `raw` = s.'u55_/ ts.h'u55_/ t'iE51n_/ j'iA55_/ j,i55@r51_!w'u21_/ v'ei55_/ t'iE51n_/ l'iou35_/ @r53s'i[51_/ 'ei51_/ S;j'Au51_/ l'y51_/ th'i35_/ s.'@55N_/ t'Au51_/ tS;,iou21sa55n_!tS;h'i55_/ (en)p322sE11nt(zh)_/
  - `survival_ratio` = 0.653
  - `ts` = 2026-10-09T21:10:29Z
  - `voice` = zf_xiaobei

### 只存在于 stdout／poller 日志里的 `case` 行

这些行是从 `pull/logs/*.log`（`resume*.log`、`run_all*.log`、`supervisor.log`）和 `pull/poller*.log`（每 2 分钟 `tail` 一次各 stdout）里正则抓出来的，字段只有 `case／mode／first／gen／audio／rtf／hwm`——**没有 `rep`，也没有 `samples`**，所以不能和上面按 jsonl 落的行混在一张表里横比。最后一列标出同一 `(用例, 模式, 首包 ms)` 在三套 jsonl（`results/`、`merged/`、`results2/*/`）里有没有对应行：`无` 就是**只有日志留下来了**（进程被杀前 jsonl 没落这一行）。

| 用例 | 模式 | 首包 ms | 生成 ms | 音频 s | rtf | hwm MB | jsonl 里有同一行吗 | 出现在 |
|---|---|---|---|---|---|---|---|---|
| `long` | split | 1125.8 | 23403.1 | 31.0451 | 1.3265 | 391.5 | 有 | `run_all.194226.log` |
| `long` | split | 1860.3 | 44823.3 | 65.3526 | 1.458 | 754.8 | 有 | `run_all.194226.log` |
| `mixed1` | split | 0.6 | 40.4 | 3.877 | 96.0601 | 32.2 | 无 | `espeak_smoke.log` |
| `mixed1` | split | 20596.7 | 45831.2 | 5.1413 | 0.1122 | 643.1 | 有 | `poller.log` |
| `mixed1` | split | 20607.9 | 45080.1 | 5.1413 | 0.114 | 643.1 | 有 | `poller.log` |
| `mixed1` | split | 23409.9 | 40364.0 | 6.3147 | 0.1564 | 532.5 | 有 | `run_all.194226.log` |
| `mixed1` | whole | 2.7 | 60.4 | 3.8764 | 64.2293 | 31.9 | 无 | `espeak_smoke.log` |
| `mixed2` | split | 41042.8 | 41043.1 | 5.8667 | 0.1429 | 644.7 | 有 | `poller.log` |
| `mixed2` | split | 45046.3 | 45046.6 | 5.8667 | 0.1302 | 644.4 | 有 | `poller.log` |
| `mixed2` | whole | 40344.5 | 40344.8 | 5.8667 | 0.1454 | 644.4 | 有 | `poller.log` |
| `mixed2` | whole | 40457.7 | 40458.0 | 5.8667 | 0.145 | 643.1 | 有 | `poller.log` |
| `mixed2` | whole | 61355.1 | 61355.5 | 10.112 | 0.1648 | 645.9 | 有 | `poller.log` |
| `num_only` | whole | 55826.6 | 55827.0 | 7.808 | 0.1399 | 602.8 | 无 | `poller4.log` |
| `num_only` | whole | 55904.3 | 55904.8 | 7.808 | 0.1397 | 645.6 | 有 | `poller.log` |
| `zh_only` | split | 34810.7 | 34811.1 | 4.3307 | 0.1244 | 645.6 | 有 | `poller.log` |
| `zh_only` | split | 35235.4 | 35235.8 | 4.3307 | 0.1229 | 645.6 | 有 | `poller.log` |
| `zh_only` | split | 35461.5 | 35461.9 | 4.3307 | 0.1221 | 645.6 | 有 | `run_all.194226.log` |
| `zh_only` | whole | 32691.0 | 32691.2 | 4.3307 | 0.1325 | 645.6 | 有 | `poller.log` |
| `zh_only` | whole | 37033.5 | 37033.8 | 4.3307 | 0.1169 | 645.6 | 有 | `poller.log` |

共抓到 **19 条**不重复的日志行，其中 **3 条在 jsonl 里没有对应行**（表里标`无`的那几行）。台账 §十 结论 14 引用的 `num_only／whole／首包 55,826.6 ms` 就在其中——它**只存在于 `pull/logs/resume3.log`**，进程被杀前 jsonl 没落这一行，所以这一条的证据等级是 B（日志读数、无 jsonl 交叉）。

jsonl 里没有对应行的那些行：`mixed1／split／first=0.6 ms` ／ `mixed1／whole／first=2.7 ms` ／ `num_only／whole／first=55826.6 ms`

## 五、`/usr/bin/time -v` 整进程读数（峰值 RAM 的另一套口径）

正本取 `pull/results/*.time`（主跑 6 支，`Command being timed` 里的 out 目录都是 `results`）＋`pull/results2/*/time.txt`（补测 9 支，各支指向自己的 out 目录）。**`Exit status: 0` 不能单独当"跑成功"的证据**——被信号杀掉的子进程它也写 0（台账 §十 结论 8），所以倒数第二列给出该文件字节数、最后一列给出该作业 jsonl 里的 `type=case` 行数。

| 作业 | `time -v` 件 | B | md5 前 8 | User s | Sys s | CPU ％ | 墙钟 | MaxRSS kB | MaxRSS MB | Major fault | Minor fault | 自愿／非自愿 csw | `Command being timed` 的 out 目录 | 该作业 jsonl 的 case 行数 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `espeakng` | `results/espeakng.time` | 771 | `cc27c770` | 5.61 | 0.63 | 76 | 0:08.18 | 37,752 | 36.9 | 106 | 25128 | 952／524 | `results` | 28 |
| `espeakng_b20` | `results/espeakng_b20.time` | 765 | `370e97ff` | 6.46 | 0.78 | 95 | 0:07.58 | 37,884 | 37.0 | 0 | 25310 | 392／517 | `results` | 28 |
| `kokoro_af_alloy` | `results/kokoro_af_alloy.time` | 832 | `2e11a042` | 582.67 | 1.79 | 336 | 2:53.55 | 678,368 | 662.5 | 550 | 257251 | 2252／43218 | `results` | 3 |
| `kokoro_zf_xiaobei` | `results/kokoro_zf_xiaobei.time` | 839 | `9663dcfb` | 3202.14 | 6.65 | 321 | 16:37.50 | 795,756 | 777.1 | 7265 | 315879 | 11158／469587 | `results` | 19 |
| `piper_en_US-lessac-medium` | `results/piper_en_US-lessac-medium.time` | 802 | `77e78b6b` | 1406.94 | 10.16 | 365 | 6:27.22 | 772,948 | 754.8 | 99 | 205096 | 664／365020 | `results` | 28 |
| `piper_zh_CN-huayan-medium` | `results/piper_zh_CN-huayan-medium.time` | 800 | `a0f8bb9e` | 657.11 | 1.80 | 352 | 3:07.18 | 400,992 | 391.6 | 75 | 117291 | 534／122171 | `results` | 28 |
| `af_long（补测）` | `results2/af_long/time.txt` | 841 | `98df330a` | 365.16 | 2.36 | 279 | 2:11.49 | 735,756 | 718.5 | 695 | 270233 | 2430／59368 | `results2/af_long` | 0 |
| `af_longw（补测）` | `results2/af_longw/time.txt` | 0 | `d41d8cd9` | — | — | — | — | — | — | — | — | — | `—` | 0 |
| `af_mix2（补测）` | `results2/af_mix2/time.txt` | 842 | `5326dc50` | 227.41 | 2.47 | 271 | 1:24.77 | 610,072 | 595.8 | 415 | 236552 | 1609／140358 | `results2/af_mix2` | 0 |
| `af_num（补测）` | `results2/af_num/time.txt` | 840 | `28985138` | 224.62 | 1.77 | 267 | 1:24.58 | 619,548 | 605.0 | 453 | 237353 | 2107／45624 | `results2/af_num` | 0 |
| `af_zh（补测）` | `results2/af_zh/time.txt` | 839 | `3a409a17` | 185.05 | 1.66 | 251 | 1:14.26 | 654,052 | 638.7 | 480 | 247936 | 2195／26190 | `results2/af_zh` | 0 |
| `zf_long（补测）` | `results2/zf_long/time.txt` | 841 | `2909b5d6` | 216.07 | 1.87 | 233 | 1:33.26 | 663,192 | 647.6 | 354 | 251483 | 1595／22961 | `results2/zf_long` | 0 |
| `zf_longs（补测）` | `results2/zf_longs/time.txt` | 845 | `b0d6b037` | 1111.99 | 2.54 | 341 | 5:26.01 | 623,056 | 608.5 | 2413 | 248130 | 4403／89716 | `results2/zf_longs` | 0 |
| `zf_longw（补测）` | `results2/zf_longw/time.txt` | 0 | `d41d8cd9` | — | — | — | — | — | — | — | — | — | `—` | 0 |
| `zf_num（补测）` | `results2/zf_num/time.txt` | 840 | `ecf4be1c` | 209.08 | 1.63 | 269 | 1:18.08 | 613,932 | 599.5 | 151 | 237628 | 1613／20349 | `results2/zf_num` | 0 |

**两支 0 字节**：`results2/af_longw/time.txt` 与 `results2/zf_longw/time.txt` 都是空文件（md5 `d41d8cd9…`＝空串）——子进程被 SIGKILL，`/usr/bin/time` 来不及写报表，表里留的是空而不是漏抄。

**一处归属更正**：`pull/merged/kokoro_af_alloy.time` 与 `results2/af_long/time.txt` **md5 完全相同**（`98df330a…`），而它自己的 `Command being timed` 写的是 `bench_kokoro.py out results2/af_long` ⇒ 它是 **af_long 那次补测**的副本，回传时被按主跑名字落在了 `merged/` 下，**不能当 af_alloy 主跑的整进程读数**。af_alloy 主跑的正本是 `pull/results/kokoro_af_alloy.time`：MaxRSS **678,368 kB＝662.5 MB**、User 582.67 s、墙钟 2:53.55、CPU 336 %。这条和内核日志对得上：`dmesg` 里主跑那次 `pid 3029 anon-rss:676432kB` 与 678,368 kB 差 1,936 kB（＝匿名页与整进程 MaxRSS 的口径差），而补测 `pid 8028 anon-rss:733,028kB` 对得上 735,756 kB。其余五支 `merged/*.time` 的 `Command being timed` 都是 `out results`、字节数与 `results/` 版本一致，没有同类问题。

## 六、生成音频清单（`pull/out/`，144 件，只落盘不出声）

命名＝`引擎__用例__模式__r重复序号.wav`／`引擎__用例__cli.wav`。时长用 `wave` 模块直接读文件头，不是估算。

| 文件 | 字节 | 采样率 | 声道 | 位宽 | 时长 s |
|---|---|---|---|---|---|
| `espeakng__long__cli.wav` | 1,903,988 | 22050 | 1 | 16 bit | 43.17 |
| `espeakng__long__split__r0.wav` | 1,903,336 | 22050 | 1 | 16 bit | 43.16 |
| `espeakng__long__split__r1.wav` | 1,902,800 | 22050 | 1 | 16 bit | 43.15 |
| `espeakng__long__whole__r0.wav` | 1,908,954 | 22050 | 1 | 16 bit | 43.29 |
| `espeakng__long__whole__r1.wav` | 1,903,902 | 22050 | 1 | 16 bit | 43.17 |
| `espeakng__mixed1__cli.wav` | 183,958 | 22050 | 1 | 16 bit | 4.17 |
| `espeakng__mixed1__split__r0.wav` | 171,030 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed1__split__r1.wav` | 170,994 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed1__split__r2.wav` | 171,006 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed1__whole__r0.wav` | 170,992 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed1__whole__r1.wav` | 171,020 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed1__whole__r2.wav` | 170,994 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng__mixed2__cli.wav` | 262,006 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng__mixed2__split__r0.wav` | 262,020 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng__mixed2__split__r1.wav` | 262,034 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng__mixed2__split__r2.wav` | 262,594 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng__mixed2__whole__r0.wav` | 262,046 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng__mixed2__whole__r1.wav` | 262,594 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng__mixed2__whole__r2.wav` | 262,614 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng__num_only__cli.wav` | 266,944 | 22050 | 1 | 16 bit | 6.05 |
| `espeakng__num_only__split__r0.wav` | 269,196 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__num_only__split__r1.wav` | 269,184 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__num_only__split__r2.wav` | 269,186 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__num_only__whole__r0.wav` | 269,216 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__num_only__whole__r1.wav` | 269,188 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__num_only__whole__r2.wav` | 269,194 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng__zh_only__cli.wav` | 269,960 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__split__r0.wav` | 269,982 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__split__r1.wav` | 269,980 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__split__r2.wav` | 269,978 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__whole__r0.wav` | 269,976 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__whole__r1.wav` | 269,980 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng__zh_only__whole__r2.wav` | 269,976 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__long__cli.wav` | 1,903,988 | 22050 | 1 | 16 bit | 43.17 |
| `espeakng_b20__long__split__r0.wav` | 1,903,336 | 22050 | 1 | 16 bit | 43.16 |
| `espeakng_b20__long__split__r1.wav` | 1,902,800 | 22050 | 1 | 16 bit | 43.15 |
| `espeakng_b20__long__whole__r0.wav` | 1,908,954 | 22050 | 1 | 16 bit | 43.29 |
| `espeakng_b20__long__whole__r1.wav` | 1,903,902 | 22050 | 1 | 16 bit | 43.17 |
| `espeakng_b20__mixed1__cli.wav` | 183,958 | 22050 | 1 | 16 bit | 4.17 |
| `espeakng_b20__mixed1__split__r0.wav` | 171,030 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed1__split__r1.wav` | 170,994 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed1__split__r2.wav` | 171,006 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed1__whole__r0.wav` | 170,992 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed1__whole__r1.wav` | 171,020 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed1__whole__r2.wav` | 170,994 | 22050 | 1 | 16 bit | 3.88 |
| `espeakng_b20__mixed2__cli.wav` | 262,006 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng_b20__mixed2__split__r0.wav` | 262,020 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng_b20__mixed2__split__r1.wav` | 262,034 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng_b20__mixed2__split__r2.wav` | 262,594 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng_b20__mixed2__whole__r0.wav` | 262,046 | 22050 | 1 | 16 bit | 5.94 |
| `espeakng_b20__mixed2__whole__r1.wav` | 262,594 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng_b20__mixed2__whole__r2.wav` | 262,614 | 22050 | 1 | 16 bit | 5.95 |
| `espeakng_b20__num_only__cli.wav` | 266,944 | 22050 | 1 | 16 bit | 6.05 |
| `espeakng_b20__num_only__split__r0.wav` | 269,196 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__num_only__split__r1.wav` | 269,184 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__num_only__split__r2.wav` | 269,186 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__num_only__whole__r0.wav` | 269,216 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__num_only__whole__r1.wav` | 269,188 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__num_only__whole__r2.wav` | 269,194 | 22050 | 1 | 16 bit | 6.10 |
| `espeakng_b20__zh_only__cli.wav` | 269,960 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__split__r0.wav` | 269,982 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__split__r1.wav` | 269,980 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__split__r2.wav` | 269,978 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__whole__r0.wav` | 269,976 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__whole__r1.wav` | 269,980 | 22050 | 1 | 16 bit | 6.12 |
| `espeakng_b20__zh_only__whole__r2.wav` | 269,976 | 22050 | 1 | 16 bit | 6.12 |
| `kokoro_af_alloy__mixed1__split__r0.wav` | 303,148 | 24000 | 1 | 16 bit | 6.31 |
| `kokoro_af_alloy__mixed1__whole__r0.wav` | 257,068 | 24000 | 1 | 16 bit | 5.35 |
| `kokoro_af_alloy__mixed2__whole__r0.wav` | 485,420 | 24000 | 1 | 16 bit | 10.11 |
| `kokoro_zf_xiaobei__mixed1__split__r0.wav` | 246,828 | 24000 | 1 | 16 bit | 5.14 |
| `kokoro_zf_xiaobei__mixed1__split__r1.wav` | 246,828 | 24000 | 1 | 16 bit | 5.14 |
| `kokoro_zf_xiaobei__mixed1__split__r2.wav` | 246,828 | 24000 | 1 | 16 bit | 5.14 |
| `kokoro_zf_xiaobei__mixed1__whole__r0.wav` | 230,444 | 24000 | 1 | 16 bit | 4.80 |
| `kokoro_zf_xiaobei__mixed1__whole__r1.wav` | 230,444 | 24000 | 1 | 16 bit | 4.80 |
| `kokoro_zf_xiaobei__mixed1__whole__r2.wav` | 230,444 | 24000 | 1 | 16 bit | 4.80 |
| `kokoro_zf_xiaobei__mixed2__split__r0.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__mixed2__split__r1.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__mixed2__split__r2.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__mixed2__whole__r0.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__mixed2__whole__r1.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__mixed2__whole__r2.wav` | 281,644 | 24000 | 1 | 16 bit | 5.87 |
| `kokoro_zf_xiaobei__num_only__whole__r0.wav` | 374,828 | 24000 | 1 | 16 bit | 7.81 |
| `kokoro_zf_xiaobei__zh_only__split__r0.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `kokoro_zf_xiaobei__zh_only__split__r1.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `kokoro_zf_xiaobei__zh_only__split__r2.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `kokoro_zf_xiaobei__zh_only__whole__r0.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `kokoro_zf_xiaobei__zh_only__whole__r1.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `kokoro_zf_xiaobei__zh_only__whole__r2.wav` | 207,916 | 24000 | 1 | 16 bit | 4.33 |
| `piper_en_US-lessac-medium__long__split__r0.wav` | 2,876,460 | 22050 | 1 | 16 bit | 65.22 |
| `piper_en_US-lessac-medium__long__split__r1.wav` | 2,882,092 | 22050 | 1 | 16 bit | 65.35 |
| `piper_en_US-lessac-medium__long__whole__r0.wav` | 2,880,556 | 22050 | 1 | 16 bit | 65.32 |
| `piper_en_US-lessac-medium__long__whole__r1.wav` | 2,878,508 | 22050 | 1 | 16 bit | 65.27 |
| `piper_en_US-lessac-medium__mixed1__split__r0.wav` | 200,236 | 22050 | 1 | 16 bit | 4.54 |
| `piper_en_US-lessac-medium__mixed1__split__r1.wav` | 200,236 | 22050 | 1 | 16 bit | 4.54 |
| `piper_en_US-lessac-medium__mixed1__split__r2.wav` | 193,580 | 22050 | 1 | 16 bit | 4.39 |
| `piper_en_US-lessac-medium__mixed1__whole__r0.wav` | 189,484 | 22050 | 1 | 16 bit | 4.30 |
| `piper_en_US-lessac-medium__mixed1__whole__r1.wav` | 194,092 | 22050 | 1 | 16 bit | 4.40 |
| `piper_en_US-lessac-medium__mixed1__whole__r2.wav` | 189,484 | 22050 | 1 | 16 bit | 4.30 |
| `piper_en_US-lessac-medium__mixed2__split__r0.wav` | 393,260 | 22050 | 1 | 16 bit | 8.92 |
| `piper_en_US-lessac-medium__mixed2__split__r1.wav` | 399,916 | 22050 | 1 | 16 bit | 9.07 |
| `piper_en_US-lessac-medium__mixed2__split__r2.wav` | 394,796 | 22050 | 1 | 16 bit | 8.95 |
| `piper_en_US-lessac-medium__mixed2__whole__r0.wav` | 392,236 | 22050 | 1 | 16 bit | 8.89 |
| `piper_en_US-lessac-medium__mixed2__whole__r1.wav` | 394,796 | 22050 | 1 | 16 bit | 8.95 |
| `piper_en_US-lessac-medium__mixed2__whole__r2.wav` | 397,868 | 22050 | 1 | 16 bit | 9.02 |
| `piper_en_US-lessac-medium__num_only__split__r0.wav` | 479,788 | 22050 | 1 | 16 bit | 10.88 |
| `piper_en_US-lessac-medium__num_only__split__r1.wav` | 480,812 | 22050 | 1 | 16 bit | 10.90 |
| `piper_en_US-lessac-medium__num_only__split__r2.wav` | 480,300 | 22050 | 1 | 16 bit | 10.89 |
| `piper_en_US-lessac-medium__num_only__whole__r0.wav` | 484,908 | 22050 | 1 | 16 bit | 10.99 |
| `piper_en_US-lessac-medium__num_only__whole__r1.wav` | 474,156 | 22050 | 1 | 16 bit | 10.75 |
| `piper_en_US-lessac-medium__num_only__whole__r2.wav` | 469,036 | 22050 | 1 | 16 bit | 10.63 |
| `piper_en_US-lessac-medium__zh_only__split__r0.wav` | 580,140 | 22050 | 1 | 16 bit | 13.15 |
| `piper_en_US-lessac-medium__zh_only__split__r1.wav` | 550,956 | 22050 | 1 | 16 bit | 12.49 |
| `piper_en_US-lessac-medium__zh_only__split__r2.wav` | 567,340 | 22050 | 1 | 16 bit | 12.86 |
| `piper_en_US-lessac-medium__zh_only__whole__r0.wav` | 547,372 | 22050 | 1 | 16 bit | 12.41 |
| `piper_en_US-lessac-medium__zh_only__whole__r1.wav` | 568,876 | 22050 | 1 | 16 bit | 12.90 |
| `piper_en_US-lessac-medium__zh_only__whole__r2.wav` | 556,076 | 22050 | 1 | 16 bit | 12.61 |
| `piper_zh_CN-huayan-medium__long__split__r0.wav` | 1,402,412 | 22050 | 1 | 16 bit | 31.80 |
| `piper_zh_CN-huayan-medium__long__split__r1.wav` | 1,369,132 | 22050 | 1 | 16 bit | 31.05 |
| `piper_zh_CN-huayan-medium__long__whole__r0.wav` | 1,340,972 | 22050 | 1 | 16 bit | 30.41 |
| `piper_zh_CN-huayan-medium__long__whole__r1.wav` | 1,360,428 | 22050 | 1 | 16 bit | 30.85 |
| `piper_zh_CN-huayan-medium__mixed1__split__r0.wav` | 130,604 | 22050 | 1 | 16 bit | 2.96 |
| `piper_zh_CN-huayan-medium__mixed1__split__r1.wav` | 140,332 | 22050 | 1 | 16 bit | 3.18 |
| `piper_zh_CN-huayan-medium__mixed1__split__r2.wav` | 131,116 | 22050 | 1 | 16 bit | 2.97 |
| `piper_zh_CN-huayan-medium__mixed1__whole__r0.wav` | 109,100 | 22050 | 1 | 16 bit | 2.47 |
| `piper_zh_CN-huayan-medium__mixed1__whole__r1.wav` | 109,100 | 22050 | 1 | 16 bit | 2.47 |
| `piper_zh_CN-huayan-medium__mixed1__whole__r2.wav` | 89,644 | 22050 | 1 | 16 bit | 2.03 |
| `piper_zh_CN-huayan-medium__mixed2__split__r0.wav` | 185,900 | 22050 | 1 | 16 bit | 4.21 |
| `piper_zh_CN-huayan-medium__mixed2__split__r1.wav` | 193,580 | 22050 | 1 | 16 bit | 4.39 |
| `piper_zh_CN-huayan-medium__mixed2__split__r2.wav` | 196,652 | 22050 | 1 | 16 bit | 4.46 |
| `piper_zh_CN-huayan-medium__mixed2__whole__r0.wav` | 207,404 | 22050 | 1 | 16 bit | 4.70 |
| `piper_zh_CN-huayan-medium__mixed2__whole__r1.wav` | 198,700 | 22050 | 1 | 16 bit | 4.50 |
| `piper_zh_CN-huayan-medium__mixed2__whole__r2.wav` | 195,116 | 22050 | 1 | 16 bit | 4.42 |
| `piper_zh_CN-huayan-medium__num_only__split__r0.wav` | 223,276 | 22050 | 1 | 16 bit | 5.06 |
| `piper_zh_CN-huayan-medium__num_only__split__r1.wav` | 229,932 | 22050 | 1 | 16 bit | 5.21 |
| `piper_zh_CN-huayan-medium__num_only__split__r2.wav` | 217,132 | 22050 | 1 | 16 bit | 4.92 |
| `piper_zh_CN-huayan-medium__num_only__whole__r0.wav` | 224,300 | 22050 | 1 | 16 bit | 5.09 |
| `piper_zh_CN-huayan-medium__num_only__whole__r1.wav` | 226,860 | 22050 | 1 | 16 bit | 5.14 |
| `piper_zh_CN-huayan-medium__num_only__whole__r2.wav` | 224,300 | 22050 | 1 | 16 bit | 5.09 |
| `piper_zh_CN-huayan-medium__zh_only__split__r0.wav` | 214,060 | 22050 | 1 | 16 bit | 4.85 |
| `piper_zh_CN-huayan-medium__zh_only__split__r1.wav` | 215,596 | 22050 | 1 | 16 bit | 4.89 |
| `piper_zh_CN-huayan-medium__zh_only__split__r2.wav` | 225,836 | 22050 | 1 | 16 bit | 5.12 |
| `piper_zh_CN-huayan-medium__zh_only__whole__r0.wav` | 221,228 | 22050 | 1 | 16 bit | 5.02 |
| `piper_zh_CN-huayan-medium__zh_only__whole__r1.wav` | 235,052 | 22050 | 1 | 16 bit | 5.33 |
| `piper_zh_CN-huayan-medium__zh_only__whole__r2.wav` | 227,372 | 22050 | 1 | 16 bit | 5.15 |

合计 **144 件 / 69,813,780 字节**。试听按引擎名对照：`espeakng__*`／`piper_zh_CN-huayan-medium__*`／`piper_en_US-lessac-medium__*`／`kokoro_zf_xiaobei__*`／`kokoro_af_alloy__*`。

## 七、C1 采样率／重采样（输入侧）

六档全跑在同一支 `fix/src_48k_mo.wav`（48 kHz 单声道 60 s）上，两模式：`stream`＝按 20 ms 分块喂、`whole`＝整档一次算。`cpu_per_audio_ms` 是这一族的判据列（0.01＝一个核的 1 %）。`alsa_plughw` 那档落在 `measurable=false`（板上没声卡）。

原始文件＝板上 `/root/compbench/results/`，逐字节副本 `S:\apps\llm\agentwork\comp-bench\pull\results\`（脚本与夹具位置见台账 `#125`～`#139`）。每张表**列出该文件里出现过的全部字段**，不做列筛选。

### `C1_src__alsa_plughw.jsonl`
  - `argv` = c1_src.py alsa_plughw
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 690352, "SwapTotal": 0, "load1": 0.31}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（1 条）**

| ts | case | mode | measurable | aplay_l | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:02:57Z | plughw_capture_48k_to_16k | whole | false |  | 850.0 | 47,132 | 46.0 | L0.31/A673/C127 |

### `C1_src__ffmpeg_soxr.jsonl`
  - `argv` = c1_src.py ffmpeg_soxr
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 690076, "SwapTotal": 0, "load1": 0.28}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | work_s | gen_ms | p50_ms | rtf | out_samples | rc | cpu_ms | wall_s | first_ms | p95_ms | max_ms | cpu_ms_proc | cpu_per_audio_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:15:50Z | 48k_mono->16k | whole | 1 | 66.922 | 1022.6 | 1022.6 | 65.4445 | 1070754 | 0 | 1000.0 |  |  |  |  |  |  | 57,876 | 56.5 | L0.28/A669/C85 |
| 2026-10-09T22:16:10Z | 48k_mono->16k | stream | 1000 | 20.0 |  | 0.029 |  | 302720 |  | 1120.0 | 20.0 | 1080.2 | 0.105 | 0.135 | 90.0 | 0.0045 | 58,104 | 56.7 | L0.2/A659/C85 |

### `C1_src__ffmpeg_swr.jsonl`
  - `argv` = c1_src.py ffmpeg_swr
  - `block_ms` = 20.0
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 696524, "SwapTotal": 0, "load1": 0.16}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | p50_ms | rtf | out_samples | rc | cpu_ms | wall_s | first_ms | p95_ms | max_ms | cpu_ms_proc | cpu_per_audio_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:15:26Z | 48k_mono->16k | whole | 1 | 66.922 | 3819.2 | 3819.2 | 17.5223 | 1070754 | 0 | 970.0 |  |  |  |  |  |  | 57,520 | 56.2 | L0.31/A675/C85 |
| 2026-10-09T22:15:27Z | 48k_stereo->16k | whole | 1 | 66.922 | 1095.9 | 1095.9 | 61.0674 | 1070754 | 0 | 1060.0 |  |  |  |  |  |  | 64,232 | 62.7 | L0.31/A673/C85 |
| 2026-10-09T22:15:47Z | 48k_mono->16k | stream | 1000 | 20.0 |  | 0.028 |  | 302720 |  | 1180.0 | 20.0 | 1080.1 | 0.087 | 0.132 | 100.0 | 0.005 | 64,232 | 62.7 | L0.22/A660/C85 |

**cli 行（1 条）**

| ts | case | mode | rc | stderr | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:15:47Z | ffmpeg_tail | stream | 0 |  | 1180.0 | 64,232 | 62.7 | L0.22/A668/C85 |

### `C1_src__numpy_fir.jsonl`
  - `argv` = c1_src.py numpy_fir
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 662476, "SwapTotal": 0, "load1": 0.36}
  - `cutoff_hz` = 7600
  - `python` = 3.8.10
  - `taps` = 96
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | work_s | gen_ms | p50_ms | rtf | out_samples | rc | cpu_ms | wall_s | first_ms | p95_ms | max_ms | cpu_ms_proc | cpu_per_audio_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:02:15Z | 48k_mono->16k | whole | 1 | 66.922 | 1778.5 | 1778.5 | 37.6288 | 1070754 | 0 | 4760.0 |  |  |  |  |  |  | 168,428 | 164.5 | L0.36/A645/C127 |
| 2026-10-09T22:02:35Z | 48k_mono->16k | stream | 1000 | 20.0 |  | 1.194 |  | 320000 |  | 6030.0 | 20.0 | 2.0 | 1.767 | 2.24 | 1260.0 | 0.063 | 168,428 | 164.5 | L0.34/A638/C127 |

### `C1_src__numpy_linear.jsonl`
  - `argv` = c1_src.py numpy_linear
  - `block_ms` = 20.0
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 690056, "SwapTotal": 0, "load1": 0.34}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | work_s | gen_ms | p50_ms | rtf | out_samples | rc | cpu_ms | wall_s | first_ms | p95_ms | max_ms | cpu_ms_proc | cpu_per_audio_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:02:36Z | 48k_mono->16k | whole | 1 | 66.922 | 5.7 | 5.7 | 11679.8349 | 1070754 | 0 | 840.0 |  |  |  |  |  |  | 48,812 | 47.7 | L0.34/A672/C127 |
| 2026-10-09T22:02:56Z | 48k_mono->16k | stream | 1000 | 20.0 |  | 0.031 |  | 320000 |  | 930.0 | 20.0 | 0.2 | 0.082 | 0.112 | 60.0 | 0.003 | 55,028 | 53.7 | L0.31/A671/C127 |

### `C1_src__scipy_poly.jsonl`
  - `argv` = c1_src.py scipy_poly
  - `block_ms` = 20.0
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 661612, "SwapTotal": 0, "load1": 0.34}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | p50_ms | rtf | out_samples | rc | cpu_ms | wall_s | first_ms | p95_ms | max_ms | cpu_ms_proc | cpu_per_audio_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:01:48Z | 48k_mono->16k | whole | 1 | 66.922 | 937.8 | 937.8 | 71.3571 | 1070754 | 0 | 3990.0 |  |  |  |  |  |  | 127,136 | 124.2 | L0.34/A630/C115 |
| 2026-10-09T22:01:50Z | 48k_stereo->16k | whole | 1 | 66.922 | 1934.5 | 1934.5 | 34.5938 | 2141508 | 0 | 5920.0 |  |  |  |  |  |  | 202,544 | 197.8 | L0.34/A636/C121 |
| 2026-10-09T22:02:10Z | 48k_mono->16k | stream | 1000 | 20.0 |  | 1.773 |  | 320000 |  | 7810.0 | 20.0 | 2.7 | 2.574 | 3.598 | 1860.0 | 0.093 | 202,544 | 197.8 | L0.31/A631/C121 |


## 八、C2 语音活动检测（分段侧）

三族五档（能量 FSM 按三个阈值分开记账）。`work_s`＝被测素材时长，`speech_s`＝判为语音的总长，`n_intervals`＝段数，`first_speech_s`＝首个语音起点。分段明细在第十二节，可逐段核。

原始文件＝板上 `/root/compbench/results/`，逐字节副本 `S:\apps\llm\agentwork\comp-bench\pull\results\`（脚本与夹具位置见台账 `#125`～`#139`）。每张表**列出该文件里出现过的全部字段**，不做列筛选。

### `C2_vad__energy_e-45.jsonl`
  - `argv` = c2_vad.py energy_fsm
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 698600, "SwapTotal": 0, "load1": 0.27}
  - `enter` = -45.0
  - `exit` = -50.0
  - `frame_ms` = 30.0
  - `hop_ms` = 10.0
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | rtf | p50_ms | p95_ms | max_ms | first_speech_s | n_intervals | speech_s | thresh_dbfs | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:07:02Z | speech16k | scan | 6690 | 66.922 | 727.7 | 91.959 | 0.102 | 0.105 | 0.439 | 0.0 | 1 | 66.84 | -45/-50 | 1560.0 | 49,288 | 48.1 | L0.27/A680/C127 |
| 2026-10-09T22:07:05Z | long16k | scan | 28946 | 289.489 | 3131.2 | 92.452 | 0.102 | 0.104 | 0.411 | 0.0 | 13 | 284.02 | -45/-50 | 4730.0 | 78,548 | 76.7 | L0.33/A679/C127 |
| 2026-10-09T22:07:06Z | quiet64db | scan | 5998 | 60.0 | 667.5 | 89.884 | 0.102 | 0.104 | 0.653 |  | 0 | 0 | -45/-50 | 5400.0 | 78,548 | 76.7 | L0.33/A674/C123 |

### `C2_vad__energy_e-55.jsonl`
  - `argv` = c2_vad.py energy_fsm
  - `ctx` = {"CmaFree": 126628, "CmaTotal": 262144, "MemAvailable": 689992, "SwapTotal": 0, "load1": 0.33}
  - `enter` = -55.0
  - `exit` = -60.0
  - `frame_ms` = 30.0
  - `hop_ms` = 10.0
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | rtf | p50_ms | p95_ms | max_ms | first_speech_s | n_intervals | speech_s | thresh_dbfs | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:07:06Z | speech16k | scan | 6690 | 66.922 | 723.0 | 92.562 | 0.102 | 0.103 | 0.31 | 0.0 | 1 | 66.86 | -55/-60 | 6130.0 | 78,548 | 76.7 | L0.33/A673/C123 |
| 2026-10-09T22:07:09Z | long16k | scan | 28946 | 289.489 | 3143.7 | 92.085 | 0.102 | 0.104 | 0.361 | 0.0 | 5 | 287.64 | -55/-60 | 9330.0 | 86,360 | 84.3 | L0.38/A672/C123 |
| 2026-10-09T22:07:10Z | quiet64db | scan | 5998 | 60.0 | 646.6 | 92.8 | 0.102 | 0.103 | 0.303 |  | 0 | 0 | -55/-60 | 9980.0 | 86,360 | 84.3 | L0.38/A672/C123 |

### `C2_vad__energy_e-62.jsonl`
  - `argv` = c2_vad.py energy_fsm
  - `ctx` = {"CmaFree": 126628, "CmaTotal": 262144, "MemAvailable": 689068, "SwapTotal": 0, "load1": 0.38}
  - `enter` = -62.0
  - `exit` = -66.0
  - `frame_ms` = 30.0
  - `hop_ms` = 10.0
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | rtf | p50_ms | p95_ms | max_ms | first_speech_s | n_intervals | speech_s | thresh_dbfs | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:07:11Z | speech16k | scan | 6690 | 66.922 | 724.2 | 92.412 | 0.102 | 0.106 | 0.304 | 0.0 | 1 | 66.87 | -62/-66 | 10720.0 | 86,360 | 84.3 | L0.38/A672/C123 |
| 2026-10-09T22:07:14Z | long16k | scan | 28946 | 289.489 | 3136.9 | 92.286 | 0.102 | 0.103 | 3.004 | 0.0 | 3 | 288.52 | -62/-66 | 13900.0 | 86,360 | 84.3 | L0.43/A672/C121 |
| 2026-10-09T22:07:15Z | quiet64db | scan | 5998 | 60.0 | 647.5 | 92.67 | 0.102 | 0.103 | 0.304 |  | 0 | 0 | -62/-66 | 14560.0 | 86,360 | 84.3 | L0.43/A657/C121 |

### `C2_vad__silero.jsonl`
  - `argv` = c2_vad.py silero
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 701208, "SwapTotal": 0, "load1": 0.48}
  - `model` = /root/compbench/models/silero_vad.onnx
  - `model_present` = true
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": null, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": null, "ORT_NUM_THREADS": null}

**case 行（3 条）**

| ts | case | mode | n | work_s | gen_ms | rtf | p50_ms | p95_ms | max_ms | first_speech_s | n_intervals | speech_s | thresh_dbfs | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:19:36Z | speech16k | scan | 2091 | 66.922 | 6103.0 | 10.965 | 2.222 | 4.926 | 5.744 | 31.814 | 3 | 32.562 |  | 7010.0 | 96,392 | 94.1 | L0.52/A668/C85 |
| 2026-10-09T22:20:01Z | long16k | scan | 9046 | 289.489 | 25246.3 | 11.467 | 2.588 | 3.375 | 4.47 | 0.134 | 29 | 277.298 |  | 32260.0 | 125,288 | 122.4 | L0.69/A642/C85 |
| 2026-10-09T22:20:05Z | quiet64db | scan | 1875 | 60.0 | 4180.5 | 14.352 | 2.16 | 2.458 | 3.423 |  | 0 | 0 |  | 36450.0 | 125,288 | 122.4 | L0.71/A647/C85 |

### `C2_vad__webrtc.jsonl`
  - `aggressiveness` = 2
  - `argv` = c2_vad.py webrtc
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 696872, "SwapTotal": 0, "load1": 0.51}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**error 行（1 条）**

| ts | case | mode | error | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|
| 2026-10-09T22:03:14Z | import | load | ModuleNotFoundError: No module named 'webrtcvad' | 820.0 | 40,448 | 39.5 | L0.51/A680/C127 |


## 九、C3 图像编码（预览侧）

两档分辨率各 4 帧、每帧重复 `reps` 次。`psnr_vs_src` 是旧的按首帧配对（已作废，见第十六节），`psnr_frames` 是逐帧自配对的正本；`mean_bytes` 是位流字节。

原始文件＝板上 `/root/compbench/results/`，逐字节副本 `S:\apps\llm\agentwork\comp-bench\pull\results\`（脚本与夹具位置见台账 `#125`～`#139`）。每张表**列出该文件里出现过的全部字段**，不做列筛选。

### `C3_jpeg__cv2_jpeg_q85.jsonl`
  - `argv` = c3_jpeg.py all
  - `ctx` = {"CmaFree": 66920, "CmaTotal": 262144, "MemAvailable": 682008, "SwapTotal": 0, "load1": 0.67}
  - `cv2` = 4.6.0
  - `pillow` = 9.3.0
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | psnr_vs_src | psnr_frames | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:16:55Z | cv2_jpeg_q85 | 1920x1080 | 20 | 5 | 4 | 236.777 | 255.506 | 281.767 | 345057 | 4.17 | 40.34 | 4 | 7470.0 | 198,980 | 194.3 | L0.7/A646/C61 |
| 2026-10-09T22:16:56Z | cv2_jpeg_q85 | 640x352 | 20 | 5 | 4 | 34.285 | 37.761 | 38.904 | 66014 | 30.5 | 32.73 | 4 | 8290.0 | 198,980 | 194.3 | L0.7/A654/C65 |

### `C3_jpeg__cv2_jpeg_q95.jsonl`
  - `argv` = c3_jpeg.py all
  - `ctx` = {"CmaFree": 66920, "CmaTotal": 262144, "MemAvailable": 669908, "SwapTotal": 0, "load1": 0.7}
  - `cv2` = 4.6.0
  - `pillow` = 9.3.0
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | psnr_vs_src | psnr_frames | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:17:02Z | cv2_jpeg_q95 | 1920x1080 | 20 | 5 | 4 | 243.386 | 250.445 | 250.558 | 599880 | 4.13 | 43.65 | 4 | 14600.0 | 200,836 | 196.1 | L0.72/A644/C65 |
| 2026-10-09T22:17:03Z | cv2_jpeg_q95 | 640x352 | 20 | 5 | 4 | 28.707 | 29.28 | 29.341 | 116496 | 35.32 | 35.84 | 4 | 15330.0 | 200,836 | 196.1 | L0.75/A652/C65 |

### `C3_jpeg__cv2_png.jsonl`
  - `argv` = c3_jpeg.py cv2_png
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 681260, "SwapTotal": 0, "load1": 0.71}
  - `cv2` = 4.6.0
  - `pillow` = 9.3.0
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": null, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": null, "ORT_NUM_THREADS": null}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | psnr_vs_src | psnr_frames | lossless_frames | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:20:18Z | cv2_png | 1920x1080 | 20 | 5 | 4 | 541.293 | 556.762 | 560.316 | 2934627 | 1.93 |  | 0 | 4 | 12830.0 | 221,928 | 216.7 | L0.78/A622/C85 |
| 2026-10-09T22:20:20Z | cv2_png | 640x352 | 20 | 5 | 4 | 65.057 | 66.071 | 66.947 | 445436 | 15.7 |  | 0 | 4 | 14280.0 | 221,928 | 216.7 | L0.78/A651/C85 |

### `C3_jpeg__cv2_webp.jsonl`
  - `argv` = c3_jpeg.py all
  - `ctx` = {"CmaFree": 66920, "CmaTotal": 262144, "MemAvailable": 663944, "SwapTotal": 0, "load1": 0.93}
  - `cv2` = 4.6.0
  - `pillow` = 9.3.0
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | psnr_vs_src | psnr_frames | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:18:36Z | cv2_webp | 1920x1080 | 20 | 5 | 4 | 1925.07 | 2093.031 | 2094.442 | 239031 | 0.53 | 39.31 | 4 | 73560.0 | 215,492 | 210.4 | L1.02/A644/C65 |
| 2026-10-09T22:18:41Z | cv2_webp | 640x352 | 20 | 5 | 4 | 256.38 | 272.957 | 273.076 | 59149 | 4.09 | 34.27 | 4 | 78610.0 | 215,492 | 210.4 | L1.01/A650/C65 |

### `C3_jpeg__ffmpeg_mjpeg_q85.jsonl`
  - `argv` = c3_jpeg.py all
  - `ctx` = {"CmaFree": 66920, "CmaTotal": 262144, "MemAvailable": 669260, "SwapTotal": 0, "load1": 0.75}
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | note | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:17:34Z | ffmpeg_mjpeg_q85 | 1920x1080 | 20 | 5 | 4 | 1390.68 | 1437.121 | 1485.633 | 302760 | 0.72 | includes process start | 21110.0 | 200,836 | 196.1 | L0.9/A647/C65 |
| 2026-10-09T22:17:44Z | ffmpeg_mjpeg_q85 | 640x352 | 20 | 5 | 4 | 491.072 | 498.087 | 506.138 | 69570 | 2.05 | includes process start | 21440.0 | 200,836 | 196.1 | L0.92/A648/C65 |

### `C3_jpeg__pil_jpeg_q85.jsonl`
  - `argv` = c3_jpeg.py all
  - `ctx` = {"CmaFree": 66920, "CmaTotal": 262144, "MemAvailable": 668120, "SwapTotal": 0, "load1": 0.75}
  - `cv2` = 4.6.0
  - `pillow` = 9.3.0
  - `python` = 3.8.10
  - `reps` = 5
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | reps | frames | p50_ms | p95_ms | max_ms | mean_bytes | fps_equiv | psnr_vs_src | psnr_frames | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:17:06Z | pil_jpeg_q85 | 1920x1080 | 20 | 5 | 4 | 91.746 | 96.442 | 228.544 | 345057 | 10.24 | 40.34 | 4 | 18870.0 | 200,836 | 196.1 | L0.75/A645/C65 |
| 2026-10-09T22:17:07Z | pil_jpeg_q85 | 640x352 | 20 | 5 | 4 | 11.66 | 12.139 | 12.143 | 66014 | 87.93 | 32.73 | 4 | 19380.0 | 200,836 | 196.1 | L0.75/A653/C65 |


## 十、C4 文本前置与意图

语料 29 行（ASR 参考句 24＋TTS 句 5，共 3,665 字）。`sents_per_s`＝每秒处理句数；`load` 行是词典载入前后的 VmHWM／VmRSS 差。

原始文件＝板上 `/root/compbench/results/`，逐字节副本 `S:\apps\llm\agentwork\comp-bench\pull\results\`（脚本与夹具位置见台账 `#125`～`#139`）。每张表**列出该文件里出现过的全部字段**，不做列筛选。

### `C4_nlp__intent_rules.jsonl`
  - `argv` = c4_nlp.py
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 642560, "SwapTotal": 0, "load1": 1.03}
  - `n_intents` = 5
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（1 条）**

| ts | case | mode | n | gen_ms | p50_ms | p95_ms | max_ms | sents_per_s | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:05:09Z | match_only | single_pass | 29 | 1.5 | 0.042 | 0.058 | 0.092 | 19840.79 | 7570.0 | 96,964 | 94.7 | L1.03/A627/C127 |

### `C4_nlp__jieba_exact.jsonl`
  - `argv` = c4_nlp.py jieba_exact
  - `corpus` = 29
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 723040, "SwapTotal": 0, "load1": 0.6}
  - `jieba_cache_exists` = false
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": null, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": null, "ORT_NUM_THREADS": null}

**case 行（3 条）**

| ts | case | mode | n | gen_ms | p50_ms | p95_ms | max_ms | sents_per_s | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:20:39Z | jieba_cut | cold | 29 | 5469.3 | 2.414 | 9.901 | 5342.584 | 5.3 | 5740.0 | 85,400 | 83.4 | L0.72/A633/C85 |
| 2026-10-09T22:20:40Z | jieba_cut | warm | 29 | 125.2 | 2.279 | 9.335 | 9.75 | 231.71 | 5870.0 | 85,720 | 83.7 | L0.72/A633/C85 |
| 2026-10-09T22:20:40Z | jieba_cut_noHMM | warm | 29 | 111.6 | 1.698 | 8.26 | 8.47 | 259.82 | 5980.0 | 85,720 | 83.7 | L0.72/A633/C85 |

**load 行（1 条）**

| ts | case | mode | vmhwm_before_kb | vmrss_before_kb | vmhwm_after_kb | vmrss_after_kb | dict_growth_kb | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:20:40Z | jieba_dict | cold | 16708 | 16708 | 85400 | 85400 | 68692 | 5740.0 | 85,400 | 83.4 | L0.72/A633/C85 |

### `C4_nlp__jieba_search.jsonl`
  - `argv` = c4_nlp.py jieba_search
  - `ctx` = {"CmaFree": 87400, "CmaTotal": 262144, "MemAvailable": 724520, "SwapTotal": 0, "load1": 0.72}
  - `jieba_cache_exists` = false
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": null, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": null, "ORT_NUM_THREADS": null}

**case 行（2 条）**

| ts | case | mode | n | gen_ms | p50_ms | p95_ms | max_ms | sents_per_s | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:20:46Z | cut_for_search | cold | 29 | 5485.6 | 2.522 | 10.363 | 5353.466 | 5.29 | 5750.0 | 85,360 | 83.4 | L0.74/A633/C85 |
| 2026-10-09T22:20:46Z | cut_for_search | warm | 29 | 129.5 | 2.345 | 9.463 | 10.051 | 224.02 | 5880.0 | 85,360 | 83.4 | L0.74/A633/C85 |

**load 行（1 条）**

| ts | case | mode | vmhwm_before_kb | vmrss_before_kb | vmhwm_after_kb | vmrss_after_kb | dict_growth_kb | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:20:46Z | jieba_dict | cold | 16560 | 16560 | 85360 | 85360 | 68800 | 5750.0 | 85,360 | 83.4 | L0.74/A633/C85 |

### `C4_nlp__regex_only.jsonl`
  - `argv` = c4_nlp.py
  - `corpus` = 29
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 719956, "SwapTotal": 0, "load1": 1.04}
  - `python` = 3.8.10
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（2 条）**

| ts | case | mode | n | gen_ms | p50_ms | p95_ms | max_ms | sents_per_s | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:05:02Z | clean | single_pass | 29 | 10.1 | 0.189 | 0.649 | 0.679 | 2884.77 | 150.0 | 9,384 | 9.2 | L1.04/A703/C127 |
| 2026-10-09T22:05:02Z | clean+intent | single_pass | 29 | 10.9 | 0.225 | 0.685 | 0.703 | 2657.85 | 160.0 | 9,384 | 9.2 | L1.04/A703/C127 |


## 十一、C5 ASR 备选的运行时可达性

`meta` 档用 onnxruntime 直读三张 funasr int8 导出的元数据键；另外三档真去建 sherpa recognizer，三档都失败。

原始文件＝板上 `/root/compbench/results/`，逐字节副本 `S:\apps\llm\agentwork\comp-bench\pull\results\`（脚本与夹具位置见台账 `#125`～`#139`）。每张表**列出该文件里出现过的全部字段**，不做列筛选。

### `C5_asr_runtime__onnx_metadata.jsonl`
  - `argv` = c5_asr_runtime.py meta
  - `ctx` = {"CmaFree": 130724, "CmaTotal": 262144, "MemAvailable": 711796, "SwapTotal": 0, "load1": 0.43}
  - `python` = 3.8.10
  - `threads` = 4
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}

**case 行（3 条）**

| ts | case | mode | load_ms | n_meta_keys | meta | cpu_ms | vmhwm_kb | VmHWM MB | ctx |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-09T22:07:51Z | SenseVoiceSmall | meta | 35089.3 | 1 | {"onnx.infer": "onnxruntime.quant"} | 26260.0 | 561,108 | 548.0 | L0.89/A188/C127 |
| 2026-10-09T22:08:18Z | Paraformer-large | meta | 26009.2 | 1 | {"onnx.infer": "onnxruntime.quant"} | 43080.0 | 561,192 | 548.0 | L1.16/A190/C0 |
| 2026-10-09T22:08:35Z | Paraformer-online | meta | 17564.8 | 1 | {"onnx.infer": "onnxruntime.quant"} | 54440.0 | 561,192 | 548.0 | L1.33/A314/C4 |

### `C5_asr_runtime__paraformer.jsonl`
  - `argv` = c5_asr_runtime.py paraformer
  - `ctx` = {"CmaFree": 130232, "CmaTotal": 262144, "MemAvailable": 714972, "SwapTotal": 0, "load1": 1.01}
  - `extra` = {}
  - `kind` = paraformer
  - `model` = /root/funasr/models/Paraformer-large/model_quant.onnx
  - `model_bytes` = 238380216
  - `python` = 3.8.10
  - `threads` = 4
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}
  - `tokens` = /root/compbench/fix/paraformer_tokens.txt

### `C5_asr_runtime__sensevoice_default.jsonl`
  - `argv` = c5_asr_runtime.py sensevoice_default
  - `ctx` = {"CmaFree": 105136, "CmaTotal": 262144, "MemAvailable": 715920, "SwapTotal": 0, "load1": 1.17}
  - `extra` = {"language": "", "use_itn": false}
  - `kind` = sense_voice
  - `model` = /root/funasr/models/SenseVoiceSmall/model_quant.onnx
  - `model_bytes` = 241216270
  - `python` = 3.8.10
  - `threads` = 4
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}
  - `tokens` = /root/funasr/models/SenseVoiceSmall/tokens.txt

### `C5_asr_runtime__sensevoice_zh_itn.jsonl`
  - `argv` = c5_asr_runtime.py sensevoice_zh_itn
  - `ctx` = {"CmaFree": 129752, "CmaTotal": 262144, "MemAvailable": 715548, "SwapTotal": 0, "load1": 1.05}
  - `extra` = {"language": "zh", "use_itn": true}
  - `kind` = sense_voice
  - `model` = /root/funasr/models/SenseVoiceSmall/model_quant.onnx
  - `model_bytes` = 241216270
  - `python` = 3.8.10
  - `threads` = 4
  - `threads_env` = {"MKL_NUM_THREADS": "4", "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4", "ORT_NUM_THREADS": "4"}
  - `tokens` = /root/funasr/models/SenseVoiceSmall/tokens.txt

## 十二、VAD 分段明细（`pull/out/`，可逐段核对）

每份 json＝`{alt, case, segments:[[起, 止] 秒], extra}`。素材 `speech16k`＝`a067.wav`（66.9 s 讲话）、`long16k`＝`d290.wav`（289.5 s）、`quiet64db`＝合成底噪（RMS −64.5 dBFS，种子 20261010）。**这是"能量 FSM 与 silero 分段不一致"这条的原始依据**——两个族在同一份字节上给出的段边界都在这里，谁对谁错要带人工标注停顿的语料才能仲裁，本轮不裁。

| 文件 | 档 | 素材 | 段数 | 段边界（s） |
|---|---|---|---|---|
| `C2__energy_e-45__long16k.json` | energy_e-45 | long16k | 13 | [[0.0, 241.72], [242.12, 243.15], [243.48, 244.27], [244.86, 245.5], [245.91, 251.44], [251.78, 260.41], [260.88, 266.98], [267.32, 269.41], [269.79, 272.51], [273.0, 275.14], [275.69, 281.02], [281.34, 284.03], [284.53, 289.14]] |
| `C2__energy_e-45__quiet64db.json` | energy_e-45 | quiet64db | 0 | [] |
| `C2__energy_e-45__speech16k.json` | energy_e-45 | speech16k | 1 | [[0.0, 66.84]] |
| `C2__energy_e-55__long16k.json` | energy_e-55 | long16k | 5 | [[0.0, 260.48], [260.86, 272.58], [272.96, 275.21], [275.66, 284.05], [284.52, 289.32]] |
| `C2__energy_e-55__quiet64db.json` | energy_e-55 | quiet64db | 0 | [] |
| `C2__energy_e-55__speech16k.json` | energy_e-55 | speech16k | 1 | [[0.0, 66.86]] |
| `C2__energy_e-62__long16k.json` | energy_e-62 | long16k | 3 | [[0.0, 272.58], [272.96, 284.05], [284.47, 289.32]] |
| `C2__energy_e-62__quiet64db.json` | energy_e-62 | quiet64db | 0 | [] |
| `C2__energy_e-62__speech16k.json` | energy_e-62 | speech16k | 1 | [[0.0, 66.87]] |
| `C2__silero__long16k.json` | silero | long16k | 29 | [[0.134, 21.308], [21.606, 42.524], [43.11, 53.972], [54.502, 58.132], [58.726, 63.988], [64.518, 69.428], [70.182, 73.652], [74.118, 94.172], [94.534, 96.532], [98.022, 112.884], [113.35, 130.132], [130.406, 133.012], [133.446, 140.82], [141.094, 147.668], [147.974, 149.972], [150.246, 158.868], [159.174, 168.852], [169.318, 193.084], [193.158, 195.988], [196.39, 217.788], [217.862, 237.948], [23… |
| `C2__silero__quiet64db.json` | silero | quiet64db | 0 | [] |
| `C2__silero__speech16k.json` | silero | speech16k | 3 | [[31.814, 34.164], [35.334, 60.028], [60.102, 65.62]] |

**`C4__tokens__jieba_exact.txt`**（jieba 精确模式对语料第 1 行的切分结果，正本留档）：

```
怎么 /   / 怎 /   / 么
```

## 十三、每档起跑与收尾时的板况（全部 `load` 记账件）

表里两套件都在：组件基准 22 支（`comp-bench/pull/logs/*.load`；其中 Wave A2 那 5 支是单行 `before=… after=… avail=…`，`avail` 单位是 **kB**，其余是 `free -m` 整行）＋TTS 主跑 6 支／补测 9 支（`tts-bench/pull/logs/*.load`、`logs2/*.load`）。`free -m` 第二行六列全录。**`rc` 是 shell 看到的 wait status，`137`＝被 SIGKILL，也就是 OOM 击杀**。§十 结论 17 已经证明**`avail` 在这颗板上没有预测力**（含 `CmaFree` 与当时的 buff/cache），列在这里是留痕、不是门禁依据。共存前 5 大 RSS 只有组件基准那批采了 `ps`（TTS 那批的 harness 没记）——另一条会话那颗 `python3`（pid 5407）全程驻着 36～38 MB。

| 出处 | 作业 | 相 | 时刻 | load 1／5／15 | run／tot | Mem total | used | free | shared | buff\/cache | avail MB | rc | 共存前 5（pid:RSS kB:comm） | tries |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 组件基准 | `a2_c1_soxr` | 单行 |  | 前 0.22／后 0.20（1 min） |  |  |  |  |  |  | 709 |  |  |  |
| 组件基准 | `a2_c1_swr` | 单行 |  | 前 0.16／后 0.22（1 min） |  |  |  |  |  |  | 711 |  |  |  |
| 组件基准 | `a2_c2_silero` | 单行 |  | 前 0.20／后 0.56（1 min） |  |  |  |  |  |  | 710 |  |  |  |
| 组件基准 | `a2_c3_all` | 单行 |  | 前 0.56／后 1.01（1 min） |  |  |  |  |  |  | 710 |  |  |  |
| 组件基准 | `a2_cv2backend` | 单行 |  | 前 0.09／后 0.16（1 min） |  |  |  |  |  |  | 711 |  |  |  |
| 组件基准 | `c1_alsa_plughw` | before | 2026-10-09T22:02:56Z | 0.31／0.20／0.24 | 1／100 | 993 | 220 | 297 | 0 | 476 | 704 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_alsa_plughw` | after | 2026-10-09T22:02:57Z | 0.37／0.21／0.24 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c1_ffmpeg_soxr` | before | 2026-10-09T22:01:19Z | 0.23／0.14／0.22 | 1／100 | 993 | 219 | 338 | 0 | 435 | 706 |  | 5407:37836:python3／103:17536:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_ffmpeg_soxr` | after | 2026-10-09T22:01:42Z | 0.29／0.16／0.23 | 1／99 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c1_ffmpeg_swr` | before | 2026-10-09T22:00:57Z | 0.32／0.15／0.23 | 2／102 | 993 | 219 | 334 | 0 | 439 | 706 |  | 5407:37836:python3／103:17536:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_ffmpeg_swr` | after | 2026-10-09T22:01:19Z | 0.23／0.14／0.22 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c1_numpy_fir` | before | 2026-10-09T22:02:10Z | 0.31／0.18／0.23 | 1／101 | 993 | 219 | 298 | 0 | 475 | 705 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_numpy_fir` | after | 2026-10-09T22:02:35Z | 0.34／0.19／0.24 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c1_numpy_linear` | before | 2026-10-09T22:02:35Z | 0.34／0.19／0.24 | 1／100 | 993 | 219 | 297 | 0 | 475 | 705 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_numpy_linear` | after | 2026-10-09T22:02:56Z | 0.31／0.20／0.24 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c1_scipy_poly` | before | 2026-10-09T22:01:42Z | 0.29／0.16／0.23 | 1／99 | 993 | 219 | 338 | 0 | 435 | 706 |  | 5407:37836:python3／103:17536:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c1_scipy_poly` | after | 2026-10-09T22:02:10Z | 0.31／0.18／0.23 | 1／101 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c2_energy_fsm` | before | 2026-10-09T22:07:00Z | 0.27／0.41／0.34 | 1／99 | 993 | 217 | 271 | 0 | 504 | 707 |  | 5407:37836:python3／103:19668:systemd-journal／149:7608:unattended-upgr／192:7368:systemd-resolve／1:5712:systemd |  |
| 组件基准 | `c2_energy_fsm` | after | 2026-10-09T22:07:15Z | 0.43／0.44／0.35 | 2／99 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c2_silero` | before | 2026-10-09T22:03:11Z | 0.46／0.24／0.25 | 1／100 | 993 | 220 | 297 | 0 | 476 | 705 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c2_silero` | after | 2026-10-09T22:03:13Z | 0.51／0.25／0.25 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c2_webrtc` | before | 2026-10-09T22:03:13Z | 0.51／0.25／0.25 | 1／100 | 993 | 219 | 289 | 0 | 484 | 705 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c2_webrtc` | after | 2026-10-09T22:03:14Z | 0.51／0.25／0.25 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c3_encode` | before | 2026-10-09T22:03:14Z | 0.51／0.25／0.25 | 1／100 | 993 | 219 | 289 | 0 | 484 | 705 |  | 5407:37836:python3／103:17732:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c3_encode` | after | 2026-10-09T22:05:02Z | 1.04／0.51／0.35 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c4_nlp` | before | 2026-10-09T22:05:02Z | 1.04／0.51／0.35 | 1／100 | 993 | 219 | 285 | 0 | 489 | 705 |  | 5407:37836:python3／103:17840:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c4_nlp` | after | 2026-10-09T22:05:10Z | 1.03／0.52／0.36 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c5_meta` | before | 2026-10-09T22:07:15Z | 0.43／0.44／0.35 | 1／99 | 993 | 217 | 271 | 0 | 504 | 707 |  | 5407:37836:python3／103:19712:systemd-journal／149:7608:unattended-upgr／192:7368:systemd-resolve／1:5712:systemd |  |
| 组件基准 | `c5_meta` | after | 2026-10-09T22:08:36Z | 1.33／0.74／0.46 | 1／101 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c5_paraformer` | before | 2026-10-09T22:10:34Z | 1.01／0.86／0.54 | 1／99 | 993 | 217 | 500 | 0 | 275 | 711 |  | 5407:37824:python3／103:9440:systemd-journal／149:7608:unattended-upgr／192:6776:systemd-resolve／1:4756:systemd |  |
| 组件基准 | `c5_paraformer` | after | 2026-10-09T22:11:02Z | 1.25／0.93／0.58 | 1／100 |  |  |  |  |  |  | 255 |  |  |
| 组件基准 | `c5_sensevoice_cjk` | before | 2026-10-09T22:05:10Z | 1.03／0.52／0.36 | 1／100 | 993 | 219 | 270 | 0 | 503 | 705 |  | 5407:37836:python3／103:17840:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c5_sensevoice_cjk` | after | 2026-10-09T22:05:10Z | 1.03／0.52／0.36 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c5_sensevoice_default` | before | 2026-10-09T22:08:51Z | 1.18／0.73／0.46 | 1／104 | 993 | 226 | 455 | 0 | 311 | 703 |  | 5407:37824:python3／11980:15692:python3／103:12776:systemd-journal／11967:7692:sshd／149:7608:unattended-upgr |  |
| 组件基准 | `c5_sensevoice_default` | after | 2026-10-09T22:09:31Z | 1.35／0.84／0.51 | 1／100 |  |  |  |  |  |  | 255 |  |  |
| 组件基准 | `c5_sensevoice_subword` | before | 2026-10-09T22:05:11Z | 1.03／0.52／0.36 | 1／100 | 993 | 219 | 270 | 0 | 503 | 705 |  | 5407:37836:python3／103:17840:systemd-journal／10885:7700:sshd／149:7608:unattended-upgr／192:7368:systemd-resolve |  |
| 组件基准 | `c5_sensevoice_subword` | after | 2026-10-09T22:05:11Z | 1.03／0.52／0.36 | 1／100 |  |  |  |  |  |  | 0 |  |  |
| 组件基准 | `c5_sensevoice_zh_itn` | before | 2026-10-09T22:09:46Z | 1.05／0.80／0.51 | 1／100 | 993 | 217 | 569 | 0 | 206 | 711 |  | 5407:37824:python3／103:12500:systemd-journal／149:7608:unattended-upgr／192:6788:systemd-resolve／1:4920:systemd |  |
| 组件基准 | `c5_sensevoice_zh_itn` | after | 2026-10-09T22:10:19Z | 1.30／0.90／0.55 | 1／101 |  |  |  |  |  |  | 255 |  |  |
| TTS 主跑 | `espeakng` | before | 19:42:26 | 1.18／4.27／4.19 | 1／103 | 993 | 213 | 360 | 0 | 419 | 709 |  |  |  |
| TTS 主跑 | `espeakng` | after | 19:42:34 | 1.17／4.22／4.18 | 1／103 | 993 | 213 | 321 | 0 | 459 | 709 | 0 |  |  |
| TTS 主跑 | `espeakng_b20` | before | 19:42:35 | 1.17／4.22／4.18 | 1／103 | 993 | 213 | 320 | 0 | 459 | 708 |  |  |  |
| TTS 主跑 | `espeakng_b20` | after | 19:42:42 | 1.14／4.11／4.14 | 1／103 | 993 | 213 | 297 | 0 | 482 | 708 | 0 |  |  |
| TTS 主跑 | `kokoro_af_alloy` | before | 20:13:37 | 0.92／3.69／3.96 | 1／96 | 993 | 179 | 765 | 0 | 49 | 756 |  |  |  |
| TTS 主跑 | `kokoro_af_alloy` | after | 20:16:31 | 3.76／3.74／3.93 | 1／99 | 993 | 178 | 793 | 0 | 21 | 771 | 137 |  |  |
| TTS 主跑 | `kokoro_zf_xiaobei` | before | 19:54:58 | 1.06／3.02／3.64 | 1／97 | 993 | 179 | 736 | 0 | 78 | 750 |  |  |  |
| TTS 主跑 | `kokoro_zf_xiaobei` | after | 20:11:36 | 7.02／5.52／4.51 | 1／104 | 993 | 182 | 787 | 0 | 24 | 766 | 137 |  |  |
| TTS 主跑 | `piper_en_US-lessac-medium` | before | 19:47:09 | 1.24／3.17／3.78 | 1／95 | 993 | 179 | 503 | 0 | 311 | 726 |  |  |  |
| TTS 主跑 | `piper_en_US-lessac-medium` | after | 19:53:37 | 4.03／3.95／3.97 | 1／95 | 993 | 177 | 753 | 0 | 62 | 751 | 0 |  |  |
| TTS 主跑 | `piper_zh_CN-huayan-medium` | before | 19:42:42 | 1.14／4.11／4.14 | 1／103 | 993 | 214 | 296 | 0 | 482 | 707 |  |  |  |
| TTS 主跑 | `piper_zh_CN-huayan-medium` | after | 19:45:49 | 4.17／4.07／4.11 | 1／97 | 993 | 179 | 540 | 0 | 273 | 726 | 0 |  |  |
| TTS 补测 | `af_long` | before | 20:54:32 | 1.00／1.73／2.26 | 1／100 | 993 | 218 | 716 | 0 | 58 | 713 |  |  | 1 |
| TTS 补测 | `af_long` | after | 20:56:44 | 4.48／2.78／2.58 | 1／102 | 993 | 216 | 753 | 0 | 24 | 732 | 137 |  | 1 |
| TTS 补测 | `af_longw` | before | 21:07:47 | 1.06／2.49／2.52 | 1／100 | 993 | 219 | 732 | 0 | 42 | 720 |  |  | 1 |
| TTS 补测 | `af_mix2` | before | 21:12:21 | 1.17／2.04／2.35 | 1／101 | 993 | 218 | 711 | 0 | 63 | 711 |  |  | 1 |
| TTS 补测 | `af_mix2` | after | 21:13:47 | 3.24／2.43／2.46 | 1／102 | 993 | 217 | 747 | 0 | 29 | 728 | 137 |  | 1 |
| TTS 补测 | `af_num` | before | 21:17:05 | 1.16／1.91／2.24 | 1／101 | 993 | 218 | 731 | 0 | 43 | 720 |  |  | 1 |
| TTS 补测 | `af_num` | after | 21:18:30 | 3.06／2.27／2.34 | 1／100 | 993 | 214 | 755 | 0 | 23 | 734 | 137 |  | 1 |
| TTS 补测 | `af_zh` | before | 21:14:49 | 1.19／1.99／2.30 | 1／101 | 993 | 217 | 739 | 0 | 36 | 724 |  |  | 1 |
| TTS 补测 | `af_zh` | after | 21:16:03 | 2.88／2.29／2.38 | 1／101 | 993 | 214 | 755 | 0 | 23 | 734 | 137 |  | 1 |
| TTS 补测 | `zf_long` | before | 20:48:48 | 1.17／1.58／2.39 | 1／100 | 993 | 217 | 681 | 0 | 94 | 710 |  |  | 1 |
| TTS 补测 | `zf_long` | after | 20:50:22 | 3.55／2.26／2.55 | 1／102 | 993 | 215 | 756 | 0 | 22 | 734 | 137 |  | 1 |
| TTS 补测 | `zf_longs` | before | 21:00:59 | 0.86／1.90／2.26 | 1／100 | 993 | 218 | 732 | 0 | 42 | 720 |  |  | 1 |
| TTS 补测 | `zf_longs` | after | 21:06:26 | 4.04／3.26／2.75 | 1／101 | 993 | 215 | 754 | 0 | 23 | 732 | 137 |  | 1 |
| TTS 补测 | `zf_longw` | before | 21:19:31 | 1.12／1.86／2.19 | 1／99 | 993 | 216 | 745 | 0 | 31 | 728 |  |  | 2 |
| TTS 补测 | `zf_num` | before | 21:10:02 | 1.07／2.20／2.42 | 1／100 | 993 | 218 | 704 | 0 | 71 | 711 |  |  | 2 |
| TTS 补测 | `zf_num` | after | 21:11:20 | 2.90／2.47／2.50 | 1／101 | 993 | 215 | 755 | 0 | 23 | 733 | 137 |  | 2 |

## 十四、十二次 OOM 击杀的逐次读数（内核 `dmesg` 解析）

正本＝板上 `/tmp/dmesg_tts.txt` 的回传副本 `S:\work\WCIS\workenv\tts-bench\dmesg_board.txt`（md5 `3ae1f161e13a25aaf33555012c53d480`，台账 `#124`）。这张表是"峰值 RSS 为什么不能当门禁"的证据：**十一条有 zone 行的死亡，`非 CMA free − min` 全落在 −1832～+136 kB 的窄带里**，也就是全都死在同一个内核水位（`min`＝22,528 kB）。**`/tmp` 是 tmpfs，本机这份副本是唯一长期件**。

| dmesg 时刻(s) | pid | job | 它自己 anon-rss | 其余进程 rss 合计 | 整板 anon 合计 | DMA32 free | 其中 free_cma | 非 CMA free | min | 非 CMA−min | 同刻 cache |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 697.434919 | 592 | zf 主跑 | 622,408 | 173,140 | ? | 该 block 的 zone 行已滚出 dmesg | | | | | |
| 2835.619936 | 2219 | zf 主跑 | 796,460 | 29,676 | 825,496 | 28,212 | 6,876 | 21,336 | 22528 | -1192 | 904 |
| 3130.938400 | 3029 | af 主跑 | 676,432 | 25,480 | 702,476 | 149,980 | 127,756 | 22,224 | 22528 | -304 | 2,532 |
| 5162.241999 | 7525 | zf_long | 662,876 | 62,068 | 726,416 | 127,348 | 104,968 | 22,380 | 22528 | -148 | 256 |
| 5330.727248 | 7747 | zf_num #1 | 609,812 | 89,828 | 700,752 | 151,696 | 130,644 | 21,052 | 22528 | -1476 | 2,100 |
| 5543.708347 | 8028 | af_long | 733,028 | 69,216 | 803,576 | 48,756 | 26,532 | 22,224 | 22528 | -304 | 928 |
| 5718.002263 | 8376 | zf_longw | 655,180 | 65,404 | 721,172 | 131,664 | 109,808 | 21,856 | 22528 | -672 | 992 |
| 6125.888776 | 8504 | zf_longs | 620,176 | 82,652 | 704,296 | 149,804 | 128,020 | 21,784 | 22528 | -744 | 396 |
| 6420.625375 | 8907 | af_mix2 | 612,076 | 88,072 | 701,144 | 151,448 | 130,752 | 20,696 | 22528 | -1832 | 968 |
| 6566.671511 | 9123 | af_zh | 608,296 | 88,972 | 698,348 | 153,008 | 130,740 | 22,268 | 22528 | -260 | 1,148 |
| 6703.543596 | 9244 | zf_num #2 | 652,856 | 62,156 | 715,948 | 136,236 | 113,572 | 22,664 | 22528 | +136 | 1,188 |
| 6850.173825 | 9374 | af_num | 611,564 | 87,760 | 699,984 | 152,592 | 130,752 | 21,840 | 22528 | -688 | 24 |

**时间锚点（本次启动，A 级）**：板钟 22:35:50 UTC 时 `/proc/uptime`＝11,490.52 s ⇒ 开机＝19:24:20 UTC；十二次击杀的时刻依次＝697.4／2,835.6／3,130.9／5,162.2／5,330.7／5,543.7／5,718.0／6,125.9／6,420.6／6,566.7／6,703.5／6,850.2 s，**最后一次折成北京时＝10-10 05:18:30，早于组件基准那四波（05:55～06:20）**。`dmesg | grep -c 'Out of memory'` 到复核时仍是 **12**，组件基准零新增击杀。

## 十五、本轮没测／测不了的（逐条写清是"没做"还是"做不了"）

| 项 | 状态 | 原因 |
|---|---|---|
| 重采样输出质量（混叠） | **按她裁定不测**（10-10） | 只留成本数；`cpu_per_audio_ms` 那列就是本轮的交付 |
| 识别质量"对不对" | **不测**（10-15 她关掉的） | 跨机器／跨 ORT 构建的逐字一致性留 C 级未验 |
| MeloTTS（第四支引擎） | **按她裁定不跑**（10-09："不跑 melotts 了，删掉"） | 板上从未安装，所以第四、五、六节里没有它的行——这是撤项，不是漏测 |
| 能量 FSM 与 silero 的分段谁更对 | **判不了** | 没有带人工标注停顿的语料；分歧的成因已量化到素材本身（`speech16k` 的 p1＝−28.3 dBFS、只有 0.1 % 帧低于 −45） |
| webrtcvad 一族 | **没跑成** | 板上两个解释器都没有 `webrtcvad`（`C2_vad__webrtc.jsonl` 只有一行 `error`），本轮不装包 ⇒ 空白 |
| sherpa-onnx 换 Zipformer-CTC／CAM++／YuNet 等 Wave B 备选 | **没跑** | 要下载；板上 `github.com` 直连超时、release CDN 只能走 7897 代理；且需要她点头 |
| Qwen2-0.5B 的 CPU 路线（板上 llama.cpp） | **没跑** | 要在板上编译，撞她的硬指令（禁止在开发板上编译） |
| NPU 极限吞吐 | **不测**（她 10-10 判） | "测 npu 极限会不会卡死了" ⇒ 撤 |
| Kokoro 主跑缺的 34 格 | **没补** | fp32 ONNX 在 993 MB 无 swap 上必死（第十四节），要补只能加 swap／zram 或换 int8 权重，两件都要她点头 |
| `cv2` 与 `Pillow` 差 2.5 倍的机制 | **标 C** | 只拿到构建信息（`JPEG: libjpeg-turbo (ver 2.1.2-62)`），没做后端级消融 |
| Pillow 后端探针 | **探针本身失败** | `a3_pil_backend` 报 `module 'PIL.features' has no attribute 'supported'`（9.3.0 的正确入口是 `features.check`）⇒ 这一档只有版本号 `PIL 9.3.0` |
| `jieba_cache_exists` 那一行 | **不可信** | 探针猜的路径 `~/.cache/jieba.__main__.cache`，恒 False 只说明猜错，不证明没缓存 |
| 板子的热与"响声" | **软件侧判不了** | `/sys/class/thermal` 空、无 hwmon、无 `temp*_input` ⇒ 内核零温度读数；`/proc/asound/cards`＝`no soundcards` ⇒ 没有放音通路；`dmesg` ring buffer 只剩本次启动 697 s 之后（前面 12 个 OOM block 挤掉了）；板上没有 `/var/log/kern.log` 与 `syslog` ⇒ "开机以来没有 X"这类负断言一律不成立 |

## 十六、公开更正（写错的地方当场改，不删旧文）

| # | 先前写成 | 现在改判 | 依据 |
|---|---|---|---|
| 1 | `C4_nlp__regex_only` 的 9.2 MB "采样点存疑" | **是真读数**：`c4_nlp.py` 不 import numpy，`compcommon.py` 的 numpy 在两个函数体里（77／89 行）⇒ 该档整进程就没加载 numpy | 代码直读＋与 `alsa_plughw` 46.0 MB 相减得 numpy 固定成本 36.9 MB |
| 2 | C1 `whole` 模式行标"48k→16k" | **读数作废并重测**：命令少了 `-ar 16000`，实际算的是 48 kHz 拷贝 | Wave A2 重跑，`C1_src__ffmpeg_swr/soxr.jsonl` 里 `out_samples` 与 16 kHz 对齐 |
| 3 | C3 `psnr_vs_src`（1080p 报过 9.3 dB） | **配对方式错**（拿末帧比首帧）⇒ 正本改 `psnr_frames`（逐帧自配对），旧列仍在表里但只作对照 | `c3_jpeg.py` 改为 `last[fi] = buf` 逐帧配对 |
| 4 | C2 silero 首跑用 `accept_waveform(rate, list)` 且以为有 `vad.start()` | **两处都不存在**：真签名是单参数 float32／512 样本，段起始取 `vad.front.start`（单位是样本号） | 板上 introspection＋Wave A2 重测 |
| 5 | Wave A3 的 jieba 两档 | **解释器用错**（系统 python3 没 jieba）且 `Recorder` 以 `"w"` 打开 ⇒ 两个 jsonl 被截空；正本由 Wave A4 在 venv 下重跑恢复 | `logs/wave_a3.log` 的 `ModuleNotFoundError`＋A4 末行 `WAVE_A4_DONE` |
| 6 | "`dmesg` 里开机以来没有任何 USB／热事件" | **只对 ring buffer 现存范围成立**（起点 697.4 s），前面已滚出 | `dmesg \| head -3` 首行时间戳＝697.43 |
| 7 | A2／A3／A4 驱动里 `rc=$?` | **取的是管道末端的 `tail`，不是 python 的** ⇒ 判成败要看有没有 `type=case` 行 | `run_wave_a2.sh:38` 的结构 |
| 8 | "`/usr/bin/time -v` 退出码 0＝跑成功" | **不成立**：被信号杀掉的子进程它照写 `Exit status: 0`，必须与 `.load` 里的 `rc=` 并排看 | 台账 §十 结论 8 |
| 9 | 第五节把 `pull/merged/kokoro_af_alloy.time` 当成 **af_alloy 主跑**的整进程读数（MaxRSS 735,756 kB／墙钟 2:11.49） | **归属错**：那个文件的 `Command being timed` 写的是 `bench_kokoro.py out results2/af_long`，与 `results2/af_long/time.txt` **md5 相同**（`98df330a…`）⇒ 它是补测 af_long 的副本；af_alloy 主跑正本＝`pull/results/kokoro_af_alloy.time`，MaxRSS **678,368 kB＝662.5 MB**、User 582.67 s、墙钟 2:53.55、CPU 336 % | 本次生成时逐件读 `Command being timed` 行；正本与 `dmesg` 的 `pid 3029 anon-rss:676432kB` 对齐（差 1,936 kB＝匿名页与整进程口径差），补测与 `pid 8028 anon-rss:733,028kB` 对齐 |
| 10 | 全库多页写「**Piper 慢于实时 25–47%**」（含 [[MatchaVocosNPU]] §11.4、[[实时伪tts]] 两处、`repos/lang/tts` 四个 README） | **方向读反了**：本页 `rtf` 列 ＝ **音频毫秒 ÷ 生成毫秒**（**>1＝快于实时**，与基准大盘页 `syn_rtf` 同口径），不是标准 RTF。重算后 `piper_zh_CN-huayan` **常驻标准 RTF 0.648–0.810 ＝ 快于实时 23–54%**，`piper_en_US-lessac` 0.902–1.011 临界 | 原始行验算 `2.4729 s ÷ 1686.2 ms ＝ 1.4666` 与该行 `rtf 1.4665` 吻合；常驻样本 piper_zh 5 条／piper_en 2 条；复算脚本 `workenv/rtf_recheck.py`。**Piper 的真实死因是「放不下」（峰值 391.5／754.8 MB，12 次 OOM），不是「跑不动」** |
| 11 | `piper xiao_ya`「**RTF 0.865–0.966，快于实时 67–83%**」 | **那是同句 5 次取 min（最好情况）。单次典型值 0.987／1.079／1.030／1.000（短→长），** **默认配置典型 RTF ≈ 1.10＝慢于实时约 10%** | 5 次重复测（`workenv/rss/piper_len.py`）；**引用时必须标明 `min-of-N` 还是单次** |
| 12 | 「中文齿音/擦音集中在 8–11 kHz，**16 kHz 会砍掉**」（我据此判 16 kHz 不可用） | **损失被我夸大了**：实测本模型四句输出 **8 kHz 以上能量只占 0.21%／1.33%／2.29%／0.21%** ⇒ 16 kHz 丢得很少；`huayan-x_low` 的降质主因是 **x_low 架构档 ＋ int8 量化**，不是 16 kHz。（转 48 kHz 仍不补信息，其价值只是免掉播放端重采样） | `workenv/rss/band_analysis.py` 对桌面四个 22.05 kHz wav 做 FFT 分频段能量统计 |
| 13 | `D-1793606494` 标题与结论 1「**换小模型是压内存最有效的一招**」 | **不成立**：RSS 与模型体积基本无关——HiFi-GAN 3.75 MB→**72.5 MB（19×）**、piper 17.7 MB→**155.8 MB（9×）**、matcha 75.6 MB→**149.6 MB（2×）**。**决定峰值的是最长中间张量，不是参数量。** 真正有效的是**分段合成**（191.1→**152.6 MB**，−20%，2 段后到地板 152.5）。⇒ 该条收窄为"换小模型能**避开 OOM**"，不是"最有效的压内存手段" | §二十～§廿二 三组同口径实测（`workenv/rss/{rss,levers}.py`） |

## 十七、相关页面

[[板端我方代码与产物台账]]（§十＝TTS 文件与结论 1～17；§十二＝组件基准 `#125`～`#139`；§九／§十三＝ASR 链路）· [[板卡镜像实测取证]] · [[板端内存上限与心跳日志]] · [[组件选型与复用边界]] · [[交叉编译主机路由SOP]] · [[os]]

**复跑方法**（全部只在板端，本机不跑链路）：`cd /root/compbench; setsid nohup bash run_wave_a.sh > logs/wave_a.log 2>&1 < /dev/null &`（`_DONE` 跳过已完成档）；单档＝`/root/funasr/venv/bin/python c1_src.py scipy_poly` 这种形式。TTS 侧＝`/root/ttsbench/run_all.sh` 与 `kokoro_resume.sh`（台账 `#88`～`#106`）。

**测试集纪律（她定的规矩，D-69，2026-10-20）**：凡记入本页的 TTS CPU 读数，测试集一律用 `/root/ttsbench/bench/common.py` 的共享用例（`mixed1`／`mixed2`／`zh_only`／`num_only`／`long`，文本与切句规则定死在脚本里、全引擎同源），指标口径同 ttsbench（`first_ms`／`gen_ms`／`rtf`＝audio÷gen，**>1 是快于实时**；峰值内存走 `/usr/bin/time -v`＋VmHWM）。某引擎做不到某项（如 CLI 面没有流式首包 ⇒ `first_ms` 测不了）就**显式声明缺哪项**，不许换一套私有文本顶替。

## 十八、ekho 板端 CPU 基准：48 对 44.1 kHz 包（D-69，2026-10-20）

> 本节晚于十七追加。来历＝[[状态源与决策记录#D-69 · 板端 48 对 44.1 kHz 包 CPU 实测（停泵→测→复原）＋ aarch64 kit 代跑重建交付|D-69]]：她的授权「把任务停掉，你测完再重启」，加上她明禁板端编译（「不要在113上编译啊，性能不行的」）⇒ 二进制走校机交叉编译。板上仓库 `/root/ekho-bench/` 测毕保留。

**前置（先说死）**：

- 二进制＝`d043e07` 校机（MSYS2＋Arm GNU 10.3）交叉编译，L1 三闸全绿（AArch64 门禁、DT_NEEDED 闭包对出厂 rootfs 全部供货、glibc 2.31／GLIBCXX 3.4.26 天花板；libsndfile／espeak／sonic 静态吸库、DT_NEEDED 不见）。三件 md5：`ekho` `4f317146…`／`ekho-stream` `ad2ee1c4…`／`ekho-server` `be303c14…`，与开发机侧逐一相符。
- 数据两包同在 root ext4：`p48`（`pinyin.voice` 136,359,454 B md5 `28c46088…`／`pinyin.index` `d21c3d27…`）与 `p44`（125,287,518 B md5 `e9632c7f…`／`pinyin.index` `ef4addc3…`）；小件（zh.dict、jyutping 16k、toneaway 等）放 `common/`，两包目下相对符号链接 `../common/*`。字母两包各一份真件（`alphabet/*.wav`，48 kHz 源）。
- SDI 单元 `wcis-sdi-refclk-fix-20261020.service` 测试期间停止；load1 全程 0.01→0.40，护栏 <1.0；暖页缓存＝两包各 `cat` 递 `/dev/null` 一轮才开跑；每格 3 次 `/usr/bin/time -f "%U %S %e %M"` 取中位；输出一律 `/root/ekho-bench/out/`。板钟 UTC。
- **`ESPEAK_DATA_PATH` 必给**：编进二进制的默认路径是校机构建树（`D:/yzd/...`），不给就 `Error processing file ... phontab` exit 1；板上用 kit 裁剪版 `share/espeak-ng-data`（en 独苗＋公共件，1.17 MB）。纯中文文本＋单字母路径不触 espeak 合成。
- 校验：同一格 3 次输出逐位一致（md5 全同）；与 x86（WSL，同 `d043e07` 源码全量重建）的三档字母输出**逐字节一致**（见下）。

**读数（7 段 reg-44k 文本，中位 usr+sys 秒）**：

| 文本 | 48k包→48k/2ch | 44.1k包→48k/2ch（运行期上采样） | 44.1k包→44.1k/1ch | Δ（p44o48−p48o48） |
|---|---|---|---|---|
| 01-plain（3.01 s） | 1.44 | 1.47 | 1.26 | +2.1% |
| 02-numbers（7.19 s） | 3.31 | 3.45 | 2.86 | +4.2% |
| 03-polyphone（5.67 s） | 2.77 | 2.72 | 2.37 | −1.8% |
| 04-sishi（8.06 s） | 4.27 | 4.12 | 3.60 | −3.5% |
| 05-erhua（5.68 s） | 2.70 | 2.64 | 2.35 | −2.2% |
| 06-prose（12.37 s） | 5.94 | 5.78 | 5.05 | −2.7% |
| 07-long-news（18.32 s） | 8.92 | 8.92 | 7.65 | 0.0% |
| **合计 7 段** | **29.35** | **29.10** | **25.14** | **−0.9%** |
| 字母 K（0.110 s） | 0.24 | 0.25 | 0.25 | — |

- 括号里的时长＝渲染时长（每格 3 次 md5 相同，时长逐位一致；44.1k 上采样档的时长比 48k 档长 ~0.2%，来自包率换算）。CPU/墙钟比全程 ≤1.000（单核无干扰）。
- **结论一：同输出格式（48k/2ch）下 44.1k 包不省 CPU**——合计 −0.9% 在噪声内，逐段 −3.5%～+4.2% 双向摆动、无方向性。省 14% 的那一档（p44o44）改了输出格式（44.1k/1ch），不能与基线比。
- **结论二：RTF≈0.49**（07 段 8.92 s CPU / 18.32 s 音频，单核 out-of-box；06 段同口径 0.480）。
- **结论三：RSS 与包大小无关**——字母单字格 ~15.3–15.5 MB，长文格峰 19.4–19.8 MB（p48o48 07 段 20,288 kB），三配置几乎同值（按索引逐音节付费，不是按包整载）。
- **字母 K 跨架构逐字节一致**：三档输出 md5 板与 x86 全同——`160a6603…`（p48o48）／`b8a46140…`（p44o48）／`387b61af…`（p44o44）⇒ 包率（48↔44.1）路径在 aarch64 上逐位正确。

**过程事故三笔（全部自记，板子全程无伤）**：

1. 停板第一支脚本没走 ssh、在本机 WSL 跑了全文（nproc 撞出 16、MemAvailable 15 GB 本机特征才露馅）⇒ 板零接触、虚惊。教训固化：上板动作一律 scp→板跑（`runcb.sh` 包装）。
2. `systemctl is-active X | grep -q active` 子串坑：`inactive` 也命中成"active"（假阳性；journal 显示那个 photo 单元本 boot 零记录、NRestarts 0）⇒ 检查改全词 `[ "$PHS" = "active" ]`。
3. **主基准 p44 两格字母读数作废重测**：造的 `p44/alphabet/*.wav` 符号链接写 `../p48/alphabet/$c.wav`，但链接从 `p44/alphabet/` 层解析、`../p48`＝`p44/p48`（少一层）⇒ 字母加载失败、输出 44 B 空 WAV、rc=0 静默。x86 同源复测一切正常顺带排除了引擎嫌疑；回查板目录（`find`）发现 `p48/alphabet` 26 件俱在、p44 相件件悬空 ⇒ 换真件重跑 6 跑（泵复原后进行，load1 0.40 起步仍在护栏内，中位与停泵期读数一致）后 0.25／0.25，与 48k 无差、与 x86 逐字节同。**「44.1k 包＋字母＝空输出」这一先前判断作废**——不是引擎缺陷，是我打的测试数据错。

**方法对齐（与既有 ttsbench 的关系，诚实声明）**：本节与十七节所系的 ttsbench 线**不是同一套**——① 测试集：本节用 7 段 reg-44k 自选文本＋单字母 K；页面既有 TTS 基准（kokoro／piper，台账 `#88`–`#106`）用 `bench/common.py` 共享用例 `mixed1`／`mixed2`／`zh_only`／`num_only`／`long`。② 指标：本节＝中位 usr+sys CPU＋输出 md5；ttsbench＝`first_ms`／`gen_ms`／`rtf`＝audio÷gen（**>1 是快于实时**，与本节 RTF＝CPU÷audio 极性相反）＋VmHWM。③ 次数：本节统一 3 次；ttsbench 约定 long=2、其余=3。**⇒ 本节读数与 §五～§十五 的 kokoro／piper 行不可横比**（输入文本与指标口径都不同；本节 RTF 0.49 换成页面口径≈audio÷gen **2.05**，只当近似看）。**她定的规矩（D-69）**：以后往本页记 TTS CPU 一律用共享用例集（见十七节"测试集纪律"）——同集对齐补测见下。

**同集对齐补测（她点头后跑，10-20 晚）**：文本零转录（板上 python 直读 `common.py`），42 行零失败（long=2、其余=3，页面惯例），原始行 `/root/ekho-bench/results-align.jsonl` md5 `c85a9339…`（本机正本 `S:\work\WCIS\workenv\ekho-bench-1020\`）。条件与声明：泵 DOWN（见 D-69 未决⑤）但补测纯用户态不受累；`first_ms` 缺测（CLI 无流式首包，留到 server 流路径）；`gen_ms` **含** CLI 冷起＋包索引载入（kokoro/piper 行模型载入在 case 外）——long 档稀释到 ~1%、mixed1 档或占 ~10%，横比看 long 档最稳；load1 0.91–1.23 每行留痕。中位数（gen ms／rtf=audio÷gen／HWM kB）：

| 用例 | p48o48 | p44o48 | p44o44 |
|---|---|---|---|
| mixed1 | 1447 / 2.070 / 16336 | 1419 / 2.112 / 16340 | 1300 / 2.302 / 16352 |
| mixed2 | 2030 / 2.209 / 16816 | 1973 / 2.271 / 16800 | 1823 / 2.460 / 16712 |
| zh_only | 2334 / 2.072 / 17136 | 2408 / 2.090 / 17168 | 2101 / 2.397 / 16984 |
| num_only | 3194 / 2.122 / 17796 | 3164 / 2.140 / 17552 | 2774 / 2.441 / 17580 |
| long | 15578 / 2.285 / 21412 | 15600 / 2.283 / 21196 | 13343 / 2.668 / 21232 |

- **读法**：rtf>1＝快于实时 ⇒ ekho 同文本同口径比实时快 **2.1–2.7×**；44.1k/1ch 又比 48k 输出快 8–17%（与十八 CPU 结论同向）。
- **与 kokoro 的同例对照**（只到量级）：页面既有 kokoro 行 `zh_only split rtf 0.1221`（gen≈35 s 对 4.3 s 音频，**慢于实时 ~8×**）——同一行文本同口径，**拼接式对神经式 ~17× 的算力差**，正是当初选拼接的算力论据；两轮的板面负载状态不同，不进精度比较。

**未核（C，别当结论）**：① 多核间调度与超线程差异没量（读数全是单核 CPU 时间）；② sonic 变速档（如 1.2×）没测，本轮全部 1.0×；③ 页缺/换页统计没采（只有 MaxRSS 采样）。

**证据行**：原始 CSV `/root/ekho-bench/results.txt`（73 主基准＋4 勘正注释＋6 勘正数据行＝83 行；本机正本 `S:\work\WCIS\workenv\ekho-bench-1020\results.txt` md5 `ec6b124bd83f38ca5ea6ecd120396f6c`）。板上目录 `/root/ekho-bench/`（p48／p44／common／alphabet／texts／scripts／bin／out）测毕保留。

**总账（D-69 决定 2）**：48 kHz 包的 CPU 侧无悬念——同输出格式不比 44.1k 慢，RTF≈0.5 有余量；与 D-64「48 更好」的听感判例合流，44.1k 包的 CPU 疑问就此结案。FunASR 场景 CPU 侧无障碍。

## 十九、piper 17.8 MB 小模型：换小模型能**避开 OOM**（不是"最有效的压内存手段"——见 §二十一与更正 13）

> 起因：她问「有量级比这个还小的、但没到 ekho 那种级别的中文 TTS 吗」，随后追问
> 「纯 CPU 部署时**非冷启动、常驻**的 RTF 有木有测过」。两问一起查，得出一条**推翻旧结论**的结果。

### 19.1 板上现成的小件（不是新下载的）

| 模型 | ONNX | 位置 | 备注 |
|---|---:|---|---|
| `zh_CN-xiao_ya-medium.onnx` | **17.8 MB** | `/mnt/data/models/tts-piper/` | **本节测的就是它** |
| `vits-aishell3.int8.onnx` | 39.9 MB | `/mnt/data/models/tts/vits-zh-aishell3/` | 未测 |
| `piper_zh_CN-huayan-medium` | 63.2 MB | 曾用于 icraft 横评 | 峰值 391.5 MB，OOM |
| `vits-aishell3.onnx` | 116 MB | 同上 | 未测 |

`xiao_ya` 之所以只有 17.8 MB：**词表仅 85 个符号**（pinyin **音素**级：声母＋韵母，不是音节级），
配套 `lexicon.txt` 68,012 条，格式 `汉字 声母 韵母 声调 _`。

### 19.2 实测读数（板上 4×A53 @1 GHz、993 MB RAM、onnxruntime 4 线程、arena 默认开）

| 句 | 音素数 | 生成 ms | 音频 s | **标准 RTF** | **峰值 VmHWM** |
|---|---:|---:|---:|---:|---:|
| 01_问候 | 22 | 954 | 1.59 | **0.600** | **154.7 MB** |
| 02_天气 | 26 | 997 | 1.67 | **0.596** | **160.4 MB** |
| 03_数字 | 26 | 1058 | 1.94 | **0.546** | **163.2 MB** |
| 04_长句 | 34 | 1276 | 2.24 | **0.570** | **167.6 MB** |

**⇒ 快于实时 67–83%，峰值只占板子 993 MB 的 17%。**

**与 huayan 的对照（这是本节最值钱的一条）**：

| | huayan 63.2 MB | **xiao_ya 17.8 MB** |
|---|---:|---:|
| 峰值 RSS | **391.5 MB** ⇒ 12 次 OOM | **154.7–167.6 MB** ⇒ 安全 |
| 标准 RTF | 0.648–0.810 | 0.546–0.600 |
| 判读 | 算得动，**放不下** | **算得动、也放得下** |

### 19.3 压内存的四个手段（全部实测，含一条反直觉的）

| 手段 | 实测效果 | 结论 |
|---|---|---|
| **① 换小模型** | 63.2 → 17.8 MB，峰值 **391 → 155 MB** | ✅ **最有效，一步解决** |
| **② 控制单次句长** | 42 音素 136 MB／62 音素 190 MB／142 音素 **364 MB** | ✅ 内存**随句长线性增长**；长文本必须分段（≤60 音素可压到 ≤190 MB） |
| **③ 保持 `enable_cpu_mem_arena=True`（默认）** | 关掉反而**固定占 436 MB**（不管多长） | ⚠️ **反直觉：别关 arena**。开着是按需增长，关掉是一次性向 OS 要一大块 |
| **④ 必须 4 线程** | 4 线程 RTF 0.579／单线程 **1.583（慢于实时 58%）** | ✅ 单线程慢 2.7 倍 |
| ⑤ 进程常驻 | `load_ms=30548`（30 s） | ✅ 只该加载一次，别每句起进程 |

**逐配置原始读数**（4 线程 + arena on/off、1 线程）：

```text
线程4 arena=on  音素 42  生成 1419ms  音频 2.45s  RTF 0.579  峰值 135.9MB
线程4 arena=on  音素 62  生成 1834ms  音频 3.20s  RTF 0.572  峰值 190.3MB
线程4 arena=on  音素142  生成 3829ms  音频 6.91s  RTF 0.554  峰值 363.6MB
线程4 arena=off 音素 42  生成 1414ms  RTF 0.577  峰值 436.4MB（固定）
线程4 arena=off 音素142  生成 3833ms  RTF 0.555  峰值 436.4MB（固定）
线程1 arena=on  音素 42  生成 3879ms  RTF 1.583  峰值 436.4MB
线程1 arena=on  音素 62  生成 5145ms  RTF 1.606  峰值 436.4MB
```

### 19.4 与 ekho 的对照（同文本 4 句，已交付试听）

| | piper xiao_ya 17.8 MB | ekho |
|---|---|---|
| 峰值内存 | 154.7–167.6 MB | **~20 MB** |
| 标准 RTF | 0.546–0.600 | ~0.49 |
| 采样率 | 22050 Hz 单声道 | 48000 Hz 双声道 |
| 音色 | 神经网络，音质受小模型限制 | 录音包决定，机械感较重 |

交付：`C:\Users\takomi\Desktop\klar-matcha-samples\piper小模型vsEkho\`（4 句 × 2 引擎 + `_说明.txt`）。

### 19.5 ⚠️ ekho 的两个环境变量（本轮踩过）

`ekho` 直接跑会报 `Fail to open file /zh_list` —— 它去找**根目录**的 `zh_list`，但实际在 `p48/` 里。
必须两个都设：

```bash
export EKHO_DATA_PATH=/root/ekho-bench/p48
export ESPEAK_DATA_PATH=/root/ekho-bench/espeak-ng-data
/root/ekho-bench/bin/ekho -o out.wav '文本'
```

（`--help` 里**没有** `-d` 参数，别猜；`EKHO_DATA_PATH` 指 `/root/ekho-bench` 会去找 `.../zh_list` 也失败，
指 `.../common` 会报 `Fail to find voice data directory: .../common/pinyin`。）

### 19.6 未测／未决

| # | 项 | 状态 |
|---|---|---|
| 1 | **音质** | 数值只证明"跑得动、内存够"；**好不好听要她听**（已交付 4 句待判） |
| 2 | int8 量化能否再压 | 未测；可能再降 30–50%，但要验音质 |
| 3 | 17.8 MB 是**音素**级模型 | 前端要把汉字→声母/韵母/声调，需要自带 `lexicon.txt`；换别的 piper 件要确认词表口径 |
| 4 | 长文本分段策略 | 只验到"≤60 音素峰值 ≤190 MB"，拼接处的韵律未验 |

### 19.7 复现件

| 文件 | 作用 |
|---|---|
| `workenv/rtf_recheck.py` | 从原始行重算两种 RTF 口径（本次更正的证据） |
| `workenv/piper_small/probe.py` | 读模型 io 与 phoneme_id_map |
| `workenv/piper_small/bench3.py` | 内存/RTF 矩阵（线程 × arena × 句长） |
| `workenv/piper_small/gen_both2.py` | 4 句 piper 合成（用自带 lexicon 映射音素） |
| `workenv/piper_small/gen_ekho.sh` | 4 句 ekho 合成（含两个环境变量） |

## 二十、RSS 总表（**峰值，不是静态体积**）——2026-11-02 同口径重测

> 她在 2026-11-02 明确要求：「**我要的不是他的静态占用体积，我要的是 rss**」。
> 此前全库没有一张跨方案的总表，模型体积和 RSS 经常混着说。本节一次补齐。
>
> **口径**：`VmHWM`（进程级峰值，含解释器与已 import 的库）；**一个方案一个独立进程**；
> `intra_op_num_threads=4`、`execution_mode=SEQUENTIAL`、`arena` 默认开、`graph_opt=ALL`；
> 输入统一为 `01_问候`（42 音素，约 2.5 s 音频），除注明者外。
> **基线**＝只 `import onnxruntime`、不加载任何模型 ＝ **43.3 MB**（这一块是纯运行时开销，跟模型无关）。

| 方案 | 模型体积 MB | **峰值 RSS MB** | 扣基线增量 | 备注 |
|---|---:|---:|---:|---|
| **baseline**（无模型） | — | **43.3** | 0 | python＋ORT |
| HiFi-GAN v2 单独 | 3.75 | **72.5** | +29 | 加载 0.46 s |
| vocos 单独（fp32） | 53.9 | **115.8** | +72 | 加载 1.7 s |
| matcha 单独 | 75.6 | **149.6** | +106 | 加载 **27.8 s** |
| **matcha ＋ HiFi-GAN** | 79.4 | **155.3** | +112 | 两段式最短链 |
| **piper xiao_ya int8（短句）** | 17.7 | **155.8** | +113 | 加载 31.6 s |
| **matcha ＋ vocos** | 129.5 | **218.3** | +175 | 两段式 |
| **piper xiao_ya int8（长句 66 音素）** | 17.7 | **213.4** | +170 | 随句长涨 |
| piper zh_CN-huayan（fp32，旧测 10-09） | 60.3 | 391.5 | +348 | 12 次 OOM |
| kokoro_af_alloy（旧测） | — | 645.9 | +603 | |
| piper en_US-lessac（fp32，旧测） | 60.3 | 754.8 | +711 | |
| ekho（旧测） | 2.6 | 15.3–19.8 | ≈0 | 48k 包 29.5 |
| espeak-ng（旧测） | ~2 | 31.9 | ≈0 | 共振峰 |

**三条必须记住的**：

1. **RSS 与模型体积基本无关**：HiFi-GAN 3.75 MB→72.5 MB（**19×**）、piper 17.7→155.8（9×）、
   matcha 75.6→149.6（**2×**）。**决定峰值的是最长中间张量，不是参数量。**
   所以"压模型体积"对 RSS 帮助有限（见更正 13）。
2. **piper 峰值随输出长度线性涨**：42 音素 155.8 → 66 音素 213.4 → **202 音素 443.8**（§廿三）。
3. **同进程连跑多句会额外累积约 47 MB**（arena 不还）：4 句连续跑 5 轮曾读到 **260.6 MB**，
   而单句独立进程只到 213.4。**报 RSS 必须说清单句还是常驻多句。**

## 二十一、压运行时峰值：四个手段的实测矩阵

> 她的问题：「怎么压运行时峰值（分段合成、控制句长）」。**逐条实测，不靠推断。**
> 输入统一为 `04_长句`（66 音素，约 4.2 s 音频），一配置一进程。

| 手段 | 峰值 RSS MB | 生成 ms | 判读 |
|---|---:|---:|---|
| **基准**（4 线程／arena 开） | **191.1** | 4337 | — |
| 减到 1 线程 | 190.8 | 6743 | ❌ **内存不变，慢 55%** |
| 关 arena | 224.3 | 4459 | ❌ **反而多 33 MB** |
| **切 2 段** | **152.6** | 4971 | ✅ **−20%**，时间 +15% |
| 切 4 段 | 152.5 | 6716 | ❌ **到地板，时间 +55%** |
| 4 句顺序（同进程） | 221.5 | — | arena 累积 |
| 4 句 ＋ `malloc_trim(0)` | 215.4 | — | ❌ **只还 RSS，不降 peak** |

**地板 152.5 MB 的构成**：模型加载完 **109.1 MB**（17.7 MB 模型 → 109 MB，**6.2×**）＋ 每段一套激活 **43.4 MB**。
**切 2 段之后边际收益归零，再切只会更慢、音频更长。**

### 21.1 分段到底能把 202 音素的长文本压到多少（这条是**安全**问题，不是优化）

| 模式 | 段数 | **首包 ms** | 音频 s | 总生成 ms | **峰值 RSS MB** |
|---|---:|---:|---:|---:|---:|
| **整段不分** | 1 | **9818** | 11.91 | 9818 | **443.8** ⚠️ |
| **按句切**（`。！？`） | 4 | **2212** | 13.17 | 11250 | **214.7** |
| **按逗号切**（`，。！？`） | 7 | **952** | 14.85 | 12715 | **184.6** |

- **首包 9818 → 2212 → 952 ms（−77% / −90%）**
- **峰值 443.8 → 214.7 → 184.6 MB（−52% / −58%）**
- **代价**：总时间 +15% / +30%；**音频变长 +11% / +25%**（每段自带 BOS/EOS 与边界静音）

> ⚠️ **不分段在长文本上会撞 OOM**：443.8 MB ＋ 相机服务常占约 460 MB ＝ 904 MB／993 MB。
> **⇒ 长文本分段不是优化项，是必要条件。**
>
> **推荐**：**按句切**（214.7 MB／首包 2.2 s，平衡最好）；只在"极快出声"场景用按逗号切。

## 二十二、提速：运行时开关就够了（**整链 −17.3%**）

> 她的问题：「有没有办法提升速度」。四句全量、每组独立进程、每句 3 次取中位。

| 配置 | 合计中位 ms | **整链 RTF** | 判读 |
|---|---:|---:|---|
| **4 线程 ＋ 自旋（原默认）** | 13689 | **1.030** | 慢于实时 3% |
| **4 线程 ＋ 关自旋** | **11325** | **0.862** | ✅ **最优，快于实时 16%** |
| 3 线程 ＋ 自旋 | 11506 | 0.859 | 近似 |
| 3 线程 ＋ 关自旋 | 11513 | 0.871 | 近似 |

**⇒ 只加两个运行时开关，中位耗时 13689 → 11325 ms，−17.3%；RTF 1.030 → 0.862。**

### 22.1 关自旋是什么

ONNX Runtime 的工作线程**没有任务时不立刻休眠**，而是空转（spin）一段时间反复查有没有新工作，
好处是有活时零唤醒延迟。代价是**空转期仍占着 CPU 周期**。

这块板有相机服务占着一个核 ⇒ 空转抢 CPU、相机抢回去 ⇒ **互相抢**。
改成被动等待反而快：

```python
so.add_session_config_entry("session.intra_op.allow_spinning", "0")
os.environ["OMP_WAIT_POLICY"] = "passive"
```

> **这是"共存优化"不是普适最优**：空载独占时自旋通常更快。换负载条件要重测。

### 22.2 线程数扫描（66 音素长句，5 次，开自旋）

| 线程 | 1 | 2 | 3 | **4** | 5 | 6 | 8 |
|---|---:|---:|---:|---:|---:|---:|---:|
| RTF(med) | 1.705 | 0.961 | **0.872** | 1.096 | 1.291 | 1.303 | 1.435 |

**>4 线程单调恶化**（超订反而慢）。**关自旋后 4 线程仍最优**——早先"3 线程最优"只在开自旋时成立。

### 22.3 两个负面结果（省得别人再试）

| 尝试 | 结果 |
|---|---|
| `execution_mode = ORT_PARALLEL` | **更慢 19%**（RTF 1.096→1.299） |
| 减线程省内存 | **内存不变**（190.8 vs 191.1），只慢 |
| CPU 调频（governor） | **板子没有 cpufreq 接口**（`/sys/devices/system/cpu/cpu0/cpufreq/` 不存在），路封死 |

### 22.4 还没做的三条（按预期收益排序）

| 手段 | 预期 | 前置 |
|---|---|---|
| 静态 int8（QDQ）替动态量化 | **<15%**（见 §22.5） | 需 fp32 原件 60.3 MB |
| 16 kHz 模型（`huayan-x_low`） | 解码器采样点 −28% | 需下载 + 量化 + 验音质 |
| C++ 直连 ORT / sherpa-onnx | 省掉 43 MB 基线的大部分开销 | 工作量最大 |

### 22.5 静态量化为什么判断"不值得"（**在花 60 MB 下载之前查完的**）

直接解析这颗 ONNX 的 initializer dtype（793 个，`workenv/rss/onnx_dt.py`／`onnx_by_layer.py`）：

| 部分 | dtype | 大小 |
|---|---|---:|
| `onnx::Conv_*_quantized`（Conv 权重） | **uint8＝已是 int8** | 14.23 MB |
| **`dec.ups`（上采样 ConvTranspose）** | **float32** | **2.56 MB** |
| biases 等小张量 | float32 | 0.21 MB |

**⇒ 1396 个 Conv 的权重早就量化了**（名字尾缀 `_quantized` 即证据）。静态量化只剩两处可咬：
110 个 `DynamicQuantizeLinear` 的现算 scale、以及 2.56 MB 的 `dec.ups`。
**相对 1396 个 Conv 的算力，上限 <15%，不值得为它重新下载 fp32 原件。**

## 二十三、16 kHz 到底丢多少（更正我的夸大）

对桌面四个 22.05 kHz 成品 wav 做 FFT 分频段能量统计：

| 句 | 8 kHz 以上能量占比 |
|---|---:|
| 01_问候 | **0.22%** |
| 02_天气 | **1.33%** |
| 03_数字 | **2.29%** |
| 04_长句 | **0.21%** |

**⇒ 16 kHz 的损失远小于我先前断言**。`huayan-x_low` 的降质主因是 **x_low 最小架构档 ＋ int8 量化**。

**另两条口径**：
- **转 48 kHz 不补任何信息**（Nyquist 决定），其唯一价值是**免掉播放端重采样**
  （板子唯一播放设备只收 48000）。
- 本项目在 **ekho 上已经吃过一次"降采样磨齿音"的亏**（8 kHz 包被否、升 48 kHz）——
  方向没错，但**幅度要说准**。

