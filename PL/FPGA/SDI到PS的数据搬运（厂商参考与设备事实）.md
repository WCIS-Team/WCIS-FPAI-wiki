# SDI到PS的数据搬运（厂商参考与设备事实）

> **本页回答什么问题**：任务「FPGA实现HD-SDI至PS视频采集卡」（2026-10-14～16）的**厂商信息与设备信息收口** —— 这条链用到哪些厂商资产（版本与落点）、厂商自己那条 SDI→PS 通路长什么样、设备侧哪些事实与它相关、这次产物收在哪。
> **本页不回答**：RTL 设计细节（工程 `docs/设计说明.md`）、寄存器表（`docs/寄存器手册.md`）、上板步骤（`docs/上板检查.md`）。
> **判据等级**：A＝板上/本机实测原文，B＝厂商源码或文档直证，C＝推断或未取证（沿用 [[板卡镜像实测取证]] 的用法）。

**一句话**：把 SDI 接收链解出来的像素**不看格式、不判帧率、不丢帧（仅 FIFO 满时整拍丢弃）**地连续写进 PS DDR —— 设计准则是"只是数据搬运，不是采集卡"。工程本体在 `repos/sdi-cap`（2026-10-16 由 `S:/apps/llm/agentwork/sdi-cap` 迁入；）；收档快照在 `repos/FPGA HD-SDI to PS Video Capture Card/`。

## 一、厂商信息

### 1.1 这条链用到的厂商资产

| 资产 | 版本 / 标识 | 落点 | 本任务的用法 |
|---|---|---|---|
| FPGA 参考工程 `fpai_demo_fpga` | 20260916 交付包（`fdw/20260916/fpai_demo_fpga.rar`，6 594 786 B）| `S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga` | SDI 接收链、PS7 配置原型、厂商写帧器参考 |
| SDI 接收核 `smpte_sdi` | AMD/Xilinx LogiCORE **PG071 v3.0**（随 Vivado 免费），wrapper 属 XAPP592 系 | 同上 `rtl/sdi/` | **原样复用**；制式自动识别是核自带（收 PAL/NTSC 不由我们写）。唯一例外是它的 wrapper `rx_sdi.v`，见 1.3 |
| `frame_convertor.v`（复旦微） | 交付包内 | 同上 | 4:2:2 转换；**未改动** |
| PS7 器件库补丁（JFM Kits） | 版本组合与装法见 [[官方demo时序基线与器件库补丁]] | 本机 Vivado 2018.3 | 让 PS7 在 2018.3 里能综合/实现 |
| 客户说明《PS-PL AXI HP 接口：事务计数与复位语义》 | 2026-10-12，11 页 PDF | `fdw/PS-PL_AXI_HP_事务计数与复位语义.pdf`（收档 `research/` 有副本）| HP 口在途/复位语义**正本** → 结论登记在 [[PS-PL_AXI_HP口与复位语义]] |
| ModelScope 参考设计 `AIBS/fpai_reference_design` | 分支 `func_icraft3.36`（SDK Icraft 3.36.1）| 下载件收档 `research/modelscope/` | 厂商 PS 侧取帧协议 + 30TAI profile（见 1.2）|
| 厂商参考位流 `ver 25122301`（30TAI / ZHUGE 两包）| 直链在 ModelScope README 文末 | **两条都返 401**（缺下载站账号）| 拿不到；缺口登记在 [[哪些要跟厂商要]] |
| UG601 / UG602 / UG603 | 本地没有 | — | UG602 是 HP 复位类寄存器地址的唯一出处，**当前硬缺口**（[[PS-PL_AXI_HP口与复位语义]] 已登记）|

### 1.2 厂商自己那条 SDI→PS 通路（B，全部来自公开源码）

- **软件侧**（`sdicamera.hpp` / `sdi_input.hpp`）：取帧是**一问一答、每帧一次** —— 写目标地址 `0x40080050`（单位 8 B 字，代码 `addr >> 3`）→ 写 `0x40080004`=1 触发 → 轮询 `0x40080058`（bit0 done / bit2 error）→ 出错走 `0x70` 软复位、等 `0x74` bit0。完整登记（含 `>>3` 的更正）在 [[NPU调用链]]。
- **PL 侧**：厂商自己的写帧器 `frame_to_ps_largebuf` 挂 **`S_AXI_HP2`**（`fpai_demo_fpga/rtl/ps_ai_peripheral.sv:857` 起，`m00_axi_awid(S_AXI_HP2_AWID)` 这类端口直连）。本工程的 AXI 主机就是照这条通路写的。
- **和厂商的根本差异**（本任务取证）：厂商是**每帧由 PS 给地址、PS 取一次才搬一帧**；本工程是**PL 连续 push、PS 只管读**。对照表：

| | 厂商参考实现 | 本工程 `sdi-cap` |
|---|---|---|
| 谁决定往哪写 | PS 每帧写目标地址 | PL 环形缓冲自推进，PS 只读 |
| 节奏 | 一问一答（不取不搬）| 连续 push，收到就写 |
| 帧边界 | 无此概念（一次取帧事务即边界）| vsync 标记随数据流走（`FRAME_ADDR`）|
| 格式判断 | 不判断（裁剪/缩放是 PS 下发的参数）| 完全不判断 |
| 地址单位 | 8 B 字（`>>3`）| 字节地址 |

> ⚠️ **偏移别跨设计对号**：厂商基址 `0x40080000`，本工程寄存器在 `0x80000000`。同一个 `0x50` 两边含义完全不同（只写目标地址 vs 只读帧起始地址）。逐行对照在工程 `docs/调研与选型.md` 第九节。

### 1.3 复用边界（A）

- **复用**：GT 解串 + `smpte_sdi` + `frame_convertor` + 状态链。
- **厂商 RTL 只动过一个文件**：`rx_sdi.v` —— ①加法式引出 `y422_*`（16 bit 4:2:2；原 RGB888 路径逐字节不变）；②`cam_clk` 失锁兜底时钟 200 MHz → 100 MHz（时序原因，见 [[位流构建与SDI信号检测]] 与工程 §3.5）。差异文件在收档 `evidence/rx_sdi_y422_patch.diff`。
- **自研**：6 个模块（`sdi_px_pack` / `sdi_px_afifo` / `sdi_stream_wr` / `sdi_cap_regs` / `sdi_cap_cdc` / `sdi_cap_meas`）+ 2 个封装文件；清单见 [[FPGA自研模块清单]] 与工程 `README.md`。

## 二、设备信息（与本任务相关）

### 2.1 板子与芯片

- 复旦微 FMQL30TAI「悟净」板；PS7 按 **`xc7z030ffg676-2`** 同档配置（A）。身份三处互证（U-Boot 自报 / 设备树笔误 / 芯片档）见 [[位流构建与SDI信号检测]] 第一节与 [[板卡镜像实测取证]]。
- 运行时：Linux `U.FMSH 5.4.52`，4×Cortex-A53（A）。
- icraft 运行时头部自报 `device: 25122301`（A，2026-10-04 实测，[[NPU调用链]]）。

### 2.2 SDI 通路与跳线

| 事实 | 值 | 出处 |
|---|---|---|
| SDI 口 | **4 入 1 出**（BNC）；输入均衡 LMH0344、输出驱动 LMH0302 | [[我方在板外设]]、[[板子（除芯片）]] |
| GT 归属 | 与 PCIe / SFP / SMA **共用唯一 GT bank**（bank112），板上 MUX 片选 | [[板载接口与内核改造收纳进dev]] |
| 选 SDI（数据）| **J26** 的 `GTX_LANE_SEL0~3` 全接**高**（PCIe/SFP0/SFP1/SMA 是 J12 上相应 `GTX_LANE_SELn` 接低）| [[板载接口与内核改造收纳进dev]] |
| 选 SDI（时钟）| **J27** 把 **148.5 MHz** 送进 bank112 的 **CLK1**（J26 的 1、2 脚短接才是 PCIe 100M → CLK0）| 完整版手册跳线段；2026-10-16 核对原文（[[板载接口与内核改造收纳进dev]] 的 CLK0 误记已更正）|
| 参考时钟引脚 | 本工程用 **lite** 变体：R6/R5（与厂商交付包生效那对一致）| `constrs/gt_refclk_lite.xdc` |
| 承载模块 | `amvx.ko` 随开机加载 | [[PS/psrt&dev/os]] |

### 2.3 板载 LED 的判读（2026-10-16 更正）

- 厂商 `LED_MON=1` 的接线：**M6（`led[1]`）= `rx0_locked`（传输帧锁定）**、**J1（`led[0]`）= 恢复时钟心跳**（`rx_usrclk_cnt[25]` 慢闪）。本工程 RTL 同向；早先多处文档写反，已全部更正。
- 判读表与证据链在 [[位流构建与SDI信号检测]] 6.5.2 与工程 `docs/上板检查.md` 第三节。
- 2026-10-11 的实测记录（"M6 闪、J1 灭"）需按新映射重读，**待下次上板复核**。

### 2.4 PS 内存面与 AXI 口

- PS DDR `mem=1024M`（A）；`/dev/udmabuf0` 给用户态划出 **128 MiB** 连续窗口（A，[[板卡镜像实测取证]]）。
- 本任务数据面选 **`S_AXI_HP2`**（64 bit，4 px/beat）；寄存器面 `M_AXI_GP1` @ `0x80000000`。HP 口在途/复位语义与"不能假设什么"全部登记在 [[PS-PL_AXI_HP口与复位语义]]。
- PS7 只开 FCLK0 = 50 MHz；100 / 200 MHz 由 PL 内 `clk_wiz_0` 产生（工程 `docs/设计说明.md` 第三、四节）。
- 为什么 AXI 主机跑 `clk_100m` 而不是像素时钟：`cam_clk` 会随 GT 锁定状态**换源变频**，在途事务跨时钟源是厂商客户说明里点名的挂死场景（同上）。

## 三、本任务自己的验收数字（A，2026-10-15/16）

| 项 | 值 |
|---|---|
| 带宽 | 链路上限 64 bit × 100 MHz = **800 MB/s**；仿真实测 **150.91 MB/s**（1080p30 所需 124.4 MB/s 的 **121.3%**）|
| 仿真 | 行为级 19 套件 + 寄存器 52 项全 PASS；**门级（综合后网表 + UNISIM）与行为级逐项相同** |
| 位流 | `sdi_cap_lite_20261015_230629.bit`，md5 `01712DB8DE9329ABB4706781A83AFB19`；WNS 2.388 / WHS 0.049 / WPWS 1.100；DRC 0 错 25 警 |
| FIFO 落点 | 布线后网表探针：`u_px_fifo` = 2 × `RAMB36E1`，`LUT as Distributed RAM` = 0（悬案定案）|
| BOOT.bin 候选 | 工程 `dist/BOOT_sdi_cap_20261015_230629.bin`，md5 `03AB070C241D17C5BC912EE713CD81E8`；拼接可复现、槽外字节不动（`evidence/boot_splice_verify.txt`）；**未上板** |
| 驱动 | `ps/sdi_cap.c/.h`；x86 语法级编译干净（WSL gcc 15.2，**非** aarch64 真编译）|

## 四、落点

- **工程本体（权威、可编译）**：`S:/work/WCIS/repos/sdi-psddr/sdi-cap`（2026-10-16 由 `S:/apps/llm/agentwork/sdi-cap` 迁入；BOOT 候选镜像同在 `dist/`。`S:/work/WCIS/sdi-cap` 这个中间位置不存在，10-17 改正，见 D-54）。
- **收档目录（快照，2026-10-16 建）**：`S:/work/WCIS/repos/sdi-psddr/FPGA HD-SDI to PS Video Capture Card/`
  —— `bitstream/`（位流 + BOOT.bin 候选 + md5）、`ps/`（驱动）、`docs/`（五份文档）、`evidence/`（仿真/构建/探针/拼装/编译原始输出）、`research/`（HP 说明 PDF + ModelScope 原件）、`src/`（源码快照）、`tools/`（拼装脚本）；根上 `README.md` 与 `MD5SUMS.txt`。
- **仍然没做的**：上板。步骤：换 BOOT.bin → **先看灯**（判读见 2.3）→ 读寄存器 → 跑驱动；判据在工程 `docs/上板检查.md`。

## 相关页面

- [[位流构建与SDI信号检测]] —— 板子身份、LED 判读、`cam_clk` 时序陷阱
- [[PS-PL_AXI_HP口与复位语义]] —— HP 口语义正本收口
- [[NPU调用链]] —— 厂商取帧协议与 icraft 运行时
- [[哪些要跟厂商要]] —— 缺口清单（位流 401、UG602 等）
- [[板载接口与内核改造收纳进dev]] —— GT bank112 与跳线
- [[我方在板外设]] / [[板子（除芯片）]] / [[芯片]] —— 设备事实
- [[板卡镜像实测取证]] —— 板端读数正本
- [[SDI转HDMI转换器]] —— 同板另一个纯 PL 的 SDI 工程
- [[魔改厂商视频流程部署记录]] —— 厂商视频链路的部署记录
- [[官方demo时序基线与器件库补丁]] —— 器件库补丁与官方基线
- [[PL位流重载通道失效]] / [[BOOTbin位流替换手术]] —— 位流替换通道
- [[FPGA自研模块清单]] —— 自研模块职责
- [[工具链与素材进README]] —— 厂商素材落点
