---
tags: [index]
---

# repo项目索引

本页索引 `repos/` 子仓库下的项目目录。**2026-11-03 重建**：`repos/` 已重组为三类——**本仓自有项目**（顶层）＋`official/`（`repos/official/`，厂商 kit 快照）＋`unofficial/`（`repos/unofficial/`，民间）。**2026-11-04 二次重组**：`asr/`、`llm/`、`tts/` 收进 `repos/lang/`（按语言域分组，另设 `lang/tool/` 放跨域工具），`tts4fpai/` 同日改名 `tts/`，`funasr/`（asr_chain）压平并入 `lang/asr/`。`工程解读/` 同日（11-03）从 `repos/工程解读/` 移入本目录并按 repo 拆分（见末尾）。项目目录的存在不表示其工具链、构建或板端状态当前可用；逐项验证范围见各自 README 和记录。

## 本仓自有项目

本仓在做的交付与实验：`lang/`（asr／llm／tts／tool 四个语言域）＋顶层其余项目。其中 `ekho-linux`、`HA4FPAI`、`ERNIE-4.5-0.3B-PT4icraft430tai` 是 Git 子模块（见 [[状态源与决策记录]] 与 `.gitmodules`）。

| 项目索引 | 仓库目录 | 内容 |
|---|---|---|
| [[ekho-linux]] | `repos/lang/tts/ekho-linux/`（子模块） | Ekho 开源 TTS 引擎的 Linux 专版 fork；文档已迁 `PS/Backend/` |
| ERNIE-4.5-0.3B-PT4icraft430tai | `repos/lang/llm/ERNIE-4.5-0.3B-PT4icraft430tai/`（子模块） | ERNIE-4.5-0.3B 推到 ZG330 `_ZG` 件并上板（门 4 已通） |
| [[FPAI30TAI图像FPGA索引]] | `repos/FPAI30TAI图像FPGA/` | 悟净 FMQL30TAI 图像 PL／ModelBackend／PS-NPU：视觉前端 RTL＋PS／网页链路 |
| [[PS/ha/oldmainchain/Backend/funasr]] | `repos/lang/asr/`（2026-11-04 由 `repos/funasr/` 改名 `asr_chain`、收进 `lang/` 并**压平**：`funasrarm/asr/` 与 `asr_chain.py` 提到顶层） | 顶层＝`asr_chain.py`＋`selftest.py`＋板端入口 `funasr-lite`／`funasr-onnx`；`asr/`＝板端链路件（backends、起链脚本）。`asr_chain.py` 采集→VAD→ASR→TTS，**在跑的 Python 链路**。⚠ 本行旧描述「C++ 链路规划，代码零行」与实际不符（D-78 的 C++ 规划是另一件事，待核清后拆行）；**旧 PC 侧 `.bat`＋venv 变体（原 `funasr/`）已丢弃**（她 2026-11-04 裁，D-1793752728；原件在 repos 仓 HEAD 里仍可取回） |
| HA4FPAI | `repos/HA4FPAI/`（子模块） | 悟净板上语音控制栈：klar-ha-nlu（NLU）＋sherpa-onnx |
| num-audit | `repos/num-audit/` | 交付物数字错误的外置门禁工具（非零退出，A1/A2 复算） |
| Qwen3-0.6B-Instruct | `repos/lang/llm/Qwen3-0.6B/`（目录真名 `Qwen3-0.6B`；交付线名沿 D-62） | Qwen3-0.6B 推到 ZG330 `_ZG` 件（NPU 迁移交付线） |
| sdi-psddr | `repos/sdi-psddr/` | SDI 到 PS／DDR 采集参考工程（sdi-cap 工程本体＋收档快照） |
| sdi2hdmi | `repos/sdi2hdmi/` | FMQL30TAI 纯 PL 的 SDI→HDMI 转换器（720p60，3 个 MMCM） |
| [[tts4fpai]] | `repos/lang/tts/`（2026-11-04 由 `repos/tts4fpai/` 改名 `tts/` 并收进 `lang/`；神经系组件收在 `sherpa/` 子目录，VITS 候选在 `sherpa/VITS/`） | ZG330 中文 TTS 可复现内容（前端/mel、matcha、vocos、HiFi-GAN、piper、ekho-linux、CPU 基准） |
| vpu-live | `repos/vpu-live/` | 板侧 VPU 视频编码与直播链路（H.264 泵＋HLS 打包） |
| [[yuanma索引]] | `repos/yuanma/` | 竞赛提交快照包（2026-11-03 冻结，4481 件带 SHA-256）：源码工程＋冻结 DCP/BOOT＋板端运行配套＋复现脚本与逐项校验 |
| fmql30tai-sdi-npu-face-recognition | `repos/fmql30tai-sdi-npu-face-recognition/`（子模块，公开仓 `WCIS-Team/fmql30tai-sdi-npu-face-recognition`，分支 `main`） | 视频交付工程公开形态（SDI 采集＋NPU 人脸身份/PAD）。**原作者 `anxianji11-pixel`，`takomitkm` 代上传**；署名正本见该仓 `NOTICE.md`。三组织库重建根历史后的贡献视图补记口径见 [[状态源与决策记录#D-1794150604 · 视频链路原作者署名以新提交补记，不改写重建后历史|状态源与决策记录——D-1794150604]] |

> **子模块署名口径（2026-11-08）**：上表 `fmql30tai-sdi-npu-face-recognition` 一行是**代上传**关系，不是本仓原创；本仓只钉 gitlink，不含其源码。视频链路源码从未搬进重建后的三个组织库——2026-11-06 新根 `d191810`／`f07c4e8`／`d7be1d` 都是 `Initial clean snapshot`，作者字段只有 `takomitkm`，而视频子模块仓自身历史不在重建范围内（D-1793967893）、署名完好。因此旧历史里 `anxianji11-pixel` 对视频链路的提交只在本机 `workenv/history-reset-20261106/backup/` 的 bundle 里，未回推公开仓库。详见 [[状态源与决策记录#D-1794150604 · 视频链路原作者署名以新提交补记，不改写重建后历史|状态源与决策记录——D-1794150604]] 与主库 [`作品提交/fmql30tai-sdi-npu-face-recognition.md`](https://github.com/WCIS-Team/WCIS-FPAI/blob/main/作品提交/fmql30tai-sdi-npu-face-recognition.md)。

## official/（厂商 kit 快照，`repos/official/`）

厂商 kit，只留源码与文档；公开评测集本体、示例 io/数据、编译产物（`*.ftmp`/`*.snapshot`/`*.edif`/`*.edf`/`*.padr`）、预编译二进制与 Vivado 生成物一律不入库（判据见 `official/README.md`）。

### 官方 demo（`official/demo/`）

> 这两个（`Icraft-ModelZoo-yolov5`、`03_图像分类部署示例工程`）是旧索引里登记过的官方 demo；`llm_frontend_cpp` 同目录，一并列出。

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `03_图像分类部署示例工程 image_cls_resnet18` | `repos/official/demo/03_图像分类部署示例工程 image_cls_resnet18/` | ResNet18 图像分类：训练→导出（`.pth`/`.onnx`/`.torchscript`）→三格式推理；工程解读见 [[训练与模型结构]]／[[部署链路与iCraft衔接]] |
| `Icraft-ModelZoo-yolov5` | `repos/official/demo/Icraft-ModelZoo-yolov5/` | Icraft/FPAI YOLOv5 示例工程（BIT／BOOT_Gen／fpai_demo_app／fpai_demo_fpga） |
| `llm_frontend_cpp` | `repos/official/demo/llm_frontend_cpp/` | 纯 C++ Qwen2.5-7B-AWQ 在 WL170 NPU 推理＋OpenAI 兼容服务；工程解读见 [[纯C++Qwen2.5-7B推理服务]] |

### `official/benchmark/`

ICraft 工具链精度评测仓库：按任务组织各网络类型的常见指标评测脚本与测试数据（检测 mAP、实例/语义分割、多目标跟踪 MOTA、超分 PSNR、关键点等），并配 ModelZoo Benchmark 前端筛选页。

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `benchmark` | `repos/official/benchmark/` | 精度评测集合（检测/分割/MOT/超分/关键点/PSNR/全景/像素误差/TopN 等子目录） |

### `official/fpai_reference_design/`

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `fpai_reference_design` | `repos/official/fpai_reference_design/` | FPAI 芯片＋iCraft 嵌入式 AI 参考工程：`examples/`（0_datapath／1_single_input+ai／2_pcie_hostin+ai／3_multi_inputs）、`tools/`、`skills/` |

### `official/tutorial/`（iCraft 教程与 runtime demo）

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `demo_for_icraft_by` | `repos/official/tutorial/demo_for_icraft_by/` | icraft BY（100TAI）后端示例：编译／Python／C++ 快速上手 |
| `demo_for_icraft_wl` | `repos/official/tutorial/demo_for_icraft_wl/` | icraft 3.39 / WL170（400TAI）后端 YOLOv5 部署示例（多 net／多 core／多 batch） |
| `icraft_tutorial` | `repos/official/tutorial/icraft_tutorial/` | icraft 3.39 使用教程（WL170／400TAI：环境／编译／运行） |
| `runtime_demo_for_icraft_zg_cpp` | `repos/official/tutorial/runtime_demo_for_icraft_zg_cpp/` | 直调 iCraft runtime 的 C++ YOLOv5 推理 demo（socket／axi，build_win＋build_arm） |
| `runtime_demo_for_icraft_zg_py` | `repos/official/tutorial/runtime_demo_for_icraft_zg_py/` | 直调 iCraft runtime 的 Python YOLOv5 推理 demo（socket／axi） |
| `tutorial-model_export` | `repos/official/tutorial/tutorial-model_export/` | 多框架（MMLab／Detectron2／timm／PaddlePaddle）模型导出与修改示例 |
| `yolov5_demo_for_icraft_zg` | `repos/official/tutorial/yolov5_demo_for_icraft_zg/` | YOLOv5 在 30TAI（ZG）编译＋部署端到端示例（c++/python，win/ubuntu） |

### `official/Nuscenes_v1.0-mini_subset/`

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `Nuscenes_v1.0-mini_subset` | `repos/official/Nuscenes_v1.0-mini_subset/` | nuScenes v1.0-mini 子集：为 StreamPETR 测试抽取 33 篇图片样本并预处理成 pkl |

> 本目录（`official/`）另有 `README.md` 作为厂商 kit 索引与入库口径说明；`Multi_Agent_Collaboration` 在 `official/README.md` 中标记为未拉取（需登录），不在本表。

## unofficial/（民间，`repos/unofficial/`）

| 项目 | 仓库目录 | 内容 |
|---|---|---|
| `fm33g026-rtc-demo` | `repos/unofficial/fm33g026-rtc-demo/` | 复旦微 FM33 资料借鉴产物：RTC 寄存器→SVD 抽取与三源对齐（netlist／手册／ws） |

## 工程解读（从 `repos/` 移入，按 repo 拆分）

2026-11-03 从 `repos/工程解读/` 移入本目录并重组：**一份解读对应一个 repo**，目录结构即 `工程解读/<repo>/`。

- [[00-总览与阅读地图]]：三个工程（image_cls_resnet18／FPAI30TAI／llm_frontend_cpp）的关系与阅读地图
- [[训练与模型结构]]／[[部署链路与iCraft衔接]]：`official/demo/03_图像分类部署示例工程 image_cls_resnet18`
- `repos/FPAI30TAI图像FPGA` 的解读已按组件重写并移至 [[FPAI30TAI图像FPGA索引]] 所在目录的 `组件设计/`（入口 [[组件总览与阅读地图]]）；旧四篇（平台总览／自研RTL／PS软件／事故时间线）已删除，其设计内容并入组件页，事故与踩坑仍以仓库 `docs/` 一手记录为准
- [[纯C++Qwen2.5-7B推理服务]]：`official/demo/llm_frontend_cpp`

## 相关参考资料

- [[魔改厂商视频流程部署记录]]
- [[SDI到PS的数据搬运（厂商参考与设备事实）]]
- [[SDI转HDMI转换器]]

## 索引口径

- 本页链接按页名解析（CONTRIBUTING 规定 `[[页名]]` 不带路径；`check-md.py` 也只按页名解析，写路径会判 unresolved）。仓库目录列写的是真实 `repos/` 路径。
- `ekho-linux`、`HA4FPAI`、`ERNIE-4.5-0.3B-PT4icraft430tai` 是配置在父仓库中的 Git 子模块；其余项目以 `repos/` 内的目录组织。
- 工程解读页随 `repos/` 重组已更新工程位置路径（`official/demo/...`）。数字与结论以各项目一手 README／docs 为准，本页与各解读页只做定位与摘要。
- 项目仓库远端为 [WCIS-FPAI-repos](https://github.com/takomitkm/WCIS-FPAI-repos/tree/master/)。
