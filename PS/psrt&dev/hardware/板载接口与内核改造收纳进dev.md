# 板载接口与内核改造

> **本页回答什么问题**：PCIe、SFP、SDI、XADC、eMMC、第二路网口这些接口在悟净板上到底是什么状态、"共用 GT Bank 靠 MUX 选"是什么意思、要把它们用起来需要动哪几层（逐接口核对表在第六节）、**换一颗自己编的内核进去到底怎么操作、会比厂商少什么、反过来能解锁什么**、**能不能整体绕开 USB 在 PL 端直采音视频、那样还要不要写驱动**（第十节），以及**PL 网口／PL CAN／GPIO／PS-PL JTAG／MIPI／光模块这六个口各自是干什么用的**（第十一节）。
> **前置阅读**：[[板卡镜像实测取证]]（出厂内核配置与启动链）、[[板子（除芯片）]]（板级规格与口径差异）。
> 本页只登记硬件与软件栈的事实和改造路径，不写进度。结论标记与证据等级沿用 [[状态源与决策记录]]。

---

## 一、板型：我们被分配到的是完整版

**用户口径（2026-09-22）：被分配到的型号是完整版开发板，之前那张带 `JFMQL30TAI-LITE` 丝印的图是资料图。** 这条推翻了若干按 Lite 写的结论，见下表"处理"列。

| 信号 | 内容 | 读法 |
|---|---|---|
| 用户口径 | 分配到的型号 = **完整版**；LITE 丝印那张是资料图 | 冲突已消解 |
| 手册 | `FMQL30TAI 悟净开发板（完整版）硬件使用手册 V1.0` 与 `悟净 Lite（轻量版）硬件使用手册 V1.0`，**两份都是 FMQL30TAI 芯片** | 差异只在板上引出什么 |
| 配置表 | 用户 2026-09-22 直接给出完整版的配置清单原文 | 已誊入 [[板子（除芯片）#二、完整版配置表（用户 2026-09-22 提供的板卡配置清单原文）\|板子（除芯片）——二、完整版配置表（用户 2026-09-22 提供的板卡配置清单原文）]]，并逐行标了"本板可达性" |
| 镜像里的 dtb | `model = "FMQLMP FMQL100TAI"`，文件名 `fmqlmp-verify.dtb` | 100TAI 是**参考设计树**的型号串，不针对完整版／Lite 裁剪，所以它的 `status` 既不能证明"板上有"，也不能证明"板上没有" |

### 完整版与 Lite 不是"少几个接口"的简单子集关系

两份手册正文逐项对过：**完整版确实更多，但 MIPI 只有 Lite 有**。

| 接口 | 完整版（手册正文已核对） | Lite | 对本项目的处理 |
|---|---|---|---|
| eMMC | **有**：珠海秒存 AT70B32G，32GB，eMMC 5.1，配置表写 **8bit**，挂在 **PL Bank11** IO 上，手册原话"SD 控制器可通过**外扩 EMIO** 的方式进行访问 eMMC" | 无 | 想当启动介质要改**比特流 + dtb（`dwmmc@e0044000` 现在 disabled，且 DTS 里两个 mmc 都只写了 `bus-width = <4>`）** → 本周期不动，SD 卡继续是主介质 |
| 第二路千兆网 | **有**：两片裕太微 **YT8521**，手册明确"一片连接至 PS 端，**一片连接至 PL 端**" | 手册只登记 1 路 | 芯片有 GMAC1（`e0049000`，dtb disabled），但 PHY 走 PL → 要比特流；**eth0 已实测 1Gbps/Full，够用** |
| 第 2 路 CAN | **有**：一路在 PS Bank500（`PS_MIO14/15`，收发芯片 TI SN65HVD232DR 3.3V），另一路在 **PL Bank12**（`IO_L16P/L16N_T2_12`） | 手册未列 | **CAN0 是唯一"配置表 + dtb + 内核 + 日志"四头都对得上的额外接口**：dtb `can@e0005000` = okay，`CONFIG_CAN_SJA1000_PLATFORM=y`，journal 实到 `sja1000_platform e0005000.can: device registered (irq=6)`。可拿来当 PS↔PL 之外的对照组 |
| 串口（UART 转 USB） | **2 路**：PS 端 CP2103GM + Mini-USB；PL 端 TYPE-C（与 PL JTAG 共用） | 1 路（PS 端） | 原来按 Lite 记的"1 路"已改成 2 路 |
| SMA | **有**：1 对数据 + 1 对时钟 | 无 | GT 的第四个使用者 |
| EEPROM | **有**：512Kb，**通过 PL 端 IIC 访问**，手册原话"没有直接与 FMQL30TAI 连接" | 无 | 内核侧 `EEPROM_AT24/AT25=y`、`I2C_XILINX=y`、`I2C_CHARDEV=y` 全齐，**缺的是 PL I2C 与 dtb** |
| RTC | **有**：1 路，走 I2C（`PS_RTC_SCL`/`PS_RTC_SDA`） | 无 | **软件栈里等于不存在**：dtb 两路 i2c 都 disabled，内核一个 `RTC_DRV_*` 都没开 → 每次启动 `hctosys: unable to open rtc device (rtc0)`，板子时间归零 |
| QSPI | **两片** 复旦微 EFM25QL256-E16（各 256Mb） | 手册写 1 片 | dtb `spi@e0000000` okay、`spi@e0020000` disabled |
| HDMI 输出 | 有，**IO 逻辑实现**；手册自陈 720p@60 可达、**1080p@60 部分显示器闪屏**（HR bank 时钟 748.5M TMDS 超该 bank IO 的 710M 上限） | 有 | 若要用，**定 720p60** |
| HEADER | 14×2，2.54 mm 插针，**4 根 3.3V GPIO + 12 根 1.8V GPIO** | 有（16 路） | 直连 PL 换外设的唯一落点，见第十节 |
| XADC | **配置表列"5 路"，但完整版手册正文没有 XADC 章节** | **有正文有座子**：§4.20 + J23/J24/J25，见第四节 | 属**待验证**：到板看有没有那三组排针。无论哪版，内核 `# CONFIG_IIO is not set` 都先用不了 |
| **MIPI CSI** | **手册通篇没有 MIPI／CSI 字样** | **有**：J16（SFW15R-1STE1LF），2 data lane + 1 clock lane，PL BANK12 1.8V，引出 CAM_GPIO/SCL/SDA，**LP 与 HS 分别预留 100Ω／150Ω 匹配电阻需自选焊接** | **按"没有 MIPI"登记** → 任何"接 MIPI 摄像头"的想法在这块板上不成立，视觉入流只剩 SDI／USB（HDMI 是只出不进） |

> 到板第一件事：**数 RJ45、看有没有 MIPI 座与 XADC 排针、读 J12／J26／J27 跳线位置并拍照、确认 U-Boot 有没有真的加载比特流**。手册的用户须知里还有一条要记住：**"请不要对开发板上的元器件进行改动或者焊接，如有必要请联系我司技术支持；未经技术支持的改动造成损坏或功能异常，我司不予赔付"** —— 借来的板子，**自选焊接类的动作（比如 MIPI 座的匹配电阻、或给 HEADER 焊排针之外的东西）一律不做**。


---

## 二、"SFP、PCIe、SDI 共用 GT Bank 并通过 MUX 选择"是什么意思

### 先解释三个词

- **GT**：GigaTransceiver，**高速串行收发器**。芯片里的一小撮硬件电路，每一"lane"是一对差分收 + 一对差分发，能跑到几百 Mbps 到几 Gbps。PCIe、光纤（SFP）、SDI 这类"高速串行"协议都必须由它来发信号，普通 IO 口跑不了那么快。
- **Bank**：GT 是**分组**存在的，一组就叫一个 bank。手册原话：**"JFMQL30TAI 的芯片只有一个 bank 的 GT"**，编号 **bank112**。
- **MUX**：多路选择器，一个"扳道岔"的开关。因为 GT 只有一份，而板子上想做四样事情（PCIe、SFP、SDI、SMA），于是板上放了一颗 MUX，把**同一组 GT 引脚**接到其中**一个**接口上。

### 手册原文与跳线表

完整版手册 §4.14 原话："**由于 JFMQL30TAI 的芯片只有一个 bank 的 GT，故通过一个 MUX 进行片选切换。PCIE 接口、SFP 接口、SDI 接口、SMA 接口同用同一个 bank 的 GT。各个接口的选择通过 J12 进行片选。**"

| 想用的接口 | 数据通道选择（手册原文） |
|---|---|
| PCIe | J12 的 `GTX_LANE_SEL0` 接**低电平** |
| SFP0 | J12 的 `GTX_LANE_SEL1` 接**低电平** |
| SFP1 | J12 的 `GTX_LANE_SEL2` 接**低电平** |
| SMA | J12 的 `GTX_LANE_SEL3` 接**低电平** |
| SDI（4 入 1 出） | **J26** 的 `GTX_LANE_SEL0~3` 接**高电平** |

**时钟是另一组片选，别漏。**手册 §4.4："**由于 GT 模块只有 2 路时钟，故采用片选的方式确定进入 GT 时钟的频率**"，具体是 **J26 的 1、2 脚短接选 PCIe 的 100M 时钟进入 bank112 的 CLK0**，否则走 SI570；**J27 选 SDI 用的 148.5M 还是 SMA 的时钟进入 bank112 的 CLK1**（2026-10-16 更正：此处此前误写 CLK0，把 J27/CLK1 与 J26/CLK0 混了；对照手册原文"J27 选择SDI 使用的148.5M 还是SMA 的时钟进入bank112 的CLK1"）。也就是说换一个 GT 用途，**数据和时钟两处跳线都要跟着改**，改错的表现是"接口在、链路不通"，比不通更难查。

内核里对应的可编程时钟驱动都编进去了（`CONFIG_COMMON_CLK_SI5324=y`、`SI570`、`CDCE706`、`XLNX_CLKWZRD`、`DGLNT_DYNCLK`）。

**一处本地资料判不了的**：配置表声称 SDI 是"**4 路输入 + 1 路输出**"，而 GT 只有一个 bank，四路入加一路出至少要吃 5 条 lane。**bank112 到底有几条 lane、SDI 输出是否复用某条，要查 FMQL30TAI 芯片手册或直接问厂商**。这不影响下面第一条结论，但会影响"能不能同时接 4 台摄像机"这种具体规划。

### 这条对设计的硬约束

1. **同一时刻只能用一个 GT 用途**。插着 SDI 采集就不能同时用 PCIe 或 SFP，反之亦然。**这不是软件能绕的，是物理连线。**
2. 想换，得**断电、改数据跳线（J12 或 J26）、改时钟跳线（J26/J27）、并重出对应的 PL 比特流**（不同接口用的 PL 控制器不一样）。
3. 所以"用 PCIe 把数据高速搬到 PC"和"用 SDI 采集视频"这两件事**互斥**——而 SDI 恰好是视频入流最诱人的那条路。这一条直接决定了 PCIe 在本项目里没有位置。
4. 还有一条更前置的：**SDI 的 4 入 1 出、SFP、PCIe 全都要求 PL 里有对应控制器**。出厂镜像里这些一个都没有（见第六节的分层），所以现实里我们连"选哪一个"都还没到——**先要有比特流**。

---

## 三、PCIe x1 金手指：接 PC 能干什么，为什么现在不做

### 理论上能干什么

把开发板做成 **PCIe 端点（Endpoint）**、PC 做 **根复合体（Root Complex）**，本质是**在 PC 和板子的 PL/内存之间开一条 DMA 直连通道**。量级：PCIe 2.0 x1 约 500 MB/s、Gen1 x1 约 250 MB/s。典型用途：

- 把板子当**外置加速卡**：PC 负责跑大模型/存数据，板子的 PL 与 NPU 负责预处理与推理，结果直接回 PC 显存/内存。
- **原始视频流灌进 PC**（USB 带宽不够时的解法）、把训练好的权重批量灌进板子。
- 用 PC 侧工具直接读写 PL 的 AXI 地址空间做调试。

### 这颗板子上要付的代价（逐条都是硬障碍）

| 障碍 | 证据 | 后果 |
|---|---|---|
| **Linux 侧完全没有 PCI 子系统** | 出厂内核 `# CONFIG_PCI is not set` | 既没有 root complex 也没有 endpoint 框架，`lspci` 都不存在。要用必须重编内核 |
| **出厂 dtb 里没有 PCIe 节点** | `35_dtb_flattened_shipped.txt` 全文无 `pcie` | 光开内核配置不够，还要写设备树 |
| **PCIe 控制器要在 PL 里实现** | PCIe 走的是 PL 侧 GT bank112 | 要占 PL 资源、要出比特流；7 系列的 PCIe 集成块是否被 FMQL30TAI 引出并可用，**本地资料无法判定**（属**待验证**，要查芯片手册） |
| **与 SDI/SFP 互斥** | 第二节跳线表 | 用了 PCIe 就放弃 SDI |
| **PC 侧还要写驱动** | — | Windows/Linux 都要有能识别这个自定义端点并做 DMA 的驱动，或用厂商通用 DMA 驱动 |
| **物理形态** | 板子 233×139 mm、12V 独立供电 | 金手指插台式机槽位是台架场景，笔记本用不了 |

### 判定

**本周期不做**（候选都不算，属于明确排除）。如果目的只是"把数据快速搬到 PC"，**千兆以太网已经在厂商板上实测过 `1Gbps/Full`**（约 120 MB/s 理论上限），比折腾 PCIe 便宜两个数量级；如果目的是"减 USB 带宽压力"，摄像头降到 640×480 就解决了，见 [[外设与资金申报改成设备信息]]。

---

## 四、XADC 是什么、怎么"模拟"、为什么不推荐用

### 是什么

芯片手册与 Lite 手册 §4.20 原话："**JFMQL30TAI676H 片内集成了一路 12bit、1MSPS 的 XADC 模数转换器。悟净 Lite 开发板共引出了 5 路 XADC 接口**"。它就是芯片自带的一个**小 ADC**（模拟转数字），用来量电压——不是外贴的 ADC 芯片，是 PL 里的一段硬核。

| 通道 | 位置（**Lite 手册的丝印**） | 用途 |
|---|---|---|
| `XADC_VP / XADC_VN` | J24 | 专用模拟输入（可当温度传感器） |
| `XADC_VAUX0P / N` | J25 | 辅助模拟输入通道 0 |
| `XADC_VAUX8P / N` | J23 | 辅助模拟输入通道 1 |
| `XADC_VAUX1P / N` | 板上固定 | **VCC1V5 分压至 0.75V**，片内电源监测 |
| `XADC_VAUX9P / N` | 板上固定 | **VCC1V8 分压至 0.9V**，片内电源监测 |

所以"5 路"里有 2 路是**板子自己吃进去监测电源的**，真正留给用户接外部模拟信号的只有 **3 个座子**（J23/J24/J25）。

### 为什么不推荐用（三重否决，逐条独立成立）

1. **出厂内核 `# CONFIG_IIO is not set`。** Linux 里所有 ADC/DAC/传感器读数都走 **IIO 子系统**，它没编进去，就意味着：没有 `/dev/iio:device*`，没有 sysfs 读数节点；XADC 驱动（`CONFIG_XILINX_XADC`）在配置里根本不出现，而 IIO 属 `not set` 一类，**出厂镜像里也没有对应模块可补**（镜像只随带 3 个 `.ko`，见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]）。要用就得**重编内核打开 IIO + XADC 驱动**，还要在 dtb 里使能对应节点——而随镜像的 dtb 里**没有任何 XADC/amba 模拟节点**。
2. **完整版手册通篇没有 XADC 章节。** 它的**配置表**确实写了"5 路 XADC"（芯片侧能力），但**正文没有 §4.20 那样的引出说明**，J23／J24／J25 这三个座子的丝印只出现在 **Lite** 手册的接口图里。所以我们手上这块完整版到底把没把模拟输入引到连接器上，**属待验证**，到板目视。
3. **即便可达，也只有 3 个用户可接**（另外 2 路被固定接去监测 VCC1V5／VCC1V8）。

投入产出比：为了读一个模拟量去重编内核 + 改设备树 + 冒焊排针的风险，而项目本身（视觉 + 语音）根本不需要模拟输入 → **不进任何功能设计**。这条在 [[板子（除芯片）#三、规格 → 本项目的实际用途|板子（除芯片）——三、规格 → 本项目的实际用途]]里已按"不作功能设计依据"登记。

> **焊接红线**：厂商《用户须知》原话"**请不要对……元器件进行改动或者焊接，如有必要，请联系我司技术支持……未经技术支持的改动……我司将不予赔付**"。借来的板子，**不焊**。就算完整版真的留了 XADC 焊盘没贴座子，也不能自己补焊。

### "模拟传感器数据"该怎么做（三种，从轻到重）

赛题里如果需要"有传感器数据在动"的效果，**不需要硬件 ADC**：

1. **文件喂数（推荐）**：把采样序列写成一个 csv／bin，程序按时间戳读一行。真实传感器和文件之间只隔一个读取函数，后面要换成真硬件只改那一处。零风险、可复现、能当 golden 输入。
2. **软件生成**：程序里用正弦/噪声/状态机现算，连文件都不用。适合演示"数值在变"。
3. **PL 里造一个假数据源**：在 FPGA 里放一个 ROM 或计数器，通过 AXI GPIO／BRAM 让 PS 读。这是**唯一"像真硬件"的模拟法**，也顺便验证了 PL→PS 的读通路——如果赛题要求展示"自研 FPGA 采集前端"，这条路比碰 XADC 划算得多，因为它用的是已经内建好的通路（`u-dma-buf`、AXI GPIO），不需要重编内核。

真正接模拟器件（电位器、光敏、温度探头）是第四种，需要上面"重编内核"那条路，**不在本周期**。

---

## 五、SDI 与 SFP 一句话说明

- **SDI**：完整版配置表登记 **4 路输入 + 1 路输出**（Lite 手册只写 2 路输入），BNC 座。输入侧前面是 **LMH0344** 自适应电缆均衡器，输出侧是 **LMH0302** 电缆驱动，支持 **125 Mbps–2.97 Gbps**、ST424／ST292／ST344／ST259 广播标准，75 Ω（Belden 1694A／8281）。厂商用 `amvx.ko`（linlon MVX VPU）承载，**那颗 `.ko` 本板已随开机加载**（见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]；缺的是厂商那份 SDI 采集工程与配套比特流），日志里还留过 `mvx_v4l2_vidioc_streamon+0xb4 [amvx]` 的崩溃栈。→ 范围外，见 [[板级管线详图]] 页首偏差说明。
- **SFP**：完整版配置表登记 **2 路**光模块笼（SFP0／SFP1，跳线 `GTX_LANE_SEL1`／`SEL2`），默认全速率（Full BW）模式，同样吃 GT bank112。→ 范围外。
- **一条算不平的账（待验证）**：4 收 + 1 发 = **5 对差分**，而 bank112 只有 4 lane（85 Mb/s 的 GT 通常是 4 lane 一组）。所以"4 路 SDI 输入 + 1 路输出"**不可能同时全速工作**，或者其中有 lane 走的是 PL 普通 IO 而非 GT。**本地资料无法判定**，不要按"能并行采 4 路 SDI"做设计。见 [[板子（除芯片）#四、源文件之间的口径差异（必须显式标注）|板子（除芯片）——四、源文件之间的口径差异（必须显式标注）]]。

---

## 六、"USB 之外都要重编内核 + 改设备树 + 接 PL 控制器"这句话的展开

这是三件**互相独立**的事，别混成一件：

| 层 | 要动什么 | 难度 | 举例 |
|---|---|---|---|
| ① 内核配置 | 改 `.config`、重编 `Image` | 中 | 打开 `CONFIG_PCI`、`CONFIG_IIO`、`CONFIG_WLAN`、`CONFIG_PWM` |
| ② 设备树 | 改 dts 把节点 `status` 从 `disabled` 改成 `okay`、加 `compatible` 与引脚/中断/时钟 | 中，且**最容易出错** | 第二路以太网 `e0049000`、第二路 CAN `e0006000`、两路 I2C（EEPROM 与 RTC 挂在它上面）、eMMC 的第二 mmc 实例 |
| ③ PL 逻辑 | 在 Procise 里把对应 IP 综合进比特流、接好 AXI 与中断，再重出 `download.bit` | 高 | PCIe 端点、SDI 接收、HDMI PL 输出、GPIO 扩展 |

**三层都过才有现象**：只开内核配置不动 dtb，驱动 probe 不到设备；只动 dtb 不出比特流，PL 侧根本没有那个硬件；比特流里有 IP 但内核没驱动，就是一块死逻辑。

一个反例可以佐证：**USB 是这三层全都现成的唯一外设通路**——`CONFIG_USB_DWC2=y` 内建、dtb 里 `e0045000.usb` 是 `okay`、PL 里不需要任何逻辑。这就是"当前镜像真正能直接使用的仍是 USB UVC/UAC"这句话的完整含义。

### 逐接口三层核对（配置取自 34，dtb status 取自 36）

| 接口 | ① 内核配置 | ② 随镜像 dtb | ③ PL 侧 | 判定 |
|---|---|---|---|---|
| USB（UVC／UAC／大容量存储／HID／ACM） | 全部 `=y` | `usb@e0045000` okay | 不需要 | **三层齐，插上就用** |
| eth0 | `DWMAC_FMQL=y`、`STMMAC_*=y`、`PHYLIB／MDIO／BROADCOM_PHY／REALTEK_PHY` 全 `=y` | `ethernet@e0047000` okay | PS 侧 GEM，不需要 PL | **三层齐**（厂商板实测过 `1Gbps/Full`） |
| eth1（第二路千兆） | 同一套驱动已内建，且 `CONFIG_XILINX_GMII2RGMII=y` 也在 | `ethernet@e0049000` **disabled** | 完整版第二颗 **YT8521 挂在 PL 侧**：RGMII 12 线在 PL **Bank13**、MDC/MDIO 在 Bank13、复位在 **Bank12**；MAC 是 **PS 硬核 GEM1 经 EMIO + `GMII_to_RGMII`（PG160）**，不是 PL 软 MAC（A，见 [[PL网口bring-up与GEM1EMIO]]） | 缺 ②③ |
| CAN0 | `CAN=y`、`CAN_DEV=y`、`CAN_SJA1000=y`、`CAN_SJA1000_PLATFORM=y` | `can@e0005000` **okay** | PS 侧，不需要 PL | **三层齐**：日志有 `sja1000_platform e0005000.can: ... device registered (irq=6)`。注意上游 `XILINXCAN` 并**未**开，编进去的是 SJA1000 平台驱动这一条路 |
| CAN1 | 同上 | `can@e0006000` **disabled** | 完整版第二路走 **PL Bank12** `IO_L16P／L16N_T2_12` | 缺 ②③ |
| eMMC 32GB（完整版） | `MMC=y`、`MMC_BLOCK=y`、`MMC_DW=y`、`MMC_DW_PLTFM=y` | `dwmmc@e0043000` okay（这张是 SD 卡）／`e0044000` disabled | **手册原话：SD 控制器需"外扩 EMIO"才能访问 eMMC**，即要比特流把 MIO 之外的 SD 接口引到 PL Bank11 | 缺 ②③，且 ③ 是改厂商工程 |
| QSPI ×2（各 256Mb，复旦微 EFM25QL256-E16） | `SPI_CADENCE_QUADSPI=y`、`SPI_DW_FMSH=y` | `spi@e0000000` okay／`spi@e0020000` **disabled** | PS 侧直连，不需要 PL | 缺 ② |
| EEPROM 512Kb | `EEPROM_AT24=y`、`I2C=y`、`I2C_CHARDEV=y`、`I2C_XILINX=y`、`I2C_SLAVE_EEPROM=y` | `i2c@e0002000`、`i2c@e0022000` **都 disabled** | 完整版 EEPROM 走 **PL IIC** | 缺 ②③ |
| RTC（完整版 1 路） | `RTC_CLASS=y`，但**全文没有任何一条 `CONFIG_RTC_DRV_*`** | **没有 rtc 节点** | 硬件挂在 I2C（`PS_RTC_SCL` B21／`PS_RTC_SDA` A18），而 I2C 在 dtb 里 disabled | **三层全缺**。现象已在日志里：每次启动 `hctosys: unable to open rtc device (rtc0)`，所以 RTC 不保存时间、时钟冻在 `2023-03-02 20:58` |
| HDMI 输出 | `CONFIG_DRM_XLNX_PL_HDMI=m`，**这颗 `.ko` 镜像里没带**（见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]）→ 在这块板上**等于没有** | — | 全部在 PL（IO 实现；720p60 标称，1080p60 的 748.5M TMDS 超 HR bank 710M 会闪） | 缺 ①②③，本项目不使用 |
| SDI／SFP／PCIe／SMA | `# CONFIG_PCI is not set`；GT 相关时钟驱动已 `=y` | 无 pcie 节点 | 要比特流 + **改跳线**，四者互斥 | 范围外，见第二、三、五节 |
| PL 16 路 HEADER（4×3.3V + 12×1.8V） | `GPIO_SYSFS=y`、`GPIO_XILINX=y`、`GPIO_DWAPB=y`、`GPIO_PCA953X=y` 全内建 | 取决于自己的 dts | **要自己在 Procise 里做引脚约束并接 AXI GPIO** | 缺 ③——**这正是本项目自研的主场**，不需要动内核 |
| I²S 麦克风／I²S 功放 | `# CONFIG_SND_SOC is not set`、`# CONFIG_PWM is not set` | 无 `sound` 节点 | 要 PL I²S RX／TX 逻辑 | 走第十节"绕开 ALSA"这条路可以**不动内核** |
| XADC | `# CONFIG_IIO is not set` | 无节点 | 座子在不在待板看 | 三重否决，见第四节 |

> 读法：**能不能用看板上有没有现成的 `.ko`**——出厂只随带 3 个（`u-dma-buf`／`mali_kbase`／`amvx`，见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]），其余 `=m`／`not set` 在板上都没有模块文件、效果相同。所以判定"能不能用"时不要问"驱动在不在配置里"，要问"**是不是 `=y`**"。

### 第四层：其实存在一条"不重编内核也能动设备树"的路

上面把②设备树写成"改 dts 重编 dtb"，那是最重的一种做法。取证时漏了、这一轮补上的一条事实改变了成本结构：**出厂内核把运行时设备树覆盖整套编进去了**。

| 依据 | 配置项（全部 `=y`） | 含义 |
|---|---|---|
| 覆盖框架 | `CONFIG_OF_DYNAMIC=y`、`CONFIG_OF_RESOLVE=y`、`CONFIG_OF_OVERLAY=y`、**`CONFIG_OF_CONFIGFS=y`**、`CONFIG_CONFIGFS_FS=y` | 开机后可以往里**追加／修改节点**，不需要重编 `Image`，也不需要换掉出厂 `fmqlmp-verify.dtb` |
| 用户态驱动 | `CONFIG_UIO=y`、`CONFIG_UIO_PDRV_GENIRQ=y`、`CONFIG_UIO_DMEM_GENIRQ=y` | 一个 `compatible = "uio_pdrv_genirq"` 的节点 = `/dev/uioN`，用户态 `mmap` 到 PL 的 AXI 寄存器、`read()` 阻塞等中断 |
| Linux 侧下比特流 | `CONFIG_FPGA=y`、`CONFIG_FPGA_BRIDGE=y`、`CONFIG_FPGA_REGION=y`、`CONFIG_OF_FPGA_REGION=y`、`CONFIG_FPGA_MGR_FMQL_FPGA=y`；dtb 里 `devcfg@e0040000` **okay**；日志 `fpga_manager fpga0: FMSH FMQL FPGA Manager registered` | ~~不依赖 U-Boot 那行 `loadbit` 也能把 PL 装起来~~ → **2026-10-10 实测推翻：配置齐全但写不进去**，`echo > …/firmware` 恒 `Timeout waiting for PCFG_DONE`（**用出厂位流做对照同样失败**），见 [[PL位流重载通道失效]] |
| 搬运 | dtb 里 `dma@f0010000`（`snps,axi-dma-1.01a`，PL 侧）**已经是 okay**，`CONFIG_XILINX_DMA=y`、`DW_DMAC=y`、`XILINX_FRMBUF=y` | `u-dma-buf` 那颗 `.ko` **本板已加载**（`/dev/udmabuf` 存在，见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]），**但 AXI DMA 这条路不需要它** |

**于是"要动设备树"的接口，成本从"重编内核 + 换 dtb"降为"写一个 `.dtbo` 插进去"** —— 风险等级完全不同，可回滚（`rmdir` 那个 overlay 目录就撤销），而且**不动厂商那颗 `Image`**。

操作形态（**待验证**，一次就能证实）：

```
mount -t configfs none /sys/kernel/config
mkdir /sys/kernel/config/device-tree/overlays/mypl
cat mypl.dtbo > /sys/kernel/config/device-tree/overlays/mypl/dtbo
```

一个前提要说清楚：取证件 `35_dtb_flattened_shipped.txt` 的清单里**没看到 `__symbols__`**（该文件是节选，不能定论）。**没有 symbols，就不能用 `&label` 去引用现有节点**——所以 overlay 能做的是"新增自己的节点"（够用：`uio_pdrv_genirq` 就是新节点）和"按完整路径改现有节点的 `status`"，而**不能**指望它把 PL 的 PRBO 自动挂到现有桥上。到板第一件事是 `ls /proc/device-tree/` 里找 `__symbols__`。

---

## 七、内核编完了，怎么换进去

### 先看启动链（出厂镜像实测）

> 出厂镜像的实测出处见 [[板卡镜像实测取证]]。
```
BootROM 读 SD 卡 → BOOT.bin（FSBL + U-Boot）
  → U-Boot 读 FAT 分区的 uEnv.txt
      bootcmd = run loadbit; run uenvcmd
      loadbit：从 FAT 分区读 download.bit，fpga loadb 0   ← 先下 PL 比特流
      bootargs 里写死 mem=1024M root=... rootwait rw
  → 加载 Image（内核）+ fmqlmp-verify.dtb → 挂载 ext4 根文件系统
```

`uEnv.txt` 的关键行**原文照录**（提取件 `boot_files/`）：

```
bootcmd=run loadbit; run uenvcmd
loadbit=mmc rescan && fatload mmc 0:2 0x10000000 download.bit && fpga loadb 0 0x10000000 $filesize
uenvcmd=mmc rescan && fatload mmc 0:1 0x10080000 Image && fatload mmc 0:1 0x11000000 fmqlmp-verify.dtb && booti 0x10080000 - 0x11000000
bootargs=console=ttyPS0,115200n8 earlycon=uart8250,mmio32,0xe0004000 loglevel=8 root=/dev/mmcblk0p2 rootwait rw clk_ignore_unused mem=1024M
bootdelay=3
ethact=ethernet@e0047000
```

**关键事实一：内核、dtb、比特流都是 FAT 启动分区里的普通文件。**换内核不需要重烧整张卡，也不需要 JTAG。

**关键事实二（2026-10-10 已复核为成立）：出厂镜像上这段 `loadbit` 是空转的。**三条证据叠在一起：

1. FAT 分区（`mmc 0:1`）里的文件清单是 `Image`、`fmqlmp-verify.dtb`、`uEnv.txt`、`BOOT.bin`、`ai7030_top.bit`、`ai7030_top_disable_icap.bit`——**没有 `download.bit` 这个文件**。
2. 而 `loadbit` 从 **`mmc 0:2`** 读，`0:2` 是 **ext4 根文件系统分区**，`fatload` 在那里根本读不到 FAT 文件。
3. U-Boot 的 `bootcmd` 用 `;` 串联（不是 `&&`），所以 `run loadbit` 失败**不会中断启动**，`uenvcmd` 照常执行。

**复核补充**：把 `loadbit` 改成 `fatload mmc 0:1 … video_only.bit`（分区号纠正、FAT16）之后，串口实测 `fatload` **成功**（`5979868 bytes read in 251 ms`），但紧随其后的 `fpga loadb` 仍返回 `Error 1`。→ **`0:2` 是抄错的板型，但即使纠正分区号，`fpga` 命令本身在这块板子上也是坏的。**

→ 结论：**"把比特流命名为 `download.bit` 丢进 FAT 分区就会自动下 PL"这条常见说法，在出厂镜像上是断的，而且修好分区号也不通**。详见 [[PL位流重载通道失效]]。

**~~但这条推断不阻塞任何事~~——当时以为还有第二条入口，2026-10-10 实测发现这条也不通。** 出厂内核的 **FPGA Manager 整套是内建的**（`CONFIG_FPGA=y`、`CONFIG_FPGA_MGR_FMQL_FPGA=y`，dtb 里 `devcfg@e0040000` 是 okay，日志有 `fpga0: FMSH FMQL FPGA Manager registered`），`/dev/fpga0`（misc 10:61）也在。操作形态确实是这样：

```
ls /sys/class/fpga_manager/fpga0/          # 看 state 与 firmware 两个属性
echo video_only.bin > /sys/class/fpga_manager/fpga0/firmware
```

`.bit` 放进 **`/lib/firmware`** 这一步没问题（ext4 可写），`CONFIG_FW_LOADER_USER_HELPER` 未开、没有 user-mode fallback 也理解。

**但实测结果是 `dmesg: Timeout waiting for PCFG_DONE` / `Error after writing image data to FPGA`，写完 `state` 变成 `write complete error`。用出厂位流做对照，同样超时。** 另注 `/sys/class/fpga_manager/fpga0/state` **只读**（写 `0`/`1` 均 `Permission denied`），标准状态机没实现。

**→ 修订结论：比特流这一层"不需要动 `uEnv.txt`、不需要重编 U-Boot、不需要 JTAG"这个判断是错的。当前唯一确认可用的通道是 FSBL 从 BOOT.bin 灌位流，我们已定位出该分区边界并备好字节级替换方案（同样写在 [[PL位流重载通道失效]] 第六节）。厂商那边的问题单也在同一页。**

### 换进去的操作序列

1. **备份**：把 SD 卡 FAT 分区整盘拷走（就几个文件，`Image`、`BOOT.bin`、`uEnv.txt`、`*.bit`、`*.dtb`）。这一步做了，后面怎么折腾都能回滚。2. **编译**：在交叉编译容器里用**厂商那份内核源码树**编，不要用上游原版（原因见第八节）。产物是 `arch/arm64/boot/Image`。
3. **换文件**：把新 `Image` 拷进 FAT 分区，**先另存为 `Image.new`**，改 `uEnv.txt` 里加载内核那一行的文件名指向它；确认能起来之后再覆盖原 `Image`。这样一次改错还能改回来。
4. **dtb 同步**：如果改了设备树，编出 `fmqlmp-verify.dtb` 同样按"先改名、再切 `uEnv.txt`"的方式换。
5. **模块目录**：如果新内核的版本串变了（`uname -r` 的结果变了），**必须同时把 `/lib/modules/<新版本>` 建出来**，否则出厂那 3 个 `.ko`（`u-dma-buf`／`mali_kbase`／`amvx`）反而会失配、加载不了——现状是它们与运行内核同名所以都能加载（读数见 [[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]）。最省事的办法是内核里该开的都开成 `=y`，根本不依赖模块。
6. **比特流**：自己的 `*.bit` 进 FAT 分区时注意上节"关键事实二"——默认那行 `loadbit` 指向的是 `mmc 0:2` 上并不存在的 `download.bit`。
7. **串口看日志**：接 PS 端那个 UART 转 USB（完整版有 2 路），终端开 115200。`bootargs` 里已经是 `loglevel=8`，起不来时信息会很全。
8. **兜底**：真起不来，用 **PS_JTAG** 直接下载启动（完整版还有 PL_JTAG），或者整卡重烧原镜像。两条退路都在，不会变砖。

### 教程在哪

- **厂商侧**：`fdw(raw\04_ICraft\开发教程.txt`、悟净板手册 §4.2 配置加载模式（讲跳线与启动方式）。本地资料里**没有**一份"如何重编这颗板子的 Linux 内核"的官方教程。
- **通用做法**：这就是标准的 arm64 Linux 交叉编译流程（`make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-`，配 defconfig，`make Image dtbs modules`），任何一份主流板卡的"重编内核"教程都适用；差异只在**必须用厂商那份带 fmsh 补丁的源码树**。
- **现成素材**：提取件里已经有 `32_defconfig_fmsh_fmqlmp.txt`（厂商 defconfig 原文）、`34_kernel_config_from_Image.txt`（**从出厂 `Image` 里解出的 `.config`**，这是最该拿来做基线的那份）、`17_kernel_src_selected.tar.gz` 与 `47/49`（fmsh 相关源码子树与另一棵 `linux-5.4.52-fmsh` 源码树的元数据）。
- **建议**：以 `34` 为基线改配置，**不要**从 defconfig 或上游 menuconfig 重新攒。

> 状态：**待验证**。以上路径在厂商板上没有反例，但我们自己一次都没做过；真要做之前先确认有没有必要——本项目当前所有功能都能建立在 `=y` 内建驱动之上。

---

## 八、自己编的内核会比厂商少什么（会，而且少得不少）

**先给结论：会少。** 所以必须拿 `34`（从出厂 Image 解出的 `.config`）当基线，而不是拿 defconfig 或自己的 menuconfig 结果。

### 证据一：构建树的 .config 和出厂 Image 的 .config 差 319 行

提取件 `44_diff_buildconfig_vs_imageconfig.txt` 的统计：**出厂 Image 比构建树 `.config` 多 282 项、少 37 项**。多出来的关键项包括：

| 多出的项 | 为什么重要 |
|---|---|
| `CONFIG_COMPAT=y`、`COMPAT_BINFMT_ELF`、`COMPAT_32BIT_TIME`、`OLD_SIGACTION` | **允许 64 位内核跑 32 位 ELF**。少了它，任何 32 位预编译二进制直接 exec 失败 |
| `CONFIG_CPUFREQ_DT=y`、`CPU_IDLE_MULTIPLE_DRIVERS`、`ARM_CPUIDLE` | 调频与 idle。少了可能主频/功耗行为不同 |
| `COMMON_CLK_SI5324`、`SI570`、`CDCE706`、`XLNX_CLKWZRD`、`DGLNT_DYNCLK` | **可编程时钟驱动**，正是第二节 GT 时钟片选那套硬件的驱动 |
| `BCM_NET_PHYLIB`、`BROADCOM_PHY` | 以太网 PHY 驱动。少了可能网口起不来 |
| `CRYPTO_*`、`ASN1`、`AUDIT`/`AUDITSYSCALL` | 加密与审计子系统，关系到签名模块加载与某些用户态依赖 |
| `BACKLIGHT_CLASS_DEVICE`、`BACKLIGHT_GENERIC` | 显示相关 |
| `ARM64_ERRATUM_1418040`、`845719` | **Cortex-A53 勘误补丁**。日志里 CPU 特性行就带着 erratum 845719 |

少掉的 37 项也要逐条看，别默认无所谓。

### 证据二：厂商有一批不在内核树里的东西

这些不是"配置开不开"的问题，而是**源码树里根本没有**，用错源码树就彻底没有：

| 组件 | 位置／证据 | 少了会怎样 |
|---|---|---|
| `dwmac-fmql` 以太网驱动 | 提取件 `17`/`49` 的 fmsh 源码子树 | 网口不工作（不是上游 `stmmac` 原名） |
| `fmql_uartps` 串口驱动 | 同上 | **控制台直接没有输出**，最危险的一项 |
| fmsh 的 clk / dma / soc / firmware 驱动 | 同上 | 时钟树、DMA、固件接口缺失 |
| Cadence media / i2c 补丁、`xilinx-v4l2-controls.h` | `17`、`uapi_headers/` | V4L2 通路行为不同 |
| `mali_kbase`（GPU）、`amvx.ko`（VPU）、`u-dma-buf` | 提取件 `13`，是外部 `.ko` | 这三个在出厂镜像里已是可加载状态、本板都在跑（[[os#二、内核模块（含一条对镜像取证结论的更正）\|os——二、内核模块（含一条对镜像取证结论的更正）]]）；换内核后要跟着重出配套版本，否则失配 |
| dtb `fmqlmp-verify.dts`（26 KB）及其节点 status | 提取件 `29`/`31`/`35`/`36` | 换 dtb 等于换一块板子的定义 |
| `BOOT.bin`（FSBL + U-Boot + PMU 固件 `bl31.elf`） | 提取件 `boot_files/` | **FSBL/PMU 与内核必须配套**，不要顺手重编 FSBL |

### 反过来说：一次正确的重编能解锁什么

前面读的是"会少什么"，这半边也要算清楚——**重编能解锁的是"镜像里没装的那些模块"（HDMI 输出、无线栈……）与"要改的驱动"，顺带让出厂那 3 个模块在新版本串下继续同名可加载**：

| 解锁项 | 怎么做 | 解锁后能干什么 |
|---|---|---|
| **模块加载本身** | 新内核版本串与 `/lib/modules/<新版本>` 同步产出（`make modules_install`，或直接把 `LOCALVERSION` 保持成出厂串） | 镜像里没带的模块（如 `drm_xlnx_pl_hdmi`、无线栈）变成真能 insmod；出厂那 3 个（`mali_kbase`／`amvx`／`u-dma-buf`）本就可加载，重编后要重出配套版本才不失配 |
| `CONFIG_RTC_DRV_*` | 按板上那颗 RTC 的型号打开（要先到板确认是哪家；I2C 类还要开 `RTC_DRV_RV3029C2` 这一族）＋ dtb 加 rtc 节点 ＋ 使能 i2c | `hctosys` 不再报 `unable to open rtc device`，日志时间与业务时间戳可用 |
| `CONFIG_IIO` + XADC | 开 IIO、`XILINX_XADC`，dtb 加节点 | 读片内电压／温度——**但项目不需要**，见第四节 |
| `CONFIG_WIRELESS`/`WLAN`/`CONFIG_USB_NET_DRIVERS` | 内核 + 固件 + wpasupplicant 三样一起补 | USB WiFi／USB 网卡；**当前不排期**，因为板载 eth0 已经够用 |
| `CONFIG_PCI` | 内核 + dtb + PL 端点 IP + PC 侧驱动，四层一起 | 见第三节判定：**不做** |
| `CONFIG_PWM` | 内核配置一层 | 舵机类硬实时；替代品是 I2C 挂 PCA9685，见 [[外设与资金申报改成设备信息#七、关于"用 Arduino 帮板子读传感器、控舵机"\|外设与资金申报——七、关于"用 Arduino 帮板子读传感器、控舵机"]] |

**所以"要不要重编"的判据只有一条**：这件事能不能在 `=y` 内建驱动 + 运行时 overlay + 自己的比特流之上做完。第六节的"第四层"和第十节的表已经说明：**本项目当前所有功能都能在这个范围内做完**（USB 主链路连比特流都不用出）。重编留给两种情况：一是赛题明确要求"定制内核/驱动"，二是镜像里没带的能力（HDMI 输出、无线栈等）或要改的驱动变成硬需求。

### 因此三条纪律

1. **源码树必须是厂商那棵 `linux-5.4.52-fmsh`**，配置基线必须是 `34`（出厂 Image 解出的 `.config`）。
2. **只加不减**：改配置只做"把 `not set` 改成 `=y`"这一类加法；删东西前先确认没有用户态依赖。
3. **换之前留好回滚**（第七节第 1、3 步），并且**保留 `CONFIG_IKCONFIG`** ——否则以后没法再从 `Image` 里解出 `.config` 做对比。

---

## 九、到板必查（这一页相关的项）

| 待查项 | 命令／动作 | 为什么必须查 |
|---|---|---|
| 板型与丝印 | 看 PCB 丝印、量外形、数座子 | 确认完整版；顺带确认有没有 MIPI 座与 XADC 排针（型号已确认为完整版，**丝印这一手仍未做**） |
| **PL 里到底有没有比特流** | `dmesg` 过滤 fpga、`ls /sys/class/fpga_manager/*/state`、U-Boot 里 `printenv` 看 `loadbit` | 第七节"关键事实二"是推断，到板一次就能证实或推翻。**若 PL 是空的，所有依赖 AXI IP 的自研模块都要自己出比特流并改 `uEnv.txt`** |
| FAT 分区文件清单 | 把卡插 PC 上数一遍 | 出厂清单里没有 `download.bit`，与上条互为证据 |
| GT 跳线当前状态 | 读 J12／J26／J27 跳线帽位置并**先拍照记录原状态** | 决定现在接在 PCIe／SFP／SDI／SMA 哪一个上；改跳线前要能复原 |
| eMMC 是否可用 | `lsblk`、`cat /proc/partitions`、`dmesg` 过滤 mmc | 完整版有 32GB eMMC，若能访问就不依赖 SD 卡；访问不到则印证"要外扩 EMIO" |
| CAN0 是否成网 | `ip -details link show can0`、`candump`（若无工具则看 dmesg） | dtb 已 okay、驱动已内建、日志已注册——**只差实测**，是唯一一个"零改动可能有现象"的板载外设 |
| 第二路网口 | `ip link`、`ls /proc/device-tree/` 比对 `35`/`36` 提取件 | 芯片侧两个 Gmac，随镜像只使能 eth0；第二颗 PHY 在 PL |
| RTC 与时间 | `hwclock -r`、`date`、`dmesg` 过滤 rtc | 三层全缺（见第六节表），到板再确认一次有没有冒出 rtc 节点 |
| 内核真实配置 | `zcat /proc/config.gz`（若 `IKCONFIG_PROC` 开着），否则 `unxz` 提取件 `34` 对比 | 一切驱动判断的根据 |
| PCI／IIO／WLAN／SND_SOC 现状 | `grep -E 'CONFIG_PCI=y' /boot/config*` 这类逐项查，或对照提取件 `34` | 复核本页第三、四、十节结论 |
| 时钟芯片在不在总线上 | `i2cdetect -y <bus>` | SI5324／SI570 是 I2C 编程的；但**出厂 dtb 两路 i2c 都 disabled**，先要解决 i2c |
| USB 枚举基线 | `lsusb`、`ls /sys/bus/usb/devices` | 拿到 root hub + `0424:2514` 的真实拓扑，把"4 口共享 480 Mbps"落到设备号上 |
| **configfs overlay 能不能插** | `mount -t configfs none /sys/kernel/config`、`ls /proc/device-tree/` 找 `__symbols__`、试插一个最小 `.dtbo` | 第六节"第四层"整条路的成立前提。**成了就不必重编内核去动设备树** |
| UIO 与 fpga manager 现状 | `ls /dev/uio*`、`ls /sys/class/fpga_manager/fpga0/`、`cat .../state` | 第十节 PL 直采的两个入口；预期是"没有 uio 节点、manager 在但没加载过" |
| **第二路 GEM 是 PS 硬核还是要 PL 软 MAC**（**已结，A**） | 结论：**PS 硬核 GEM1 经 EMIO 穿到 PL**，不是软 MAC。证据三处：① 厂商 PS7 IP 的 `component.xml` 里 `GMII_ETHERNET_1`／`MDIO_ETHERNET_1` 接口存在，使能条件为 `PCW_EN_EMIO_ENET1=1` 与 MDIO 选 EMIO；② `ps_ai_processing_system7_0_0.xci` 里 ENET1 全关（`PCW_EN_ENET1=0`、`PCW_EN_EMIO_ENET1=0`）、MIO0–15 已被 QSPI／SPI1／CAN0 占满，GEM1 只能走 EMIO；③ 在厂商工程**副本**上实跑改参数，`set_property` rc=0、`validate_bd_design` rc=0、两个接口均出现。详见 [[PL网口bring-up与GEM1EMIO]]。板上旁证仍可补：`ls /sys/class/net`（预期只有 `eth0`／`can0`） | ~~决定 eth1 的工作量差一个量级~~ → 已判：**硬核路线**，工作量＝改 PS7 参数＋`GMII_to_RGMII` 核＋PL 引脚约束＋dtb，**不需要自己写 MAC** |
| **PL 那路 CAN 的收发器在不在位、什么电平** | 目视 PL CAN 那个座子／器件位＋对照原理图（**改焊一律禁止**，只看不动烙铁） | 手册 §4.15 只给 PS 那路标了 TI SN65HVD232DR／3.3 V，PL 那路只给引脚 `IO_L16P／L16N_T2_12`。而 Lite 手册 §4.19 写明 **Bank12 是 1.8 V IO**，PL CAN 恰好在 Bank12 → 若收发器实为 3.3 V 件，逻辑侧还要电平转换。见第十一节 |

> 这一张表一次开机做完：前四条靠目视与拍照，其余是 SSH 里十几条命令。命令清单见 [[外设与资金申报改成设备信息#五、到板第一天：一件外设一条命令|外设与资金申报——五、到板第一天：一件外设一条命令]]，接口参数冻结见 [[接口契约与数据通路]]。

---

## 十、"能不能全在 PL 端处理"——板级直采外设的判定

这一节回答两个问题：**① 不用 USB，能不能直接从 PL 收摄像头和麦克风；② 走 PL 直采还要不要写驱动。**

### 结论先给

| 路线                                        | 本板可行性                                                                                                                  | 判定                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **MIPI CSI 摄像头直采**                        | **基本作废**：完整版手册通篇没有 MIPI／CSI 字样，座子是 **Lite 独有**（J16，2 data + 1 clock lane，PL Bank12 1.8V）                               | 不排。到板目视再钉死                                                         |
| **SDI 摄像头直采**                             | 硬件有（4 入 1 出、LMH0344／LMH0302、125M–2.97G），但要 GT 跳线切到 SDI、要有承载它的比特流、要 `amvx.ko`（**本板已可加载**，缺的是厂商那份采集工程与配套比特流）、且 lane 数算不平 | **只在拿到厂商 `sdicamera + yolov5 + hdmi` 完整工程的前提下才考虑**；否则不要为此买 SDI 摄像机 |
| **HDMI 采集／输出**                            | 输出是 PL IO 方案（`CONFIG_DRM_XLNX_PL_HDMI=m` → 用不了），板子**没有 HDMI 输入**                                                       | 不作采集入口                                                             |
| **I²S 数字麦克风直采**（2× INMP441／SPH0645LM4H 类） | **可行**：PL 16 路 HEADER 里有 **4 根 3.3V GPIO**，I²S 只需 BCLK＋LRCLK＋DATA 三根；内核 `# CONFIG_SND_SOC is not set` 这条路**可以整体绕开**    | 候选，代价是自己写 PL 的 I²S RX                                              |
| **I²S 功放**（MAX98357A，D 类，3.3V 供电）         | 同上，用掉 3 根 3.3V；**与麦克风合计需要 6 根 3.3V，而 HEADER 只有 4 根**                                                                   | 若两者都做，只能**共用 BCLK／LRCLK、各自一根 DATA** → 4 根刚好够（时钟两路共用）               |
| **USB UVC 摄像头 + USB 全向麦（MCP01）**          | 三层全现成，见第六节表                                                                                                            | **本周期唯一开箱路线**，见 [[外设与资金申报改成设备信息]]                                  |

> 4 根 3.3V 的账：INMP441 与 MAX98357A 各要一根 SD 数据线，BCLK 与 LRCLK **两路共用**同一对，就是 2＋2 里省出 2 根 → **恰好 4 根**。剩余 12 根是 **1.8V**，接 3.3V 逻辑前要电平转换，**且不许自己焊**（第四节焊接红线）。

### "数据要参考驱动做解码才能读吗"——不用，解码是 PL 的事

这是这一节最关键的认知纠正。**I²S、SDI、D-PHY 这些协议的"解码"是比特级的，属于 RTL，不属于驱动。**

- **I²S**：三根线（BCLK／LRCLK／SD），LRCLK 跳变决定左右声道，BCLK 上升沿逐位移出 MSB-first 的 24／32 位字。这是**十几行状态机**就能做完的东西，在 PL 里把串行位流攒成一个并行字（比如 16 位／样本），PS 侧读到的就已经是** PCM 数组**。
- **SDI**： scrambling 解除、Word Alignment（STS-ID／SAV-EAV）、10-bit→视频数据的映射，全在 PL 的 SDI RX IP 里；到 PS 手上的是 AXI-Stream 视频像素。
- 所以 **"要不要照着驱动做解码"这个问题本身就问反了**：驱动里那些解码代码是给"协议由软件兜底"的平台用的；PL 直采恰恰是为了**不让软件碰协议**。

### 那么 PL 直采还剩什么"驱动"要做？

只剩下**搬运与打断**这一层，比 ALSA／V4L2 那套轻得多，而且**在出厂内核上就能做**。按"要不要动内核"排序：

| 手段 | 内核依据 | 要不要重编内核 |
|---|---|---|
| **UIO + 运行时设备树覆盖**（推荐首选） | `UIO=y`、`UIO_PDRV_GENIRQ=y`、`UIO_DMEM_GENIRQ=y`；`OF_OVERLAY=y`、`OF_CONFIGFS=y` | **不要**。写一个 `compatible="uio_pdrv_genirq"` 的 `.dtbo` 插进 configfs → 得到 `/dev/uioN`，用户态 `mmap` PL 寄存器、`read()` 等中断 |
| **比特流从 Linux 侧加载** | `FPGA=y`、`FPGA_MGR_FMQL_FPGA=y`、dtb `devcfg@e0040000` okay | **不要**。`.bit` 放进 `/lib/firmware` 后 `echo > /sys/class/fpga_manager/fpga0/firmware`，见第七节 |
| **AXI DMA 直写 PS 内存** | `XILINX_DMA=y`、`XILINX_FRMBUF=y`、`DW_DMAC=y`；dtb `dma@f0010000`（`snps,axi-dma-1.01a`）**已经是 okay** | **不要**，但要自己在 overlay 里把中断／掩码补对 |
| **AXI GPIO 经 `/dev/gpiochip*` 或 sysfs** | `GPIOLIB=y`、`GPIO_SYSFS=y`、`GPIO_XILINX=y`、`GPIO_DWAPB=y`、`OF_GPIO=y` | 不要 |
| `CONFIG_FMQL_REMOTEPROC=y` | 已内建 | 不要。这是 fmsh 自己的 PL↔PS 通路，到板查它暴露什么节点，可能是现成的轮子 |
| **`u-dma-buf` 共享缓冲** | 提取件 `13` 里是外部 `.ko`，**本板已加载**（`/dev/udmabuf` 存在） | **不要**（现成可用即可；`/home/udmabuf` 那套源码留着备查） |
| **`/dev/mem` 直接 mmap AXI 地址空间** | 内核默认开着，但要求目标地址**没被设备树拥有**，否则行为未定义 | 不要——但这是**最后手段**，只用于一次性调试，不进交付物 |

**结论修正（相对上一版登记）**：`u-dma-buf` 曾经是"PL 直采必须重编内核"的唯一理由。**现在不是了**——UIO + overlay + fpga_manager + 已 okay 的 AXI DMA 这条组合拳全程不动内核。厂商当年用 `u-dma-buf` 是他们的选型，不是我们的约束。

**代价要说清楚**：绕开 ALSA 之后 `arecord -l`／`aplay -l` **看不见这个设备**，任何现成的 ALSA 工具链、GStreamer 的 `alsasrc`、以及 [[音频]]里 MCP01 那套"两条命令验证"全部失效。取而代之的是自己的读取线程与自己的测试脚本。V4L2 侧同理——除非在 dtb 里注册一个 `v4l2-loopback`／自己写 media 驱动，否则 `v4l2-ctl` 也看不见。

### 因此本周期怎么选

1. **演示与主链路走 USB**（C270i + MCP01）：零驱动风险，出问题能用 `lsusb`／`arecord -l` 一步定位。
2. **PL 直采作为"自研"载体**，不做主链路：在 PL 里放 I²S RX／TX 与一个假数据源（ROM／计数器，见第四节第 3 条），验证的是**自研前端 + PL↔PS 读通路**这两件赛题真正要看的工程能力，而不是为了替代 ¥169 的全向麦。
3. **要真上板跑通 PL 直采，先解决比特流加载**（第七节"关键事实二"），再解决搬运通道（AXI DMA 在出厂 dtb 里已 okay，`u-dma-buf` 本板已加载，二者都是候选），最后才谈 I²S 状态机。

## 十一、这六个接口各自是干什么用的

> 第一至六节回答的是"**能不能用、卡在哪一层**"，本节只回答"**它是用来干什么的**"。状态不在此重复登记，一律指回第一节与第六节；"卡在哪一层"用的①②③是第六节那三层。手册节号（完整版＝提取件 `41_manual_full_extracted.txt`）：**§4.7 JTAG、§4.8 以太网、§4.12 LED、§4.13 按键、§4.15 CAN、§4.19 SFP、§4.23 HEADER**；**MIPI 只有 Lite 手册有**（Lite §4.19＝提取件 `40_manual_lite_extracted.txt`）。提取件索引见 [[板端提取件台账]]。

### 一张表先看用途与归属

| 接口 | 干什么用 | 本板怎么接（手册原文／引脚） | 卡在哪一层 |
|---|---|---|---|
| **PL 网口**（第二路千兆） | 给板子**另一条独立的网络出口**：把现场设备（相机、PLC、执行器控制器）关在一个网段里，或让视频出流不与 SSH／控制流量抢带宽 | §4.8："其中一片以太网 PHY芯片为 YT8521连接至 FMQL30TAI 的 PS 端，一片以太网 PHY芯片连接至 FMQL30TAI 的 PL 端"。PL 那片给的是 **RGMII** 十二线（`PL_PHY_TX_CLK AD23`…`PL_PHY_RXD3 AE26`）＋ `MDC AE22`／`MDIO AF22` ＋ `PL_PHY_RESET AA13` | ②③（第六节 eth1 行） |
| **PL CAN**（CAN1） | **现场总线**：一对差分线挂多个节点、按报文 ID 仲裁，是电机驱动／舵机／关节／工业设备最常见的接口；用它可以把"一路路 PWM"换成"一条总线挂满执行器" | §4.15："一路连接到 PS 端 BANK500 的 IO 上， CAN 收发芯片选用了 TI 公司的 SN65HVD232DR 芯片， 工作在 3.3V。另外一路 CAN接口连接到 PL端"。PL 侧引脚 `IO_L16P_T2_12 AF15`（R）／`IO_L16N_T2_12 AF14`（D） | ②③；**CAN0（PS 那路）三层全齐、已实测注册**，可直接用 |
| **GPIO**（HEADER 14×2） | **绕开 USB 直接挂数字外设的唯一落点**：I²S 麦／功放、传感器、开关量、给 PL 自研模块留的观测点 | §4.23："集成了可测试接口，接口形式采用 2.54MM的插针接口。其中包含了 4 根 3.3V的 GPIO接口，12根 1.8V的 GPIO接口，用户可以根据自己的需求进行测试"。同族还有 §4.12 的 4 颗 PL LED（`J1/M6/H7/J8`）与 §4.13 的 2 个 PL 按键 | **只缺 ③**——`GPIO_XILINX`／`GPIO_SYSFS` 全 `=y`，**不用动内核**，见第十节 |
| **PS_JTAG** | 调试 PS 那 4 颗 A53（裸机／GDB／ijet），并且 §4.2 那组**配置加载模式**跳线（MIO2 级联／独立、MIO3~5 启动介质、MIO6 PLL bypass、MIO7/8 Bank500/501 电压）与它是同一套救砖知识 | §4.7："PS 端的 EMIO_JTAG 接口是一个 20pin 的插座 U18"，四线 `Z7_PS_TDO AD16／TCK AB15／TMS AB14／TDI AD15` | 现成（烧写与调试通路） |
| **PL_JTAG** | **往 PL 直灌比特流**，绕开 QSPI／SD／U-Boot／fpga_manager 整条链；也是 ILA（Integrated Logic Analyzer，把 PL 内部波形经 JTAG 读回 PC）的唯一入口 | §4.7："PL 端 JTAG 接口也是一个 20pin 的插座 U19"；板载 TYPE-C 仿真器**要先短接 J35**，且"不能将仿真器插到 PL_JTAG接口上"（防信号冲突）。§4.11 另写 PL 那路 USB UART **与 PL JTAG 共用这个 TYPE-C** | 现成 |
| **MIPI CSI** | 摄像头串行输入（D-PHY 上的 CSI-2，2 data + 1 clock lane）——视觉入流里最省引脚、带宽最高的一条，所以现代模组几乎只出这个口 | **完整版通篇 0 次 MIPI／CSI**；Lite §4.19 是座子 J16（SFW15R-1STE1LF）、PL **Bank12 1.8V**，另引 `CAM_GPIO`／`CAM_SCL`／`CAM_SDA`（配传感器寄存器的 I²C）／`CAM_CLK`，**LP 100Ω／HS 150Ω 匹配电阻要用户自选焊接** | 不排（本板按"没有"登记，见第一节与第十节） |
| **SFP 光模块 ×2** | **光纤上行**：几十米以上链路、与强电现场做电气隔离、单 lane 速率高于同长铜缆 | §4.19："用户可插入 SFP 光模块实现光纤通信"、"SFP模块默认配置为全速率（Full BW）模式"；J12 的 `GTX_LANE_SEL1`／`SEL2` 拉低分别选 SFP0／SFP1 进 bank112。**"光模块的 SDA、SCL 并没有连接到 FPAI 上，而是通过一个排针引出"**（→CON40） | ③＋**跳线四选一**（与 PCIe／SDI／SMA 抢同一个 GT bank），见第二节 |

### 用途侧的三条判断（**C 级：工程判断，不是实测结果**）

1. **CAN 的价值不在"多一路"，在"换一类外设"**。PS 那路 CAN0 已经三层齐全、`can0` netdev 在板上实测存在（见 [[我方在板外设#一、当前在板清单（A 级实测）|我方在板外设——一、当前在板清单]]），所以**要接执行器总线的话根本不用等 PL**；PL 那路的意义是"两个互不干扰的总线域"（比如一条走关节、一条走传感与按键），那是优化项不是前提。
2. **PL 网口与 HEADER GPIO 是同一道闸的两半**：两者都只要"自己编的比特流上板"就能动，而现在这条闸是堵的（[[PL位流重载通道失效]]、[[BOOTbin位流替换手术]]）。**GPIO 那半对我们更值钱**——它通向赛题要看的自研前端，网口那半通向的只是部署便利性。所以比特流一旦打通，先做 HEADER 引脚约束，eth1 排后面。
3. **JTAG 在这个项目里是主通道不是备胎**：U-Boot `loadbit` 空转、Linux 侧 fpga_manager 写不进去之后，自研比特流上板只剩两条没被实测否定——**FSBL 从 `BOOT.bin` 灌**（这条**已经在用**，现役带状态导出的位流就是这么装上去的，见 [[BOOTbin位流替换手术]]）与 **PL_JTAG 直灌**。JTAG 比 BOOT.bin 替换好的地方是**不动 boot 分区、可反复试错、还能挂 ILA 看内部波形**；代价是要占一个仿真器口（并注意 J35 与那两路 TYPE-C 复用）。

### 照抄引脚表前必读：手册自己有一处笔误

§4.15 的 **PL** 通道表里，发送那行信号名写成 `PS_CAN_D`（原文如此——PL 的表挂了 PS 前缀），与 PS 表同名。**做引脚约束按引脚号 `AF14` 为准，别按信号名**；这类标号问题在本手册不止一处（§4.14 说片选"通过 J12"、§4.22 说 SDI 片写在 J26，登记见 [[我方在板外设#四、板子本体的 SDI 电气侧（B 级，悟净开发板完整版硬件使用手册 V1.0_嵌赛）|我方在板外设——四、板子本体的 SDI 电气侧]]）。

### 本地判不了、已登记进第九节的三件

| 悬项 | 为什么本地判不了 |
|---|---|
| 第二路 GEM 是 PS 硬核（I/O 经 EMIO 穿过 PL）还是要 PL 里做软 MAC | 手册只给引脚表没写归属；`e0049000` 与 `e0047000` 同在 PS 地址段、只差 0x2000 是我**据此的推断**，不作数。芯片级那本《复旦微电子可编程逻辑产品.pdf》是 **6 页扫描图、无文本层**——"检索 0 命中"只说明读不到，**不说明书里没有** |
| PL 那路 CAN 的收发器是否在位、什么逻辑电平 | 手册只给 PS 那路标了 SN65HVD232DR／3.3 V；PL 那路只给引脚。而 Bank12 按 Lite §4.19 是 **1.8 V IO**，两者对不上时要不要电平转换、能不能转，都得看原理图与实物 |
| MIPI 座子到底在不在我们这块板上 | 手册层面已判"完整版没有"，但仓库那张带中文标注的板照同时标了 MIPI 与 EMMC（[[板子（除芯片）#四、源文件之间的口径差异（必须显式标注）|板子（除芯片）——四、源文件之间的口径差异]]），只能当位置辅助图。**目视一次就能钉死**，动作在第九节第一条 |

## 相关页面

[[板卡镜像实测取证]] · [[板端提取件台账]] · [[板子（除芯片）]] · [[芯片]] · [[os]] · [[音频]] · [[外设与资金申报改成设备信息]] · [[接口契约与数据通路]] · [[板级管线详图]] · [[FPGA自研模块清单]] · [[PL网口bring-up与GEM1EMIO]] · [[工具链与素材进README]] · [[验证方法学]] · [[状态源与决策记录]]
