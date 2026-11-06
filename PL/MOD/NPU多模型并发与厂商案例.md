# NPU多模型并发与厂商案例

> **本页回答什么问题**：能不能让好几颗模型同时在悟净（ZG330）的 NPU 上跑——LLM 与小模型（YOLO 一类）分开判，每档的判据是什么，厂商有没有现成案例，案例在哪、拿不拿得到。
> **判据等级**：A＝实测读数（引台账／取证页原文）／B＝厂商文档或官方仓库原文／C＝按已知比例外推／D＝没有任何读数。
> **一件事说在页头**：**我方到目前为止，板上一次只跑过一颗模型**。所有"多模型"结论都是账面推算＋厂商案例，没有任何一条是我方自己跑出来的。这句话是引用的前提，别被下面的表格冲淡。
> **分工**：内存与 CMA 的机制正本＝[[NPU调用链]]第七节；板上产物与 md5＝[[板端我方代码与产物台账]]；LLM 那一档的四道门＝[[LLM上板要求与候选模型对照]]；本页只做"多模型"这一个问题的判定与案例登记，不复制那些读数。
> 参考批次：2026-10-21 成文（会话盘点结论），2026-10-30 按当时的实况校订（Qwen3 件已拷板、已过 `apply`，见[[板端我方代码与产物台账#十四、Qwen2-0.5B 上板（2026-10-11，本机编译＋板上只部署）|板端我方代码与产物台账——十四]] 之后的 Qwen3 登记行）。

## 一、TL;DR

| 组合 | 判定 | 一句话理由 |
|---|---|---|
| **两个 LLM 同时跑** | **fp16 下物理放不下**（可直接下结论） | 权重各自住在 PL DDR：Qwen2 占 61.2%、Qwen3 占 74.7%，两颗超过 100%；CMA 与 PS 匿名页也各差一份 |
| **LLM ＋ 小模型** | **纸面勉强、实测零读数** | PL DDR 剩 25% 能不能装下 INSTR＋FTMP＋KV，本来就登记为未测开口项；CMA 上 LLM 与视频链"不能同窗"已是 A 级纪律 |
| **多颗小模型（多 YOLO）** | **技术上可行，且厂商有现成案例** | 单件 MB 级、PL DDR 十几颗都装得下；ZG int8 中位 12.84 ms/帧，30 fps 的帧预算里分时跑两颗有富余 |
| **“同一瞬间两个推理都在飞”** | **D 级——零读数** | 两条链用户态 mmap 同一物理窗口、内核无互斥；zg330backend 单设备多 session 并发从未验证 |

**答辩口径提醒**：README 架构那句"NPU **并行**运行语音识别、目标检测、人脸识别与 OCR"目前没有任何多会话读数背书，实测口径一直是"同一时刻只能有一个"。有证据的说法是"**NPU 分时运行多模型，FPGA／CPU／NPU 三级流水并行**"。

## 二、三本账：多模型到底受什么约束

每次推理，东西落在三处（机制正本＝[[NPU调用链#七、PS 侧内存与 PL 侧内存的分层（2026-10-15 新增，答"权重到底驻在哪里"）|NPU调用链——七]]）：

| 账本 | 容量 | 单模型已实测占用 | 多模型时的算术 |
|---|---|---|---|
| **PL DDR**（权重与图张量的家） | 手册口径 2 GB（B） | Qwen2 1.224 GiB＝61.2%（跑通，A）；Qwen3-0.6B 1.493 GiB＝**74.7%** | 两颗 0.5B 级 LLM＝136% 起步 ⇒ **放不下**；十几颗 YOLO（单件 6～10 MB）⇒ 无压力 |
| **CMA 池**（PS↔PL 中转，`udma`） | 256 MiB（`CmaTotal 262,144 kB`，A） | 一轮 Qwen2 推理吃掉 **≈122 MB**（`CmaFree` 130,784→8,860 kB，A）；视频直播链同池，跑起来时实测只剩过 **15 MiB** | 两轮 LLM 并发≈244/256，加任何第三者即爆；小模型的中转是 MB 级 |
| **PS RAM**（驱动进程匿名页） | 993 MB 里匿名页额度 700～825 MB | Qwen3 驱动侧 ≈245 MiB；板上另有 387 MiB 的 ASR python；历史 **12 次 OOM** 全死在同一内核水位（A） | 每多一个模型驱动就多一份同量级占用 |

两条硬约束，任何多模型方案都绕不过：

1. **没有任何内核互斥**：两条链都是用户态 `mmap` 同一片物理窗口（`0x40000000`／`0x80000000`）加 `/dev/udmabuf0`，**并发没有保证**（[[板端我方代码与产物台账#三、编译侧本体（不在板上，但板上那份是它们编出来的）|板端我方代码与产物台账——三]] 的既有口径）。台账里"都要用 NPU，同一时刻只能有一个"就是这么来的。
2. **PL DDR 易失**：每次起 session 都要把权重整个重放一遍（Qwen2 的 `apply()` 实测 **132.1 s**，A）。所以"时间分片轮换模型"不是秒级切换，是**分钟级换装**——LLM 尤其贵。

## 三、"同时"要拆成两档说（这两档的判定完全不同）

- **档 A：同进程建多张图、分时轮推**（帧 1→模型甲，帧 2→模型乙）。厂商的多模型 demo 就是这一档，**有活证**；icraft 的 API 面也留了口子（`Network::CreateFromJsonFile` 是 Network 级方法、`getDepolySize` 的注释写"获取 **session** 在 etm 占用的总内存字节数"）。
- **档 B：两个推理在同一瞬间都在 NPU 上飞**。**D 级**，零读数。判它之前先要回答：单设备多 session 是否受支持、硬件队列是否真并行。这两问只有厂商能给。

**别把档 A 的活证当成档 B 的证据**——这是本页最容易被误引的一句。

## 四、小模型那一档：厂商有现成案例（含链接与活性）

以下是 2026-10-21 逐个拉取原文核过的（B；链接活性用云端抓取验，本机 curl 直连 ModelScope TLS 握手失败、代理也不通）。

### 4.1 主案例：`AIBS/fpai_reference_design`（公开，Apache-2.0）

- 主页 <https://www.modelscope.cn/models/AIBS/fpai_reference_design>
- 文件树 <https://www.modelscope.cn/models/AIBS/fpai_reference_design/files>
- 取件用官方工具：`git clone https://www.modelscope.cn/AIBS/fpai_reference_design.git` 或 `modelscope.snapshot_download('AIBS/fpai_reference_design')`（**注意 Git LFS**）。

README 支持矩阵里，对我们这颗 **ZG（30TAI／ZG330）标 ✅** 的多模型示例有两个，都在 `examples/3_multi_inputs/`：

| 示例 | README 原文要点 | BY | ZG |
|---|---|---|---|
| `MultiPLin+MultiNets+VPU` | **多路 SDI → 多 YOLOv5 → 多 VPU；一个 NPU scheduler 调度，BY 通常 4 路、ZG 通常 2 路**，物理端口在 YAML 中指定 | ✅ | **✅** |
| `MultiWebcams+MultiNets+VPU` | 双路 RTSP → 多 YOLOv5 → 文件／Print／RTSP；**单核 NPU 调度** | ✅ | **✅** |

`examples/3_multi_inputs/` 目录树现读只有四个示例（`MultiPLin+MultiNets+VPU`、`MultiPLin+SingleNet+VPU`、`MultiPSin+SingleNet+VPU`、`MultiPSin+MultiNets+Save2File`、`MultiWebcams+MultiNets+VPU` 五选四——以文件树 API 返回为准，共四个 tree 项）＋`0_datapath`／`1_single_input+ai`／`2_pcie_hostin+ai` 三个兄弟目录。

**关键结论**：多网络调度是**软件层**做的（"一个 NPU scheduler"），`initialize_npu` 里加载 Network、拆图、建多个 Session——这正是"多颗 YOLO 挂 NPU"的官方答案，**不用自己猜 API**。

### 4.2 官方双 YOLO 裸机案例（100TAI 布衣档，开放制）

- <https://www.modelscope.cn/models/AIBS/yolov5_dual-network_pipeline_bare-metal>

README 原文："YOLOv5 **双网络流水线（GIC 中断驱动的并行流水）**"；含 IAR 裸机工程＋SD 卡启动件＋`save_snapshot.py`（脚本里就是"1、2 两个 network"的设置）。芯片不是我们的，但**双网络怎么组织**是权威参考。

### 4.3 同档但申请制的两个（zg-30t）

- 多智能体协同：<https://www.modelscope.cn/models/AIBS/Multi_Agent_Collaboration>（zg-30t、完成、**申请制**）
- 无人机野外飞行：<https://www.modelscope.cn/models/AIBS/flightmare_pipeline/summary>（zg-30t、单路、申请制）

### 4.4 案例与"方案表"的对应

[[解决方案汇总.xlsx - sln列表]]（厂商方案表 80 条）里，同名案例在两档位流下都标"完成"：

| 方案表条目 | 芯片 | icraft | 位流版本 | 数据通路 | 状态 |
|---|---|---|---|---|---|
| 多模型多PLIN输入demo | **zg-30t** | 3.33.1 | **25122301** | 多路-base | **完成** |
| 多模型多PLIN输入demo | by-100t | 3.33.1 | 25060601 | 多路-base | 完成 |
| 2路plin 单模型多输入（CFT／MISO） | by-100t | 3.33.1 | 25060601 | 多路-base | 完成 |
| 2路psin 单模型多输入 | by-100t | 3.33.1 | 25060601 | 多路-base | 完成 |

## 五、三个要先知道的坑

1. **位流缺口（最要紧）**。`fpai_reference_design` README 文末"位流汇总"里，**30TAI(ZHUGE) 只挂了单路两款**（单路PLIN+VPU编码_MIG_axi、单路PLIN+pHDMI，均 ver 25122301）＋PCIE 标 TODO；"多路PLIN+两路网络摄像头""多路PLIN+VPU编码"只列在 **100TAI** 名下。而方案表给 zg-30t 的多模型 demo 标的是 25122301。
   ⇒ 两种可能：多网示例能跑在单路位流上（多模型调度在软件侧，多路更多是 SDI 输入侧的事），或需要一份厂商还没公开的多路基位流。**这一条不确认，别说"我们能跑多模型"**。
   ⇒ 而 `download.fdwxhb.com` 的位流直链此前实测 **401 要账号**（[[哪些要跟厂商要#七、补上两个空的参考工程目录|哪些要跟厂商要——七]]）。
2. **版本口径**：该仓库主线是 icraft **3.36.1**（我方板上 runtime 是 3.39.0，[[板端我方代码与产物台账]] 已验同版本兼容）；个别示例（`MultiPSin+MultiNets+Save2File`，YOLOv5+TarDAL）固定 **3.31.1**，不能与主线混编。
3. **矩阵不是回归结论**。README 自己写着"矩阵不代表当前提交已完成全部板端回归；部署时应核对实际 target、SDK/Runtime、模型和位流组合"。⇒ 标 ✅ 只表示"有源码与配置"，**不等于我方板上跑通过**。

## 六、我方现状与待办

**现状（A）**：板上现役是单网络 demo（`PLin+SingleNet+HDMI`，一颗 yolov5s）；所有编译产物都是单模型件；**一件多模型产物都没有**。

待办按顺序：

1. **向厂商要两样**（登记进 [[哪些要跟厂商要]]）：① `examples/3_multi_inputs` 与配套位流（尤其 zg-30t 多路基／或确认单路基可用）；② zg330backend **单设备多 session 并发**是否受支持。这条决定档 B 能不能做。
2. **换位流**（若确需多路基）：走 [[BOOTbin位流替换手术]]（这条路 10-10 已走通过一次），代价是动 PL 现场，需她点头。
3. **拿到 demo 后照抄改造**：厂商源码是"多图怎么挂、怎么轮"的权威答案，比自己试 API 省一个量级。第一站建议 `MultiWebcams+MultiNets+VPU`（不依赖 SDI 多路硬件，最接近我方 webcam 场景）。
4. **档 B 才是真并发**：先做 CMA 叠加实测（`mem_watch.sh` 现成，1 s 心跳落 eMMC），再拿厂商结论。
5. **双 LLM 若要立项**：只有 int8 量化一条路（权重减半），属全新验证线（校准集、精度判据、`qdtype` 改档全要从零立），或改架构把第二颗 LLM 挪到云（README 本来就写了"端云混合调度"，是设计内的路）。
6. 存储：每颗 LLM 件 1.6 GB 级、小模型 10 MB 级——小模型这条 eMMC 可忽略，LLM 那条不是。

## 相关页面

[[NPU调用链]] · [[板端我方代码与产物台账]] · [[LLM上板要求与候选模型对照]] · [[哪些要跟厂商要]] · [[解决方案汇总.xlsx - sln列表]] · [[交叉编译主机路由SOP]] · [[BOOTbin位流替换手术]]
