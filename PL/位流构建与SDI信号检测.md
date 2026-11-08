# 位流构建与SDI信号检测

本页记 2026-10-09～10 两轮：把官方 FPGA 参考工程从"综合都跑不起来"推到**位流出得来**，以及在真板子上测 SDI 口到底有没有信号。取证标记沿用 [[官方demo时序基线与器件库补丁]]：**A** = 正本/实测，**B** = 推断，**C** = 边界或未取证。

**一句话（2026-10-10 更新）：不含 NPU 的纯视频位流已经构建成功并通过时序；但刷不进板子 —— 厂商提供的三条运行时重载通道全部失效，拿厂商自己那份位流做对照同样失败。详见 [[PL位流重载通道失效]]。**

工程位置 `S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga`，上位机 `S:/apps/llm/agentwork/build/`。工作区不是 git 仓库，所有改动靠 `C:\Users\takomi\AppData\Local\Temp\opencode\` 下的备份兜底。

---

## 一、板子实际身份

**A**（`ssh root@192.168.1.113`，登录口令见 [[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]]，**D-27** 单点，此处不复述值）：

```
/proc/device-tree/model         FMQLMP FMQL100TAI
/proc/device-tree/compatible    fmsh,fmsh-fmqlmp
uname -a  Linux U.FMSH 5.4.52 #3 SMP Fri Mar 13 13:44:29 CST 2026 aarch64
cpuinfo   4 × CPU part 0xd03 (Cortex-A53)
```

**A（2026-10-10 串口实证，板子自己说的）**：

```
U-Boot 2020.07-gd24dcccd-dirty (Oct 31 2025 - 14:58:27 +0800)
CPU: FMQL Plus FMQL30TAI, Revision Code:9
Model: FMQLMP FMQL100TAI
```

**→ 板子实际是 FMQL30TAI。设备树 `model` 写 100TAI 是厂商没改，与硬件无关。**

- **A**：U-Boot 自报 `FMQL30TAI`；`fpga info` 的 `Device name: FMQL30TAI` 也这么写。两处独立佐证。
- 资料目录叫 `03_FMQL30TAI` 是对的；**该改的是设备树 `model`**，已列入厂商问题单（[[PL位流重载通道失效]] Q5）。
- **C（别被名字带跑）**：Zynq-7030 的器件模型仍成立（LUT 数、封装都对得上），**但器件库补丁跟板型名无关，仍必须是 `ip_patch/100ai/` 那一对** —— 理由见 [[官方demo时序基线与器件库补丁]] 第七节：`030ai` 那套里 `AI_IN` 端口一个都没有，装上去必定失败。

---

## 二、位流构建：卡了两个真问题，都已定位

### 2.1 器件库补丁（A，细节见另一页）

症状是 PS7 IP 综合报 104 个 `named port connection 'AI_IN1622' does not exist`。根因两条：

1. **装错目录**：Vivado 读 `scripts/rt/data/unisim_comp.v`，不读 `data/verilog/src/`。
2. **装错版本**：`scripts/rt/data/` 里原本那份（410 928 B）是残缺构建，`AI_IN` 端口一个都没有；正确的是 `JFM_Kits/ip_patch/100ai/` 那对 3.4 MB 的。

修完 `ps_ai_processing_system7_0_0.dcp` 产出，`synth_1 status = synth_design Complete!`。

### 2.2 `build_bitstream.tcl` 自己的 bug（A）

```
get_files -quiet -filter {FILE_TYPE == "BD"}   →   返回空
```

`ps_ai.bd` 明明存在、按名字也能取到。**BD 拥有 21 个 IP 里的 8 个**，BD 从没被生成 → 那 8 个永远没有产物 → `synth_1` 连 `runme.log` 都不写就报 `SYNTHESIS FAILED`。这就是之前每次"只看到一句失败、看不到原因"的原因。

改成按路径 glob `sources_1/bd/*/*.bd` 之后，日志里出现 `BUILD: BD files = .../ps_ai.bd`，综合随即通过。

**B**：这条不是厂商的问题，是本地构建脚本的问题，但它把 2.1 的真实报错藏了很久 —— 值得记住这个模式。

### 2.3 `generate_target` 与 `IS_GENERATED`（A）

- `generate_target all <bd>` 返回成功但 `IS_GENERATED` 恒为 0，**这个属性别信**。
- 实测把 `bd/ps_ai/{hdl,synth,ipshared}` 整个删掉再 `generate_target`，三样按字节还原（`ps_ai_wrapper.v` 61 507 B、`ps_ai.v` 410 348 B）。内容是当前 BD 的正确输出，**不是陈旧产物**。

---

## 三、`AI_Mate` 的 stub 与 EDIF：一个想当然会踩的坑

**A**：Vivado 综合时同时读两个都定义 `AI_Mate` 的文件：

```
INFO: [Synth 8-6157] synthesizing module 'AI_Mate'  [rtl/AI_Mate_stub.v:15]
Parsing   EDIF File  [rtl/edif/AI_Mate.edif]
Finished  Parsing EDIF File [rtl/edif/AI_Mate.edif]
```

- `AI_Mate_stub.v` 是**端口桩**，带 `syn_black_box`，声明 321 个端口。
- `AI_Mate.edif` 是**实现**（71 313 177 B，只有 EDIF 没有 RTL）。

**这不是冲突，是标准 EDIF 流程**：桩给 elaboration 提供端口声明，EDIF 提供实现。我一度把 stub 改成仅仿真、想让 EDIF 成为唯一定义，结果直接 `module 'AI_Mate' not found` —— 桩是必需的。已恢复。

- **A**：`AI_Mate_no_detpost.edif`（47 312 469 B）**顶层名同样是 `(edif AI_Mate`**。换用它之后报 `DRC INBB-3 has undefined contents and is considered a black box`，**不是"模块不存在"**，而是 EDIF 内容没链进去。这条路也不通。
- **C**：`detpost` / `no_detpost` 到底对应什么板级配置，没有本地正本。要问厂商。

### 3.1 七个端口没接（A）

`WARNING: [Synth 8-350] instance 'ZGolo' of module 'AI_Mate' requires 321 connections, but only 314 given`

按 stub 端口表和 `ps_ai_peripheral.sv` 实例化做差集，正好 7 个：

```
pl_exhs  pl_exhs_vld  pl_exhs_ack  pl_row_en_b[3:0]  pl_col_en_b[3:0]
pl_buyi_error  pl_scan_pipe_clk
```

- **B**：很可能是厂商有意的（未用的 BIST/scan/exhs 通道）。工程里还有一批同类警告（`afifo_16i_64o_largebuf` 11/13、`proc_sys_reset_0` 7/10 与 6/10、`processing_system7_0` 352/370），看着像厂商工程本身就这么发的。

---

## 四、当前拦路虎：NPU 网表内部悬空（A，无法从 RTL 修）

```
BUILD: impl_1 status = opt_design ERROR
ERROR: [Opt 31-67] LUT2 缺 I0 连接   U0_ps_ai_peripheral/ZGolo/u_ai_io/s_data[10]_i_2
CRITICAL WARNING: [Opt 31-430] 109 个 FDCE 数据脚无驱动
```

全部在 `ZGolo`（= `AI_Mate`）内部：`u_ai_io/…`、`ddr_intf_u/…`。被点名无驱动的网络是 NPU 的 AXI：`pl_araddr`、`pl_awaddr`、`pl_ra_rdata`、`pl_rready`、`pl_awvalid`、`pl_bist_done`。

### 4.1 接口是连着的（A，逐级证据）

```
ps_ai.v:4150            .pl_araddr(processing_system7_0_M_AI_HP_pl_araddr)
ps_ai.v:3106            assign M_AI_HP_0_pl_araddr[26:0] = processing_system7_0_M_AI_HP_pl_araddr;
bd/ps_ai/hdl/ps_ai_wrapper.v:592   output [26:0] M_AI_HP_0_pl_araddr
bd/ps_ai/hdl/ps_ai_wrapper.v:1515  .M_AI_HP_0_pl_araddr(...)
rtl/ps_ai_wrapper.sv:423           output [26:0] pl_araddr
rtl/ps_ai_wrapper.sv:931           .M_AI_HP_0_pl_araddr(pl_araddr)
ps_ai_peripheral.sv:1442           .pl_araddr(pl_araddr)
ps_ai_peripheral.sv:1764           AI_Mate ZGolo(.pl_araddr(pl_araddr))
```

注意驱动源是 **PS7**：`ps_ai.v` 里 PS7 实例接的是 `.pl_araddr`（不是 `M_AI_HP_pl_araddr`，这个命名不一致容易看错）。

**A**：BD 生成产物删掉重建后字节一致，所以也不是陈旧文件问题。

**B**：悬空发生在 EDIF 内部，不是连接问题。

### 4.2 但"删掉 NPU"这条路是走不通的（A，2026-10-10 实测推翻）

**先说清楚一个后来才搞明白的架构事实，它推翻了我最初的绕行思路。**

寄存器通路是这样连的：

```
PS ─M_AI_HP─→ BD 互联 ─→ AI_Mate 的 pl_* (512 bit 自定义 AXI)
                                  │
                    ┌─────────────┘          │ ← 地址译码器在 EDIF 内部
                    ↓ fabric                    │    看不见、改不了
        frame_trans(S_AXI-Lite) ─→ frame_ctrl(S_AXI-Lite)
```

- **A**：`frame_ctrl` 是标准 AXI4-Lite 从口（`S_AXI_AWADDR[8:0]` 等），实例化在 `frame_trans.sv:199`；`frame_trans` 的 S_AXI 靠 **NPU 当透明桥**才连得到 PS。
- **A**：**NPU 不只是"一个加速器"，它是 PS 通往 PL 的唯一 AXI 端点。** 删掉它（连同 EDIF 里的译码器），`0x4000_0000` 整个窗口就没有从设备了。

实测后果（**A，三条都验证过**）：

| 操作 | 结果 |
|---|---|
| `dd if=/dev/mem … 0x400800b0` | `Bad address` —— 内核 `devmem_is_allowed` 挡掉，与位流无关 |
| `/dev/uio*` | 不存在 |
| `sdi_probe`（会开 `axi://zg330aiu?npu=0x40000000` 做 ICore 握手） | **把 PS 楔死**：SSH 与串口同时无响应，只能断电 |

而采集**必须**由软件开火，没有连续模式：

```verilog
// rtl/display/frame_ctrl.v:1001
frame_en <= 1'b0;//frame_en <= 1'b1;      ← 厂商把自动使能注释掉了
else if(dvp_vsync_start & frame_fetch_req)  ← frame_fetch_req 由软件写 0x04 置位
```

**→ 结论：拿不到 PL 寄存器就点不着火，SDI 帧就进不了 PS DDR。所以 NPU 不能删，这条绕行方案作废，必须回去修 `opt_design`。**（顺带回答一个常见误解：这**不是**"厂商就这么设计的"，厂商那份带 NPU 的位流下 `sdi_probe` 读 `0x88 fetch_cnt` 拿得到 140、写 `0x18` 也生效，通路本来是通的。）

### 4.3 厂商实例化漏接的 3 根输入（A，待验证）

这条是 4.2 之外唯一还没试过的假设，值得单独记：

```
WARNING: [Synth 8-350] instance 'ZGolo' of module 'AI_Mate' requires 321 connections, but only 314 given
```

按 `AI_Mate_stub.v` 的端口表与实例化做差集，缺的正好 7 个：

| 方向 | 端口 |
|---|---|
| **input** | `pl_exhs[7:0]`、`pl_exhs_vld`、`pl_buyi_error` |
| output | `pl_exhs_ack`、`pl_row_en_b[3:0]`、`pl_col_en_b[3:0]`、`pl_scan_pipe_clk` |

- **B**：输出未接无害，但**输入悬空读作 X**，常量传播穿过 X 是 `Opt 31-430`（FDCE 数据脚无驱动）的一个合理来源 —— 被点名的无驱动网络恰好是 NPU 的 AXI（`pl_awaddr`、`pl_araddr`、`pl_awvalid`…），也就是那 3 根悬空输入所在的那一组。
- **A（已实施并跑完，2026-10-10 01:47，结论＝不成立）**：`ps_ai_peripheral.sv` 里给这 3 根绑 `8'd0 / 1'b0 / 1'b0`，`build_npu_tieoff.log` 跑完了。**端口确实接上了**（`Synth 8-350` 从 `only 314 given` 变成 `only 317 given`），但 **`opt_design` 报的还是同一句**：`ERROR: [Opt 31-67] LUT2 缺 I0 连接 U0_ps_ai_peripheral/ZGolo/u_ai_io/s_data[10]_i_2`，同一批 `Opt 31-430`（101 条）也原样在，没有 `.bit`。**→ 悬空点在 EDIF 内部（`u_ai_io`、`ddr_intf_u` 这两层里，而且按 `s_data[10]/[14]/[18]/…` 每 4 位一组重复出现），跟实例化少接几根端口无关。这条假设到此关闭。**
- `build_bitstream.tcl` 新增 `WITH_NPU=1` 环境变量，用来切回带 NPU 的原始设计（默认 0＝纯视频）。

### 4.4 给厂商的问法

> **Q7（已按板型更正为 30TAI）**：FMQL30TAI，`AI_Mate.edif` 链进 `ai7030_edif_top` 后 `opt_design` 报 `ZGolo/pl_araddr[*]` 等 109 个 FDCE 无驱动（Opt 31-430 / Opt 31-67）。已确认 PS7 与 EDIF 的 `pl_*` 接口连接完整、BD 重新生成结果字节一致。是否需要特定板型或配置的 EDIF？什么条件下该用 `AI_Mate_no_detpost.edif`？
>
> 补充一条对定位这条报错很可能有用的事实：厂商自己的 RTL 里，`AI_Mate ZGolo(...)` 实例只接了 314/321 个端口，**漏接的 3 个输入是 `pl_exhs`、`pl_exhs_vld`、`pl_buyi_error`**（另外 4 个漏接的是输出，无害）。请问这 3 根保持悬空是设计意图吗？如果不是，我们准备先把它绑成 0 试一次。
>
> 另：能否确认 `AI_Mate` 的 `pl_*` 是**透明桥**（PS 访问 `0x4000_0000` 是穿过 NPU 落到 fabric 里的 `frame_trans`/`frame_ctrl`）？如果是，那 NPU 就不能当可裁剪模块处理，编不过时整条 PS→PL 通路都会断。

### 4.5 "NPU + 状态导出同片"到底卡在哪（A，2026-10-13 判定）

先把一个我自己先前说错的判断公开更正：**这不是"放不下"**。位流 payload 长度由器件配置决定而不是由设计大小决定（官方那颗含 NPU 的 `ai7030_edif_top.bit` 和我方不含 NPU 的 `ai7030_lite_pd1_20261010_032140.bit` 解出来的 payload **都是 5 979 868 B**；厂商 detpost 那颗是 5 980 412 B，BOOT.bin 总长 7 023 552 B），所以槽位从来不是瓶颈。

拦路的是 `opt_design` 里那句 connectivity check，而且它是**厂商网表自带**的性质，不是我们拷贝时弄坏的：

**A（本次自己跑的 md5，不是转述）**：

| 文件 | 我方树 `rtl/edif/` | 官方案例 `fdw/20260916/fpai_demo_fpga/rtl/edif/` |
|---|---|---|
| `AI_Mate.edif` | `28174d8040c5360c123a01ed97330963` | **同一个** |
| `AI_Mate_no_detpost.edif` | `e1b33a7cd7c0841d4a5f3a17f7bbebf2` | **同一个** |

也就是说官方交付的就是这颗悬空网表，而官方又有含 NPU 的成品位流 ⇒ **差别在流程里，不在网表里**。往官方 `JFM_Kits/ip_patch` 里找那个差别，只找到这些：

- 全目录 grep `AI_Mate` / `ZGolo`：**0 命中**（`.tcl`/`.cfg`/`.txt` 里一处没有）⇒ 没有针对 NPU 的专属补丁。
- `process_control/implementation_opt_pre.tcl` / `_post.tcl` 确实钩在 `opt_design` 前后，但它们只认 `JDY_ip_top_*` 那种单元：把预布线好的 `045ai/JDY_ip_top_0_route.dcp`（19 406 258 B）当黑盒恢复、并按 pblock 圈地（`resize_pblock ... -add SLICE_X80Y50:SLICE_X139Y149 ...`、`set_property PROHIBIT true [get_sites ...]`）。
- **`030ai/` 目录里没有这种 DCP**，只有器件库文件（`xc7z030ai.paspd`、`unisim_comp.v`、`Sitemap2.xml`）⇒ 我们这块 30TAI 拿不到"预布线 NPU 黑盒"这条现成路。
- `top.tcl` 是**混淆过的**（前 400 B 读不出 Tcl 语句），所以厂商 `opt_design` 到底还做了些什么，从这份交付里看不全。

**结论**：合并位流在**工程上还没被排除**，但它需要的不是"再省一点资源"，而是绕开一句对厂商网表成立、对 Vivado 是 fatal 的检查。可试的路，按代价从低到高（**10-13 写这张表时全部 B 级；10-14 已经跑了 1、2 和一次降级 DRC 的变体，判定见下面 §4.5.1**）：

| # | 做法 | 代价 / 风险 |
|---|---|---|
| 1 | `PRE_OPT_TCL` 里 `set_msg_config -id {Opt 31-67} -new_severity {WARNING}`（顺带 `Opt 31-430`），让 opt 过 | 最便宜，一行。风险：后面 place/route 可能换个 ID 再报同一件事；且真让悬空 LUT 输入进了布线图，行为由工具决定 |
| 2 | `set_property STEPS.OPT_DESIGN.SKIP true [get_runs impl_1]`，综合后直接 place | 一行。风险：QoR 变差、时序可能不过（我方那条 10 Hz 状态路径无所谓，怕的是 NPU 主频） |
| 3 | 拿 `synth_1` 的 dcp 进 `ecoshell`，把被点名的 LUT/FDCE 输入脚绑到常量，再 `write_checkpoint` 继续跑 impl | 真正的网表 ECO，和厂商 `runEco` 同源的做法。要写脚本并核 `connect_nets` 在 2018.3 的可用性 |
| 4 | 问厂商要 30TAI 的预布线 NPU DCP 或他们内部的 `opt_design` 设置（话术见 §4.4 Q7） | 不用动手，但要等 |
| 5 | **不合并**：两颗位流换着用 | 已就绪。`board-boot-swap.py` 走 SFTP＋md5＋自动回滚，实测换一次＝上传 7 MB（1.0 s）＋`cp`＋`sync`＋重启 |

**建议是 5 打底、1 顺手试**：这次要的是"摄像头有没有信号、什么格式"，那颗纯视频位流已经把这件事答完了（§6.8.11）；NPU 那颗只在跑模型时才需要。两者不同时使用，合并只省一次重启，不值得为它去动厂商网表。

### 4.5.1 10-14 实跑：#1 与 #2 都被证伪，堵点从 NPU 网表挪到 PS 侧（A）

跑的是隔离副本 `S:\apps\llm\agentwork\fpga-src\npu_merge_1014\`（`fpai_demo_fpga` 的完整拷贝，原工程的 `.runs`／xdc／`verilog_define` 现场一律没动）。入口：`run_npu.bat`（`WITH_NPU=1 BOARD_VARIANT=lite RESET_PD=1 JOBS=8`）与 `run_skip_opt.tcl`。

时间线（本机时钟）：11:45 起 → 12:00 **综合通过**（`synth_design completed successfully`，3 分 15 秒，peak 1 296 MB，0 Errors；日志里出现 `U0_ps_ai_peripheral/ZGolo/u_AI_Mate_top/{u_axi_2to1,U0_ddr2hp_itcn,buyi_icore_post_top_u0}` ⇒ NPU 真的进了网表）→ 12:03 钩子生效 → 12:04:09 opt 死 → 12:11 换成"跳过 opt" → 12:14 place 前置 DRC 死 → 12:18 再把那条 DRC 降级 → 12:23 place 内部检查死。**三次都死在同一件事上，而且第 2、3 次把真东西抖出来了：**

1. **`set_msg_config` 降级 ERROR 级消息在 2018.3 是不允许的**：`WARNING: [Common 17-239] ERROR Messages are prohibited to be downgraded. Message 'Opt 31-67' is not downgraded.` 钩子本身打进去了（`HOOK: implementation_opt_pre ...`）、`Opt 31-155`／`31-430` 确实降成了 WARNING、opt 的六个阶段（Retarget／Constant propagation／Sweep −6 994 颗／BUFG／ShiftReg／PostProc）也全跑完了，最后仍在收尾的 **Connectivity Check Task** 上 fatal。⇒ **表里第 1 行从原理上不成立**：只有 DRC check 的 `SEVERITY` 能改（`ai7030.xdc` 头四行的 REQP-44/46/52/56 就是这么干的），opt／place 的消息不能。
2. **表里第 2 行的属性名是错的**：run 对象上没有 `STEPS.OPT_DESIGN.SKIP`（实测 `ERROR: [Common 17-54] The object 'run' does not have a property 'STEPS.OPT_DESIGN.SKIP'`），`list_property [get_runs impl_1]` 的 86 条里只有 `STEPS.OPT_DESIGN.IS_ENABLED`／`.TCL.PRE`／`.TCL.POST`／`.REPORTS`／`.ARGS.*`。正确的闸＝`set_property STEPS.OPT_DESIGN.IS_ENABLED false`（已确认读回 `= 0`）。
3. **跳过 opt 后，place 的前置 DRC 列出 70 条无驱动网络**（`ERROR: [DRC NDRV-1] Driverless Nets`，报"the first 15 of 70"）：全在 `U0_ps_ai_peripheral/` 这一层——`pl_awdata[511:0]`（397 位没驱动）、`pl_awen[63:0]`（62 位）、`pl_araddr[26:0]`（全 27 位）、`pl_awaddr[26:0]`（16 位）、`pl_ra_rdata[31:0]`（31 位）、`pl_arinfo`／`pl_awinfo[5:0]`、`pl_arvalid`／`pl_arlast`／`pl_awvalid`／`pl_awlast`／`pl_bready`／`pl_rready`／`pl_ra_arready`／`pl_ra_awready`／`pl_ra_rvalid`／`pl_bist_*`／`pl_repair_*`，外加 `S1_AXI_HP_HC_WID[4:0]` 和一条 PS7 内部网络 `processing_system7_0/inst/PS7_i/PS7_inst_n_2315`。把 `NDRV-1` 也降成 WARNING 后，place 走到它自己内部的检查，报 `ERROR: [Opt 31-65] LUT input is undriven ... U0_ps_ai_peripheral/ZGolo/u_ai_io/s_data[10]_i_2`——**与 10-13 记的、这次 opt 点名的，是同一颗 LUT**。

**谁本该驱动它们（查到端口声明级，A；"为什么没实现"这一层是 B）**：
- `ps_ai_peripheral.sv` 两端都接了，不是 `ifdef` 改坏的——`pl_*` 在 `ps_ai_wrapper_u0`（行 1450～1487）与 `AI_Mate ZGolo`（行 1767～1791）各接一次；这份副本与原 `fpai_demo_fpga/rtl/ps_ai_peripheral.sv` 逐字节相同（`diff -q` 无输出）。
- BD 侧往下：`.../ps_ai_processing_system7_0_0/hdl/verilog/processing_system7_v5_5_processing_system7.v:17651` 是 `assign pl_arvalid = PS7_AI_OUT1868 ;`，`PS7_AI_OUT1868` 接的是 PS7 原语的 `AI_OUT1868` 端口。
- 而装进 `<Vivado>/scripts/rt/data/unisim_comp.v` 的那套（按第八节配方来自 kit 的 `ip_patch/100ai/`——**那个目录本机现在没有，只能确认已装进 Vivado 的这份**，3 458 329 B，`module PS7 (` 在 41 657 行）里，`AI_OUT1868` **全文只出现 2 次**：端口表（45 950 行）＋`output AI_OUT1868;`（50 478 行），**没有一句驱动**；全文件 `assign AI_OUT*` 计 0。
- ⇒ **悬空来自本地这套器件库的 PS7 模型"只声明 AI 端口、不实现驱动"**；`AI_Mate.edif` 是无辜的（它的 `u_ai_io` 只是这些悬空网络的下游）。本节上一段那句"差别在流程里，不在网表里"现在有了具体位置：**堵在 PS 侧，不在 NPU 网表里**。
- 旁证（**没验证，B**）：kit 的 `ip_patch/100ai/` 里还有 `unisim.btl`（2 124 794 B）、`unisims/*.btl`（含 131 383 B 的 `PS7.btl`）、`xc7z100ai*.paspd`、`zynq.{lib,padr,rtd,xng}`、`Sitemap2.xml`，而 [[官方demo时序基线与器件库补丁]] 第八节的安装配方**只 copy 了 `unisim_comp.v` ＋ `unisim_comp.lib` 两个文件** ⇒ PS7 黑盒的引脚方向／驱动信息有可能本来就缺一份。本次没动：那是改 Vivado 安装目录、会连带影响另一条会话正在跑的构建。
- **10-14 复核这条旁证的取材条件（A）**：那批文件**本机根本没有**——`fpai_demo_fpga/ip_patch/` 与本次副本的 `ip_patch/` 下都只有 `process_control` 一个目录（8 个 `*.tcl` 钩子），`100ai`／`030ai` 这两个名字只出现在日志文件名里（`build_full_100ai.log`、`build_full_030ai.log`）；在 `S:\apps\llm\agentwork` 下 `find` `unisim.btl`／`PS7.btl`／`*.paspd`／`zynq.lib` 全部为空，`jfmkits/JFM_Kits/ip_patch/` 里只有 `edif_transform`＋`ip_patch.cfg`＋`ip_patch_version.log`＋`time_check.txt`。⇒ 上面那句 B 既不能证实也不能证伪，**要试就得先从厂商把整套 kit 取回来**（本机不下大资源，下载归校机）。
- **同一堵墙 10-09 就撞过，而且是原工程正本、不是我的副本（A）**：`fpai_demo_fpga/build_full_100ai.log`（10-09 12:58 起、`variant=full reset_pd=1`、综合过、13:05:37 `opt_design failed`）末尾那条 ERROR 点名的 cell 与本次**逐字相同**＝`U0_ps_ai_peripheral/ZGolo/u_ai_io/s_data[10]_i_2`，前面 `Opt 31-430` 那批 `ZGolo/u_AI_Mate_top/ddr_intf_u/.../s_data_reg[*]` FDCE 也一致。⇒ 合并失败与板卡变体（full／lite）、与我这次的 `ifdef` 改法都无关；**下次要动合并，先读这两份日志再决定要不要花 20 分钟**。同目录还有一次更早的 `build_full_030ai.log`（10-09 12:18）是综合阶段 27 秒就 `Scripts Generated`／SYNTHESIS FAILED，属于器件库补丁没装对的另一条线，不在本节范围内。

**对上板意味着什么（这条最重要）**：表里第 3 行（ecoshell 把悬空脚绑常量）现在**不该做**——绑 0 之后 NPU 的请求通道就是死的，位流"含 NPU"只是拓扑上含，真跑推理 DMA 会挂，比现在两颗都不如。**唯一还有希望的是第 4 行**，而且要问得很具体：**30TAI 那套完整的 PS7／器件库数据（`unisim.btl`、`unisims/PS7.btl`、`xc7z030ai.paspd`、`zynq.{lib,padr,rtd,xng}`），或者他们内部编好的含 NPU 预布线 DCP**——不是"给个 `opt_design` 设置"能解决的，因为缺口在他们的器件库里，不在我们的写法里（本机这套 kit 只有 `unisim_comp.v` 被装进了 Vivado，其余文件压根没拿到，见上一条）。第 5 行（两颗换着用）仍是唯一已验证可用的方案。

**顺带答掉"加 NPU 到底放不放得下"（A，10-14 从 12:00 那份 `synth_1` 检查点直接出报告，不需要位流跑通）**：`npu_merge_1014/dist/utilization_zgolo_only.rpt`（`report_utilization -cells [get_cells U0_ps_ai_peripheral/ZGolo]`）——NPU 自己 **18 166 Slice LUT（占 7z030 的 78 600 的 23.11 %）、34 647 寄存器（22.04 %）、73 颗 RAMB36＋9 颗 RAMB18＝77.5 个 BRAM tile（29.25 %）、2 个 DSP**；同状态整片顶层＝23 169 LUT／39 523 FF／78 tile／9 DSP ⇒ **NPU 占 LUT 的 78 %、寄存器的 88 %**。
口径警告两条，别拿这组数和 `dist/utilization_lite_pd1_20261012_211546.rpt` 相减：① 这是**综合态**，报告自己注明"最终 LUT 数在物理优化后通常更低"；② 综合态报告里 BD／MIG／各 AXI IP 全列在 **Black Boxes** 一节、**内部资源不计入**，而那份 lite 是**布线态、含 OOC IP**（16 695 LUT／76.5 tile）。即便如此仍能把上一段那个判断钉死：**合并不受"放不下"限制**——粗估 NPU＋现有视频链 ≈ 35 k LUT（44 %）、BRAM ≈ 150／265 tile（57 %）、寄存器 ≈ 50 k（32 %），都在 7z030 的额度内。拦路的从来不是尺寸。

---

## 五、绕过方案：纯视频位流（`ifdef WITH_NPU`）

为了先把 SDI 视频推上板，`ps_ai_peripheral.sv` 里的 NPU 实例被 `ifdef` 包起来：

```verilog
`ifdef WITH_NPU
  AI_Mate ZGolo ( ... );
`else
  assign app_addr     = 29'd0;    // NPU 原来驱动的，就是 MIG 的输入
  assign app_cmd      =  3'd0;
  assign app_en       =  1'b0;
  assign app_wdf_data = 512'd0;
  assign app_wdf_end  =  1'b0;
  assign app_wdf_mask = 64'd0;
  assign app_wdf_wren =  1'b0;
`endif
```

- **绑死这 7 根不是可选项**：按 `AI_Mate_stub.v:94-105`，NPU 驱动 `app_addr/cmd/en/wdf_*`，消费 `app_rd_data*/app_rdy/app_wdf_rdy`。前一组正是 `mig_7series_0` 的用户接口输入，不绑就会把同一类 driverless-LUT 错误挪到 MIG 里。后一组是 MIG 的输出，NPU 走了就悬空，无害。
- **A**：视频通路不经过 NPU，也不经过这个 MIG —— `frame_to_ps_largebuf` 挂在 PS AXI（`M_AXI_GP0`）上，PS 有自己的 DDR。所以 SDI → 帧缓冲 → HDMI 不受影响。
- 定义 `WITH_NPU` 即恢复原设计。备份 `C:\Users\takomi\AppData\Local\Temp\opencode\ps_ai_peripheral.sv.bak_nonpu`。

### 5.1 结果：成了（A）

**这条判断是对的 —— 去掉 NPU 之后 `opt_design` 一路通到 `write_bitstream`。**

```
BUILD: BD files = …/sources_1/bd/ps_ai/ps_ai.bd
BUILD: synth_1 status = synth_design Complete!
BUILD: impl_1 status  = write_bitstream Complete!
BITSTREAM -> dist/ai7030_full_pd1_20261009_201512.bit  (5 980 029 bytes)
```

**时序与占用（`dist/` 下的两份报告）**：

| | 用量 | 占比 | |
|---|---|---|---|
| **WNS** | **+0.104 ns** | 通过 | TNS 0，**51 904 个端点 0 失败** |
| Slice LUTs | 16 494 / 78 600 | 21.0% | |
| Slice Registers | 15 173 / 157 200 | 9.7% | |
| BRAM | 76.5 / 265 | 28.9% | 75 RAMB36 + 3 RAMB18 |
| DSPs | 7 / 400 | 1.8% | |
| IOB | 133 / 250 | 53.2% | |
| **MMCM** | **5 / 5** | **100%** | ⚠️ **已用满，后面加东西必须重算** |

- **A（改动确实生效）**：在 `utilization` 与 `timing` 两份报告里搜 `AI_Mate` / `ZGolo` / `u_ai_io` / `ddr_intf_u` —— **一个都没有**。NPU 不是被优化掉了，是根本没进实现。
- **C（注意余量）**：**WNS 只有 +0.104 ns，等于零余量。** 这份位流能跑不代表任何改动都安全，动 RTL 前必须重跑时序。
- **C**：`MMCM 5/5` 用满，加不进去新的时钟资源。
- **A**：位流头部 `ai7030_edif_top;UserID=0XFFFFFFFF;Version=2018.3.1; b 7z030ffg676 c 2026/10/09 d 20:14:59`。`UserID=0XFFFFFFFF` 是未授权 Vivado 的默认值，与厂商位流的 `UserID=53210711` 不同 —— 能否在硅片上正常配置已列入厂商问题单（[[PL位流重载通道失效]] Q6）。

**产物位置**（工作区非 git 仓库，改动靠 `C:\Users\takomi\AppData\Local\Temp\opencode\` 下的备份兜底）：

```
S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga/dist/ai7030_full_pd1_20261009_201512.bit
S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga/dist/timing_full_pd1_20261009_201512.rpt
S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga/dist/utilization_full_pd1_20261009_201512.rpt
```

**唯一还没解决的问题是刷不进去** → [[PL位流重载通道失效]]。

---

## 六、SDI 有没有信号：实测结论是「没有」

### 6.1 探测原理（A）

厂商 `frame_ctrl` 的 0x000–0x0B4 **没有任何 SDI/GT 锁定状态位**，但有一条和真实帧垂直同步绑死的握手：

```
写 0x04 bit0   arm 一次单帧采集，并把 camera_wr_done 清零
读 0x58 bit0   camera_wr_done，该帧 DDR 写完成后置 1
```

链路：`frame_ctrl.v:747-755` 的 `camera_wr_done` 由 `frame_done_req_pos` 置位，后者来自 `frame_to_ps_largebuf` 的 `wr_done_pulse`，而它只能在 `frame_en` 起来之后触发 —— `frame_en` 需要 `dvp_vsync_start`，也就是 SDI 侧真实的帧垂直同步。所以 `0x58` bit0 从 0 变 1 就是"帧真的到了"的证据。

### 6.2 踩过的坑：`img_en` 门控整条通路（A）

第一次探测报 `NO FRAMES`，**但那个结论不可信**：

```
frame_trans.sv:338   assign dvp_vsync = resize_vsync & img_en ;
frame_ctrl.v:375     img_en <= 1'h0;        ← 复位默认 0
```

`img_en` 门控 `dvp_vsync`，不开就永远不会有帧 —— 典型假阴性。补上之后结论才成立。

同时 `frame_trans.sv:191` 是 `assign dvp_vsync_in = vtc_enable ? vtc_vs : cam_vs ;` —— `vtc_enable`(0xB4) 置位的话采的是内部测试图，探测结论与 SDI 无关。探测现在会一并报这两项。

### 6.3 实测（A）

```
img_en (0x18) was 0, set to 1 for the test
0xB4 vtc_enable : clear (taking cam_vs)
0x88 fetch_cnt  : 140          ← 与握手次数一致，AXI 写正常
0x58            : 恒为 0
handshakes completed : 0 of 80 attempts over 20096 ms
VERDICT: NO FRAMES
```

条件：SDI 插着源、板子在线、AXI 正常、`img_en` 已开、`vtc_enable` 关。

**结论：SDI 口上没有帧垂直同步。**

### 6.4 这个结论的边界（C，必须说清）

- 它是**间接**的 —— 测的是"帧有没有到达帧缓冲"，位置在 GT 锁定**之后**。分不开"根本没信号"和"锁上了但栅格不可用"。
- 答不了 GT 锁没锁、SMPTE 制式、分辨率、帧率。
- 厂商原有的 0x000–0x0B4 里没有这些信息；要确定答案需要 `rtl/sdi/sdi_status.v` 那套状态寄存器（0x0B8–0x0E4），而它需要能出位流。

### 6.5 第一嫌疑：GT 参考时钟引脚 —— 且我一开始选错了变体

`impl_constraints.xdc` 原文（**A**）：

```tcl
create_clock -period 6.734 [get_ports FMC_HPC_GBTCLK0_M2C_C_P]
set_property PACKAGE_PIN U6 [get_ports FMC_HPC_GBTCLK0_M2C_C_P]  ## WUJING BOARD
set_property PACKAGE_PIN U5 [get_ports FMC_HPC_GBTCLK0_M2C_C_N]
##set_property PACKAGE_PIN R6 [get_ports FMC_HPC_GBTCLK0_M2C_C_P] ## WUJING LITE BOARD
##set_property PACKAGE_PIN R5 [get_ports FMC_HPC_GBTCLK0_M2C_C_N]
```

- **A**：`6.734 ns` = **148.5 MHz**，即 3G-SDI 的参考时钟；与 `rtl/sdi/rx_sdi.v:183` 的注释 `// 148.5 MHz MGT reference clock input from the FMC SDI mezzanine board.` 一致。
- **A（重要，更正）**：厂商交付包里 **lite（R6/R5）是生效的那一行，`full`（U6/U5）是注释掉的**。而板上跑的那份厂商位流（`ai7030_top.bit`，与 `BOOT_Gen/ai7030_edif_top.bit` 逐字节相同，见 6.7）就是用这份 xdc 出来的，**并且它之前在这块板子上能出画面**。
  → **结论：不管板子被叫什么，证据指向 lite 才是这块板实际用的引脚。本轮一度把 xdc 切到 `full`，那是错的，已改回。**
- **C**：`6.734`/`U6,U5`/`R6,R5` 这些名字带 "WUJING"，说明这个 xdc 是跨板型共用的，靠改注释切换；厂商包里给的是 lite 版本。

### 6.5.1 但更可能是：摄像头输出模式被改了（A，现场信息）

2026-10-10 用户提供了关键现场事实，**改变了整个问题的性质**：

- **A**：SDI 口接线正确，**之前是能出画面的**。
- **A**：期间用 OBS 改过摄像头设置，**疑似把输出切成了 CVBS**（复合视频），而 CVBS 那路没接板子。
- **A**：开镜头盖后 LED 亮，但黑屏；按摄像头重置无效。

**→ 如果 SDI 输出被切成 CVBS，SDI 口上就没有任何信号**，与"一直黑屏"完全吻合。而摄像头重置按钮**不会恢复 OBS 菜单里的设置**，所以"按重置没用"是预期行为。

**这解释为什么本文前面所有的软件侧结论（0 帧、GT 未锁）都指向同一个症状，却查不出根因：根因在源端，不在板子上。**

- **B**：另有一种可能是 OBS 里设了"自动/跟随输出"，格式跟随所连显示器的 EDID 而变。这种情况下分辨率/帧率会被动改变，而不是彻底没信号。**建议 OBS 里显式固定 1080p30，不要用 Auto。**
- **A（格式与症状的对应关系，用于判读）**：

| 症状 | 含义 |
|---|---|
| 缓冲区全零、GT 从未锁定 | 没有信号，或线路速率超出接收范围 —— 指向源端模式设错 |
| 有数据但错行/撕裂 | GT 锁上了，几何不匹配（例如 720p 源配 1080p 行距） |
| 正常画面 | 格式正确 |

- **C（自动开火下的几何陷阱）**：自动开火时没人写几何寄存器，`write_ps_size`/`disp_ps_size` 保持复位默认值 **518400 字 = 1920×1080 YCbCr 4:2:2（4 147 200 字节）**。源若不是 1080p，行距会错，画面必然错位 —— **但仍会有数据，不会是全零**，这一点可用于区分两种症状。

### 6.5.2 板载 LED 是最直接的判据（A；映射 2026-10-16 更正，实测记录待复核）

这块板只有 2 个 LED，而且 `LED_MON=1` 时**厂商把它们专门用来看 SDI 锁定**：

```verilog
// ai7030_edif_top.v:115-118
// LED_MON=1: led[0]=rx_usrclk 在翻转(GT 参考时钟/恢复时钟), led[1]=rx0_locked(SDI 真的解出码流)
localparam LED_MON = 1;
assign led = (LED_MON == 1) ? {led3, led1} : led_ai;
//                    led[1]=led3=rx0_locked, led[0]=led1=rx_usrclk_cnt[25]

// rx_sdi.v:246 / :255
assign led3 = rx0_locked;            // ← smpte_sdi 的 rx_t_locked
assign led1 = rx_usrclk_cnt[25];     // 恢复时钟计数器翻转（心跳）

// constrs_1/impl_constraints.xdc:17-20
set_property PACKAGE_PIN J1 [get_ports {led[0]}]
set_property PACKAGE_PIN M6 [get_ports {led[1]}]
```

| 灯 | 引脚 | BANK | 信号 | 来源 |
|---|---|---|---|---|
| `led[1]` | **M6** | 13 | **`rx0_locked`** | `rx_sdi.v:246` ← `smpte_sdi` 的 `rx_t_locked` |
| `led[0]` | **J1** | 13 | 恢复时钟心跳（`rx_usrclk_cnt[25]`，慢闪）| `rx_sdi.v:255` |

> **2026-10-16 更正：本页最初把 J1/M6 与两个信号对应写反了**（把 `{led3, led1}` 的位序读成了 `led[0]=led3`）。证据链三处一致 —— 拼接式里 `led3` 在高位、厂商源码注释（`led[0]=rx_usrclk…, led[1]=rx0_locked…`）、厂商 xdc（`led[0]`→J1、`led[1]`→M6）⇒ **M6=锁定、J1=心跳**。旧表与旧解读作废；下面那条 2026-10-11 实测记录也要按新映射重读。

**2026-10-11 实测记录（原文照录）：M6 闪、J1 灭。**

- 按**更正后**映射重读：M6 闪 = `rx0_locked` 在抖（锁定/失锁/复位来回）；J1 灭 = 心跳计数器没走到第 25 位（恢复时钟被反复打断）。方向仍与"源端无有效信号（当时疑似 CVBS）"一致，但**这一条待下次上板复核**。
- 旧解读（"恢复时钟在翻 → CDR 锁了 + 只是格式认不出"）作废。
- **C（保留）**：两个灯的正/负逻辑没有板上手册佐证；两灯同款线，相对判读不受影响。

**更正后的判读表：**

| J1（心跳）| M6（`t_locked`）| 含义 |
|---|---|---|
| 灭 | 灭 | GT 没锁、恢复时钟也没活动 —— 参考时钟/输入层面 |
| **闪** | 灭 | 有恢复时钟但传输帧没锁上（无有效 SMPTE 流/格式不认）—— 常见于源端输出模式被改（如 CVBS）|
| 闪 | 亮 | 全链路通，问题在更下游 |

- **C（重要保留，方向不变）**：J1 闪**不能证明链路上真有信号**。它是自由运行计数器的第 25 位，GTX 在无有效输入时也可能输出漂移的恢复时钟，计数器照样会闪。**真正有意义的判据是 M6。**

**教训**：这类"厂商留的调试指示"应该在早期就找出来。LED_MON 这个参数就是厂商为排查同类问题准备的，我们之前绕了一大圈软件侧的弯，而它在 xdc 注释里明明白白写着。

### 6.5.3 自动检测是开着的（更正我自己的一个误判）

我一度以为制式被写死了，**这是错的**：

```verilog
x7gtx_sdi_wrapper.v:298  .rx_mode_detect_en  (1'b1),    ← 自动检测已启用
x7gtx_sdi_wrapper.v:347  .rx_mode_en         (3'b111),   ← SD/HD/3G 三种全开
```

所以 `rx_mode`（制式）和 `rx_bit_rate` 看起来像外部输入，实际它们是核的**输出**（检测结果经 `rx_mode_int`/`rx_m_int` 回读）。接收器在自动搜三种模式，M6 不亮（校正后映射）意味着**三种都没搜到**。

### 6.6 两份厂商位流的差分（A，2026-10-09）

`30tai_detpost` 与 `30tai_lite_detpost` 逐字节比较：

| 偏移区间 | 差异内容 |
|---|---|
| 130–142 | 头部元数据：构建时间 `2026/09/16 09:55:29` vs `2026/09/14 20:22:25` |
| 3 895 603–3 896 426 | 4 段，各 1–2 字节 —— **IOB 配置区** |
| 4 367 087–4 371 111 | 若干 1 字节 —— 路由 |
| 5 978 445 | 3 字节 —— 尾部校验 |

- **A**：除头部时间戳外，实体差异就是几个 IOB 配置字 + 路由 + CRC。**这就是换 GT 参考时钟引脚会产生的差异**，原先"B 级可能是引脚变体"的猜测可以关闭。
- **C**：两份各自对应 U6/U5 还是 R6/R5，**仍未从位流内部直接解出**。目录名是后加的，不能拿名字当证据（循环论证）。要坐实得解码位流里的 IOB 赋值，或两份各刷一次对比。

### 6.7 板上跑的根本不是这两份里的任何一份（A）

**这块要单记，是 6.3 那个"没有信号"最重要的背景。**

挂载 SD 卡引导分区读出来的实况：

```sh
mkdir -p /mnt/boot && mount -t vfat -o ro /dev/mmcblk0p1 /mnt/boot
```

`mmcblk0p1` 是 **FAT16、卷标 `NO NAME`**（不是裸镜像），里面有：

| 文件 | 大小 | MD5 | 文件日期 |
|---|---|---|---|
| `BOOT.bin` | 7 023 040 | `aca4612b…` | 2025-09-27 |
| `ai7030_top_disable_icap.bit` | 5 980 604 | `663c06c1…` | 2025-12-30 |
| `ai7030_top.bit` | 5 980 020 | `b1cf2f22…` | 2025-12-24 |
| `FSBL251210_ddr400_demo.out` / `bl31.elf` / `u-boot` / `Image` / `fmqlmp-verify.dtb` / `uEnv.txt` | — | — | 2025-10~12 |

位流头部的原文：

```
板上：ai7030_top;UserID=53210711;Version=2018.3;Patched=DISABLE_ICAP,VCCM;PatchID=32033.b; 2025/12/24 14:16:39
候选：ai7030_edif_top;UserID=53180205;Version=2018.3;Patched=DISABLE_ICAP,VCCM;PatchID=32494;  2026/09/16 09:55:29
```

- **A**：**顶层模块名不同**（`ai7030_top` vs `ai7030_edif_top`）、UserID 不同、PatchID 不同、构建日期差 9 个月。
- **A**：板上那份与我手上两份候选逐字节比，598 万字节里 **241 万字节不同**，且长度差 5 B。不是同一构建的引脚变体，是**另一版设计**。
- **A**：`0x400800b8` 读回 0 —— 板上确实没有我这轮加的状态寄存器，它跑的就是 2025/12 那版。
- **B**：板上烧的是 2025 年 12 月的老镜像，而 `fdw/20260916/` 交付包里的源码/位流是 2026 年 9 月的。**两者不是同一份东西**。这可能才是"厂商 demo 在别人那儿能跑、这份源码在我这儿出不来位流"的一个真实来源，值得单独向厂商核对"板上应该刷哪个版本"。
- **A（可恢复）**：原 `BOOT.bin` 和两份板上原始位流都还在 SD 卡上没动过，本地已另存 `C:\Users\takomi\AppData\Local\Temp\opencode\board_boot\`。**刷位流做实验是可逆的**。

> 顺带纠正一个容易犯的错：`/root/vpu/` 下那几十个 `.bit`（10 月 4 日）**不是** FPGA 织物位流，是 VPU 固件，由 VPU 驱动加载。织物位流只在 SD 卡 `p1` 里。

---

## 六点八、把 SDI 状态送进 PS：绕过不掉的 NPU（A，2026-10-12）

### 6.8.1 为什么必须绕开 NPU

NPU 编不出来（`opt_design` 失败，见 §6.7），而 NPU 是 PS 通向 PL 的**唯一** AXI 端点。于是形成死结：

- 走**寄存器**读 PL 状态 → 需要 NPU → NPU 编不出来
- 走 **DDR** 读 PL 状态 → 帧通道能写，但**没信号时就没有帧**，而"有没有信号"正是我们最想知道的事
- `/dev/mem` 被内核 lockdown（mode 2，运行时不可降级）锁死
- `/dev/uio*` 不存在；DT overlay 挪不动 udmabuf（节点无 `reg` 属性）

**结论：任何"读 PL 寄存器"的方案都必须绕开。** 唯一剩下的路是自己加一个往 DDR 写的小通道。

### 6.8.2 状态其实早就采到了

`frame_ctrl.v:1235` 早就有 `sdi_bus_meta <= sdi_status_bus` 在锁这条总线。**状态一直存在，只是卡在读不出来的 NPU 那条路上。** 厂商把探测逻辑做全了（`sdi/sdi_status.v`，160 bit，含实测几何），只是出口只有一个。

### 6.8.3 落点：DDR 首 4 KB

`rtl/display/sdi_status_axiw.v` —— 独立 AXI4 写通道，按定时器写 5 个 beat（设计意图每 100 ms 一次；**板上实际 1 ms 一次**，原因与修法见 §6.8.11）：

| 偏移 | 内容 | 作用 |
|---|---|---|
| `+0x00` | magic `0x53444953`（"SDIS"） | 区分"PL 写的"和全零/陈旧缓冲 |
| `+0x08` | `seq` 递增计数器 | 证明写入器还活着 |
| `+0x10` | `status[63:0]` | |
| `+0x18` | `status[127:64]` | |
| `+0x20` | `status[159:128]` | 上 32 位补零 |

**magic + 变化的 seq 合起来，让读侧不需要任何寄存器访问、也不需要任何前置状态就知道数据是新的。** 这对"开机后 3 秒内判断有没有信号"至关重要。

**地址布局**（`frame_ctrl.v:719`）：

```verilog
camera_wr_addr <= 30'h3010_1000;   // 原 30'h3010_0000，向上移 4 KB
```

首 4 KB 划给状态块。**这一步不做就是 bug**：两者都用 `0x30100000` 的话，第一帧就会盖掉状态 —— 而那正是我们用来判断"有没有帧"的东西。4 KB 正好一页，两者不共页，读侧 mmap 一次就够。

`rtl/display/sdi_status_export.v` 是复用/仲裁层，挂在 `S_AXI_HP2`。

### 6.8.4 仲裁策略是单向的，这是真的取舍

状态写**只在帧通道空闲时启动**，一旦拿到端口持有到突发完成。**帧路径永不被中途抢占** —— 那样会让帧 DMA 的 `aq_axi_master` 以为某 beat 被接受，下一帧静默写错地址。

| 场景 | 帧通道 | 状态写 |
|---|---|---|
| **无信号**（我们当前要诊断的） | 永远空闲 | **满速跑**（现役位流实测 1 000 次/秒，非设计意图的 10 次/秒，见 §6.8.11） |
| 视频流密集 | 几乎不空闲 | **可能被饿死** |

代价明确写在 `sdi_status_axiw.v` 的文件头注释里。**"有信号时状态读不到"是可接受的** —— 有信号时我们能直接看画面，不需要读状态。

### 6.8.5 两个 DRC 组合环：一个是自己的，一个是既有设计的

Vivado 报 `LUTLP-1`，第一次我猜错了，**猜错的教训值得记**：

**第一次猜测（错）**：以为环来自 `aq_axi_master.v:146` 的 `WR_FIFO_RE = ... & M_AXI_WREADY & ...`，把 ready 寄存一拍 —— 环还在。

**第二次（错）**：以为环来自可变索引 `status_bus[(beat-2)*64 +: 64]` 的桶形选择器 —— 改掉，环还在。

**真正的原因（自己的 bug）**：

```verilog
assign f_bready = m_bready;                        // ← 帧侧
assign m_bready = s_active ? s_bready : f_bready; // ← 端口侧，mux 的输入就是它自己的输出
```

`s_active=0` 时 `m_bready = f_bready = m_bready`，**经 mux LUT 自环**。报告里"1 个 LUT"、网络名 `ps_ai_i_i_149_n_0`（`_n_0` 是反相后缀）正是自环特征。

**修法**：`bready` **直接生成，不路由**。它只表示"我能收写响应"，两个 master 都没有理由拒绝：

```verilog
assign s_bready = 1'b1;
assign f_bready = 1'b1;
assign m_bready = 1'b1;
```

`awready`/`wready` 仍然寄存一拍再发给帧侧 —— 那条路径上的既有反馈是真的，避开它不改动厂商代码。

> **教训**：组合环找不到时，别猜。查网表（`get_nets`/`get_property LOAD_PINS`）才能定位；当时那个 LUT 已被优化掉，所以直接读 RTL 逐行排除更快。

### 6.8.6 顺带修掉的越界读

160 bit = 2.5 个 64-bit beat。原来的 4-beat 突发需要 `status_bus[192 +: 64]` —— **读过 160 位向量的末尾**，结果是无意义的 X。改成 3 个显式切片 + 5 beat 突发，越界在结构上不可能发生。

### 6.8.7 时钟频率写错了但不显形

毫秒 tick 一开始写成 `ms_cnt >= 999_999`，隐含"`aclk` 是 1 MHz"。但 `ai7030_edif_top.v:232` 是 `.sys_clk_200m (hp_clk)`，**实际 200 MHz**。

这类错误**不报错、不黑屏，只是让所有周期悄悄差 200 倍**。改成参数化：

```verilog
parameter integer CLK_HZ = 200_000_000
localparam integer MS_CYCLES = CLK_HZ / 1000;
```

### 6.8.8 "raw"的边界（用户提问，回答）

| 类别 | 信号 | 是 raw 吗 |
|---|---|---|
| **像素流** | `cam_rgb[23:0]`、`cam_hs`、`cam_vs`、`cam_data_en` | ❌ 不是。SDI 的 20-bit 码流在 `smpte_sdi` 核**内部**已完成解复用+解码，出来的是并行 RGB |
| **边带/状态** | `rx_eav`/`rx_sav`、`rx_line_a`、`rx_a_vpid`、`rx_crc_err_a`、`rx_ds1a`/`ds2a`、`rx_mode`、`rx_t_family`/`rate`/`scan`、`rx_bit_rate`、`t_locked`、`qpll_lock` | **半 raw** —— 解码过程中的中间量，比像素流更接近线上的东西 |

**真正的 raw（EDH 包、ANC 数据、20-bit 线元数据）拿不到** —— 必须把 `smpte_sdi` 换成裸串并行接收器，是另一个工程量。

而这些信号**没有一个**送到 `rx_sdi` 顶层端口，全在内部用掉了。`sdi_status.v` 挑出来的那 160 bit 就是唯一能把它们带出去的口子。

### 6.8.9 读侧

交付的是 `sdi_stat.py`（本地源 `S:/work/WCIS/workenv/sdi_stat.py`，板上 `/root/sdi_stat.py`，纯 stdlib，板上不编译）。传输有两条：优先 `open("/dev/udmabuf0")` 直接读偏移 0，每轮采样前写 `sync_for_cpu` 做 cache 维护；`/dev/mem` 只在 udmabuf 不在位时兜底（本板 `CONFIG_STRICT_DEVMEM=y`，兜底那条会 EPERM）。

```sh
python3 /root/sdi_stat.py                  # 单采样
python3 /root/sdi_stat.py 30 --every 200 \
        --jsonl /root/sdi_stat.jsonl       # 采样 30 s，逐行落盘供 PC 侧分析
```

**退出码：0＝采到信号，1＝全程无信号，3＝magic 不对（这颗位流没有状态导出），2＝参数错。** 行内容一屏可读：`NO-SIGNAL seq=843078/FRESH st=t0s0q1m1 geo=0x0 fper=0 pxclk=156.250MHz(gt-free-run) fps=- fld=- ppm=- loss=0 frame=static/nz0`，其中 `FRESH/STALE` 就是靠 `seq` 判断"这一轮 PL 有没有重新写过"。

按 `sdi/sdi_status.v:369-376` 原文解码，**读起来先看锁定链**：

```
qpll_lock → mgt_lock → t_locked(LED M6) → sig_locked
```

`sig_locked` 是去抖后的"有信号"，**回答"有没有信号"用它，不要用 `t_locked`**（后者会抖）。`loss_cnt` 记录丢失次数。

解码正确性用离线向量测试 `test_sdi_stat.py` 钉住（7 条：1080p50 实测、1080i 场/帧拆分、720p60/1.001、计数器死掉退回查表、无信号、锁定但无几何、未锁定但 GT 自由运行），**7/7 PASS**；板上实测读数见 §6.8.11。"有信号"那一支目前只有仿真和向量测试覆盖，板上还没跑过 —— 需要一个真信号源或 XS5→输入口自环（那条实验的完整前提在 [[板卡镜像实测取证]] 里，含"4 口全无反应也不能推出 RX 链坏"这条限制）。

### 6.8.10 最终产物（A，2026-10-12 21:15）

| 项 | 值 |
|---|---|
| 位流 | `dist/ai7030_lite_pd1_20261012_211546.bit` |
| 大小 / payload | 5 980 029 B / **5 979 868 B（= 槽位，严丝合缝）** |
| MD5 | `2A3983EC9FA8A49E0095165720D9415D` |
| BOOT.bin | `BOOT_status_export.bin`，7 023 040 B |
| BOOT.bin MD5 | `0F4F00E1DE0AF8F70299572BE622E45A` |
| WNS / TNS | **+0.072 ns / 0**（52 387 端点 0 失败） |
| WHS / WPWS | +0.057 ns / +0.062 ns |
| LUT / FF | 16 668（21.21%）/ 15 359（9.77%） |
| BRAM / DSP | 76.5（28.87%）/ 7（1.75%） |
| MMCM | 5 / 5（满） |
| `LUTLP-1` | **0 次** |

BOOT.bin 手术的**五项独立复验**（不信脚本自检，自己抽区域比对）全部 PASS：

1. 区外改动 **0** 字节
2. 区内与 `.bit` 字序翻转后逐字节一致，**0** 不符
3. 文件尺寸与原版相同
4. **槽位之后到 BL31 起点 `0x5E1910` 改动 0 字节 —— 未侵入 BL31**
5. `0x5E1910` 处仍是原样的 AArch64 指令 `81 D2 A0 18 A6 F2`

**该位流已于 2026-10-13 上板并验收**（换入过程与门禁见 `板端我方代码与产物台账.md`）：`BOOT.bin` = `0f4f00e1...` 这颗，换前的 `fd15bb85...` 存成 `BOOT.pre_swap.bin`，厂商原版 `BOOT.bak`（`aca4612b...`）与 `BOOT.bak2` 未动。上板后 PS 侧第一次不接显示器就读到了状态块（§6.8.11 有实测读数）。

**10-14 更正：这一颗已经不是现装了。** 上板 1 小时 32 分钟后（10-13 17:02:46 UTC）被另一条会话的发布脚本 `restore.py` 换回厂商原版，现场 `md5sum /mnt/boot/BOOT.bin`＝`aca4612b566738350a8c5edac0db1929`（含 NPU），`0f4f00e1…` 存成 `BOOT.before_factory_20261013T170246Z-8766769e.bin`；收据与 sha256 闭环见 [[板端我方代码与产物台账]] §十四"现装位流（10-14 复核）"。**后果：本节的状态导出通道现在在板上是关的**（`/root/sdi_stat.py` 实测打印 `PL status writer ABSENT: magic=0x00000000`），而 §4.5 那句"NPU＋状态导出同片还没排除"因此成了唯一能把两件事同时拿回来的路——10-14 起在跑它的第 1 号改法（`WITH_NPU=1` ＋ 把 `Opt 31-67` 降级），**结果在第 1、2 号上都是否定的，根因挪到 PS 侧：见新增的 §4.5.1**。

### 6.8.11 "每 100 ms"是假的：`PERIOD_MS` 的单位错（A，2026-10-13）

上板后第一件事就是拿 `seq` 验活，结果 1 秒涨了约 1 000 次，和注释里的 100 ms 差 100 倍。板上的精确读数（`/root/sdi_stat_1013b.jsonl`，142 行 / 30.03 s）：

| 项 | 实测 |
|---|---|
| 状态写频率 | **1 000.0 次/秒**（均值与中位数相同，min 995.3 / max 1 004.7） |
| `seq` 30 s 总增量 | 30 026，单调 |
| magic | 142/142 全对 |
| `t_locked` | 全程 0（没插信号，符合预期） |
| 恢复时钟计数 `cus_win` | 97 090 398～97 090 403 → **156.250 MHz**，GT 自由运行 |
| 帧区 4 KB | 全程 `nz0`、零变化（帧路径确实空闲） |

**根因**：`per_cnt` 每个 `aclk` 周期加一（＝数的是**周期数**），却被拿去和 `PERIOD_MS - 1`（＝**毫秒数**）比：

```verilog
if (period_hit) per_cnt <= 32'd0;
else            per_cnt <= per_cnt + 32'd1;   // 每周期都加
wire period_hit = tick_1ms && (per_cnt >= (PERIOD_MS - 1));
```

200 MHz 下 99 个周期只要 0.5 µs，阈值永远在第一个 1 ms tick 之前就过了 —— 于是 `period_hit` 退化成"每个 tick 都成立"，`PERIOD_MS` 无论填 100 还是 1 000 都不起作用。这跟 §6.8.7 那个"时钟频率写错但不显形"是同一族错误：**参数没生效，界面上一切正常**。

**修法**：让 `per_cnt` 只在 1 ms tick 上加一，它才真的数毫秒：

```verilog
if (tick_1ms) begin
    if (period_hit) per_cnt <= 32'd0;
    else            per_cnt <= per_cnt + 32'd1;
end
```

**验证**（`sim/tb_sdi_status_axiw.v`，Vivado 2018.3 xsim，参数与出货位流一致：`PERIOD_MS=100`、`CLK_HZ=200_000_000`、`GUARD_CYCLES=100_000`，AXI 从端是最简合法响应）：

| DUT | 仿真突发时刻 | 间隔 | 判定 |
|---|---|---|---|
| 修正前（`sim/buggy/`，留作正对照） | 1.500 / 2.500 / 3.500 … ms | **1.000 ms** | FAIL，1 000 次/秒 |
| 修正后（`rtl/display/`） | 100.500 / 200.500 / 300.500 ms | **100.000 ms** | PASS |

正对照跑出来的 1 000 次/秒与板上 1 000.0 次/秒**逐位对上**（0.5 ms 的首次偏移＝`GUARD_CYCLES`，仿真里也在）。所以这条链现在是：板上实测 ＝ 仿真复现 ＝ 源码推得，三处一致。

**这个 bug 的实际代价**：状态写有 1/1 的时间在争用 `S_AXI_HP2`（每次突发前还要等 0.5 ms 保护窗），而 §6.8.4 的仲裁是**单向、不可抢占帧通道**的 —— 频率错 100 倍意味着"有信号、流密集时状态可能被饿死"这句取舍的严重程度被低估了 100 倍。**没信号时它无害**（帧路径全闲），而"没信号"正是这条通路要回答的场景，所以上板的这颗可以先不重编。**修正只在源码里，需要重编位流才生效**（见 §6.8.12 待决）。

### 6.8.12 fps/像素时钟：未锁定时不许跟模式表比（A，2026-10-13）

`sdi_stat.py` 第一版把 `cus_win` 换算出的频率无条件当成像素时钟，于是没插信号时它拿 GT 的自由运行 156.250 MHz 去比 SD 的 13.5 MHz，打出 `ppm=+1.06e7` 这种荒谬数。量本身没测错（156.250 MHz 恰好是 GT 参考自由运行频率，是"锁定链活着"的好旁证），错在**归因**。现在按 `t_locked` 分三种来源标注：

| `t_locked` | `lk_usrclk_alive` | 标的来源 | `pxclk_used` | `ppm` | `fps` |
|---|---|---|---|---|---|
| 1 | 1 | `measured` | 实测恢复时钟 | 报 | 报 |
| 1 | 0 | `table` | SMPTE 模式表 | 报 | 报 |
| 0 | 1 | `gt-free-run` | GT 自由运行值 | **留空** | **留空** |
| 0 | 0 | `none` | 空 | 留空 | 留空 |

另一条同族修正：`fper_raw` 只在 `cam_vs` 上升沿更新，信号掉了以后**保留最后一个值**，所以帧率的两个输入必须一起门控，不然会拿"自由运行时钟 ÷ 上一轮的周期"算出一个像是读数的数。离线向量测试 `test_sdi_stat.py` 现 7 条，第 7 条就是照抄上面这组板上读数（`gt-free-run` + `ppm=None` + `fps=None`），**7/7 PASS**。

---

## 七、上位机

`S:/apps/llm/agentwork/build/`，交叉编译走 podman 里的 ICraft 3.39.0（`build/build-zg9.sh`），产物 aarch64：

| 二进制 | 大小 | 用途 |
|---|---|---|
| `sdi_probe` | 3 312 136 | SDI 探测。优先读 0x0B8 状态块；读不到就自动降级到 6.1 的厂商握手 |
| `sdi_live` | 11 020 320 | SDI → 硬件 VPU H.264 → 分段文件 |
| `sdicamera+yolov5+hdmi` | 12 720 536 | 厂商 demo，未改动 |

**A**：`sdi_probe` 已在板上跑通（就是 6.3 那组数据）。

### 7.1 直播编码走硬件 VPU，但绕开码率控制

**A（实测）**：这块板子的 VPU 硬件码率控制不生效 —— 请求 400 kbps 和请求 2 Mbps 产出**字节完全相同**的 222 kbps 流。所以"请求一个码率"等于什么都没请求。

改法是关掉码率控制、固定量化器：

```c
struct v4l2_rate_control rc {};
rc.rc_type = V4L2_OPT_RATE_CONTROL_MODE_OFF;   // 注意字段名是 rc_type
ioctl(fd, VIDIOC_S_MVX_RATE_CONTROL, &rc);
int q = qp;                                     // H.264 范围 0..51
ioctl(fd, VIDIOC_S_MVX_QP_EPR, &q);             // 注意这个 ioctl 收的是裸 int
```

两个 ioctl 都是尽力而为，被拒就明说并继续编码。参考 [[NPU调用链]] 里 ICraft 侧 `--frequency` 不可设那条 —— 同一类"硬件参数不按文档生效"的坑。

### 7.2 一个自己写错、已修的探测 bug（留档）

厂商寄存器降级路径初版只写 `0x04` 去 arm，没开 `img_en`，于是**无论有没有信号都会报 `NO FRAMES`**。见 6.2。凡是"用厂商寄存器反推硬件状态"，先确认所有使能位都被置上。

---

## 八、当前状态表

| 项 | 状态 |
|---|---|
| 板子身份 | ✅ 实测 **FMQL30TAI**（U-Boot 自报；设备树字符串 100TAI 是厂商没改） |
| SDI 有没有信号 | ✅ 实测**没有**（边界见 6.4） |
| 板上烧的是哪版位流 | ✅ 2025/12 的 `ai7030_top`，与交付包 2026/09 版**不是同一构建**（见 6.7） |
| PS7 IP 综合 | ✅ 已修（器件库，见另一页第七节） |
| `synth_1` | ✅ `synth_design Complete!` |
| `impl_1 / opt_design` | ✅ 去掉 NPU 后**通过**（含 NPU 时是 NPU 网表内部悬空，改不动） |
| **纯视频位流** | ✅ **`dist/ai7030_full_pd1_20261009_201512.bit` 5 980 029 B，WNS +0.104 ns，NPU 确认不在实现里**（见第五节） |
| **位流上板** | ❌ **三条运行时重载通道全断**（含用厂商位流做的对照实验）→ [[PL位流重载通道失效]] |
| GT 引脚假设 | ⏳ 变体差异已确认（A），但两份各自对应哪个引脚仍未解出 |
| 上位机三件套 | ✅ 交叉编译通过，`sdi_probe` 板上验证过 |
| 串口控制台 | ✅ COM6/CP210x/115200，`Hit any key` 可停在 `fmsh>`（u-boot 与 Linux 共用 UART0） |

---

## 九、动过的东西（都可还原）

**Vivado 2018.3**

| 文件 | 状态 |
|---|---|
| `scripts\rt\data\unisim_comp.v` + `.lib` | **已验证必需**，保留 |
| `data\parts\xilinx\zynq\devint\` 5 个器件库 + `xc7z030ai.paspd` | 猜着装的，**未验证必要性**，待逐个撤测 |
| `data\verilog\src\unisim_comp.*` + 1104 个 `.btl` | 装错目录，Vivado 不读，**可删** |

备份 `C:\Users\takomi\AppData\Local\Temp\opencode\vivado_backup_20261009\`，逐文件带 MD5。

**工程**

| 文件 | 改动 |
|---|---|
| `rtl\ps_ai_peripheral.sv` | NPU 实例包进 `ifdef WITH_NPU`，`else` 分支绑死 7 根网络 |
| `constrs_1\impl_constraints.xdc` | GT 引脚切到 `full`（U6/U5） |
| `build_bitstream.tcl` | BD 检测改 glob；先 BD 后独立 IP |
| `fpai_demo_vivado.xpr` | 已还原（EDIF 换回 `AI_Mate.edif`、stub 恢复综合） |

**板子**：只有 `/tmp/sdi_probe`。

---

## 相关页面

- **[[PL位流重载通道失效]]** — 位流做好了刷不进去：三条通道全断，含用厂商位流做的对照实验与厂商问题单

- [[官方demo时序基线与器件库补丁]] — 器件库补丁装到哪、装哪个的实测闭环（第七节）
- [[NPU调用链]] — ICraft 调用、NPU 频率不可设
- [[验证方法学]] — 验收判据
- [[接口契约与数据通路]] — PS↔PL、时钟复位
- [[工具链与素材进README]] — 交付包清单
- [[板卡镜像实测取证]] — GT 板型那一支的位流差分取证
- [[确认摄像头是否识别]] — 本轮任务的全流程总结（位流身份→死机归因→上板→读数→停手清单）