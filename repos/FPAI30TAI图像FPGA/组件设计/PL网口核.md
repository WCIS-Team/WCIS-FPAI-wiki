# PL网口核

本页讲 `repos/FPAI30TAI图像FPGA/rtl/` 下 PL 侧以太网组件的设计与实现：JPEG 字节流怎么打成 UDP 报文（`rtl/wcis_jpeg_udp_packetizer.v`）、怎么切一拍再进校验器（`rtl/wcis_udp_payload_pipe.v`）、怎么复用 alexforencich/verilog-ethernet 的 MAC/ARP/IPv4/UDP 组合出收发（`rtl/wcis_jpeg_network.v`）与单向发送（`rtl/wcis_jpeg_network_tx.v`）、RGMII 引脚级怎么实现（`rtl/wcis_rgmii_tx_serdes.v`、vendor 的 `rgmii_phy_if.v`/`ssio_ddr_out.v`/`eth_mac_1g_rgmii.v`）、PHY 怎么管理（`rtl/wcis_mdio_clause22.v`），以及时钟域、CDC 契约与 PS 侧接口。

整条链路是**单向推流**：FPGA 只发不收业务数据，接收 UDP/IP 路径被排空当哑负载，ARP 在收发组合里保留、在单向组合里换成"显式下一跳 MAC"。这是本页所有设计的共同前提。

## 总览与分层

| 层 | 组件 | 时钟域 | 职责 |
|---|---|---|---|
| 分片 | `wcis_jpeg_udp_packetizer` | 150 MHz | JPEG 字节 → WJP1 应用头 + 1400 字节载荷分片，算每包 CRC32 与末帧总长 |
| 切分 | `wcis_udp_payload_pipe` | 150 MHz | 16 字节同步 FIFO，切断"分片存储 → UDP 校验累加"的组合路径 |
| 协议（完整） | `wcis_jpeg_network` + vendor `udp_complete` | 150 MHz | 以太网帧 + ARP + IPv4 + UDP 全组合，收发都在 |
| 协议（单向） | `wcis_jpeg_network_tx` + vendor TX 链路 | 150 MHz | `udp_checksum_gen → udp_ip_tx → ip_eth_tx → eth_axis_tx`，目标 MAC 显式配置 |
| MAC | vendor `axis_gmii_tx` / `axis_gmii_rx` / `eth_mac_1g` | 125 MHz（TX） | 前导码、CRC32、最小帧填充、FCS 检查 |
| 引脚 | `ssio_ddr_out` 或 `wcis_rgmii_tx_serdes` | 125 / 250 MHz | RGMII DDR 输出与转发时钟 |
| 管理 | `wcis_mdio_clause22` | 100 MHz | Clause 22 单次事务，配置 PHY |

板级封装 `wcis_pl_jpeg_preview.v` 选的是"单向 + 共用时钟串化器"这一支（`wcis_pl_jpeg_preview.v:131`：`wcis_jpeg_network_tx #(.TARGET("XILINX"),.USE_SERDES_TX(1))`）。完整收发组合 `wcis_jpeg_network` 保留在源码里，用于全链路仿真（`sim/tb_jpeg_network.sv`、`sim/tb_pl_preview_pipeline.sv`）。

## UDP 分片打包

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_jpeg_udp_packetizer.v` 把 JPEG 字节流切成 UDP 数据报，并在每个报文前放一段 40 字节应用头（WJP1），让接收端能在 UDP 之上做重组、校验和丢包判定。

输入侧（`wcis_jpeg_udp_packetizer.v:12-18`）：`session_id`（配置期固定）、`s_frame_id`、`s_data[7:0]`、`s_valid/s_sof/s_last`、`s_ready`、`abort_frame`。输出侧（`wcis_jpeg_udp_packetizer.v:19-28`）：`m_hdr_valid/m_hdr_ready`（UDP 头握手）、`m_udp_length[15:0]`、`m_data/m_valid/m_ready/m_last`（载荷）、`busy`、`protocol_error`、`frames_done/frames_aborted/packets_sent`。

参数：`CHUNK_BYTES`（默认 1400）、`IMAGE_WIDTH/HEIGHT`（写进头里的几何）、`MAX_FRAME_BYTES`（默认 8 MiB）（`wcis_jpeg_udp_packetizer.v:7-10`）。

### 数据通路

四态机 `COLLECT → UDP_HEADER → APP_HEADER → PAYLOAD`（`wcis_jpeg_udp_packetizer.v:31`）：

- `COLLECT`：把字节写进一个 8 位同步 RAM FIFO（`axis_fifo`，深度取 `CHUNK_BYTES` 向上取 2 的幂，`RAM_PIPELINE=1`），同时累加 CRC32、累计 `count`；满 `CHUNK_BYTES` 或遇到 `s_last` 就锁存包头字段并转 `UDP_HEADER`（`wcis_jpeg_udp_packetizer.v:54-64`、`wcis_jpeg_udp_packetizer.v:125-143`）。
- `UDP_HEADER`：拉 `m_hdr_valid`，把 `m_udp_length = 8 + 40 + count` 交给下游（`wcis_jpeg_udp_packetizer.v:77-79`、`wcis_jpeg_udp_packetizer.v:145`）。
- `APP_HEADER`：按 `header_position` 逐字节输出 40 字节 WJP1 头（`wcis_jpeg_udp_packetizer.v:83-106`）。
- `PAYLOAD`：从 FIFO 读 `count` 字节，最后一字节拉 `m_last`（`wcis_jpeg_udp_packetizer.v:80-81`、`wcis_jpeg_udp_packetizer.v:156-164`）。

WJP1 头逐字节定义（`header_position` → 内容，`wcis_jpeg_udp_packetizer.v:86-105`）：`0..3` = `"WJP1"`；`4` = 版本 1；`5` = flags；`6` = 0，`7` = 40（头长）；`8..11` 会话号；`12..15` 帧号；`16..19` 本包在帧内的偏移；`20..23` 整帧总长（仅末包有效）；`24..25` 本包载荷长度；`26..29` 宽高；`30..31` 保留；`32..35` 本包 CRC32；`36..39` = `"JPEG"`。

### 特色设计

**UDP 长度在报名时就固定，中途绝不改**。`m_udp_length` 是 `8+HEADER_BYTES+count` 的组合输出（`wcis_jpeg_udp_packetizer.v:79`），而 `count` 在进入 `UDP_HEADER` 后不再变化。所有"取消"因此必须绕开这个已广告长度：`discard_partial` 只在 `state==COLLECT` 且有待取消/正在取消时复位 FIFO（`wcis_jpeg_udp_packetizer.v:52-53`、`wcis_jpeg_udp_packetizer.v:58`），而 `state==PAYLOAD` 期间绝不复位——正在发的 UDP 报文一定按已广告长度发完（`wcis_jpeg_udp_packetizer.v:51-52`）。

**中止走一条独立的空报文**。`abort_pending` 在 `COLLECT` 看到取消时被提出（`wcis_jpeg_udp_packetizer.v:117`），下一拍用 `count=0`、`flags=4`、`packet_total=0`、`packet_crc=0` 发一个"只有 40 字节头、无载荷"的报文，并 `frames_aborted++`（`wcis_jpeg_udp_packetizer.v:120-124`）。接收端看到 `flags` 的 abort 位就能立刻丢弃拼接中的帧，而不必等超时。

**flags 三位表达位置语义**：bit0 = 本帧首包（`!active || offset==0`）、bit1 = 本帧末包（`s_last`）、bit2 = 中止包（`wcis_jpeg_udp_packetizer.v:139`、`wcis_jpeg_udp_packetizer.v:122`）。首包同时给出 `packet_total`，所以接收端从第一包就知道整帧该多大（`wcis_jpeg_udp_packetizer.v:137`）。

**CRC32 是按包重算的，且与包头同时锁存**。`crc_byte` 是标准反射多项式 `0xEDB88320` 的逐位实现（`wcis_jpeg_udp_packetizer.v:65-75`）；收满一包时 `packet_crc <= ~crc_byte(crc, s_data)`——把当前这个仍在输入端的字节也折进去，所以 CRC 恰好覆盖本包全部载荷（`wcis_jpeg_udp_packetizer.v:138`）。每包开始前 `crc` 复位成 `0xFFFFFFFF`，包结束再复位（`wcis_jpeg_udp_packetizer.v:159`）。接收端因此可以逐包独立校验，不必等整帧。

**"后来的 SOF 不能顶掉在飞帧"，入口只认一种合法序列**。`malformed_input` 三条：无活动帧时来了不带 SOF 的字节、活动帧中又出现 SOF、累计偏移越 `MAX_FRAME_BYTES`（`wcis_jpeg_udp_packetizer.v:49-50`）。命中即置 `protocol_error`（粘滞），若当时有活动帧则转成 `abort_pending`（`wcis_jpeg_udp_packetizer.v:126-128`）。这是 fail-closed：宁可整帧作废，也不把两帧字节拼在一起。

**存储用同步 RAM FIFO，读延迟被应用头遮住**。注释写明了动机：原来的字节数组由同一个 `count` 驱动大量 LUT RAM 写地址，扇出与布线都差；改成同步读 RAM 后，`APP_HEADER` 的 40 拍输出正好覆盖 `RAM_PIPELINE=1` 的预取延迟，`PAYLOAD` 一开始就有数据（`wcis_jpeg_udp_packetizer.v:33-35`、`wcis_jpeg_udp_packetizer.v:145-149`）。

**参数边界在 elaboration 期硬检查**：`CHUNK_BYTES >= 1`、`CHUNK_BYTES + 40 <= 1472`（1500 − 20 IP − 8 UDP）、`MAX_FRAME_BYTES >= CHUNK_BYTES`，否则 `$error`（`wcis_jpeg_udp_packetizer.v:168-171`）。默认 1400 + 40 + 8 = 1448，正好在 1472 以内。

### 关键参数与时序

| 项 | 值 | 依据 |
|---|---|---|
| 应用头 | 40 字节，`HEADER_BYTES` | `wcis_jpeg_udp_packetizer.v:30` |
| 默认分片 | 1400 字节载荷，UDP 长度 1448 | `wcis_jpeg_udp_packetizer.v:7`、`wcis_jpeg_udp_packetizer.v:79` |
| 载荷 FIFO | 深度 = `2^clog2(CHUNK_BYTES)`（1400 → 2048），8 位，`RAM_PIPELINE=1` | `wcis_jpeg_udp_packetizer.v:35`、`wcis_jpeg_udp_packetizer.v:54-64` |
| CRC | 32 位反射，poly `0xEDB88320`，按包 | `wcis_jpeg_udp_packetizer.v:65-75` |
| 头握手 | `m_hdr_valid` 只在 `UDP_HEADER` 状态为高 | `wcis_jpeg_udp_packetizer.v:77` |
| 满负荷判据 | `busy` 为 `active`、`state != COLLECT`、`abort_pending` 三者的逻辑或 | `wcis_jpeg_udp_packetizer.v:82` |

## 载荷切分管道

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_udp_payload_pipe.v` 是一个只用一处的 16 字节 AXI4-Stream FIFO，插在分片器载荷输出与 UDP 校验累加器之间（`wcis_udp_payload_pipe.v:5-8`）。

### 数据通路

直接例化 vendor `axis_fifo`：`DEPTH=16`、`DATA_WIDTH=8`、`LAST_ENABLE=1`、`RAM_PIPELINE=1`、`OUTPUT_FIFO_ENABLE=0`、`FRAME_FIFO=0`、不丢帧不旁路（`wcis_udp_payload_pipe.v:10-20`）。字节与 `tlast` 一起排队、一起出队。

### 特色设计

**它的存在理由只有一条：切组合路径**。分片器的 `position/count` 组合译码 → 存储 RAM 读 → UDP 校验累加器是一条纯组合长链；插入一级寄存读口把这条链断成两段，且因为 FIFO 会反压，语义完全不变（`wcis_udp_payload_pipe.v:1-4`）。

**接口刻意做窄**：只暴露 `s_data/s_valid/s_last/s_ready` 与 `m_data/m_valid/m_last/m_ready`，不带 keep/id/dest/user（`axis_fifo` 的那些端口在例化里被常量或空置），所以它在链路里是纯延迟元件而不是协议参与者（`wcis_udp_payload_pipe.v:10-20`）。

### 关键参数

| 项 | 值 | 依据 |
|---|---|---|
| 深度 | 16 字节 | `wcis_udp_payload_pipe.v:10` |
| 读流水 | `RAM_PIPELINE=1` | `wcis_udp_payload_pipe.v:12` |
| 反压 | 满时反压生产者；无 `DROP_*` | `wcis_udp_payload_pipe.v:13` |

## 完整收发组合

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_jpeg_network.v` 是"MAC + ARP + IPv4 + UDP"的整体组合，收发都在：RGMII 管脚、AXI4-Stream 收发 FIFO、以太网帧收发、UDP 发送与接收（`wcis_jpeg_network.v:5-17`）。

发送接口与分片器直接对接：`s_hdr_valid/s_hdr_ready/s_udp_length` 加 `s_data/s_valid/s_last/s_ready`。配置面：`local_mac/local_ip/destination_ip/gateway_ip/subnet_mask/source_port/destination_port`。状态面：`speed[1:0]`、`arp_failed`、`tx_underflow`、`rx_bad_fcs`。

### 数据通路

四段串起来（`wcis_jpeg_network.v:29-233`）：

1. `eth_mac_1g_rgmii_fifo`：RGMII 引脚 ↔ GMII ↔ 8 位 AXI4-Stream，内含 TX/RX 各 4096 深的异步帧 FIFO，跨 `gtx_clk`/`rx_clk` 与 `clk` 逻辑域（`wcis_jpeg_network.v:29-66`）。
2. `eth_axis_rx`：以太网帧 → 头字段 + 载荷流（`wcis_jpeg_network.v:67-89`）。
3. `udp_complete`：ARP 缓存/请求 + IPv4 收发 + UDP 收发（`wcis_jpeg_network.v:112-233`）。
4. `eth_axis_tx`：头字段 + 载荷流 → 以太网帧（`wcis_jpeg_network.v:90-111`）。

### 特色设计

**接收侧整条路径被"排空"而不是被关掉**。`s_ip_hdr_valid=0`、`m_ip_hdr_ready=1'b1`、`m_ip_payload_axis_tready=1'b1`、`m_udp_hdr_ready=1'b1`、`m_udp_payload_axis_tready=1'b1`（`wcis_jpeg_network.v:135`、`wcis_jpeg_network.v:150`、`wcis_jpeg_network.v:169`、`wcis_jpeg_network.v:189`、`wcis_jpeg_network.v:212`）。收到的报文被逐级吸收，永远不会在内部积压成反压源；同时 `udp_rx_busy`/`ip_rx_busy` 等状态仍被引出，便于观测（`wcis_jpeg_network.v:215-227`）。文件头明确写"receive UDP/IP paths are drained and never execute commands"（`wcis_jpeg_network.v:2-4`）。

**ARP 参数按逻辑时钟换算成周期数**：`ARP_REQUEST_RETRY_INTERVAL = LOGIC_HZ/10`（100 ms 量级）、`ARP_REQUEST_TIMEOUT = LOGIC_HZ`（1 s 量级），缓存 4 项（`ARP_CACHE_ADDR_WIDTH(4)`）（`wcis_jpeg_network.v:112`）。参数跟 `LOGIC_HZ` 绑定，换时钟不用改魔数。`clear_arp_cache` 固定为 0，缓存只在超时/重试逻辑下自然更新（`wcis_jpeg_network.v:232`）。

**MAC 的时钟输入风格是有意的选择**：`CLOCK_INPUT_STYLE("BUFIO")` + `USE_CLK90("TRUE")` + `IODDR_STYLE("IODDR")`，TX/RX FIFO 各 4096（`wcis_jpeg_network.v:29`）。注释解释了为什么不选 BUFR：区域时钟缓冲会把 RX FIFO 连同它的块 RAM 限死在某个时钟区域；BUFIO 让 IDDR 继续吃专用 I/O 时钟，同时给 MAC/FIFO 一个 BUFG，块 RAM 可以放到别的区域（`wcis_jpeg_network.v:26-28`）。

**UDP 校验和打开**：`UDP_CHECKSUM_GEN_ENABLE(1)`（`wcis_jpeg_network.v:112`），配合 IPv4 头校验一起，使主机侧抓包即可独立验算（见 `docs/pl-jpeg-ethernet-validation-20261024.md` 的校验项）。

**配置必须在复位期间固定**：文件头要求"Configuration must remain fixed while reset is low"，板级封装据此做成"只有 TX 关闭时才提交配置"（`wcis_jpeg_network.v:2-4`、`wcis_pl_jpeg_preview.v:57-88`）。

### 关键参数

| 项 | 值 | 依据 |
|---|---|---|
| IFG | `cfg_ifg = 12` | `wcis_jpeg_network.v:63` |
| 收发 FIFO | 各 4096 | `wcis_jpeg_network.v:29` |
| ARP 缓存 | 4 项 | `wcis_jpeg_network.v:112` |
| IP TTL | 64 | `wcis_jpeg_network.v:176` |
| UDP 校验 | 生成使能 | `wcis_jpeg_network.v:112` |
| 目标 | `TARGET="XILINX"` | `wcis_jpeg_network.v:6` |

## 单向发送组合

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_jpeg_network_tx.v` 只做发送：`udp_checksum_gen → udp_ip_tx → ip_eth_tx → eth_axis_tx → axis_async_fifo → axis_gmii_tx → 引脚`。没有接收时钟、没有 RX FIFO、没有自动速率侦测、没有动态 ARP（`wcis_jpeg_network_tx.v:2-9`）。

参数三个：`TARGET`、`USE_PHY_TX_DELAY`（0 = MAC 出 +90° 时钟、PHY 附加 TX 延迟为 0；1 = 同相 125 MHz 直出，延迟交给 PHY，注释标注为 offline candidate）、`USE_SERDES_TX`（0 = vendor `ssio_ddr_out` ODDR 路，1 = `wcis_rgmii_tx_serdes`）（`wcis_jpeg_network_tx.v:11-13`、`wcis_jpeg_network_tx.v:5-8`）。

### 数据通路

上层接口与分片器一致，另加 `next_hop_mac`（48 位显式下一跳）与三个错误输出 `tx_underflow/packet_error/configuration_error`（`wcis_jpeg_network_tx.v:18-24`）。

- `udp_checksum_gen`：接收 `accepted_header` 与载荷流，输出已算好 UDP/IP 校验的头字段 + 载荷（`PAYLOAD_FIFO_DEPTH=2048`、`HEADER_FIFO_DEPTH=8`）（`wcis_jpeg_network_tx.v:99-153`）。
- `udp_ip_tx` → `ip_eth_tx` → `eth_axis_tx`：逐级把并行头字段变成流式以太网帧（`wcis_jpeg_network_tx.v:155-269`）。
- `axis_async_fifo`（4096 深、`FRAME_FIFO=1`、`DROP_OVERSIZE_FRAME=1`、`DROP_BAD_FRAME=1`）：把完整以太网帧从 150 MHz 逻辑域搬到 125 MHz MAC 域（`wcis_jpeg_network_tx.v:276-286`）。
- `axis_gmii_tx`：`ENABLE_PADDING=1`、`MIN_FRAME_LENGTH=64`、`cfg_ifg=12`，做前导码、CRC32、最小帧填充，并给出 `error_underflow`（`wcis_jpeg_network_tx.v:287-293`）。

### 特色设计

**目标 MAC 是配置项，也是准入条件**。`valid_destination = (next_hop_mac != 0) && !next_hop_mac[40] && !(USE_SERDES_TX && USE_PHY_TX_DELAY)`（`wcis_jpeg_network_tx.v:26`）。第 40 位是组播位，置位即拒绝；`USE_SERDES_TX` 与 `USE_PHY_TX_DELAY` 同时为 1 也拒绝——因为共用时钟串化器方案要求 PHY 侧附加 TX 延迟为零，两者语义冲突，冲突时直接不让链路起来（`wcis_jpeg_network_tx.v:5-8`、`wcis_jpeg_network_tx.v:26`）。

**长度检查在报头握手这一层完成**：`s_hdr_ready = header_ready && valid_destination && (s_udp_length >= 8) && (s_udp_length <= 1480)`，且 `accepted_header` 用同一组条件（`wcis_jpeg_network_tx.v:28-30`）。小于 8 是非法 UDP 长度，大于 1480 会超 MTU；两者都不让进协议栈。

**IP 头字段是常量拼装，不走配置**：`eth_type=0x0800`、`ip_version=4`、`ip_ihl=5`、`dscp/ecn=0`、`identification=0`、`flags=3'b010`（DF）、`fragment_offset=0`、`ttl=64`，源/目的 IP 与端口来自配置（`wcis_jpeg_network_tx.v:104-119`）。这样只要配置对了 IP/MAC/端口，其余字段不可能写错。

**帧级 FIFO 是跨时钟域的唯一手段**。`s_clk = clk`（150 MHz）、`m_clk = gtx_clk`（125 MHz），`FRAME_FIFO=1` 使 FIFO 以"整帧"为单位管理，`DROP_OVERSIZE_FRAME`/`DROP_BAD_FRAME` 把超长帧和带错误标记的帧丢掉，绝不把半个帧送到 MAC（`wcis_jpeg_network_tx.v:274-278`）。满时反压生产者（`DROP_WHEN_FULL=0`），所以上层会自然降速而不是丢包。

**三种引脚实现用 `generate` 互斥选择**。`USE_SERDES_TX=1` 走 `wcis_rgmii_tx_serdes`（同一条 125 MHz 送给 5 个数据/控制串化器与 1 个时钟串化器）；`=0` 走 `ssio_ddr_out`，其 `USE_CLK90` 由 `USE_PHY_TX_DELAY` 反相决定（延迟给 PHY 时不使用 90° 时钟）（`wcis_jpeg_network_tx.v:296-307`）。两条支路共用同一份 GMII 输入，切换只改参数。

**错误汇总成一个口**：`packet_error = udp_transmitter_error | ipv4_transmitter_error | fifo_overflow | fifo_bad_frame`（`wcis_jpeg_network_tx.v:308`）。上层只接一根线就能知道"这一帧在协议层或 FIFO 层出过事"。

### 关键参数

| 项 | 值 | 依据 |
|---|---|---|
| UDP 长度范围 | 8..1480 | `wcis_jpeg_network_tx.v:28` |
| 帧 FIFO | 4096 深、整帧模式、满时反压 | `wcis_jpeg_network_tx.v:276-278` |
| MAC 侧 | 最小帧 64、开填充、IFG 12 | `wcis_jpeg_network_tx.v:287` |
| 校验 FIFO | 载荷 2048、头 8 | `wcis_jpeg_network_tx.v:99` |
| 板级选择 | `USE_SERDES_TX=1`、`USE_PHY_TX_DELAY=0` | `wcis_pl_jpeg_preview.v:131` |

## RGMII 物理层

### 定位与接口

- `repos/FPAI30TAI图像FPGA/rtl/wcis_rgmii_tx_serdes.v`：用 6 个 `OSERDESE2` 实现 RGMII 发送——5 个数据/控制、1 个转发时钟（`wcis_rgmii_tx_serdes.v:8-14`）。
- vendor `rtl/vendor/verilog_ethernet/rtl/ssio_ddr_out.v`：ODDR 版发送（数据吃 `clk`，转发时钟吃 `clk90` 或 `clk`）（`ssio_ddr_out.v:58-82`）。
- vendor `rtl/vendor/verilog_ethernet/rtl/rgmii_phy_if.v`：双向 RGMII 前端，含 RX 的 IDDR/采样、TX 的 DDR 组装、速率适配与复位同步（`rgmii_phy_if.v:100-253`）。
- vendor `rtl/vendor/verilog_ethernet/rtl/eth_mac_1g_rgmii.v`：把 `rgmii_phy_if` 与 `eth_mac_1g` 连起来，并做 PHY 速率侦测（`eth_mac_1g_rgmii.v:128-252`）。

### 数据通路

`wcis_rgmii_tx_serdes` 把 GMII 的一个字节拆成低/高半字节，每个半字节重复两次送进 4:1 DDR 串化器的 D1..D4，从而在每个 8 ns 周期输出 `低,低,高,高`（`wcis_rgmii_tx_serdes.v:15-29`）。`gmii_error` 不单独出脚，而是按 RGMII 约定在**高半字节的 TX_CTL 上取 `tx_en ^ tx_er`**、低半字节只取 `tx_en`（`wcis_rgmii_tx_serdes.v:15-16`）。时钟串化器的图样是 `0,1,1,0`（`wcis_rgmii_tx_serdes.v:31-39`），即上升/下降沿落在每个半字节跳变之后 2 ns。

`rgmii_phy_if` 的 RX 侧用 IDDR 在 `rgmii_rx_clk` 双边沿各收 4 位数据 + 1 位 CTL，拼成 8 位 GMII 数据；`rx_ctl` 的低半字节是 DV、两半字节异或是 ER（`rgmii_phy_if.v:100-106`）。TX 侧按 `speed` 组装 `rgmii_txd_1/2`，再分别用 ODDR 打出数据和转发时钟（`rgmii_phy_if.v:165-226`）。

### 特色设计

**发送时钟与数据同源同相，相位差由串化图样而不是时钟相位给出**。6 个 `OSERDESE2` 全部用同一条 250 MHz `CLK` 和相位对齐的 125 MHz `CLKDIV`，`OCE` 常开、`DATA_WIDTH=4`、`DATA_RATE_OQ="DDR"`、`TRISTATE_WIDTH=4`、`SERDES_MODE="MASTER"`（`wcis_rgmii_tx_serdes.v:20-29`、`wcis_rgmii_tx_serdes.v:31-39`）。数据图样 `L,L,H,H` 加时钟图样 `0,1,1,0`，在理想波形上得到 2 ns 的采样窗口错位。这样不需要第二个 PLL 输出或额外的 90° 时钟网络，全部相位关系来自同一个时钟域的寄存器初值。

**PHY 侧的 TX 延迟必须置零，这是一条硬前提**。文件头写"PHY TX internal delay MUST remain zero"，因为延迟已经在 FPGA 内部做掉了（`wcis_rgmii_tx_serdes.v:7`）；`wcis_jpeg_network_tx` 里也用 `valid_destination` 把"串化器 + PHY 附加延迟"这个组合直接拒绝（`wcis_jpeg_network_tx.v:26`）。

**ODDR 支路保留 90° 时钟的两种归属**。`ssio_ddr_out` 的 `USE_CLK90` 决定转发时钟用 `clk90` 还是 `clk`（`ssio_ddr_out.v:58`）；`wcis_jpeg_network_tx` 把它与 `USE_PHY_TX_DELAY` 反相绑定（`wcis_jpeg_network_tx.v:303`）。于是"延迟在 MAC 侧"与"延迟在 PHY 侧"是同一个参数的两个取值，不会出现两边都加延迟。

**速率适配是时钟使能而不是换时钟**：10M/100M 时 `gmii_clk_en` 按计数器产生周期性使能，1G 时常 1（`rgmii_phy_if.v:114-198`）；MAC 侧用 `tx_clk_enable`/`rx_clk_enable` 吸收这个使能（`eth_mac_1g_rgmii.v:242-243`）。转发时钟也按速率改变翻转节奏（`rgmii_phy_if.v:116-156`）。

**速率侦测靠"数 RX 时钟相对参考时钟的快慢"**。`rx_prescale` 在 `rx_clk` 域自由计数，其高位同步到 `gtx_clk` 域形成边沿检测；用参考计数器在两个连续 prescale 边沿之间的长度判 10M / 100M / 1000M，并据此设 `speed` 与 `mii_select`（`eth_mac_1g_rgmii.v:128-181`）。这是纯数字测速，不需要 PHY 寄存器。

**复位在两个时钟域各自同步释放**：`tx_rst_reg`/`rx_rst_reg` 各是 4 位链，`[0]` 作为该域复位（`rgmii_phy_if.v:232-253`）。异步置位、本域释放，避免复位撤销时的亚稳态。

### 关键参数与时序

| 项 | 值 | 依据 |
|---|---|---|
| 串行/并行时钟 | 250 MHz / 125 MHz，同一 PLL、同类型 BUFG | `wcis_rgmii_tx_serdes.v:3-6` |
| 串化比 | 4:1 DDR，每周期 2 个半字节 | `wcis_rgmii_tx_serdes.v:20-24` |
| 数据图样 | `L,L,H,H`；时钟图样 `0,1,1,0` | `wcis_rgmii_tx_serdes.v:24`、`wcis_rgmii_tx_serdes.v:35` |
| CTL 编码 | 低半字节 = `tx_en`，高半字节 = `tx_en ^ tx_er` | `wcis_rgmii_tx_serdes.v:15-16` |
| MAC 最小帧 | 64 字节，开填充 | `wcis_jpeg_network_tx.v:287` |
| 速率档 | 10M 计数 0..49、100M 0..4、1000M 恒开 | `rgmii_phy_if.v:119-148` |

## MDIO 管理

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_mdio_clause22.v` 做一次有界的 Clause 22 读或写：给 PHY 地址、寄存器地址，返回 16 位读数据或错误标志（`wcis_mdio_clause22.v:5-14`）。

接口：`command_valid/command_ready` 发起，`command_read` 选读写，`phy_address[4:0]`/`register_address[4:0]`/`write_data[15:0]` 为参数；输出 `done`、`error`、`read_data[15:0]`、`mdc`、`mdio_out`、`mdio_tristate`、`mdio_in`。参数 `HALF_PERIOD` 决定 MDC 半周期（`wcis_mdio_clause22.v:6`）。

### 数据通路

整个事务被展开成一个 64 位移位寄存器：起始位 32 个 1（前导码）+ `01` + 操作码（读 `10`、写 `01`）+ 5 位 PHY 址 + 5 位寄存器址 + `10`（turnaround）+ 16 位数据（`wcis_mdio_clause22.v:31-32`）。`mdio_out` 就是 `bits[63]`，`position` 每半个 MDC 周期右移一位（`wcis_mdio_clause22.v:21`、`wcis_mdio_clause22.v:42-48`）。`mdio_tristate = !busy || (read_mode && position >= 46)`——空闲时不驱动，读事务进入 turnaround 之后也不驱动（`wcis_mdio_clause22.v:22`）。

### 特色设计

**数据只在 MDC 下降沿改变**。移位发生在 `divider == HALF_PERIOD-1` 且 `mdc==1` 那一拍（即"MDC 高电平结束、即将拉低"的时刻）（`wcis_mdio_clause22.v:42-47`）。这样 MDIO 的高/低电平在整个 MDC 高相位内保持稳定，符合 PHY 在 MDC 上升沿采样的时序要求。

**读数据不在边沿采，而是在高电平中间采**。`mdio_in` 先过两级同步（`mdio_sync`），再在 `mdc && divider == HALF_PERIOD/2` 那拍取样（`wcis_mdio_clause22.v:19`、`wcis_mdio_clause22.v:38-41`）。注释给出量化依据：100 MHz 输入、`HALF_PERIOD=25` 时采样点距 MDC 上升沿 120 ns，远大于 PHY 的 20 ns 最大数据延迟（`wcis_mdio_clause22.v:36-37`）。用"高相位中点"而不是"边沿"，把 PHY 输出延迟与同步器延迟都算进预算。

**turnaround 缺失被判为错误**：读事务在 `position==47` 采样到的值必须为 0（PHY 在这拍释放总线），否则置 `error`（`wcis_mdio_clause22.v:39`）。没有 PHY 时这条会立刻触发，而不是读回一串无效数据。

**`HALF_PERIOD` 有下界**：`initial` 里 `HALF_PERIOD < 10` 直接 `$error`（`wcis_mdio_clause22.v:52`），保证至少留出同步器建立时间。上层的寄存器页用它做慢速管理通道（`wcis_preview_registers.v:24-28`）。

### 关键寄存器与时序

| 项 | 值 | 依据 |
|---|---|---|
| 帧格式 | 32×`1` + `01` + op + 5 + 5 + `10` + 16 位数据 = 64 位 | `wcis_mdio_clause22.v:31-32` |
| MDC 半周期 | `HALF_PERIOD` 个 `clk` 周期（上层 100 MHz 域） | `wcis_mdio_clause22.v:6`、`wcis_mdio_clause22.v:18` |
| 读采样点 | MDC 高相位中点，两级同步后 | `wcis_mdio_clause22.v:38-41` |
| 三态 | 空闲或读 turnaround 之后释放 | `wcis_mdio_clause22.v:22` |
| 错误 | turnaround 非 0 | `wcis_mdio_clause22.v:39` |

上层寄存器页把 MDIO 封装成一条命令寄存器：写 `0x30` = `{read, phy[25:21], reg[20:16], data[15:0]}`，读 `0x34` = `{error, complete, busy, read_data}`（`wcis_preview_registers.v:60-71`、`wcis_preview_registers.v:92`）。

## verilog_ethernet 复用清单

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/vendor/verilog_ethernet/` 是 alexforencich/verilog-ethernet 的固定切片：`sources.json` 记录 commit `77320a9471d19c7dd383914bc049e02d9f4f1ffb`、MIT 许可、`modifications: []`（`rtl/vendor/verilog_ethernet/sources.json:1-6`），共 41 个文件，含 RTL、`axis/rtl/` 子模块、Vivado 综合脚本与两份 `COPYING`。

### 数据通路

用到的组合层次（自上而下）：

- `eth_mac_1g_rgmii_fifo` → `eth_mac_1g_rgmii`（速率侦测）→ `rgmii_phy_if` + `eth_mac_1g`。
- `eth_mac_1g` → `axis_gmii_rx` / `axis_gmii_tx`（GMII 双向边沿 ↔ 8 位 AXI4-Stream，含 CRC 与填充）。
- `udp_complete` → `ip_complete`（→ `ip` → `ip_eth_rx`/`ip_eth_tx`、`arp` → `arp_eth_rx`/`arp_eth_tx`/`arp_cache`）+ `udp`（→ `udp_ip_rx`/`udp_ip_tx`）。
- `udp_checksum_gen`：单向发送链里替代 `udp` 的校验生成级。
- 基础设施：`axis_async_fifo`（跨域，格雷码指针 + 多级同步）、`axis_fifo`（同步 RAM）、`axis_async_fifo_adapter`、`axis_gmii_rx/tx` 里用到的 `lfsr`（CRC32）、`arbiter`/`priority_encoder`。
- 引脚原语封装：`oddr`、`iddr`、`ssio_ddr_in`、`ssio_ddr_out`。

### 特色设计

**只挑 TX 需要的那几块拼单向链**。`wcis_jpeg_network_tx` 用的是 `udp_checksum_gen` + `udp_ip_tx` + `ip_eth_tx` + `eth_axis_tx` + `axis_gmii_tx`，而不是 `udp_complete`（`wcis_jpeg_network_tx.v:99-293`）。原因是这几个模块都把目标 MAC 当显式输入，不需要 ARP 解析，也不含接收侧状态机。

**校验生成独立成一级**。`udp_checksum_gen` 先按 `STATE_IDLE → SUM_HEADER_1..3 → SUM_PAYLOAD → FINISH_SUM` 把 UDP 伪头、UDP 头与整个载荷累加，再把算好的 `m_udp_checksum` 与载荷一起交出去（`udp_checksum_gen.v:107-151`）。它对载荷做的是"旁路 FIFO + 累加"，所以发送端不需要先把报文缓完整才能算校验。

**CRC32 用 LFSR 而不是表**：`lfsr` 配 `LFSR_POLY(32'h4c11db7)`、`GALOIS`、`REVERSE(1)`，每字节更新一次状态（`axis_gmii_tx.v:162-176`、`axis_gmii_rx.v:152-166`）。接收侧把算出的状态与帧尾 4 字节比对，`{rxd_d0..d3} == ~crc_next` 判 FCS 好坏（`axis_gmii_rx.v:220-228`）。

**异步 FIFO 用格雷码 + 多级同步**：`bin2gray`/`gray2bin` 两个函数 + `wr_ptr_gray_sync1/2`、`rd_ptr_gray_sync1/2` 两极同步（`axis_async_fifo.v:194-201`、`axis_async_fifo.v:207-252`）。`FRAME_FIFO` 模式额外用"提交指针"（`wr_ptr_sync_commit`）确保只把完整帧暴露给读侧。

**MAC 状态跨域用"翻转位"而不是电平**。`eth_mac_1g_rgmii_fifo` 把 `tx_error_underflow`、`rx_error_bad_frame`、`rx_error_bad_fcs` 用发送域/接收域的翻转位记录，再在逻辑域用"当前 ^ 上一拍"还原成单拍脉冲（`eth_mac_1g_rgmii_fifo.v:141-200`）；`speed` 走普通两级同步（`eth_mac_1g_rgmii_fifo.v:202-212`）。这样逻辑域的脉冲宽度与源域时钟无关。

**ARP 缓存是带哈希的环形查找表**：`CACHE_ADDR_WIDTH` 决定表大小，查询用 `query_request_hash` 作读指针、写侧用环形 `wr_ptr`（`arp_cache.v:78-83`、`arp_cache.v:158-176`）。`arp.v` 把收发、缓存、请求重试/超时状态机拼在一起，向上只暴露 `arp_request/arp_response`（`arp.v:229-268`）。

### 关键参数

| 项 | 值 | 依据 |
|---|---|---|
| 上游 commit | `77320a9471d19c7dd383914bc049e02d9f4f1ffb` | `sources.json:3` |
| 许可 | MIT，`modifications: []` | `sources.json:4-5` |
| 切片来源 | NexysVideo RGMII/UDP 示例的依赖列表（不含板级示例） | `sources.json:6` |
| 本项目 MAC 参数 | `IODDR_STYLE="IODDR"`、`CLOCK_INPUT_STYLE="BUFIO"`、`USE_CLK90="TRUE"` | `wcis_jpeg_network.v:29` |
| 本项目 TX 参数 | `ENABLE_PADDING=1`、`MIN_FRAME_LENGTH=64`、`cfg_ifg=12` | `wcis_jpeg_network_tx.v:287-292` |

## 时钟与 CDC

### 定位与接口

PL 网口一共涉及四个时钟域：

| 域 | 频率 | 来源 | 谁在里面 |
|---|---|---|---|
| GP 寄存器 | 100 MHz | 平台给定 | NTP 寄存器页、MDIO |
| 网络/JPEG 逻辑 | 150 MHz | 预览 PLL `CLKOUT0` | 分片器、切分管、协议栈、MAC 逻辑侧 |
| MAC 物理发送 | 125 MHz | 预览 PLL `CLKOUT1` | `axis_gmii_tx`、帧 FIFO 读侧 |
| 串行 | 250 MHz | 预览 PLL `CLKOUT2` | 6 个 `OSERDESE2` |
| 摄像头 | `cam_clk` | SDI 恢复时钟 | `wcis_sdi_jpeg_stream` 的采集侧 |

依据：`wcis_pl_jpeg_preview.v:19-27`（PLL 分频比）、`wcis_pl_jpeg_preview.v:113`（`LOGIC_HZ=150000000`）。

### 数据通路

配置与状态的跨界各有一条明确通路：GP → 150 MHz 用 224 位配置邮箱一次性提交（`wcis_pl_jpeg_preview.v:73-88`）；150 MHz → GP 用 167 位状态邮箱整批快照（`wcis_preview_registers.v:29-36`）；125 MHz → 150 MHz 的错误脉冲先锁成电平再单比特同步（`wcis_pl_jpeg_preview.v:100-112`）。业务数据本身跨域只靠两个 FIFO：摄像头域的 `axis_async_fifo`（像素）与 150→125 MHz 的帧 FIFO（以太网帧）。

### 特色设计

**"载荷总线必须走邮箱或 FIFO，不能拆成多根同步器"**。`wcis_cdc_mailbox` 是单入口 + 请求/应答翻转 + 载荷保持：源侧 `s_ready` 只有在"请求位 == 同步回来的应答位"时才为高，目的侧消费后回翻转（`wcis_cdc_mailbox.v:13`、`wcis_cdc_mailbox.v:18-32`）。复位是"异步置位、本域两级释放"（`wcis_cdc_mailbox.v:14-17`），所以两侧可以同时被同一个组合复位拉起而不会各自锁死在半路。

**只在集成时加约束，不在 RTL 里塞假路径**。`constraints/pl_jpeg_preview_cdc.tcl` 对每个 mailbox 的保持寄存器 → 捕获寄存器加 `set_max_delay -datapath_only 8.0` 与 `set_bus_skew 8.0`（`pl_jpeg_preview_cdc.tcl:30-31`），对同步器只用 `set_false_path -to <第一级 D 引脚>`（`pl_jpeg_preview_cdc.tcl:20`、`pl_jpeg_preview_cdc.tcl:33`、`pl_jpeg_preview_cdc.tcl:39-45`），并显式拒绝"整时钟组假路径"和"整条数据总线排除"（`pl_jpeg_preview_cdc.tcl:2-3`）。

**单比特状态有独立的同步器组件**，`wcis_status_sync` 只做两级同步 + 本地复位释放，注释明确要求生产者保持足够长、载荷总线不得走这条路（`wcis_status_sync.v:1-19`）。它与邮箱的分工写在文件名里：状态 vs 数据。

**使能/复位本身也是一条 CDC 路径，而且要单独设计**。`enable_to_network` 在 150 MHz 域两级同步后，只用于"异步置位"（`wcis_pl_jpeg_preview.v:61-64`、`wcis_pl_jpeg_preview.v:78-87`）；公共复位在目标域各自同步释放（`wcis_pl_jpeg_preview.v:89-94`）。这样既不把 200 MHz 的复位直接送进 150 MHz 的组合逻辑，也不让不同域的复位撤销时刻彼此依赖。

### 关键约束

| 项 | 值 | 依据 |
|---|---|---|
| 邮箱数据路径 | `set_max_delay -datapath_only 8.0` + `set_bus_skew 8.0` | `pl_jpeg_preview_cdc.tcl:30-31` |
| 同步器 | 只对第一级 D 端 `set_false_path` | `pl_jpeg_preview_cdc.tcl:20` |
| 异步复位 | `ASYNC_REG` 寄存器 PRE/CLR 端 `set_false_path` | `pl_jpeg_preview_cdc.tcl:39-45` |
| 生成时钟不确定度 | 0.100 ns（PLL 三路输出与转发时钟） | `fmql30tai_pl_ethernet_tx.xdc:32-33` |
| TX 输出要求 | `set_output_delay` 双边沿 ±1.2 ns | `fmql30tai_pl_ethernet_tx.xdc:27-31` |

## 与 PS 的接口

### 定位与接口

PS 只碰两条路径：**NTP 寄存器页**（配置与统计）与 **MDIO 命令寄存器**（PHY 管理）。它不搬业务数据。

- 页基址 `0x400c2200`，与 JPG1（`0x400c2100`）同属 CustomOp 寄存器区（`npu_photo/src/pl_net_config.cpp:16`）。
- 页内偏移由 `wcis_preview_registers.v` 定义；`wcis_preview_csr_router` 按 `awaddr[17:8] == 10'h022` 把这一窗口从既有寄存器页里切出来（`wcis_preview_csr_router.v:13-14`）。

### 数据通路

配置顺序（PS 侧 `pl_net_config.cpp` 的实际流程）：先读 `0x00` 校验 magic、`0x5c` 校验能力、`0x54/0x58` 校验几何 → 写 `0x04` 置 0 确保关闭 → 拉低 PHY 复位 20 ms 再释放、等 50 ms → 用 MDIO 命令寄存器找 YT8521（ID `0x0000011a`）、读写扩展寄存器清 TX 延迟位并读回校验 → 通过 MII 寄存器强制 1000 全双工并等到 BMSR/特定状态寄存器显示链路就绪 → 写 `0x0c/0x18/0x1c/0x28/0x60/0x64` → 最后写 `0x04` 置 1 并使能，读回 `0x04` 与 `0x2c` 确认没有被拒绝（`npu_photo/src/pl_net_config.cpp:47-100`）。

统计读取：`0x40..0x50` 五个 32 位计数器，`0x44/0x48/0x4c` 是 JPEG 侧帧计数与拒绝/中止数，`0x50` 是已发 UDP 包数（`wcis_preview_registers.v:94-98`、`npu_photo/src/pl_net_config.cpp:52-53`）。

### 特色设计

**"默认关闭 + 使能前校验 + 运行中拒改"三段式**。复位后 `enable=0`、`phy_reset_n=0`（PHY 保持复位）（`wcis_preview_registers.v:39`）；使能要求一整套字段非零（见上一节 `wcis_preview_registers.v:49-57`）；使能后除 `0x04` 外的写全部计入 `rejected_writes`（`wcis_preview_registers.v:57`）。PS 侧读回 `0x2c` 就知道自己有没有被拒。

**能力位让软件能识别固件形态**：`0x5c` 在 TX-only 时读 `7`——bit0 显式下一跳、bit1 固定 1G 全双工、bit2 共用时钟串化器（PHY 附加 TX 延迟为 0）（`wcis_preview_registers.v:101-103`）。PS 侧先比对这个值再决定后续流程，避免软件按错误拓扑配置（`npu_photo/src/pl_net_config.cpp:47`）。

**PHY 只改已知寄存器，且改完必读回**：只清 TX 延迟相关位、只写 MII BMCR 的固定位，每次写完都读回比对（`npu_photo/src/pl_net_config.cpp:79-86`）；文件头明确"不改 LDO/电压 strap、不猜别的 PHY 型号"（`npu_photo/src/pl_net_config.cpp:80`）。

**协商结果自己验，不信 strap**：轮询 BMSR 与 PHY specific status，直到 `bmsr & 0x24 == 0x24`（链路 + 自协商完成）且 `ssr & 0xec00 == 0xac00`（1000 全双工），否则直接抛错，不带着错速率启用发送（`npu_photo/src/pl_net_config.cpp:89-94`）。

**下一代 MAC 是配置项而不是寄存器副作用**：`0x60/0x64` 只在 `TX_ONLY_SERDES=1` 时接受写入，否则计入拒绝（`wcis_preview_registers.v:72-73`）。这样 NTP1（收发版）不会误收一个"下一跳 MAC"却用它做 ARP 目标。

### 关键寄存器（NTP 页，偏移相对基址 0x400c2200）

| 偏移 | 读 | 写 |
|---|---|---|
| `0x00` | `0x4e545031`（NTP1）/ `0x4e545032`（NTP2） | — |
| `0x04` | `{31'd0, enable}` | 1 = 使能（带前置校验），0 = 关闭 |
| `0x08` | `{lock, packet_error, rx_bad_fcs, tx_underflow, arp_failed, speed}` | — |
| `0x0c`/`0x10`/`0x14` | `session_id` / `local_mac[31:0]` / `local_mac[47:32]` | 同 |
| `0x18`..`0x24` | `local_ip` / `destination_ip` / `gateway_ip` / `subnet_mask` | 同 |
| `0x28` | `{source_port, destination_port}` | 同 |
| `0x2c` | `rejected_writes` | — |
| `0x30` | — | MDIO 命令 `{read, phy[25:21], reg[20:16], data}` |
| `0x34` | `{error, complete, busy, read_data}` | — |
| `0x38` | `{31'd0, phy_reset_n}` | bit0 = PHY 复位释放 |
| `0x40`..`0x50` | 5 个 32 位统计快照 | — |
| `0x54`/`0x58` | 1920 / 1080 | — |
| `0x5c` | 能力位（TX-only 为 `7`） | — |
| `0x60`/`0x64` | `next_hop_mac[31:0]` / `[47:32]` | 仅 TX-only 接受 |

依据：`wcis_preview_registers.v:58-107`。

## 关键参数汇总

- 分片：1400 字节载荷 + 40 字节 WJP1 头 + 8 字节 UDP 头 = 1448，上限 1472；`MAX_FRAME_BYTES` 8 MiB。
- 协议：IPv4（IHL 5、DF、TTL 64）、UDP 校验生成开启、目的 MAC 显式配置、拒绝零/组播地址。
- MAC：IFG 12、最小帧 64、开填充、`IODDR` + `BUFIO` + `USE_CLK90`。
- 引脚：RGMII TX 5 根数据/控制 + 1 根转发时钟；串化 4:1 DDR，图样 `L,L,H,H` / `0,1,1,0`；PHY 附加 TX 延迟必须为 0。
- 时钟：150 MHz 逻辑、125 MHz MAC、250 MHz 串行、100 MHz 寄存器；令牌只在邮箱/FIFO 里跨域。
- 管理：Clause 22、64 位移位帧、MDC 下降沿改数据、高相位中点采数据、turnaround 非 0 即错。
- PS：NTP 页 `0x2200`（基址 `0x400c2200`），默认关闭，使能前校验一整套字段，运行中拒改；统计按 167 位整批快照读回。

具体数值、位宽与状态编码以对应源码为准；本页引用的行号对应当前 `repos/FPAI30TAI图像FPGA/` 工作副本。
