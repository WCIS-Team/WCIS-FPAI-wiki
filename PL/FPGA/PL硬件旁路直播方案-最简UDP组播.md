# PL 硬件旁路直播方案（方案 B 简化版：TEMAC，TX-only）

> 目标：SDI 视频在 PL 内完成 MJPEG 编码后，**数据面全程不经过 PS**，直接从 PL 侧网口（YT8521，RGMII）以 UDP 推到接收端。PS 最多做一次性配置，也可以完全不做。
> 板卡：FMQL30TAI676H 悟净（完整版），192.168.1.113
> 日期：2026-10-25（原文由豆包生成 2026-10-25；本版按盘上实测记录修订）。**2026-10-26 加了实验 A 的本机实测：全部读数集中在 §16，正文只留结论。**
> 选型原则：PL 侧怎么简单怎么来——不做 RTP/RTSP、不做 ARP、不做 TCP、不做 RX、不做 DMA、不做 MicroBlaze、不挂 Linux 网络栈。
>
> **命名更正**：原标题写"方案 C"。`wiki/dict.md:33` 里已有的口径是 **方案 A＝PS GEM 经 EMIO 出 PL 口（配 GMII-to-RGMII 核）**、**方案 B＝TEMAC（AXI Ethernet Subsystem）放 PL、不占 PS GEM**。本方案是后者的"只发不收、不挂 axienet"简化版，所以叫 **方案 B 简化版**。

---

## TL;DR（先看这十条）

**拦路项（不解决就只能做到 M3，上不了真链路）**

1. **自研 MJPEG 编码器不在本仓，盘上不可核。** 队友不做 git 同步。没有它的接口契约（AXIS 位宽、每帧是否给 `tlast`/`tuser`、瞬时与平均码率、Q 值能否在线改、资源占用），FIFO 深度、分片数、水位阈值、丢帧点全都只能拍脑袋。**这是第 0 号依赖。**
2. **SDI 口现在没有帧。** 板上实测 `0x58` 恒为 0、80 次握手 0 次成功、`VERDICT: NO FRAMES`（A，`wiki/todo/位流构建与SDI信号检测.md`）。真 SDI 源这条要等 GT 参考时钟那件事查完才能走。**缓解：M1 起改用厂商内部测试图（`0xB4 vtc_enable`），不依赖 SDI。**
3. **含 NPU 的位流：队友那边已经做好了，但我方看不到"怎么做的"（2026-10-25 更新）。** 我方自己的尝试至今没有一次跑通 `opt_design`——**盘上有记录的尝试是：10-10 给 EDIF 那 3 根悬空输入绑常量（`:181`）＋ 10-14 的 #1 降级 `set_msg_config`、#2 跳过 `opt_design`、以及一次降级 DRC 变体（`:212`）**，全部失败或作废。**上一版写的"十次全失败"里没有"十次"这个记录，那是我编的，已删。****根因也已改判**：10-14 追到端口声明级后，堵点在 **PS 侧**——本地装的这套器件库里 `processing_system7_v5_5_processing_system7.v:17651` 是 `assign pl_arvalid = PS7_AI_OUT1868 ;`，**模型只声明 AI 端口、不实现驱动**；`AI_Mate.edif` 被判**无辜**（`位流构建与SDI信号检测.md:234-238`）。所以别再照"EDIF 悬空"去修。现在板上能跑 YOLO＋直播的那颗是**厂商原版位流**（`BOOT.bin` md5 `aca4612b…`），也不是我方重建的。⇒ 缺的东西变了：**不再是"能不能构建"，而是"构建流程能不能交接"**。三条路按对我方侵入度排序：① 队友给一次性工程快照（zip，不需要 git）＋失败两条 `Opt 31-67/430` 在他们那边是怎么消掉的；② 队友只给产物＋构建日志/Tcl（我方无法加自己的逻辑）；③ 队友代跑我方提供的增量 RTL＋XDC 并回传 `.bit`（我方不必拿到全工程，但每次改版都要过他们一次）。**本方案要在 PL 里加 TEMAC＋分帧器＋packetizer ⇒ 只有 ① 和 ③ 能用；② 只能维持现状。** 要拿最小改动先验证，就走 ③：M0 那个最小资格工程正好是可以单独交给他们跑的东西。详见 §14-Q6。

   **另有一条能立刻缓解这条拦路项的路，本方案原来漏了**：`位流构建与SDI信号检测.md:220` 的**做法 5「不合并，两颗位流换着用」已经就绪并有实测**——换一次＝上传 7 MB（1.0 s）＋`cp`＋`sync`＋重启，走 `board-boot-swap.py`（SFTP＋md5＋自动回滚）。⇒ **不必等含 NPU 构建闭合**：旁路演示用我方那颗（YOLO 下线），跑模型的演示切回厂商那颗，代价只是每次重启一次。这也让 §12 末尾那条"位流二选一"从**拦路项降级成运维选择**。

**必改项（原方案里会直接把链路做死的）**

4. **切帧从"可选"改成必做**：PL 里必须有 JPEG SOI(`FF D8`)/EOI(`FF D9`) 分帧器，不能假定编码器给边界。
5. **packetizer 必须加 `WAIT_LEVEL` 门（攒够一整片再发）**：千兆线比编码器快，直通式打包必然在帧中间把 FIFO 抽干，产生 mid-frame underrun（MAC 半途没数据）。
6. **字节序统一改成大端**：原方案私有头写"小端"，但 RTL 字面量 `16'h8000` 按 AXIS 送出来就是 `80 00`＝大端。照原文写，接收端永远读不到"末片"位。
7. **`devmem` 这条路在本盘上是死的**，原方案 §9 用它做初始化。改成厂商同形的用户态 `mmap("/dev/mem")`，并把 TEMAC 寄存器落在**厂商已经用通的那个 16 MiB 窗口内**（`0x4010_0000`）。上板前先跑只读探针。
8. **溢出策略按你定的：丢帧 + 降画质**，具体行为见 §4.6（含 `frame_id` 照常推进、残缺位 `info` bit14、`drop_cnt` 计数）。
9. **时钟没有余量**：纯视频位流已经 **MMCM 5/5 用满、WNS 只剩 +0.104 ns**（A）。~~RGMII 还要 125 MHz＋200 MHz 两个新时钟~~ **更正（A，§16.3）：只要 125 MHz 的相位对——`gtx_clk` ＋ `gtx_clk90` 同为 8 ns，网表里没有 `IDELAYCTRL` 就不需要 200 MHz**。所以这一条的真实内容是"**往已满的 MMCM 里再挤一路 90°**"，不是"两个新频率"。这一条必须在 M0 之前想清楚来源。

**已清掉的一条（本轮实测，A，全在 §16）**

10. **TEMAC 到底落不落得了地——不用等别人回答，已经自己验完了。** 本机 Vivado 2018.3.1＋`xc7z030ffg676-2`：TEMAC 设 `Physical_Interface=RGMII` 能建、能生成、能综合，5 644 个 leaf、网表里 `[Netlist 29-180]`（"不支持的原语"）命中 0 条；用的全是 7 系列原生件。原来压在第一位的那条"器件库缺 ODDRE1/IDDRE1"的资格风险**是错的**（那两颗是 UltraScale 件，7 系列不用；我数的还是错的库），已撤销。**没证到的仍然没证**：place／route／WNS／位流、以及两颗 bank 的实际 VCCIO（§16.6）。

---

## 0. 前提与证据（分级：**A**＝盘上实测／正本原文，**B**＝由 A 推断，**C**＝未取证／待查，**D**＝盘上根本没有）

| # | 前提 | 等级 | 出处与说明 |
|---|---|---|---|
| P1 | 自研 MJPEG 编码器存在但拿不到（队友拒绝 git 同步） | **D（本仓内）** | 全仓无该 RTL 的任何副本。所有依赖它参数的设计项一律标"待契约" |
| P2 | SDI 口当前无帧垂直同步 | A | `位流构建与SDI信号检测.md:321`（§6.3 板端实测）原文：`handshakes completed : 0 of 80 attempts over 20096 ms` |
| P3 | 位流长度不是拦路项 | A | 我方 `dist/` 连续 15 次构建均 5 980 026 B，同步字在 158，payload **5 979 868 B＝BOOT.bin 槽位**；`加逻辑不会让位流变大`（器件配置容量定死，wiki `BOOTbin位流替换手术.md` §6.5） |
| P4 | PL 运行时重载通道全废，只能走 BOOT.bin 手术 | A | `PL位流重载通道失效.md`：`fpga loadb` 报 Error 1、`fpga_manager` 报 `Timeout waiting for PCFG_DONE`；本机无 JTAG |
| P5 | PS 能访问 PL 寄存器面，走的是用户态 `mmap /dev/mem` | A/B | strace（`板卡镜像实测取证.md:459-470`）：openat("/dev/mem", O_RDWR\|O_SYNC)=8 → mmap(NULL, 16777216, …, 0x40000000) 与 …, 0x80000000；`ioctl` 全程只有 `TCGETS`。⇒ **厂商链就是"无内核驱动、mmap 直读写"**，`devmem`／`dd` 的 `Bad address` 只出现在 `read()` 路径 |
| P6 | 读一个位流里不存在的从设备 ⇒ PS 楔死只能断电 | A（事故）／B（归因） | `sdi_probe` 在不含 NPU 的位流上开 `axi://zg330aiu?npu=0x40000000` 把整机楔死 |
| P7 | PL 侧网口 15 个球号 | A | 手册抽取件 `wiki/PS/board_extract/41_manual_full_extracted.txt:195-235`（§4.8）——本轮逐个复核：15 个球号 AD23/AD26/AF24/AF25/AA24/AB24/AC23/AA25/AB26/AC26/AE25/AE26/AE22/AF22/AA13 **全部在该区间内** |
| P8 | ~~"Bank13／VCCIO 1.8V／表 4-12"这三条出处不存在~~ → **Bank 已由工具反查（§16.4）：14 根在 Bank 13、`AA13` 在 Bank 12；VCCIO 仍然没有出处** | **A**（Bank）／**D**（VCCIO 出处） | 手册抽取件 `wiki/PS/board_extract/41_manual_full_extracted.txt:221-235` 那张表确实只有 3 列（信号名／引脚号／备注），**没有表号、没有 Bank、没有 VCCIO**——原判断"出处不存在"到这一步是对的；但 Bank 不必靠手册：**`report_io` 直接读得出来**（§16.4）。VCCIO 只有原理图／厂商能给，就是 Q1 |
| P9 | RGMII 不能用 LVCMOS33 | A | 盘上唯一相关硬记录：PS7 IP `case/PS_AI IP/processing_system7_v5_5/xgui/validate_update.tcl:170` — *"LVCMOS33 (3.3V) is not supported for RGMII interface… Recommendation is to use 1.8/2.5V IO."* |
| P10 | ~~JFM 器件库里查不到 ODDRE1／IDDRE1 ⇒ TEMAC 落不了地~~ | **作废（A，§16.1／§16.3）** | 三条都错：① `ODDRE1`/`IDDRE1` 是 **UltraScale** 原语，7 系列 Zynq 的 TEMAC RGMII 前端用的是 `ODDR`/`IDDR`/`IDELAYE2`/`BUFIO`/`BUFR`（§16.3 实测网表，`ODDRE1 present = 0`）；② 我数的 `030ai/zynq.lib` 不是这条构建路径用的库——正本工程走 `xc7z030ffg676-2` ＋ Vivado 自带 unisim（`repos/sdi2hdmi/build.tcl:174`）；③ "盘上没有任何 `axi_ethernet` IP 副本"也是错的，Vivado 就装着它（9 颗 ethernet IP 在库，§16.2），只是它综合不过。**保留这一行只为记录改判** |
| P11 | MMCM 已用满 5/5，WNS +0.104 ns | A | `位流构建与SDI信号检测.md:285-293` 纯视频位流的利用率表（`:287` `WNS +0.104 ns`＋`51 904 个端点 0 失败`；`:293` `MMCM 5/5 100%`；`:297` 把 MMCM 这条标成 C 级余量提醒）。**行号二次更正**：上一版这里写 `:263-273`／`:269`，并且"更正"成"`:285-293` 是六、SDI 有没有信号"——**那句更正本身是错的**：现文件里六节从 `:312` 起，`:285-293` 正是这张利用率表 |
| P12 | 现役 PS 软编 JPEG 的码率量级 | A | `魔改厂商视频流程部署记录.md:99`（960×540·q60·10 fps，**25.5–27.1 kB/张**）与 `:150`（1080p 高熵 VPU 硬编 ≈19 ms/帧、**2.35 MB/帧**）。⇒ **注意：2.35 MB 是 VPU 的读数，不是 PL 编码器的**，这里只当量级参考 |
| P13 | 网络卸载与 FPGA 图像压缩不在本周期自研范围 | A | `状态源与决策记录.md` **D-02**；`风险与完成判据.md:144`（O2 硬件图像压缩）／`:146`（O4 网络协议卸载）；`任务卡与台账规范.md:158`／`:193`（backlog #3 TOE/MAC（触发条件＝**实测证明网络/压缩是端到端瓶颈**）；`全链路逻辑基线.md:180` "当前无此证据" |

> **P13 是本方案在项目台账里的真实位置**：它是下版 backlog 的候选卡，不是当期任务。要转正，按 D-02 的回退条件必须先给"PS 网络栈／软编已成为端到端主因"的实测数据（原话：*真实码率、OBS、长会话三项从未测过*）。**建议 M0–M3 期间不动台账**，拿到 M4 的实测数字再立卡。

---

## 1. 目标与非目标

**做**

- PL 内：（队友的）MJPEG 编码器 → **JPEG 分帧器** → 帧打包器 → TEMAC → RGMII → YT8521，单向推流。
- 接收端：PC 上一个 Python 脚本，收 UDP、重组 JPEG、显示。
- 千兆固定速率、私有分片格式（自己定、自己收）。
- 溢出时**丢帧 + 降画质**，保证不卡死、不越积越多。

**不做（刻意省掉）**

- 不做 PS 数据面（不接 AXI DMA、不进 PS DDR、不占 CMA/A53）。
- 不做 RTP（RFC 2435）、RTSP、RTMP、HLS。
- 不做 ARP（目的 MAC 用组播/广播地址绕开）。
- 不做 TCP 栈、不做 IP 分片（置 DF 位，应用层自己分片）。
- 不做网口接收（RX），只发。**但 RGMII 的 RX 引脚与 TEMAC 的 RX 逻辑要不要留，见 §8 待查项——PL 侧那颗 PHY 到底怎么连的，盘上没记录。**
- 不做 PHY 速率自适应（固定千兆）。
- **不做 VPU 对照路线**（已按你的意见撤掉：有 FPGA 编码器就不走 VPU）。

---

## 2. 架构（更正后）

```
SDI 子卡
  │ GTX 收发器（PL 已有，148.5 MHz refclk = R6/R5）
  ▼
SDI RX / 视频处理（PL 工程已有）
  │  ※ 现在这条路没有帧（P2）。M1 起改用 0xB4 vtc_enable 的内部测试图。
  ▼ AXI-Stream（像素，YUV）
自研 MJPEG 编码器（D：不在本仓，队友侧持有 —— 接口契约是第 0 号依赖）
  ▼ AXI-Stream（JPEG 字节流；边界不可假定 ⇒ 下面这级必做）
JPEG 分帧器（新增，约 30–60 LUT）—— 扫 FF D8 / FF D9，产出 frame_start / frame_end
  ▼
AXI-Stream FIFO（新增）—— 深度按 §4.5 的水位算，不是"≥16KB 即可"
  ▼
自研 packetizer（新增，约 1–2K LUT）
  - WAIT_LEVEL 门：攒满一整片才开始发（防 underrun）
  - 切 1400 B 分片，加大端 私有头 + UDP + IPv4 + 以太网头
  - IP 首部校验和硬件算；UDP 校验和置 0
  - 水位越线 ⇒ 丢帧（§4.6），drop_cnt++
  ▼ AXI-Stream（从目的 MAC 开始的完整以太网帧，不含 FCS）
TEMAC = AXI Ethernet Subsystem（PG138，只配 TX + RGMII）
  - 自动加前导、SFD、PAD、FCS(CRC32)、帧间隔
  - ※ P10：器件库里查不到 ODDRE1/IDDRE1，这颗 IP 能不能在本器件出位流，M0 之前是未知的
  ▼ RGMII（15 个球号已证 A；Bank/VCCIO 待查，见 §8）
YT8521 PHY → 网口 → 直连 PC / 交换机

PS（A53/Linux）：两条路，推荐第 1 条
  1) PS 完全不参与：TEMAC 的上电初始化写在 PL 里（一个 20 行 AXI-Lite 主 FSM + 常量 ROM）。
     ⇒ 不用动 BD 地址、不用 /dev/mem、不碰厂商那条链。AXI-Lite 留给以后改地址用。
  2) PS 配：把寄存器面挂进 BD 的 M_AXI_GP0 互联，地址取 0x4010_0000（在厂商已用通的 16 MiB 窗口内），
     用与厂商同形的用户态 mmap 读写（§10）。
```

---

## 3. 为什么这些选择最简化

| 决策 | 省掉的东西 | 修订说明 |
|---|---|---|
| UDP 组播（239.255.0.1 → MAC `01:00:5e:7f:00:01`）或广播 | 发送方向**不需要 ARP**（目的 MAC 是算出来的，不是学出来的） | 原表写"组播帧交换机直接泛洪，完全不用实现 ARP"——**ARP 省掉是对的，"直接泛洪"这半句不成立**，见 §3.1 |
| UDP 校验和填 0 | 省掉伪首部＋全载荷校验和。IPv4 下合法 | ✓ 保留 |
| 私有 8 B 分片头 | 省掉 RTP 头与 JPEG 量化表编码 | ✓ 保留，但字节序改大端（§4.4） |
| DF=1 + 应用层分片 1400 B | 不做硬件 IP 分片，丢一片只废一片 | ✓ 保留 |
| 只配 TX | TEMAC 减半，没有接收缓冲/中断/协议栈 | ✓ 保留 |
| 打包器从以太网头开始输出 | FCS/前导/PAD 由 TEMAC 自动加 | ✓ 已核：TEMAC 确实自动加前导、SFD、PAD、CRC32、IPG |
| PS 不参与（走 §2 第 1 条） | 不写设备树、不写驱动、不碰 `/dev/mem` | 原方案写"`devmem` 或一个小 C 程序即可"——**`devmem` 在本盘是死的**，所以更彻底地把 PS 移出关键路径 |
| 不做 MicroBlaze | 软核、lwIP、交叉调试全免 | ✓ 保留 |

### 3.1 "组播改广播"是什么意思（大白话）

- **组播**＝发包时目的地址写成"一组"，只有"报名加入这一组"的主机才收。报名动作用的是 IGMP 协议（接收端 PC 会发 IGMP report 说"我要收 239.255.0.1"）。
- **广播**＝发包时目的地址写成"这个网段所有机器"（`192.168.10.255`，以太网目的 MAC 全 `FF`），**不用报名**，凡是同网段的机器都会收到。

为什么这里要提：**我们的 FPGA 只发不收，压根不发 IGMP report**，而 PC 那侧的 IGMP report 是从 eth0（PS 网口）走还是从接收网卡走、交换机认不认，都不由我们控制。**如果中间过了带 IGMP snooping（监听）的交换机，它"看不到有人报名"就可能把组播丢掉**——表现就是"明明抓包能看到，脚本收不到"或干脆不通。

三档处理，按省事排序：

1. **PC 与板子网线直连**（推荐第一版）：没有交换机，组播必然收得到，最干净。
2. **过交换机不通 ⇒ 改广播**：只改 4 个常量（目的 IP `192.168.10.255`、目的 MAC 全 F、IP 头 `total length` 与校验和重算自动跟着走、Python 端删掉 `IP_ADD_MEMBERSHIP`）。代价：同网段所有主机都会收到这些包（我们用的是 `192.168.10.x` 独立网段，只有测试 PC，无所谓）。
3. **保持组播但让交换机放行**：在交换机上对该 VLAN 关 snooping，或静态绑组播端口。要有网管口，比第 2 条麻烦。

---

## 4. 网络配置与帧格式

### 4.1 网络参数（固定写死）

| 项 | 值 | 说明 |
|---|---|---|
| PL 源 MAC | `02:00:00:00:00:01` | 本地管理地址，别和 eth0 冲突 |
| PL 源 IP | `192.168.10.113` | 独立网段，避开 PS eth0 的 192.168.1.x |
| 目的 IP | `239.255.0.1`（组播）／`192.168.10.255`（广播） | 见 §3.1 |
| 目的 MAC | `01:00:5e:7f:00:01`／`ff:ff:ff:ff:ff:ff` | 与上一行成对改 |
| UDP 源/目的端口 | `5000 / 5000` | |
| 接收端 PC IP | `192.168.10.100`（**手工静态**，同网段） | 不设就收不到（没有 DHCP） |
| PC 防火墙 | 入站 UDP 5000 放行 | **本机火绒＋Windows 防火墙两道**，不放行时表现＝Wireshark 有包、脚本没包 |
| 每包 JPEG 载荷 | 1400 B（整帧 1450 B < 1518 B） | ✓ 已核 |

### 4.2 以太网帧布局（TEMAC AXIS 输入，不含前导/FCS）

| 偏移 | 长度 | 内容 | 谁产生 |
|---|---|---|---|
| 0 | 6 | 目的 MAC | packetizer（常量） |
| 6 | 6 | 源 MAC | packetizer（常量） |
| 12 | 2 | EtherType `08 00` | packetizer（常量） |
| 14 | 20 | IPv4 头（§4.3） | packetizer |
| 34 | 8 | UDP 头（§4.4） | packetizer |
| 42 | 8 | 私有分片头（§4.5） | packetizer |
| 50 | ≤1400 | JPEG 数据分片 | 直通 FIFO |
| 末尾 | 4 | FCS（CRC32） | **TEMAC 自动加** |

### 4.3 IPv4 头（20 B，无选项）

- `[0] 0x45`、`[1] 0x00`
- `[2..3]` total length = `36 + 本片载荷字节数`
- `[4..5]` identification：每个 IP 包 +1（16 位回绕）
- `[6..7]` = `0x40 0x00`（DF=1）
- `[8] 0x40`（TTL 64）、`[9] 0x11`（UDP）
- `[10..11]` 首部校验和：20 B 按 16 位大端累加、折叠、取反
- `[12..15]` 源 IP、`[16..19]` 目的 IP

算术全对，保留原文。（广播选项下只有 `[16..19]` 和目的 MAC 变。）

### 4.4 UDP 头（8 B）

- `[0..1]` 5000 = `0x13 0x88`；`[2..3]` 5000
- `[4..5]` length = `16 + payload`
- `[6..7]` checksum = `0x00 0x00`（IPv4 允许；接收端不校验）

### 4.5 私有分片头（8 B，**全部大端／网络字节序**）

| 偏移 | 长度 | 字段 | 说明 |
|---|---|---|---|
| 0 | 4 | `frame_id` | 每帧 +1，**丢帧也 +1**（§4.6） |
| 4 | 2 | `frag_idx` | 帧内从 0 开始 |
| 6 | 1 | `info`：bit7 = 本片是末片；bit6 = **本帧被截断（不完整，别送解码器）** | |
| 7 | 1 | `drop_cnt`（低 8 位） | 累计丢帧数，用于 M5 的丢包统计 |

**改动说明（两条都要认）**

1. **字节序**：原方案写"小端"，并写 `48,49 = 末片?16'h8000:0`。AXIS 按 MSB-first 出字节，`16'h8000` 发出来就是 `80 00`——那是**大端**的 0x8000。接收端用 `struct.unpack("<HH")` 会读成 0x0080，**末片位永远为假，一帧都拼不完整**。⇒ 统一大端，Python 用 `>IBB`。
2. **`info` 从 u16 拆成 2 个 u8**：bit15 那位跨字节，硬件和 Python 都容易写错；拆成两个单字节标志位，`frag_idx` 仍 u16 大端，容量够用（65535 片/帧）。`frag_total` 依然不放头里——这样不必先缓存整帧就能流式切片。

### 4.6 溢出策略：**丢帧 + 降画质**（按你 2026-10-25 的决定写死）

先算清楚"线比编码器快"这件事，因为它决定了丢帧点。

千兆 TEMAC 的实际可用载荷（每一片在线上的构成）：

```
头 = 14(eth) + 20(ip) + 8(udp) + 8(§6.3 的私有分帧头) = 50 B
线上一片 = 8(preamble+SFD) + 50 + 1400(payload) + 4(FCS) + 12(IPG) = 1474 B = 11 792 bit
载荷效率 = 1400 / 1474 = 94.98%
线上原始速率 = 1 Gbit/s ÷ 8 = 125 MB/s
  交叉校验：64 B 最小帧在线上要占 84 B ＝ 672 bit ⇒ 1 Gbit/s ÷ 672 bit = 1 488 100 pps（千兆的已知上限，对得上）
可用 JPEG 字节率 = 125 × 0.9498 ≈ 118.7 MB/s（= 118.7 × 8 ≈ 950 Mbps）
最高包速 = 125 MB/s ÷ 1474 B ≈ 84 803 pps
```

| 画质点（参考，非编码器实测） | 每帧字节 | 片数/帧 | @25 fps 线上码率 | @25 fps 包速 | 帧字节预算(4.75 MB) |
|---|---|---|---|---|---|
| 960×540 q60（**25.5–27.1 kB 是现役 10 fps 预览档的实测**，下表按 25 fps 外推） | 27 KB | 20 | **5.9 Mbps** | **500 pps** | 余 **176 倍** |
| 960×540 q80（估 B） | 45 KB | 33 | 9.7 Mbps | 825 pps | 余 106 倍 |
| 1080p 高熵（VPU 实测 2.35 MB/帧，仅作量级参考） | 2.35 MB | 1 679 | **495 Mbps** | **41 975 pps** | 余 **2.0 倍** |

三条结论：

- **千兆线不是瓶颈**，原方案 §12-9"余量充足"成立——连 1080p 高熵那种帧都装得下（余 2.0 倍）。
- **真正会先崩的是接收端 Python**：41 975 pps 单线程 recv＋`imdecode` 是明确的瓶颈（这条是 B：按"每包一次系统调用＋每帧一次解码"的结构推的，接收端实测还没做）。而 960×540 档只有 500 pps，量级上完全不构成压力（同为 B，未实测）。⇒ **"降画质"的第一动机是把 pps 压到几百量级，不是让线跑得动。** 文档里原那句"1080p30 MJPEG 约 56–190 Mbps"是**估计值（B/D）**，请当假设，别当依据。
- **线比编码器快约 2.0 倍**（118.7 MB/s 对 2.35 MB×25 fps＝58.8 MB/s）⇒ 直通式打包必然 underrun（见 §5.3）。

> 更正记录（2026-10-25，两次）：
> **第一次（原稿）**：写的基数是"117.5 MB/s × 0.9498 ≈ 111.6 MB/s"。这个 117.5 MB/s（≈940 Mbps 那个常见"goodput"说法）**盘上零出处**，是唯一的真错——基数应自下而上取 `1 Gbit/s ÷ 8 = 125 MB/s`，得 118.7 MB/s。
> **第二次（我上一轮的"改正"，也是错的）**：我当时判"preamble+SFD 被算了两遍"，把 1474 改成 1466、效率改成 95.50%。**那个判定本身是错的**——1474 里的第二个 8 B 不是前导码，是 §6.2/§6.3 那个**私有分帧头**（IP 总长写 `36 + payload_len`，36 = 20+8+8 就是它）。原稿的 1474 与 94.98% 一直是对的。
> 触发我回去重看的是审计工具在 §6.2 那行 `14 + 20 + 8 + 8 = 50` 上报的 FAIL——**它逼我发现 §4.6 与 §6.2 对不上**：改完之后 §4.6 的头(50 B)与 §6.2 的头(50 B)同源同值。教训写进纪律：**"我发现了一个错"这句话本身也要过一遍算式才能落笔。**

**丢帧的具体行为（写进 RTL 的规格，别只写"丢帧"两个字）**

```
水位信号：fifo_level（字节数，FIFO 输出侧计数）
HIGH = 3 × PAYLOAD_MAX = 4200 B      LOW = 1 × PAYLOAD_MAX = 1400 B
（HIGH 只是"编码器比线快时先泄压"的保护线；数值待 P1 契约后按瞬时码率重定）

1. fifo_level ≥ HIGH 且当前不在丢弃模式 → 进入丢弃模式
2. 丢弃模式下：
   a. 若正在发某一片，把这一片发完（发一半停手会留一个残帧在交换机/网卡上，比丢整帧更糟）；
   b. 之后不再开新片：从 FIFO 继续把字节吸收到下一个 frame_end（EOI）为止，全部丢掉不发；
   c. 该帧已发出的最后一片：把 info bit6（截断）置 1；
      若一字节都没发出去过，则本帧不产生任何包（没有"空帧"包）。
   d. frame_id 仍然 +1（保证接收端"看到缺号"而不是"看到重复号"）。
   e. drop_cnt += 1。
3. fifo_level ≤ LOW → 退出丢弃模式，从下一个 frame_start 恢复发送（绝不在帧中间恢复）。
```

- **降画质（Q 值）这一半需要编码器接口配合**：要有在线改 Q 的寄存器/AXI-Lite 位，PL 才能按水位自动降档。**契约里没有 → 本版只做丢帧，Q 由队友侧固定**。这条在 §14 待查清单里。
- 需要一个 `drop_cnt`/水位可读的出口：最省事的办法就是像上表那样塞 1 个字节进私有头（0 成本），PL 侧计数器位宽 32，进包取低 8 位。

---

## 5. JPEG 分帧器（**必做**，原方案列为可选）

### 5.1 为什么必做

原方案 §12-8 写"若编码器把多帧连续输出无边界，需先按 SOI/EOI 切帧"——**这条不能等出问题时再说**：

1. 编码器的 AXIS 行为我们**看不到源码**（P1），任何"它会给 tlast"的假定都不可核。
2. 一帧 1080p 跨 1 715 片，边界错一字节 ⇒ 后面所有帧全部错位 ⇒ 表现是"满屏花且永远不自愈"，而这是最难 debug 的形态。
3. 有了独立分帧器，`frame_id`、丢帧退出点（§4.6 步骤 2b/3）、接收端的"整帧丢弃"才都有唯一可信的边界。

### 5.2 逻辑（很小，约 30–60 LUT）

```
输入：原始 JPEG 字节流（来自编码器）
输出：frame_start（1 拍）、frame_end（1 拍）、以及"当前是否在 scan 段内"（可选，用于统计）

FSM（2 状态 + 1 个 pending 寄存器）：
  IDLE      : 收到 FF → 转 MARK
  MARK      : 收到 D8 → frame_start=1（并转 SCAN）
              收到 D9 → frame_end=1（并转 IDLE）
              收到 00 → 位填充(stuffing)，回 SCAN（不算 marker）
              收到其它 → 其它 marker，回 SCAN
```

**成立前提（记进契约项）**：JPEG 熵编码段内所有 `FF` 必须按 T.81 补 `00`。只要编码器合规，流内就不会出现假的 `FF D9`。⇒ 若队友的编码器**不做位填充**，EOI 检测会误判——这个必须问，见 §14。

### 5.3 packetizer 的 `WAIT_LEVEL` 门（防 mid-frame underrun）

问题：编码器输出约 58.8 MB/s（2.35 MB/帧 × 25 fps）时，线能以 118.7 MB/s 抽，**线跑赢编码器 2.0 倍**（B，按 P12 的 1080p 量级算，载荷速率见 §4.6）。直通式打包"有字节就发"会在片中间把 FIFO 抽干，`m_axis_tvalid` 不得不在帧内掉下来。TEMAC 对 TX underrun 的处理（补 PAD／中止帧／置错误状态）**盘上没有正本可查**（PG138 不在本地），所以不去赌它，直接从构造上排除：

```
只有当 fifo_level ≥ PAYLOAD_MAX（发整片）或 frame_end 已出现且 fifo_level > 0（发末片）
时才进入 HDR 状态开始发一个包。
⇒ 每个包一旦开头发，就必然能连续喂满，tvalid 永不在包中间掉。
```

代价：每个包要等 1400 B 攒齐才开头发，**额外延迟 = 1400 B ÷ 编码器输出率**：1080p 高熵（58.8 MB/s）≈ **0.024 ms**，960×540 q60（0.675 MB/s）≈ **2.1 ms**。⇒ **封顶就是一个片的攒积时间，不随片数累加**（第 n 片在发送时，第 n+1 片已在攒）。**上一版写的"20–60 ms 量级"是数量级错误（差 3 个数量级），已按实算改正。** 这同时把整条链变成"每片 store-and-forward"，正是 §4.6 丢帧策略需要的形态。

**判据（写死在 testbench 里）**：跑 1 万片，断言 `m_axis_tvalid` 从拉高到对应 `m_axis_tlast` 之间没有 0 拍间隙（除 `m_axis_tready=0` 的情况）。这条只有仿真能验，上板看不出来。

---

## 6. packetizer 模块

### 6.1 接口

```verilog
module video_packetizer #(
    parameter [47:0] SRC_MAC = 48'h02_00_00_00_00_01,
    parameter [47:0] DST_MAC = 48'h01_00_5e_7f_00_01,
    parameter [31:0] SRC_IP  = {8'd192,8'd168,8'd10,8'd113},
    parameter [31:0] DST_IP  = {8'd239,8'd255,8'd0,8'd1},
    parameter [15:0] SRC_PORT = 16'd5000,
    parameter [15:0] DST_PORT = 16'd5000,
    parameter integer PAYLOAD_MAX = 1400
)(
    input  wire        aclk, aresetn,
    output wire        s_axis_tready,          // 只有非丢弃模式且已过 WAIT_LEVEL 才为 1
    input  wire [7:0]  s_axis_tdata,
    input  wire        s_axis_tvalid,
    input  wire        s_axis_frame_start,     // 来自 §5 分帧器，不是编码器
    input  wire        s_axis_frame_end,
    input  wire [15:0] fifo_level,             // WAIT_LEVEL 与丢帧水位的输入
    input  wire        force_drop,             // PS/PL 手控丢帧（调试用）
    input  wire        drop_enable,            // 允许自动丢帧
    output reg  [7:0]  m_axis_tdata,
    output wire        m_axis_tvalid,
    output reg         m_axis_tlast,
    output reg  [31:0] drop_cnt
);
```

相对原方案接口的改动：去掉"编码器每帧 tlast"这个输入（改成 §5 的 `frame_start/frame_end`），加 `fifo_level`／`force_drop`／`drop_cnt`，加 `DST_MAC` 参数（广播选项要用）。

### 6.2 状态机

```
IDLE        : 等 frame_start。此时不读 FIFO（读也读不到新帧的头）
ARM         : WAIT_LEVEL 判定——(fifo_level >= PAYLOAD_MAX) 或 (frame_end 已到且 fifo_level>0)
              不满足就停在这里。⇒ 杜绝 underrun（§5.3）
HDR         : 依次出 14 + 20 + 8 + 8 = 50 字节，期间不读输入
PAY         : 读 PAYLOAD_MAX 字节直通（或读到 frame_end）
              满片 → m_axis_tlast=1（TEMAC 发完整帧）→ frag_idx+1 → 回 ARM
              遇 frame_end → info bit7=1 → 回 IDLE
DROP        : 丢弃模式。吸收到 frame_end 为止，不发任何包；
              若在 HDR/PAY 中途进入，先把当前片发完再转这里，并给该片打 info bit6
```

`m_axis_tlast` 每个包都给 1（TEMAC 要求 AXIS 边界＝以太网帧边界）；分片关系靠私有头表达，不靠 `tlast=0`。原方案写"满 1400 → 发 `m_axis_tlast=0` 回 HDR"——**那会让 TEMAC 把多片拼成一个超长以太网帧**，超过 1518 B 后要么被 PAD 要么被丢弃。**这是原方案 RTL 部分的一处硬错。**

### 6.3 头部模板（按 hdr_idx 选择；全大端）

```
0..13   以太网头（DST_MAC / SRC_MAC / 0800）—— 常量
14,15   0x45 0x00
2,3     36 + payload_len（末片时是 36 + 余数）
4,5     ip_id（每包 +1）
6,7     0x40 0x00（DF=1）
8,9     0x40 0x11
10,11   ip_crc：20 字节按 16 位大端累加→折叠→取反
12..19  SRC_IP / DST_IP
34..41  端口 / 16+payload_len / 0x0000
42..49  frame_id(4, BE) frag_idx(2, BE) info(1) drop_cnt低8位(1)
```

固定字段可预计算校验和，只有 `total_length`、`id` 变，流水加即可。**注意**：`ip_id` 与 `frame_id` 是两个计数器，别合成一个——`ip_id` 每包 +1，`frame_id` 每帧 +1 且丢帧也 +1。

### 6.4 实现要点

- `s_axis_tready` **不能恒为 1**。原方案 §6.4 说"只要 FIFO 不溢出就不丢帧"，但 FIFO 溢出正是我们要利用的丢帧信号。
- 输出严格按 `m_axis_tready` 背压；`tvalid` 拉高后数据保持到握手。
- IP 校验和：16 位累加器，HDR 状态发 IP 头时同步累加，输出 `[10..11]` 时取反。
- 第一版可不做 AXI-Lite，所有地址用 parameter 写死。

---

## 7. PL 工程清单

1. **Zynq7 Processing System IP**
   - 不勾 GEM EMIO（数据面不用 PS GEM）。
   - 若走 §2 第 2 条（PS 配），要在 Address Editor 里给新从设备分配地址；若走第 1 条（PL 自举），PS 侧一个端口都不用动。
2. **`tri_mode_ethernet_mac` v9.0（TEMAC）**——**不是 AXI Ethernet Subsystem**。
   - **改判依据（A，见 §16）**：本机 Vivado 2018.3.1 实测 `axi_ethernet` v7.1 的 `create_ip`＋`generate_target` 都过，但 `synth_design -mode out_of_context` **失败**（`[Synth 8-439] module 'bd_ae5e_c_counter_binary_0_0' not found`——它 BD 里引用了一个本机没有的子 IP）。TEMAC v9.0 同一条路**全过**。所以这颗 IP 从清单里划掉，别当备选。
   - `CONFIG.Physical_Interface` 的合法取值由工具本身给出：**`RGMII, GMII, MII, Internal`**（`[IP_Flow 19-3461]` 原文）。⇒ RGMII 是原生选项，不需要外挂 GMII-to-RGMII 桥（`gmii_to_rgmii` v4.0 本机也能建能综合，留作对照，不必用）。
   - Physical interface = RGMII、`MAC_Speed = Tri_speed`（默认，未改）、勾 AXI4-Lite、不勾 DMA。
   - **时钟端口（A，从生成件 `synth/temac_rg.v` 的 60 个端口里数的）**：要喂 `gtx_clk`（125 MHz）**和 `gtx_clk90`（同频移相 90°）两个**；PHY 侧 `rgmii_rxc` 入／`rgmii_txc` 出；另有 `s_axi_aclk`、`rx_mac_aclk`／`tx_mac_aclk` 出。⇒ **90° 那一相必须用 MMCM/PLLE 做**，这条比原方案写得更硬；`200 MHz` 那一头见下面第 7 项的更正。
   - ~~**资格风险（P10）**：盘上器件库 `zynq.lib` 没有 ODDRE1/IDDRE1 ⇒ TEMAC 落不了地。~~ **已撤销，见 §16 与 R2。**
3. **AXI-Stream FIFO**
   - 位宽 8（与 TEMAC 千兆 AXIS 一致）。异步 FIFO 更稳（编码器时钟与 125 MHz 解耦）。
   - 深度：`2 × PAYLOAD_MAX + 50 = 2 850 B` 是硬下限（WAIT_LEVEL 要求整片可用；50 B ＝一片的头，构成见 §4.6），水位 HIGH=4200 B ⇒ **建议 8 KB**，原方案"≥16 KB 即可"没有依据但也无害。
4. **JPEG 分帧器**（§5，新增，必做）
5. **自研 packetizer**（§6）
6. **TEMAC 上电初始化 FSM**（若走 §2 第 1 条）：复位→等自清→写 MAC→写速度→使能 TX，约 20 行，常量表放 ROM。
7. **时钟（这里仍是真拦路项，但需求比原方案小一号）**
   - **更正（A，见 §16）**：原方案写"要 125 MHz＋200 MHz 两个新时钟"。实测 TEMAC RGMII 配置综合后的网表里**有 `IDELAYE2`、没有 `IDELAYCTRL`** ⇒ **200 MHz 那个参考时钟这一版不需要**。真实需求是 **125 MHz 两相：`gtx_clk` 与 `gtx_clk90`**（TEMAC 的端口就叫这两个名，A，§7 第 2 项）。
   - RX 侧 125 MHz 由 PHY 的 `rgmii_rxc` 给出（板上 `PL_PHY_RX_CLK AC23`，正好是 Bank13 的 **MRCC** 脚，A，§16）⇒ 时钟**能**从 PHY 进来，但 `gtx_clk90` 还得由 MMCM/PLLE 从这个 125 MHz 上做出来。
   - 现状：**MMCM 5/5 已用满**（P11，`sdi2hdmi` 那份位流）。三条来源，按可行性排序：
     (a) 给现有某个 MMCM 加输出抽头（一个 MMCM 最多 7 个输出；先看现有 5 颗的输出口有没有空，且注意 WNS 已贴线）；
     (b) PS `FCLK_CLK0..3` 分频——**FCLK 给不出 90° 移相**，只能当 125 MHz 源，90° 仍要一级 PLLE/MMCM；
     (c) 板载空闲晶振（待查原理图）。
   - ⇒ 净结论：**需求从"2 个新频率"降到"125 MHz 的两相"，但一颗都还没落地**。要么给现有某颗 MMCM 加一路 90° 输出（不增颗数，前提是有空闲输出脚——这条本轮没数），要么新加一颗时钟原语（5/5 已满，必须先腾负载）。两条都不轻，这就是 M1 的真正内容。
   - **M0 之前不要开始写整条链。**
8. RESET（`AA13`）：**极性、时长、上拉仍未知（C）**，但**归属已更正（A，§16）：`AA13` 是 `IO_L6P_T0_12`，在 Bank 12，不在 Bank 13**——那颗 PHY 的 15 个脚里有 14 个在 Bank13，复位单独跨到 Bank12。⇒ XDC 要按两个 bank 写，别整组当同一个电压域。
9. 约束：§8。

---

## 8. XDC 约束

**出处更正**：原标题写"Bank13，VCCIO 1.8V，摘自完整版手册 4.8 节表 4-12"。盘上 §4.8 抽取件（`41_manual_full_extracted.txt:195-235`）那张表**只有 3 列**（信号名／引脚号／备注），**没有表号、没有 Bank、没有 VCCIO、PL 侧没有引脚名列**；同抽取件 `:241`（§4.9 SD 卡）那句 "该 BANK 的 VCCIO 设置为 1.8V" 讲的是 **PS 的 BANK501**，与 PL 网口无关。⇒ **15 个球号是对的（A），`Bank13`／`VCCIO 1.8V`／`表 4-12` 这三条出处不存在（D）**，`dict.md:31` 引的也是这条断链。器件库 `zynq.padr` 加密，离线解不出 Bank。

```tcl
# ---- 引脚（A：手册 §4.8 实测）----
# TX（MAC→PHY，FPGA 输出）
set_property PACKAGE_PIN AD23 [get_ports rgmii_txc]
set_property PACKAGE_PIN AD26 [get_ports rgmii_tx_ctl]
set_property PACKAGE_PIN AF24 [get_ports {rgmii_txd[0]}]
set_property PACKAGE_PIN AF25 [get_ports {rgmii_txd[1]}]
set_property PACKAGE_PIN AA24 [get_ports {rgmii_txd[2]}]
set_property PACKAGE_PIN AB24 [get_ports {rgmii_txd[3]}]
# RX（PHY→MAC，FPGA 输入）
set_property PACKAGE_PIN AC23 [get_ports rgmii_rxc]
set_property PACKAGE_PIN AA25 [get_ports rgmii_rx_ctl]
set_property PACKAGE_PIN AB26 [get_ports {rgmii_rxd[0]}]
set_property PACKAGE_PIN AC26 [get_ports {rgmii_rxd[1]}]
set_property PACKAGE_PIN AE25 [get_ports {rgmii_rxd[2]}]
set_property PACKAGE_PIN AE26 [get_ports {rgmii_rxd[3]}]
# 管理 / 复位
set_property PACKAGE_PIN AE22 [get_ports mdc]
set_property PACKAGE_PIN AF22 [get_ports mdio]
set_property PACKAGE_PIN AA13 [get_ports phy_reset_n]

# ---- 电气标准（待核，见 §14-Q1）----
# 唯一能引的硬事实：PS7 IP 的 validate_update.tcl:170 —— RGMII 不支持 LVCMOS33，只能 1.8/2.5V。
# 所以本块只能是 LVCMOS18 或 LVCMOS25 之一。按 18 先写，M0 用 Procise/Vivado 的
# Device/Bank 视图按球号反查 VCCIO 需求（或直接量 bank 电源）后再定稿。
set_property IOSTANDARD LVCMOS18 [get_ports {rgmii_txc rgmii_tx_ctl rgmii_txd[*] \
                                             rgmii_rxc rgmii_rx_ctl rgmii_rxd[*] mdc mdio phy_reset_n}]
```

**原方案 XDC 缺的、必须补的四类（缺一类就表现为"静默无帧"或时序假通过）**

```tcl
# 1) RX 侧输入时钟没建 —— 原方案只 create_clock 了 rgmii_txc（那是我们输出的时钟）
create_clock -period 8.000 -name rgmii_rxc [get_ports rgmii_rxc]
set_input_delay  -clock rgmii_rxc -max 0.6 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]   ;# 数值待按 rgmii-id 重算
set_input_delay  -clock rgmii_rxc -min 0.2 [get_ports {rgmii_rxd[*] rgmii_rx_ctl}]

# 2) TX 侧源同步输出没有 set_output_delay —— txc 是送给 PHY 的，不是本地采样时钟
set_output_delay -clock <MAC内部125MHz> -max 0.6 [get_ports {rgmii_txd[*] rgmii_tx_ctl}]   ;# 双沿：-clock_edges {1 2}
set_output_delay -clock <MAC内部125MHz> -min 0.2 [get_ports {rgmii_txd[*] rgmii_tx_ctl}]

# 3) ~~IDELAYCTRL 的 200MHz 参考时钟必须被约束到~~
#    §16.3 实测：TEMAC RGMII 的网表里有 IDELAYE2、没有 IDELAYCTRL ⇒ 这一版没有 IDELAYCTRL 要喂，
#    这条约束先删掉；只有将来自己加 IDELAYE2 到 FIXED/CARRY 模式时才需要 200 MHz。
#create_clock -period 5.000 -name idelay_ref [get_pins <mmcm>/clk_out?]

# 4) 与视频/编码器域是异步的，要显式隔离，否则 STA 会给假的余量
set_clock_groups -asynchronous -group [get_clocks -include_generated_clocks rgmii_txc] \
                                    -group [get_clocks <sdi/编码器域>]
```

（`<...>` 里的时钟/引脚名要按实际生成的 IP 层次填，不能照抄。）数值也先当占位：RGMII 的 2 ns 预算怎么在"PHY 已 rgmii-id"的前提下落成约束，要在 M2 的仿真＋一次实跑里核（C）。

---

## 9. PHY 与时钟

- YT8521 上电默认 RGMII + 自协商，strap 一般优先千兆。第一版 FPGA 不主动配 PHY。
- 千兆 RGMII 对 2 ns 时延极敏感：PHY 侧 **rgmii-id**（内部加 TX/RX delay），MAC 侧就**不要再加**，两端约定必须一致。这与 PS 侧口"千兆不稳"是同一个坑。
- 自协商结果与 TEMAC 固定速率不一致会不通 ⇒ MDIO 读确认；必要时 MDIO 强制 1000M Full。
- 官方"研发板只保百兆"口径针对的是 **PS 侧网口**；PL 侧是独立 PHY，不受该口径限制，但**能否千兆只能实测**。（旁证：现役 PS eth0 协商到的对端只广告 10/100，`Link partner advertised: 10baseT/100baseT only`、`Speed: 100Mb/s`，PHYAD 0——A 级读数在 `wiki/PS/hardware/raw_logs/net_ethtool.txt`。这说明**当前接的那台设备/那条线只跑百兆**，PL 口实测时别用同一台对端。）
- **待查（阻塞 M0）**：PL 那颗 PHY 物理上接到哪个 RJ45？板上现在只有 eth0 在用。若是同一个 RJ45 共用变压器/磁件，那需要查互斥 MUX；若是独立第二个 RJ45，要在 §14 找到它的位置。

---

## 10. PS 配置（两条路，推荐第 1 条）

### 10.1 路 1：**PS 完全不参与**（推荐）

TEMAC 上电初始化（§10.3 那 6 步）写成 PL 里的 AXI-Lite 主 FSM，寄存器值全常量。好处：**不动 BD 地址、不碰 `/dev/mem`、不影响厂商那条链**，把 P5/P6 两个风险从关键路径上摘掉。以后要改 IP/MAC 再开路 2。

### 10.2 路 2：PS 配（原方案那条，写法要改）

**盘上实测的 BD 地址与通路**（A，`case/…/bd/ps_ai/ps_ai.bd` 的 `addressing` + `interface_nets`）：

| 地址段（各 512 KB） | BD 外部端口 | 从 PS 走哪条路到 |
|---|---|---|
| `0x4000_0000–0x4007_FFFF` | `BYolo_GP0`（NPU 寄存器面） | `M_AXI_GP0` → `axi_interconnect_0/M00` |
| `0x4008_0000–0x400F_FFFF` | `User_GP0`（视频/frame_trans 寄存器面） | `M_AXI_GP0` → `axi_interconnect_0/M01` |
| `0x8000_0000–0x8007_FFFF` | `BYolo_GP1` | `M_AXI_GP1` → `axi_interconnect_1/M00` |
| `0x8008_0000–0x800F_FFFF` | `User_GP1` | `M_AXI_GP1` → `axi_interconnect_1/M01` |
| `0x0000_0000–0x3FFF_FFFF`（1 G） | `S_AXI_HP0..HP3` → PS DDR 低 1 G | 如果哪天要 DMA，这条路现成，**不经 NPU** |

⇒ **新从设备的 TEMAC 管理口建议放 `0x4010_0000`（512 KB）**：GP0 侧空着，而且**落在厂商已经用通的那个 16 MiB 映射窗口（`0x4000_0000–0x40FF_FFFF`）之内**——这正好绕开"新地址能不能 mmap"这个未知。做法：`axi_interconnect_0` 的 `NUM_MI` 2→3，新增一个 BD 外部 AXI-Lite slave 端口（照 `User_GP0` 抄），在 Address Editor 里 assign `0x4010_0000`。

**架构要点：新从设备完全不经过 NPU（A，本轮追线）**

`wiki/todo/位流构建与SDI信号检测.md` §4.2 那句"**NPU 是 PS 通往 PL 的唯一 AXI 端点**"容易被读成"PL 里再加从设备也得走 NPU"。**不是这个意思**，它只对厂商的连线成立。追线：

```
ps_ai.bd：M_AXI_GP0 → axi_interconnect_0 → M01 = User_GP0（BD 外部 slave 端口，0x4008_0000）
ps_ai_peripheral.sv:1134  BD 实例的 User_GP0_* 端口
ps_ai_peripheral.sv:690   gp_io u_gp0_io( .M_AXI_GP_ARVALID(User_GP0_ARVALID), … )
gp/gp_io.sv:13-17         这些 GP 信号在 gp_io 里全是 input
                          → gp_io 把标准 AXI-Lite 转成 EDIF 的自定义 pl_* 总线
                          → AI_Mate 内部译码 → frame_trans / frame_ctrl 的 S_AXI-Lite
```

⇒ 现有 `frame_trans` 寄存器之所以"必须靠 NPU 当桥"，是因为厂商只把 `User_GP0` 这一路口给了 `gp_io`。**BD 里的 `axi_interconnect_0` 本身就是标准互联，多挂一个 M 口直接接 TEMAC 的 `S_AXI_LITE`，那座桥就不在路径上**——既不依赖 EDIF 内部译码器，也不受"删 NPU 就没从设备"那条影响。
（**代价**：改 BD ＋ 重跑地址 ＋ 与厂商那份 EDIF 共存时 `frame_ctrl` 的连线不能动。这也是为什么 §10.1 那条"PL 自己写、PS 一个端口都不动"仍然是首选。）

**写法更正（原方案说"第一版可直接 `devmem`"——那是错的）**

`dd if=/dev/mem` 读 `0x400800b0` 返回 `Bad address`（A），内核是 `CONFIG_STRICT_DEVMEM=y`（A，`34_kernel_config_from_Image.txt:4260`）。⇒ `devmem`/`dd` 这条路不通。厂商链靠的是**用户态 mmap**（P5，A）。板子上**没有** `/dev/uio*`（A）。所以只能 mmap，形如：

```python
import mmap, os
f = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
m = mmap.mmap(f, 4096, offset=0x40100000)     # 偏移必须页对齐
# 小端读写：int.from_bytes(m[off:off+4], 'little')
```

**上板第一步：只读探针（先证明"这个地址有位流里的 slave 在应答"，再做任何写）**

```python
import mmap, os
f = os.open('/dev/mem', os.O_RDONLY | os.O_SYNC)   # 只读，先把写风险摘掉
m = mmap.mmap(f, 4096, offset=0x40100000, prot=mmap.PROT_READ)
for off in (0x000, 0x004, 0x0FC):                  # 0xFC 的版本寄存器偏移按生成 IP 的 PG138 附录 A 核对
    print(hex(off), hex(int.from_bytes(m[off:off+4], 'little')))
```

判读：
- 返回**非全 0、非全 F** 且稳定 ⇒ 该地址有 slave 在应答，可以继续（B）。
- 返回全 0/全 F ⇒ 地址没 assign 上／位流里没这个 slave。**停手，别再写**（写同样可能挂总线）。
- `open`/`mmap` 返回 `EPERM`/`ENXIO` ⇒ STRICT_DEVMEM 把这个窗口挡了。此时**只有**这条路可走：改回 §10.1（PL 自举），或把设备塞进厂商已验证过的窗口内重试。
- **卡死／串口无响应** ⇒ 命中 P6（读未映射的从设备会把 AXI 挂死，整机要断电）。**⇒ 探针必须一次只读一个字，且只在你能接串口、愿意断电的时候做。**

这条探针的边际成本是几分钟，收益是把 P5/P6 两个 B/C 级判断变成 A 级，并且它本身就该是 M4 的第一个动作。

### 10.3 初始化顺序（两路都要走，只是谁去写的问题）

1. 释放 PHY 复位（`AA13`），等 ≥50 ms（时长待 §14-Q3）。
2. TEMAC 软件复位（管理寄存器 `0x0000` bit0），等自清零。
3. 写 unicast MAC 地址寄存器。
4. 配 RGMII/PCS 速度 1000M Full（按生成 IP 版本的寄存器表）。
5. TX 使能（若例化了 RX，RX 使能）。
6. 可选：MDIO 轮询链路状态，确认 1G/Full。

不产生任何网络接口（`ip link` 看不到，正常——数据面不归 Linux）。若走路 2，写一个 `init` 脚本（`/root/wcis-plnet/init.py`）而不是 rc.local，方便回滚；**不要在厂商链在跑的时候同时读写 `0x4008_0000` 面**。

---

## 11. 接收端（PC，Python）

保存为 `pl_mjpeg_rx.py`（本机 Python，需要 opencv-python；**Firefox 之外的 GUI 库**，`cv2.imshow` 会弹自己的窗口）。

相对原方案的 8 处修正（编号进代码注释，逐条都可复现）：

| # | 问题 | 后果 | 修法 |
|---|---|---|---|
| 1 | `struct.unpack("<IHH")` | 末片位永远读不到（§4.5 改动 1） | 改 `>IBB` |
| 2 | `f[i] for i in range(total)` | 收到的 index 不连续时 **KeyError 直接崩** | 先 `set(range(total)) <= set(f)` |
| 3 | `IP_ADD_MEMBERSHIP` 填 `0.0.0.0` | 多网卡时内核挑错接口，收不到 | 填接收网卡的 IP `192.168.10.100` |
| 4 | `stale` 用 `& 0xffff` 而 `frame_id` 是 u32 | 残留帧永不清理／或误清 | 用 `& 0xFFFFFFFF`，且按"号差 > N"和"时间戳"双条件 |
| 5 | `cv2.waitKey(1)` 只在收到完整帧后才走到 | 无帧时窗口冻死、ESC 退不出去 | `waitKey` 移到每轮循环末尾（`continue` 之前也要走） |
| 6 | 单线程 recv＋`imdecode` | pps 一高就自堵（§4.6） | 收线程 + 解码线程分离；`SO_RCVBUF` 抬到 8 MB |
| 7 | 没设 `IP_MULTICAST_IF` | 组播报文从别的网卡出去，收不到 | 绑组网卡 |
| 8 | "喂现有 `mjpeg_server.py`" | **它默认 `--fps 2.0` 且只在文件 mtime 变化时发**（A，`workenv/live/mjpeg_server.py`） ⇒ 会把流悄悄压到 ≤2 fps | 要么显式 `--fps 30` 并理解它仍是"按文件变化转发"，要么直接自己发 HTTP multipart |

```python
# -*- coding: utf-8 -*-
import socket, struct, threading, time, queue
import cv2, numpy as np

MCAST_GRP, IF_IP, PORT = "239.255.0.1", "192.168.10.100", 5000
RXQ = queue.Queue(maxsize=2048)

def recv_thread(sock, rxq):
    while True:
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            continue
        if len(data) < 8:
            continue
        rxq.put(data)

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
    s.bind((IF_IP, PORT))                      # 修 3：绑到接收网卡，不 bind ""
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(IF_IP))   # 修 7
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                 socket.inet_aton(MCAST_GRP) + socket.inet_aton(IF_IP))
    s.settimeout(1.0)
    threading.Thread(target=recv_thread, args=(s, RXQ), daemon=True).start()   # 修 6

    frames, last_report, pkts, bad, last_fid = {}, 0.0, 0, 0, None
    while True:
        try:
            data = RXQ.get(timeout=0.5)
        except queue.Empty:
            data = None
        if data is not None:
            frame_id, frag_idx, info, drop_cnt = struct.unpack(">IHBB", data[:8])   # 修 1
            chunk, pkts = data[8:], pkts + 1
            f = frames.setdefault(frame_id, {})
            f[frag_idx] = chunk
            if info & 0x80:                                  # 末片
                total = frag_idx + 1
                if info & 0x40:                              # 本帧被截断（发送侧丢帧）
                    frames.pop(frame_id, None)
                elif set(range(total)) <= set(f):            # 修 2
                    jpg = b"".join(f[i] for i in range(total))
                    img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                    if img is not None:
                        cv2.imshow("PL MJPEG bypass", img)
                    else:
                        bad += 1
                    frames.pop(frame_id, None)
                else:
                    print(f"missing frag frame {frame_id}: got {len(f)}/{total}")
                last_fid = frame_id
            stale = [k for k in frames if ((frame_id - k) & 0xFFFFFFFF) > 16]   # 修 4
            for k in stale:
                frames.pop(k, None)
            now = time.time()
            if now - last_report > 2:
                print(f"pkts={pkts} bad={bad} pending={len(frames)} "
                      f"last_frame_id={last_fid} tx_drop_cnt={drop_cnt}")
                last_report = now
        if cv2.waitKey(1) & 0xFF == 27:                       # 修 5：每轮都走，无包时窗口不冻
            break

if __name__ == "__main__":
    main()
```

（上面那行 `np.zeros` 的填充只为在无帧时保持窗口有泵；正式用可以换成 `waitKey` 前不动图。广播版把 `IP_ADD_MEMBERSHIP` 那两行删掉、`bind` 到 `0.0.0.0` 或网卡 IP 即可。）

**`drop_cnt` 是这条链的验收仪表**：它涨说明 PL 在丢帧（编码器快过线，或 WAIT_LEVEL 水位定错），它不涨而"missing frag"出现说明是**网络/交换机丢包**。两件事必须分得开，否则 M4 的判据没法读。

---

## 12. 验证里程碑（判据都改成可读数）

| 里程碑 | 内容 | 判据（可复现读数） |
|---|---|---|
| **M0 器件与 IP 资格** | 只做 TEMAC＋空 AXIS 口的最小工程，出位流。**不含视频逻辑、不接 PHY** | **部分已达成（A，§16，2026-10-26 本机 Vivado）：TEMAC `Physical_Interface=RGMII` 的 `create_ip`＋`generate_target`＋`synth_design -mode out_of_context` 全过，5 644 个 leaf、网表里零条 `Netlist 29-180`（不支持原语）**。剩下没做的：**布局／DRC／WNS／出 bit**——需要把 TEMAC 装进一个带 PHY 引脚约束的真工程再跑一遍。判据不变：`opt_design` 0 error；DRC 0 error；WNS > 0；**MMCM 用量 ≤5** |
| **M1 时钟** | 定 **125 MHz ＋ 它的 90°** 的来源（§7.7／§16.3；~~125/200 MHz 两个新频率~~ 已被 §16.3 判掉） | `report_clocks` 里 `gtx_clk` 与 `gtx_clk90` 存在、**两条都 8.000 ns**、无 CRWARNING；`set_property HD.CLK_SRC` 落在两个不同 BUFGCTRL 上不冲突；**MMCM 总数仍 ≤5**（超了就是 R3 兑现，回来改设计） |
| **M2 仿真闭环** | testbench 喂假 JPEG（含位填充、随机帧长），逐字节比对输出 | 头部字节全等；`ip_id`/`frame_id` 关系正确；末片/截断位正确；**`tvalid` 包内无间隙**（§5.3 判据）；underrun 场景 0 次；丢帧模式下无残包 |
| **M3 固定测试帧** | packetizer 写死一个 1450 B 帧周期发 | PC 直连，Wireshark 抓到；IP 校验和显示正确；无 "Malformed"；目的 MAC/组地址正确 |
| **M4 上板链路** | 接上 PHY＋真 FIFO＋分帧器，源用**厂商内部测试图**（`0xB4 vtc_enable`，不依赖 SDI） | ①§10.2 探针通过；②接收端连续出图；③`drop_cnt` 读数可解释；④帧率与源制式一致（**先确认源是 25 还是 29.97**，别拿"和 SDI 一致"当判据，因为现在没有 SDI） |
| **M5 稳流** | 连续 30 min | 0 次 `missing frag`（或全部由 `drop_cnt` 增长解释）；接收端 `pkts` 速率与 §4.6 表算出的 pps 吻合（±5%）；PS 侧无异常（`dmesg`、厂商链仍在跑） |
| **M6 真 SDI** | 换成真 SDI 源 | 前提是 P2 那个拦路项关掉（GT 参考时钟 + SDI 状态寄存器 0x0B8–0x0E4）。此时 SDI 与 RGMII 不抢 GT——手册 §4.14 原文（A，`41_manual_full_extracted.txt:303-307`）："JFMQL30TAI 的芯片只有一个 bank 的 GT，故通过一个 MUX 进行片选切换。PCIE 接口、SFP 接口、SDI接口、SMA 接口同用同一个 bank 的 GT。各个接口的选择通过 J12 进行片选"。**手册没提 RGMII** ⇒ "RGMII 在 HR bank、不占 GT" 是推断（B），要在 M0 的综合报告里用 IO/Bank 资源核实 |

**部署方式（不变，但要说清代价）**：位流只能走 BOOT.bin 手术（P4）。换之前 `md5sum /mnt/boot/BOOT.bin` 确认现装是哪颗（**点火门禁**：现役 `aca4612b…`＝厂商原版＝唯一能跑模型的那颗）；手术用 `workenv/boot-splice.py` + `workenv/board-boot-swap.py`（先拿已知答案的旧件做往返复现，再拼新件）；槽位不是问题（P3）；换完留 `BOOT.pre_swap.bin`，Linux 起不来时停在 `fmsh>` 用 `fatwrite` 从串口回滚（**这条路没演练过，C**）。

---

## 13. 风险与待查（按"会不会白做"排序）

| # | 风险 | 等级 | 处理 |
|---|---|---|---|
| R1 | 编码器拿不到，接口契约缺失 ⇒ FIFO/水位/Q 控制全无法定 | D | 第 0 号依赖。§14-Q7 列了最小必需字段 |
| R2 | ~~器件库没有 ODDRE1/IDDRE1 ⇒ TEMAC 落不了地~~ | **已撤销**（A，§16） | 原判断有两处错：① `ODDRE1/IDDRE1` 是 **UltraScale** 原语，7 系列 Zynq 从来不用它们，缺不缺与 JFM 库无关；② 我数的是 `030ai/zynq.lib`，而实际构建用的器件是 **Xilinx `xc7z030ffg676-2`**（`repos/sdi2hdmi/build.tcl:174`）＋**Vivado 自带的 unisim**，那份库跟 `zynq.lib` 不是一个东西。实测：`ODDR/IDDR/OSERDESE2/ISERDESE2/IDELAYE2` 综合＋布局＋DRC 全过，TEMAC RGMII 配置综合通过且网表里只有 7 系列原语。⇒ 不必转方案 A |
| R3 | **MMCM 5/5 满** ⇒ 90° 那一相没处来 | A | 需求已从"两个新频率"降到"125 MHz 的两相"（§7 第 7 项、§16.3）；三条来源里只有 (a) 现成 MMCM 加抽头能同时给同频两相。**而 (a) 成立与否取决于"现有 5 颗里有没有一颗还剩空闲输出脚"——这轮没数**（盘上有 `*.xci` 与综合报告可查，是我方能自己解决的，不用问人）。M1 第一件事就是数这个，判据见 §12 M1 行 |
| R4 | WNS 已贴线（+0.104 ns） ⇒ 加逻辑后可能翻负 | A | 每加一级跑一次 impl 看 WNS，别攒到最后 |
| R5 | SDI 无帧 ⇒ M6 走不到 | A | 用内部测试图（M4）绕开；真 SDI 另页跟 |
| R6 | 读未映射地址楔死 PS | A 事故／B 归因 | §10.2 只读探针＋单字读＋可断电时才做 |
| R7 | ~~Bank/VCCIO 未证 ⇒ IOSTANDARD 可能选错~~ **降到"只剩电压"** | A／C | **Bank 已用工具反查完毕（A，§16）**：14 脚在 **Bank 13**、`PL_PHY_RESET AA13` 在 **Bank 12**，两颗都是 **High Range** bank。而且拿到了一个比"查手册"更硬的结果：**`HSTL_I_18` 在 Bank13 布局失败**，原因不是 bank 不支持，是 **VREF 脚 `AB24` 已被 `PL_PHY_TXD3` 占用**（`[DRC BIVRU-1]` 原文）⇒ 这一版只能用 **LVCMOS18/25** 类不带 VREF 的标准。**仍缺的只有 Bank13/12 的实际 VCCIO（1.8 还是 2.5 V）**——那是板子供电，工具看不见，见 Q1 |
| R8 | 交换机 IGMP snooping 丢组播 | C | §3.1 三档；首选直连，不通就改广播（4 个常量） |
| R9 | RGMII 时延两端不一致 ⇒ "link up 但丢包/不通" | B | PHY 侧 rgmii-id，MAC 侧不加；PS 侧 dts 的 `rxc/txc-skew-ps=1860` 只当参考 |
| R10 | 千兆资格未测（`eth0` 现只协商到 100M） | A 读数／C 归因 | 换对端重测；不通先降 100M（TEMAC 配 100M、RGMII 25 MHz）验链路，再攻千兆 |
| R11 | 接收端 pps 自堵被误判成"PL 丢帧" | B | 分离线程＋`drop_cnt` 双读数分开记账 |
| R12 | 台账口径：网络卸载／FPGA 图像压缩不在本周期（D-02、O2/O4、backlog #3） | A | M0–M3 不动台账；要转正先补"PS 网络栈/软编是端到端瓶颈"的实测 |

---

## 14. 查不到的点（请你去找的清单）

**Q1 Bank 已解决，只剩 VCCIO（原"15 个脚的 Bank 与 VCCIO"）**：**Bank 不用查了**——我用 Vivado 把 15 个球号真的约束、布局、`report_io` 出来，14 脚 Bank 13、`AA13` Bank 12，全是 High Range（A，§16）。**唯一还缺的是这两个 bank 板上实际接的是 1.8 V 还是 2.5 V**，这是供电网络，工具推不出来。可接受的来源任一：原理图 bank 供电页；万用表量 `VCCO_13`／`VCCO_12` 网络；手册的电源章节。⚠️ 顺带一个约束条件（§16）：**这版不能选带 VREF 的标准**（VREF 脚 `AB24` 已被 `PL_PHY_TXD3` 占了），所以 PHY 侧 RGMII 电平必须与 FPGA 侧同为 LVCMOS 一档——如果量出来 bank 是 2.5 V，就要确认 YT8521 的 RGMII 口也配在 2.5 V。

**Q2 已做完，而且原问题问错了方向**：~~`ODDRE1/IDDRE1/ODDR2` 在 `030ai/zynq.lib` 里命中 0 ⇒ TEMAC 落不了地~~。你说的那句"在 Vivado 里建一个 5 分钟的工程、只实例化这几个原语看综合器认不认"**就是我跑的实验 A1**，实测结果在 §16。要点：① `ODDRE1/IDDRE1` 在这颗 7 系列器件上确实**不可用**，但那是 Xilinx 的架构门（它们是 UltraScale 原语），与 JFM 库无关；② **TEMAC 的 RGMII 根本不用它们**，它用的是 `ODDR`/`IDDR`/`IDELAYE2`/`BUFIO`/`BUFR`，全部可用；③ 我原来数的那份 `030ai/zynq.lib` 不是这条构建链用的库（构建用 `xc7z030ffg676-2`＋Vivado 自带 unisim）。⇒ **这条从"要你去查"里删掉。**

**Q3 PHY 复位 `AA13`**：极性（高有效还是低有效）、最短时长、是否有板上 RC 上电自动释放、是否已内部上拉。

**Q4 PL 那颗 YT8521**：PHYAD（手册没给，读原理图上下拉，或 MDIO 扫 0–31）、RGMII delay 模式（rgmii / rgmii-id / 需不需要寄存器写）、25 MHz 时钟来源（晶振 Y4 是否本板实配）、供电与变压器／RJ45 归属（板上有几个物理网口，PL 那颗接哪一个）。

**Q5 板卡原理图（正本 PDF）**：仍然零命中——**但我上一轮把这条写大了，得更正**。我当时说"Q1/Q3/Q4 全指向原理图、盘上什么都没有"，实际上**手册提取件里就有 PL 那颗 PHY 的 15 个脚与球号**（`wiki/PS/board_extract/41_manual_full_extracted.txt:221-235`，`PL_PHY_TX_CLK AD23` … `PL_PHY_RESET AA13`），而且 `wiki/todo/dev/板载接口与内核改造收纳进dev.md:422`、`wiki/dict.md:31` 早就登记过"PL 口在 Bank13"。**我没有检索到就写了"零命中"，这是我的错**（只搜了"原理图/schematic"这类词，没搜信号名）。⇒ 现在真正还缺的只剩：**① Bank13/12 的 VCCIO 供电（Q1）；② `AA13` 复位的极性与上电时序（Q3）；③ PHYAD 与 RGMII 延时模式（Q4）；④ 网口变压器／RJ45 归属**。这四条确实要正本。

**Q6 含 NPU 位流的构建（2026-10-25 更新：队友那边已经做好了，缺的是交接形式）**

不用说服他们做 git 同步——**一次性快照就够了**。按"我方后续能不能自己加逻辑"分成要问清的三件：

- **a. 消掉 `Opt 31-67/430` 的那一步到底是什么。** 我方的堵点判断在 10-14 已经改判过一次：不是 EDIF 的 3 根悬空输入（10-10 给它们绑常量后**仍然不过**，A），而是**本地这套器件库的 PS7 模型只声明 AI 端口、不实现驱动**（`processing_system7_v5_5_processing_system7.v:17651` `assign pl_arvalid = PS7_AI_OUT1868 ;`，A 到端口声明级；"为什么没实现"是 B），`AI_Mate.edif` 无辜。⇒ 要问的是**他们那边这一步落在哪里**：换了带驱动的 PS7 模型／打了新补丁？改了 xci／约束？还是换了 `opt_design` directive？**只要这一句话的答案，我方就能自建**。这是 Q6 里性价比最高的一条。（更正：上一版那句"十次全失败"的**次数是我编的**，盘上只有上面这些带日期的尝试记录。）
- **b. 工程快照（zip 一次性传，不进 git）**：`srcs`/`constrs`/BD 的 `.xci`＋器件库补丁版本＋跑的顺序（或直接给 `create_project`→`write_bitstream` 那份 Tcl）。有了它，后续 TEMAC 的增量是我方自己跑。
- **c. 如果 a、b 都拿不到 ⇒ 只剩"他们代跑"**：那我方交付给他们的是**增量包**（新增 RTL 文件＋XDC 片段＋BD 改动说明：`axi_interconnect_0` 的 `NUM_MI` 2→3、新从设备地址 `0x4010_0000`），回传 `.bit` ＋ `utilization_routed.rpt` ＋ `drc_routed.rpt`。**代价要认**：每改一行都要过他们一次，迭代速度由他们决定。M0 那个最小资格工程正好可以当第一个代跑件（顺便验 Q2）。
- 另外仍想知道：厂商侧有没有官方的"重建含 NPU 位流"流程或问题单进展。

**优先级**：Q6-a ＞ Q1（只剩 VCCIO）＞ Q7 ＞ Q6-b。Q2 已由 §16 关掉。**a 是一条口头答案就能解决的问题，却要解锁整条自建路径。**

**Q7 队友 MJPEG 编码器的接口契约**（最小集，缺一项就有一串设计项定不下来）：AXIS 位宽与 `tvalid`/`tready`/`tlast`/`tuser` 语义；一帧的字节数分布（各分辨率/画质档）；瞬时与平均输出字节率；是否按 T.81 做位填充（决定 §5.2 的 EOI 检测成立）；资源占用（LUT/BRAM/MMCM 输出，决定 R3 能不能挤下）；**Q 值能否在线改**（决定 §4.6 的"降画质"这半边能不能做）；复位/使能握手方式；有没有现成的 test 激励或仿真波形。

**Q8 交换机是否开 IGMP snooping**（或者能不能拿到一个可关的网管口）。直连能绕开，但答辩现场多半要过交换机。

**Q9 源制式**：SDI 到底是 1080p25 还是 29.97／30（帧率决定 §4.6 预算和 M4 的判据）。**盘上有一条旁证（B）**：`魔改厂商视频流程部署记录.md:99` 写现役档位 `EVERY=3` 时"恰好整除**采集侧 30.06 fps**"⇒ 采集侧是 30/29.97 档，不是 25；而 §4.6 那张表是按 25 fps 算的（30 fps 时帧预算降到 3.72 MB，结论不变）。几何只实测到 1920×1080。

**Q10 PS 侧那颗 `CONFIG_XILINX_AXI_EMAC`（内核未开，A：`34_kernel_config_from_Image.txt:1413`）与 `CONFIG_MOTORCOMM_PHY`（未开，A：`:1461`）**：如果哪天想让 Linux 管 PL 网口（走 `axienet`）就要重配内核。**本方案刻意不需要**——列在这里只为防止有人把它当成前置条件。

---

## 15. 参考

| 文档 | 用途 | 盘上有没有 |
|---|---|---|
| PG051《Tri-Mode Ethernet MAC》 | **现在真正需要的那本**：TEMAC 的 AXIS 帧接口、管理寄存器面、TX underrun 行为 | **没有**（本地无副本）。§5.3／§10.3 的寄存器偏移原本按 AXI Ethernet 写，改成 TEMAC 后要照 PG051 重推一遍 |
| PG138《AXI Ethernet Subsystem》 | ~~本方案的主 MAC~~ | **不再需要**：`axi_ethernet` v7.1 在本地这套 2018.3.1 里综合不过（§16.2）。留着只在"以后想换 AXI Ethernet"时用 |
| PG160《GMII to RGMII》 | 理解 RGMII 时序与 delay；本方案不例化它 | 未核 |
| PG085《AXI4-Stream FIFO》 | 码流缓冲 | 未核 |
| UG585 Zynq-7000 TRM | 本方案不碰 PS GEM，仅背景 | 未核 |
| XAPP1082 | TEMAC + RGMII 工程组织参考 | 未核 |
| RFC 791 / RFC 768 | 报文头与校验和 | ✓ 规则已在 §4.3-4.4 落成算术 |
| ITU-T T.81 (JPEG) | 位填充规则 ⇒ §5.2 的 EOI 检测成立前提 | 未核（依赖 Q7） |
| 悟净完整版手册 4.8 节 | **给 PL 网口 15 个球号**（A）；Bank 已由工具反查完毕（§16.4）；**仍不给 VCCIO**，这是 Q1 唯一剩下的空洞 | ✓ `wiki/PS/board_extract/41_manual_full_extracted.txt:221-235` |
| YT8521S 数据手册（motorcomm.cn） | RGMII delay、strap、PHYAD、寄存器 | 未核（Q4） |
| `wiki/todo/位流构建与SDI信号检测.md` | MMCM/资源/时序现状、SDI 无帧结论、寄存器面与地址冲突 | ✓ |
| `wiki/SOP/BOOTbin位流替换手术.md` | 部署方式、槽位、点火门禁、`fatwrite` 回滚 | ✓ |
| `wiki/todo/PL位流重载通道失效.md` | 为什么只能走手术；给厂商的问题单 | ✓ |
| `wiki/todo/板卡镜像实测取证.md:459-470` | `/dev/mem` mmap 的 A 级 strace（§10.2 的依据） | ✓ |
| `wiki/archive/开发管理/状态源与决策记录.md` D-02 | 本方案在台账里的范围归属 | ✓ |

---

## 16. 实验 A 实测结果（2026-10-26，本机跑，A 级）

**这一节是本方案所有改判的唯一出处**——§7／§12／§13／§14 里那些"见 §16"都指到这里，别处不复述表格。

**运行条件（可复现）**：Vivado 2018.3.1（`S:\apps\Xilinx\Vivado\2018.3`）＋器件 `xc7z030ffg676-2`（**不是 `xc7z030ai`**；正本工程 `repos/sdi2hdmi/build.tcl:174` 用的就是这颗）。阶段只到 `synth_design`／`opt_design`／`place_design`／`report_drc`，**没跑 route、没出位流**。所有工程与脚本落在 `workenv/pl-probe/`（`.gitignore` 内，不入库）。**全程没碰开发板、没改厂商任何一份文件**——这也是你选 A 的前提（"是不会搞坏是吧"）成立的方式：A 只吃本机的工具和我自己写的探针文件。

### 16.1 A1：原语支持探针（＝你问的那个"5 分钟工程"）

你原话是"只实例化 ODDR1/IDDR1/ODDR2 看综合器认不认"。**是同一件事**，只有名字要改：7 系列没有 `ODDR1`/`IDDR1`，UltraScale 那对叫 `ODDRE1`/`IDDRE1`，`ODDR2` 存在。所以探针跑的是 11 颗：`FDRE`（正对照）`ODDR` `IDDR` `ODDRE1` `IDDRE1` `ODDR2` `OSERDESE2` `ISERDESE2` `IDELAYE2` `IDELAYCTRL` `MMCME2_BASE`。探针文件不是手写的——从 `data/unisim_comp.v` 逐颗解析端口名与方向自动生成（`workenv/pl-probe/rtl/probe_<CELL>.v`），只有正对照 `probe_FDRE.v` 是手写的。

| CELL | synth | place | DRC | 读数来源 |
|---|---|---|---|---|
| FDRE | PASS | PASS | CLEAN | `a1-result.txt` / `a1b-result.txt` |
| ODDR | PASS | PASS | CLEAN | 同上 |
| IDDR | PASS | PASS | CLEAN | 同上 |
| **ODDRE1** | **PASS** | **FAIL** | — | `a1b-result.txt:10` |
| **IDDRE1** | **PASS** | **FAIL** | — | `a1b-result.txt:12` |
| ODDR2 | PASS | —（未跑） | — | `a1-result.txt`：网表 REF 回落成 `ODDR`，等价于 ODDR |
| OSERDESE2 | PASS | PASS | CLEAN | `a1b-result.txt` |
| ISERDESE2 | PASS | PASS | CLEAN | `a1b-result.txt` |
| IDELAYE2 | PASS | —（未跑） | — | `a1-result.txt`（5 leaves，含 BUFG） |
| IDELAYCTRL | PASS | —（未跑） | — | `a1-result.txt` |
| MMCME2_BASE | PASS | —（未跑） | — | `a1-result.txt`：网表 REF 是 `MMCME2_ADV` |

`ODDRE1` 被拒时的三条逐字消息（`a1b-run.log`，行号 1449／1453／1469）：

```
CRITICAL WARNING: [Netlist 29-180] Cell 'ODDRE1' is not a supported primitive for zynq part: xc7z030ffg676-2.  Instance 'U' will be treated as a black box, not an architecture primitive [S:/work/WCIS/workenv/pl-probe/rtl/probe_ODDRE1.v:4]
CRITICAL WARNING: [Project 1-486] Could not resolve non-primitive black box cell 'ODDRE1' instantiated as 'U'
ERROR: [DRC INBB-3] Black Box Instances: Cell 'U' of type 'ODDRE1' has undefined contents and is considered a black box.  The contents of this cell must be defined for opt_design to complete successfully.
   place: ERROR: [Opt 31-236] Found primitives driven by Empty Hierarchy Cells/Black boxes.
```

**方法学结论（比结果更值钱）**：**只看综合会给出假绿灯。** `ODDRE1`/`IDDRE1` 在 `synth_design` 阶段两颗都 PASS，直到 `opt_design`/`place_design` 才炸。⇒ 本方案任何"器件库缺不缺件"的判断，**必须跑到 place＋DRC**，不能停在综合。我上一版就是停在综合得出反向结论的（§13 R2 已公开更正）。

**另一条要记住的**：手写的 `probe_FDRE.v` 第一版**失败**过——我给 7 系列的 `FDRE` 接了根本不存在的 `.S` 脚，工具报 `[Common 17-69] Synthesis failed`，删掉 `.S` 后 PASS。⇒ 工具不会因为"名字像"就放过你，自动解析端口这件事不是可省的方便，是正确性前提。

### 16.2 A2：本器件的 IP 目录 ＋ 三颗候选 IP 的建／生成／综合

`list_project_templates` 不算，直接问器件目录（`a2b-catalog.txt`）：`xc7z030ffg676-2` 可见 **292** 条 ipdef，其中名字含 ethernet 的 **9** 条（`axi_10g_ethernet:3.1`／`axi_ethernet:7.1`／`tri_mode_ethernet_mac:9.0`／`ethernet_1_10_25g:2.2`／`tsn_endpoint_ethernet_mac:2.0`／`gig_ethernet_pcs_pma:16.1`／`l_ethernet:2.4`／`xxv_ethernet:2.5`／`axi_ethernetlite:3.0`），含 gmii 的 **3** 条（`gmii_to_rgmii:4.0`／`usxgmii:1.0`／`quadsgmii:3.4`）。**⇒ "盘上没有厂商 IP 副本"根本不构成前提：TEMAC 是随 Vivado 装的。**

| IP | create_ip | generate_target all | `synth_design -mode out_of_context` |
|---|---|---|---|
| `tri_mode_ethernet_mac` 9.0 | OK | OK | **OK**（GMII：5 599 leaves／213 REF；RGMII 见 §16.3） |
| `axi_ethernet` 7.1 | OK | OK | **FAIL** |
| `gmii_to_rgmii` 4.0 | OK | OK | OK（258 leaves／33 REF） |

`Physical_Interface` 的合法值是一条拒绝消息告诉我的（`a2d-run.log:89`，逐字）：

```
ERROR: [IP_Flow 19-3461] Value 'SGMII' is out of the range for parameter 'PHY Interface(Physical_Interface)' for IP 'tri_mode_ethernet_mac_u' . Valid values are - RGMII, GMII, MII, Internal
```

`axi_ethernet` 的失败原因（`a2d-run.log:1154`，逐字）：

```
ERROR: [Synth 8-439] module 'bd_ae5e_c_counter_binary_0_0' not found [s:/work/WCIS/workenv/pl-probe/a2prj/axi_ethernet/a2c_axi_ethernet.srcs/sources_1/ip/axi_ethernet_u/bd_0/synth/bd_ae5e.v:301]
```

⇒ 它 BD 里引用的子 IP（`c_counter_binary`）在这套安装里生成不出来，**AXI Ethernet Subsystem 在本地不可用**（不是"配置没配对"，是缺件）。§7 因此定死 **TEMAC 为唯一 MAC**，P10 那条"TEMAC 会不会落不了地"的资格风险已经划掉。

### 16.3 TEMAC 设成 RGMII 之后的网表读数

`m0-probe.tcl` 建 `Physical_Interface=RGMII` 的 TEMAC，`generate_target all` ＋ OOC 综合全过：**5 644 个 leaf、216 个不同 REF_NAME、整份运行日志里 `[Netlist 29-180]` 命中 0 条**（算式：`grep -c 'Netlist 29-180' m0-run.log` → `0`；读数来源 `m0-result.txt:12-13`）。网表里出现的时钟／IO 相关原语（`m0-result.txt:15-21`）：`ODDR present = 1`、`IDDR present = 1`、`IDELAYE2 present = 1`、`BUFIO present = 1`、`BUFR present = 1`，而 `ODDRE1 present = 0`、`IDDRE1 present = 0`——**它用的是 7 系列原生件，不碰 §16.1 里那两颗会被拒的 UltraScale 件**。这就是"方案 B 不会白做"的直接证据。

两条从这里读出来的具体约束：

- **网表里有 `IDELAYE2`、没有 `IDELAYCTRL`** ⇒ `IDELAYCTRL` 需要的那个 200 MHz 参考时钟**这一版不需要**（§7 第 7 条据此改写）。剩下的时钟问题只有"90° 相位"这一件。
- **RGMII 变体的 OOC 约束直接把两颗时钟摆出来**（`a2prj/m0_temac_rg/.../temac_rg/synth/temac_rg_ooc.xdc`，逐字）：

  ```
  create_clock -name gtx_clk_ooc  -period 8.000 [get_ports gtx_clk]
  set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports gtx_clk]
  create_clock -name gtx_clk90_ooc -period 8.000 [get_ports gtx_clk90]
  set_property HD.CLK_SRC BUFGCTRL_X0Y1 [get_ports gtx_clk90]
  ```

  两者同 period 8 ns＝**同为 125 MHz**，`gtx_clk90` 是**输入脚**（IP 要你把 90° 那一路从外面喂进来），且被要求走两个不同的 BUFGCTRL 位置。⇒ §13 R3 的正确表述是"多一路 90° 相移的时钟输出"，不是"多两个频率"。这件事的真实难度来自另一条读数：现役工程 **MMCM 已 5/5 用满**（读数 `wiki/todo/位流构建与SDI信号检测.md:293`，把这条标成 C 级余量提醒的是同页 `:297`）——所以 90° 那一路要么挤掉现有负载、要么重排 clocking，得先算资源再谈。至于"用 PS 的 FCLK 代替"：FCLK 的分频不带相位控制（B，未在本地查证），不能当兜底。
- 观察（B，别当结论）：RGMII 变体的 OOC 网表 REF 列表里**没有 `BUFG`/`BUFGCTRL`**、却有 `BUFIO`/`BUFR`。BUFIO/BUFR 要求时钟从对应时钟区域的专用脚进来，而 `AC23` 恰好是 `IO_L12P_T1_MRCC_13`（§16.4），方向是对的；但 OOC 阶段本来就可能不插 BUFG，**这条要等实现层再看**。

**TEMAC RGMII 的 60 个端口**（`awk` 数 `synth/temac_rg.v` 端口声明行 → 60；分组照抄）：`gtx_clk`／`gtx_clk90`／`glbl_rstn`／`rx_axi_rstn`／`tx_axi_rstn`；RX 侧 `rx_enable`、`rx_statistics_vector[27:0]`、`rx_statistics_valid`、`rx_mac_aclk`、`rx_reset`、`rx_axis_mac_tdata[7:0]`、`tvalid`、`tlast`、`tuser`、`rx_axis_filter_tuser[4:0]`；TX 侧 `tx_enable`、`tx_ifg_delay[7:0]`、`tx_statistics_vector[31:0]`、`tx_statistics_valid`、`tx_mac_aclk`、`tx_reset`、`tx_axis_mac_tdata[7:0]`、`tvalid`、`tlast`、`tuser`、**`tx_axis_mac_tready`**；`pause_req`、`pause_val[15:0]`、`speedis100`、`speedis10100`；RGMII 脚 6 根 `rgmii_txd[3:0]`/`rgmii_tx_ctl`/`rgmii_txc`/`rgmii_rxd[3:0]`/`rgmii_rx_ctl`/`rgmii_rxc` ＋ `inband_link_status`/`inband_clock_speed[1:0]`/`inband_duplex_status`；MDIO `mdio`(inout)/`mdc`；AXI-Lite `s_axi_aclk`/`s_axi_resetn`/`s_axi_awaddr[11:0]`/…

对 §5/§6 有直接后果的三点：**TX AXIS 位宽只有 8 位**（`tx_axis_mac_tdata[7:0]`）⇒ packetizer 按字节喂，§6 的缓冲深度不用为宽总线重算；**`tx_axis_mac_tready` 存在**⇒ 反压是可选的，不做反压也能活（IP 自己会 underrun，判据要照 PG051 补，见 §15）；**没有 `s_axi_*` 之外的管理面**，`inband_*` 是只读状态，链路速度得靠 MIIM 轮询 PHY。

### 16.4 手册那 15 个球 → Bank（`report_io` 实测，A 级）

`m0b-pins.tcl` 把 `wiki/PS/board_extract/41_manual_full_extracted.txt:221-235` 的 15 个球全绑成真实 IO（1 个 125 MHz 输入做垫子），`synth`＋`place`＋`report_io`。结果：**15 个球全部是本器件的合法用户 IO**，先前 `m0-probe.tcl` 报的"NOT A PIN OF THIS PART"是我自己用错命令的假阴性（`get_package_pins` 要先有 open design，被 `-quiet` 吞掉的 `ERROR: [Common 17-53] No open design`，诊断见 `diag.tcl`）。

| 球 | 信号 | Bank | IO 名 | 方向 |
|---|---|---|---|---|
| AD23 | PL_PHY_TX_CLK | 13 | `IO_L11P_T1_SRCC_13` | OUTPUT |
| AD26 | PL_PHY_TX_CTRL | 13 | `IO_L4N_T0_13` | OUTPUT |
| AF24 / AF25 / AA24 / AB24 | TXD0..3 | 13 | `IO_L5P_T0_13` / `IO_L5N_T0_13` / `IO_L6P_T0_13` / **`IO_L6N_T0_VREF_13`** | OUTPUT |
| AC23 | PL_PHY_RX_CLK | 13 | `IO_L12P_T1_MRCC_13` | INPUT |
| AA25 | PL_PHY_RX_CTRL | 13 | `IO_L1P_T0_13` | INPUT |
| AB26 / AC26 / AE25 / AE26 | RXD0..3 | 13 | `IO_L2P_T0_13` / `IO_L2N_T0_13` / `IO_L3P_T0_DQS_13` / `IO_L3N_T0_DQS_13` | INPUT |
| AE22 / AF22 | MDC / MDIO | 13 | `IO_L7P_T1_13` / `IO_L7N_T1_13` | OUTPUT / **BIDIR** |
| **AA13** | **PL_PHY_RESET** | **12** | **`IO_L6P_T0_12`** | OUTPUT |

算式：Bank 13 里 **14** 根 ＋ Bank 12 里 **1** 根（`AA13`）＝ **15**。⇒ 手册那句"Bank 13"（我上一版照抄的）**只对 14／15 根**，复位那颗在 **Bank 12**，XDC 要跨两个 bank（§7 第 8 条据此改写）。15 行的读数来源：`m0pins/report_io_LVCMOS18.txt` 的 `:76,87,88,113,115,138,141,164,167,189,192,193,215,217,218`（一条一行，正好 15 行；`AD20` 那行 `:161` 是我垫的 125 MHz 测试脚，不属于网口）。

**HSTL 这条路被工具当场堵死**（全部绑 `HSTL_I_18` 时 `place_design` 直接失败，`m0b-run.log:939`，逐字）：

```
ERROR: [DRC BIVRU-1] Bank IO standard Vref utilization: Bank 13 contains ports that use a reference voltage. ... Example port: PL_PHY_RXD0 (HSTL_I_18).  However, the following VREF sites are occupied and can't be used to supply the necessary voltage:
site IOB_X0Y87 (occupied by port PL_PHY_TXD3).
```

外加一条 `CRITICAL WARNING: [DRC IOSTDTYPE-1]`：`PL_PHY_MDIO is bidirectional but has an IOStandard of HSTL_I_18 which can only support inputs or outputs`（`m0b-run.log:942`）。⇒ 按工具的判定，**这 15 根只能用 LVCMOS 族**：全绑 `LVCMOS18` 那一版 `SYNTH OK`／`PLACE OK`／`DRC errors = 0`（`m0b-result.txt`）。
一个我没查清的角落：bank 13 里名字带 `VREF` 的脚不止 `AB24`（`IO_L6N_T0_VREF_13`），还有一颗空闲的 `Y20`（`IO_L19N_T3_VREF_13`），但 `BIVRU-1` 只点名 `IOB_X0Y87`、没把 `Y20` 当作可用解。**为什么不算，这轮没查**——它不影响"LVCMOS 过、HSTL 报死"这条读数，但谁将来想用需要 VREF 的标准（HSTL 之类）碰这组脚，得先把这一点弄明白。

**这里必须挡住一个误读**：同一份 `report_io` 里 `VCCO_13`、`VCCO_12` 那几行印着 `1.80`（`:79,89,102,112,125,135,158,181,191`）——**那是我自己约束 `LVCMOS18` 的后果，不是对板子的测量**（我没设 `BANK_VCCO`，脚本里可查）。⇒ **Q1 没有被这一步关掉**：还缺的就是"这两颗 bank 的 VCCIO 实际是 1.8 还是 2.5"，它决定 `LVCMOS18` 还是 `LVCMOS25`，而这个只有原理图／厂商一句话能给。

### 16.5 三条附带发现

1. **厂商 demo 的"网络"根本不在 PL 里**（回答"官方 demo 都成功了，我们的问题在哪"）。BD 的 PS7 参数（`repos/FPAI30TAI图像FPGA/case/fpai_demo_vivado.srcs/sources_1/bd/ps_ai/ip/ps_ai_processing_system7_0_0/ps7_parameters.xml`）逐字：`:55` `PCW_ENET0_ENET0_IO = MIO 16 .. 27`、`:65` `PCW_ENET1_ENET1_IO = ""`、`:71` `PCW_ENET1_PERIPHERAL_ENABLE = 0`、`:75-77` 复位使能／Active Low／Share reset pin。再加上整份 case 只有一个 BD（`find -name '*.bd'` → `ps_ai.bd` 一份），而它里面用到的 IP 全集是 `processing_system7`／`axi_crossbar`／`axi_interconnect`／`axi_register_slice`／`proc_sys_reset`／`util_vector_logic`／`xlconcat` 七种（`grep -oh '"xilinx.com:ip:...' ps_ai.bd | sort -u`）——**没有任何 MAC**。⇒ **demo 跑通证明的是 PS GEM0 ＋ Linux 软件栈，跟 PL 位流路径一点关系都没有**。我们的堵点全在"位流能不能自己建／自己下"，这两件事不共享任何证据。
2. **厂商 NPU 那次 `opt_design` 失败，和我这次复现的不是同一种失败**（这条是对我自己上一版类比的收紧）。我这颗是"器件库里没这颗原语"→ `Netlist 29-180`→`DRC INBB-3`→`Opt 31-236`（§16.1 逐字）。NPU 那次报的是 `ERROR: [Opt 31-67] LUT2 缺 I0 连接 U0_ps_ai_peripheral/ZGolo/u_ai_io/s_data[10]_i_2` ＋ 109 条 `Opt 31-430` FDCE 数据脚无驱动（`wiki/todo/位流构建与SDI信号检测.md:105-106`、`:241`；另一例 `wiki/PS/板端我方代码与产物台账.md:667`）——**被点名的 cell 在 EDIF 内部、说明件已经装载进来了**，缺的是连接不是件。⇒ 给队友的 Q6-a 该问的是"悬空网络那一步你们怎么消的"，而不是"你们换了器件库补丁没有"。真正属于"缺件"那一类的，是 `wiki/todo/位流构建与SDI信号检测.md:241` 末尾那句另一条线（10-09 12:18 的 `build_full_030ai.log`，综合 27 秒就失败，归因＝器件库补丁没装对）。
3. **手册提取件早就有那 15 个球**：`wiki/PS/board_extract/41_manual_full_extracted.txt:221-235`，`:197-198` 还写了"两片 YT8521，一片接 PS、一片接 PL"。我上一版说的"板卡原理图／PHY 引脚全仓零命中"是错的（§14 Q5 已公开更正）。

### 16.6 这轮**没**证到的（别把 §16 读成"全都清了"）

- TEMAC 只做到 **OOC 综合**。没跑 place／route／时序／位流，也**没在含 PS7＋NPU 的真工程里连进去跑过**——M0 剩下的正是这一段。
- **两颗 bank 的 VCCIO 未知**（§16.4 末段），`LVCMOS18` 只是"DRC 全过的那一档"，不是"板子接的那一档"。
- `AA13` 到底是复位还是被复用成别的（手册这么写，没有原理图佐证）；`AB24` 的 P／N 极性我按单端用，`rgmii_*` 的 DDR 边沿时序要靠实现层。
- PHY 侧的 `PHYAD`、RGMII delay 是 PHY 内部还是 FPGA 内部做（YT8521S 手册盘上没有，Q4）。
- 交换机 IGMP snooping（Q8）、源制式 25／30 fps（Q9）、队友 MJPEG 编码器的接口契约（Q7）——**这三条没有一条能靠本机实验解决**。

### 16.7 复现

```
cd S:/work/WCIS/workenv/pl-probe
S:/apps/Xilinx/Vivado/2018.3/bin/vivado.bat -mode batch -source a1-probe.tcl   # 16.1 综合层
S:/apps/Xilinx/Vivado/2018.3/bin/vivado.bat -mode batch -source a1b-place.tcl  # 16.1 place+DRC 层
S:/apps/Xilinx/Vivado/2018.3/bin/vivado.bat -mode batch -source a2-build.tcl   # 16.2 三颗 IP
S:/apps/Xilinx/Vivado/2018.3/bin/vivado.bat -mode batch -source m0-probe.tcl   # 16.3 TEMAC=RGMII 网表
S:/apps/Xilinx/Vivado/2018.3/bin/vivado.bat -mode batch -source m0b-pins.tcl   # 16.4 15 球 → bank
```

每步的 stdout 同步落 `a1-result.txt`／`a1b-result.txt`／`a2-result.txt`／`m0-result.txt`／`m0b-result.txt`，完整工具消息在对应的 `*-run.log`（§16 里所有逐字消息都能在里面 `grep` 到）。

