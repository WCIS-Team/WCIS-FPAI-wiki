---
tags: [SOP]
---

# BOOTbin位流替换手术

本页记 2026-10-10 实测走通的一条路：**在没有 JTAG、厂商三条重载通道全坏的情况下，靠直接改写 SD 卡引导镜像里的 PL 位流分区，把自己的位流灌进 FPGA。**

这条路已经**端到端验证过**：改完重启，`FSBL` 正常加载新位流（`Download the PL bitstream is done at the 616.99 ms`），Linux 照常启动。相关背景见 [[PL位流重载通道失效]]（为什么必须走这条路）。

**前提**：SD 卡引导分区里要有厂商原版 `BOOT.bin` 的备份。这条路改的是厂商引导镜像，**没有厂商配合时属于非支持操作**，仅在我们自己的板子上做。

---

## 一、先决条件：位流格式与槽位边界

### 1.1 位流在 BOOT.bin 里是 32 bit 字序翻转存放的（A）

Zynq 位流在文件里以 `AA 99 55 66` 开头；在 `BOOT.bin` 里它变成 `66 55 99 AA`，即**每个 32 bit 字内部字节反转**。

- **踩过的坑**：拿原始 `.bit` 直接去搜 `BOOT.bin`，四处全 `-1`。**必须先做字序翻转再搜。**（这条 [[板卡镜像实测取证]] 早就记过，本轮又踩了一次。）
- 反向验证：Linux `fpga_manager` 那条路报的错也是 `Bitstream must be a byte swapped .bin file`，与此处一致。

### 1.2 怎么找到槽位边界（A，本轮方法）

不要去猜 `BOOT.bin` 的分区表字段（FMSH 是私有布局，`Image Header Table Offset` / `Partition Header Address` 都对不上标准 Zynk 格式）。**用内容指纹反推**：

1. 从板载 `.bit` 里找同步字 `AA 99 55 66`，得到 payload 起点。
   - **注意**：不同 `.bit` 的偏移不同。`ai7030_top_disable_icap.bit` 是 192，`ai7030_top.bit` 是 **152**。差 40 字节，差点算错槽位大小。
2. 取 payload 前 256 字节，按 4 字节字序翻转，在 `BOOT.bin` 里搜 —— 得到精确起点。
3. 起点 + payload 长度 = 终点。

实测结果：

```
board_ai7030_top.bit  = 5 980 020 B，同步字在偏移 152，payload = 5 979 868 B
字序翻转后在 BOOT.bin 命中 0x2D9F0 (186 864)
终点 = 0x2D9F0 + 5 979 868 = 0x5E18CC (6 166 732)
0x5E18CC 起是 48 字节 FF 填充，再往后是 BL31(ATF) → u-boot
```

`BOOT.bin` 布局（本板，实测）：

| 区间 | 内容 |
|---|---|
| `0x000000..0x02D9EF` | FSBL、init 数组、OID/证书区 |
| **`0x02D9F0..0x5E18CB`** | **PL 位流，5 979 868 B，字序翻转存放** |
| `0x5E18CC..0x5E18FF` | 填充（48 B FF） |
| 之后 | BL31(ATF) `0x5EADA8` 附近 → u-boot `0x69322A` 附近 |

### 1.3 长度必须精确相等（A）

我们出的位流 payload 恰好也是 **5 979 868** 字节，**正好塞满，差 0**。

- **不要裁也不要补**。尾部是 `20 00 00 00`（7 系位流的空操作 dummy 命令，厂商那份同样以此结尾），看起来"多出几十字节可以截"，但槽位长度是引导镜像写死的，改长度就会让 FSBL 的分区校验对不上。
- 构建脚本里因此有一道硬检查：`payload ≠ slot` 直接 `throw`，不做任何自动裁剪。

---

## 二、替换步骤

### 2.1 构建（脚本会自校验）

脚本：`C:\Users\takomi\AppData\Local\Temp\opencode\build_bootbin.ps1`

```
BOOT.bin  7023040 字节  MD5 ACA4612B566738350A8C5EDAC0DB1929
slot 5979868 字节；our payload 5979868 字节；delta 0
sync word OK at bit offset 161

=== verification ===
  bytes changed before 0x2D9F0 : 0
  bytes changed after  0x5E18CC : 0
  region bytes != source payload: 0
  size: orig 7023040 / new 7023040
  readback sync byte0 = 0xAA … byte3 = 0x66
```

**三项校验必须全过才写出文件**：

1. `[0, 0x2D9F0)` 变动 0 字节（FSBL 等不能碰）
2. `[0x5E18CC, end)` 变动 0 字节（ATF/u-boot 不能碰）
3. 区域内每个字节 == 字序翻转后的源 payload

> **自校验救过一次命**：第一版校验逻辑拿**原始**字节去比**已字序翻转**的区域，13% 偶然对上 → 报 796916 字节不符。脚本拒绝写文件。如果是先写文件再校验，损坏的引导镜像就上板了。**校验一定要和写入用同一份"期望值"数组。**

### 2.2 上板与切换

```sh
mount -t vfat -o rw /dev/mmcblk0p1 /mnt/boot

# 先以新文件形式传，别直接覆盖
pscp BOOT_video_only.bin  root@板子:/mnt/boot/NB.bin
md5sum /mnt/boot/NB.bin              # 必须等于本地算出的值

# 备份原件，再切换
cp /mnt/boot/BOOT.bin /mnt/boot/BOOT.bak
cp /mnt/boot/NB.bin  /mnt/boot/BOOT.bin
sync                                 # FAT 写缓存，必须显式 sync
md5sum /mnt/boot/BOOT.bin /mnt/boot/BOOT.bak
```

**坑一：文件名**。`BOOT_NEW.bin` 用下划线加长名时 pscp 报 100% 成功但**文件根本没落盘**；换成 `NB.bin` 一次就成。**传完必须 `md5sum` 核对**，别信 pscp 的进度。

**坑二：分区不会自动挂载**。重启后 `/mnt/boot` 只是个空目录，`ls` 什么都看不到，很容易误判成"文件丢了"。每次都要先 `mount -t vfat /dev/mmcblk0p1 /mnt/boot`。

**坑三：必须显式 `sync`**。FAT 有写缓存，不 sync 就重启等于没写。

### 2.3 验证

重启，串口看 FSBL：

```
Preparing initialize file BOOT.bin......
Image ID verified success!!!
Checksum verified success!!!
Boot header validate success, this is a valid image!!!
Prepare downloading bitstream.....
Download the PL bitstream is done at the 616.99 ms     ← 成功
Partition Load Success   (×3)
Exit from FSBL → U-Boot → Linux
```

只要 `Download the PL bitstream is done` 这行出现，就说明新位流进 PL 了。

---

## 三、安全网（做之前先确认都就位）

| 层 | 备份 | 恢复方式 |
|---|---|---|
| 卡上 | `BOOT.bak`（原版引导镜像） | `cp BOOT.bak BOOT.bin`（Linux 还能起时） |
| 卡上 | `uEnv.txt.bak` | 同上 |
| 本地 | `board_BOOT.bin`（从板上拉的原件） | pscp 回传 |
| 本地 | `board_boot\board_ai7030_top*.bit`（板上原始位流） | pscp 回传 |
| **兜底** | U-Boot 的 **`fatwrite` 可用** | 起不来时停在 `fmsh>` 提示符，从串口写回去，**不用拆卡** |

**`fatwrite` 是这张安全网的关键**。实测 U-Boot 有这个命令：

```
fmsh> fatwrite
fatwrite - write file into a dos filesystem
```

所以最坏情况（引导镜像改坏、板子起不来）也还在 U-Boot 提示符里，可以从串口恢复 —— **前提是你能接串口**。本板的 U-Boot 控制台与 Linux 控制台**是同一个物理口**（UART0 / `serial@e0004000` = `ttyPS0`，`In`/`Out`/`Err` 三者同口），按任意键可停在 `fmsh>`。

> **C（未验证）**：我们**没有真的走到过 `fatwrite` 恢复那一步** —— 替换一次就成功了。这条恢复路径是"命令存在 + 逻辑上可行"，**没有端到端演练过**。真要用这条路之前，建议先故意破坏一次引导镜像演练一遍。

---

## 四、串口控制台（调试这类问题的前提）

**这块板子的 U-Boot 和 Linux 共用一个 UART**：`In: serial@e0004000` / `Out:` / `Err:`，Linux 侧是 `ttyPS0`，`bootargs` 里 `console=ttyPS0,115200n8`。

- 参数：**115200 8N1**，本机是 **COM6 / Silicon Labs CP210x**。
- `bootdelay=3`，开机 3 秒内**按任意键**即可停在 `fmsh>`。
- 本轮所有"厂商机制到底怎么坏的"的结论都是靠它拿到的 —— 没有串口就只能猜 `fpga loadb` 为什么失败。

**用 PowerShell 驱动 u-boot 的坑**：`$filesize` 这类变量必须**原样送进串口**，不能被本地 shell 展开。

```powershell
powershell -NoProfile -Command "& 'uboot_send.ps1' -Port 6 -Commands @('fpga info')"
```

- 外层用 `"..."` 双引号包 `& '...'` 时，里面的 `$var` **会被外层 PowerShell 先展开成空**。要么用单引号整体包住，要么直接在脚本里用字面量数值。
- **PowerShell 5.1 读 `.ps1` 用系统 ANSI 码页，不是 UTF-8。** 脚本里只要有中文注释就会 `ParserError`。**这些辅助脚本一律写纯 ASCII**（`build_bootbin.ps1` 就因此返工过一次）。

---

## 五、方法论沉淀

1. **私有格式不要靠猜，靠内容指纹。** `BOOT.bin` 的字段名和标准 Zynk 对不上，但"字节翻转后在文件里搜 256 字节切片"一次就定死了起止点。
2. **长度差是最危险的信号。** 差 40 字节时，位流尾部那些 dummy 命令看起来"可以截"。但引导镜像的长度是写死的 —— 必须精确相等，让脚本 `throw` 掉，而不是自作聪明地裁剪。
3. **校验必须与写入同源。** 用不同的字节序去验证自己刚写的文件，会得到看似合理的错误。
4. **传文件永远要核对 MD5。** pscp 报 100% 成功但文件不存在，本轮真遇到过。

---

## 六、BOOT.bin 内部结构实测（A，2026-10-12 逆向）

加状态导出模块时担心"位流变大装不进槽位"，于是把 `BOOT.bin` 头尾彻底翻了一遍。结论有几条反直觉，单列。

### 6.1 Boot Header 关键字段（实测偏移）

| 偏移 | 值 | 含义 |
|---|---|---|
| `0x020` | `66 55 99 AA` | 宽度检测字（小端读作 `0xAA995566`），**字序翻转存放** |
| `0x024` | `48 53 4D 46` | 镜像标识（`FSM…`，同样翻转） |
| `0x030` | `0x00000B40` | Image Header Table 大小 = 2880 B |
| `0x03C` | `0x0F17AB69` | **头校验和** |

**`0x03C` 的校验和只覆盖头本身，不覆盖载荷。** 这就是为什么手术能只改位流字节、头一个都不动 —— 上板实测 FSBL 正常下载就是证据。

### 6.2 分区偏移**根本没有被记录**

最想确认、也最意外的一条。把 `0x2D9F0`（位流在文件里的偏移）以 **BE32 和 LE32 两种编码全文件逐字节搜索**，**一个命中都没有**。`0x5E18CC`（槽位末尾）、`0x5E1910`（BL31 起点）在头 0x3000 内同样搜不到。

也就是说：**FSBL 不靠查表定位分区，是靠扫描。** 这解释了 §1.2 那套"字节翻转后搜索 256 字节切片"为什么能定死边界 —— 那不是巧合，那就是 FSBL 自己的做法。

推论（**注意是推论，未经上板验证**）：若整镜像都是扫描定位，把位流后面的 BL31 + u-boot 整体后移，中间的表或许不必改。但这属于**没有把握的改动**，除非必须否则不走。

### 6.3 Image Header Table 在 `0x900`，每项 `0x40`

```
0x900  width=0x250  nameoff=0x280  attr=0  "LBSF2152d_0104rd"   (FSBL)
0x940  width=0x260  nameoff=0x290  attr=0  "07iae_03_fid.bit"   (位流)
0x980  width=0x270  nameoff=0x2A0  attr=0  "13lbfle..."         (bootloader)
0x9C0  width=0x000  nameoff=0x2B0  attr=0  "...boot.bin"
0xA3C  0x0003AE57                                   (IHT 校验)
```

**四项里没有任何一项记录文件偏移或分区长度** —— 与 §6.2 互相印证。表里只有宽度、名字偏移、属性、名字本身。

### 6.4 槽位后面的余量只有 68 字节

```
0x5E18CC  00 00 00 20  FF×N  F4 03 00 AA F5 03 01 AA F6 03 02 AA F7 03 03 AA
0x5E1910  00 06 81 D2  A0 18 A6 F2  00 10 1E D5  DF 3F 03 D5   <- BL31
```

`0x5E1910` 起的 `81 D2` / `1E D5` / `3F D5` 是 AArch64 指令（`MSR`、`MSR DAIFSet`），**BL31(ATF) 从这里开始**。中间只有 68 字节。

**所以"位流变长顶掉 BL31"风险很高。** 幸好下面这条化解了。

### 6.5 位流长度由器件决定，与设计无关（这一条解了所有问题）

`dist/` 里三次**完全不同的构建**（full / lite、不同日期、不同代码）：

| 文件 | 大小 | payload |
|---|---|---|
| `ai7030_full_pd1_20261009_201512.bit` | 5 980 029 | 5 979 868 |
| `ai7030_full_pd1_20261010_024540.bit` | 5 980 029 | 5 979 868 |
| `ai7030_lite_pd1_20261010_032140.bit` | 5 980 029 | 5 979 868 |

**三个互不相同的位流长度一模一样，正好等于槽位。** 这不是巧合 —— 7 系列位流的头部加填充帧要铺满器件配置内存，**尺寸由 xc7z030 的配置容量固定**。

**推论：给设计加逻辑（本次加了约 600 个单元）不会让位流变大。** 槽位不是问题。

> 代价也要认：正因为长度恒定，"长度相等"**不能**用来验证位流内容对不对。校验必须靠 MD5 逐次比对 —— 三个文件同长但内容不同，只有 MD5 区分得开。

### 6.6 方法论补充

5. **格式没看懂时，先验证一件具体的事，别先理解全部。** 当时只想知道"位流能不能变长"，搜一次偏移就够了，不需要读懂整个 Image Header Table。
6. **"三次构建同长"这种巧合要么是铁律要么是 bug，要用实验证明。** 同一器件位流定长是铁律；换器件就未必成立。
5. **"能重新配置 PL"和"PS 能访问 PL"是两件事。** 位流灌进去了不等于能读写它的寄存器 —— 详见 [[位流构建与SDI信号检测]] 第 4.2 节。

---

## 七、第二次手术：换上带 SDI 状态导出的位流（A，2026-10-13 15:30 UTC）

§2.1 那个构建脚本在 `%TEMP%`（`opencode\build_bootbin.ps1`）里，早没了。本轮把它和上板切换都做成了常驻工具，两个文件按"拼"和"换"分工，**先离线证明拼得对，再上板换**：

| 工具 | 干什么 | 自校验 |
|---|---|---|
| `S:\work\WCIS\workenv\boot-splice.py` | 把 `.bit` 拼进 BOOT.bin 的槽位 | 槽位靠 `--ref OLD.bit` **定位**（拿参考位流的字序翻转体在模板里逐字节验到 `0x2D9F0`），长度不等直接拒绝；写完回读再比三段：区前、区内、区后必须全等，否则 `VERIFY FAILED` |
| `S:\work\WCIS\workenv\board-boot-swap.py` | 上传＋切换＋回滚 | 上传后校 md5 → `cp BOOT.bin BOOT.pre_swap.bin` → `mv NB.bin BOOT.bin` → `sync` → 终验；终验不符**自动回滚**；`--expect-boot` 换前缀检查、`--reboot` 才重启 |

**先用旧件证明工具没错，再换新件**（这一步是本轮最关键的方法，因为它把"脚本自己说成功"变成了独立可核的事实）：

```
拼 …20261010_032140.bit  →  fd15bb856d66419679a9430bc79298ea   ← 与板上当时那份逐位相同
拼 …20261012_211546.bit  →  0f4f00e1de0af8f70299572be622e45a   ← 与 §6.8.10 记的期望值相同
```

第一行是**往返复现**：用一个已知答案（板上正在跑的那颗的 md5）反推工具链正确；只有它过了，第二行的新 md5 才有意义。上板后卡上四颗的身份（15:51 UTC 实测）：

| 文件 | md5 | 内含 | NPU | 状态导出 |
|---|---|---|---|---|
| `BOOT.bin` | `0f4f00e1…` | `ai7030_lite_pd1_20261012_211546.bit` | ❌ | ✅ |
| `BOOT.pre_swap.bin` | `fd15bb85…` | `…20261010_032140.bit`（换前的现装，本次新加的备份） | ❌ | ❌ |
| `BOOT.bak` | `aca4612b…` | 厂商原版 `ai7030_edif_top.bit` | ✅ | ❌ |
| `BOOT.bak2` | `611ea706…` | 10-09 那颗 `full_pd1` | ❌ | ❌ |

**没做串口验证**（§2.3 那套 FSBL 打印本轮没取），判定"新位流进 PL 了"用的是它自己的行为：`/dev/udmabuf0` 首 4 KB 里 magic `0x53444953` 142/142 正确、`seq` 每秒 1 000.0 次在涨 —— 全零缓冲或旧位流都不会有这个行为。这条替代判据比 FSBL 打印更接近"设计在跑"，但它**不覆盖** FSBL 校验和那一段（那一段本次由 md5 相同间接保证）。

**点火门禁**：`md5sum /mnt/boot/BOOT.bin`。`fd15bb85…` 与 `0f4f00e1…` 都**不含 NPU**，跑模型会整机楔死（机理见 [[位流构建与SDI信号检测]] §4.2）；只有 `aca4612b…` 可以跑。

**10-14 复核（A，板上直接读）：现装＝`aca4612b…`＝厂商原版，门禁已过。** 上面那张身份表是 10-13 15:51 UTC 的现场，它的第一行（`BOOT.bin`＝`0f4f00e1…`）在 1 小时 32 分钟后就过期了：那条会话的发布脚本 `/root/wcis-camera-preview/boot-restores/20261013T170246Z-8766769e/restore.py` 于 10-13 17:02:46 UTC 把 `BOOT.bin` 换回厂商原版，`receipt.json` 记 `firmware_replaced:true`、备份名 `BOOT.before_factory_20261013T170246Z-8766769e.bin`，现场 `/mnt/boot/BOOT.bin` 的 sha256 `0088581b738fdef741983d2dfd4dd52363d2d90fddc2fa4dafb30cfdb3b23fca` 与收据里 `final_boot_sha256` 逐位相同 ⇒ **本次手术（状态导出那颗）在板上只活了 1.5 h**，我方那条状态导出通道随之关闭。全程没有我方下手；证据链完整版在 [[板端我方代码与产物台账]] §十四"现装位流（10-14 复核）"。

**手术仍然不是受支持操作**：动的是 SD 卡上的引导镜像，而这块卡的 PL 现场另一条会话也在用；换之前先 `md5sum` 确认现装是哪颗，换完留 `BOOT.pre_swap.bin`。

---

## 相关页面

- [[PL位流重载通道失效]] — 为什么必须走这条路，以及厂商问题单
- [[位流构建与SDI信号检测]] — 位流怎么构建出来的，以及"删 NPU"为什么行不通
- [[板卡镜像实测取证]] — 位流字序翻转的原始发现
- [[板载接口与内核改造收纳进dev]] — 内核侧改造方案（其中重载通道两条已被实测推翻）