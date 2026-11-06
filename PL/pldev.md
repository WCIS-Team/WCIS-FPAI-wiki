---
tags: [index]
---

# pldev

> 本页记悟净板**板载与外接外设**的实测归属与调用入口。板级规格与手册口径差在 [[板子（除芯片）]]，
> 改造层次（内核配置／设备树／位流）在 [[板载接口与内核改造收纳进dev]]，运行环境现状在
> [[硬件与基础运行环境档案]]——这三处已有的表，本页只指过去，不复制。

## 摄像头

视频分辨率1920*1080 FULL HD 1080P；
视频帧率PAL:1080P25帧；NTSC:1080P30帧 ；
视频接口:1路HD-SDI高清数字接口 ,1路CVBS模拟视频信号；
支持日夜彩转黑功能 支持IR-CUT电磁式自动切换；
星光级照度0.00008Lux/F1.2（彩色模式）,0.00008Lux（黑白模式）
镜头可选：2.8-12MM 或 5-50MM
视频输出标准 HD-SDI SMPTE 292M 可兼容，默认输出1080p25/30fps(1920×1080)
可调输出格式 1080P30、25

镜头上面有3个可调的圈:  
外圈可固定N-F/∞： F是Far 远，N是Near近  
内圈可固定W-T:  W是wide angle 广角端，T是telephoto长焦端  
O-C: 光 圈的开关，open和close的缩写

## 网口

板上第二颗千兆 PHY（接 PL 的那片 YT8521）的路线划分、各自卡点与读数正本，见 [[plnet]]。

## hdmi

## can接口

## eMMC（板载存储）

**一句话**：控制器是 **PS 硬核**，颗粒焊盘按手册在 **PL Bank11**、要靠 **EMIO 外扩**才够得着——
所以"eMMC 是不是 PL 端的"这个问题本身混了两层。Linux 侧看不到任何 PL 总线上的存储控制器；
但它今天能被枚举、挂载、写生产数据，是 2026-10-15 换过 `BOOT.bin`（含 PL 位流）＋ dtb 的结果。

### 三层归属

| 层 | 结论 | 证据与等级 |
|---|---|---|
| 控制器 | **PS 侧硬外设** | **A**（本次直读）：`/proc/device-tree/amba-apu@0/dwmmc@e0044000` 的 `compatible = fmsh,psoc-dw-mshc`、`status = okay`；同一条总线 `amba-apu@0` 的子节点是 `can@e0005000`／`serial@e0004000`／`gpio@e0003000`／`i2c@e0002000`／`usb@e0045000`／`ethernet@e0047000`／`devcfg@e0040000`／`slcr@e0026000`／`nfc@e0042000`／`smc@e0041000`——全是 SoC 固定外设。运行 DT 顶层**没有 `amba_pl`**，`/sys/devices/platform/` 下只有 `amba-apu@0` |
| 数据引出 | 经 PL 的 EMIO 到 Bank11（**手册口径，板上未复核**） | **B**：手册原话"SD 控制器可通过外扩 EMIO 的方式进行访问 eMMC"，已由 [[板子（除芯片）]] 存储表与 [[板载接口与内核改造收纳进dev]] 第六节各登记一次。要在板上证实就得重刷位流——破坏性动作，本次没做 |
| 驱动与块层 | `dw_mmc` → `mmc1` → `mmcblk1` | **A**：`dmesg`（内核 `5.4.52-fmsh-sdk-v2025.04`，缓冲起点 `[0.000000] Booting Linux on physical CPU 0x0000000000`）给出 `dw_mmc e0044000.dwmmc: Using PIO mode`、`Version ID is 220a`、`DW MMC controller at irq 24, 32 bit host data width, 32 deep fifo`，随后 `mmcblk1: mmc1:0001 Y2P032 29.1 GiB` 与 `mmcblk1boot0/boot1: partition 1/2 4.00 MiB` |

EMIO 是 PS↔PL 之间的内部并行出口。走 EMIO 时**控制器仍是 PS 那颗硬 IP**，只是把时钟、命令与
数据线交给 fabric，由位流的引脚约束落到 Bank11 的颗粒上。"必须经 PL"说的是**信号引出**，
不是"PL 里做了一颗软控制器"——把这两件事说成一件，就会得出"eMMC 是 PL 端设备"的错印象。

**"到底是不是 eMMC"的内核级判据**：`/sys/block/mmcblk1/device/type = MMC`，对照
`/sys/block/mmcblk0/device/type = SD`。挂载脚本自己就用这条判据（`mount_face_store.py` 的
`device/type` 检查，不符报 `Personnel partition is not on eMMC`）；另一条旁证是 `mmcblk1boot0`／
`mmcblk1boot1` 这两个 4 MiB 启动分区——SD 卡没有。

### 站点上是怎么标的（她指的入口）

`GET http://192.168.1.113:8091/api/health`（本次抓取，`status = ready`）里与存储有关的只有两项：
`gallery_storage: "emmc"`、`gallery_storage_ready: true`。同一段 JSON 里挨着的
`frame_transport: "single_upload_retained_PL_DDR"`、`preprocessing_backend: "FAC1_customop_PL"`、
`backend: "zg330_npu_pl_and_host"` 说的是**取帧通路和前处理／推理**在 PL，不指存储。页面文案也
只讲这个分工——首页正文写"PS 裁图 · NPU 双模型"，健康脚本按
`preprocessing_backend === 'FAC1_customop_PL'` 显示"上传与登记照片使用 PL 缩放和对齐、NPU 检测和
特征提取；PS 负责矩阵求解、归一化和比对"。即：**站点从未把 eMMC 标成 PL 端**。

### 怎么调用的（四层，命令原文）

| 层 | 动作 | 判据 |
|---|---|---|
| 引导 | 根文件系统不在 eMMC 上：`root=/dev/mmcblk0p2`（SD 卡的 p2），eMMC 只是数据卷 | `Kernel command line` 实测行 |
| 挂载 | 不由 fstab 管（`/etc/fstab` 只有出厂残桩＋一行注释"WCIS personnel eMMC: UUID-checked `wcis-face-storage.service`（vendor image has no udev）"）。systemd 单元 `Type=oneshot`＋`RemainAfterExit=yes`、`After=local-fs.target`、`Before=wcis-face-photo.service`、`TimeoutStartSec=90`／`TimeoutStopSec=30`，`ExecStart` 与 `ExecStop` 跑同一个脚本 `/root/wcis-face/tools/storage-5df5f1c1e614/mount_face_store.py --device /dev/mmcblk1p1 --mount /mnt/wcis-emmc --uuid 67104a06-74a6-4268-a124-269d1b232a28`（后者加 `--unmount`）——**每次关机卸载、每次开机才挂上** | 脚本顺序：设备名必须匹配 `/dev/mmcblk[0-9]+p[0-9]+` → 等节点最多 30 s → `stat` 必须是块设备 → `device/type` 必须是 `MMC` → `blkid -p -o export` 校 UUID 与 `ext4` → 已挂载则 `findmnt -J -T` 复核身份 → 挂载目录非空就拒（不把已有文件盖在挂载点下）→ `e2fsck -p` 只接受返回码 0／1 → `mount -t ext4 -o rw,nosuid,nodev,noexec,noatime,errors=remount-ro` → 挂完再核一次身份才打印 `Personnel eMMC filesystem mounted and verified`。本次启动该行为 `Oct 26 05:54:51 U.FMSH`。挂载机理与"某一次整块没被枚举"的取证在 [[硬件与基础运行环境档案#eMMC 挂载：机理与那次"没挂上"的真相]]，本页不重复 |
| 应用 | 录像服务不信任上游挂载，自己再校一遍：`Storage.__init__` 用 `findmnt -J -T` 比 `(target, uuid, fstype)` 三元组、要求 `--storage` 是挂载点**之下的独立子目录**（等于挂载点就报错）、记下 `st_dev`；此后每次列表／写／删前 `guard()` 比 `st_dev`（失败文案写死 `Recording storage unavailable; no SD fallback`）；写前 `admit()` 校配额与磁盘预留（各留 1 MiB 余量）；写完 `account()` 记账 | 现役单元 `wcis-face-recording.service` 的参数（`systemctl cat`）：`--storage /mnt/wcis-emmc/wcis-face/recordings --mount /mnt/wcis-emmc --uuid 67104a06-…`、`--quota-mib 4096`、`MemoryMax=192M`、`TasksMax=24`、`Restart=no`。代码侧校验见 [[板端我方代码与产物台账]] 登记的录像服务 |
| 文件系统 | 数据写 ext4（ordered data 模式），段先 `.part` 落盘、`fsync` 后改名，帧索引 `frames.jsonl` 与摘要 `rec-*.json` 同目录 | `EXT4-fs (mmcblk1p1): mounted filesystem with ordered data mode. Opts: errors=remount-ro` |

### 协商参数与带宽（含两处对不上）

本次实测读数：DT `dwmmc@e0044000` 有 `bus-width = <4>`、`max-frequency = <0x017d7840>`
＝25000000 Hz、`non-removable`、`no-sd`、`no-sdio`、`broken-cd`、`disable-wp`，且**没有**
`dmas`／`dma-names`（TF 那个节点 `e0043000` 有——这就是 dmesg 里 eMMC 走 PIO、SD 走外部 DMA 的
原因）。`/sys/kernel/debug/mmc1/ios`：clock 25000000 Hz、bus width 4 bits、timing spec 1
（mmc high-speed）、3.3 V；对照 `mmc0/ios`：clock 50000000 Hz、4 bits、timing spec 2。

按这组读数算 SDR 单沿上限：`25000000 * 4 / 8 = 12500000` B/s ＝ 12.5 MB/s（十进制）≈ 11.9 MiB/s。

- **冲突一**：[[状态源与决策记录]] 记的 eMMC 直写 **17.6／19.7 MB/s**（那条"口径澄清用的两个数"，
  两个数都引 D-44 证据 1）高于上面的 12.5 MB/s。二者至少一条不是 IO 时刻的真实设置——debugfs 的
  `ios` 很可能是空闲／时钟门控下的快照。**本次没跑 IO 基准**（另一个人正在用板子，测吞吐会干扰
  ta），带宽按**待核**处理：12.5 MB/s 与 23 MB/s 都别拿来容量或链路预算。
- **冲突二（归属）**：[[我方在板外设]] §7.5 那句"放 rootfs 会被 eMMC 的 23 MB/s 读速压死"是
  2026-10-05 的实测，但 rootfs 是 `/dev/mmcblk0p2` ＝ SD 卡；eMMC 的分区与文件系统是
  **2026-10-15** 才建的（板上取证 `candidates/emmc-20261015/filesystem.json` 的
  `formatted: true`、GPT p1 29.1 GiB、`boot_partitions_untouched: true`、`sd_untouched: true`），
  10-05 那次测的时候 `mmcblk1` 还不存在。所以那 23 MB/s 应归 SD 卡。此处只记事实差，改哪页由她定。
- 另一条**推断（B）**：手册标这颗是 8-bit 颗粒，而 DT 与 `ios` 都只有 4 bit，与"EMIO 只外扩了部分
  数据线"相符；要证实得看厂商 PL 工程的引脚约束。

### 它是怎么从"预期不可用"变成现役的

2026-10-15 一次部署同时换了两份文件，取证在板上 `candidates/emmc-20261015/`
（`deploy-config.json`／`deployment.json`／`final-state.json` 记 sha256 与备份名）：

| 文件 | 备份 | 换它做什么 |
|---|---|---|
| `BOOT.bin` | `FEC1015.BAK` | 内含 FSBL 与 PL 位流；位流槽边界与替换手法见 [[BOOTbin位流替换手术]] |
| `fmqlmp-verify.dtb` | `FDT1015.BAK` | 把 `dwmmc@e0044000` 从 `disabled` 改成 `okay` |

这正好落在 [[板载接口与内核改造收纳进dev]] 第六节预判的"缺 ②③"两层（设备树＋PL 逻辑）上。
PL 现在确实在跑：`/sys/class/fpga_manager/fpga0/state = operating`。

**需要更正的旧口径**（指过去，不在本页改）：[[板子（除芯片）]] 存储表的"**不可用（改造量大）**"、
[[状态源与决策记录]] 第 212 行与"到板必查"勾选框里的"预期**不可用**"——今天的结论是
**已可用并承载生产数据**（`/mnt/wcis-emmc` 上现有录像与人脸库）。

**芯片身份旁注（A，本次直读）**：运行 DT 的 `model = FMQLMP FMQL100TAI`、
`compatible = fmsh,fmsh-fmqlmp`，与库内登记的 FMQL30TAI／`FMQL30TAI676H` 口径不一致；本页只记
读数，是否更正登记由她定。
