# io待测

> **本页回答什么问题**：校机（`ssh school-guest`，远程用户 `win11-hv1\yizhidi`）上**实际存在的视觉模型，逐个数地回答"它吃什么、吐什么"**——输入张量的名字／形状／数据类型／通道顺序／是否必须归一化，输出的形状语义、门限与尺寸的真实边界，以及**封装层（OpenCV／MediaPipe）与裸 ONNX 之间那层谁看不见的转换**。全部结论来自 2026-10-12 在校机上的实跑探针，不来自文档。
> **本页不回答什么**：不上板、不涉及 ZG330 NPU 档的算子支持（同一批模型搬到 NPU 时后处理归定制算子，见 [[NPU调用链]]）；不做精度/速度评测（吞吐见 [[组件选型与复用边界]]）；不覆盖训练与导出过程。
> **判据等级**：A＝本轮校机实测原文（探针脚本与 JSON 路径见第九节，可复跑）；B＝由 A 级数据推出来、但机制未取证；C＝文档／二手口径，本机未验；D＝只知道存在，内容未看。**每条断言后面都标了级**，未归因的机制一律写成"机制未取证"，不当结论用。
> **校机路径（2026-10-18 变更）**：页内 `D:/yzd/qwen3/…` 是当时实测原文、未改；那个根现在在 `D:/yzd/WCIS/MOD/qwen3/…`，换址后 `venv\Scripts\python.exe` 实测仍 import torch 2.14.1＋cpu／transformers 5.19.0，见 [[Qwen3按厂商Qwen2配方迁移]] 开头。

## 一、清点结果：这台机上到底有几个视觉模型（A）

两条**互相独立**的枚举（Python `os.walk` 与 MSYS2 `find`），门槛下调后完全对齐：

| 枚举方式 | 门槛 | 命中文件数 |
|---|---|---|
| Python `os.walk` 扫 `D:/yzd` | ≥300 KB | 61 |
| MSYS2 `find /d/yzd` 扫同一根 | ≥16 KB | 68 |
| 同一根，16 KB–300 KB 这一档 | 补扫 | 7 |

**61 ＋ 7 ＝ 68，两侧逐文件一致**（A）。这轮把门槛从 300 KB 降到 16 KB 是有原因的：唯一的视觉件 `yunet.onnx` 只有 **232,589 B**，旧门槛会把它整个漏掉（A）。

补扫那一档的 7 个文件逐个看（A）：

| 文件 | 大小 | 判定 |
|---|---|---|
| `D:/yzd/tmp/bench_cpu/models/yunet.onnx` | 232,589 B | **视觉件**（人脸检测，见第四节） |
| `D:/yzd/qwen3/qwen3_fp32_cpu/model.onnx`、`qwen3_fp16_cuda/model.onnx`、`qwen3_fp32_cpu_v/model.onnx`、`qwen3_fp16_cuda_v/model.onnx`、`qwen2_ref_model.onnx` | 145 KB–249 KB | 语言模型的**外部数据桩**（权重在旁边的 `.bin`/外存里），不是视觉件 |
| `D:/yzd/MSYS2/tmp/y8.onnx` | 269,578 B | **根本不是模型**，见下面第三行 |

- `D:/yzd/tmp/bench_cpu/models/` **清点时点**（10-12 上午）5 个文件：4 个视觉件 ＋ 1 个音频件（`speaker_eres2net.onnx`），无子目录（A）。本轮按"补一颗 yolov8n"的决定又放进 **2 个文件**，现在是 7 个（5 个视觉件 `.onnx`／`.task` ＋ `yolov8n_512x960.pt` ＋ 音频件），新增的两件见第十一节，来源与哈希在那一节登记（A）。
- 68 个里**视觉件本体只有 4 个**（都在 `bench_cpu/models/`），另有 `t.onnx` 是 yolov5n 的副本（下表），`y8.onnx` 不是模型；剩下 **63 个全是语音／TTS／语言模型**（CosyVoice-300M `llm.pt` 1,242,994,835 B 最大、SenseVoice、Paraformer、sherpa 的 whisper/zipformer/moonshine、TTS 的 vits/kokoro/piper/melo、FireRedASR/Punc/VAD/LID、qwen3 系列）。**没有任何别的视觉模型**——负断言的范围是"`D:/yzd` 下 ≥16 KB、扩展名 `.onnx/.tflite/.task/.pt/.pb/.engine/.nb/.torchscript/.om/.mlmodel/.caffemodel/.wk`、排除 `site-packages`／`.uvcache`／`.git`"（A，但**只对这条枚举口径成立**，低于 16 KB 或未列扩展名的不在覆盖面内）。
- 另外扫了 `C:/Users/YiZhidi` 与 `C:/Users/Public`（同口径 ≥300 KB）：只有 2 个 Edge 的 `typosquatting_list.pb`，不是模型（A）。
- **重复件**：`D:/yzd/MSYS2/tmp/t.onnx` 与 `yolov5n.onnx` 同尺寸（3,981,910 B）且 SHA256 前 16 位都是 `04f0e55c26f58d17` → yolov5n 的副本；`D:/yzd/MSYS2/tmp/sp.onnx` 与 `speaker_eres2net.onnx` 同尺寸（39,593,761 B）且完整 SHA256 都是 `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b` → 同一文件（A）。
- **`y8.onnx` 是一次失败下载的网页**：ORT 拒绝加载（`INVALID_PROTOBUF … Protobuf parsing failed`），文件头是 8 个 `0A` 之后接 `<!DOCTYPE html>`，`<title>` 为 `Page not found · GitHub · GitHub`，页面里的 `selected-link` 是 `/ibaiGorordo/ONNX-YOLOv8-Object-Detection/raw/main/yolov8n.onnx`（A）→ 有人想拉 yolov8n 但拿回 404 页面并存成了 `.onnx`。
- **`yolov8n.onnx` 到本轮结束时仍然不存在**：`bench_cpu/src/bench_src/` 的脚本把它当兜底文件名，但 `bench_cpu/models/yolov8n.onnx` 不存在（A）。拿它做基准的脚本会静默走 yolov5n 那条分支。
  本轮为"补一颗 yolov8n"探过三条路，只有一条通（A）：
  1. GitHub 两条直链 `raw.githubusercontent.com/ibaiGorordo/ONNX-YOLOv8-Object-Detection/main/yolov8n.onnx` 与 `cdn.jsdelivr.net/gh/ibaiGorordo/…@main/yolov8n.onnx` **都是 404**——`y8.onnx` 那份 404 网页不是偶然，那个仓库根本没有这个文件；
  2. 厂商 ModelZoo（ModelScope `AIBS` 组）的 yolov8 系列给的形态是 **TorchScript `.pt`，不是 ONNX**（清单页 `00_模型清单与性能.md` 第 241 行；仓库有 v3.31.0／v3.33.1／v3.36.1／v3.39.0_demo 四个 tag）；
  3. **正本本来就在手上**：ZG 编译那次用的输入件就是这颗 TorchScript——`S:\apps\llm\agentwork\build\icompile_v8n_512x960\fmodel\yolov8n_512x960.pt`，与 `config/ZG/Yolov8n_int8_512x960.toml` 里 `network = "fmodel/yolov8n_512x960.pt"` 指的是同一个文件（A）。把它传上去即可，**没有从外网下任何大资源，也没有动这台机上的 venv**。

## 二、实测环境（A）

**解释器有两个，各管一段**（第十一节的探针必须跨这两个跑，原因见 11.5）：

| 件 | 版本／读数 |
|---|---|
| **主 venv** `D:/yzd/tmp/bench_cpu/venv/Scripts/python.exe` | Python 3.12.15 |
| numpy | 2.5.3 |
| OpenCV（`cv2`） | 4.11.0 |
| ONNX Runtime（ORT，微软的 ONNX 推理引擎） | 1.20.1 |
| MediaPipe Tasks | 1.1.0 |
| 可用 provider | `AzureExecutionProvider`、`CPUExecutionProvider`；会话实际只有 `CPUExecutionProvider`（**无 GPU**） |
| **第二个 venv** `D:/yzd/qwen3/venv/Scripts/python.exe` | Python 3.12.15、**torch 2.14.1＋cpu（只有 CPU）**、transformers 5.19.0；**没有 `cv2`、没有 `PIL`**，也没有 `ultralytics`（所以 TorchScript 只能靠归档自带的 `code/` 跑，见 11.2） |

**并行约束**：校机上的 ASR 批次计划任务 `asr-xhs-chain` 本轮全程在跑（PID 21484／30436，10-12 03:02:54 起），探针跑前跑后各查一次进程表核对，未动它一根毫毛；探针一律限 2 线程。

## 三、视觉件的口，一览（A，本轮补到 6 个）

| 模型 | 大小／内容哈希 | 裸 ONNX 输入 | 裸 ONNX 输出 | 谁做解码与筛选 |
|---|---|---|---|---|
| `yunet.onnx` | 232,589 B／`8f2383e4dd3cfbb4` | `input` float32 **[1,3,640,640]** 静态 | **12 个张量**：`cls_8/16/32`、`obj_8/16/32` 各 [1,6400｜1600｜400,1]，`bbox_*` [.,4]，`kps_*` [.,10] | 调用方（或 `cv2.FaceDetectorYN`）：anchor 解码＋NMS（非极大值抑制，去重叠框） |
| `sface.onnx` | 38,696,353 B／`0ba9fbfa01b5270c` | `data` float32 **[1,3,112,112]** 静态 | `fc1` [1,128] float32，**未做 L2 归一化** | 调用方归一化；`cv2.FaceRecognizerSF` 会归一化 |
| `yolov5n.onnx` | 3,981,910 B／`04f0e55c26f58d17` | `images` **float16** [1,3,640,640] 静态 | `output0` **float16** [1,25200,85]，**已经 sigmoid 完（是概率）** | 调用方（无封装层，只能自己解码＋NMS） |
| `face_landmarker.task` | 3,758,596 B／`64184e229b2631…4e0bc9ff` | **不是单个 ONNX**：ZIP 容器里 3 个 TFLite ＋ 图元数据 | 只能经 MediaPipe Tasks，出 478 点／张脸 | MediaPipe 图（检测→关键点→blendshape 三级）**——这条路线已于 10-12 判废，见第七节抬头与 [[状态源与决策记录]] 的 D-46** |
| `yolov5s_960x512.onnx`（本轮补） | 28,944,074 B／`88f2ba7b1087931b` | `images` **float32** [1,3,**512,960**] 静态 | **3 个张量** `o0/o1/o2`＝[1,255,64,120]／[1,255,32,60]／[1,255,16,30]，**原始 logits（没 sigmoid）** | 调用方：先 sigmoid 再解码＋NMS，与 v5n 的口径**不通用**（见 6.4、十一节） |
| `yolov8n_512x960.pt`（本轮补） | 12,901,640 B／md5 `5acdcb81907edb79cf8e444f9494670f` | **不是 ONNX**：TorchScript，只吃 **float32 NCHW** [1,3,H,W]，H/W **动态** | **6 个张量**＝3 档 ×（80 类 logits ＋ 64 通道 DFL 框），**DFL／拼接都没做** | 调用方（`bench_yolo.py` 假设的 [1,84,8400] 形状**不是**它的，见十一节） |

---

## 四、`yunet.onnx` ＋ `cv2.FaceDetectorYN`（人脸检测）

### 4.1 文件本体（A）

ir_version 6、producer `pytorch 1.7`、opset `ai.onnx` 11、106 个节点、graph 名 `torch-jit-export`、**没有 `metadata_props`、没有 `doc_string`**（A）→ 文件里不带任何来源/许可标注，出处只能靠封装层（opencv_zoo 的 YuNet 口径，C）。

### 4.2 裸 ONNX 口（A）

- 输入 `input` float32 **[1,3,640,640]**，四根轴全是 `dim_value`（**静态**，batch／高／宽一律改不了）。
- 输出 **12 个张量**，按 stride 8/16/32 三档 × {cls, obj, bbox, kps}：锚点数分别 6400（80×80）、1600（40×40）、400（20×20）；`bbox_*` 每锚 4 维、`kps_*` 每锚 10 维（5 个点 × 2）。
- **所以"拿到 12 个张量"不是模型坏了**：解码、置信度合成、NMS 全在调用方。想要"直接给框"就得用 OpenCV 封装。

### 4.3 `cv2.FaceDetectorYN` 封装口（A）

`create(model_path, "", (w, h), score_threshold, nms_threshold, top_k)`；本轮 `create` 时给的 `(320,320)` 只是初值，**每次 detect 前必须 `setInputSize((帧宽, 帧高))`**，否则：

```
OpenCV(4.11.0) …/objdetect/src/face_detect.cpp:133: error: (-2:Unspecified error)
Size does not match … [2048x2048] must be equal to [320x320]
```

- 帧格式：**HWC 3 通道**，uint8 或 float32（0–255 数值域）都收；**非连续的 ROI 视图收**；尺寸不必是 32 的倍数（321×320 正常出）。
- **灰度图 (H,W) 直接被拒**：`convolution_layer.cpp:396` 报通道数必须是 3 的倍数、拿到 1。
- 输出 `ndarray [N,15]` float32：`x, y, w, h` ＋ 5 组 `(x,y)` ＋ 第 14 列是 score。**N 可以为 0**（`faces` 返回 `None` 或空数组，两种都遇到过，判空要 `faces is None or len(faces)==0`）。
- 5 个点的坐标几何自证（A）：第 1、2 点在最上（两眼），第 3 点在中间偏下（鼻尖），第 4、5 点在最下且分居中线两侧（两口角）。语义按 YuNet 惯例＝左眼／右眼／鼻尖／左嘴角／右嘴角（B，几何只能定到"眼/鼻/嘴"这一层，左右归属是文档口径）。
- **通道顺序实测**：`face_a.jpg`（|R−B| 均值 19.83，是彩色图）在 640² 下，按 BGR 进 score **0.94539**、按 RGB 进 score **0.93893** → 两样都出脸，**封装不校验通道顺序**（A）。

### 4.4 尺寸／门限的真实关系（A，本轮把旧结论改了）

同一张 `face_a.jpg` 缩放到不同方形帧，`FaceDetectorYN` 在两种 `score_threshold` 下的读数（首行 score；`0/-` 表示 0 行）：

| score_threshold | 160² | 320² | 640² | 1080² | 1440² | 1920² | 2048² | 2560² |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 1/0.9446 | 1/0.9539 | 1/0.9454 | 1/0.8862 | **3**/0.7042 | **5**/0.6346 | **6**/0.6364 | **11**/0.6344 |
| 0.3 | 1/0.9446 | 1/0.9539 | 1/0.9454 | 1/0.8862 | 2/0.7042 | 4/0.6346 | 5/0.6364 | 8/0.6344 |
| 0.5 | 1/0.9446 | 1/0.9539 | 1/0.9454 | 1/0.8862 | 2/0.7042 | 2/0.6346 | 2/0.6364 | 4/0.6344 |
| 0.7 | 1/0.9446 | 1/0.9539 | 1/0.9454 | 1/0.8862 | 1/0.7042 | **0/-** | **0/-** | **0/-** |
| 0.9 | 1/0.9446 | 1/0.9539 | 1/0.9454 | **0/-** | 0/- | 0/- | 0/- | 0/- |

三条要点：

1. **"1920²／2048² 检不到脸"不是硬尺寸上限**——把 `score_threshold` 从 0.7 降到 0.1，同样的帧照样出行（score 0.634 左右）。**是分数被跨过阈值**（A）。本轮之前挂在页面上的"尺寸律上限 1080²"这条按此作废。
2. 分数随帧边长单调衰减：0.9446@160 → 0.9539@320 → 0.9454@640 → 0.8862@1080 → 0.7042@1440 → 0.634 一带（1920 以上）。原因与"裸输入静态 640×640、整帧必须重采样进模型"一致，但**逐段归因未取证**（B）。
3. **大帧时 `rows[0]` 不再是人脸**：1920²／score_threshold 0.1 下首行框是 `[559.1, 672.2, 583.8, 693.4]`，而 640² 那次的框等比放大到 1920 应为 `[592.5, 441.9, 745.5, 1032.3]`——差得很远（A）。所以**别默认"第一行就是最可信的那张脸"，大帧时会拿到错位框**；同时 1440²／1920²／2560² 会返回 3～11 行冗余框（A）。

半高贴图画布（同一张照片缩到帧高 50%、贴进 16:9 灰底）：

| 画幅 | sthr 0.1 | 0.3 | 0.5 | 0.7 | 0.9 |
|---|---|---|---|---|---|
| 640×360 | 1/0.9422 | 同 | 同 | 同 | 0/- |
| 1280×720 | 1/0.9501 | 同 | 同 | 同 | 0/- |
| 1920×1080 | 1/0.9529 | 同 | 同 | 同 | 0/- |
| 3840×2160 | 2/0.8859 | 1/0.8859 | 1/0.8859 | 1/0.8859 | 0/- |

注意 **3840×2160（脸 1080 px）拿到 0.8859，与 1080² 满帧（脸几乎铺满）的 0.8862 几乎相同**——两个画幅的脸占帧长边的比例完全不同（0.28 与 0.53）却同分（A）。所以**这轮拿不到一条可用的"相对尺寸律"**，任何按"脸占画幅比例"外推分数的做法都没有实测支撑（诚实写法：机制未取证，勿当判据用）。

## 五、`sface.onnx` ＋ `cv2.FaceRecognizerSF`（人脸特征 128 维）

### 5.1 文件本体（A／B）

ir_version 6、**producer 字段为空**、graph 名 `mxnet_converted_model`、opset 11、88 个节点、无 `metadata_props`／`doc_string`（A）。graph 名说明它是**从 MXNet 转出来的**（B）；`insightface` 的 SFace/ArcFace 系这一说属于圈内口径（C），文件里没有自证。

### 5.2 裸 ONNX 口（A）

- 输入 `data` float32 **[1,3,112,112]**。batch=2、224²、100² 全部 `INVALID_ARGUMENT`。
- 输出 `fc1` [1,128] float32，**不是单位向量**：实测范数 6.97206／10.21521／11.74368／12.61908／13.06008／14.42501（A）。
- 模型图里只有 1 个 initializer（A）→ BN 等已折叠，没有额外权重外置。

### 5.3 预处理：16 种组合里只有 1 种能复现封装（A，本轮定案）

用 `cv2.dnn.blobFromImage(alignCrop 出的 112² 图, scale, (112,112), mean, swapRB, False)` 喂裸模型，与 `FaceRecognizerSF.feature()` 的输出比余弦：

| 组合 | cos vs 封装 |
|---|---|
| **swapRB=True，scale=1.0，mean=0** | **1.000000** |
| swapRB=False，scale=1.0，mean=0 | 0.888584 |
| swapRB=True，scale=1.0，mean=(129.15,104.91,104.0) | 0.299217 |
| swapRB=True，scale=1/255，mean=0 | −0.021457 |
| 其余 12 种（各 mean × 两种 scale） | 0.13–0.35 |

逐图复核（`v5d`）：`cos_rawRGB` 1.0–1.00000012，最大逐元素差 ≤ 4.53e-6，**范数与封装一致到 5 位小数**（A）。手写 `transpose(RGB,(2,0,1))` 也是 1.0（A）。

- **结论：这个 build 的正确预处理是"转 RGB、CHW、不除 255、不减均值"**（A）。被广泛抄用的 mean (129.15, 104.91, 104.0) 在这里是**错的**（cos 0.299），/255 更是灾难（cos ≈ −0.02）。
- **通道陷阱**：保留 BGR 在彩色脸上 cos 只掉到 0.86916–0.888584（看着"还能用"），但在近灰的爱因斯坦照片上 cos **恰好 1.0**（A）——这就是前几轮探针分不清通道顺序的原因，也意味着**通道顺序错了不会报错、只会静默降质**，而拿灰度图去验通道顺序是验不出来的。

### 5.4 `alignCrop` 吃什么（A）

输入形态**六种全收**：15 列 float32、去掉 score 的 14 列、float64、只给 4 列矩形（float32 与 int32 都行）、`[1,15]` 二维数组。输出恒为 `[112,112,3]` uint8。
**封装不做通道转换**：BGR 帧进去输出均值 `[142.21,148.31,171.01]`，RGB 帧进去输出 `[171.01,148.31,142.21]`（A）。所以 5.3 那条"必须转 RGB"要一路管到 `feature()` 之前。

### 5.5 `match()` 的两种度量（A）

6 对人脸特征（爱×2、居里×2 共 4 张，两两 + 交叉）实测：

| 度量 | 语义 | 读数 |
|---|---|---|
| `match(a,b,0)` | **余弦**，与手算 6 位小数完全一致 | 同人 0.572525（爱因斯坦两张）／0.654750（居里两张）；异人 0.070567–0.195564 |
| `match(a,b,1)` | **归一化之后的 L2 距离** ＝ sqrt(2−2cos) | 0.924635／0.830964／1.268413／1.282797／1.331908／1.363403 |

关键：**type 1 不是原始 L2**——爱因斯坦两张的原始 L2 是 12.32966，而 `match(…,1)` 给 0.924635（A）。拿 0.363 这个常用门限（opencv_zoo 样例口径，C，本轮未做数据集验证）判同人时，必须知道它配套的是**归一化后**的余弦／L2，而不是裸输出的距离。

## 六、`yolov5n.onnx`（物体检测，无封装层，裸 ORT）

### 6.1 文件本体（A／B）

**ir_version 8**（另三个件都是 6）、producer `pytorch 1.14.0`、opset 17、263 个节点、`metadata_props` 只有两项：`stride=32` 与 `names=`（COCO-80 的 Python 字典字面量）。图名 `torch_jit`（A）。
op 直方图头部：`Mul` 69、`Conv` 60、`Sigmoid` 60、`Constant` 27、`Concat` 17、`Add` 10、`Reshape` 6、`MaxPool` 3（A）。
**字节扫描里没有 `Ultralytics`、`YOLOv5`、doc_string、日期、版本号任何一处**（A）→ "它是 Ultralytics 官方导出的"只能按 `names` 字典字面量＋`stride` 这对特征判到 **B**。

### 6.2 口（A）

- 输入 `images` **float16** [1,3,640,640]，**静态**。喂 float32 直接：`Unexpected input data type. Actual: (tensor(float)), expected: (tensor(float16))`。(1,3,320,320)、(1,3,640,416)、(1,3,1280,720)、(2,3,640,640) 全 `INVALID_ARGUMENT`。**必须显式 `.astype(np.float16)`**。
- 输出 `output0` float16 **[1,25200,85]**：25200 =（80²＋40²＋20²）×3 个锚框，85 = 4（cx,cy,w,h，**在 640 像素空间**）＋ 1（obj）＋ 80（类别）。**没有 NMS、没有解码**，全是调用方的活。
- 实测最高项示例：conf 0.94683／cls 0（person）／obj 0.9292，框 `[226.5, 363.8, 76.5, 230.6]`（640 空间）。

### 6.3 归一化与通道（A）

| 送进去的东西 | obj>0.25 的锚数 | 最大 obj×cls | obj×cls>0.25 的锚数 |
|---|---|---|---|
| RGB ÷255 | 285 | 0.94683 | 251 |
| BGR ÷255 | 251 | 0.94783 | 213 |
| **RGB 原样 0–255** | **4362** | **1.0** | 1934 |
| RGB ÷255 再减 114 | 228 | 0.9449 | 182 |

- **÷255 是硬要求**：不除的话 sigmoid 输入爆掉，conf 齐刷刷顶到 1.0，**判别度彻底消失**，而且不报错（A）。
- 通道顺序同样**静默**：BGR 也能跑，只是候选框少 38 个（213 vs 251）（A）。
- "减 114"这一行是**把 padding 值当均值减掉**的近似，**不等于 letterbox（保持比例补边再缩放）**；真 letterbox 的实测本轮未做（D）。

### 6.4 与 `yolov5s_960x512.onnx` 的口径差：一个吐概率、一个吐 logits（A，本轮补测）

同一套 letterbox（补边值 114、÷255、转 RGB）把 4 张真图分别送进两个件，读输出张量的数值域就把两件事分开了：

| 件 | 输出 | 第 5 列（obj）／`o0` 的数值域 | 直接当概率用 | 再过一道 sigmoid |
|---|---|---|---|---|
| `yolov5n.onnx` | [1,25200,85] float16 | obj ∈ **[0.0, 0.61816]**，全部落在 [0,1] | obj×cls>0.25 的锚数 **8** | **25200**（＝全过，判别度归零） |
| `yolov5s_960x512.onnx` | 三个 [1,255,GH,GW] float32 | `o0` ∈ **[−19.14, +7.38]**（跨 4 张图） | —— | 必须；解出来才是 11 节那张表 |

- **`yolov5n.onnx` 的导出图里已经把 Sigmoid 算进去了**（6.1 的 op 直方图里 `Sigmoid` 60 个就是证据；本轮拿到的是数值域上的直接自证）→ **再 sigmoid 一次会把所有锚的分数抬到 0.5 以上**，`conf>0.25` 计数从 8 变成 25200，等于什么都没筛（A）。
- **`yolov5s_960x512.onnx` 是原始 logits**（出现 −19 这一档负数，概率不可能为负）→ 解码前必须自己做 `sigmoid`（A）。
- 所以**同一份"YOLOv5 后处理代码不能跨这两个件复用**：形状不同（拼接 25200×85 vs 三头 255×GH×GW）、数值域也不同（概率 vs logits）。写基准脚本时这两个差异要分开处理（A）。

## 七、`face_landmarker.task` ＋ MediaPipe Tasks 1.1.0（478 点人脸关键点）

> **本节路线已判废（10-12，D-46，见 [[状态源与决策记录]]）**：`face_landmarker.task` 不进现役，人脸侧只保留 `yunet.onnx` ＋ `sface.onnx` 那条 OpenCV 链（第四、五节）。下面的实测**全部保留**，它们是判废依据，也是以后有人再提这条路线时的成本账。

### 7.1 容器：`.task` 是 ZIP，不是模型（A）

magic `0000504b`（`PK`），`is_zipfile` 为真，4 个条目全是 **stored（不压缩）**、时间戳 2023-05-03 18:01:28：

| 条目 | 大小 | 偏移 4 处 |
|---|---|---|
| `face_detector.tflite` | 229,746 | `TFL3` |
| `face_landmarks_detector.tflite` | 2,553,590 | `TFL3` |
| `face_blendshapes.tflite` | 955,312 | `TFL3` |
| `geometry_pipeline_metadata_landmarks.binarypb` | 19,376 | 图元数据（二进制 protobuf） |

内嵌字符串里有 `keras2tflite_facedetector-front.tflite`（A）。**ORT 加载它直接失败**：`INVALID_PROTOBUF : Load model from …face_landmarker.task failed:Protobuf parsing failed`（A）→ 这条 `task` 只能走 MediaPipe Tasks，**别指望在 ORT／NPU 上直推**；上 NPU 时要把三级子图分别当三个 TFLite 处理（B，容器结构直接可推）。

### 7.2 接受的输入（A）

`mp.Image(image_format=mp.ImageFormat.SRGB, data=…)`，`ImageFormat` 的枚举值：SRGB=1、SRGBA=2、GRAY8=3、GRAY16、SRGB48、SRGBA64、VEC32F1=9、VEC32F2=12、VEC32F4。

**能出关键点的**：

- SRGB ＋ (H,W,3) uint8 → 478 点（正常路径）。
- SRGBA ＋ (H,W,4) uint8 → 出点，**alpha 被完全忽略**（同图与 SRGB 的首点 xyz 逐位相同：0.5024／0.5557／−0.0133）。
- **把 BGR 数组当 SRGB 塞进去照收不误**，不报错、不转换（A）→ 通道顺序自己负责。
- 4000×3000 收（detect 0.012 s）。

**构造成功但 detect 失败**（报 `ImageToTensorCalculator … Unsupported format`）：GRAY8 ＋ (H,W)、VEC32F1、VEC32F2；GRAY8 标志 ＋ (H,W,3) 数组（只读前 H·W 字节后失败）。

**构造函数当场拒绝**：SRGB ＋ (H,W) → `Pixel data size is too small: 518400 (expected 1555200)`；VEC32F4 ＋ (H,W,3) float32；`UNKNOWN` → 错误文本把合法 uint8 集合写全了：`expected GRAY8, SRGB, or SRGBA`，float/uint16 的报错列 `VEC32F1/F2/F4` 与 `GRAY16, SRGB48, SRGBA64`。

**两条会打死进程的**（A，最该记住的一条）：

> **GRAY16 与 SRGB48 触发 glog 的 `CHECK` 而非 Python 异常**：`F0000 … image_frame.cc:135] Check failed: ImageFormat::UNKNOWN != format_ (0 vs. 0)`，进程返回码 **3221226505（0xC0000409）**。`try/except` **拦不住**，整个解释器没了。探针因此一律做了子进程隔离（第九节）。

**静默失败的**：非连续的切片视图（如 `arr[::2]`）构造成功、detect 返回 **0 张脸**、不报错（A）→ 传数组前一律 `np.ascontiguousarray`。全零图、随机噪声、1×300、63×63 → 都是 0 张脸、不报错。

### 7.3 输出结构（A）

`FaceLandmarkerResult` 三个字段：`face_landmarks`、`face_blendshapes`、`facial_transformation_matrixes`（IMAGE 模式）。

- **`face_landmarks`**：每张脸 **478** 个 `NormalizedLandmark`，字段 `x, y, z, presence, visibility, name`；**IMAGE 模式下 `presence`／`visibility` 恒为 `None`**（只有 VIDEO 模式填）。x、y 是**整帧**归一化到 [0,1]（不是脸的框内归一）；z 是相对量，实测范围 −0.0289…0.0549（脸占帧高 50%）与 −0.046…0.0873（占 80%）——**z 的尺度随脸大小变，不能当绝对深度用**（A）。
- **`face_blendshapes`**：每张脸 **52** 个 `Category`（`name`/`score`），名字就是 ARKit 那一套（Apple 定义的面部动作单元命名，`_neutral`、`browDownLeft`…`noseSneerRight`，全表在 `io_probe5.json`）；**52 个 score 之和实测 2.5404 → 不是 softmax 概率**（A），别当"加起来＝1 的表情分布"用。
- **`facial_transformation_matrixes`**：每张脸 4×4 float32，末行 `0 0 0 1`；实测旋转部分≈单位阵、平移 z = **−61.6775**（A）→ 单位不是像素也不是归一化帧，**坐标约定本轮未取证**（D）。

### 7.4 门限、尺寸、多人（A，除注明）

`num_faces` 可以是几？——**0 或 −1 会让图初始化就失败**：`ClipNormalizedRectVectorSizeCalculator: max_vec_size should be greater than or equal to 1`（A）。

**检测尺寸律（对 `face_a.jpg`，21 帧无反例）**：脸边长 ÷ 帧**长边** ≥ **0.196** 才出点；251/1280 出，216/1280、200/1280、360/2560、300/2000、144/1280、270/4000 都不出。**绝对像素数无关**：240 px 在 640×480 出，200 px 在 1280×400 不出。机制**未取证**，只与"检测器输入是按长边归一的方形图"这个假设相容（B）。
**同门限下不是所有脸都守这条**：`face_b.jpg` 贴正中间时 360 出、315 出、302 出、**330 不出**（非单调，A）→ 尺寸律只对测过的那张脸成立，别外推成通用判据。

**多人行为**（`num_faces=5`，同一实例只改门限；下表是每组输出的 x 中心均值）：

| min_face_detection_confidence = min_face_presence_confidence | `face_b` 单张贴右侧（302 px） | 双人脸帧（两张各 302 px） |
|---|---|---|
| 0.5（默认）／0.3／0.2 | **0 组** | **1 组**：0.151（左脸） |
| 0.1 | 1 组：0.856 | **2 组：0.151、0.153 —— 两组都落在左脸上，右脸仍缺席** |
| 0.01 | 2 组：0.84、0.856（**同一张脸重复两组**） | 3 组：0.151、0.84、0.153 ＝ 左×2 ＋ 右×1 |

三条要点（A）：

1. **返回的组数 ≠ 画面里的人数**。门限低时一张物理脸会给多组关键点（重叠检测），门限默认时双人帧只出一组。任何"按 `len(face_landmarks)` 数人头"的写法在这套默认参数下**必错**。
2. 双人帧在默认门限下拿到的是**置信度较高的那张**（本例左侧），另一张不是被裁掉而是**根本没通过检测门限**（把门限降到 0.01 它就出现，A）。至于它为什么分数低，**本轮分不开**：同一张 `face_b` 在默认门限下 302 px 贴正中出、贴右边缘不出，360 px 贴右边缘又出，330 px 贴正中反而不出（A）——尺寸、贴边位置、脸本身内容三个变量互相纠缠，没有一组实验能把它们拆开（B，**未归因**）。
3. 单张 detect 在这些尺寸下 **0.005–0.02 s**。

### 7.5 贵得要命的一步：`close()`（A）

同一份代码分相计时（`io_probe5i.json`，5 次独立子进程）：

| 阶段 | 耗时 |
|---|---|
| 读图＋构造 `mp.Image` | 0.03–0.07 s |
| `FaceLandmarker.create_from_options` | **0.08–0.10 s** |
| 每次 `detect` | 0.01–0.05 s |
| **`m.close()`** | **42.21／42.20／42.24／42.27／42.30 s** |

**`close()` 每次都固定阻塞约 42.2 秒**（A），而创建和推理都是百分秒级。**"建实例→跑→关掉"循环在这台机上会表现成"程序卡死"**：本轮两个探针（v5f、v5h）就是这么废掉的——v5h 的 6 档门限 × 42 s 直接撞上 240 s 超时。不 `close()`、直接让进程退出是干净的（v5g、v5j 就是这么跑的）。**是 CPU 计算还是在等什么，本轮没拆**（机制未归因）。

## 八、`speaker_eres2net.onnx`（同目录，但**不是**视觉件）

顺手登记以免被误当视觉模型：输入 `x` float32 [**N**, **T**, 80]（动态 batch／帧数，80 维是 fbank 特征），输出 `embedding` [?, 512]；`metadata_props` 自报 `framework=3d-speaker`、`language=Chinese`、`sample_rate=16000`、`output_dim=512`、`feature_normalize_type=global-mean`、`url=modelscope iic/speech_eres2net_base_sv_zh-cn_3dspeaker_16k`，ir_version 7、producer `pytorch 2.4.1`、opset 13、516 节点（A）。**是说话人向量（声纹）模型，吃音频特征不吃图**。音频侧口径见 [[音频]]。

## 九、探针怎么跑的，原始记录在哪（A）

**隔离口径**：每个探针都是"父进程 `subprocess.run(child, timeout=…)` ＋ 子进程打印 `RESULT::{json}`"，原因是 MediaPipe 的 `CHECK` 会当场打死解释器（7.2），不隔离就会连带丢掉后面所有用例。子进程同时把结果**增量**写盘，超时也能留下半份数据。

第十一节的探针还要多一层：TorchScript 只能在 `D:/yzd/qwen3/venv` 里跑，而那个 venv 没有图像读取库，所以父进程**按用例分别指定两个解释器**起子进程，图像侧先由主 venv 落成 `.npy` 交接件、再由 qwen venv 读盘（11.5）。

| 位置 | 内容 |
|---|---|
| 本机 `S:\work\WCIS\workenv\benchcpu\` | 脚本 `io_probe_v5.py`、`_v5b`…`_v5n`（`_v5f`、`_v5h` 两轮作废：见 7.5）、**`io_probe_v6.py`（装载＋签名＋候选输入）、`_v7.py`（真图解码，跨两个 venv）、`_v8.py`（形状／dtype 边界）、`_v9.py`（50 档尺寸阶梯）、`_v10.py`（失败档的完整报错）**、`io_probe_vision.py`、`io_probe_v4.py`、`scan_models.py`、`count_find.sh`、`get_v8.sh`／`find_v8.sh`／`read_zoo.sh`／`read_zoo2.sh`（第一节那三条"补 yolov8n"的路径探查）；结果 `io_probe4.json`、`io_probe5.json`、`io_probe5b/5c/5d/5e/5j/5l/5n.json`、`out\io_probe5g.json`、`out\io_probe5i.json`（分相计时）、`out\io_probe5i_child_*.json`、**`io_probe6_v8n_ts.json`、`io_probe6_v5s_ort.json`、`io_probe6_parent.json`、`io_probe7_v5s_decode.json`、`io_probe7_v8n_real.json`、`io_probe7_parent.json`、`io_probe8_v5s_shape.json`、`io_probe8_v8n_shape.json`、`io_probe9_sizes.json`、`io_probe10_err.json`**、`scan_d.txt`、`scan_c.txt`、`y8.onnx`（第一节那条"404 网页冒充模型"的本地留样，269,578 B）、`topush\`（两件上传用的暂存副本，与 11.1 的两个 md5 一致） |
| 校机 `D:\yzd\tmp\bench_cpu\src\io_probe\` | 同名脚本＋`out\io_probe.json`、`io_probe4/5/5b/5c/5d/5e/5g/5i/5j/5l/5n.json`、`out\io_probe5h.json`（那是一份 `TIMEOUT_240S` 的存根，留着当 7.5 那条的证据）、`out\io_probe5i_child_*.json`（10 份）、`out\run5*.out`、`out\count_find.txt`（68 行清单原件）、**`out\io_probe6_*.json`、`out\io_probe7_*.json`、`out\io_probe8_*.json`、`out\npy_*.npy`（8 份 letterbox 交接件，见 11.5）、`out\io_probe9_sizes.json`、`out\io_probe10_err.json`、`out\run7.out`／`run8.out`／`run9.out`** |
| 校机（同目录） | `scan_models2.py` 已推上去但**未执行**——清点改用 MSYS2 `find` 做独立交叉核对，两个枚举已经一致（第一节），Python 版重复跑没有新增信息 |

**跑过的清理**：本轮生成的 22 个 `*.tar`（tar-over-ssh 的传输件）已按"删除一律进回收站"的口径送进回收站、没有硬删（A）；`.npy` 交接件与全部 JSON 留在校机上没动。

**被本轮作废的旧说法**（写在这里防止复活）：① "FaceDetectorYN 在 1920²／2048² 检不到脸"→ 那是 `score_threshold=0.7` 被跨过，降到 0.1 就有行；② "尺寸律上限是 1080²"→ 同上作废；③ "双人帧只返回 1 组"→ 补门限扫描后改成 7.4 那条更完整的表述（**组数≠人数**，且低门限会重复出组）；④ "这台机上没有 yolov8 模型，只有一个 404 网页冒充它"——**前半句到本轮结束时只对 ONNX 形态成立**：`yolov8n_512x960.pt`（TorchScript）现在在这台机上并且跑通了（第十一节）；`yolov8n.onnx` 仍然不存在，那条 404 网页的判断不变；⑤ **v6 那轮报的 v8n 单次耗时（126.5／147.8／100.5 ms）与那批输出统计**——分别是"第一发"和"全零输入"下的数，按 11.2 与 11.5 作废，别再引用。

## 十、音箱（本页原有内容，逐字保留）

原来这一页只有三行，没有任何实测支撑，也没在本次视觉模型的清点范围内。为不丢内容，逐字抄在这里（只把行尾从 CRLF 换成 LF，符合 `tools/check-md.py`）：

```
音箱
输出 WAV、PCM （S16_LE）、双声道、48000 Hz。plughw:0,0
输入 arecord -D plughw:0,0 -f S16_LE -r 48000 -c 1 test.wav
```

其中"双声道"与示例命令里的 `-c 1`（单声道）措辞不一致，本轮**没有复测声学侧**，所以不判哪一条对（D）。板载 USB 声卡 MCP01 的采样与控件实测在 [[音频]]（那条链上 48000 Hz 是实测过的，`plughw` 的重采样行为有记录）。

## 十一、本轮补进来的两件：`yolov8n_512x960.pt` 与 `yolov5s_960x512.onnx`（A）

她 10-12 的裁定是"**补**"（原话："补，不进现役但要作为废案记录"）。两件都从 ZG 编译工程的 `fmodel/` 原样传上校机，**没有从外网下任何大资源，也没有动这台机上的 venv**。MediaPipe 那条路线按 [[状态源与决策记录]] 的 **D-46** 判废、第七节转留档。

### 11.1 来源与落点（A）

| 件 | 大小 | md5 | 正本在本机的位置 | 校机落点 |
|---|---|---|---|---|
| `yolov8n_512x960.pt` | 12,901,640 B | `5acdcb81907edb79cf8e444f9494670f` | `S:\apps\llm\agentwork\build\icompile_v8n_512x960\fmodel\`——**ZG 编译实际吃的那颗输入件**，`config/ZG/Yolov8n_int8_512x960.toml` 里 `network = "fmodel/yolov8n_512x960.pt"` 指的就是它 | `D:\yzd\tmp\bench_cpu\models\`，mtime 2026-10-12 10:11 |
| `yolov5s_960x512.onnx` | 28,944,074 B | `4e17a85445fe1b8f76bb376524e85ae4` | `S:\apps\llm\agentwork\build\icompile_960\fmodel\`——板上现役 `yolov5s_plin_960x512_ZG` 那颗 imodel 的输入（[[板端我方代码与产物台账]] #25／#26 的正本上游） | 同上 |

上传＝`tar -cf - … \| ssh school-guest "tar -xf - -C …"`，两侧 md5 复算逐字一致（A）。

### 11.2 `yolov8n_512x960.pt`：TorchScript 归档的口

**装载**（A）：`torch.jit.load` 直接成功，1.51 s，得到 `RecursiveScriptModule`。这台机的 venv 里**没有装 `ultralytics`**——归档自带 `code/__torch__/…` 字节码，不需要那个包就能跑。torch 2.14.1＋cpu，2 线程。

**图签名**（A，`graph.inputs()`／`graph_outputs()`）：输入 `input.1: Tensor`（另一个 `self.1` 是模块自身），**输出只有 1 个值、类型 `List[Tensor]`**；顶层 77 个节点，尾部是 `prim::CallMethod`×4 ＋ `prim::TupleUnpack` ＋ `prim::ListConstruct` → 那个列表展开成 **6 个张量**（见下）。

**吃什么**（A，逐档试出来的）：

| 送进去 | 结果 |
|---|---|
| float32 NCHW [1,3,512,960]，像素 ÷255 | **通** |
| float32 NCHW，原样 0–255 | **通**（不报错；但本轮这一档是在全零输入下试的，见 11.5） |
| uint8 [1,512,960,3] | **拒**，TorchScript 在 `self.model.0` 的 Conv 处失败 |
| float32 NHWC [1,512,960,3]／[1,640,640,3] | **拒**，同一处 |
| float64／float16 | **拒** |
| float32 NCHW，batch=2 | **通**，6 个输出的第 0 轴都变 2 |

→ **这个归档的口是 float32 NCHW**，NHWC／uint8 一律进不去。送进去的是 RGB（letterbox 后 `canvas[:,:,::-1]`），但**本轮没做 BGR／RGB 差分，通道顺序对这颗件的影响未证**（D）。

**分辨率的真实边界**（A，50 档扫描 ＋ 规则核对）：**不是任意动态**。规则是（B；对全部 50 档实测零反例）：每个轴独立，令 `g8 = ceil(ceil(ceil(H/2)/2)/2)`、`g16 = ceil(g8/2)`、`g32 = ceil(g16/2)`，要求 **`g8` 与 `g16` 都是偶数**；不满足就在 neck 里那次 `torch.cat` 上崩。

| | 尺寸（方形） | 尺寸（矩形，H×W） |
|---|---|---|
| **通** | 32、63、64、96、128、160、192、224、256、288、318、319、320、352、384、416、448、480、512、544、576、640、704、768、896、1024、255 | 512×960、960×512、1280×704、1280×640、640×1280、1280×960、960×1280、384×1024、1024×384 |
| **崩** | 16、45、48、80、112、257、720、1080 | 1280×**720**、**720**×1280、1920×**1080**、**1080**×1920、30×40、40×30 |

- **板侧那两档直播分辨率直接喂都进不去**：1920×1080 与 1280×720 都崩，因为坏在 H 轴；把高改成 704（1280×704）或 640 就通（A）。任何"整帧塞进 v8n"的写法都得先落到合法档。
- 崩溃正文（A，逐字）：`RuntimeError: Sizes of tensors must match except in dimension 1. Expected size 46 but got size 45`（720²）、`136／135`（1080²）、`2／1`（16²）、`4／3`（48² 与 30×40）、`18／17`（257²）。**每一条都正好等于规则里第一个失败的拼接**（P4←P5 那一跳先于 P3←P4），报错点是 `torch.cat([argument_1, argument_2], 1)`。
- 输出网格随轴独立转置：960×512 → `[[120,64],[60,32],[30,16]]`，512×960 → `[[64,120],[32,60],[16,30]]`（A）→ H／W 各走各的，没有"必须正方形"这种隐藏约束。

**吐什么**（A）：**6 个张量 = 3 档 ×（80 类 ＋ 64 通道）**，顺序是 `(P3 cls, P3 box, P4 cls, P4 box, P5 cls, P5 box)`；512×960 下是 `[1,80,64,120] [1,64,64,120] [1,80,32,60] [1,64,32,60] [1,80,16,30] [1,64,16,30]`。
- **DFL 与拼接都没做**：`bench_yolo.py` 假设的 `[1,84,8400]` 对这颗件不成立（A）。类别侧是**原始 logits**（4 张真图实测跨 −45.05…＋2.95），必须先 sigmoid；框侧 64 = 4 边 × 16 bin 的分布（实测 −9.98…＋20.00），要自己做 `softmax(16)·arange(16)` 求和再乘 stride（B——"这 64 个通道就是 DFL 分布"按形状与数值域判，图里没读代码）。
- 真图门限读数（sigmoid 后，`max prob` 与 `cell>0.25` 的格子数，8 组＝4 图 × 2 档）：

| 输入 | P3（细） | P4（中） | P5（粗） | 出现类别（argmax，门限 0.25） |
|---|---|---|---|---|
| face_a 512×960 | 0.051／0 | 0.060／0 | **0.897／10** | 0 |
| face_a 640² | 0.068／0 | 0.090／0 | **0.776／11** | 0 |
| curie 512×960 | 0.010／0 | 0.015／0 | **0.915／10** | 0 |
| curie 640² | 0.022／0 | 0.029／0 | **0.884／10** | 0 |
| einstein 512×960 | 0.025／0 | 0.248／0 | **0.935／10** | 0 |
| einstein 640² | 0.027／0 | 0.108／0 | **0.913／15** | 0、56 |
| scene 512×960 | 0.729／18 | 0.891／85 | **0.933／73** | 0、1、2、9、24、25／0、1、2、5 |
| scene 640² | 0.849／38 | 0.925／78 | **0.950／52** | 0、2、24、26／0、1、2、9、25／0、1、2、5 |

**单张人像只在最粗那档（stride 32）出格子**，细档概率连 0.25 都不到；多人／多物场景三档全出（A）。640² 与 512×960 两种档位给的结论一致，档位本身不改变"人像落在 P5"这件事（A，仅此 4 张图）。

**计时**（A，同一进程内三连发）：512×960 = **225.5／127.8／75.2 ms**，640² = 74.9／61.4／61.1 ms，1024² ≈ 200 ms，32² ≈ 19 ms。**第一发是热身的 2–3 倍**，所以单次计时不能报；v6 那轮的 126.5／147.8／100.5 ms 全是"第一发"，**降级为不作数**（A）。

**与 ZG 编译 toml 的对照**（A，这条是给编译侧的更正）：`[parse]` 段写的是 `inputs = [1, 512, 960, 3]`、`inputs_layout = "NHWC"`、`inputs_dtype = "UINT8"`、`pre_scale = [255,255,255]`、`pre_mean = [0,0,0]`、`channel_swap = [0,1,2]`、`image_channel_order = "rgb"`、`framework = "pytorch"`、`frame_version = "1.9"`。**这些字段描述的是 icraft 往模型里灌数据的方式（编译器摄取约定），不是归档自己的签名**——同一个文件在 torch 里只收 float32 NCHW（A）。把 toml 当"模型接受 NHWC uint8"来写 PC 侧预处理会直接跑不通。`frame_version = "1.9"` 与本机 torch 2.14.1 能装载并不矛盾（归档向后兼容，本轮实测装载并前向成功，A；机制未取证，B）。

顺带一条**出处证据**（A，从 TorchScript 的报错正文里掉出来的）：失败栈里带着导出时的绝对路径 `1_save.py(90): new_export_torchscript` 与 `…\yolov8\yolov8_icraft\.venv\lib\site-packages\ultralytics\engine\exporter.py`——这颗 `.pt` 是**别人用 ultralytics 的导出器在一台 Windows 机上现导的**，账号名一段本轮按 D-21 凭据条款脱敏，原文在 `io_probe9_sizes.json` 的 `err` 字段里。

### 11.3 `yolov5s_960x512.onnx`：裸 ONNX 的口

**文件本体**（A）：28,944,074 B、SHA256 前 16 位 `88f2ba7b1087931b`、ir_version 8、producer `pytorch **2.10.0**`、graph 28,944,046 B、**231 个节点**、opset `ai.onnx` 17、**`metadata_props` 是空的**（对比：`yolov5n.onnx` 带 `stride` 与 `names` 两项）→ **这颗件里不带 COCO 类名表**，第 5 节之后要打名字得从外部拿（A）。

**吃什么**（A）：输入名 `images`，float32 **[1,3,512,960]**，**完全静态**——8 档形状尝试只有这一档通过：

| 尝试 | 结果 |
|---|---|
| [1,3,512,960] | **通** |
| [1,3,**960,512**] | 拒：`index: 2 Got: 960` |
| [1,3,640,640]／[1,3,512,640]／[1,3,256,480]／[1,3,608,960] | 拒（index 2 或 3） |
| [2,3,512,960]（batch）／[1,4,512,960]（通道） | 拒（index 0／1） |
| dtype 换 double／uint8／float16 | 三种全 `Unexpected input data type … expected (tensor(float))` |

- **文件名里的 "960x512" 是 W×H，张量轴序是 [N,C,H,W]＝[1,3,512,960]**：把两处顺序搞混就是上面那条 `index: 2 Got: 960`（A）。
- 与 `yolov5n.onnx` **正好相反**：那颗必须 float16，这颗必须 float32（A，第六节 6.2）。

**吐什么**（A）：**3 个输出** `o0`/`o1`/`o2` = [1,**255**,64,120]／[1,255,32,60]／[1,255,16,30]，每档 NCHW；**255 = 3 个 anchor × 85（4 框 + 1 obj + 80 cls）**。这与 `yolov5n.onnx` 的单一 `[1,25200,85]` 是两种导出约定（拼接与否）。
- **数值域是原始 logits**：4 张真图的 `o0` 跨 **[−20.54, ＋7.38]**（A）→ **必须自己先 sigmoid**；把 v5n 的后处理直接搬过来会让所有锚的分数挤到 0.5 以上（6.4 那条 8→25200 就是这么来的）。
- 真图解码（letterbox 补边 114、÷255、RGB；`sigmoid(obj)×max sigmoid(cls) > 0.25` 的锚数）：

| 图 | 缩放 k | 三档锚数（P3／P4／P5） | 合计 | 最高 obj×cls | 类别 |
|---|---|---|---|---|---|
| face_a | 0.25 | 0／0／**4** | 4 | 0.880 | 0 |
| einstein1 | 1.138 | 0／0／**8** | 8 | 0.906 | 0 |
| curie1 | 0.5 | 0／0／**8** | 8 | 0.908 | 0 |
| scene | 0.333 | 36／**157**／130 | **323** | 0.933 | 0、1、2、5、9、24、25、26 |

人像同样**只在最粗档出锚**（与 v8n 一致，A）；scene 那张三档都出、323 个锚是"还没 NMS"的量级（A，本轮未做 NMS，框数≠目标数）。
- **计时**（A，三连发）：142.1／157.8／141.7 ms → **取 141.7 ms**，同机同线程下比 v8n 的热态 75 ms 贵近一倍。

### 11.4 四件放一起，没有一份后处理能通用（A）

| | `yolov5n.onnx` | `yolov5s_960x512.onnx` | `yolov8n_512x960.pt` | `yunet.onnx` |
|---|---|---|---|---|
| 容器 | ONNX | ONNX | **TorchScript** | ONNX |
| 输入 dtype | **float16** | float32 | float32 | float32 |
| 轴序／形状 | NCHW 640² 静态 | NCHW 512×960 **静态** | NCHW **受限动态**（见 11.2 规则） | NCHW 640² 静态 |
| 输出 | 1 个 [1,25200,85] | 3 个 [1,255,GH,GW] | 6 个 [1,80／64,GH,GW] | 12 个 |
| 数值域 | **已 sigmoid（概率）** | 原始 logits | 原始 logits | 已 sigmoid（`FaceDetectorYN` 直接读） |
| 定位头 | anchor＋obj＋cls | anchor＋obj＋cls | **anchor-free：80 cls ＋ 64 DFL** | anchor＋bbox＋5 kps |

→ 形状、数值域、是否有 obj 支、要不要 sigmoid，四项全都不一样。**"YOLO 后处理"在本项目里必须按件写，不存在一份通用解码**（A）。

### 11.5 本轮的坑与作废（A）

- **v6 那轮 v8n 的输出数值全是"全零输入"下的**：`D:/yzd/qwen3/venv` 里既没有 `cv2` 也没有 `PIL`，探针取不到图就退化成 `torch.zeros` → 于是"÷255"与"0–255"两档输出**逐字节相同**。**那不是"归一化不影响"的证据**，是零除以零还是零（A）。11.2 与 11.3 的真图数字来自 v7：**先用 bench venv 把 letterbox 结果存成 `.npy`，再让 qwen venv 读盘**——这是这台机上跨 venv 传图的唯一可行路（A）。
- **单次计时不作数**（11.2 计时条）。以后在这台机上报延迟一律 min-of-N。
- **ONNX 形态的 `yolov8n` 仍然没有**：要在 PC 侧拿到它，得在她的 venv 里装 `ultralytics` 再导出，**本轮没装**（"不改她机器上的环境"是硬边界）。`bench_yolo.py` 那条兜底分支照样走不到（第一节）。

## 相关页面

- [[音频]] — 上一条音箱记录涉及的那台声卡的实测正本（T1–T27），MCP01 的控件与采样口径全在那边
- [[组件选型与复用边界]] — 这些件的成本／替代基准（CPU JPEG、VAD、jieba 等）
- [[验证方法学]] — 探针隔离、A/B/C/D 判级的方法论
- [[板卡镜像实测取证]] — 板侧图像通路（与本页的 PC 侧是两条链）
- [[NPU调用链]] — 同一批模型搬到 ZG330 时，检测后处理落定制算子的口径
- [[1-NPU模型部署]] — 第十一节这两件在 NPU 侧的编译台账（主 v8n／备 v5s，D-30）
- [[板端我方代码与产物台账]] — 两件正本的下游编译产物（v8n 的 ZG 档、板上现役 `yolov5s_plin_960x512_ZG`）登在这里
- [[状态源与决策记录]] — D-46（MediaPipe 路线判废）与 D-30（v8n 主／v5s 备）两条决定
- [[校机无容器交叉编译]] — 这台机的远程入口与工具链实况
