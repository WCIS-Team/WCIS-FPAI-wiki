# PL 网口 / RGMII / SDI 直播旁路 参考文档清单

整理日期：2026-10-24
适用板卡：FMQL30TAI676H 悟净（完整版），192.168.1.113，PL 侧网口为 YT8521SC-CA（RGMII，Bank13）

## 1. TySOM-2A-7Z030（同芯片、同双 RGMII 拓扑的第三方板）

| 名称 | 链接 | 用途 |
|---|---|---|
| Aldec 产品页（完整规格：PS 口 Marvell 88E1116R、PL 口 TI DP83867CR、1GB DDR3、FMC-HPC） | https://www.aldec.com/en/products/emulation/tysom_boards/zynq_7000_soc/tysom_2a_7z030--zynq-board | 看 PL 侧 RGMII 千兆的板级组织 |
| Aldec 支持页（BSP/参考设计下载入口） | https://support.aldec.com/en/products/emulation/tysom_boards/zynq_7000_soc/tysom_2a_7z030--zynq-board | 拿 PetaLinux/Yocto BSP |
| AMD 官方板卡目录收录页 | https://japan.xilinx.com/products/boards-and-kits/1-m1r8wl.html | 确认其为 AMD 生态收录板 |
| TySOM EDK（Yocto/PetaLinux 构建说明） | https://www.edaway.com/product/tysom/ | 软件集成参考 |

## 2. XAPP1082 与配套 IP 文档

| 名称/编号 | 链接 | 看什么 |
|---|---|---|
| XAPP1082《Zynq-7000 AP SoC Ethernet Performance》Wiki 页（含 PDF 与设计文件 zip 入口） | https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841633/XAPP1082+-+Zynq-7000+Ethernet+Performance | PS GEM 经 EMIO、AXI Ethernet、SGMII 多套参考工程 |
| XAPP1082 PDF（AMD 文档站直链，若失效从 Wiki 页进） | https://docs.amd.com/v/u/en-US/xapp1082-zynq-eth | 同上 PDF 版 |
| PG160《GMII to RGMII LogiCORE IP Product Guide》产品页 | https://www.amd.com/en/products/adaptive-socs-and-fpgas/intellectual-property/gmii-to-rgmii.html | 方案 A 的核心 IP，含 GEM 经 EMIO 连接图 |
| PG160 PDF（标准路径，若失效从产品页 Documentation 进） | https://docs.amd.com/v/u/en-US/pg160-gmii-to-rgmii | 同上 |
| PG138《AXI Ethernet Subsystem Product Guide》 | 无固定直链，AMD 文档站（docs.amd.com）搜 PG138，或 Vivado IP catalog 该 IP 右键“Product Guide” | 方案 B 的 PL 端 MAC（TEMAC） |
| PG021《AXI DMA Product Guide》 | 同上，docs.amd.com 搜 PG021 | 方案 B 的数据搬运 |
| 《1G/2.5G Ethernet PCS/PMA or SGMII Subsystem》PG | docs.amd.com 按名称搜索 | 走 SFP/SGMII 时才需要（本板 SFP 与 SDI 抢 GT，互斥） |

## 3. 芯片与 Linux 侧文档

| 名称/编号 | 链接 | 看什么 |
|---|---|---|
| UG585《Zynq-7000 SoC Technical Reference Manual》PDF | https://www.xilinx.com/support/documents/user_guides/ug585-Zynq-7000-TRM.pdf | 其中 Gigabit Ethernet Controller（GEM）一章 |
| UG585 在线版 | https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM | 同上 |
| Linux stmmac 驱动文档（新版 html） | https://www.kernel.org/doc/html/latest/networking/device_drivers/ethernet/stmicro/stmmac.html | dwmac 驱动参数、能力 |
| stmmac 旧版文档（txt） | https://www.kernel.org/doc/Documentation/networking/stmmac.txt | 老内核结构说明 |
| 设备树绑定 snps,dwmac.yaml | https://www.kernel.org/doc/Documentation/devicetree/bindings/net/snps,dwmac.yaml | gmac 节点所有属性含义（内核源码树同路径） |
| Motorcomm PHY 驱动源码（无独立文档页，源码即文档） | 内核源码 `drivers/net/phy/motorcomm.c` | YT8521 驱动与 delay 配置 |
| 设备树 PHY 通用绑定 ethernet-phy.yaml | https://www.kernel.org/doc/Documentation/devicetree/bindings/net/ethernet-phy.yaml | phy-mode、reset-gpios 等 |
| YT8521S 数据手册 | 裕太微官网 motorcomm.cn 按型号 YT8521S 下载 | PHY 寄存器、delay 档位、PHYAD 上下拉 |

## 4. SDI 与直播旁路相关

| 名称/编号 | 链接/位置 | 看什么 |
|---|---|---|
| SMPTE ST 424M（3G-SDI，2.97 Gbps）、SMPTE ST 292-1（HD-SDI，1.485 Gbps） | SMPTE 标准（付费，概览可查 Wikipedia“Serial digital interface”） | 线速率、148.5 MHz 基准时钟的由来 |
| Xilinx SMPTE UHD-SDI / 3G-SDI 接收 IP（UG 与 PG 系列） | docs.amd.com 搜 “SMPTE SDI” | GT 接收 SDI 与视频时序恢复（PL 侧 SDI RX） |
| 项目内 [[VPU串流直播SOP]] | `wiki/PS/OrchestrationLayer/VPU串流直播SOP.md` | 现役直播链（SDI→PL 采集→PS VPU H.264→HLS），VPU 已在板上跑通 |
| 项目内 [[位流构建与SDI信号检测]] | `wiki/todo/位流构建与SDI信号检测.md` | GT 参考时钟 R6/R5（148.5 MHz）实测、SDI 帧判据 |
| 复旦微 FMQL30TAI 数据手册/TRM | 本地 `S:\work\WCIS\source\` | GEM/EMIO、VPU、PS 外设以复旦微文档为准 |
| 悟净开发板（完整版）硬件使用手册 V1.0 | 本地 `source\03_FMQL30TAI-悟净开发板手册\` | 4.8 节 PL 网口 RGMII 引脚表（Bank13）、4.14 SFP、4.15 PCIe |

## 5. 三种 PL 网口方案速查

| 项 | 方案 A：GEM 经 EMIO + GMII-to-RGMII | 方案 B：TEMAC + AXI DMA（PS 供数） | 方案 C：硬件旁路（PL 直出） |
|---|---|---|---|
| MAC 位置 | PS 硬核 GEM1 | PL 软核 TEMAC | PL 软核 TEMAC |
| 关键 IP | PG160 GMII-to-RGMII | PG138 TEMAC + PG021 AXI DMA | PG138 TEMAC + 自建 UDP/IP/RTP 封装 RTL |
| 帧由谁产生 | PS GEM | PS Linux 打包后经 DMA 下发 | PL 打包器直接从 MJPEG AXI-Stream 产生 |
| **视频数据是否过 PS** | **是**（帧在 PS 生成） | **是**（载荷来自 PS DDR） | **否**（全程 PL 内流转，PS 只做初始化） |
| Linux 驱动 | stmmac（snps,dwmac） | xilinx_axienet | 仅管理面需要 AXI-Lite 访问，数据面无驱动 |
| 设备树 | 使能 gmac1 e0049000，phy-mode rgmii-id | 挂 AXI 以太网节点 | TEMAC 可不挂 Linux，仅 AXI-Lite 寄存器 |
| PL 资源 | 极小（IO 延时原语） | 中等（MAC + DMA） | 中等（MAC + 打包状态机，约 5–10K LUT 级） |
| 适用 | 多一路标准 eth1 | 多口、SGMII，软件仍在 PS | **MJPEG/视频硬件直推、低延迟旁路** |

关键澄清：**GMII-to-RGMII 核（PG160）不是 MAC，只是接口电平/时序转换器**，其 GMII 侧必须接 MAC；方案 A 里该 MAC 就是 PS GEM，所以方案 A 的数据必然经过 PS，不能用于硬件旁路。

## 6. 硬件旁路（方案 C）落地要点

1. PL 内数据面：MJPEG 编码器（AXI-Stream）→ 帧打包器（填以太网/IP/UDP/RTP 头、序号、时间戳、校验和、JPEG 分片）→ TEMAC TX（AXI-Stream）→ RGMII → YT8521。
2. 控制面：PS 仅在开机经 AXI-Lite 配 TEMAC、经 MDC/MDIO 配 YT8521（复位、速率、协商）；运行时不碰视频数据。
3. JPEG 帧远大于 MTU（960×540 约 11 KB/帧，1080p 几十 KB/帧），必须分片。标准做法 RTP JPEG（RFC 2435）；自定义接收端可用"帧序号+分片序号+载荷"私有格式，Python socket 重组，最简单。
4. 时钟：TEMAC/RGMII 需 125MHz（可用 YT8521 板载 25MHz 晶振 Y4 倍频或 PHY 输出的 125MHz GTX_CLK）。
5. 待查项：PL 口 YT8521 的 PHYAD（手册未给，读原理图上下拉或 MDIO 扫描 0–31）；MDC/MDIO 在 AE22/AF22、RESET AA13。
6. 带宽：1080p MJPEG q80 约 50–100 KB/帧，30fps 约 100–200 Mbps，千兆口（净荷约 940 Mbps）足够。
7. 协议参考：RFC 2435（RTP JPEG）、RFC 3550（RTP）、RFC 791/768（IP/UDP）；RTP 封装 RTL 可参考开源 Video-over-UDP 工程。


## 7. “SDI 直走 PL 网口、不过 PS”的关键事实（补充）

- 未压缩 SDI 裸视频量级约 1.0–2.5 Gbps（1080p25/60 4:2:2 10bit），千兆网有效载荷约 940 Mbps，**必须在 PL 里做压缩（JPEG/MJPEG、H.264 等）或降规格**，万兆需走 SFP。
- 纯 PL 出流至少需要：SDI RX + 视频处理 + 编码器 + TS/RTP 封装 + UDP/IP 栈 + TEMAC；UDP 可硬件化，RTMP/RTSP 控制面仍需 CPU。
- 板级约束：SDI 与 RGMII 铜口**不抢 GT**（RGMII 不用 GT），可同时工作；SDI 与 SFP/PCIe 抢 GT，靠 MUX 互斥。
- 现役工程链路已用 PS 侧 VPU 硬编 H.264（见 VPU串流直播SOP），纯 PL 旁路前先评估资源（7030 约 125K LC、400 DSP）与是否值得重复实现编码器。
