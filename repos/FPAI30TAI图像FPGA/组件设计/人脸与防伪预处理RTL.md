# 人脸与防伪预处理RTL

这一层把"像素级几何前处理"从 PS 搬进 PL：一条描述符执行成一帧 RGB888（检测画布或对齐人脸），防伪（PAD）裁图复用同一套采样核心，全部经厂商 CustomOp 的 512 位 PL-DDR 原生端口与 PS 交换原帧与结果。模块位于 `rtl/`，接入现场在 `case/rtl/ai7030_edif_top.v` 的 `U_adder_top` 位置。

分工契约：PS 保留五点矩阵求解、模型调用次序与结果解释；PL 只执行像素搬运、逆仿射、双线性插值、边界处理与握手状态机；NPU 跑检测与特征模型。PS 计算的 InsightFace 五点相似变换矩阵以有符号 Q16.16 六系数随描述符下发，PL 不求解矩阵。

## wcis_face_preprocess：人脸预处理描述符执行器

### 定位与接口

单条 ModelBackend 命令执行成一帧 RGB888 canvas，不含任何摄像头/模式策略（头注释 `rtl/wcis_face_preprocess.v:2`）。命令字段：frame_id、base_addr、pitch_bytes、rgb565、src/content/canvas 宽高、六个 Q16.16 逆仿射系数 m00..m12、replicate 与 border（:5-12）。输出 valid/ready 像素流带 m_sof/m_eol/m_eof，另向下游 `wcis_pixel_read_axi` 发起点读请求（rd_x/rd_y）。所有端口同一 `clk`，PS/AXI-Lite CDC 与缓冲区所有权是外部契约（头注释 :3）。支持两类几何描述：YuNet 全图等比缩放+右下黑色补边到 640×640；MobileFaceNet 由 PS 五点求相似变换后 PL 从同一原帧逆向采样出 112×112（以 `docs/face-pl-modelbackend-20261015.md` 为准）。

### 数据通路

命令 FSM 三段 `CMD_IDLE → CMD_CHECK → CMD_SEND`（:24），接受时把整个描述符（345 位 `geometry_hold`）一次锁存（:62-64）；`CMD_CHECK` 寄存存储合法性结果（:67），`CMD_SEND` 等采样器 ready 后交令并回到 IDLE（:68）。核心是两个子模块：`wcis_affine_sampler`（:72-83）与 `wcis_pixel_read_axi`（:84-92），前者发坐标、后者回像素。

### 特色设计

1. 描述符一次锁存，上游改写不影响已接受命令（`geometry_hold` + `base_addr/pitch_bytes/rgb565` 全部只在 accept 拍写入，:60-66）。
2. 校验分级流水，防长组合链：`storage_valid` 组合式（64 位 allocation_end 乘加、8 字节对齐、pitch 覆盖行宽、分配不越 4 GiB，:50-54）的结果先寄存一拍（`storage_valid_q`，:67）再门控采样器的使能，不在 100 MHz 一拍内串接"校验→高扇出门控"。校验失败时把 `cmd_src_w` 压成 0 令采样器报错拒绝，不发起任何 DDR 读（:74）。
3. 外部标签/错误语义在命令接受边界保持：`frame_id` 始终回锁存的 `held_frame_id`，命令处理阶段错误置 0、执行阶段透传采样器错误（:42-43）。
4. 每条命令仅增加两拍（CHECK/SEND），采样与搬运循环不加拍；两个新阶段均可被复位中止，未交给采样器的命令不发 AXI 请求也不出像素（以 `docs/pl-command-validation-20261022.md` 的 RTL 变更节为准）。

### 关键参数/时序

- 错误码与采样器共用：1 描述符无效、2 AXI 错误/缺 RLAST、3 非法状态；`done` 为一拍脉冲（以 `docs/face-pl-modelbackend-20261015.md` 描述符表为准）。
- 存储契约：base/pitch 须 8 字节对齐，pitch 至少容纳一行（rgb565 时 ×2、否则 ×4 字节），`base + pitch*height ≤ 4 GiB`。

## wcis_affine_sampler：逆仿射双线性采样核

### 定位与接口

ModelBackend 像素算子，不是应用/模型调度器（头注释 `rtl/wcis_affine_sampler.v:2`）。输入逆映射系数（输出坐标→原帧坐标）为有符号 Q16.16，几何上限 src 8192×8192、canvas 640×640（:50-54）；参考语义＝OpenCV remap INTER_LINEAR 的 1/32 像素插值网格，边界支持常量或复制；PS 端计算 InsightFace 五点变换（头注释 :3-5）。对读写两侧都是同步 valid/ready：读侧 `rd_valid/rd_x/rd_y` 请求邻点、`rsp_*` 收像素；写侧 `m_valid/m_rgb` 带 SOF/EOL/EOF（:20-26）。

### 数据通路

八态 FSM：`IDLE → COORD → NEIGHBOR →(REQUEST)→ RESPONSE → HORIZONTAL → VERTICAL → OUTPUT_PIXEL`（:28-29）。每输出像素：坐标舍入到 1/32 网格（`qx/qy` 与 5 位小数 `fx/fy`，:135-141）、取四个邻点（`neighbor 0..3` 逐一 `store_neighbor`，:88-98）、两通道水平插值（`h0/h1[3]`，:156-162）、垂直插值出 RGB（:163-167）、握手输出后按行/列增量推进坐标累加器（:168-184）。

### 特色设计

1. Q16.16 坐标 + 1/32 像素插值网格 + 半格取向正无穷舍入。`(sx + 48'sd1024) >>> 11` 完成"四舍五入到最近 1/32 像素"，对负坐标同样成立（:135-140 注释）；48 位累加器 `row_sx/row_sy/sx/sy` 防止变换映射出帧时回绕（:33-34）。行进仅用加法：列推进加 m00/m10、行推进加 m01/m11（:173-180），整帧无坐标乘法。
2. 零权重邻点不访存。`fx==0` 时右邻点、`fy==0` 时下邻点权重为零，直接存 0 跳过 DDR 读（`tap_needed`，:57、:146）；越界且非常量边界时邻点直接取 border（:147）。插值只在最终像素处 `+512` 再取整（`vertical` 函数，:79-87），中间水平级不引入舍入误差。
3. 五点对齐语义由矩阵表达：模块不感知"人脸"，`cmd_m00..m12` 即 SimilarityTransform 的逆矩阵；112×112 对齐与 640×640 检测画布是同一核的两种描述符。
4. 边界逐邻点判定而非整帧裁剪：`outside` 在舍入后的整数坐标上判（:45-47），常量边界填 `cmd_border`、复制边界把坐标钳到帧内再读（`clipped_x/y`，:48-49）。
5. NEIGHBOR 直发读请求的快路径：判定某邻点需要访存后直接在 NEIGHBOR 态置 `rd_valid`（:61），读端未就绪才转 REQUEST 并保持同样坐标与 VALID 直到接受（:59-60 注释、:148-151），每邻点省一个控制空拍（以 `docs/pl-reader-fastpath-20261022.md` 为准，该优化与 reader 优化合计使 960×540→640×640 仿真作业时间减 23.4%）。
6. 错误与反压纪律：几何非法在 IDLE 当拍拒绝（error=1，:116）；AXI 错误或单 beat 响应缺 RLAST 置 error=2 并终止（:152-155）；输出侧反压时状态保持、SOF/EOL/EOF 与像素同拍稳定（:66-68）。

### 关键参数/时序

- 插值算术显式 Unsigned 加宽：255×32×32 恰好 18 位（:70 注释），无符号乘法避免符号扩展误判。
- geometry_valid 守卫：src 1..8192、canvas 640×640、content≤canvas（:50-54），非法在发起任何 DDR 读之前拒绝。
- 独立 OOC 综合 1502→1585 LUT / 1075→1187 FF / 10 DSP / 0 BRAM（以 `docs/pl-reader-fastpath-20261022.md` 表格为准）。

## wcis_face_customop：CustomOp 接入封装（FAC1）

### 定位与接口

厂商 CustomOp 集成壳：保留原加法器寄存器页与操作，在 0x2000 页新增 FACE（`face_write/read = itf_ra_*addr[17:8]==10'h020`，:27-28）；读写数据与旧客户端共享同一条 512 位 PL-DDR 原生端口（头注释 :2-4）。GP 寄存器域 ra_clk 100 MHz、原生 DDR 域 clk 200 MHz。输出 `native_write_is_face` 供上层识别写事务归属（:18、:44）。

### 数据通路

三条路径：CSR（face 页寄存器读写）；native 读（采样器的 AXI 读请求经双行缓存聚合后走 itf_ar/r）；native 写（输出缓冲 512 位行经 mailbox 走 itf_aw）。读方向有 `read_hold/read_owner` 在反压时锁定归属（:83-84），写方向有 `write_hold/write_owner`（:81-82）；在读响应在途期间（`memory_read_busy`）不再放行新 AR（:69-73）。

### 特色设计

1. CustomOp 页路由与旧加法器共存：face 页命中时旧加法器的 aw/ar 被屏蔽（`itf_ra_awvalid && !face_write`，:52-53），读侧单条在管 `read_pending/read_face` 保持响应归属（:47-49、:231-244）；寄存器页布局 0x00 读 ID `0x46414331`（"FAC1"）、0x04 状态（busy/completed/rejected/error）、0x08/0x0C 完成帧号/像素数、0x10..0x48 描述符（:236-240）。
2. 双行全相联缓存桥接逐像素读与 512 位总线。两路 64 字节行 `line/second` 全相联（地址＝{addr[31:6],6'b0}），LRU 驱逐（`replace_second` 翻转），一次只一个在途读、无预取（:135-138 注释、:176-200）；双行恰好保住双线性采样的两行源数据，命中行按 `araddr[5:3]` 选 64 位 lane 移位出读数（:179、:181）。每次作业开始强制双行失效（`start` 清 line_valid/second_valid，:174），同物理地址换帧不残留旧数据。
3. 三条 `wcis_cdc_mailbox` 过 100/200 MHz 域：读请求 32 位、读响应 544 位（{rinfo,rdata}）、写请求 608 位（{addr,buffer,mask}）（:155-165），payload 保持到目的侧 ACK。
4. 27 位地址窗口内校验：源/输出范围乘、加、比拆三拍（`validate_state 1→2→3`，:215-229），输出按 64 字节对齐、与源分配不重叠、总窗 128 MiB；busy 期间描述符锁定，重复启动或改写置 rejected（:246-252）。
5. 输出按 512 位行累积提交：16 个 32 位像素（64 字节）或 EOF 凑满一行置 `output_pending`，经写 mailbox 提交（:254-264）；错误时已完成的部分缓冲不清零不提交（:265-271 注释"partial buffer on an error is intentionally not committed"），完成状态等最终写请求被 DDR 接口接受（`writer_finished && !output_pending && write_mail_ready`，:266-268）。
6. 乘/加/比分拍与 busy 锁定配合：校验路径按实际 100 MHz GP 时钟拆拍，不用松弛时序例外（:116-117 注释）。

### 关键寄存器/时序

- 描述符寄存器 `cfg[0..18]`：0x10 frame_id、0x14/0x18/0x1C base/pitch/output_base、0x20 src、0x24 content、0x28 canvas、0x2C replicate/rgb565、0x30 border、0x34..0x48 六系数（:121-127 的连线序）。
- 使能写 0x00 bit0=1 启动；错误经 `job_error` 上浮到 0x04（:265）。

## wcis_pixel_read_axi：原帧点读 AXI 客户端

### 定位与接口

只读 64 位 AXI 客户端，面向厂商 DDR/HP 互连边界：一次一条 8 字节对齐读、单行缓存、无预取（头注释 `rtl/wcis_pixel_read_axi.v:2-3`）。读侧坐标请求（s_x/s_y）、响应 RGB888；AXI 侧标准 AR/R 握手，arlen=0、arsize=3（8 字节，与厂商 aq_axi_master 同 beat 宽）、INCR（:54-56）。

### 数据通路

八态 FSM：`IDLE → ROW_OFFSET → ADD_OFFSET → CHECK_ADDRESS → ADDRESS → DATA →(DRAIN)→ RESPONSE`（:23-24）。地址＝base + y*pitch + x*bytes_per_pixel，行乘、加址、校验分拍（:87-102）；命中缓存直接解包（:97-101），未命中发单 beat 读并装缓存（:104-115）。

### 特色设计

1. 双层缓存标签与坐标快速路径。物理层：8 字节对齐字地址（`cache_addr`）命中则免 AXI 往返；逻辑层：成功的物理读同时建立 {base,pitch,format,y,word_x} 坐标标签（:32-45），同字内后续像素命中 `coordinate_hit` 时直接从 `cache_data` 解包，省掉重复的行乘、加址与地址校验状态（:29-31 注释、:83-85）。base/pitch 非 8 字节对齐的合法布局自动退回慢路径（:43-44 条件）。
2. 像素解包统一函数：小端 B,G,R,X 展开 8 位 RGB888；RGB565 走位复制扩展（高位复制补齐，非零填充，`unpack_pixel`，:58-67），并明确其精度损失须另测、不等价 RGB888 模型输入（头注释 :4-5）。
3. 地址校验先行：64 位溢出、对齐违例、pitch=0 在发 AR 之前拒绝（`invalid_address`，:48-50、:93-96）。
4. 异常响应排空：本应单 beat 的响应若缺 RLAST，转 DRAIN 态读到 RLAST 才释放 AXI ID（:112-116 注释、:114-116）；错误响应不建立有效缓存（:108 条件）。
5. 复位契约：AXI reset 须与互连共享，不得只复位本客户端而留下在途读；`clear_cache` 仅在两条命令之间合法（头注释 :6-7）。
6. 坐标先寄存再乘、行积先寄存再加址（:46-47 注释），采样器→乘法→比较不在同一拍。

### 关键参数

缓存一次一字（64 位），无容量/预取扩张；fastpath 收益依赖源格式与缩放轨迹（1080p 整数抽样场景几乎无收益，以 `docs/pl-reader-fastpath-20261022.md` 实测表为准）。

## wcis_native_write_commit：原生写提交桥

### 定位与接口

厂商原生 DDR 端口没有 B 响应，本模块以"读回校验"充当数据可见性回执：客户端每个带 `c_requires_verify` 的写，都由桥自动发起同地址读，逐字节比对使能掩码后才向客户端回 ack（头注释 `rtl/wcis_native_write_commit.v:2-4`）。参数 MAX_READS=1024、MAX_CYCLES=100,000,000（:6）。当前默认关闭，经 `wcis_recording_customop` 的 `VERIFY_NATIVE_WRITES` 参数选配（`rtl/wcis_recording_customop.v:35-53`）。

### 数据通路

五态：`ISSUE → READ → WAIT → ACK →(FAILED)`（:21）。ISSUE 放行写并锁存期望值/掩码/地址（:74-77）；READ/WAIT 发验证读并等待（:35-37、:58-62）；逐字节掩码比对（组合 `equal_bytes`，:47-51）全等进 ACK 放行客户端写完成（:78），不等则重读，超过 MAX_READS 或等待超 MAX_CYCLES 置 fault 进 FAILED（:65-72、:79-82）。

### 特色设计

1. 回执语义是"数据可见"而非伪造 AXI B 响应：ack 只在验证读逐字节等于写数据后给出（头注释 :4），软件侧 epoch/守卫仍须保留。
2. 故障不撤回、不替换：fault 后不 ack 客户端写、不允许新写覆盖；迟到的验证响应仍被消费（:42-44 注释、:44）；超时也不能撤回已发出的 AR（`grant_hold/grant_verify` 在反压期间锁定在途请求归属，:28-29、:58-61）。
3. 客户端直通模式：不带验证要求的写/读组合直通（:33-34、:35-38），非验证路径零额外拍。

### 关键计数器

`writes_visible/retry_reads/last_address` 三只读计数器（:19）供诊断区分"写可见慢"与"写不可见"。

## wcis_pad_preprocess：防伪 80×80 裁图预处理

### 定位与接口

MiniFASNet 裁图局部缩放适配器，不含任何活体/身份判定逻辑（头注释 `rtl/wcis_pad_preprocess.v:2`）。输入完整 BGRX 原帧描述符（frame_id/base/pitch/src_w/h）与上游 CropImage 的含端点 ROI（x,y,w,h），输出 80×80 像素流（:7-22）。PAD 模型契约：80×80、完整 8 位 BGR、FP32 0～255（以 `docs/face-pad-minifas-20261018.md` 为准）。

### 数据通路

复用 `wcis_affine_sampler` + `wcis_pixel_read_axi`：ROI 局部逆缩放系数构成对角仿射矩阵（scale_x/scale_y 与 offset_x/offset_y，:39-42），采样器 src 维度取 ROI 宽高（`valid_storage && valid_roi ? cmd_roi_w : 0`，:58）、content/canvas 固定 80（:59）、`cmd_replicate=1` 复制边界（:62）；读端坐标加 ROI 偏移回全帧（`s_x=rd_x+roi_x`，:70）。

### 特色设计

1. 112×112 对齐同一核的姊妹用法：80×80 输出由固定 content/canvas=80 表达，缩放比由 ROI 尺寸推出——半像素逆映射系数化成常数分母除法（`({roi_w,16'd0}+40)/80` 的 Q16.16 形式，:39-42），综合出常数电路，无变量除法器。
2. ROI 局部先夹边、再全帧平移：采样器看到的 src 是 ROI 尺寸，边界钳位发生在裁图局部坐标，之后读端才加 roi_x/roi_y（:53-54 注释）；若只把原仿射坐标整体偏移，小 ROI 采样会越界读到 ROI 外像素。奇数 x 裁图无需取偶对齐（以 `docs/face-pad-minifas-20261018.md` PL 裁图节为准）。
3. 与 face 链一致的安全网：base/pitch 8 字节对齐、pitch≥4×src_w、分配不越 4 GiB（:27-31）；ROI 含端点不越帧（:32-36）；命令握手锁存 base/pitch/roi 偏移，读缓存每命令清空（:46-52、:68）；Q5 插值与 cv2.resize 非逐位一致，部署前须量化输入与模型输出差异（头注释 :5-6）。

### 关键参数

固定输出 80×80；错误码/done/frame_id 语义与采样器一致；原帧在 done 前不可覆写由外部所有权契约保证。

## wcis_recording_customop：FAC1+JPG1 共享端口封装

### 定位与接口

在保留 FAC1 与旧加法器的 CSR 窗口上再并入 JPG1（`jw/jr = itf_ra_*addr[17:8]==10'h021`，:55-56），页 0x2100（头注释 :2）。两个客户端（`wcis_face_customop` face、`wcis_jpeg_customop` jpeg）共享同一条 512 位原生 DDR 端口与同一条 CSR 读响应通道；`FAIR_ARBITRATION` 与 `VERIFY_NATIVE_WRITES` 两个参数分别控制仲裁与写回执（:4-6）。

### 数据通路

CSR：face/jpeg 两页各自 awready，读侧 `csr_pending/csr_jpeg` 单条在管保持响应归属（:74-82）。native 写/读：`choose_wr/choose_rd` 二选一选主（:69-72、:104-115）；读在途（`rd_busy/rd_jpeg`）期间不放新 AR，读响应按归属分发 `client_rready`（:115、:125-128）。写无在途跟踪（fire-and-forget），选主在握手沿解决。

### 特色设计

1. 反压时冻结归属的公平仲裁：双方同时请求时按 `wr_next/rd_next` 交替放行（:69-72）；握手未完成（valid 且未 ready）时 `wr_hold/rd_hold` 锁定 owner，仲裁公平性不对 DDR 停顿强加周期界（:67-68 注释）。
2. CSR 归属与 native 归属分离管理：读响应归属 `csr_jpeg` 与数据读归属 `rd_jpeg` 是两套独立状态，互不干扰。
3. 写回执桥以 generate 参数内嵌：`VERIFY_NATIVE_WRITES=1` 时 face/JPG 全部 native 写经 `wcis_native_write_commit`，默认旁路直连（:35-53）；开关按"独立构建位流通过原生端口/DDR 与整板验收后再默认启用"的纪律保持关闭。
4. 双客户端并发可验证：冻结源码上 FAC1 与 JPG1 双帧并发回归（RGB565/BGRX × 正常/慢速 DDR）通过，逐像素黄金比对与独立 JPEG 解码系数对照（以 `docs/pl-command-validation-20261022.md` 冻结候选回归节为准）。

### 关键参数

JPEG_WIDTH=1920、JPEG_HEIGHT=1080、JPEG_QUALITY=75 为 JPG1 侧默认几何（:4-6）；两个客户端的 CSR 页偏移 0x2000（FACE）/0x2100（JPG1）落在 gp0_manager 以 ASP=18 划出的 256 KiB user_op 窗口内（以 `docs/face-pl-integration-20261015.md` 寄存器节为准）。
