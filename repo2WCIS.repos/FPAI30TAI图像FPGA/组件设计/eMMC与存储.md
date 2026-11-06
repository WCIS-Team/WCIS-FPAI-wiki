# eMMC与存储

> 依据：`patches/emmc-sdio1-20261015.patch`、`patches/emmc-interface-budget-20261015.xdc`、`docs/emmc-source-manifest.json`、`docs/face-emmc-store-20261015.md`、`scripts/mount_face_store.py`、`npu_photo/persistent_gallery.py`、`release/540p-r2/`。只写设计与实现。

## eMMC 硬件接入（PL 引脚经 EMIO 到 PS SDIO1）

**定位**：板上 32 GB eMMC（Y2P032，实测报告 31,268,536,320 B ≈ 29.1 GiB）物理接在 PL Bank13 引脚上；设计目标是让 Linux 原生 MMC 栈管理它，而不是在 PL 里自造存储控制器。

**结构与接口**：

- 关键取舍是**信号路径走 PS 的 SDIO1 控制器、引脚经 EMIO 从 PL 出**：PS7 块设计新增 `SDIO_1_0` 接口（`xilinx.com:interface:sdio_rtl:1.0`，Master 模式），并打开 `PCW_EN_SDIO1`、`PCW_SD1_SD1_IO=EMIO`、`PCW_EN_EMIO_SDIO1/CD/WP`（`patches/emmc-sdio1-20261015.patch:17-19`、`:155-176`、`:205-221`）。SDIO1 控制器基址 0xE0101000（`patch:218-222`）。
- PL 侧只做电气桥接：`ps_ai_wrapper.sv` 为 cmd/data 生成 IOBUF + PULLUP，`emmc_reset_n` 直接恒 1，PS7 的 `SDIO_1_0_*` 端口接这些 IOBUF（`patch:486-501`）；顶层 `ai7030_edif_top.v` 增补 `emmc_clk/emmc_cmd/emmc_data[3:0]/emmc_reset_n` 端口（`patch:424-444`）。
- 引脚按硬件手册第 23 页原理图逐球核对（Bank13，VCCO 1.8 V）：CLK=AA20、CMD=AA19、RESET_n=AB19、D0/D1=AA18/AC18、D2/D3=W19/W18，全部 LVCMOS18 + SLEW SLOW（`patches/emmc-sdio1-20261015.patch:513-528`、`docs/emmc-source-manifest.json:44-53`）。

**特色设计**：

- 初始档位刻意保守：4-bit、SDR、最高 25 MHz（`docs/face-emmc-store-20261015.md:50-51`、`docs/source_manifest.json` 的 `emmc_bus_width:4`、`emmc_max_hz:25000000`），先保证功能与重启持久性，不上 DDR/HS200/HS400。
- 时序预算显式声明为"临时保守预算，不是器件特性化"：`emmc_sdr25` 时钟 40 ns 周期、1 ns uncertainty、输入 max 20 ns/min 0 ns、输出 +5/−5 ns（`patches/emmc-interface-budget-20261015.xdc:1-11`）；时钟直接定义在 PS7 的 `EMIOSDIO1CLK` 引脚上，让 PS7 经 EMIO 的 SDIO 输出也有可分析路径。
- 补丁以"原文件/候选文件"双份 SHA256 记录在 `docs/emmc-source-manifest.json:4-41`，只动 BD/顶层/wrapper/XDC 四处，不改 SDI、DDR、AI_Mate/NPU、FAC1 与 SD 启动接口；设备树也只改 `/amba-apu@0/dwmmc@e0044000` 一个节点（4-bit、25 MHz、non-removable），其余属性逐项核对不变（`docs/face-emmc-store-20261015.md:71-74`）。

**关键参数**：4-bit / SDR25 / LVCMOS18 / SLEW SLOW；`SDIO_1_0_cdn/wp` 恒 0（无卡检测/写保护脚，`patch:500`）；未访问 eMMC boot0/boot1 写接口（`docs/face-emmc-store-20261015.md:86`）。

## 分区、挂载与启动前置

**定位**：SD 卡管启动与系统，eMMC 专供数据；挂载身份校验是识别服务的启动前置条件。

**结构与接口**：

| 项 | 值 |
|---|---|
| SD | `/dev/mmcblk0`，p1 启动分区（BOOT/DTB/uEnv），p2 根文件系统（`docs/face-emmc-store-20261015.md:12`） |
| eMMC | `/dev/mmcblk1`，专用数据分区 `/dev/mmcblk1p1`，ext4，UUID `67104a06-74a6-4268-a124-269d1b232a28`（`docs/face-emmc-store-20261015.md:13-16`） |
| 挂载点 | `/mnt/wcis-emmc`，挂载选项 `rw,nosuid,nodev,noexec,noatime,errors=remount-ro`（`scripts/mount_face_store.py:59-61`） |
| systemd | `wcis-face-storage.service` 负责挂载，`ExecStop` 卸载；识别服务 Requires/After 它（`docs/release-source-map.md:77`、`docs/face-emmc-store-20261015.md:84`） |

**特色设计（mount_face_store.py 的无 udev 挂载协议）**：

- 厂商镜像没有 `systemd-udevd.service`，`/dev/disk/by-uuid/` 不存在，fstab UUID 项不可用；因此挂载不走 fstab/udev，由专用服务在识别服务之前执行 `mount_face_store.py`（`docs/face-emmc-store-20261015.md:78-84`）。
- 五重身份防线（`scripts/mount_face_store.py`）：
  1. 设备名必须匹配 `/dev/mmcblk[0-9]+p[0-9]+`，挂载点必须绝对路径且不是根/符号链接（`:27-30`）；
  2. 等待设备出现（30 s 有界），并经 `/sys/class/block/*/device/type` 确认确为 `MMC`（`:33-40`）；
  3. `blkid -p -o export` 核对 UUID 与 `TYPE=ext4`，不匹配即拒绝（`:41-44`）；
  4. 已挂载时用 `findmnt` 核对目标与 UUID，防止别的文件系统占用挂载点；挂载前目录必须为空，拒绝"把现有文件藏到挂载后面"（`:45-55`）；
  5. 只做受限 `e2fsck -p`（返回码 0/1 才放行，需要人工修复就失败退出），永不分区/格式化、永不回落 SD（`:56-61`、模块 docstring `:1-5`）。
- 挂载后再次 `findmnt` 复核 UUID 与目标一致才报告成功（`:62-66`）。

## 人员库布局与数据管理

**定位**：`PersistentGallery` 在 ext4 上做"特征 + 每人一张原图"的原子持久库；PS 内存缓存特征中心，正常识别不触盘。

**结构与接口**（`npu_photo/persistent_gallery.py`）：

- 库根按模型指纹分桶：`storage_root / sha(models.json)[:16]`，换模型精度/配置即换库目录，避免混用特征（`persistent_gallery.py:63-66`）。
- 目录布局：`gallery.json`（人员 + 512 维特征记录）、`originals/`（每人一张代表原图，按实际图像类型回 MIME）、`gallery.lock` 文件锁（`:65`、`:109-115`、`:80-85`）。
- 写入协议 `save_durable`：同目录写 pending → `fsync` 文件 → `os.replace` 原子改名 → `fsync` 目录（`sync_directory`），保证崩溃后要么旧库要么新库（`:24-46`）。

**特色设计**：

- **缓存与持久分层**：特征中心在 PS RAM，"原子更新后刷新缓存；正常识别不反复从 eMMC 读取特征正文，也不读取登记原图、不重跑登记模型"（`docs/face-emmc-store-20261015.md:23-25`、`persistent_gallery.py:98-100` 的 templates 注释）。存储位置变更因此不等于推理加速。
- **孤儿恢复**：`_recover_orphans` 只清理 `originals/` 目录内不被数据库引用的文件，绝不越界删除（`:117-128`）。
- **保存/删除规则**：同名追加只存新增向量；首张原图永久保留为代表图，直到删最后一份特征或删整个人员；登记的临时工作目录在成功/无效/失败路径均清理，写完才释放忙碌状态（`docs/face-emmc-store-20261015.md:29-35`）。
- **回退边界**：原 SD 库 `/root/wcis-face/galleries/...` 保留为回退副本但不再现役；回退前必须先保存 eMMC 上的新增登记增量（`docs/face-emmc-store-20261015.md:37-40`、`:109-110`）。

## 录像存储

**定位**：eMMC 第二数据面——独立录像服务把 H.264 码流 remux 成 MP4 落盘。

**结构与接口**（`npu_photo/recording_service.py`）：

- 存储 `/mnt/wcis-emmc/wcis-face/recordings`，同样强制挂载 UUID/设备校验、禁止掉挂载后回落 SD（`docs/face-recording-20261026.md:12`）。
- 配额：4 GiB 上限 + 512 MiB 磁盘预留，达到限制停止并保留已有录像，不自动删除（`recording_service.py:44`、`:72-73`）。
- 分段：默认 60 s 或 256 MiB 切段；写 `.part` 临时文件，完成时 fsync 后改名，最后提交 `.json` 完成记录；只向网页列出已提交录像，异常残片不冒充完整录像（`recording_service.py:153-154`、`docs/face-recording-20261026.md:10-11`）。
- 格式演进：MJPEG（帧拼接 + 时间索引 JSONL）→ 现役 H.264 码流 `-c:v copy` remux MP4（`recording_service.py:124`、`docs/face-recording-20261026.md:13`）。

**特色设计**：

- 录像服务**不持有 SDK/PL/VPU**：从现役 owner 的帧发布接口取已编码码流，独立 systemd 单元 8093，与识别服务解耦（`docs/engineering-flow-architecture-20261031.md:49`、`docs/face-recording-20261026.md:7`）。
- 闲时压缩（`npu_photo/recording_compression.py`）：连续空闲 60 s 才启动，录像写入/前台读取/CPU 忙碌 >15% 或 load >0.8 即暂停；FFmpeg `libx264` CRF 18，taskset 定核 + nice 19 + 每秒最多 0.15 s 的 duty 限流；只保留缩小 ≥10%、帧数/尺寸一致、逐帧 PTS 差 ≤1 ms、SSIM ≥0.98 的副本，原片永不改写（`docs/recording-idle-compression-20261031.md:15-18`）。
- 页面存储视图区分"有效录像/回收站/未完成文件/配额/磁盘剩余/可录空间"；回收站软删除占空间，确认永久删除才释放（`docs/recording-storage-20261027.md`、`docs/recording-management-20261027.md`）。

## 为什么不是 PL 自主读文件

这是本组件最核心的设计决策，三条理由都有源码依据：

1. **控制器归属**：eMMC 引脚虽在 PL Bank13，但设计把协议控制器固定为 PS 的原生 SDIO1（EMIO 引出），PL 只提供 IOBUF/PULLUP 电气桥（`patches/emmc-sdio1-20261015.patch:486-501`）。文件系统、ext4 一致性、e2fsck、 wear-leveling 全部交给 Linux MMC 栈，PL 不实现任何命令状态机。
2. **数据通路分工**：PL 的存储类访问走两条已验证的显式通道——FAC1/JPEG CustomOp 的 512 位 PL-DDR 端口（地址/长度/重叠检查 + 描述符锁定，`docs/face-pl-integration-20261015.md:29-47`）和 PS UDMA 帧缓冲；块设备语义（JSON 库、MP4、配额、回收站）留在 PS。`docs/source_manifest.json` 明确记录 `pl_autonomous_storage: false`、`ps_filesystem_managed: true`。
3. **身份与安全边界**：挂载身份（UUID/类型/sysfs MMC 归属）是识别服务的启动前提，fail-closed 不回落 SD（`scripts/mount_face_store.py:27-66`）；若 PL 能自主读文件，这条"先验明存储身份再开模型"的链就被绕过了。识别用的特征中心在 PS RAM（`persistent_gallery.py:98-100`），识别路径本来就不需要 PL 读盘。
