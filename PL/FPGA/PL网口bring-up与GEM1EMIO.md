# PL网口bring-up与GEM1EMIO

> **本页回答什么问题**：悟净完整版那只"PL 网口"到底是什么、为什么 RJ45 灯亮而系统里没有第二个网口、要用起来该走哪条路、改哪几个参数、怎么判它通了、为什么**不需要**先拿到 PHY 手册、以及**现在卡在哪一层**（顶层缺 RGMII 透传）。
> **前置阅读**：[[板载接口与内核改造收纳进dev]]（逐接口三层核对表、§九到板必查、§十一六个接口用途）、[[板子（除芯片）]]（以太网两路的来源与口径冲突）、[[dict]]（GEM／EMIO／GMII／RGMII／GMII-to-RGMII／TEMAC 六个词条）。
> **本页是结论页兼操作页**，证据等级按 [[状态源与决策记录]] 的 A／B／C 口径标注。
> **最后更新**：2026-11-06。**下次开工第一件事**看 §13.8 交接；选型已裁（A2，见 12.1），不再讨论。

---

## 〇、六条先给结论

1. **板上确实有两颗 YT8521**：一颗接 PS（MIO16–27 + MDIO52–53 + 复位 MIO49），**一颗接 PL**（RGMII 12 线 + MDC/MDIO + 复位，全在 PL 引脚上）。出处：完整版手册 §4.8（`41_manual_full_extracted.txt` 第 195–235 行）。轻量版只有 PS 那一路。
2. **PL 那颗 PHY 的 RGMII 与 MDIO 全部落在 PL Bank13（HR 银行），复位脚在 Bank12**（A：对 `xc7z030ffg676-2` 用 Vivado `get_package_pins` 实查，见第二节表）。
3. **灯亮不等于有数据**：RJ45 的 link 灯由 PHY 自己点，只要 PHY 上电并与对端自协商成功就亮，**与 MAC 在不在、通不通数据无关**。现役厂商位流里没有以太网 MAC，所以"灯亮、系统里没有 eth1"是预期现象，不是 PHY 坏。
4. **第二路 MAC 是 PS 硬核 GEM1，经 EMIO 穿到 PL，不是要在 PL 里写软 MAC**（A：厂商 PS7 IP 的 `component.xml` 里 `GMII_ETHERNET_1`／`MDIO_ETHERNET_1` 两个接口存在，使能条件就是 `PCW_EN_EMIO_ENET1=1` 与 MDIO 选 EMIO；**并且已在厂商工程副本上实跑验证**——改完 `set_property` rc=0、`validate_bd_design` rc=0、`generate_target` rc=0、两个接口都出现，见第十一节）。本页据此把 [[板载接口与内核改造收纳进dev]] §九那条悬项判为 **A、PS 硬核经 EMIO**。
5. **厂商 demo 只是没打开**：`ps_ai_processing_system7_0_0.xci` 里 `PCW_EN_ENET1=0`、`PCW_EN_EMIO_ENET1=0`、`PCW_ENET1_ENET1_IO=<Select>`、`PCW_ENET1_GRP_MDIO_ENABLE=0`、`PCW_ENET1_RESET_ENABLE=0`（A）。MIO0–15 已被 QSPI／SPI1／CAN0 占满，**GEM1 只能走 EMIO**。
6. **内核侧是现成的**：`CONFIG_DWMAC_FMQL=y`、`CONFIG_XILINX_GMII2RGMII=y`、`CONFIG_STMMAC_ETH=y` 全内建；反面是 `CONFIG_XILINX_AXI_EMAC` 与 `CONFIG_MOTORCOMM_PHY` **都没开**（A：`34_kernel_config_from_Image.txt`）。这两行基本决定了走"PS 硬核 + 转换核"而不是"PL 软 MAC"。
7. **顶层透传：10-30 时是卡点，2026-11-06 已在工程副本里做通（A）**。当时的事实是"工程真正顶层是手写的 `rtl/ai7030_edif_top.v` → `rtl/ps_ai_peripheral.sv`（1937 行）→ 第 1033 行才例化 `ps_ai_wrapper`，而 `ps_ai_peripheral.sv` 里没有 RGMII/MDIO 端口 ⇒ BD 里引出的 `RGMII_0` 传不到芯片引脚，XDC 和综合都做不下去"。**现在的状态**：三层 RTL（`rtl/ps_ai_wrapper.sv` 手抄件 → `ps_ai_peripheral.sv` → `ai7030_edif_top.v`）都改完、`launch_runs synth_1` **0 Errors**、实名顶层 XDC 两趟复校 **0 ERROR**，读数与脚本清单在 **12.1.1**。没做的只剩实现／位流／上板。~~必须先选 A2 或 B2~~ ⇒ **2026-11-06 她裁定只走 A2（改厂商 RTL 透传），A2 不成即放弃这只口**；B2 同日由"废弃"改判成**只作离线探针**（不上板、不作交付路线）。**执行序（D-1793904039）＝有界 PHY 诊断 → B2 离线探针 → A2 出整份位流**，前两步是 A2 的前置；门禁＝**本轮不动位流、不重启板子**，要动逐次请示。决策正本＝D-1793903698 与 D-1793904039，落点见 [[plnet]] 第三节，详见 12.1——那里还有一条**范围补正**：BD 只引出 `RGMII_0_*` 那一半已由 12.1.1 的 ①②③ 补完，MDIO／复位既引到了 BD 外部、也透到了顶层引脚名。
8. **乙类实测（插 PC）已证明 PHY 活着**：PC 侧 Realtek 驱动 61 秒内 6 次 `tx hang` 后判 **Code 43**；同刻板子 eth0 仍 100M／0 错误。**副作用：PC 网卡从 Code 43 → Code 22 → 拔线后自行恢复 `Status=OK / ErrCode=0`（网卡本身没坏）**，全程见 11.2.1。

> **截止 2026-10-30 夜的真实进度一句话**：路线已判明（PS 硬核 GEM1 经 EMIO + `GMII_to_RGMII`）、BD 侧改完并验证通过（`validate` 与 `generate_target` 均 rc=0）、PHY 已被实测确认是活的；**唯一卡点**是顶层 `ps_ai_peripheral.sv` 不含 RGMII 端口，A2（改厂商 RTL 透传）／B2（另起最小工程）**尚未选择**——所以 XDC、综合、比特流、上板全都没开始。
>
> **2026-11-06 更新（D-1793903698 ＋ D-1793904039）**：上面那句里"尚未选择"这一项**已裁**——她原话「定a2，a2不成就放弃」，即**只走 A2**（改 `ps_ai_peripheral.sv` ＋ `ai7030_edif_top.v` 做顶层透传）、**A2 不成即放弃这只口**；"不成"的判据边界仍是草案、待她认。同日她补了执行序与门禁（原话「除了不动位流不重启板子外你随便动：有界 PHY 诊断（一次重启窗口）→ B2 离线探针（不碰板子）→ A2 落到厂商 RTL 出整份位流。要动的时候问我要许可」）：**B2 不作交付路线，但改判成只作离线探针**（不上板），前两步是 A2 的前置。⇒ 下次开工不再讨论选型，照 ①有界 PHY 诊断→②B2 离线探针→③A2 出位流 的顺序做，从 12.1 那条**范围补正**起手（先 BD 引外部＋重生成 wrapper，再改两个 RTL 文件）；**本轮不写位流、不重启板子**。**A2 本身零实测进度**，这两条只关掉选型与排序。

---

## 一、这块网口在硬件上长什么样

手册 §4.8 原文（完整版）：

> "Demo 板采用两片 PHY 芯片，它们为裕太微的 YT8521 以太网 PHY 芯片，可以实现 2 路 10/100/1000Mpbs 自适应以太网接口。其中一片以太网 PHY 芯片为 YT8521 连接至 FMQL30TAI 的 PS 端，**一片以太网 PHY 芯片连接至 FMQL30TAI 的 PL 端**。"

PL 那片给的信号（手册引脚表，**只有引脚号、没有网络名**）：

| 组 | 信号 | 引脚 |
|---|---|---|
| 发 | `PL_PHY_TX_CLK` / `TX_CTRL` / `TXD0..3` | AD23 / AD26 / AF24 AF25 AA24 AB24 |
| 收 | `PL_PHY_RX_CLK` / `RX_CTRL` / `RXD0..3` | AC23 / AA25 / AB26 AC26 AE25 AE26 |
| 管理 | `PL_PHY_MDC` / `PL_PHY_MDIO` | AE22 / AF22 |
| 复位 | `PL_PHY_RESET` | AA13 |

对照 PS 那片的复位 `W14`（手册写作 `IO_0_12`）可知：**两颗 PHY 的复位都由 PL 引脚驱动**。PS 那颗现在能用，说明厂商位流里有一小段板级胶合逻辑在拉 `W14`；PL 那颗的 `AA13` 在现役位流里没有对应逻辑。

---

## 二、这 15 个脚落在哪个 Bank（A，Vivado 实查）

对 `xc7z030ffg676-2` 执行 `get_package_pins` 的 `PIN_FUNC`（末段即 bank 号）：

| 引脚 | PIN_FUNC | Bank |
|---|---|---|
| AD23 | `IO_L11P_T1_SRCC_13` | 13 |
| AD26 | `IO_L4N_T0_13` | 13 |
| AF24 / AF25 | `IO_L5P_T0_13` / `IO_L5N_T0_13` | 13 |
| AA24 / AB24 | `IO_L6P_T0_13` / `IO_L6N_T0_VREF_13` | 13 |
| AC23 | `IO_L12P_T1_MRCC_13` | 13 |
| AA25 | `IO_L1P_T0_13` | 13 |
| AB26 / AC26 | `IO_L2P_T0_13` / `IO_L2N_T0_13` | 13 |
| AE25 / AE26 | `IO_L3P_T0_DQS_13` / `IO_L3N_T0_DQS_13` | 13 |
| AE22 / AF22 | `IO_L7P_T1_13` / `IO_L7N_T1_13` | 13 |
| **AA13（复位）** | `IO_L6P_T0_12` | **12** |

两条推论，都要在原理图上确认（**C**，未验证）：

- **Bank13 是 HR 银行**（`BT_HIGH_RANGE`）。7 系列里 HP 才是为高速 I/O 设计的，HR 上限低一档；而 1G RGMII 是 **125 MHz DDR**。**如果 Bank13 的 VCCO 是 3.3 V，千兆很可能稳不住，100M（25 MHz）才舒服**——这与厂商资料里"板载网口只支持百兆、把上位机网卡设 100M 全双工"的口径方向一致。
- **Bank13 与 PL 串口共用**（`AE23/AF23` = `IO_L8P/N_T1_13`，手册 §4.11），同一个 bank 只有一个 VCCO，**串口电平直接决定网口能不能跑千兆**。

---

## 三、为什么"灯亮、但芯片识别不了"

三件事要分开：

1. **PHY 层**：上电 + 对端自协商成功 → link 灯亮。**这一步不需要 MAC**。
2. **MDIO 层**：谁去读 PHY 的 ID（`0x02/0x03`）？**要有 MAC 当 MDIO master**。现役位流没有 MAC，所以没人读，系统里当然"识别不到"。
3. **MAC／驱动层**：Linux 只认设备树里 `status="okay"` 且驱动 probe 成功的 MAC。随镜像 dtb 里 `ethernet@e0047000`（GEM0）是 okay，`ethernet@e0049000`（GEM1）是 disabled（A：`36_dtb_node_status.txt`）。

所以"识别不了"的准确说法是：**链路的 MAC 那一半还不存在**，不是 PHY 坏、不是线坏、也不是"网络太快"。

---

## 四、三条路线，按本镜像现状排序

| 路线 | 结构 | 本镜像代价 | 结论 |
|---|---|---|---|
| **A（推荐）** | PS GEM1 → EMIO（GMII + MDIO）→ `GMII_to_RGMII`（PG160）→ Bank13 的 14 个脚 | 只出比特流 + 改 dtb；`GMII2RGMII` 驱动已内建 | **唯一零内核改动的路** |
| B | PL 里放 `AXI 1G/2.5G Ethernet Subsystem`（TEMAC，PG138） | `CONFIG_XILINX_AXI_EMAC` 未开 → 要重编内核；占 3–5k LUT | 备选，ENET1 拿不到 EMIO 才考虑 |
| C | 纯 RTL MAC（自写／liteeth）+ AXI DMA | 工作量最大，但不依赖内核网络栈 | 只适合"PL 直出码流"的自研点 |

**为什么 A 是硬的**：GEM1 的 MIO 通道（0–15）已经被 QSPI/SPI1/CAN0 占满（A：XCI 的 `PCW_MIO_TREE_PERIPHERALS`），**物理上不存在"用 MIO 接回 PS"的选项**，而板上 PHY 又确实接在 PL 引脚上——厂商的硬件设计本身就是按"EMIO 穿出去"做的。

---

## 五、PS7 IP 的实际配置（A，读 XCI）

文件：`fpai_demo_vivado.srcs/sources_1/bd/ps_ai/ip/ps_ai_processing_system7_0_0/ps_ai_processing_system7_0_0.xci`

| 参数 | ENET0（PS 口） | ENET1（PL 口） |
|---|---|---|
| `PCW_EN_ENETx` | 1 | **0** |
| `PCW_ENETx_PERIPHERAL_ENABLE` | 1 | **0** |
| `PCW_ENETx_ENETx_IO` | `MIO 16 .. 27` | **`<Select>`** |
| `PCW_EN_EMIO_ENETx` | 0 | **0** |
| `PCW_ENETx_GRP_MDIO_ENABLE` | 1 | **0** |
| `PCW_ENETx_GRP_MDIO_IO` | `MIO 52 .. 53` | **`<Select>`** |
| `PCW_ENETx_RESET_ENABLE / IO` | 1 / `MIO 49` | **0 / `<Select>`** |
| `PCW_ACT_ENETx_PERIPHERAL_FREQMHZ` | 125 | 10（未启用时的默认） |
| `PCW_EN_PTP_ENETx` | 0 | 0 |

四个 FCLK 当前**全是 50 MHz**（`PCW_FPGA0..3_PERIPHERAL_FREQMHZ`），BD 里**只用了 FCLK_CLK0**，FCLK1/2/3 空着。

---

## 六、IP 里这扇门确实存在（A，component.xml 原文）

`PS_AI IP/processing_system7_v5_5/component.xml`：

```xml
<!-- GMII 接口：只要 ENET1 选 EMIO 就出现 -->
<xilinx:isEnabled xilinx:id="BUSIF_ENABLEMENT.GMII_ETHERNET_1"
  xilinx:dependency="(PARAM_VALUE.PCW_EN_EMIO_ENET1) = 1">false</xilinx:isEnabled>

<!-- MDIO 接口：MDIO 也选 EMIO 且使能才出现 -->
<xilinx:isEnabled xilinx:id="BUSIF_ENABLEMENT.MDIO_ETHERNET_1"
  xilinx:dependency="((PCW_ENET1_GRP_MDIO_IO) = 'EMIO')
                 &amp;&amp; ((PCW_ENET1_GRP_MDIO_ENABLE) = 1)">false</xilinx:isEnabled>
```

端口清单里也确实有 `ENET1_GMII_TX_EN / TX_ER / TXD[7:0] / COL / CRS / RX_CLK / RX_DV / RX_ER / RXD[7:0]` 与 `ENET1_MDIO_MDC / MDIO_O / MDIO_I / MDIO_T`。

**这条把"要不要写 PL 软 MAC"彻底关掉了**：GEM1 是 PS 硬核，EMIO 只是把它引到 PL 织物里，MAC 本体仍在 PS。

---

## 七、怎么改（Vivado 侧；Procise 不参与）

> 提醒：**Procise 里没有 PS7 IP 本体**。`S:\apps\ic\Procise\data\devicetree_rep\ps7\` 下只有设备树生成模板（`emacps.tcl` 同时处理 `ps7_enet_0`／`ps7_enet_1`，说明厂商工具链本来就预期两路），PS7 配置在 Vivado 工程里。

### 7.1 PS7 参数

```tcl
set_property -dict [list \
  CONFIG.PCW_EN_ENET1                 {1} \
  CONFIG.PCW_ENET1_PERIPHERAL_ENABLE  {1} \
  CONFIG.PCW_ENET1_ENET1_IO           {EMIO} \
  CONFIG.PCW_EN_EMIO_ENET1            {1} \
  CONFIG.PCW_ENET1_GRP_MDIO_ENABLE    {1} \
  CONFIG.PCW_ENET1_GRP_MDIO_IO        {EMIO} \
  CONFIG.PCW_ENET1_PERIPHERAL_FREQMHZ {1000 Mbps} \
] [get_bd_cells processing_system7_0]
```

> **cell 名是 `processing_system7_0`**，不是 IP 实例目录名 `ps_ai_processing_system7_0_0`（后者只是 `.xci` 所在的文件夹名）。按目录名写 `get_bd_cells` 会返回空。

- **不要**开 `PCW_EN_PTP_ENET1`（用不到，会多出一堆 PTP 端口）。
- **不要**设 `PCW_ENET1_RESET_ENABLE`：复位脚 `AA13` 是 PL 引脚，`snps,reset-gpio` 那套机制够不着它，必须自己在 PL 里驱动。

### 7.2 时钟（这里我连改了两次，最终以 2026-10-30 实跑为准）

`GMII_to_RGMII`（PG160 v4.0）的时钟口**取决于 `SupportLevel`**，而且这个区别很要命：

| SupportLevel | 时钟口 | 说明 |
|---|---|---|
| **`Include_Shared_Logic_in_Core`（本次采用）** | **只有一个 `clkin`，要求 200 MHz** | 核内自带 MMCM，**125 / 25 / 2.5 MHz 由核自己产生**；IDELAYCTRL 也在核里 |
| `Include_Shared_Logic_in_Example_Design`（IP 默认值） | `ref_clk_in`(200) + `gmii_clk_125m_in` + `gmii_clk_25m_in` + `gmii_clk_2_5m_in` 四路都要外部给 | 这就是为什么一开始会看到"四路时钟"——那是 example-design 模式的端口 |

**结论：选 `In_Core` 就只需要一路 200 MHz 接 `clkin`，之前担心的 2.5 MHz 问题自然消失**（B 已闭合，A：实跑 `validate_bd_design` rc=0）。

> **这颗定制 PS7 IP 只暴露 `FCLK_CLK0`（A，实测）**：`get_bd_pins -of_objects processing_system7_0` 里只有 `FCLK_CLK0` 与 `FCLK_RESET0_N`，**`FCLK_CLK1/2/3` 的 pin 根本不存在**——尽管参数里有 `PCW_FPGA1/2_PERIPHERAL_FREQMHZ`。所以：
> - **原先"把 FCLK1 设 200M、FCLK2 设 125M"的安排作废**：参数改了，pin 也不出来，`connect_bd_net` 报 `No pins matched FCLK_CLK1`。
> - 200 MHz 只能**自己用 `clk_wiz` 从 `FCLK_CLK0`（50 MHz）倍频出来**。本次做法：`clk_wiz_eth`（50 MHz in → 200 MHz out）→ `gmii_to_rgmii_0/clkin`。
>
> **`RGMII_TXC_SKEW` 只有 0 和 2 可选（对 7z030）**：IP 的 xgui 对非 7z010/015/020 器件给的范围是 `{0,0,1,2}`，依次是「PHY 加 / PHY 加 / **ODELAY 加（仅 HPIO）** / MMCM 加」。我们 Bank13 是 **HR**，ODELAY 那条路不可用，只剩 **0 = PHY 加**（本次选 0，与 PS 口一致）。

### 7.3 连线（用 IP 实测的端口名）

```
PS7.GMII_ETHERNET_1   →  gmii_to_rgmii_0/GMII            （接口对接口）
PS7.MDIO_ETHERNET_1   →  gmii_to_rgmii_0/MDIO_GEM        （接口对接口）
gmii_to_rgmii_0/MDIO_PHY → PHY 的 MDC/MDIO（AE22/AF22）
gmii_to_rgmii_0/RGMII → make_bd_intf_pins_external → Bank13 的 14 个脚（AD23…AE26）
ref_clk_in       ← **不适用**（`In_Core` 模式下没有这个口）
gmii_clk_125m_in ← **不适用**（同上，核内 MMCM 自己产生）
clkin            ← clk_wiz_eth 的 200 MHz（clk_wiz 由 FCLK_CLK0 50 MHz 倍频）
tx_reset / rx_reset ← 反相的 peripheral_aresetn（IP 的复位是**高有效**）
C_PHYADDR = 8       （默认就是 8，必须≠ PHY 真地址；PS 那颗实测 PHYAD=0，所以 8 安全）
RGMII_TXC_SKEW = 0  （PHY 加 2 ns）
SupportLevel = Include_Shared_Logic_in_Core   （**默认是 ..._in_Example_Design，必须改**）
PL_PHY_RESET (AA13) → 自己驱动，低有效，≥10 ms 后放开
```

### 7.4 设备树

```dts
&gmac1 {
    status = "okay";
    phy-mode = "rgmii";   /* 板上运行中的 DT 就是这个值，别抄 dts 源码的 rgmii-id */
    phy-handle = <&gmii2rgmii>;
    /* 不写 snps,reset-gpio：AA13 是 PL 脚 */
    mdio {
        #address-cells = <1>;
        #size-cells = <0>;
        gmii2rgmii: ethernet-phy@8 {
            compatible = "xlnx,gmii-to-rgmii-1.0";
            reg = <8>;
            phy-handle = <&phy1>;
        };
        phy1: ethernet-phy@0 { reg = <0>; };   /* YT8521 地址以 strapping 为准，可先扫 0..31 */
    };
};
```

> **少了 `xlnx,gmii-to-rgmii-1.0` 这个节点，现象就是"灯亮、零包"**：转换核上电默认按 10 Mbps 出 2.5 MHz 时钟，没人告诉它切到 1000M，PHY 侧链路照样 up。

> **phy-mode 用 `rgmii`，不是 `rgmii-id`（2026-10-30 板端实测更正）**：仓库里 `29_dts_fmqlmp-verify.dts` 的 gmac0 写的是 `rgmii-id`，但**板上跑着的设备树是 `rgmii`**——`/proc/device-tree/amba-apu@0/ethernet@e0047000/phy-mode` 读出来是 `rgmii`，`e0049000` 也是 `rgmii`（A）。源码与出厂 dtb 不是一个版本，**以运行中的为准**。

---

## 八、时序与物理风险清单

| 项 | 判据／做法 | 等级 |
|---|---|---|
| RGMII 约束 | `create_clock` RX_CLK（125 MHz）；TX_CLK 输出配 `set_output_delay`；RXD/RX_CTL 配 `set_input_delay`；不写约束工具就不知道这是 125 MHz DDR | 必须 |
| IDELAYCTRL | 必须有 200 MHz 参考时钟，且要落对时钟区，`RDY` 要拉高 | 必须 |
| 2 ns 延迟只能一处 | PHY 侧（`rgmii-id`）**或** FPGA 侧（ODELAY/MMCM），两边都加或都不加都会挂 | 必须 |
| Bank13 是 HR | 1G = 125 MHz DDR，压在 HR 上限附近；**VCCO 若 3.3 V 基本别指望千兆**，先按 100M 验收 | B（待原理图） |
| 复位 AA13 | 低有效、≥10 ms；浮空时行为不确定 | 必须 |
| 没 MAC 时的现象 | link 灯亮、`ip link` 无 eth1、`dmesg` 无第二条 `fmql-dwmac` | 预期 |

**"是不是网络太快"**：不是。1080p30 的 H.264 码流只有 5–20 Mbps，1G 口跑它连零头都用不到；出问题的是**引脚级 125 MHz DDR 时序**，与负载带宽无关。

---

## 九、需不需要 PHY 手册

**不需要**，至少起步阶段不需要：

- 同型号 PHY 在 PS 口已经跑通，用的是 `Generic PHY` 驱动（A：journal `driver [Generic PHY]`；运行中 DT `phy-mode = "rgmii"`，**不是**源码里的 `rgmii-id`）→ **延迟是 PHY 硬件 strapping 给的，不需要软件写寄存器**。
- 标准 802.3 clause-22 寄存器（BMCR 0x00 / BMSR 0x01 / PHYID 0x02-0x03）通用；**PHY 地址不知道就扫 0–31**。
- 内核里 `CONFIG_MOTORCOMM_PHY` **没开**（A），就算拿到 YT8521 手册要调它的扩展寄存器，也得自己写驱动或改 strapping——不如选"FPGA 侧延迟"绕开。

**真正该向厂商要的是原理图**，它能一次回答三件本地判不了的事：Bank13 的 VCCO、YT8521 的地址 strapping、复位极性。

只有这三种情况才非得手册：① 要在 PHY 侧改 RGMII 内部延迟；② 要改 LED／节能／SerDes 模式（YT8521S 可配 SGMII/1000BASE-X，本板没用）；③ 做 1000BASE-T 通道调试。

---

## 十、判"通了"的分阶段判据

不必等整套：每步都有独立判据。

| 阶段 | 判据 |
|---|---|
| ① 引脚通了（不过 MAC） | 照 [[板载接口与内核改造收纳进dev]] 的思路做一个 RGMII 环回（IDDR/ODDR 直连 TX↔RX），能收到自己发的包／抓到流量 |
| ② MAC 出来了 | `lspci` 无关；`ip link` 出现 eth1；`dmesg` 出现第二条 `fmql-dwmac e0049000.ethernet`；MDIO 能读到 PHY ID |
| ③ 链路起来了 | `ethtool eth1` 显示 `Link detected: yes` 与协商速率；`ip -s link show eth1` 的 RX/TX 计数在动 |
| ④ 真能跑 | `iperf3` 双向；再跑视频流，`SO_BINDTODEVICE` 或策略路由绑到 eth1 |

---

## 十一、副本试验记录（Vivado 实跑）

> **做法**：把厂商工程整份复制到 `workenv/pl_eth/proj_trial/fpai_demo_fpga`（533 MB），在**副本**上改参数、查接口、`validate_bd_design`，**不保存、不综合**，原工程一个字节没动。
> **脚本**：`workenv/pl_eth/trial_enet1.tcl`。

**结果：一次过——`set_property` rc=0、`validate_bd_design` rc=0。**（Vivado v2018.3.1，SW Build 2489853，2019-03-26）

| 项 | 改前 | 改后 |
|---|---|---|
| `PCW_EN_ENET1` | 0 | **1** |
| `PCW_ENET1_PERIPHERAL_ENABLE` | 0 | **1** |
| `PCW_ENET1_ENET1_IO` | `<Select>` | **EMIO** |
| `PCW_EN_EMIO_ENET1` | 0 | **1** |
| `PCW_ENET1_GRP_MDIO_ENABLE` | 0 | **1** |
| `PCW_ENET1_GRP_MDIO_IO` | `<Select>` | **EMIO** |
| `GMII_ETHERNET_1` 接口 | 不存在 | **PRESENT** |
| `MDIO_ETHERNET_1` 接口 | 不存在 | **PRESENT** |

三条副产品：

1. **BD 里的 cell 名是 `processing_system7_0`**，不是 XCI 目录名 `ps_ai_processing_system7_0_0`。脚本第一次按目录名取 cell 返回空，靠 fallback 按 `*processing_system7*` 匹配才找对——所以第七节的 Tcl 用 cell 名写。
2. 打开副本时 Vivado 提示 "Project file moved from 'S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga' since last save"，并报 `WARNING: [IP_Flow 19-1663] Duplicate IP found for 'xilinx.com:ip:processing_system7:5.5'`：**厂商 `PS_AI IP/` 里那份优先于 Vivado 自带的那份**。这正是要的行为，说明带 AI 端口的定制 PS7 IP 生效了。
3. `validate_bd_design` 只报一条 debug 网络的 WARNING（与 ENET1 无关），**没有 ERROR**；ENET1 打开后**不需要额外接 AXI**——GMII／MDIO 是直连信号，不走 AXI。

**这次没做**（本页不声称已完成）：没 `generate_target`、没综合、没出比特流、没上板。

### 11.1 第三、四阶段：把改动落进副本并保存（2026-10-30，A）

> 这一轮**保存进副本了**（`workenv/pl_eth/proj_trial/fpai_demo_fpga`），厂商原件仍没动。脚本：`stage2_fclk_ip.tcl`、`stage3_apply_save.tcl`、`stage4_clkin.tcl`。

| 步 | 结果 |
|---|---|
| 基线留档 | `write_bd_tcl` → `ps_ai_baseline.tcl`；`report_property -all` → `ps7_baseline_params.txt`（全量 PCW 参数快照） |
| PS7 参数 | `ENET1=1`、`ENET1_IO=EMIO`、`EN_EMIO_ENET1=1`、MDIO EMIO、`FREQMHZ=1000 Mbps` — 全部落地 |
| FCLK | `PCW_FPGA1=200`、`PCW_FPGA2=125` 写入成功，**但 FCLK1/2 的 pin 不存在**（见 7.2 的更正），这两条参数实际没有用处 |
| 装核 | `gmii_to_rgmii:4.0` 创建成功，`SupportLevel=Include_Shared_Logic_in_Core`、`RGMII_TXC_SKEW=0`、`C_PHYADDR=8` |
| 接口连线 | `GMII` ↔ `ENET1_GMII`、`MDIO_GEM` ↔ `ENET1_MDIO` **都连上了** |
| 时钟 | `clk_wiz_eth`（FCLK0 50 MHz → 200 MHz）→ `clkin` |
| 复位 | `util_vector_logic` NOT 由 `proc_sys_reset_0/peripheral_aresetn` 反相 → `tx_reset`/`rx_reset` |
| RGMII | `make_bd_intf_pins_external` 引到顶层（引脚约束下一步） |
| 验证 | **`validate_bd_design` rc=0**，BD 已保存 |

**这一轮踩到的三个新坑（都已写进 7.2／十四）**：① 定制 PS7 只有 `FCLK_CLK0`，FCLK1/2/3 的 pin 不存在；② `SupportLevel` 默认是 `In_Example_Design`，那套才要四路外部时钟，选 `In_Core` 后只吃一个 `clkin`（200 MHz），核内 MMCM 自己出 125/25/2.5；③ 打开副本时 Vivado 把 BD **迁移成 XCI 形式**（`Design successfully migrated to use XCI files`），这是副本里的正常迁移。

**仍未做**：XDC 引脚约束、综合、时序报告、比特流、上板。

### 11.2 乙类：PL 口直连 PC 的实测（2026-10-30，A）——**这条链路在动，但 PC 网卡被它打挂；网卡本身无恙，已恢复**

**做法**：用户把 PL 那只 RJ45 直接用网线插到本机 PC 的板载千兆网卡（Realtek PCIe GbE，`VEN_10EC&DEV_8168&REV_15`，驱动 `1168.15.717.2023`），板子 eth0 那根线**没动**。全程只读 PC 侧状态与事件日志。

**A 级事实（PC 侧，`Get-WinEvent` 原文）**：Realtek 驱动 `rt68cx21` 在 61 秒内连续报 **6 次 `Event ID 9`**：

```
20:15:19  Realtek PCIe GbE Family Controller is reset by tx hang.
20:15:34  Realtek PCIe GbE Family Controller is reset by tx hang.
20:15:47  Realtek PCIe GbE Family Controller is reset by tx hang.
20:15:58  Realtek PCIe GbE Family Controller is reset by tx hang.
20:16:09  Realtek PCIe GbE Family Controller is reset by tx hang.
20:16:20  Realtek PCIe GbE Family Controller is reset by tx hang.
```

之后网卡被 Windows 判 **Code 43**（`CM_PROB_FAILED_POST_START`，"Windows has stopped this device because it has reported problems"），`NetEnabled=False`、`NetConnectionStatus=0`、`Speed` 空。

**A 级事实（同一时刻的板子侧，`board_eth0_check.py`）**：`eth0` 仍是 `operstate=up`、`carrier=1`、`100 Mb/s`、`RX 312,652 包 / 0 errors / 0 dropped`、`Up=1 / Down=0`。**说明插 PC 的那根线不是 eth0 那根**——PL 口是独立的一路，插拔不影响 PS 口。

**A 级事实（BD 侧）**：`generate_target all` **rc=0**，`Generation completed for ... gmii_to_rgmii_0 / clk_wiz_eth` 全部完成，wrapper 已重新生成。

**B 级解读（推断，未验证）**：`tx hang` 是 **PC 网卡自己的发送引擎挂死**，不是"PC 收到垃圾帧"。最可能的机理是：

1. PL 侧那颗 YT8521 的复位 `AA13` **现在没有任何逻辑驱动**（现役位流里没这一段），引脚浮空；
2. 如果浮空让它处在**非复位状态**，PHY 会和 PC 侧完成自协商 → PC 看到 link（这也解释了为什么"灯亮"）；
3. 但 FPGA 侧**没有 MAC**，RGMII 的 TXD/TX_CTL/RXC 全是**浮空或常量**，PHY 收到的是无效的 RGMII 波形；
4. PC 侧发出去的包，对端永远不应答（没有 MAC 就没有 ARP/ICMP 响应），驱动的 TX 队列等不到完成 → 反复 reset → 最终 Code 43。

**这条证据的价值**：它把"PL 口完全没反应"排除掉了——**PHY 是活的，链路层物理信号在动**，只是缺 MAC。这与第三节的判断一致。

**这条证据不能证明的**：PHY 到底跑了什么速率（PC 侧 `LinkSpeed` 报 1 Gbps 是网卡自身能力值，`MediaConnectionState` 是 `Unknown`，不能当协商结果）；也不能证明 RGMII 12 根线的电气是对的（PC 网卡挂死反而说明信号可能不干净）。

**副作用与善后（A，完整过程见 11.2.1）**：网卡先进 **Code 43**，提权「禁用→启用」后变成 **Code 22（已禁用）**，**最终在拔掉网线后自己恢复成 `Status=OK`、`ErrCode=0`**。恢复过程的失败项也照实记在 11.2.1，包括非提权下三条命令全部 `Access is denied`（`IsAdmin=False`，用户 `TKMNOPC\takomi`）、提权后 `Enable` 报成功但状态未变、以及我脚本取空 `InstanceId` 导致的 `Enable-PnpDevice` 参数错误。

> **下次做这个测试要注意**：插 PC 前先确认 PL 侧的 `AA13` 已被某段逻辑拉到"非复位"，或者干脆先在 FPGA 侧把 RGMII 输出钳到固定电平、不要让管脚浮空——否则可能再把 PC 网卡打挂一次。**更省的顺序**：先用交换机替代 PC 做首次联通性检查（交换机端口被打挂的代价远小于 PC 网卡驱动）。

### 11.2.1 副作用全程与最终结果（A，2026-10-30 22:36 收尾时实测）

网卡**从 Code 43 一路恢复到完全正常**，全过程分三段，每段都有三元交叉验证：

| 时刻 | 状态 | 三元验证 |
|---|---|---|
| 20:16 起（插线期间） | **Code 43**（`CM_PROB_FAILED_POST_START`） | PnP `Status=Error`；CIM `ErrCode=43`、`NetEnabled=False`；`Get-NetAdapter` Status 空 |
| 22:25 左右（第一次提权「禁用→启用」后） | **Code 22**（`CM_PROB_DISABLED`，"This device is disabled"） | PnP `Problem=CM_PROB_DISABLED`；CIM `ErrCode=22`、`NetEnabled=False`；Adapter Status 空 |
| **22:36（拔掉网线后）** | **完全正常** | PnP `Status=OK`、`Problem=CM_PROB_NONE`、"working properly"；CIM **`ErrCode=0`**；`Get-NetAdapter` `Status=Disconnected`、`Admin=Up`、`Link=0 bps` |

**`Disconnected` / `Link=0 bps` 是拔掉网线后的正确状态，不是故障**；同刻 CIM 的 `Speed=9223372036854775807` 是 Windows 无链路时返回的 int64 占位值，**不是错误码**。

**恢复过程的操作记录（含失败项，照实写）**：

1. 非提权先试：`Disable-NetAdapter` → `Access is denied`；`pnputil /restart-device` → `Access is denied`；`Restart-PnpDevice` → **该 cmdlet 在此环境不存在**。根因：`IsAdmin=False`。
2. 改用 UAC 提权（`Start-Process -Verb RunAs`）：`IsAdmin=True` 后 `Disable` **成功**、`Enable` **报成功但状态未变**（停在 Code 22）。
3. 提权下 `pnputil /restart-device` → "Device restarted successfully"，设备**仍停在 Code 22**。
4. 再试 `Enable-PnpDevice`，**脚本取了空 `InstanceId` 导致参数为 null 而失败**——我的脚本缺陷，不是权限问题。
5. **最终恢复：用户拔掉网线并手动启用（或 Windows 自行重试），22:36 实测 `Status=OK`、`ErrCode=0`。**

**结论**：**那块 Realtek 网卡本身没有坏**。它只是被"PL 口无 MAC 却仍在驱动 RGMII 线条"的状态拖进了错误态；网线一拔、设备一重置就回来了。这同时反证了 **PHY 是活的**。

**三步取数命令**（下次复核用）：

```powershell
# 1) PnP 设备状态与错误码
Get-PnpDevice -Class Net | Where-Object { $_.FriendlyName -match 'Realtek' } |
    Select-Object Status, Problem, ProblemDescription

# 2) CIM 的 ConfigManagerErrorCode（0=正常 22=禁用 43=驱动报错）
Get-CimInstance Win32_NetworkAdapter -Filter "DeviceID='1'" |
    Select-Object NetEnabled, NetConnectionStatus, ConfigManagerErrorCode, Speed

# 3) 网卡对外状态（无链路时正确值是 Disconnected / 0 bps）
Get-NetAdapter -Name 'Ethernet' |
    Select-Object Status, AdminStatus, MediaConnectionState, LinkSpeed
```

---

## 十二、下一步（还没做，按这个顺序）

> 这一节是**待办清单**，不是已完成记录。每一步都给了"做完怎么判"，避免又把"灯亮"当"通了"。

### 12.0 现在就能做、且影响可控的测试（按影响分级）

| 级 | 测什么 | 影响 | 现状 |
|---|---|---|---|
| **甲** 板上只读 | `ip -br link`、`ls /sys/bus/platform/devices \| grep e0049`、`/proc/device-tree/.../status` 与 `phy-mode`、`ethtool eth0`、`ethtool -S eth0`、`ip -s link show eth0`、`dmesg \| grep fmql-dwmac`、Link Up/Down 计数 | **零**（纯读，不写盘、不发包、不重启） | **已跑，结果见 13.6** |
| **乙** 只动那一根网线 | 用 PC 直连 PL 口看 PC 侧是否 link、协商到多少；或插交换机看端口灯；PC 侧抓包（预期零包） | **低**：只影响这条独立链路；**别碰 eth0 那根线**（SSH 命脉）、别给该口配 IP | **已跑，结果见 11.2——PHY 活着、链路在动，但把 PC 的 Realtek 网卡打到 Code 43**；恢复需管理员权限，本次未能自动恢复 |
| **丙** 只在本机副本里 | 基线 dump、改 PS7、加 `GMII_to_RGMII`、连线、`validate`、`generate_target`、写 XDC、`synth`、看时序 | **低**：占本机 CPU／磁盘；不碰板子、不碰厂商原件 | 前 3 步 + `generate_target` **已完成并保存**（validate rc=0、generate rc=0）；**XDC／synth 卡在顶层不含 RGMII 端口**（见 12.1 的 A2／B2） |
| **丁** 现在别做 | 灌新比特流（BOOT.bin／PL_JTAG）、改 dtb、改 J12 跳线、板上编译、`devmem` 读 GEM1 寄存器 | **高**：会重启／打断现役视频链／丢 SSH／挤死内存 | 不做 |

### 12.1 在工程副本上把 PL 侧改完（本地可做，不需上板）

> **⚠ 2026-10-30 夜发现的一个阻断点（A）**：工程的**真正顶层不是 BD wrapper，而是手写的 `rtl/ai7030_edif_top.v`**；它例化 `rtl/ps_ai_peripheral.sv`（1937 行），后者才例化 `ps_ai_wrapper ps_ai_wrapper_u0`（第 1033 行）。而 **`ps_ai_peripheral.sv` 里没有任何 RGMII / MDIO 端口**（`grep -i 'rgmii|mdio|gmii'` 零命中）。
>
> 后果：我在 BD 里 `make_bd_intf_pins_external` 出来的 `RGMII_0` 接口，wrapper 会把它作为端口 `RGMII_0_rd / rx_ctl / rxc / td / tx_ctl / txc`（A：重新生成后的 `ps_ai_wrapper.v` 第 154–159、620–625 行）暴露出来，但 `ps_ai_peripheral.sv` **不接它**，于是：
> - 综合到 `ps_ai_wrapper_u0` 时这些端口会悬空（多数工具只报 warning，但功能上等于没接）；
> - 引脚约束写在顶层 `ai7030_edif_top` 上，而顶层根本没有这些端口 → `get_ports RGMII_0_txc` 等**全部找不到**，XDC 直接失效。
>
> **所以第 4–6 步之前必须先做一个架构决定（二选一）**：
>
> | 选项 | 做法 | 代价 | 保留什么 |
> |---|---|---|---|
> | **A2** | 在 `ps_ai_peripheral.sv` 里加 14 个 RGMII/MDIO 端口，从 `ps_ai_wrapper_u0` 的 `RGMII_0_*` 引出，再在 `ai7030_edif_top.v` 里继续引到芯片引脚 | **改厂商 RTL**（两个文件），要重出整份位流 | 现役全部功能（NPU/SDI/HDMI/DDR） |
> | **B2** | 另起一个最小工程／最小顶层，只放 `ps_ai_wrapper` + `gmii_to_rgmii`，不装 NPU/SDI/HDMI | 新工程，但要重新配 DDR/时钟等 | **只有网口**，不能与现役链同时跑 |
>
> 这一晚**没有选**，等你定。**在选定之前，第 4–6 步都做不了**——这也是这一轮停在 XDC 的根本原因，不是遗漏。
>
> **2026-11-06 已裁（D-1793903698 ＋ D-1793904039）**：走 **A2**、并且 **A2 不成即放弃这只口**——她原话「定a2，a2不成就放弃」；"不成"的判据边界仍是草案、待她认（见前者决定 2）。**B2 不作交付路线、不进产品、不上板，但没有废弃**：同日她把它改判成**只作离线探针**，排在执行序第二步（原话「除了不动位流不重启板子外你随便动：有界 PHY 诊断（一次重启窗口）→ B2 离线探针（不碰板子）→ A2 落到厂商 RTL 出整份位流。要动的时候问我要许可」）。上面这张表自此是历史记录，不再是待选项；**本轮的门禁＝不写位流、不重启板子，要动逐次请示**（步骤①按定义要写候选位流＋重启，故它排在最前却必须最后才拿得到窗口）。
>
> **⚠ 开工前先读这条范围补正（A，2026-11-06 本轮 grep 直读）**：A2 的面比上表写的"在 `ps_ai_peripheral.sv` 里加 14 个端口"宽一层。BD 目前**只**把 `RGMII_0_*` 这 6 组端口（展开 12 线）引到了外部——重新生成的 `ps_ai_wrapper.v` 端口表（154–159 行）里**没有 MDIO／MDC**（`grep -i 'mdio|mdc'` 零命中），也没有 PHY 复位脚的输出端口。所以真正的第一步顺序是：① 在 BD 里把 `gmii_to_rgmii_0/MDIO_PHY`（AE22/AF22）与自驱动的复位（AA13）`make_bd_intf_pins_external`／加外部端口，**重生成 wrapper**——端口名到这一步才定得下来，这正是下面 XDC 骨架那句"MDC/MDIO 两行被注释掉、端口名未知"的成因；② MDIO 是双向线，透传层大概率要 IOBUF 而不是普通 `inout`；③ 才轮到 `ps_ai_peripheral.sv` ＋ `ai7030_edif_top.v` 加端口、引线到芯片引脚。**A2 至今零实测进度**：改 RTL、重出位流、上板三件事一件都没做。
>
> **①②两步的探针读数（A，2026-11-06，`workenv/pl_eth/stage9b_mdio_ext.tcl` → `stage9b.log`）**：只在工程副本 `workenv/pl_eth/proj_trial/` 里做，厂商原件未动；`validate_bd_design` 无输出、`generate_target all` 成功、本次运行 **0 个 ERROR**（2 条 CRITICAL WARNING 是 `gp0/gp1_monitor` 时钟口那条旧账，2026-11-06 只读的 `stage9a.log` 里同样存在 ⇒ 不是这次改动引入的）。补正里的①②就此做完，端口名定下来了：
>
> | BD 外部对象 | 重生成后 `ps_ai_wrapper.v` 里的声明 | 行 |
> |---|---|---|
> | `MDIO_PHY_0`（`make_bd_intf_pins_external` 自动取名，接口 VLNV `mdio_rtl:1.0`、MODE Master） | `output MDIO_PHY_0_mdc;` ＋ **`inout MDIO_PHY_0_mdio_io;`** | 601–602 |
> | PHY 复位（探针档：新建 `phy_rst_const`＝xlconstant 宽 1 值 1 → 新建 BD 输出端口 `phy_reset_n`） | `output [0:0]phy_reset_n;`——**是向量不是标量**，XDC 要写 `get_ports {phy_reset_n[0]}` | 938 |
> | 三态这根线 | wrapper **内部已经替我们摆好了 IOBUF**：`IOBUF MDIO_PHY_0_mdio_iobuf (.I(mdio_o), .IO(mdio_io), .O(mdio_i), .T(mdio_t))` | 1425–1429 |
>
> 三条结论：
>
> 1. **⚠ 但那份自带 IOBUF 的 wrapper 根本不参与编译——A2 的面比"两个文件"宽**。两条独立证据：`.xpr` 的 `sources_1` 文件清单里只有一个 `ps_ai_wrapper`，就是手抄件 `$PPRDIR/rtl/ps_ai_wrapper.sv`（616 行条目），自动生成的 `sources_1/bd/ps_ai/hdl/ps_ai_wrapper.v` **没有登记**（`stage9c.log` 实测：glob `*wrapper*` 只命中手抄件）；那次真跑过的综合日志 `runs/synth_1/runme.log` 里读进去的是 `rtl/ps_ai_wrapper.sv` ＋ BD 结构网表 `sources_1/bd/ps_ai/synth/ps_ai.v`，`bd/ps_ai/hdl` 零命中。⇒ 手抄件是厂商 2020.2 生成后**手改过的一份**（文件头写 `Tool Version: Vivado v.2020.2`，端口表尾多出 `output clk_200mhz`，且把 `ps_ai` 实例化成的 `ps_ai_i` 端口名做了大小写重排，如 `BYolo_GP0_awvalid → BYolo_GP0_AWVALID`），**它里面 `RGMII`／`MDIO`／`phy_reset` 零命中**——10-30 说"顶层不含 RGMII 端口"其实低估了一层：不只是 `ps_ai_peripheral.sv` 没接，**连 BD 与顶层之间这一层手抄 wrapper 也没接**。所以"透传层不用管 IOBUF"那句只在自动件里成立：**在真正编译的这条路上，IOBUF 得我们自己摆**（摆进 `rtl/ps_ai_wrapper.sv`，用它拆出来的 `mdio_i/mdio_o/mdio_t` 三根，见上面 `ps_ai.v` 的 2120–2123 行），或者把 `inout` 一路带到 `ai7030_edif_top` 再摆。**A2 的落笔面由此是四处不是两处**：BD（①②已做）→ `synth/ps_ai.v`（`generate_target` 自动重出）→ `rtl/ps_ai_wrapper.sv`（手抄件加端口＋摆 IOBUF）→ `rtl/ps_ai_peripheral.sv` ＋ `rtl/ai7030_edif_top.v`（透传到引脚）。
> 2. **MDC 在 BD 里被标成 `type=clk`**（`MDIO_PHY_0_mdc`），综合会不会因此报"时钟端口没有 `create_clock`"或把它当时钟传播，**未测**——留给 ③ 之后第一次 `synth_design` 看报告，别现在猜。
> 3. **复位这一档是探针占位，不是硬件裁定**：恒 1＝上电即释放复位，软件再也拉不了这根脚，只剩 MDIO 寄存器 0 的 bit15 做软复位。真交付要不要 EMIO GPIO／`proc_sys_reset` 抽头，仍待她定——`stage9a.log` 实测**本 BD 里没有引出 PS7 的 EMIO GPIO**（`gpio` 零命中），而 AA13 的极性与 Bank12 电平本身也还没证（12.3）。

按顺序，每步都能单独验证：

| 步 | 动作 | 做完怎么判 | 状态（2026-10-30） |
|---|---|---|---|
| 1 | PS7：ENET1+EMIO+MDIO EMIO；时钟改用 `clk_wiz` 从 FCLK0 出 200M（**原来的 FCLK1/2 方案作废，见 7.2**） | ENET1 相关参数=1/EMIO；`clkin` 有 200M 源 | **完成**（FCLK 参数写入但无对应 pin，无实际作用） |
| 2 | 加 `GMII to RGMII`（PG160 v4.0）：`SupportLevel=In_Core`、`C_PHYADDR=8`、`RGMII_TXC_SKEW=0` | `gmii_to_rgmii_0` 在 BD 里，三个参数如上 | **完成** |
| 3 | 连线：`GMII_ETHERNET_1` ↔ `GMII`；`MDIO_ETHERNET_1` ↔ `MDIO_GEM`；`clkin` ← 200M；复位反相 | `validate_bd_design` 无 ERROR | **完成**（rc=0，BD 已保存） |
| 4 | RGMII 打出去：`RGMII` 接口 → 顶层端口；`PL_PHY_RESET(AA13)` 自己驱动 | 顶层有 RGMII 端口；15 个脚能对上 | **BD 侧已完成**（2026-11-06 副本实测：`RGMII_0`＋`MDIO_PHY_0`＋`phy_reset_n` 都在，wrapper 重生成成功，见上面②读数）；**顶层 RTL 仍卡住**（`ps_ai_peripheral.sv` 没接＝A2 的活） |
| 5 | 加 XDC：RGMII 时钟/输入输出延迟、IDELAYCTRL 参考、每脚 `IOSTANDARD`（按 VCCO13） | `report_timing_summary` 里 RGMII 路径有真实 slack | **卡在 4**；约束骨架已写（`workenv/pl_eth/pl_eth_placeholder.xdc`，IOSTANDARD 先按 LVCMOS18 占位） |
| 6 | `generate_target all` + `synth_design`，看资源与 license | 资源落在 125K 逻辑内；PS7 dcp 正常重建 | `generate_target` **已 rc=0**（见 11.2）；`synth` 未起 |

> 这 6 步做完仍**不上板**：先出 `.bit`/`.bin`，再走 12.4 的上板路径。

**这一晚写的 XDC 骨架**（`workenv/pl_eth/pl_eth_placeholder.xdc`）：15 个引脚号已按第二节表填好（`RGMII_0_txc/tx_ctl/td[3:0]`、`RGMII_0_rxc/rx_ctl/rd[3:0]`、`pl_phy_reset`），`IOSTANDARD` **全部按 `LVCMOS18` 占位并标了"VCCO 待确认"**；MDC/MDIO 两行**被注释掉**（当时 BD 里的 `MDIO_PHY` 接口还没引到顶层，端口名未知）；RGMII 的 `set_input_delay`/`set_output_delay` **没写**，等综合后看报告再定。

> **2026-11-06 更新：那两行注释该解开了，但名字分两层别混**。BD 这一层现在定死了：`MDIO_PHY_0_mdc`、`MDIO_PHY_0_mdio_io`、`phy_reset_n[0]`（见 12.1 的②读数表）。XDC 绑的是**工程顶层 `ai7030_edif_top` 的端口名**，那层名字仍由我们在 `ps_ai_peripheral.sv`／`ai7030_edif_top.v` 里选——建议照抄 wrapper 的写法（`MDIO_PHY_0_mdc`／`MDIO_PHY_0_mdio_io`），省得每次都要在两层之间做映射；骨架里那颗复位当时写的是 `pl_phy_reset`，跟 BD 侧的 `phy_reset_n` 不是一个名字，③ 落 RTL 时要挑一个统一掉。**这份 XDC 现在仍然不能用**：顶层没有对应端口，`get_ports` 会全部报错。它只是把"引脚号—信号名"这一层映射先固定下来，省得下次重新对一遍表。

#### 12.1.1 第③步本轮实际做到哪（2026-11-06，副本内，不写位流不上板）

**一、A2 的四处落笔已经在副本里改完，并且过了语法关。** 补丁器＝`workenv/pl_eth/a2_patch_rtl.py`（可重跑，按锚点定位、锚点不是唯一命中就当场中止、改前三份原件已复制到 `workenv/pl_eth/a2_rtl_backup/` 并记 md5），改的是：

| 层 | 文件 | 落点（本轮逐块定位，A） | 内容 |
|---|---|---|---|
| BD→手抄 wrapper | `proj_trial/.../rtl/ps_ai_wrapper.sv` | 端口块 477–487；IOBUF 501–510；`ps_ai_i` 连接 998–1010 | 9 只端口 ＋ 自己摆 `IOBUF MDIO_PHY_0_mdio_iobuf` |
| 外设层 | `rtl/ps_ai_peripheral.sv` | 模块端口 113–123；`ps_ai_wrapper_u0` 连接 1513–1523 | 只透传 `mdio_io` 一根（i/o/t 是 wrapper 内部的事） |
| 工程顶层 | `rtl/ai7030_edif_top.v` | 顶层端口 78–88；`U0_ps_ai_peripheral` 连接 232–242 | 同上，`inout MDIO_PHY_0_mdio_io` |

`xvlog` 逐文件语法关 **RC=0、0 ERROR、0 WARNING**（`workenv/pl_eth/xvlog_a2.log`）。第一版补丁把 BD 层那份 `.mdio_i/.mdio_o/.mdio_t` 连接原样抄到了上两层，`xvlog` 直接报 `undeclared symbol` ⇒ 上两层只能连 `mdio_io` 一根；改法是三份文件按备份还原（md5 复核）后重打，这次干净。厂商原件 `S:/apps/llm/agentwork/fpga-src/fpai_demo_fpga/rtl/ps_ai_wrapper.sv` 仍是 57,282 B／9-11 19:23，一个字节没动。

**二、第一次 `synth_design` 报的 `Synth 8-439 module not found` 与这四处改动无关，根因是这份副本从没综合过改动后的 BD（A）。** 三条直读证据：

1. 报错只落在 `ps_ai_s00_regslice_0`（`stage10_synth.log` 427 行起一路 cascade 到顶层），不是新端口那批网表；
2. 盘上的 OOC 检查点只有 10-29 00:39–00:40 那 7 颗（`ps_ai_proc_sys_reset_0_*`／`ps_ai_processing_system7_0_0`／`ps_ai_util_vector_logic_0_0`／`ps_ai_xbar_0,1,4`），**10-30 新加的 `gmii_to_rgmii_0`／`clk_wiz_eth`／4 颗 regslice／`gmii_rst_inv` 连 run 目录都不存在**，`fpai_demo_vivado.gen/` 整个目录也不存在；
3. 走正规路 `launch_runs synth_1` 之后，Vivado 自己把这 7 个缺失的 OOC run 建了出来并全部跑完（05:01–05:04，每个 `runme.log` 的 `err=0`），顶层 `synth_1` 随后起。⇒ 缺的是产物，不是接线。

顺带钉死两件工具行为，省得下次重新踩：① `.xpr` 现在把这 4 颗 regslice 的综合源记成 `ip/ps_ai_s00_regslice_0_1/synth/ps_ai_s00_regslice_0.v`（带 `_1` 的新目录），而 `ip/ps_ai_s00_regslice_0/` 里只剩 `.xci`＋`.xml`；`reset_target`＋`generate_target` 重跑一遍（`stage11_reset_gen.tcl`）**复现同一套 `_1` 布局**，所以不是脏状态，别指望"再生成一次就回去了"。② 想绕开托管流程、把这些生成源 `add_files` 进 `sources_1` 也不行——`filemgmt 20-1440` 明确说它们"已经作为 sub-design `ps_ai.bd` 的一部分在工程里"（`stage12a.log`）。⇒ **这份工程只能走 `launch_runs`，内存里摊平 `synth_design` 的路子在 BD 有 OOC IP 时不成立。**

**三、路线 A 的连接在 BD 里是通的（A，第一次逐条读 `ps_ai.bd` 的 `interface_nets`）。** 四条：

| interface_net | 两端 |
|---|---|
| `processing_system7_0_GMII_ETHERNET_1` | `processing_system7_0/GMII_ETHERNET_1` ↔ `gmii_to_rgmii_0/GMII` |
| `processing_system7_0_MDIO_ETHERNET_1` | `processing_system7_0/MDIO_ETHERNET_1` ↔ `gmii_to_rgmii_0/MDIO_GEM` |
| `gmii_to_rgmii_0_RGMII` | `RGMII_0`（外部）↔ `gmii_to_rgmii_0/RGMII` |
| `gmii_to_rgmii_0_MDIO_PHY` | `MDIO_PHY_0`（外部，本轮 ①② 才加）↔ `gmii_to_rgmii_0/MDIO_PHY` |

配套参数（同文件直读，A）：PS7 侧 `PCW_ENET1_ENET1_IO=EMIO`、`PCW_EN_EMIO_ENET1=1`、`PCW_ENET1_GRP_MDIO_IO=EMIO`、`PCW_ENET1_PERIPHERAL_FREQMHZ=1000 Mbps`；转换核 `C_PHYADDR=8`、`RGMII_TXC_SKEW=0`、`SupportLevel=Include_Shared_Logic_in_Core`；时钟 `clk_wiz_eth`（`clk_in1`←FCLK_CLK0，`PRIM_IN_FREQ=50.000`→`CLKOUT1=200.000`）喂 `gmii_to_rgmii_0/clkin`；复位 `gmii_rst_inv` 把 `proc_sys_reset_0/peripheral_aresetn` 反相后同时喂 `tx_reset` 与 `rx_reset`，`phy_reset_n` 仍由 `xlconstant=1` 恒置。

> **中途我写错过一句，就地更正**：第一眼看到 `PCW_P2F_ENET1_INTR=0` 时我写成"GEM1 的中断没接到 PS，驱动只剩轮询"。这句不成立——**同一张参数表里 `PCW_P2F_ENET0_INTR` 也是 0**，而现役 eth0（GEM0）正是在这个取值下带中断正常跑的（11.2／13.6 的实测）。⇒ 这一项对 ENET1 不构成障碍，`P2F_*` 管的是往 PL 侧分发中断，不是 GEM→PS GIC 那一条。GEM1 真正要盯的是 DT 里那颗 `e0049000` 节点从 `disabled` 改回来以后中断号与 `phy-handle` 怎么写（12.2）。

> **由此得到一条对步骤①的降格（机制推断，B 级，未上板）**：MDIO 走的是"PS GEM1 自己的 MDIO 经转换核桥到 PHY"，不是自建 MDIO master。所以只要 A2 位流真上板，读 PHY ID 用的是 GEM1 那条 mdio 总线——内核里 `CONFIG_XILINX_GMII2RGMII=y` 就是给这座桥准备的（13.5 表里那行）。**步骤①那个自建管理页＋`read_phy_identifiers_v2.py` 的必要性随之下降**：它服务的是回退位流／B 路候选那一版，不是 A2 这一版。这条只降格、不撤销：桥在位流里到底通不通，还是要等一次上板才说得死。

**四、顶层托管综合跑通了：0 ERROR（A，2026-11-06，`workenv/pl_eth/stage13.log` ＋ 工程内 `fpai_demo_vivado.runs/synth_1/runme.log`）。** 这是 A2 改完 RTL 之后的第一次整板综合，读数：

| 读数 | 值 |
|---|---|
| run 状态 | `synth_design Complete!`、`PROGRESS=100%`、`__synthesis_is_complete__` 在 |
| 消息汇总（`runme.log` 末行直读） | **737 Infos／591 Warnings／5 Critical Warnings／0 Errors** |
| 用时 | 2 分 53 秒 |
| 网表 | `runs/synth_1/ai7030_edif_top.dcp`＝2,560,470 B |
| 三态门 | `IOBUF => IOBUF (IBUF, OBUFT): 1 instances`（`stage13.log` 里打开这颗 dcp 时的转换小结） |

⇒ **"BD→手抄 wrapper→外设层→顶层"这条透传链在综合层面是接得住的**：新端口没有悬空、IOBUF 没被判成非法结构、BD 那批 OOC IP 也齐了产物。这不等于时序能收敛——实现一次都没跑，而"顶层 XDC 能管到哪一层"的边界写在下面第六节那三条硬结论里。

**五、XDC：从骨架换成实名一份，第一版当场被自己验出 4 条 ERROR，修完两趟复校过（A）。** 正本＝`workenv/pl_eth/pl_eth_routeA.xdc`。15 只 RGMII／MDC／MDIO＋AA13 全按解出来的顶层端口名写死（`RGMII_0_txc/tx_ctl/td[3:0]/rxc/rx_ctl/rd[3:0]`、`MDIO_PHY_0_mdc`、`MDIO_PHY_0_mdio_io`、`{phy_reset_n[0]}`），`pl_eth_placeholder.xdc` 里被注释掉的 MDC/MDIO 两行已经解开变成真约束。

> **我上一轮写在这段的两句都得改口，而且是被工具当场打回来的那种改口（A，`stage14.log` 81–94 行）**：
> ① 我原话是"顶层不能 `create_clock`，只能用 `get_clocks -of_objects [get_ports RGMII_0_txc]` 引 IP 传播出来的时钟"。**这句照写出来的结果不是"将来可能解析不到"，是立刻 4 条 `ERROR: [Vivado 12-4739] set_output_delay: No valid object(s) found for '-clock …'`**（XDC 第 90–93 行各一条），外加第 88 行那条 `WARNING: [Vivado 12-1008] No clocks found` 和 `INFO: [Designutils 20-663] Invalid constraints found`。根因在第六节：综合后的网表里转换核整颗是**没连进来的 OOC 黑盒**，顶层这一刻根本没有发送时钟对象可引。
> ② 我还写过"那份生成文件管的是核自己边界上的端口，顶层焊盘这层管不到，所以这里要再写一遍"——**"再写一遍"我上一版只搬了 4 行 delay，这是搬错了**：那 −1.5／−2.8 是相对**虚拟时钟**沿量的（生成文件第 7 行 `create_clock -name …rgmii_rx_clk -period 8` 没有 sources），不是相对 rxc 焊盘沿；只搬 delay 不搬配套的假路径与零周期，等于把 PHY 内部那约 2 ns 移位算两遍。现在按生成文件把 **4 行 input delay ＋ 4 行 false_path ＋ 2 行 multicycle** 整套搬齐。

修完的写法与两趟复校（`stage16_xdc_recheck.tcl`／`stage17_roundtrip.tcl`，都是"读 dcp＋`read_xdc`＋`write_xdc` 反写"，不跑实现）：

| 趟 | 前置 | 期望 | 实测 |
|---|---|---|---|
| 1 裸网表 | 什么都不预置（＝此刻真实处境） | 发送侧取不到钟 ⇒ 走 WARN 分支、**0 ERROR** | `ERROR` 行 0 条；时钟 3 颗＝`rgmii_rxc`／`rgmii_rx_vclk`／`mdio_mdc`；WARN 两行按预期打印 |
| 2 预置一颗 `standin_tx_clk` 在 `RGMII_0_txc` 上（模拟实现连进 OOC 黑盒后 IP scoped 约束传播出来的样子） | 发送侧 4 条 delay 应当落上 | `ERROR` 0 条；`INFO … 发送时钟取到 = standin_tx_clk`；时钟 4 颗 | 反写文件里**逐条数到**：`set_output_delay` 6 行（＝发送 4 ＋ MDIO 2）、其中引用 `RGMII_0_td/tx_ctl` 的 4 行；`set_input_delay` 6 行（＝接收 4 ＋ MDIO 2）；`set_false_path` 5 行（＝接收 4 ＋ 复位 1）；`set_multicycle_path` 2 行；`PACKAGE_PIN` 15 行、`IOSTANDARD LVCMOS18` 15 行 |

发送侧因此改成"**取到就加，取不到就明确报 WARN**"，不再有 `set_output_delay -clock <空>` 这种静默不约束的写法。MDC 那节同样加了"已有钟就复用"的判断。

**六、综合后网表的对象读数（A，`stage15_txclk_probe.tcl`／`stage15.log`）——这一节是上面那条"边界"的根据。**

| 查的东西 | 实测 |
|---|---|
| 顶层这几只脚的 `DIRECTION` | `RGMII_0_txc`=OUT、`RGMII_0_rxc`=IN、`MDIO_PHY_0_mdc`=OUT、`MDIO_PHY_0_mdio_io`=**INOUT**、`phy_reset_n[0]`=OUT |
| 自己摆的那颗 IOBUF 在网表里的路径 | `U0_ps_ai_peripheral/ps_ai_wrapper_u0/MDIO_PHY_0_mdio_iobuf`（`REF=IOBUF`，全设计 1 颗） |
| 转换核在网表里的样子 | 只有 1 个 cell：`U0_ps_ai_peripheral/ps_ai_wrapper_u0/ps_ai_i/gmii_to_rgmii_0`，`REF=ps_ai_gmii_to_rgmii_0_0`，**黑盒** |
| 生成文件第 27 行那个 `-source` 脚 | `*rgmii_txc_out*` 匹配 **0 个 cell／0 个 pin** ⇒ 顶层 XDC 抄不了这行，也就造不出这颗 generated clock |
| 这颗 dcp 里有多少 IP 是黑盒 | `open_checkpoint` 打 **27 条** `CRITICAL WARNING: [Project 1-486] Could not resolve non-primitive black box cell`（`stage16.log` 内两趟 ⇒ 全文 54 条命中）——**含 `ps_ai_processing_system7_0_0` 本身** |

⇒ 三条硬结论：① 顶层 XDC **永远不能**引用 IP 内部对象名（`rgmii_txc_out`、`i_bufgmux_gmii_clk`、`gmii_clk_125m*` 之类），这类约束的归宿是 IP 自己那份 scoped `clocks.xdc`，由工具在实现连接黑盒时应用；② 顶层只管三样——引脚、`rxc` 这颗输入钟（IP 文件里只引用不创建，创建是顶层的责任）、以及以钟为基准的 in/out delay；③ **"这份 XDC 会不会与 IP scoped 约束重复"这个问题，在综合后网表上无法判定**，只能等一次实现后的 `report_exceptions`／时序报告（未测，别当成已解决）。

IP 安装树里的 `.ttcl` 约束模板全部是加密件（`XlxV50EB` 头，`xdc.ttcl`／`xdc_clock.ttcl`／`xdc_block.ttcl`／`gmii_to_rgmii_ooc_xdc.ttcl` 都打不开），所以本机唯一能读的数值正本就是 `ip/ps_ai_gmii_to_rgmii_0_0/synth/ps_ai_gmii_to_rgmii_0_0_clocks.xdc` 那份生成文件；−1.5／−2.8、−1.0／−2.6、虚拟钟 8 ns 全部来自它（A 级＝文件直读）。`IOSTANDARD` 仍全按 LVCMOS18 占位、Bank12/13 的 VCCO 仍是 C 级待查（12.3）；MDC 的 400 ns 与 MDIO 的 ±10 ns 来自 IEEE 802.3（B 级，这颗 GEM 实际分频由板端驱动写寄存器决定）。

**七、本轮（2026-11-06）跑过的脚本，全在 `workenv/pl_eth/`，都不写位流、不碰板子。**

| 脚本 | 干什么 ／ 读数在哪 |
|---|---|
| `a2_patch_rtl.py` | 三层 RTL 透传补丁（可重跑，锚点不唯一即中止）；改前原件 md5 记在 `a2_rtl_md5_before_stage11.txt` |
| `xvlog_a2.log` | 逐文件语法关：RC=0／0 ERROR／0 WARNING |
| `stage10_a2_synth.tcl`→`stage10_synth.log` | 内存里摊平 `synth_design` ⇒ 撞 `Synth 8-439`，**这条路本工程设计不成立** |
| `stage11_reset_gen.tcl`→`stage11.log` | `reset_target`＋`generate_target all`：复现同一套 `_1` 目录布局 ⇒ 不是脏状态 |
| `stage12a_addfiles_probe.tcl`→`stage12a.log` | 试 `add_files` 把 BD 生成源挂进 `sources_1` ⇒ `filemgmt 20-1440` 拒绝 |
| `stage13_launch_synth.tcl`→`stage13.log` | 正规 `launch_runs synth_1`：自动补建 7 个缺失 OOC run 并跑完，顶层综合 **0 Errors** |
| `stage14_xdc_check.tcl`→`stage14.log` | 第一版 XDC 复校 ⇒ 抓出 4 条 `Vivado 12-4739` |
| `stage15_txclk_probe.tcl`→`stage15.log` | 网表对象读数（第六节那张表） |
| `stage16_xdc_recheck.tcl`→`stage16.log`、`stage17_roundtrip.tcl`→`stage17.log`＋`a2_xdc_rt_pass2.xdc` | 修完的 XDC 两趟复校＋约束反写逐条计数 |

### 12.2 设备树：写成可直接贴的片段


第七节给了结构，落地成一份 `.dtsi` 时要补三处：

1. **先确认厂商 dts 里有没有 `gmac1` 标签**。我读到的 `29_dts_fmqlmp-verify.dts` 只有 `gmac0`，但随镜像的 dtb 里有 `ethernet@e0049000` 节点——两边版本不一致，缺标签就按节点路径补。
2. `phy1` 的 `reg`（PHY 地址）**先扫 0–31 再填**：有 MAC 之后 `mdio-tool`／`ethtool -m`／直接读 `/sys/class/mdio_bus/*/` 都能扫。
3. `phy-mode = "rgmii"`（**运行中的 DT 就是这个值**，见 7.4 的实测更正），与 PS 口保持一致，**别在 FPGA 侧再加 2 ns**。

### 12.3 三件只有原理图能定的事（不解决则 1G 结果不可信）

| 项 | 为什么卡住 | 不解决的后果 |
|---|---|---|
| **Bank13 的 VCCO** | 决定 `IOSTANDARD` 和"1G 能不能稳"；Bank13 是 HR 银行，1G=125 MHz DDR 本就压在上限附近 | 写成错的电平 → 要么 DRC 报错，要么跑起来偶发错包；3.3 V 时可能只能跑 100M |
| **YT8521 的 PHY 地址 strapping** | 决定 DT 里 `reg` 和转换核虚拟地址（核必须≠真地址） | 地址撞了 → MDIO 读到的是核自己，`dmesg` 里 PHY ID 不对 |
| **`PL_PHY_RESET(AA13)` 的极性/时序** | 手册只给引脚号，没给有效电平与最小脉宽 | 拉反 → PHY 一直复位，灯都不亮；脉宽不够 → 偶发不识别 |

**顺带**：手册里 PS 那颗 PHY 的复位是 `W14`（写作 `IO_0_12`，也是 PL 引脚），说明厂商位流里有这一段胶合逻辑——可以参照它的写法给 `AA13` 用。

### 12.4 上板路径

受 [[PL位流重载通道失效]] 约束，自研位流目前只有两条没被否掉的路：**`BOOT.bin` 替换**（现役带状态导出的位流就是这么装上去的，见 [[BOOTbin位流替换手术]]）与 **PL_JTAG 直灌**。`uEnv.txt` 里的 `loadbit` 那条是空转的，别指望。

上板后按第十节四阶段判据推进；`iperf3` 通了再谈挂视频流（`SO_BINDTODEVICE` 或策略路由绑定 eth1）。

---

## 十三、本轮复现与环境记录

> 为了"下次不用重新发现一遍"，把这一轮用到的路径、脚本、版本、以及环境的意外变动都记在这里。

### 13.1 本轮实际跑过的脚本（都在 `workenv/pl_eth/`）

| 脚本 | 干什么 |
|---|---|
| `pinbank.tcl` | 对 `xc7z030ffg676-2` 查第二节那 15 个脚的 `PIN_FUNC`／bank |
| `lnk.ps1` | 解析 `C:\Users\Public\Desktop\Procise.lnk` → `S:\apps\ic\Procise\procise_launch.exe` |
| `find_ps7.ps1` | 在 Procise 里找 PS7 相关文件与 `PCW_ENET` 命中（结论：只有 devicetree 模板，无 PS7 IP 本体） |
| `find_ip.ps1` | 在 `S:\apps\llm\agentwork` 等根下定位厂商工程的 `.bd`／`.xci`／`component.xml` |
| `copyproj.ps1` | 把厂商工程复制到副本（`robocopy` 在当前环境不可用，最终用 `cp -r`） |
| `trial_enet1.tcl` | 第十一节的副本试验：改 ENET1 参数 → 查接口 → `validate` → **不保存退出** |
| `board_probe.py` | 甲类板端只读探测（paramiko，只跑读命令），输出落 `board_probe_<时间戳>.txt` |
| `stage2_fclk_ip.tcl` | 丙类：基线留档 → 改 FCLK1/2 → 加 `GMII_to_RGMII` → 打印 IP 参数与端口 |
| `stage3_apply_save.tcl` | 丙类：PS7+EMIO、装核并配置、连 GMII/MDIO、接复位、RGMII 引顶层、validate、保存 |
| `stage4_clkin.tcl` | 丙类：补 `clk_wiz_eth`（50M→200M）→ `clkin`，validate rc=0、保存 |
| `stage5_ports.tcl` / `stage6_rgmii_pins.tcl` | 查 BD 顶层端口与 RGMII 接口内部引脚（结论：接口级查询拿不到，改用 `write_bd_tcl`） |
| `stage7_wbd.tcl` | `write_bd_tcl` 导出当前 BD（`bd_current.tcl`），这是查端口名最可靠的一手 |
| `stage8_gen.tcl` | `generate_target all`（**rc=0**），并查重新生成后的 wrapper 端口 |
| `board_eth0_check.py` | 插 PC 那轮同时确认板子 eth0 仍正常（区分"插的是哪根线"） |
| `pc_nic*.ps1`（1–7） | PC 侧网卡状态与事件日志取证：`Get-NetAdapter` / `Get-PnpDevice` / `Get-WinEvent rt68cx21` |
| `nic_recover.ps1` / `nic_recover2.ps1` | 尝试恢复 Code 43 网卡（非提权，全部 `Access is denied`） |
| `nic_elevated.ps1` | UAC 提权版「禁用→启用」：`IsAdmin=True`、`Disable` 成功、`Enable` 报成功但状态停在 Code 22 |
| `nic_fix2.ps1` / `nic_fix3.ps1` / `nic_enable.ps1` | 提权下试 `pnputil /restart-device` 与 `Enable-PnpDevice`（前者报 "restarted successfully" 但仍是 Code 22；后两者因取空 `InstanceId` 而失败） |
| `pl_eth_placeholder.xdc` | 15 脚引脚约束骨架，`IOSTANDARD` 按 LVCMOS18 占位、MDIO 两行注释掉、无 input/output delay |

> **网卡恢复的最终结论写在 11.2.1**：工具链上的三条路（`Disable-NetAdapter`、`pnputil /restart-device`、`Enable-PnpDevice`）就本机环境而言**都没能一次修好**；实际生效的是**拔掉网线 + 手动启用 / Windows 自行重试**。`Restart-PnpDevice` 这个 cmdlet 在本机**不存在**。

复跑命令：

```bash
cd /s/work/WCIS/workenv/pl_eth
"/s/apps/Xilinx/Vivado/2018.3/bin/vivado.bat" -mode batch -nojournal -nolog -notrace \
  -source "S:/work/WCIS/workenv/pl_eth/trial_enet1.tcl"
```

### 13.2 路径清单（都是绝对路径，别按相对名猜）

| 东西 | 路径 |
|---|---|
| Vivado | `S:\apps\Xilinx\Vivado\2018.3\bin\vivado.bat`（v2018.3.1） |
| 厂商工程（**原件，勿改**） | `S:\apps\llm\agentwork\fpga-src\fpai_demo_fpga\`（`fpai_demo_vivado.xpr`，0.52 GB / 1366 文件） |
| 工程副本（试验用） | `S:\work\WCIS\workenv\pl_eth\proj_trial\fpai_demo_fpga\`（533 MB） |
| PS7 IP（定制，带 AI 端口） | `…\PS_AI IP\processing_system7_v5_5\`（`component.xml` 1.68 MB） |
| PS7 实例配置 | `…\fpai_demo_vivado.srcs\sources_1\bd\ps_ai\ip\ps_ai_processing_system7_0_0\ps_ai_processing_system7_0_0.xci` |
| BD | `…\sources_1\bd\ps_ai\ps_ai.bd`（含 `processing_system7_0` 这个 cell） |
| **工程真正顶层（改 RGMII 透传要动它）** | `…\rtl\ai7030_edif_top.v`（284 行，`TopModule` 就是它） |
| **顶层下一级（不含 RGMII 端口的那层）** | `…\rtl\ps_ai_peripheral.sv`（1937 行，第 1033 行例化 `ps_ai_wrapper`） |
| BD wrapper（有 `RGMII_0_*` 端口） | `…\fpai_demo_vivado.srcs\sources_1\bd\ps_ai\hdl\ps_ai_wrapper.v`（1856 行，`RGMII_0_*` 在 154–159 / 620–625 行） |
| Procise | `S:\apps\ic\Procise\`（PS7 只有 devicetree 模板：`data\devicetree_rep\ps7\emacps\data\emacps.tcl`） |

> 同一份厂商工程在 `S:\apps\llm\agentwork\fpga-src\npu_merge_1014\` 与 `…\_tmp_repo_probe\Icraft-ModelZoo-yolov5\` 下还有两份同尺寸副本，改之前先确认改的是哪一份。

### 13.3 环境上的一次意外与修复（2026-10-29）

**现象**：命令行（bash／PowerShell）在 `S:\work\WCIS\workenv` 下**任何建目录／写入都被拒**（`mkdir: Permission denied`、`New-Item: Access to the path 'proj_trial' is denied`），而 DSH 的文件工具能写。根因是 `workenv` 目录缺少当前用户的 `WRITE_OWNER`（`writeDac=true / writeOwner=false`）。

**处置**：用 DSH 自带的诊断修复脚本（`diagnose-windows-sandbox-acl.ps1`）只加了一条"当前用户完全控制"的权限项，**未改文件内容、未改所有者**，复验 `writeOwner=true` 通过；`workenv` 子树扫描 830 个对象，无外来应用包权限项需要清理。

- 报告：`C:\Users\takomi\dsh-acl-out\acl-report-42b28579bef74f7f9b690b142be65947.jsonl`
- 回滚：`pwsh -NoProfile -File 'C:\Users\takomi\dsh-acl-out\acl-backup-ef67dea319f54df9bad762c196413ecc.json.ps1' -Path 'S:\work\WCIS\workenv' -AllowRoot 'S:\work\WCIS' -Restore 'C:\Users\takomi\dsh-acl-out\acl-backup-ef67dea319f54df9bad762c196413ecc.json'`

### 13.4 临时产物（未删）

- `workenv\pl_eth\proj_trial\fpai_demo_fpga\` — 533 MB 工程副本。**已经带着 PL 网口的改动保存过**（PS7 ENET1+EMIO、`gmii_to_rgmii_0`、`clk_wiz_eth`、RGMII 顶层端口）；删了这些改动就没了，要重跑 `stage3`／`stage4`。
- `workenv\pl_eth\ps_ai_baseline.tcl`、`ps7_baseline_params.txt` — 改动前的 BD 与 PS7 全参数基线，回退时用得上。
- `workenv\pl_eth\*.tcl`、`*.ps1`、`board_probe_*.txt` — 脚本与板端探测原始输出，可重跑。

### 13.5 证据索引（每条结论对应哪个文件）

| 结论 | 证据 |
|---|---|
| 两片 YT8521，一片接 PL | 完整版手册 §4.8，`wiki/PS/board_extract/41_manual_full_extracted.txt` 第 195–235 行 |
| PL 口 15 个引脚号 | 同上第 219–235 行 |
| 15 个脚的 bank | Vivado `get_package_pins` 实查（第 2 节表） |
| ENET1 当前全关 | `ps_ai_processing_system7_0_0.xci` 的 `PARAM_VALUE.PCW_ENET1_*` / `PCW_EN_EMIO_ENET1` / `PCW_EN_ENET1` |
| MIO0–15 被占满 | 同 XCI 的 `PARAM_VALUE.PCW_MIO_TREE_PERIPHERALS` |
| IP 支持 ENET1+EMIO | `PS_AI IP\processing_system7_v5_5\component.xml` 的 `BUSIF_ENABLEMENT.GMII_ETHERNET_1` / `MDIO_ETHERNET_1` 与 `ENET1_GMII_*` 端口定义 |
| 改参数可行 | 第十一节：副本上 `set_property` rc=0、`validate_bd_design` rc=0 |
| 内核侧驱动齐 | `34_kernel_config_from_Image.txt` 的 `CONFIG_DWMAC_FMQL` / `CONFIG_XILINX_GMII2RGMII`（=y）与 `CONFIG_XILINX_AXI_EMAC` / `CONFIG_MOTORCOMM_PHY`（not set） |
| 运行中的 DT：gmac0 = okay / `rgmii`，gmac1 = disabled / `rgmii` | `29` 号 dts **源码**写的是 `rgmii-id`，但板上 `/proc/device-tree/amba-apu@0/ethernet@e0047000/phy-mode` 读出 `rgmii`（A，2026-10-30 实测）——源码与出厂 dtb 版本不一致，以运行为准 |
| eth0 只跑 100M 的原因 | `ethtool eth0` 的 `Link partner advertised link modes` 只有 10/100，**没有 1000baseT**（A，2026-10-30）：对端（路由器 192.168.1.1）只广播百兆，板子这边是支持并广播 1000baseT 的 |
| 四路 FCLK 参数都在，但**只有 FCLK_CLK0 这个 pin 存在** | 实测 `get_bd_pins -of_objects processing_system7_0` 只列出 `FCLK_CLK0` / `FCLK_RESET0_N`（A，2026-10-30）；`connect_bd_net ... FCLK_CLK1` 报 `No pins matched` |
| 时钟方案：`In_Core` 只需 `clkin`(200 MHz) | IP `component.xml` 的四个时钟口只在 example-design 模式下出现；实跑 `validate_bd_design` rc=0 证明 `clkin` 一路够用 |
| 改完并保存后 BD 通过验证 | `stage3_apply_save.tcl` + `stage4_clkin.tcl`：`validate_bd_design` rc=0、`BD SAVED`（A，2026-10-30） |
| `generate_target all` 可用 | `stage8_gen.tcl`：**rc=0**，`Generation completed for gmii_to_rgmii_0 / clk_wiz_eth`，wrapper 已重生成（A，2026-10-30） |
| **工程顶层不含 RGMII 端口 → XDC 无处落** | 顶层 `ai7030_edif_top`（`ai7030_edif_top.v`）→ `ps_ai_peripheral.sv`（1937 行，`grep -i 'rgmii\|mdio\|gmii'` **零命中**）→ 第 1033 行才例化 `ps_ai_wrapper`；重新生成的 `ps_ai_wrapper.v` 有 `RGMII_0_rd/rx_ctl/rxc/td/tx_ctl/txc`（第 154–159、620–625 行）但上层没接（A，2026-10-30）。**2026-11-06 补一层（A）**：那句"重新生成的 `ps_ai_wrapper.v`"是自动件，而它**不参与编译**——工程实际用的是厂商手抄件 `rtl/ps_ai_wrapper.sv`（`.xpr` 第 616 行唯一登记、`runs/synth_1/runme.log` 实测读它＋`bd/ps_ai/synth/ps_ai.v`，`bd/ps_ai/hdl` 零命中），手抄件里 RGMII/MDIO/复位同样零命中 ⇒ 透传要穿过**三层** RTL，见 12.1②读数表结论 1 |
| PL 口确实能拉 link（PHY 活着） | PC 侧 `rt68cx21` 6 次 `tx hang` + 最终 Code 43；同刻板子 eth0 仍 100M/0 错误（A，2026-10-30，见 11.2） |
| PC 网卡本身没坏（错误态可自愈） | 同一块 Realtek：Code 43 →（提权禁/启）→ Code 22 →（拔线+手动启用）→ `Status=OK / ErrCode=0 / Disconnected`（A，2026-10-30 22:36 实测，见 11.2.1） |
| SP 口与 PL 口是两根独立的线 | 插 PC 期间 eth0 `operstate=up`、`RX 312,652 包 / 0 errors`、`Up=1/Down=0`（A，2026-10-30） |
| A2 三层 RTL 透传改完且过语法关 | `workenv/pl_eth/a2_patch_rtl.py`＋`xvlog_a2.log`（RC=0／0 ERROR／0 WARNING），行号表在 12.1.1 一（A，2026-11-06） |
| **第一次整板综合 0 Errors** | `workenv/pl_eth/stage13.log` ＋ 工程内 `fpai_demo_vivado.runs/synth_1/runme.log`（737/591/5/**0**，2:53，dcp 2,560,470 B）；`stage10_synth.log` 那条 `Synth 8-439` 走的是内存里摊平的死路（A，2026-11-06） |
| 顶层多出 15 只端口对象、方向与 IOBUF 都在 | `workenv/pl_eth/stage15.log`：`DIRECTION` 逐项、`U0_ps_ai_peripheral/ps_ai_wrapper_u0/MDIO_PHY_0_mdio_iobuf` 1 颗（A，2026-11-06） |
| **顶层 XDC 不能引用 IP 内部对象名** | `stage15.log`：`*rgmii_txc_out*` 匹配 0 cell／0 pin；`stage16.log`：`open_checkpoint` 打 27 条 `Project 1-486` 黑盒（含 `ps_ai_processing_system7_0_0` 本身）⇒ 第一版 XDC 因此炸 4 条 `Vivado 12-4739`（`stage14.log` 81–94 行）（A，2026-11-06） |
| 修完的 XDC 两趟复校 0 ERROR、delay 逐条数到 | `stage16_xdc_recheck.tcl`／`stage17_roundtrip.tcl` ＋ `a2_xdc_rt_pass2.xdc`（15/15/6/6/5/2/4/4/4，算式与期望值在 12.1.1 五）（A，2026-11-06） |
| 自研位流上板受限 | [[PL位流重载通道失效]]、[[BOOTbin位流替换手术]] |

### 13.6 甲类板端只读探测结果（2026-10-30，A）

脚本 `board_probe.py`，原始输出 `workenv/pl_eth/board_probe_20261030_195736.txt`。当时 PL 口**用网线连着路由器 `192.168.1.1`**（用户告知）。

| 读数 | 值 | 说明 |
|---|---|---|
| 网口数 | `lo / can0 / eth0 / sit0`，**没有 eth1** | GEM1 没 probe（DT 里 disabled） |
| `e0049000` platform 设备 | **不存在** | 因为 DT `status="disabled"`，内核根本没为它建 platform device |
| DT 里的 ethernet 节点 | `e0047000` = okay / `rgmii`；`e0049000` = disabled / `rgmii` | **两路都在 DT 里**，只是第二路关着 |
| eth0 速率 | **100 Mb/s / Full**，`carrier=1`，`operstate=up` | 现役链路正常 |
| link partner 广播 | 10baseT/Half·Full、100baseT/Half·Full，**无 1000baseT** | **100M 是对端（路由器）决定的，不是板子** |
| eth0 收发计数 | RX 242,127 包 / 264 MB，TX 228,200 包 / 152 MB，**errors 0、dropped 0、overrun 0** | 这条链路健康 |
| 本次开机 Link Up/Down | **Up=1，Down=0** | 没有反复掉线（历史 archive 里那 42 次 Up 是 97 次启动累计） |
| `fmql-dwmac` 驱动 | 已注册，`PHY [stmmac-0:00] driver [Generic PHY]`，`PHYAD: 0` | 与第三节的推断一致 |

**这次探测确定的**：① 板上只有 eth0 一个网络接口；② GEM1 的 DT 节点存在但被关；③ eth0 本身健康、100M 是对端限制；④ **PS 那颗 PHY 的地址是 0**（`PHYAD: 0`），所以 PL 那颗转换核的虚拟地址**必须避开 0**（用 8 是安全的）。

**这次探测不能确定的**：PL 那颗 PHY 是否 link up（没有 MAC 就没有 `ethtool` 入口）、它的 MDIO 地址是多少（可能同为 0，要看原理图/上电 strapping）。

### 13.7 本页的提交状态

本页与 [[板载接口与内核改造收纳进dev]]、[[板子（除芯片）]] 三处改动**尚未提交**（wiki 子模块里另有约 149 个改动是别的会话留下的，别用 `git add -A`）。提交时按 `CONTRIBUTING.md`：H1 与文件名一致、LF/UTF-8/无 BOM，`python -X utf8 wiki/format/check-md.py` 对本页应为 0 issue。

### 13.8 本轮结束时留下的状态（2026-10-30 夜，一句话交接）

| 在哪 | 状态 |
|---|---|
| **板子 192.168.1.113** | **没动**：只跑过只读命令；现役视频链未受影响 |
| **PL 口那根线** | 曾插到用户 PC（已拔掉），确认"PHY 活着、链路在动"，但把 PC 的 Realtek 网卡打进错误态 |
| **用户 PC 网卡** | **已恢复**：22:36 实测 `Status=OK`、`ErrCode=0`、`Status=Disconnected`（拔线后的正确态）。全程 Code 43 → Code 22 → 正常，见 11.2.1 |
| **厂商原件** `S:\apps\llm\agentwork\fpga-src\fpai_demo_fpga` | **一个字节没动** |
| **工程副本** `workenv\pl_eth\proj_trial\fpai_demo_fpga` | **已保存改动**：PS7 ENET1+EMIO、`gmii_to_rgmii_0`、`clk_wiz_eth`、`gmii_rst_inv`、RGMII 接口引顶层；`generate_target` 已跑（rc=0） |
| **卡点** | **10-30 那个卡点（"顶层不含 RGMII 端口 → XDC／综合都做不下去"）到 2026-11-06 已在副本里解除**：三层 RTL 透传改完、`launch_runs synth_1` 0 Errors、实名 XDC 两趟复校 0 ERROR（12.1.1 四／五／六）。**换成新的卡点＝没跑过实现**：这份 dcp 里 27 个 IP（含 PS7 本身）全是未连入的 OOC 黑盒，布局布线、时序收敛、`gmii_to_rgmii` 那颗 generated clock 到底能不能传播到顶层端口，全都还没有读数。**选型仍照 2026-11-06 裁定＝只走 A2，B2 只作离线探针**（见 12.1 与 [[plnet]] 三节） |
| **三件只有原理图能定** | Bank13 的 VCCO、YT8521 地址 strapping、AA13 复位极性——**仍全部未知** |
| **2026-11-06 副本新增（①②）** | 工程副本另存了两处：`MDIO_PHY_0` 接口引外部（wrapper 出 `MDIO_PHY_0_mdc`＋`inout MDIO_PHY_0_mdio_io`，IOBUF 由 wrapper 自带）＋ `phy_rst_const`(xlconstant=1) 驱动的输出端口 `phy_reset_n[0]`；`validate` 无输出、`generate_target all` 成功、0 ERROR，见 12.1②读数表。厂商原件仍**一个字节没动** |
| **2026-11-06 副本新增（③）** | 三层 RTL 透传**已在副本里改完并综合过**：`rtl/ps_ai_wrapper.sv`＋`rtl/ps_ai_peripheral.sv`＋`rtl/ai7030_edif_top.v`（行号与内容见 12.1.1 一），`launch_runs synth_1` **0 Errors**、顶层 dcp 已落盘，顶层多出 15 只端口对象、自摆的 IOBUF 在网表里是 1 颗（12.1.1 四／六）。正本 XDC＝`workenv/pl_eth/pl_eth_routeA.xdc`，两趟复校 0 ERROR（12.1.1 五）。**位流一次没出、板子一次没碰** |

选型已裁完（A2 ＋ ①②③ 执行序，见 12.1 与 [[plnet]] 三／八节），本行原话"就是 12.1 里那个 A2／B2 的选择；选完才能继续第 4–6 步"到 2026-11-06 已作废。**第 ③ 步的 RTL 面到 2026-11-06 本轮已做完并核过**（副本内三层透传＋`launch_runs synth_1` 0 Errors＋实名 XDC 两趟复校 0 ERROR，见 12.1.1 四／五／六），原话里"再跑第一次 `synth_design`"这一件已经不再是下一件事。

**现在的下一件事只剩两件，都不在"改 RTL"这一档**：
1. **第一次实现**（`launch_runs impl_1`＋`write_bitstream` 之前的那一段）——本机可跑、不碰板子，但要吃掉几小时 machine 时间，且要先定下面这条；**是否开这一档要她点头**（她的门禁原文＝"除了不动位流不重启板子外你随便动"，实现本身不动位流，但它是通往位流的那一步）。
2. **AA13 复位由谁驱动**（xlconstant 恒 1／`proc_sys_reset` 抽头／EMIO GPIO）——**探针占位不是硬件裁定**，仍未定；它决定要不要再回 BD 改一次，所以排在实现之前更省事。正本在 [[plnet]] 八节待裁清单。

步骤①（板上 PHY 诊断）脚本已就绪，但它按定义要写候选位流＋重启，所以排在最前却要最后才拿得到窗口；而且 12.1.1 三末尾那条降格（B 级）说得更狠：**A2 上板后读 PHY ID 走的是 GEM1 自己的 mdio，那座桥在位流里通不通只能上板判**，所以①那套自建管理页脚本对 A2 只作备用入口。


---

## 十四、坑与禁手

1. **别把"灯亮"当"通"**：link 灯是 PHY 自己的状态，MAC 没起来照样亮。
2. **别在 PL 里重写 MAC**：GEM1 是硬核，写软 MAC 等于把工作量放大一个量级，而且 `axienet` 驱动还没编进内核。
3. **别用 `snps,reset-gpio` 管 AA13**：那是 PS GPIO 机制，够不到 PL 引脚。
4. **别两边都加 2 ns 延迟**：PHY 侧 `rgmii-id` 与 FPGA 侧 odelay 同时存在会破坏采样窗口。
5. **别只开 `PCW_EN_ENET1` 不开 `PCW_EN_EMIO_ENET1`**：两者都要，MDIO 还额外要 `PCW_ENET1_GRP_MDIO_ENABLE=1` + `..._MDIO_IO=EMIO`，否则 MDIO 接口不出现，PHY 照样读不到。
6. **别在开发板上编译**：要改的只有比特流与 dtb，编译在校机，见 [[交叉编译主机路由SOP]]。
7. **位流通道现状**：自研位流上板仍受 [[PL位流重载通道失效]] 约束，可行路径按 [[BOOTbin位流替换手术]]。
8. **别以为 `PCW_FPGA1/2` 参数能换来 FCLK1/2**：这颗定制 PS7 只引出 `FCLK_CLK0`，参数写了也不出 pin（`connect_bd_net` 直接报 `No pins matched FCLK_CLK1`）。200 MHz 用 `clk_wiz` 从 FCLK0 倍频。
9. **别用 IP 默认的 `SupportLevel`**：默认是 `Include_Shared_Logic_in_Example_Design`，那套要外部给 200/125/25/2.5 四路时钟；改成 `Include_Shared_Logic_in_Core` 后只吃一个 `clkin`（200 MHz），25/2.5 由核内 MMCM 产生。
10. **别照 ds 源码抄 `phy-mode`**：源码写 `rgmii-id`，板上运行的是 `rgmii`（A）。以运行中的 `/proc/device-tree` 为准。
11. **别在顶层没有 RGMII 端口时写 `get_ports RGMII_0_*` 的 XDC**：约束会全部找不到对象——这句在 10-30 是实况（顶层那三层 RTL 不含 RGMII 端口）。**2026-11-06 副本里已经透传完，所以这条现在只约束"别拿正本工程或未改 RTL 的副本直接贴 XDC"**；实名与逐条读数在 12.1.1 五。
12. **别让 PL 口的 RGMII 管脚悬空着插 PC**：实测会把 PC 的千兆网卡连续 `tx hang` 打到 **Code 43**（A，2026-10-30，见 11.2）。网卡本身**没有坏**——拔线 + 手动启用后就恢复成 `Status=OK / ErrCode=0`（见 11.2.1），但中间一度卡在 **Code 22（已禁用）**，非提权会话**改不动**（`Disable-NetAdapter` / `pnputil /restart-device` 全 `Access is denied`），必须 UAC 提权或手动操作。所以：**插之前先把 TX 侧钳到固定电平、或让 PHY 处于复位**；更好的做法是**先用交换机做首次联通性检查**，别拿 PC 网卡试第一刀。
13. **别用 `Restart-PnpDevice`**：这个 cmdlet 在本机 PowerShell 环境里**不存在**（A，2026-10-30）。等价物是提权后的 `pnputil /restart-device "<InstanceId>"`、或 `Enable-PnpDevice -InstanceId <id>`；后者**必须传非空的完整 InstanceId**，取空值会报"required parameter missing"。
14. **别在顶层 XDC 里引用 IP 内部对象名**：`*rgmii_txc_out*`、`i_bufgmux_gmii_clk`、`gmii_clk_125m*` 这类名字在综合后的顶层网表里**一个都解析不到**——BD 里每颗 IP（连 PS7 自己）都是未连入的 OOC 黑盒，`open_checkpoint` 打 27 条 `Project 1-486`（A，`stage15.log`／`stage16.log`）。照 IP 生成文件抄第 27 行那种 `create_generated_clock -source …` 一定报错；顶层只能"取"传播出来的钟，取不到就明确 WARN，别留一条静默失效的 `set_output_delay -clock <空>`——第一版就是这么炸出 4 条 `Vivado 12-4739` 的（A，`stage14.log` 81–94 行）。
15. **别把负数 delay 直接挂到 rxc 焊盘时钟上**：`ps_ai_gmii_to_rgmii_0_0_clocks.xdc` 那套 −1.5／−2.8 是相对**虚拟时钟**量的（该文件第 7 行 `create_clock -name … -period 8` 没有 sources），配套还有 4 条 false path ＋ 2 条 multicycle；只搬 delay 那一半等于把 PHY 内部约 2 ns 移位算两遍（A，文件直读；顶层已整套搬齐，见 12.1.1 五）。

---

## 相关页面

[[板载接口与内核改造收纳进dev]]（三层核对表与悬项）· [[板子（除芯片）]]（两路以太网的来源与口径）· [[dict]]（GEM／EMIO／GMII／RGMII／GMII-to-RGMII／TEMAC）· [[FPAI DEMO说明]]（厂商参考设计的系统方案与 PS7 工程结构）· [[官方demo时序基线与器件库补丁]]（Vivado 2018.3 + JFM_Kits 的版本组合）· [[PL位流重载通道失效]] · [[BOOTbin位流替换手术]] · [[交叉编译主机路由SOP]] · [[硬件与基础运行环境档案]]（eth0 实测 100M）· [[状态源与决策记录]]
