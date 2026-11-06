# JPEG与MJPEG核

本页只讲设计与实现：一个固定版本的 mjpegzero 基线 JPEG（4:2:2）编码核（`repos/FPAI30TAI图像FPGA/rtl/vendor/mjpegzero/rtl/`），加上四层自研适配——输出缓冲与命令适配（`rtl/wcis_jpeg_compressor.v`）、DDR 原生帧的 CustomOp 接入（`rtl/wcis_jpeg_customop.v`）、SDI 无 ready 流的取流桥（`rtl/wcis_sdi_jpeg_stream.v`）、纯 PL 预览的板级封装（`rtl/wcis_pl_jpeg_preview.v`）。

编码算法与 JPEG 语法全部在 vendor 核内（`sources.json` 固定 commit `90bc0c46d2c2c4bda1020113f306a5f17dcc5f2f`，Apache-2.0 附 Commons Clause v1.0，`modifications: []`，即 vendor RTL 未改）；自研部分只解决四件事：帧边界（一条命令恰好拥有一帧像素）、反压（编码器字节输出没有 ready）、跨域（GP/HP/摄像头/网络四个时钟域）、寻址（DDR 与寄存器页）。

三条使用入口与各自的帧来源：

| 入口 | 顶层 | 上游 | 帧来源 | 输出去向 |
|---|---|---|---|---|
| JPG1 CustomOp | `wcis_jpeg_customop` | PS 经 512 位 CustomOp 总线 | PL-DDR 里的整帧（RGB565 或 BGRX8） | 写回 PL-DDR |
| SDI 流式 | `wcis_sdi_jpeg_stream` | SDI 摄像头 RGB24（无 ready） | 摄像头逐帧 | 下游 ready/valid 字节流 |
| 纯 PL 预览 | `wcis_pl_jpeg_preview` | 上面两者 + 网口 | 摄像头逐帧 | UDP/RGMII 直发 |

## mjpegzero 编码流水（顶层）

### 定位与接口

`rtl/vendor/mjpegzero/rtl/mjpegzero_enc_top.v` 是整个编码器的唯一顶层。三个接口面：

- 视频输入 AXI4-Stream 从口：`s_axis_vid_tdata/tvalid/tready/tlast/tuser`，宽度由 `RGB_INPUT` 派生（`VID_DATA_W`，24 位 RGB 或 16 位 YUYV），`tlast` 为行尾、`tuser` 为帧首（`mjpegzero_enc_top.v:36-48`）。
- JPEG 输出 AXI4-Stream 主口：8 位 `m_axis_jpg_tdata` + `tvalid` + `tlast`，**没有 tready**，注释明确写 "no backpressure"（`mjpegzero_enc_top.v:50-53`）。
- AXI4-Lite 从口：5 位地址、6 个寄存器（`mjpegzero_enc_top.v:55-72`），寄存器映射见 `rtl/vendor/mjpegzero/rtl/axi4_lite_regs.v:8-14`：`0x00` CTRL（bit0 enable、bit1 soft_reset）、`0x04` STATUS（bit0 busy、bit1 frame_done，W1C）、`0x08` FRAME_CNT、`0x0C` QUALITY、`0x10` RESTART、`0x14` FRAME_SIZE。

参数面决定资源与画质：`LITE_MODE`（1 = 综合期固定质量，不走运行时质量 FSM）、`LITE_QUALITY`、`IMG_WIDTH`/`IMG_HEIGHT`、`RGB_INPUT`、`HUFF_BANKS`（2/4/8，Huffman 输入环深度 = 在飞块上限）、`EXIF_ENABLE` 与三个 EXIF 分辨率参数（`mjpegzero_enc_top.v:28-38`）。顶层 `initial` 块做参数合法性硬检查：宽必须是 16 的倍数、高必须是 8 的倍数、质量 1..100（`mjpegzero_enc_top.v:75-96`），否则 `$finish`。

### 数据通路

流水线顺序为 Input Buffer → 2D DCT → Quantizer → Zigzag → Huffman → Bitstream Packer → JFIF Writer（`mjpegzero_enc_top.v:15-24`）。逐级连接在 `mjpegzero_enc_top.v:519-671`：

1. `input_buffer` 把 YUYV 拆成 Y/Cb/Cr 三块 8 行缓冲，按 MCU 顺序吐 8×8 块（`u_input_buffer`，`mjpegzero_enc_top.v:520-541`）。
2. 电平移位：无符号 0..255 转有符号 −128..127，`$signed({4'b0, ibuf_blk_data}) - 12'sd128`（`mjpegzero_enc_top.v:130`）。
3. `dct_2d` 输出 16 位有符号系数（`mjpegzero_enc_top.v:544-553`）。
4. `quantizer` 按分量选亮度/色度表做量化（`mjpegzero_enc_top.v:556-578`）。
5. `zigzag_reorder` 重排为锯齿序（`mjpegzero_enc_top.v:581-590`）。
6. `huffman_encoder` 输出变长码字 `out_bits`/`out_len`（`mjpegzero_enc_top.v:593-623`）。
7. `bitstream_packer` 拼字节、做 0xFF 填充与 RST 标记（`mjpegzero_enc_top.v:626-642`）。
8. `jfif_writer` 在前面插 SOI/APP0/DQT/SOF0/DRI/DHT/SOS、在后面补 EOI，并复用 `m_axis_jpg_*`（`mjpegzero_enc_top.v:645-671`）。

`RGB_INPUT != 0` 时输入支路先过 `rgb_to_ycbcr`，把 24 位 RGB 变成 16 位 YUYV 再进 input buffer（`mjpegzero_enc_top.v:431-451`）；`ENABLE=0` 时 `s_axis_vid_tready` 被拉低，是"停流"而不是"收下再丢"（`mjpegzero_enc_top.v:436`、`mjpegzero_enc_top.v:454`）。

### 特色设计

**分量 ID 用影子 FIFO 而不是固定延迟**。DCT/量化/zigzag 的延迟随块内容变化，用常数打拍会错位。顶层为量化器与 Huffman 各建一条 2 位宽的 comp_id 影子队列：写端在 `ibuf_blk_valid && ibuf_blk_sob` 入队，读端分别在 `dct_out_valid && dct_out_sof`（量化器用）和 `zz_out_valid && zz_out_sob`（Huffman 用）出队（`mjpegzero_enc_top.v:191-231`）。队深 4 与 8，正好覆盖对应级数的最多块数在飞。这样"哪个块属于 Y0/Y1/Cb/Cr"永远跟着数据走，与流水级数解耦。

**块粒度准入 + 在飞块数上限**。准入信号是 `ibuf_blk_start = ctrl_enable && (fstate == F_RUN) && jfif_headers_done && (pipeline_depth < HUFF_BANKS_CAP)`（`mjpegzero_enc_top.v:419-420`），`pipeline_depth` 只在"块真正进入 DCT"时加、在"Huffman EOB 被接收"时减（`mjpegzero_enc_top.v:397-411`）。上限刻意等于 Huffman 输入环深度，因为 zigzag 无法反压 Huffman——环一旦溢出就丢系数。注释写清了这条因果链（`mjpegzero_enc_top.v:384-392`、`mjpegzero_enc_top.v:413-417`），并在 `HUFF_BANKS` 非 2/4/8 时用 `generate` 实例化一个不存在的模块名来在综合期硬失败（`mjpegzero_enc_top.v:388-392`）。

**四态帧机 + 每帧控制快照**。`F_IDLE` 等"有条带已缓冲且使能"，同时把 `frame_quality`/`frame_restart` 锁存（`mjpegzero_enc_top.v:296-303`）——这样帧中途写 QUALITY 寄存器不会让量化表和已经发出的 DQT 段脱节。`F_QWAIT` 等 `q_tables_busy` 落下（量化表重建完成）才拉 `frame_start_pulse`（`mjpegzero_enc_top.v:304-312`）。`F_RUN` 按**块计数**准入恰好 `TOTAL_BLOCKS` 块，而不是靠 tlast（`mjpegzero_enc_top.v:313-319`）。`F_DRAIN` 先等 `frame_done_pulse`，再等 `jfif_headers_done` 落下（即 EOI 已发、writer 回到 idle），才回 `F_IDLE`（`mjpegzero_enc_top.v:320-329`）。

块总数按 4:2:2 MCU 算：`TOTAL_BLOCKS = (IMG_WIDTH/16) * (IMG_HEIGHT/8) * 4`，每 MCU 两块 Y 加一块 Cb、一块 Cr（`mjpegzero_enc_top.v:247`）。按块计数而非按输入帧尾，使"下一帧条带已经缓冲"时也能保证每张 JPEG 结构完整（`mjpegzero_enc_top.v:242-246`）。

**EOB 计数必须带反压条件**。完成块计数写成 `huff_out_eob && huff_out_valid && huff_bp_ready`（`mjpegzero_enc_top.v:339`）。因为 Huffman 在等 packer 排空时会把 `out_valid/out_eob` 保持多拍；少了 `huff_bp_ready` 就会每拍加一次，帧提前结束、packer 提前 flush。这条约束在注释里写成了"CRITICAL"（`mjpegzero_enc_top.v:333-338`）。

**DC 预测器按帧复位，但用帧尾而不是帧首**。Huffman 的 `restart` 输入接 `restart_trigger || frame_done_pulse`（`mjpegzero_enc_top.v:611`）。用 `frame_done_pulse` 的理由：它对齐在 Huffman 自己的最后一块 EOB 之后、下一帧首块之前；`frame_start_pulse` 在 8 行缓冲刚满时就发了，可能撞上还没排空的前一帧（`mjpegzero_enc_top.v:599-610`）。RST 标记通路仍只由 `restart_trigger` 驱动，所以这个复位不会额外插 RST。

**帧字节数在输出侧统计**。`m_axis_jpg_tvalid` 驱动一个计数器，`tlast` 那拍把 `jpg_byte_cnt + 1` 写进 `last_frame_size` 并清零（`mjpegzero_enc_top.v:465-480`），供 `FRAME_SIZE`（`0x14`）读。

**寄存器面的两处细节**（`axi4_lite_regs.v`）：AW 与 W 各自独立握手、各自锁存，两者都到手才写、才回 B，B 未完成前不再收新 AW/W（`axi4_lite_regs.v:72-151`）；`STATUS[1]` 是 W1C，但同拍新到的 `frame_done` 优先，写 1 清不掉刚发生的事件（`axi4_lite_regs.v:124-135`）。`LITE_MODE=1` 时 QUALITY 写入被忽略，寄存器读回仍反映默认值（`axi4_lite_regs.v:136-137`）。

### 关键参数与时序

| 参数 | 值/含义 | 依据 |
|---|---|---|
| `LITE_MODE` | 本项目用 1（综合期固定质量） | `wcis_jpeg_compressor.v:62` |
| `LITE_QUALITY` | 适配器 `QUALITY`，默认 75 | `wcis_jpeg_compressor.v:9`、`wcis_jpeg_compressor.v:62` |
| `TOTAL_BLOCKS` | `(W/16)*(H/8)*4`，1080p 为 120×135×4 = 64800 块 | `mjpegzero_enc_top.v:247` |
| 流水延迟 | DCT 约 24 拍到首出（注释口径） | `dct_2d.v:17` |
| 吞吐 | 每块 64 输入拍，块内 1 样本/拍 | `dct_2d.v:18`、`input_buffer.v:42` |
| 输出 | 8 位、无 ready；`tlast` 与 EOI 末字节同拍 | `mjpegzero_enc_top.v:50-53`、`jfif_writer.v:1181-1186` |

## 输入缓冲与颜色空间转换

### 定位与接口

三个 vendor 模块组成编码器的"入口"：

- `rtl/vendor/mjpegzero/rtl/input_buffer.v`：YUYV 16 位流 → 8×8 块样本流。输出侧 `blk_valid/blk_data/blk_sof/blk_sob/blk_comp` 与 `blk_ready/blk_start` 握手，另给 `lines_done`（8 行写满脉冲）和 `blk_avail`（有条带可发）（`input_buffer.v:34-53`）。
- `rtl/vendor/mjpegzero/rtl/rgb_to_ycbcr.v`：24 位 RGB → 16 位 YUYV，AXI4-Stream 两端（`rgb_to_ycbcr.v:33-46`）。
- `rtl/vendor/mjpegzero/rtl/bram_sdp.v`：行为级简单双口 RAM，两块 4096 深分块、2 拍读延迟（`bram_sdp.v:31-36`、`bram_sdp.v:76-84`）。

### 数据通路

`rgb_to_ycbcr` 的定点系数按 2^16 缩放写死在乘加里（`rgb_to_ycbcr.v:16-19`、`rgb_to_ycbcr.v:92-106`），三级流水：打输入并取 R/G/B → 乘加（落 DSP48）→ 移位、限幅、按奇偶像素打包成 `{Cb,Y0}` / `{Cr,Y1}`（`rgb_to_ycbcr.v:57-154`）。色度不做水平平均，直接取每个像素自身的 Cb/Cr，即水平 4:2:2（`rgb_to_ycbcr.v:24`）。

`input_buffer` 的写侧按 (bank, line, x) 算地址：Y 每行 `IMG_WIDTH` 个样本，Cb/Cr 每行 `IMG_WIDTH/2`，偶数像素写 Cb、奇数像素写 Cr（`input_buffer.v:219-250`）。读侧按 MCU 顺序走 4 个分量块（Y 左、Y 右、Cb、Cr），每个块 64 样本，列快、行慢（`input_buffer.v:361-406`）。

### 特色设计

**双 bank ping-pong，写侧永不等读侧收完**。三块存储都是 `2*BANK_SIZE` 深，`wr_bank` 与 `rd_bank` 互斥时写侧就绪：`s_axis_tready = (wr_bank != rd_bank) || !rd_active`（`input_buffer.v:160`）。每写满 8 行翻一次 bank（`input_buffer.v:260-266`）。帧首不清 bank——`px_x/px_line/px_phase` 在 `wr_sof` 那拍被强制归零（`input_buffer.v:168-173`），但 bank 选择继续沿用上一帧的 ping-pong 位置，所以新帧不会覆盖上一帧还在读出的最后一个条带（`input_buffer.v:164-167`）。

**一拍宽的 lines_done 会被锁存**。写侧完成一个条带只发一拍脉冲；若读侧正在 `RD_READ`，这一拍会丢，读侧就永久停住。所以读侧把"脉冲 + 那个 bank + 是否帧首条带"整体存进 `lines_done_pending/rd_bank_pending/rd_first_pending`（`input_buffer.v:139-141`、`input_buffer.v:326-330`、`input_buffer.v:334-337`）。

**三级输出流水对齐 BRAM 的 2 拍读延迟**。地址 → (BRAM 阵列 + DOB_REG) → 输出多路选择，共三级寄存器；`blk_data` 在第三级按 `out_comp_d2` 选 Y/Cb/Cr 的 `rdata`（`input_buffer.v:415-462`）。`blk_sob`/`blk_sof`/`blk_comp` 与 `blk_valid` 一起走同样的打拍链，所以块首标志与首样本严格对齐。

**准入只在块边界判定**。`rd_issue = blk_ready && (!rd_blk_first || blk_start)`（`input_buffer.v:298-299`）。一旦某块的第一个样本被放行，后续 63 个样本不再看 `blk_start`，块不会被切成半块——这正对上层的 `pipeline_depth` 上限模型。

**计数器宽度跟着 `IMG_WIDTH` 走**。`X_W = $clog2(IMG_WIDTH)`、`COL_W = $clog2(MCU_COLS)`，末值用 `X_LAST_I[X_W-1:0]` 截位比较（`input_buffer.v:70-78`），避免固定位宽在更大分辨率下回绕。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| Y bank | `8*IMG_WIDTH`，双 bank | `input_buffer.v:81`、`input_buffer.v:114-117` |
| Cb/Cr bank | `8*(IMG_WIDTH/2)`，双 bank | `input_buffer.v:82-83` |
| 读延迟 | 2 拍（阵列 + 输出寄存器） | `bram_sdp.v:8-11` |
| MCU 构成 | Y0、Y1、Cb、Cr 各 8×8（H=2,V=1） | `input_buffer.v:19-24` |
| YCbCr 系数 | 19595/38470/7471、−11056/−21712/32768、32768/−27440/−5328（2^16） | `rgb_to_ycbcr.v:17-19` |
| 转换流水 | 3 级；`s_axis_tready` 取 `m_axis_tready` 与 `!m_axis_tvalid` 的逻辑或 | `rgb_to_ycbcr.v:49`、`rgb_to_ycbcr.v:26` |

## DCT 与量化

### 定位与接口

- `rtl/vendor/mjpegzero/rtl/dct_1d.v`：8 点一维正 DCT。输入 12 位有符号、串行 8 样本，输出 16 位有符号、串行 8 系数（`dct_1d.v:21-36`）。
- `rtl/vendor/mjpegzero/rtl/dct_2d.v`：行列分解的 8×8 二维 DCT，两端都是 1 样本/拍、行主序，`in_sof`/`out_sof` 标块首（`dct_2d.v:21-34`）。
- `rtl/vendor/mjpegzero/rtl/quantizer.v`：按分量选表做量化，带质量缩放与 Q 表读口（`quantizer.v:30-63`）。

### 数据通路

`dct_1d` 走的是"系数 ROM 矩阵乘 + 加法树"的定点实现：`cos_rom` 是 8×8、13 位有符号，值按 `round(alpha(k)*cos((2n+1)k*pi/16)*4096)` 预先算好（`dct_1d.v:84-114`）。每拍算一个输出系数 k，8 个乘积分四对相加、再两级合并，最后 `(sum + 2048) >>> 12` 定点还原并舍入（`dct_1d.v:156-226`）。位宽按最坏情况推：12×13 = 25 位乘积，8 项和 28 位，与注释一致（`dct_1d.v:126-133`）。

`dct_2d` 三步：行 DCT → 转置 → 列 DCT（`dct_2d.v:8-19`）。行级输出按行主序写进 `tbuf0/tbuf1`，读侧按 `{col,row}` 换址实现转置（`dct_2d.v:95-149`）。列级输出是列主序，进 `obuf0/obuf1` 后再按 `{cnt[2:0],cnt[5:3]}` 换址还原成行主序，同时用 `out_cnt` 生成 `out_sof`（`dct_2d.v:212-299`）。

`quantizer` 不做除法：用"乘倒数再右移"。`Q[i] = (DCT[i] * recip[i] + round) >> 16`（`quantizer.v:9`），四级流水：读倒数并登记输入 → 取绝对值 + 登记倒数（多一级为 150 MHz 时序）→ DSP48 相乘 → 移位、加 32768 舍入、按符号还原（`quantizer.v:581-693`）。

### 特色设计

**两个转置缓冲各自冻结选择位**。`dct_2d` 的输出转置用 `obuf_rd_sel <= ~obuf_wr_sel` 在块完成那拍锁定读缓冲（`dct_2d.v:280-285`）；输入侧的 `tbuf_rd_sel` 同理（`dct_2d.v:167-172`）。原因是写侧与读侧可能只差一拍，用实时选择位会在块尾取到下一块的数据。

**"块完成"写在读逻辑之后**，让 `rd_active<=1` 在同拍冲突时压过 `rd_active<=0`（`dct_2d.v:139-141`、`dct_2d.v:163-172`），保证背靠背块不丢。

**列级输入做饱和截位**：16 位中间结果截到 12 位再进第二个 `dct_1d`，超界夹到 ±2047/−2048（`dct_2d.v:190-194`）。

**量化器的表重建是显式状态机**，不是组合重算。`UPD_LOAD → UPD_SCALE → UPD_ADD → UPD_DIV → UPD_RECIP` 每项 5 拍，先亮度 64 项再色度 64 项（`quantizer.v:306-382`）。`tables_busy = (upd_state != UPD_IDLE) || (quality != last_quality)`（`quantizer.v:322`）就是顶层 `F_QWAIT` 等的那个信号。缩放公式：`Q>=50 → 200-2Q`，`Q<50 → floor(5000/Q)`（`quantizer.v:131-190`），`scaled_q = max(1, (base*scale+50)/100)`，倒数 `recip = round(65536/q)`（ reciprocal LUT 注释在 `quantizer.v:191-192`，取值在 `quantizer.v:194-201`）。

**除以 100 用精确定点乘**：`(n * 41944) >> 22` 在 n < 43690 范围内精确，且先把 n 饱和到 25600（因为再大商必 ≥256，反正要夹到 255）（`quantizer.v:289-304`、`quantizer.v:349-357`）。这条写法保证 Q<50 的表与 IJG 一致，注释给出了反例（`quantizer.v:291-294`）。

**LITE 模式把表在综合期算完**。`LITE_MODE=1` 时没有 UPD 状态机、没有基础表 ROM、没有倒数 LUT，`tables_busy` 恒 0（`quantizer.v:397-398`）；缩放与倒数为 128 行（亮度 64 + 色度 64）**完全展开**的 `initial` 赋值（`quantizer.v:406-553`），注释说明展开是为了绕开"Vivado 在 initial 块里无法求值变量下标寄存器数组读"（`quantizer.v:418-419`）。本项目适配器一律 `LITE_MODE=1`，所以编码期不存在表重建等待。

**Q 表另开一个读口给 JFIF writer**：`qt_rd_addr/qt_rd_is_chroma → qt_rd_data`，一拍寄存（`quantizer.v:555-563`），让 DQT 段可以按当前实际表输出。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| 余弦定点 | 2^12（4096），13 位有符号 | `dct_1d.v:79-87` |
| 1D 延迟 | 末样本到首输出 3 拍 | `dct_1d.v:16` |
| 2D 延迟 | 首入到首出约 24 拍 | `dct_2d.v:17` |
| 量化流水 | 4 级，乘法在 P3 | `quantizer.v:21-25` |
| 表重建 | 每项 5 拍 × 128 项 | `quantizer.v:309-315` |
| 倒数 | `round(65536/q)`，q=1 时取 65535 | `quantizer.v:191-192`、`quantizer.v:421` |
| 表重建拍数 | 每项 5 拍 × 128 项 | `quantizer.v:309-315` |
| LITE 表 | 综合期展开赋值，128 行 | `quantizer.v:397-553` |

## 熵编码

### 定位与接口

- `rtl/vendor/mjpegzero/rtl/zigzag_reorder.v`：64 系数栅格序 → 锯齿序，1/拍，双缓冲（`zigzag_reorder.v:18-31`）。
- `rtl/vendor/mjpegzero/rtl/huffman_encoder.v`：锯齿序系数 → 变长码字。输出 `out_bits[31:0]`（码字 MSB 对齐，后面紧跟数值位）、`out_len[5:0]`、`out_sob`、`out_eob`，并有 `out_ready` 反压（`huffman_encoder.v:22-42`）。

### 数据通路

`zigzag_reorder` 写侧按 `zigzag_pos[wr_cnt]` 落址（`zigzag_reorder.v:37-59`、`zigzag_reorder.v:80-93`），读侧顺序读出（`zigzag_reorder.v:120-138`）。

`huffman_encoder` 分两段：**输入环**（`coeff_buf[0:NB*64-1]`，按 bank 存整块，写入时同步积累"非零图" `bank_nz` 与 `bank_any`，`huffman_encoder.v:485-554`）与**码流水**（issue → S2 取值/DC 差分/零游程 → S3 绝对值+类别 → S4 查表+数值位 → 输出寄存器，共 5 级，`huffman_encoder.v:556-572`）。控制器在块内只遍历非零 AC：`rem` 位图 + `prefix_or` 找最低置位（`huffman_encoder.v:633-642`），零系数不占拍。

### 特色设计

**零系数不花时间，靠位图而不是逐项扫描**。`rem_below = prefix_or(rem64) << 1` 得到"比我低的位有没有置"，`rem64 & ~rem_below` 即最低置位的一位独热，再用 `onehot_idx`（纯 OR 树，无优先链）换成下标（`huffman_encoder.v:455-479`、`huffman_encoder.v:633-638`）。清位用 `rem_clr = rem64 & rem_below`，等价于 `x & (x-1)`，不带进位链（`huffman_encoder.v:640-642`）。`prefix_or` 写成 6 次移位或（log 深度），明确为了把最低位逻辑从 64 位进位链上挪开（`huffman_encoder.v:466-479`）。

**超过 15 个零要拆 ZRL**。S2 判 `s2_run[5:4] != 0` 就发一个 ZRL 码（`huffman_encoder.v:628-631`、`huffman_encoder.v:745-749`），并让控制器停一拍——因为 ZRL 多占一个输出槽。

**三路 DC 预测器 + 两处复位源**。`prev_dc_y/cb/cr` 分开存（`huffman_encoder.v:589-591`），按 `blk_comp_id` 选择（`huffman_encoder.v:645-646`、`huffman_encoder.v:753-760`）。`C_IDLE` 里同时看"锁存的 `restart_pending`"和"当拍到达的 `restart`"（`huffman_encoder.v:689-694`）：帧中 RST 触发与控制器进入 `C_IDLE` 是同拍事件，只等锁存就会漏掉，下一个 MCU 的 DC 就会按旧预测器编码，与解码器（在 RSTn 处复位）失步。

**块与块不重叠**。只有 `C_WAIT` 收到"EOB 码被接收"才 `rd_count++` 回 `C_IDLE`（`huffman_encoder.v:731-738`），所以 DC 复位一定落在上一块末、下一块首之前；下一块的第一个码也比 EOB 晚 ≥2 拍到达 packer，packer 已看到 `in_restart`（`huffman_encoder.v:568-572`）。

**整条码流水一起走 `adv`**：`adv = !out_valid || out_ready`（`huffman_encoder.v:626`），输出寄存器空或下游接收时全流水推进一拍，天然把反压传回控制器。

**码字与数值位在一次拼接里合成**：`out_bits = {s5_code,16'd0} | ({21'd0,s5_vbits} << vshift)`，`vshift = 32 - s5_len - s5_cat`；负数的数值位按 `raw + (1<<cat) - 1` 取反（`huffman_encoder.v:789-820`）。所以下游 packer 只需按 `out_len` 左对齐取位，不必知道是 DC 还是 AC。

**Huffman 表用 function 而不是寄存器 ROM**：DC 两张、AC 两张全部写成组合 `case`（`huffman_encoder.v:48-431`），注释点明这是为了避开"Vivado initial 块初始化寄存器数组导致 ROM 内容损坏"（`huffman_encoder.v:87-89`）。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| `HUFF_BANKS` | 2/4/8，本项目顶层默认 8 | `mjpegzero_enc_top.v:37` |
| 输入环容量 | `NB*64` 个 16 位系数，`ram_style=distributed` | `huffman_encoder.v:500` |
| 码流水 | 5 级，每拍一个码 | `huffman_encoder.v:565-566` |
| 单码最大位宽 | 16 位码 + 11 位数值 = 27 位 | `bitstream_packer.v:63-65` |
| 类别 | 由系数幅值的最高置位给出，0..11 | `huffman_encoder.v:435-451` |

## 码流打包与文件封装

### 定位与接口

- `rtl/vendor/mjpegzero/rtl/bitstream_packer.v`：变长码 → 字节流。输入 `in_bits/in_len` + `in_flush/in_restart`，输出 `out_data/out_valid/out_last/out_ready`，并给 `bp_ready` 回压 Huffman（`bitstream_packer.v:23-39`）。
- `rtl/vendor/mjpegzero/rtl/jfif_writer.v`：把头部字节与扫描数据多路复用到同一输出 AXI4-Stream，帧尾补 EOI（`jfif_writer.v:21-61`）。`headers_done` 是"可以灌扫描数据"的许可（`jfif_writer.v:60`）。

### 数据通路

`bitstream_packer` 用 64 位累加器 + 位计数：新码按 `bit_cnt` 右移后 OR 进 `bit_buf`，取 `bit_buf[63:56]` 出字节，`bit_cnt` 相应加减（`bitstream_packer.v:66-123`）。状态机 7 态：`S_NORMAL`、`S_RST_PAD`、`S_RST_DRAIN`、`S_RST_FF`、`S_RST_MARKER`、`S_FLUSH_PAD`、`S_FLUSH_LAST`（`bitstream_packer.v:52-59`）。

`jfif_writer` 有两套实现，由 `LITE_MODE` 选择：

- `LITE_MODE=0`：14 态 FSM，DQT 段**逐字节从量化器读当前表**（`jfif_writer.v:411-426`、`jfif_writer.v:485-527`）。
- `LITE_MODE=1`：一套 623 字节的固定头部 ROM（`jfif_writer.v:15`），FSM 简化为 `SL_IDLE → SL_HDR_PRE(0..176) → [SL_DRI] → SL_HDR_POST(177..622) → SL_SCAN_DATA → SL_EOI_0 → SL_EOI_1 → SL_DONE`（`jfif_writer.v:1052-1076`、`jfif_writer.v:1086-1196`）。

### 特色设计

**`bp_ready` 就是"这一拍真的收下了这个码"**。它写成 `state == S_NORMAL && bit_cnt <= 32`（`bitstream_packer.v:66`）。因为 `bit_cnt <= 32` 时一个最多 27 位的码必然装得进 64 位累加器，而且 `merged` 是在"同拍排空一个字节"的前提下算的（新码从 ≥8 位处开始写，不碰 `bit_buf[63:56]`），所以接受、排字节、加位计数可以在同一拍完成（`bitstream_packer.v:61-73`）。这条把"反压"从"要等有空位"变成"本拍有无空位"，省掉一整拍。

**0xFF 填充是一等状态而不是补丁**。每排出一个字节，若它是 `8'hFF` 就置 `need_stuff`，下一拍先出 `0x00`（`bitstream_packer.v:111-119`、`bitstream_packer.v:104-110`）。RST 与 FLUSH 的排空路径都各自检查 `need_stuff` 并重复这套逻辑，且 `S_RST_FF` 出 `0xFF` 时显式清 `need_stuff`——因为下一个字节是标记而不是填充（`bitstream_packer.v:202-210`）。

**重启标记前先把残余位补成整字节**。`S_RST_PAD` 只在 `bit_cnt < 8` 时用 `| (8'hFF >> bit_cnt)` 把高位补 1；若已有 ≥8 位待发，转到 `S_RST_DRAIN` 排空，且**排到最后一小截（1..7 位）也要补成整字节发出**，并再判一次 0xFF（`bitstream_packer.v:138-197`）。RST 编号由 `rst_counter` 3 位自然回绕，输出 `{5'b11010, rst_counter}`（`bitstream_packer.v:215-226`）。

**flush 用一个带 tlast 的哑字节收尾**。`S_FLUSH_LAST` 在无残留位时发 `out_data=8'h00` 且 `out_last=1`，同时把 `bit_buf/bit_cnt/rst_counter` 复位给下一帧（`bitstream_packer.v:269-287`）。JPEG 真正的 EOI 由 jfif_writer 补，这里的 tlast 只是"扫描数据到此为止"的域内信号（`jfif_writer.v:1163-1172`）。

**LITE 模式的 DQT 也是参数化的**。虽然用 ROM，但 `header_rom` 里 DQT 的 64 字节是 `initial` 块按 `LITE_QUALITY` 现算并按锯齿序写入的（`jfif_writer.v:685-843`），SOF0 的宽高也从 `IMG_WIDTH/IMG_HEIGHT` 覆写（`jfif_writer.v:843-856`）。所以同一个 ROM 结构能出不同质量与尺寸的头。

**DRI 段按需插入**：`restart_interval != 0` 才在 SOF0 与 DHT 之间插 6 字节 `FF DD 00 04 hi lo`（`jfif_writer.v:1102-1107`、`jfif_writer.v:1132-1149`）。

**full 模式的 DQT 读表要提前一拍发地址**：`S_DQT_L_DATA` 第一拍只置 `qt_data_valid` 不置 `tvalid`（等量化器一拍读延迟），之后每拍把地址预取到 `seg_idx+2` 对应的锯齿位置（`jfif_writer.v:506-527`）。这样输出字节与 `qt_rd_data` 对齐。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| 累加器 | 64 位，位计数 7 位 | `bitstream_packer.v:44-50` |
| LITE 头长 | 623 字节（0..622），SOF0 止于 176，DHT 起于 177 | `jfif_writer.v:15`、`jfif_writer.v:673` |
| DHT 长度 | 432 字节（4 张表） | `jfif_writer.v:92`、`jfif_writer.v:856` |
| SOI+APP0 | 20 字节 | `jfif_writer.v:349` |
| SOS | 14 字节 | `jfif_writer.v:337` |
| EXIF APP1 | 可选 76 字节，插在 APP0 之后 | `jfif_writer.v:1063`、`jfif_writer.v:1117-1129` |
| 输出侧 | 无 tready，消费者必须常收 | `jfif_writer.v:54-57` |

## JPEG 压缩适配器

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_jpeg_compressor.v` 是 vendor 核与项目其余部分的唯一接缝，把一个"没有反压、没有帧语义"的编码核包成"一条命令一帧、带帧号、带中止、带统计"的组件。

对外接口（`wcis_jpeg_compressor.v:16-31`）：

- 命令侧：`cmd_valid/cmd_ready` + `cmd_frame_id[31:0]`。
- 像素侧：`s_rgb[23:0]`（`{R,G,B}` 行扫）、`s_valid/s_ready`、`abort_frame`。
- 输出侧：`m_data[7:0]`、`m_valid/m_ready`、`m_sof/m_last`、`frame_id`。
- 状态侧：`frame_abort`（事件）、`busy`、`overflow_sticky`、`frames_done/frames_aborted/fifo_overflows`、`last_frame_bytes/last_frame_cycles`。

参数：`IMG_WIDTH`/`IMG_HEIGHT`/`QUALITY`、`FIFO_AW`（默认 12 → 4096 字节）、`PIPELINED_FIFO`（0 = 老的 FWFT 分支，1 = 用 vendor `axis_fifo` 同步 RAM + 两级读流水）（`wcis_jpeg_compressor.v:7-14`）。

### 数据通路

`mjpegzero_enc_top` 实例化在 `wcis_jpeg_compressor.v:61-79`，全部用 `LITE_MODE=1`。像素直接进 `s_axis_vid_tdata`，`tvalid` 由 `s_valid && feeding && initialized && !recover && !abort_frame` 合成；行尾/帧首不靠上游给，而是本地按像素计数生成：`tlast = (column == IMG_WIDTH-1)`、`tuser = (pixel_index == 0)`（`wcis_jpeg_compressor.v:66-70`）。这样上游只需按行扫送 `W*H` 个像素，不必懂 AXI4-Stream 的帧标志。

字节侧：编码器输出进一个 8 位 FIFO（附带 1 位 last），`m_valid` 只在 `inflight && !abort_frame` 时有效（`wcis_jpeg_compressor.v:81-90`）。`m_sof = m_valid && byte_index == 0`，`m_last = m_valid && fifo_last`（`wcis_jpeg_compressor.v:86-87`）。

主状态：`inflight`（一帧在进行）、`feeding`（还该收像素）、`recover`（一拍恢复脉冲）、`initialized`（核的 CTRL.enable 已写成功）（`wcis_jpeg_compressor.v:34-59`）。

### 特色设计

**一帧的边界由"像素配额 + 字节 EOF"两端夹住**。命令被接受时清 `pixel_index/column/byte_index/cycle_count` 并置 `inflight/feeding`（`wcis_jpeg_compressor.v:151-154`）；收到第 `PIXELS` 个像素就撤 `feeding`（`wcis_jpeg_compressor.v:156-161`），此后不再收像素；只有末字节被下游真正接收（`pop && m_last`）才撤 `inflight`、加 `frames_done`、记 `last_frame_bytes/last_frame_cycles`（`wcis_jpeg_compressor.v:162-169`）。因此"帧完成"以下游交付为准，不是以内部编码完成为准——下游卡住时 `inflight` 一直为 1，`cmd_ready` 也就一直为 0，不会叠帧。

**核的 enable 是一次性握手初始化，且每次恢复都重做**。AW 与 W 独立，各自记住"已握手"，收到 `bvalid && bresp==0` 才置 `initialized`（`wcis_jpeg_compressor.v:40-49`）；`awvalid/wvalid` 直接由 `!init_aw/!init_w` 驱动（`wcis_jpeg_compressor.v:73-75`）。`reset || recover` 会把这三个标志全清，所以溢出中止后不需要外部干预就会自动重新初始化。

**溢出不是一个"丢字节"事件，而是一次整帧作废**。判据只有一条：`overflow_now = push && !fifo_ready`（`wcis_jpeg_compressor.v:90`）——编码器要写而 FIFO 满。此时置 `recover`、撤 `inflight/feeding`、发一拍 `frame_abort`、`frames_aborted++`，并置 `overflow_sticky`、`fifo_overflows++`（`wcis_jpeg_compressor.v:143-149`）。`recover` 同时复位核（`core_reset_n = !reset && !recover`，`wcis_jpeg_compressor.v:36`）和清空 FIFO（两个分支都把 `recover` 接到 FIFO 复位，`wcis_jpeg_compressor.v:98`、`wcis_jpeg_compressor.v:116`），所以不会把半帧的预取字节留给下一帧。

**输出缓冲两种实现，接口不变**。`PIPELINED_FIFO=1` 走 `axis_fifo`（`DEPTH=1<<FIFO_AW`、`RAM_PIPELINE=2`、`FRAME_FIFO=0`），复位源是 `reset || recover || abort_frame || overflow_now`（`wcis_jpeg_compressor.v:92-104`）；`=0` 保留老的分布式 RAM FWFT 分支（`ram_style="distributed"`，9 位宽存 `{last,data}`，`fifo_ready = depth != FIFO_DEPTH || pop`）（`wcis_jpeg_compressor.v:105-131`）。两条路径对外的 `m_*` 时序语义一致，只是存储资源与时序不同。SDI 预览用 1，DDR 原生帧路径用默认 0（`wcis_sdi_jpeg_stream.v:106`）。

**显式中止与自恢复共用一条恢复通路**。`abort_frame && inflight` 与 `overflow_now` 进同一个 `if` 分支（`wcis_jpeg_compressor.v:143-149`），区别只在是否置 sticky 与计数。`frame_abort` 只保持一拍（每拍默认清 0，`wcis_jpeg_compressor.v:141`），下游要按"事件"而不是"电平"处理。

**反压契约写在文件头**：下游必须等到有效 EOF 才提交帧；收到 `frame_abort` 就丢弃该 `frame_id` 已交付的部分；有限 FIFO 不能承诺无限反压；SDI 这类不遵守 ready 的源必须经独立帧缓冲再进来（`wcis_jpeg_compressor.v:1-6`）。

### 关键参数与寄存器

| 项 | 值 | 依据 |
|---|---|---|
| 默认几何/质量 | 1920×1080 / Q75 | `wcis_jpeg_compressor.v:8-10` |
| 输出 FIFO | `2^FIFO_AW` 字节，默认 4096 | `wcis_jpeg_compressor.v:11`、`wcis_jpeg_compressor.v:32` |
| `cmd_ready` | `!reset && !recover && initialized && !inflight && !abort_frame` | `wcis_jpeg_compressor.v:56` |
| `s_ready` | 上述条件再与 `feeding && core_ready` | `wcis_jpeg_compressor.v:57-58` |
| `busy` | `inflight` 或 `recover` 或 `!initialized` | `wcis_jpeg_compressor.v:59` |
| `last_frame_cycles` | 从命令被接到末字节交付，含下游等待 | `wcis_jpeg_compressor.v:155-168` |

## JPEG CustomOp

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_jpeg_customop.v` 把编码器挂到厂商 512 位 CustomOp 总线上，让 PS 用"配置 + 触发 + 轮询"的方式压缩 PL-DDR 里的一整帧，不搬像素、不做软件编码。

两个时钟域：`ra_clk`（寄存器与像素/字节路径，本项目为 GP 100 MHz）与 `clk`（CustomOp 存储侧，HP 200 MHz）；`reset = !rst_n || !ra_rst_n`（`wcis_jpeg_customop.v:18-20`）。

接口分三面（`wcis_jpeg_customop.v:7-17`）：寄存器从口（`itf_ra_*`，32 位地址/数据，单拍读）；存储主口写（`itf_awaddr[31:0]`、`itf_awdata[511:0]`、`itf_awinfo[71:0]`、`itf_awvalid/awready`）；存储主口读（`itf_araddr/arinfo`、`itf_rdata[511:0]/rinfo`）。JPG1 页基址 `0x400c2100`，ID `0x4a504731`（`wcis_jpeg_customop.v:116`；PS 侧 `npu_photo/src/jpeg_runner.cpp:22`）。

### 数据通路

读方向：`fetch_offset` 从 0 递增，每次 64 字节，`req_valid = busy && error==0 && !read_outstanding && line_count<2 && fetch_offset<input_bytes`（`wcis_jpeg_customop.v:47-48`）。地址 = `cfg_src + fetch_offset`，经 `wcis_cdc_mailbox` 跨到 `clk` 域驱动 `itf_ar*`（`wcis_jpeg_customop.v:60-63`）。返回数据经第二个 mailbox 跨回 `ra_clk`，落进 `lines[0:1]` 双行缓冲（`wcis_jpeg_customop.v:64-66`、`wcis_jpeg_customop.v:176`）。

像素解包：`pixel_line = lines[line_rd]`，按 `lane` 切片；`cfg_format[0]=1` 时按 BGRX8 取 32 位、直接取低 24 位；`=0` 时按 RGB565 取 16 位再逐段拼成 24 位（`{p565[15:11],p565[15:13],p565[10:5],p565[10:9],p565[4:0],p565[4:2]}`，即高位复制补低位）（`wcis_jpeg_customop.v:51-55`）。一行 512 位含 32 个 RGB565 像素或 16 个 BGRX8 像素，`line_pop` 在最后一个 lane 上触发（`wcis_jpeg_customop.v:59`）。

写方向：编码器字节逐个塞进 `output_pack[511:0]`，同时用 `byte_mask` 记有效字节（`wcis_jpeg_customop.v:182-189`）；满 64 字节或遇到 `jpeg_last` 就置 `write_pending`，由第三个 mailbox 把 `{dst_pointer, output_pack, byte_mask}` 跨到 `clk` 域发 `itf_aw*`（`wcis_jpeg_customop.v:91-96`）。`itf_awinfo = {1'b0, byte_mask, 6'd0, 1'b1}`——末位 1 是"这是一次写"的标志（`wcis_jpeg_customop.v:96`）。

### 特色设计

**存储合法性在触发那拍一次性判完**。`valid_storage` 同时检查：源与目的地址 64 字节对齐（`[5:0]==0`）、容量 ≥64 且 64 字节对齐、格式 ≤1、源尾与目的尾都不越 128 MiB 窗口（`<= 33'h08000000`）、以及源区与目的区不重叠（`src_end <= dst || dst_end <= src`）（`wcis_jpeg_customop.v:34-37`）。不合法就不启动，直接 `done<=1, error<=1`（`wcis_jpeg_customop.v:145`）——错误在"发命令"这一步暴露，而不是跑一半才发现。

**两行缓冲 + 只留一次在飞读**。`line_count` 上限 2（`req_valid` 里的 `line_count<2`），且 `read_outstanding` 保证同一时刻只有一个读请求（`wcis_jpeg_customop.v:47-49`、`wcis_jpeg_customop.v:166-169`）。这样存储侧接口不需要深队列，也不必依赖乱序返回；像素侧按 `line_rd` 交替消费，`line_pop` 才换行（`wcis_jpeg_customop.v:177-181`）。

**三处 mailbox 把"数据"和"控制"分开跨域**。读请求（32 位地址，`ra→clk`）、读响应（512 位数据，`clk→ra`）、写请求（608 位 `{dst_pointer, pack, mask}`，`ra→clk`）各用一个 `wcis_cdc_mailbox`（`wcis_jpeg_customop.v:60-66`、`wcis_jpeg_customop.v:91-93`）。mailbox 是单入口 + 请求/应答翻转 + 载荷保持，源侧必须等目的侧消费完才允许下一次（`wcis_cdc_mailbox.v:13`、`wcis_cdc_mailbox.v:18-32`）。这让 512 位总线永远不需要"打包成同步器"。

**没有 B 响应的写也算完成**。注释明确：native write 没有 B response，和 vendor 路径一致，所以 `write_mail_ready` 本身就代表"目的侧已消费这次写"（`wcis_jpeg_customop.v:198-201`）。

**结束条件是四个"都空了"**。`busy` 落下要求 `!launch_pending && (encoded_eof || (error!=0 && !encoder_busy)) && !write_pending && write_mail_ready && !read_outstanding && req_ready`（`wcis_jpeg_customop.v:200-203`）——EOF 已编码、没有待写包、写邮箱可再用、没有在飞读、读请求通道空闲。少一项就可能把半帧当完成。

**错误码分开而不是一个 fail 位**：`error==2` 是编码器 `frame_abort`（含 FIFO 溢出），`error==3` 是输出容量不够（`bytes_encoded >= cfg_capacity` 时仍有字节要出），`error==1` 是配置非法（`wcis_jpeg_customop.v:190-192`、`wcis_jpeg_customop.v:145`）。触发时同时拉一拍 `encoder_abort` 取消编码（`wcis_jpeg_customop.v:191`）。

**忙时写配置被拒绝但总线照样完成**：`if(busy) rejected<=1;` 否则才按地址写（`wcis_jpeg_customop.v:138-139`）。`rejected` 是状态位而不是错误——PS 读回就知道这次配置没生效。

**流水统计三件套**：`input_wait`（已启动但还没有像素）、`output_wait`（有字节但 `jpeg_ready` 低）、`read_blocks`/`write_blocks`（实际 64 字节事务数），加上 `job_cycles` 与 `last_cycles`（`wcis_jpeg_customop.v:161-169`、`wcis_jpeg_customop.v:202`）。这些都是寄存器可读的，用于区分"卡在取数"还是"卡在写回"。

### 关键寄存器（JPG1，基址 0x400c2100，按地址位 awaddr[7:2] 索引）

| 偏移 | 读 | 写 |
|---|---|---|
| `0x00` | `0x4a504731`（JPG1） | bit0 触发一次作业 |
| `0x04` | `{error[3:0], rejected, done, busy}` | 只读 |
| `0x08`/`0x0c` | `completed_frame` / `bytes_encoded` | 只读 |
| `0x10` | `cfg_frame` | 帧号 |
| `0x14` | `cfg_src` | 源地址（64 字节对齐） |
| `0x18` | `cfg_dst` | 目的地址（64 字节对齐） |
| `0x1c` | `cfg_capacity` | 输出容量（≥64，64 字节对齐） |
| `0x20` | `cfg_format` | 0 = RGB565，1 = BGRX8 |
| `0x24`/`0x28`/`0x2c` | `IMG_WIDTH`/`IMG_HEIGHT`/`QUALITY` | 只读 |
| `0x30`/`0x34` | `last_cycles`/`encoder_cycles` | 只读 |
| `0x38`..`0x44` | `input_wait`/`output_wait`/`read_blocks`/`write_blocks` | 只读 |

依据：`wcis_jpeg_customop.v:113-159`。输入字节数由格式决定：`PIXELS*4`（BGRX8）或 `PIXELS*2`（RGB565）（`wcis_jpeg_customop.v:31`）。

## SDI 流式取流

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_sdi_jpeg_stream.v` 解决"SDI 没有 ready"这件事：摄像头域连续出像素，编码器只能按 ready 收，两者必须解耦，而且不能因为下游忙就把一帧拆成半帧。

接口（`wcis_sdi_jpeg_stream.v:10-18`）：摄像头侧 `cam_clk/cam_vsync/cam_de/cam_rgb[23:0]/cam_locked`；逻辑侧 `clk`；控制 `enable`、`downstream_idle`；输出 `m_data/m_valid/m_sof/m_last/m_ready`、`m_frame_id`、`abort_frame`、`idle`、`frames_encoded/frames_rejected`。参数 `IMAGE_WIDTH/IMAGE_HEIGHT/QUALITY`、`PIXEL_FIFO_DEPTH`（默认 8192）、`LOGIC_HZ`（超时换算用，预览传 150000000，`wcis_pl_jpeg_preview.v:113`）。

### 数据通路

摄像头域：`cam_vsync` 上升沿（`source_start = cam_vsync && !vs_d`）是唯一准入口。准入条件 `admission = enable_sync[1] && idle_sync[1] && descriptor_ready && cam_locked`（`wcis_sdi_jpeg_stream.v:32`），只在帧首采样一次，`select_now` 之后整个帧保持不变（`wcis_sdi_jpeg_stream.v:33`）。被选中的帧逐像素写进 `axis_async_fifo`（24 位数据 + 32 位 ID + 1 位 user，`FRAME_FIFO=0`，`wcis_sdi_jpeg_stream.v:78-85`），`tlast` 由 `pixel_number == PIXELS-1` 生成、`tuser` 由 `pixel_number == 0` 生成（`wcis_sdi_jpeg_stream.v:81-82`），`tready` 真正反压摄像头域。

逻辑域：5 态机 `WAIT → START → FEED → FINISH`，异常进 `DROP`（`wcis_sdi_jpeg_stream.v:86`）。`WAIT` 里等"FIFO 有帧首像素 + 编码器可接命令 + 下游不忙"三者同时成立才 `cmd_valid`（`wcis_sdi_jpeg_stream.v:130-133`）；`START` 等 `cmd_ready`；`FEED` 把像素流给编码器并按 `pixel_last` 转 `FINISH`；`FINISH` 等 `!encoder_busy && downstream_idle` 回 `WAIT`（`wcis_sdi_jpeg_stream.v:134-139`）。

### 特色设计

**整帧准入 / 整帧跳过**。因为 SDI 不会等，唯一的干净做法是"要么整帧收，要么整帧不收"。`idle` 是从逻辑域打回摄像头域的"我可以接一帧"电平（`wcis_sdi_jpeg_stream.v:98-99`、`wcis_sdi_jpeg_stream.v:120`），准入在 `source_start` 那拍只判一次。没被选中的帧照旧被 SDI 接收器吃完，只是不写 FIFO；`frames_rejected` 记被放弃的帧（`wcis_sdi_jpeg_stream.v:125-128`）。

**idle 是注册过的整条件，不是组合拼出来**。`idle_registered <= state==WAIT && !pixel_valid && encoder_cmd_ready && downstream_idle`（`wcis_sdi_jpeg_stream.v:120`）。注释给了理由：这个指示要跨到摄像头域，若用组合式，可能在编码器/FIFO 状态切换的缝隙里被采到毛刺，从而在错误时刻开一帧（`wcis_sdi_jpeg_stream.v:117-119`）。

**几何校验走独立描述符邮箱，且"不合格帧不发 EOF"**。摄像头域在 `source_end` 时把 `{ok, frame_id}` 打进 33 位 mailbox（`wcis_sdi_jpeg_stream.v:67-73`、`wcis_sdi_jpeg_stream.v:41-43`）。`ok` 的判据是四条全真：没有 `source_bad`、`cam_locked`、像素数 == `PIXELS`、行数 == `IMAGE_HEIGHT`（并把正在进行的最后一行算进去）、且行尾时列数 == `IMAGE_WIDTH`（`wcis_sdi_jpeg_stream.v:70-71`）。逻辑域把结果锁进 `validation_known/validation_good`（`wcis_sdi_jpeg_stream.v:122-124`），而 `m_valid` 被写成 `jpeg_valid && (!jpeg_last || (validation_known && validation_good)) && !cancel`（`wcis_sdi_jpeg_stream.v:104`）——即**校验未到或不合格时，末字节永远不出现**，下游按"没有 EOF 就不提交"的契约自然丢弃这帧。

**取消有三个来源，且要等描述符**。`cancel = mismatch || invalid_end || timeout_frame`（`wcis_sdi_jpeg_stream.v:93-96`）：`mismatch` 是 FEED 中出现帧号跳变或帧内二次 SOF（`wcis_sdi_jpeg_stream.v:93`）；`invalid_end` 是描述符到达且判不合格（`wcis_sdi_jpeg_stream.v:94`）；`timeout_frame` 是状态非 WAIT/DROP 时 `deadline >= LOGIC_HZ/10`（即 100 ms 量级，`wcis_sdi_jpeg_stream.v:95`、`wcis_sdi_jpeg_stream.v:121`）。`abort_frame` 只在非 WAIT/DROP 状态发出（`wcis_sdi_jpeg_stream.v:97`）。

**像素 ready 由状态决定，而不是由 FIFO 决定**。`pixel_ready = (state==WAIT && !pixel_sof) || (state==FEED && !mismatch && encoder_ready) || (state==DROP)`（`wcis_sdi_jpeg_stream.v:100`）。`WAIT` 时允许非帧首像素流走（把上一帧残尾排掉），`DROP` 时全放行（尽快清空），只有 `FEED` 且无异常才真正送编码器——这样"丢弃"和"接收"用的是同一个 FIFO，不需要旁路。

**溢出即本帧作废，但帧号继续**。摄像头域一旦发现 `!fifo_ready || !cam_locked || pixel_number >= PIXELS` 就置 `source_bad` 并撤 `selected`（`wcis_sdi_jpeg_stream.v:59-61`），本帧描述符必然判不合格，逻辑域走 `cancel` → `DROP`；下一帧重新走准入。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| 像素 FIFO | 8192 深、24 位、带 32 位 ID 与 user | `wcis_sdi_jpeg_stream.v:8`、`wcis_sdi_jpeg_stream.v:78-85` |
| 帧超时 | `LOGIC_HZ/10`（150 MHz 下 100 ms） | `wcis_sdi_jpeg_stream.v:95` |
| 状态编码 | `WAIT=0, START=1, FEED=2, FINISH=3, DROP=4` | `wcis_sdi_jpeg_stream.v:86` |
| 复位释放 | 两域各三级同步，`[2]` 位用 | `wcis_sdi_jpeg_stream.v:20-25` |
| 编码器分支 | `PIPELINED_FIFO(1)` | `wcis_sdi_jpeg_stream.v:106` |

## 纯 PL 预览封装

### 定位与接口

`repos/FPAI30TAI图像FPGA/rtl/wcis_pl_jpeg_preview.v` 是"摄像头 → JPEG → UDP → RGMII"整条纯 PL 链路的板级封装，不含 DDR 主口、不含 PS 像素拷贝、不改 NPU 时钟（`wcis_pl_jpeg_preview.v:1-3`）。

对外：`hp_clk`（200 MHz 参考）、`gp_clk`（100 MHz 寄存器域）、`cam_*`（SDI 摄像头）、一组 AXI4-Lite 从口（`awaddr/awdata/araddr/rdata`）与一路 legacy 从口（与既有寄存器页共存）、以及 PHY 引脚（`phy_tx_clk/tx_ctl/txd[3:0]/reset_n/mdc/mdio_*`）（`wcis_pl_jpeg_preview.v:4-14`）。

### 数据通路

时钟：一个 `PLLE2_BASE` 从 200 MHz 参考产生 150/125/250 MHz 三路（VCO 1500 MHz：`DIVCLK_DIVIDE=2`、`CLKFBOUT_MULT=15`、`CLKOUT0_DIVIDE=10`、`CLKOUT1_DIVIDE=12`、`CLKOUT2_DIVIDE=6`），带外部反馈 BUFG（`wcis_pl_jpeg_preview.v:19-27`）。`net_clk=150`（JPEG/网络逻辑）、`gtx_clk=125`（MAC 物理侧）、`gtx_clk250=250`（串化器）。

寄存器：`wcis_preview_csr_router` 按地址位把 `0x2200` 窗口分给本模块、其余交给 legacy（`wcis_pl_jpeg_preview.v:36-45`）；`wcis_preview_registers` 实现 NTP 页（`wcis_pl_jpeg_preview.v:46-56`）。

主链：`wcis_sdi_jpeg_stream`（摄像头 → JPEG 字节）→ `wcis_jpeg_udp_packetizer`（字节 → WJP1 分片 + UDP 长度）→ `wcis_udp_payload_pipe`（16 字节切分）→ `wcis_jpeg_network_tx`（UDP/IP/MAC/引脚）（`wcis_pl_jpeg_preview.v:113-138`）。`downstream_idle` 由 `!packetizer_busy` 提供（`wcis_pl_jpeg_preview.v:116`）。

### 特色设计

**配置用一个 224 位原子邮箱提交，禁用即取消**。GP 域把 `{session_id, local_ip, destination_ip, local_mac, next_hop_mac, source_port, destination_port}` 打包进一个 `wcis_cdc_mailbox`（`wcis_pl_jpeg_preview.v:73-77`）；网络域收到后一次性写进 `net_*` 影子寄存器并置 `network_enabled`（`wcis_pl_jpeg_preview.v:78-88`）。邮箱复位源是 `reset || !enabled`（`wcis_pl_jpeg_preview.v:59`），所以关闭时任何在途配置都会被取消；`configuration_sent` 只在邮箱可接受时置位，避免重复提交（`wcis_pl_jpeg_preview.v:69-72`）。这样"半套新配置 + 半套旧配置"不会同时生效。

**复位分三层，且刻意不让 HP 域复位进 150 MHz 的同步选择器**。`common_reset = reset || !locked || !enabled || !network_enabled`（`wcis_pl_jpeg_preview.v:89`），两个目标域各自三级同步释放（`wcis_pl_jpeg_preview.v:90-94`）。网络域的使能判定写成"异步置位、只在 `net_clk` 上释放"：`if(!enable_to_network[1]) network_enabled<=0; else if(configuration_valid) ...`（`wcis_pl_jpeg_preview.v:78-87`），注释说明 200→150 MHz 只有 1.667 ns 边沿间隔，不能把 HP 域复位再喂进这一级同步使能/数据选择（`wcis_pl_jpeg_preview.v:79-81`）。

**跨域状态先在源域变成电平，再同步**。125 MHz MAC 的 `tx_underflow` 是脉冲，先在 `gtx_clk` 域锁成 `underflow_seen` 电平（`wcis_pl_jpeg_preview.v:100-105`），再用 `wcis_status_sync` 过到 `net_clk`（`wcis_pl_jpeg_preview.v:106-108`），最后在 `net_clk` 域与 `arp_failed/rx_bad_fcs/packet_error` 一起 OR 进 `sticky_errors`（`wcis_pl_jpeg_preview.v:109-112`）。`wcis_status_sync` 只传单比特，并要求生产者保持足够长、两级同步、复位在本地释放（`wcis_status_sync.v:1-19`）。

**寄存器域的统计是"整批快照"而不是逐位同步**。167 位状态（锁状态、四个错误位、速率、五个计数器）由一个 `wcis_cdc_mailbox` 整体搬到 GP 域，再一次性写进 `sampled_status`（`wcis_preview_registers.v:29-36`、`wcis_preview_registers.v:45`）。读回时按 `0x40..0x50` 分段取，保证一次读到的计数来自同一时刻。

**使能前有一整套前置条件，运行中拒绝改配置**。写 `0x04` 置 1 时要求：`session_id != 0`、`local_ip != 0`、`destination_ip != 0`、`local_mac != 0` 且不是组播位（`!local_mac[40]`）、两个端口非 0、`phy_reset_n` 已置、MDIO 空闲（`command_ready && !command_valid`），TX-only 模式还要求 `next_hop_mac != 0 && !next_hop_mac[40]`；任一不满足就 `rejected_writes++` 而不置 `enable`（`wcis_preview_registers.v:49-57`）。`enable` 为 1 时除 `0x04` 外的写一律计入拒绝（`wcis_preview_registers.v:57`）——配置只能在关闭时改。

**读响应归属在背压期间保持**。`wcis_preview_csr_router` 用一个 `pending` + `owner_preview` 记住"这次读是谁的"，`rvalid/rdata` 由 owner 决定，直到 `rready` 才清（`wcis_preview_csr_router.v:19-32`）。同时 `arready` 在 `pending` 期间整体拉低，所以同一时刻只有一个在飞读（`wcis_preview_csr_router.v:19`）。

**能力寄存器说明自己是哪一版**：`0x00` 读回 `0x4e545031`（NTP1）或 `0x4e545032`（NTP2，TX-only），`0x5c` 在 TX-only 时读 `7`（bit0 显式下一跳、bit1 固定 1G 全双工、bit2 共用时钟串化器且 PHY 附加 TX 延迟为 0）（`wcis_preview_registers.v:80`、`wcis_preview_registers.v:101-103`）。`speed` 读回是固定 `2'b10` 而不是实测速率，注释点明"这是固定 MAC 模式 + 粘滞错误，不是 PHY 链路速率测量"（`wcis_pl_jpeg_preview.v:124-126`）。

### 关键参数与关键量

| 项 | 值 | 依据 |
|---|---|---|
| PLL 输出 | 150 / 125 / 250 MHz，VCO 1500 MHz | `wcis_pl_jpeg_preview.v:19-23` |
| JPEG 逻辑域 | `net_clk = 150 MHz` | `wcis_pl_jpeg_preview.v:25`、`wcis_pl_jpeg_preview.v:113` |
| 寄存器页 | NTP 偏移 `0x2200`，magic `0x4e545031/2` | `wcis_preview_csr_router.v:13-14`、`wcis_preview_registers.v:80` |
| 几何读回 | `0x54` = 1920，`0x58` = 1080 | `wcis_preview_registers.v:99-100` |
| 复位 | 公共复位 + 两域各自三级同步释放 | `wcis_pl_jpeg_preview.v:89-94` |
| 统计 | 5 个 32 位计数器 + 4 个错误位，167 位一次快照 | `wcis_preview_registers.v:32-36` |

## 参数与口径汇总

把上面分散的常量集中一处，便于交叉核对（具体值仍以源码为准）：

- 编码核：`LITE_MODE=1`、`RGB_INPUT=1`、4:2:2、`HUFF_BANKS=8`、`TOTAL_BLOCKS=(W/16)*(H/8)*4`。
- 适配器：`FIFO_AW=12`（4096 字节）；SDI 预览用 `PIPELINED_FIFO=1`，DDR 路径用默认 0。
- CustomOp：JPG1 = `0x4a504731` @ `0x400c2100`；64 字节对齐、64 字节事务；源/目的互不重叠且都在 128 MiB 内。
- SDI 取流：像素 FIFO 8192 深；帧超时 100 ms（按 `LOGIC_HZ` 换算）。
- 预览：150 MHz 编码/网络逻辑、125 MHz MAC 物理侧、250 MHz 串化；NTP 页 `0x2200`，默认关闭。
- 三处"不允许含糊"的契约：下游必须见有效 EOF 才提交帧（`wcis_jpeg_compressor.v:4-5`）；SDI 必须经独立帧缓冲才能进编码器（`wcis_jpeg_compressor.v:6`）；mailbox 跨域必须在集成时加最大延迟与总线偏差约束（`wcis_cdc_mailbox.v:4`）。
