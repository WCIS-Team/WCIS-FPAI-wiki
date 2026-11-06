# 视觉前端RTL

视觉前端是图像进入 PS/NPU 之前的整流与观测层：按帧准入控制流量（整帧选择）、提供板内测试图源（VTC 重写）、把模型输入画布补齐（letterbox）、被动观测真实 RX 流（SDI 诊断），并把配置与状态安全地跨进 AXI 时钟域（CSR 路由、NTP1 管理页、CDC mailbox、单比特状态同步）。模块位于 `rtl/`，接入现场在 `case/rtl/display/frame_trans.sv` 与 `frame_ctrl.v`。

这批 RTL 的三条共同纪律：

- 跨时钟域为一等公民：多位数据一律走捆绑式 mailbox（payload 保持到目的侧消费并回 ACK 为止），单比特才允许两级同步；每个模块头注释都声明自己没做什么（无 CDC、不能反压、不能撤销请求），把集成责任显式交给使用方。
- 请求永不撤销：ready 只在能接受新请求时打开，忙时新写被拒并由软件读回判定；在途请求/响应不回收、不复用。
- 有效性与 payload 解耦：数据无条件寄存，不用有效与否去选择宽位数据，从结构上消掉大数据 mux。

## wcis_frame_rate_gate：整帧选择

### 定位与接口

把厂商案例内部的 RGB888 DVP 流（`s_vsync/s_href/s_data[23:0]`）按整帧放行或丢弃，把源帧率降到工作帧率或待机帧率；配置走 `cfg_clk`（AXI），帧判定走 `cam_clk`（`rtl/wcis_frame_rate_gate.v:6-27`）。配置字 `cfg_word[1:0]`＝{enable, active}：2'b01 旁路、2'b10 待机、2'b11 工作；复位默认旁路（`payload_hold`/`cfg_applied`/`current_config` 初值均为 2'b01，:45、:87）。模块不能反压摄像头，被丢弃的帧仍被 SDI 接收器完整接收，只是不交给后级（头注释 :2）。输出 `seen_frames/selected_frames/dropped_frames` 三个 camera 域计数器。

### 数据通路

帧边界＝`s_vsync` 上升沿（`frame_start`，:74）。每个相机时钟拍 `m_vsync/m_href <= s_vsync/s_href && pixel_keep`（:109-110）；`pixel_keep` 在帧边界取 `boundary_keep`、帧内保持 `keep_frame`（:81）。`m_data <= s_data` 无条件寄存（:113）。帧边界一拍内完成：提交新配置（:115-118）、更新相位（:120-121）、更新三个计数器（:122-124）。

### 特色设计

1. cfg 与 cam 的双向 toggle mailbox（请求永不撤销、帧边界提交）。cfg 域持锁 `payload_hold` 并翻转 `request_toggle`（:62-65）；`request_toggle` 两级同步进 cam 域（`request_sync`，:107），cam 域只在帧边界取保持的数据提交 `current_config`、回 `applied_toggle`（:115-118）；`applied_toggle` 再两级同步回 cfg 域（`ack_sync`），更新 PS 可读的 `cfg_applied`（:57-61）。`cfg_ready = request_toggle == ack_sync[1]`（:41）：忙时新配置不接受、在途请求不撤销，由软件读回判定。帧内绝不切换参数：`boundary_config` 只在 `frame_start` 那拍生效（:76、:115-118），保证一帧内判定条件恒定。
2. 分数帧率相位累加。相位宽度 `PHASE_BITS = $clog2(SOURCE_FPS+1)`（:72）；每帧 `phase_sum = phase + target_fps`，`boundary_keep = !enable || phase_sum >= SOURCE_FPS`（:79-80），放行帧扣减 `phase_sum - SOURCE_FPS`（:120-121）。30 到 20 呈丢1留2循环，30 到 1 每 30 帧保留 1 帧；每次配置提交相位从零重计（:79 的 pending 分支），因此切入待机后首帧最长等约 1 秒，PS 取帧超时须按此加长（以 `docs/interface.md` 为准）。
3. 复位结构：两域共用同一组合复位输入异步断言、各自本地两级同步释放（`cfg_reset_sync/cam_reset_sync`，:28-34），释放前数据路径保持旁路默认；camera 复位后软件须重读 applied 状态并重发模式。
4. payload 无 mux：`m_data` 无条件寄存（:111-113 注释），避免把帧选择做成 24 位数据选择器。
5. 静态参数 elaboration 守卫：`initial $error` 检查三参数范围（:130-134）；`SOURCE_FPS` 是编译期假设，真实到达率变化需重构建。

### 关键参数/寄存器

- 例化参数 `SOURCE_FPS=30, ACTIVE_FPS=20, STANDBY_FPS=1`（`case/rtl/display/frame_trans.sv:208`），挂接在源选择 mux 之后、frame_ctrl 之前（`frame_trans.sv:201-215`），PS 抓帧与 NPU 看到同一批被准入的帧。
- frame_ctrl 扩展寄存器（基址 0x40080000，旧 0x00..0xB4 全保留）：0xB8 写＝低字节 strobe 有效时提交 bit1:0＝{enable,active}，读＝最近接受配置＋忙时写入被拒标记（`case/rtl/display/frame_ctrl.v:261-278`、:950）；0xBC 读＝帧边界已应用并回 ACK 的配置＋pending（:263、:951）；0xC0 读＝扩展识别字 0x57434953（"WCIS"，:952）——软件先验魔数再操作，防止把模式控制写给旧位流。
- 计数器带 `mark_debug` 供 ILA 抓取（`frame_trans.sv:207`），不直接跨到 AXI-Lite（避免再开一条多位总线 CDC）；计数表示进入前端的帧数，不表示 NPU 完成次数。

## vtc：重写版 VTC 测试图源

### 定位与接口

注册型测试图发生器，兼容厂商 vtc 的端口契约：模块名 `vtc`、端口与 32 位时序配置宽度不变，经 `scripts/integrate_case.py` 写入实际工程 `case/rtl/display/vtc.v`，属替换实现而非新增模块（`rtl/wcis_vtc.v:8-14`）。输出 `vs/hs/de/data[23:0]`。

### 数据通路

三段：时序算术寄存器组（`h_start/h_stop/h_total/h_last` 等每拍由 `H_SYNC+H_BACK_PORCH` 等输入寄存，:17-31）；`hcnt/vcnt/frame_cnt` 计数器（:33-47）；两级流水输出（:49-70）。

### 特色设计

1. 两级流水与 RGB 仅 de=1 有效的契约。第一级各自寄存水平/垂直有效比较、hs/vs 原始比较与灰度加法 `gray_d <= hcnt[7:0]+frame_cnt`（:60-64）；第二级合并 `de = h_active_d && v_active_d`、`data <= {3{gray_d}}`（:65-68）。所有输出相对厂商计数序列统一延迟两级（头注释 :6-7），比较、有效区合并与 payload 不再挤在同一拍，下游寄存器前没有长组合链。无效区 RGB 不清零（数据路径不含 validity mux），改为契约 RGB 仅在 de=1 时消费，下游按 href 门控接收。
2. 时序算术与计数/像素路径分离缓存（:15-16 注释），保留原 32 位寄存器契约包括 sum 算术。
3. 测试图为 64 级灰度行渐变叠加帧号（`{3{hcnt[7:0]+frame_cnt}}`，:64、:68）。

### 关键参数/时序

- 无 AXI CDC、无原子提交：时序参数必须在停流且 VTC 未被选中时配置，保持至少 4 个 clk 沿后再选择；冷启动要求 rst_n 低保持至少 4 个运行时钟，让边界寄存器预装载（头注释 :3-5）；运行中逐项修改时序不支持。
- 独立 OOC（xc7z030ffg676-2、5 ns）综合到布局布线 473 LUT / 415 FF，WNS +1.723 ns / WHS +0.092 ns（以 `docs/rtl-rewrite-20261013.md` 记录为准）。

## wcis_stream_letterbox：独立补边模块

### 定位与接口

把已缩放好的 RGB888 valid/ready 像素流贴到更大画布：默认 640×360 内容到 640×640 画布、右/下补 `PAD_RGB=24'h727272`（114 灰）；参数含内容/画布尺寸、左/上 padding 与填充色，全部静态配置（`rtl/wcis_stream_letterbox.v:8-14`）。只补边：无 resize、无色序交换、无归一化、无对齐（头注释 :2）。上游契约：每帧恰好 CONTENT_W×CONTENT_H 个 row-major 像素，`s_valid && !s_ready` 期间数据保持稳定；禁止直连不可反压的 DVP 摄像头（头注释 :4-5）。

### 数据通路

画布游标 `x/y` 在 `m_valid && m_ready` 握手时推进，帧尾回零、`active` 拉低等下一帧第一个 `s_valid`（:42-51）。逐像素组合判断 `content`（:33-34），`m_data = content ? s_data : PAD_RGB`（:38）。

### 特色设计

1. valid/ready 加 SOF/EOL/EOF 同拍。`m_sof/m_eol/m_eof` 与像素同拍产生（:39-41）且反压、停顿时保持稳定（头注释 :6）；区别于厂商 ImageMake 的 `img_start`（与 FIFO 数据分离的跨时钟脉冲），两者不能接同一根线，接入须连同模型图、buffer 与框回映射整体设计（以 `docs/interface.md` 为准）。
2. 内容区才反压上游：`s_ready = content && m_ready`（:37），补边像素由模块自产、不占上游握手；`m_valid` 对补边像素恒为 1、对内容像素跟随 `s_valid`（:36），帧在第一个输入像素到达时自动启动（`started = active || s_valid`，:35）。
3. 几何参数 elaboration 守卫（content 不越画布、padding 不越界等，:52-57）。

### 关键参数

静态参数化；复位取消当前帧，上游须从下一完整帧重新开始；支持 1×1 与零 padding。

## wcis_sdi_monitor：SDI 被动诊断

### 定位与接口

挂在 VTC/选帧之前的真实 RX 流上（`case/rtl/display/frame_trans.sv:192-199`），被动统计锁定期间的帧/行/像素计数、最大行宽、帧高与 SDI 标志字（`rx_flags[11:0]`＝scan/rate/family/mode/lock），打包成 416 位 `words` 供 AXI-Lite 只读寄存器解码（`rtl/wcis_sdi_monitor.v:8-15`）。监测点在 VTC 之前，板内测试图不会计入真实输入计数。rx_clk（SDI 恢复时钟，允许长期停振）与 cfg_clk 异步。

### 数据通路

rx 域：`old_vs/old_de` 沿检测出帧/行边界（:44-46），累计 cycles/frames/lines/pixels；只在完整 VS 间隔（`in_frame`）上提交 width/height（:64-80）。快照请求被应答时，把 `{height,width,pixels,lines,frames,cycles,rx_flags}` 共 192 位整体锁入 `payload_hold`（:81-84）。cfg 域：快照寄存器 `snapshot`、`age`、`snapshot_seq` 与状态位（:88-116），拼成 `words` 输出（:117-125）。

### 特色设计

1. 10 ms toggle 快照。cfg 域每 `SAMPLE_CYCLES=500000`（50 MHz 下 10 ms）且管道空闲时发一次 toggle 请求（:110-114）；rx 域应答即锁 payload。快照是周期采样，不是事件中断。
2. 请求永不撤销、迟到应答不丢弃。源时钟停振也不清请求；仅在 `src_reset` 未释放时把 `ack_toggle` 清零（:54-55）；时钟恢复后的应答仍对应原请求（头注释 :2-3）。cfg 域用 `consumed_ack` 区分新到的 ACK 与复位残留（:94、:105-108），提交时 `snapshot_seq` 递增、`commit_tick` 记录、`age` 清零（:105-108）。
3. stale 判据内置硬件：`age` 饱和计数（:104），`fresh = ever_received && age < STALE_CYCLES`（STALE_CYCLES=5,000,000 即 100 ms，:122-123）；`pending` 位单独报请求未应答。软件规则：序号不变才算稳定快照，陈旧快照不得当作实时锁定。
4. 复位与同步器纪律：异步复位断言加两域本地两级释放（:17-21）；同步链无时钟使能、无中间逻辑（:26-27）。
5. 192 位 payload 靠先锁存后应答保证稳定，集成时须随附 payload max-delay/bus-skew 物理约束（头注释 :41-42）。

### 关键寄存器

`words` 打包（:118-125）：0x100 魂数 0x53444932（"SDI2"）、0x104 版本 1、0x108 状态位（ever_received/fresh/pending/MMCM locked/GT 复位释放）、0x10C 快照序号、0x110/0x114 commit_tick/age、0x118 rx_flags、0x11C-0x128 周期/帧/行/像素计数、0x12C {height,width}、0x130 CFG 频率。

## wcis_preview_csr_router：预览 CSR 路由

### 定位与接口

在既有 native 寄存器接口上内嵌一页预览管理寄存器，DDR/NPU 通路不触碰（头注释 `rtl/wcis_preview_csr_router.v:2`）。地址 `awaddr[17:8]==10'h022`（18 位 CustomOp 窗口内 0x2200 页）路由到 preview 侧，其余透传 legacy 侧（:13-14）；插入点在 `rtl/wcis_pl_jpeg_preview.v:36-45`。

### 数据通路

写路径组合分流：`awready/awvalid` 按 `write_preview` 选择去向（:16-18）；读路径单条在管（:19-21），响应按归属回送（:22-25）。

### 特色设计

单 outstanding 读加响应归属保持：`arvalid&&arready` 时锁存 `pending/owner_preview`（:26-32）；`rvalid/rdata` 按锁定的归属选择 preview 或 legacy（:22-23），`rready` 同样按归属分发（:24-25）。客户端背压（迟迟不给 rready）期间，响应归属不会被新的读请求改写，旧页读响应保持原属主。

### 关键参数

`arready` 在 pending 期间拉低（:19），管道里同时只有一条读。

## wcis_preview_registers：NTP1 管理页

### 定位与接口

0x2200 页内容：网络会话配置（session_id/MAC/IP/端口）、PHY 复位与 Clause22 MDIO 管理、链路与收发统计快照。复位默认网络关闭（`enable=0`、`phy_reset_n=0`，:38-43）；不暴露任何像素缓冲地址，预览走独立 FIFO（头注释 :2-3）。`TX_ONLY_SERDES` 参数切换单向发送形态（增加 next_hop_mac 配置，:72-73）。MDIO 由内嵌 `wcis_mdio_clause22` 执行（:24-28）。

### 数据通路

AXI-Lite 写配置（0x0c..0x64）、读回（0x00..0x64）；MDIO 命令字写 0x30、状态读 0x34（:67-70、:92）；net_clk 域统计经 167 位 `wcis_cdc_mailbox` 整体快照到 cfg 域（:30-36）。

### 特色设计

1. 使能前完整性检查加运行中写拒绝。写 0x04 使能位时校验 session_id/local_ip/destination_ip/local_mac/双端口/phy_reset_n 全部就绪且 MAC 非组播（`local_mac[40]=0`），TX_ONLY_SERDES 形态还要求显式 next_hop_mac；不满足则 `rejected_writes` 计数（:50-56）。enable=1 后其余配置写一律拒绝并计数（:57），配置集合在运行期不可变。
2. 统计原子快照：net_clk 域的 speed/clock_locked/四类错误标志与五类帧计数打包成 167 位，经单条 mailbox 整体过域、cfg 侧整批锁存（:32-36、:45），多位统计无撕裂。
3. MDIO 事务互锁：命令仅在 `command_valid && command_ready` 时接受；完成置 `mdio_complete`，busy/done/error/read_data 从 0x34 读回（:67-70、:92）。
4. 魂数与特性自描述：0x00 读 NTP1/NTP2（0x4e545031/32，:80）；0x5c 报特性位（bit0 显式下一跳、bit1 固定 1G 全双工、bit2 共享时钟 serializer，:101-103）；0x54/0x58 报 1920/1080（:99-100）。软件先验魔数与特性位再配置。

### 关键寄存器

0x00 魂数；0x04 enable；0x08 快照状态位；0x0c session_id；0x10/0x14 local_mac；0x18-0x28 IP/端口；0x2c rejected_writes；0x30 MDIO 命令；0x34 MDIO 状态；0x38 phy_reset_n；0x40-0x50 统计快照；0x5c 特性；0x60/0x64 next_hop_mac（仅 TX_ONLY_SERDES）。

## wcis_cdc_mailbox：单条目捆绑数据 mailbox

### 定位与接口

参数化 WIDTH 的一次一条数据过域通道，是全工程多位跨时钟的标准件：`s_clk` 域写入、`m_clk` 域读出，payload 保持到目的侧消费并回 ACK（头注释 `rtl/wcis_cdc_mailbox.v:2-4`）。

### 数据通路

s 域：`s_valid && s_ready` 时锁 `payload_hold` 并翻转 `request_toggle`（:22）；`s_ready = !s_reset[1] && request_toggle == ack_sync[1]`（:13）。m 域：`request_sync` 两级同步（:28），空闲（`!m_valid`）且有新请求时装载 `m_data/m_valid`（:29），`m_valid && m_ready` 消费后清 valid 并回 `ack_toggle`（:30）。

### 特色设计

1. 握手语义保证 payload 稳定：源在 ACK 返回前不改写 `payload_hold`；目的侧反压期间 `m_valid/m_data` 保持。一次只有一条在途。
2. 复位纪律：共享异步断言 reset，两域各自两级同步释放（`s_reset/m_reset`，:14-17）；两侧数据 always 块以本地释放信号作异步复位（:18-19、:25-26）——两域释放先后无关紧要，握手关系被复位强制归零，不会出现半条消息。
3. 集成契约：payload 总线须随附 max-delay/bus-skew 物理约束（头注释 :4）。

### 关键使用点

- 预览统计快照 167 位（`rtl/wcis_preview_registers.v:32`）。
- 预览配置 224 位（session/MAC/IP/端口原子过域，`rtl/wcis_pl_jpeg_preview.v:73-77`；disable 时以 `configuration_reset` 复位 mailbox 取消在途配置，:59）。
- face CustomOp 的读请求 32 位、读响应 544 位、写请求 608 位三条（`rtl/wcis_face_customop.v:155-165`）。

## wcis_status_sync：单比特状态同步

### 定位与接口

仅用于单比特电平状态跨时钟；生产者必须把事件保持为足够长的粘滞电平，payload 总线必须改用 mailbox/FIFO（头注释 `rtl/wcis_status_sync.v:1-2`）。

### 特色设计

两级 `ASYNC_REG` 且 `SHREG_EXTRACT="NO"` 的状态同步（:14-18），显式禁止 SRL 提取，保证物理上是两级触发器；复位走固化的 `sync_reset #(.N(3))` 三级异步置位、同步释放链（:11-13），使复位释放对本 clk 局部化。`m_status` 取第二级（:19）。

### 关键使用点

125 MHz MAC 欠载事件先在源域粘滞成电平（`underflow_seen`，`rtl/wcis_pl_jpeg_preview.v:100-105`），再经本模块进 150 MHz sticky 诊断寄存器（:106-108）；短脉冲不先展宽会漏记，这是模块契约的一部分。
