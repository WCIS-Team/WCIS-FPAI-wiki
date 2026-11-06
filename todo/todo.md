网页在ps接渲染到hdmi，可用鼠标操作做终端机
我想写逻辑调度，有没有语言，在测试的时候可以做脚本语言，很方便的。手感，并且逻辑固化没问题的。我可以让把它编译，让它获得高性能。

- 不是绝对必须，PL 直接上网有三种现实路径：① 在 PL 里实例化软 MAC（AXI Ethernet/TEMAC），[Xilinx Wiki — Zynq PL Ethernet](https://xilinx-wiki.atlassian.net/wiki/pages/viewpage.action?pageId=189628488) 给出完整 PL 侧以太网（AXI Ethernet + AXI DMA）方案；② 用硬件 TCP/IP 卸载栈 IP，如 [CAST TCP/IP 1G/10G 全硬件协议栈](https://www.cast-inc.com/interfaces/internet-protocol-stacks/tcpip-1g10g)（无需 CPU）、[ETH Zurich 开源 fpga-network-stack](https://github.com/fpgasystems/fpga-network-stack)（纯硬件 TCP/RoCEv2）；③ 只做 UDP 的纯 RTL 收发（[电子栈讨论：FPGA 上实现最小化 TCP/IP](https://electronics.stackexchange.com/questions/585679/minimalistic-tcp-ip-implementation-on-fpga)，社区共识是 TCP 子集可行、完整 TCP 很重）。
- 但"走 PS"仍是常规选择，理由有二：① Zynq-7000 的硬以太网控制器 GEM（含 MAC）在 **PS** 里——EMIO 只是把 PHY 接口信号布线进 PL，MAC 仍在 PS；只有 AXI Ethernet 才是真 PL 侧 MAC。来源：[Xilinx Wiki — PS and PL based Ethernet in Zynq](https://xilinx-wiki.atlassian.net/wiki/pages/viewpage.action?pageId=70156399)、[Zynq-7000 GEM 介绍](https://www.embedic.com/technology/details/introduction-to-the-zynq-7000-gigabit-ethernet-controller-)；② AMD 官方答复明确说 TCP 的复杂度通常应交给处理器来做（[Does FPGA support TCP/IP?](https://adaptivesupport.amd.com/s/question/0D52E00006hpkS4SAI/does-fpga-support-tcpip-protocol?language=en_US)），PS 上有 lwIP/完整 socket 栈，发 HTTP 请求到 API 成本极低。
- 结论：PL 直传"能做但贵"——UDP 组包直发最轻，TCP/HTTP 建议买 TOE IP 或交给 PS；PL 收好数据经 DMA 送 PS、由 PS 调 API，是最省力的成熟架构（与备忘录里的直觉一致，只是"必须"二字不成立）。

emmc实际上支持dma但是pio够用了

平常不弄人脸识别只物体识别到人就开始录制
虹膜识别 多摄像头
声音喊出 人脸防伪 五点确认3d正面侧面 当成不同人脸重新确认 三色识别
接图像生成或live2d
sdi接HDMI还在不，这是离线展示
把知识库"AI 算子与 NPU 加速"那套 AMD Versal AIE / XRT / PLIO / GMIO删掉，我这个WCIS用不上的FPGA知识都删掉
S:\work\WCIS\wiki\PL\FPGA\FPGArt\Procise手册Markdown 引脚约束 I/O Planning、Timing Wizard、Set Up Debug 向导、编程下载 Chain 配置这几处手册只给了 GUI 操作，没有等价 tcl；做全 headless 时需要用它们产出的 `.fdc`、`mark_debug.json`、`.bit` 文件来衔接，指南第 10 节列了这些边界。补充 Procise_Headless无GUI操作指南.md,procise在我桌面有快捷方式
UTC 时间戳的 0 对应 1970 年 1 月 1 日 00:00:00 UTC。 重排 D- 改为按照时间记录，避免与协作者冲突导致git合并出错
校机测试把cpu核和频率限制在和开发板一个
技术文档：需求文档上叠 EARS，文档走 prose 闸门，CI 里跑 Vale。 0基础用户手册：asd-ste
可以加入导盲系统和路障等等，做成一个车机系统
S:\work\WCIS\source\ProciseDocuments ， icraft你在wiki和Gitee上找
一定要走HTTP POST吗，有木有更省资源的数据传输方法，funasr内部组件之间怎么传数据的呢

找门锁同类对比一下

    [ ] 人脸、OCR 和 VLM 路径各自需要的目标尺寸与颜色顺序
- [ ] 麦克风实际采样率、位宽、声道数，以及 ASR 输入格式
      
自己定义"某段音频 = 某个词"？热词

先定位问题：早八点那节课，同一句话每次识别成不同的词（人名、术语），改不完。三个层次，按性价比排序：

都不出对的词"的那几个。
[[ASR CPU-only Benchmark SOP#3.2 家居语音 ASR|自建家居指令音频集]]
- 555 个 md 里带 frontmatter `tags:` 键的**只有 1 个**：`PL/MOD/modellist/…/model_cards/AIBS__ShuffleNet.md`，值是 `- image-classification`。它在 `modellist` 原料目录里、**根本不进站点内容集**，所以线上索引 124 条 `tags` 全空。

| 层                     | 做法                                                                                                                                                                                                                                                | 什么时候用            | 代价              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | --------------- |
| ① **事后术语纠错**          | 照常转写，再用自建的术语词典做模糊替换（拼音 + 编辑距离，如 `rapidfuzz` + `pypinyin`）。**错一次往词典加一条**，映射从此稳定可复现，不存在"替换不完"                                                                                                                                                       | **先上这一层**，收益最大   | 只需要一张词典表；离线可跑   |
| ② **约束识别**            | 把候选限制在给定词表内。本地能跑的：sherpa-onnx 的 hotwords / contextual biasing（中文 zipformer 模型齐全，**注意它是加权提升，不是硬约束**）；Vosk 支持 context / 受限 grammar。要"只允许输出这几个词"就走命令词／唤醒词路线：sherpa-onnx KWS、openWakeWord（给文本 + 少量样本即可训自定义词）、Picovoice Porcupine（按文字定义关键词，**商用要买授权**） | ①补不住的词           | 工程量大一档；授权要单独核   |
| ③ **小样本模板匹配**（不做 ASR） | 用说话人／语音嵌入模型（WeSpeaker、3D-Speaker 的 ECAPA 类 embedding，或 whisper encoder 帧特征）给每段参考音频存一个向量，新片段按余弦相似度最近邻判决。改词只需重录参考音频                                                                                                                                 | 只留给"怎么都不出对的词"那几个 | 几十条短指令够用；不是通用识别 |

**建议顺序**：① 先上 → ② 用 sherpa-onnx 热词补齐 → ③ 只留兜底。

**与本项目的关系**：我们的 ASR 备选是 CitriNet-CTC → Zipformer-CTC → 云端（[[组件选型与复用边界]]）。第 ② 层的 sherpa-onnx 恰好就是 zipformer 族，**热词接口是同一条路**，所以这条经验可以直接进 ASR 卡的判据；第 ① 层则是纯 CPU 后处理，**不需要 NPU**，是本项目的可落地项。**当前证据等级 E0（讨论），未在任何模型上实测。**


tts要么piper要么ekho
ASR 是整个方案最薄的一环，比 wiki 里预期的差很多。 whisper 不支持（-inf 算子）；SenseVoice 在 100 平台是"算子不支持+编译bug+运行bug+速度慢"；SenseVoiceSmall_axi 已入库但"int8 量化精度差"且只标 100；conformer 同样"int8 精度差"；Paraformer 台账里根本没有条目；qwen2-audio 不支持。TTS 侧 fastspeech2 / tacotron2 / hifigan / CosyVoice1/2 全部不支持——语音合成别指望 NPU，你 wiki 里"云端 TTS + 拼音拼接兜底"是唯一可行路线，这个判断是对的。

人脸识别零记录。 台账里没有任何 MobileFaceNet / ArcFace / face 相关条目（最接近的 strongReid 是行人重识别，且只有 100 平台）。这不是"候选待验证"，是从零自己导 ONNX + 自己趟算子，工作量和失败率都要重估。
OCR 只有识别没有检测。 CRNN 能落地，但 DBNet / PSENet / FCENet 全是"待入库、速度慢、仅 100 平台"，SVTR"算子不支持"，CRNN_Chinese 备注"8bit 可运行，16bit 内存爆炸，可用 argmax 硬算子优化"。文本检测的投影/连通域/ROI 后处理落到 CPU 或 FPGA——这恰好是 FPGA 能加分而不是减分的地方。
Qwen2-0.5B 是"已入库、速度慢"，用的是单独的 3.33.1-llmgenai 分支工具链（本地 3.39.0 包里没有 llm-genai 包，得向厂商要），且 PS DDR 只有 1 GB、bootargs mem=1024M 改不动，0.5B INT8 权重 + KV cache + runtime 在 1 GB 里非常紧。建议把本地 LLM 从主线降级成可选演示项。

顺带拿到一份算子黑名单（改网络的判据）：ScatterND、GridSample（3.7 已在 xir 注册但未正式并入）、Gather/GatherND、floor_divide、cumsum、arange、ne、reciprocal、unbind、tensor 相除的 div/pow、conv1DTranspose 与分组反卷积、ConvTranspose3d、ROIAlign、MaxUnPool、FFT/复数。另外 opset=11 会让 parser 报错，统一用 opset≥15。

现在就做的事，按优先级
装 ICraft 3.39.0 + CustomOp（04_ICraft\v3.39\icraft_v3.39.0\，注意 v3.36.1 别混用；Python API 只支持 3.8）。
跑通 08_FMQL30TAI开发教程资料\03_图像分类部署示例工程\image_cls_resnet18.zip（354 MB，含 train/model/onnx/torchscript/onnx_infer.py/img2ftmp.py/predict + 3312/370 张数据）。这就是每个模型的模板工程；img2ftmp.py 定义了 NPU 输入张量的字节格式，FPGA 视觉前端的验收标准就是逐像素对上它。
同一套流程把 yolov8n 编译到"C++ 仿真通过"——主模型先落地，算子问题在没有板子的压力下解决。
写视觉前端 golden model（resize / letterbox / 色彩转换 / normalize / INT8 定点量化，用 Q 格式手写而不是浮点近似）+ 测试向量；写音频前端 golden model（分帧、能量 VAD 状态机、可选 48k→16k FIR）。这两块没板子也能全部完成并自检，RTL 一到位直接对拍。
读 CustomOp_Setup 里的 DetPost / DetPostZG / GridSample / WarpAffine / NearestUpsample 头文件——先确定后处理哪些留在 NPU 硬算子，再决定 FPGA/CPU 的分工，否则 RTL 边界是猜的。
CPU 侧纯软件全部先写先测：意图路由状态机、身份库 cosine 检索与权限逻辑、云端 API 抽象层（三家可切换 + 断网兜底）、pypinyin 音节拼接 TTS 样音、V4L2/ALSA 设备参数探测脚本（顺手回答 wiki 里"摄像头实际格式""麦克风采样率"两条待验证项）。
交叉编译环境：07_交叉编译环境\02_Docker镜像\ubuntu20.04_container.tar（781 MB，厂商明确说 VM 方式不推荐）+ IcraftMdzThirdParty.deb（ModelzooDeps/aarch64/{Dynamic,Static}，自带 yaml-cpp 和静态 OpenCV4，就是板上 demo 的 C++ 依赖）。
攒离线 bundle：Icraft_3.39.0_onchip.deb、CustomOp_3.39.0_onchip.deb、aarch64 icraft wheel、torch_v2.0.1_aarch64.zip 和上一轮脚本的 apt 包一起下载好。板子到手时插网线之前就能装完。

三个要立刻发问的（今天就发，别等）
04_ICraft\v3.36.1\FMQL30TAI参考实现\悟净开发板\ 下两个空文件夹：单路PLIN+pHDMI(外置detpost)参考实现、单路PLIN+VPU编码_MIG_axi接口(外置detpost)参考实现。里面正是 PL 视频输入 / HDMI 输出 / AXI / DMA / DDR / 位流加载的完整 PL 工程，对应 wiki 第八条最关键的待验证项。要文件，不给就要目录树截图。
07_交叉编译环境\03_自行搭建环境 也是空的，要文档。
要 icraft-llm-genai 包 + 30 平台各模型的 yolov8_time.md / yolov8_metrics.md 实测报告原文。




### 1.2 功能边界类

| # | 限制 | 用户可见表现 | 本周期是否解决 |
|---|---|---|---|
| L6 | **身份事件触发什么业务动作未确定**——"开门／开放权限"只是示例 | 认证只会给出"通过／拒绝"的判定，不会真的控制某个设备 | 不确定，属 `待验证` 项 |
| L7 | **声纹认证为 P2 可选**，不列为必做 | 只用声音（背对摄像头）时无法确认身份 | 不承诺；方向保留 |
| L8 | 端侧小语言模型只承担**简单、不需联网**的问答 | 复杂推理、写作、知识密集型问题必须走云端 | 是，这就是设计分工 |
| L9 | 本地模型的中文回答质量与长度上限未测 | 回答可能简短或不完整 | `待实测` |
| L10 | 首版文字识别为轻量方案 | 大字号、单栏、平整纸张效果好；多栏、表格、手写、倾斜反光的场景不保证 | 完整版为后续升级项 |
| L11 | **未定义活体检测／防伪** | 用照片或视频对着摄像头可能被误判为本人 | 不在当前范围，见 FAQ Q8 |
| L12 | 身份库容量、注册流程、多人同框未定义 | 演示前需人工预置名单 | 待定义 |
| L13 | 无自动重拍／自动重试策略 | 没读清就要人工调整距离角度再问一次 | 不在当前范围 |
| L14 | 不承诺多人并发、长时间无人值守 | 面向单人近距离交互 | 不在当前范围 |
| L15 | **端侧不做语音增强／降噪**：嘈杂环境里"把语音先洗干净再识别"这条路本周期不实现 | 噪声大的会场里识别率会直接掉下来，设备不会先替你修音；只能走近、降低环境噪声，或改走云端识别 | 不解决。厂商逐模型实测表已把语音增强类模型判为不支持（依据见 [[状态源与决策记录]] D-19），因此它从未进入候选清单 |

### 1.3 范围外（明确不做，别期待）

| # | 项目 | 口径（以状态源为准） |
|---|---|---|
| O1 | 连续视频流编码（H.264／H.265） | 不做。需要理解画面时只拍**一帧** |
| O2 | 硬件图像压缩 | **不在本周期自研范围**。按需抓帧的压缩由设备侧软件完成 |
| O3 | 硬件语音合成后端 | **不在本周期自研范围**。播报＝云端合成为主 + 离线拼音音节拼接兜底 |
| O4 | 网络协议卸载 | **不在本周期自研范围**。走系统标准网络栈 |
| O5 | 自定义硬件算子补 NPU 缺口 | **不是预设必做项**，只有实测发现值得硬件化的瓶颈后才评估 |
| O6 | 用硬件重写 OCR／人脸／语音／语言模型 | 不做，这些交给加速单元跑现成模型 |
| O7 | 继续扩张新功能 | 不做。当前优先把已有双链路做成可验证、可上板、可测性能、可解释的完整系统 |

### 1.5 性能类：全部待实测

| 指标 | 状态 | 说明 |
|---|---|---|
| 说完停顿到开始播报的端到端时延 | `待实测` | 依赖到板 |
| 语音识别响应速度 | `待实测` | 依赖模型能否跑通 |
| 画面分析帧率 | `待实测` | 依赖摄像头实际格式与目标尺寸 |
| 硬件通路与软件通路的性能对比 | `待实测` | 测量方案已定（同一功能两条通路分别测），数据未产生 |
| 连续运行稳定性时长 | `待实测` | 长跑判据的目标小时数在开发侧仍是空格 |
| 身份认证误识率／拒识率 | `待实测` | 需测试集与统计口径，尚未定义 |
