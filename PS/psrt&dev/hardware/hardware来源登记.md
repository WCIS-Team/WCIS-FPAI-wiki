# hardware来源登记

SOP 2 硬件与基础运行环境信息采集——信息来源登记。本页只登记"某个数据是从哪里来的"，数据本身在 `device.json` / `system.json` / `software.json` / `resources.json` 里。

文件名从 SOP 2 第 6 节的建议值 `sources.md` 改为 `hardware来源登记.md`：本库页名必须全局唯一，而 `schoolhardware/`（校机归档）已占用 `sources.md`。目录 `hardware/` 与四个 JSON 的 SOP 2 交付结构不变。

- 档案版本：1.0
- 目标设备：192.168.1.113（内网开发板），用户 `root`，SSH
- 采集时间：2026-10-18T21:08:24Z（主采集）／2026-10-20T07:45:38Z 与 2026-10-20T07:49:07Z（两轮补采）
- 板端时区：`+0000`（板子时钟走 UTC；21:08:24Z 即本地 2026-10-19 05:08:24 +0800）
- 传输工具：PuTTY plink 0.85 / pscp 0.85（Windows x86_64）
- 采集脚本：`../collect.sh`、`../collect_followup.sh`、`../collect_gap3.sh`（三份都在 `../` 下，可复跑）
- 原始输出：`raw_logs/`（共 92 个文件 = 85 份命令输出 + 6 个时间戳文件〔三轮各 2 个〕+ 1 个 `.keep` 占位）

## 1. 官方资料（官方规格）

| 来源                   | 位置                                                                                              | 提供的内容                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 悟净开发板手册（完整版 / 轻量版）转档 | `../board_extract/41_manual_full_extracted.txt`、`../board_extract/40_manual_lite_extracted.txt` | 芯片概述、PS/PL DDR3 容量与带宽、QSPI FLASH、以太网与 USB 路数、PL 时钟、125K 可编程逻辑                             |
| 板卡规格表（本仓库自著页）        | `../psdev.md`                                                                                   | FMQL30TAI 完整版与 JFMQL30TAI676H 轻量版两张规格表：算力、缓存、FPGA 资源、封装、功耗                                |
| 出厂设备树源文件             | `../board_extract/29_dts_fmqlmp-verify.dts`                                                     | `vpu: mve@F0020000` 节点定义（`compatible = "arm china,linlon-v5"`）、`operating-points-v2` 被注释掉 |
| 出厂设备树二进制展开           | `../board_extract/35_dtb_flattened_shipped.txt`                                                 | `l2-cache` 节点只有 `compatible` 与 `phandle`，无 `cache-size`                                   |
| 出厂 DTB 节点状态表         | `../board_extract/36_dtb_node_status.txt`                                                       | 各外设节点 status 与 compatible：mve / mali_gpu / dma / ethernet / usb / can / spi / i2c / gpio  |
| 启动环境变量               | `../board_extract/37_boot_uEnv.txt`                                                             | `bootargs`（含 `mem=1024M`）、`loadbit`（从 mmc 0:2 加载 `download.bit` 到 PL）                     |
| 镜像文件系统快照             | `../board_extract/26_system_identity.txt`                                                       | 镜像内 hostname / machine-id / os-release / rc.local / 已启用服务                                 |

## 2. 现场采集（系统报告 / 工具报告 / 现场测量）

以下全部是本机经 SSH 在 192.168.1.113 上实跑命令得到的原始输出，原始文件在 `raw_logs/`。文件名即 `device.json` / `system.json` / `software.json` / `resources.json` 里 `evidence` 字段引用的目标。

### 2.1 设备身份与 OS

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| 主机名 | `hostname.txt` | `U.FMSH` |
| machine-id | `machine_id.txt` | `c18338d14c3049b3ab6cdaed8c0ee749` |
| 内核 | `uname.txt`、`kernel.txt`、`dmesg_full.txt` | `5.4.52`，完整构建串 `5.4.52-fmsh-sdk-v2025.04`，构建日 2026-03-13，gcc 7.5.0 Linaro |
| 发行版 | `os_release.txt` | Ubuntu 20.04.4 LTS (focal) |
| 设备树型号 | `dt_model.txt`、`dt_serial.txt` | `FMQLMP FMQL100TAI`，`compatible = fmsh,fmsh-fmqlmp` |
| 容器判定 | `init_container.txt`、`cgroup_v2.txt` | 无 `/.dockerenv`、无容器挂载标记，PID 1 = systemd ⇒ 裸板 |
| 启动命令 | `dmesg_full.txt` | `mem=1024M`，`root=/dev/mmcblk0p2` |

### 2.2 CPU 与缓存

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| CPU 型号与拓扑 | `lscpu.txt`、`cpuinfo.txt`、`nproc.txt`、`cpu_topology.txt` | Cortex-A53 ×4，1 socket，4 线程/核，online 0-3，implementer 0x41 / part 0xd03 / r0p4 |
| 频率 | `cpu_freq.txt`、`cpu_freq_dtb.txt`、`cpu_clock.txt` | 无 cpufreq、无 `cpu_opp_table`、无 `clock-frequency` ⇒ 频率不可上报 |
| 缓存结构 | `cache_sizes.txt`、`cache_shared.txt` | index0 L1D / index1 L1I / index2 L2 Unified；L1 `shared_cpu_map=1`，L2 `shared_cpu_map=f`；size 属性缺失 |
| 温度 | `thermal.txt`、`cpu_temp.txt` | 平台无 thermal zone |
| 电源管理 | `mtd_flash.txt`（dmesg grep）、`../board_extract/35_dtb_flattened_shipped.txt` | cpuidle governor = menu；PSCI cpu-sleep-0 |

### 2.3 内存与存储

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| 内存总量与可用 | `meminfo.txt`、`free.txt`、`mem_avail_sys.txt` | MemTotal 1017704 kB（993 MiB），MemAvailable 721084 kB |
| Swap | `swap.txt`、`free.txt` | `/swapfile` 文件型 1 GiB，已用 0 B |
| zram | `zram.txt` | 未启用 |
| CMA | `dmesg_full.txt`、`meminfo.txt` | 256 MiB @ 0x30000000，CmaFree 130784 kB |
| 挂载与容量 | `df.txt`、`findmnt.txt`、`lsblk.txt`、`partitions.txt` | 根分区 ext4 26.1 GiB（78-80% 已用）；`/mnt/wcis-emmc` 在第一批挂载、第三批未挂载 |
| eMMC 挂载机制（追查轮） | 现场 SSH 复查：`systemctl cat wcis-face-storage.service`、`cat /etc/fstab`、`journalctl --list-boots`、`journalctl -u wcis-face-storage.service`、`journalctl -k -b -4/-5/-3`、`blkid /dev/mmcblk1p1`、`stat` 单元与脚本 | 挂载由 `wcis-face-storage.service`（oneshot+RemainAfterExit，带 UUID 校验）管，**不由 fstab 管**；第三批未挂载的那次启动里 eMMC 根本没被枚举 |
| 介质识别 | `dmesg_full.txt` | mmcblk0 = SD 58.4 GiB；mmcblk1 = Y2P032 eMMC 29.1 GiB |
| QSPI NOR | `mtd_flash.txt` | cadence-qspi，`n25q256a` 32768 Kbytes；mtd0 bootloader 4 MiB / mtd1 kernel 16 MiB / mtd2 rootfs 0 |
| u-dma-buf 池 | `dmesg_accel.txt` | 版本 3.2.5，128 MiB @ 0x30100000 |
| hugetlb / shm | `hugepages.txt` | 各尺寸类均 free=0；`/dev/shm` 497 MiB tmpfs |

### 2.4 加速器

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| NPU 设备树节点 | `35_dtb_flattened_shipped.txt` | 全文搜 `npu`／`aiu`／`zhuge`／`icore`，**0 命中**——现场没有 NPU 的设备树节点（2026-10-23 更正，D-79） |
| VPU 驱动 | `dmesg_accel.txt` | `MVX dev: Linlon v5276 identified. cores=2, nlsid=4, id=0. (mvx_dev.c:427)` |
| VPU 平台设备 | `npu_platform.txt` | `f0020000.mve` 已注册；内核线程 `mvx_sched`、`kworker/u8:3-f0020000.mve` 在跑 |
| VPU 设备节点 | `npu_dev.txt`、`dev_list.txt` | 采集时记成"无专用 `/dev` 节点，走 `/dev/udmabuf0` + `amvx`"——**这一条对 VPU 是错的**（`/dev/video0` 在位，见 2026-10-05 §15）；那句只对 NPU 成立 |
| VPU 固件 | `58_rootfs_system_config.txt` | `/lib/firmware/linlon-v52_v76-80-2/` 17 个 `.fwb`，全是视频 codec |
| GPU 驱动 | `dmesg_accel.txt`、`mali_gpu.txt` | Mali DDK `r31p0-01eac0`，GPU id 0x2，arch 7.4.0 r1p0，`/dev/mali0` 存在，coherency mode 31 |
| GPU 显存 | `mali_gpu.txt` | sysfs 未公布容量，debugfs gpuinfo 为空 ⇒ unknown |
| FPGA | `fpga_detail.txt`、`fpga_bitstream.txt` | `fpga_manager fpga0`，name `FMSH FMQL FPGA Manager`，state = **operating**，device → `e0040000.devcfg`；固件属性只写不读 |
| DMA | `dmesg_accel.txt` | `dw_dmac e004b000.dma` 8 通道 + `dw_axi_dmac_platform f0010000.dma` 8 通道 |
| PCIe | `pci_sysfs.txt`、`lspci.txt` | `/sys/bus/pci/devices` 为空，`lspci` 未安装 ⇒ 无任何 PCI 设备枚举 |

### 2.5 软件与运行时

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| Python | `python.txt` | Python 3.8.10；无 `python` 别名，无 python2 |
| pip | `pip.txt` | pip 20.0.2；icraft 3.39.0 / numpy 1.23.0 / opencv-python 4.6.0.66 / Pillow 9.3.0 / tflite-runtime 2.10.0 / tokenizers 0.13.3 |
| 编译器 | `gcc.txt`、`cmake.txt` | gcc/g++/cc 9.4.0 (Ubuntu 9.4.0-1ubuntu1~20.04.2)，cmake 3.16.3 |
| 包管理 | `pkg_mgr.txt`、`dpkg_count.txt` | apt / apt-get / dpkg / pip 在；无 conda / yum / dnf；dpkg -l 共 566 行 |
| Icraft CLI | `icraft.txt` | Icraft v3.39.0，CLI `3.39.0.0-431be90(2608220046)` |
| Icraft 用法 | `icraft_backend.txt` | `icraft <command> [config.toml] ...`；`icraft device list` 不是合法子命令 |
| NPU 用户态库 | `inference_fw.txt` | `libicraft_zg330backend.so`、`libsocketzg330aiu.so`、`libaxizg330aiu.so`、`libmockzg330.so`、`libcustomop.DetPostZG.so` 等 12 个 |
| 厂商 deb | `dpkg_vendor.txt` | icraft 3.39.0 / customop 3.39.0 / icraftmdzthirdparty 0.1.1（均 arm64） |
| 内核模块 | `lsmod.txt`、`npu_module.txt` | amvx、mali_kbase、u_dma_buf |
| 环境变量 | `env_vars.txt` | 仅 PATH 与 DBUS_SESSION_BUS_ADDRESS；无 OMP/MKL/OPENCL/CUDA/ICRAFT 相关变量 |

### 2.6 运行限制与后台负载

| 数据 | 原始日志 | 关键读数 |
| --- | --- | --- |
| cgroup 限制 | `cgroup_self.txt`、`cgroup_v2.txt`、`findmnt.txt` | v1/v2 的 `memory.max`、`cpu.max`、`pids.max` 均不存在 ⇒ 无限制 |
| ulimit | `ulimit.txt`、`fd_limit.txt` | open files 1024/1048576，max processes 2948，locked memory 64 MiB，stack 8 MiB |
| 内核上限 | `nproc_limits.txt` | threads-max 5897，pid_max 4194304，somaxconn 4096 |
| 网络 | `net_addr.txt`、`net_link.txt`、`net_sysfs.txt`、`net_ethtool.txt`、`net_route.txt` | eth0 `ae:59:f4:2d:3a:99`，`192.168.1.113/24`，网关 192.168.1.1，MTU 1500，**协商结果 100 Mb/s Full**，MAC 支持并广播 1000baseT |
| 后台负载 | `ps_snapshot.txt`、`ps.txt`、`loadavg.txt` | `wcis_sdi_vpu_li` 占 8.7% CPU / 32.5 MB RSS（跑了 56 分钟），另有两个 python3；总线程数 109 |

## 3. 交叉验证结论

| 关键项 | 官方规格 | 现场实测 | 判定 |
| --- | --- | --- | --- |
| CPU 核心数 | 4 核 | 4 物理 / 4 逻辑 / 4 可用，无 SMT | 一致 |
| CPU 主频 | 最高 1 GHz | 平台不上报（无 cpufreq / 无 OPP 表） | 未验证 |
| L1 / L2 缓存 | 32KB+32KB / 1MB | 结构可见（层级、类型、共享关系），容量不上报 | 规格采信，现场未验证 |
| 内存总量 | PS 侧 1GB DDR3 | 993 MiB（`mem=1024M` 预留内核） | 一致 |
| PS DDR 类型与带宽 | DDR3，1600MHz×32bit = 51.2 Gbps | 未读出控制器配置，未测带宽 | 规格采信，现场未验证 |
| PL 侧 DDR | 2GB DDR3 | PS 内存树中不可见 | 现场不可验证 |
| DMA 通道 | 8 通道 | 两个控制器各 8 通道 | 一致 |
| NPU 架构 | 1 个 ZG330 iCore | 现场无设备树节点（`npu`／`aiu`／`zhuge`／`icore` 全文 0 命中）、无内核模块、无 `/dev` 节点；用户态 12 件 ZG330 库在位 | **无法与现场交叉验证**（原判"一致"依据的是 VPU 的日志，2026-10-23 更正，D-79） |
| VPU 架构 | 规格表未列 | 设备树 `arm china,linlon-v5`，驱动识别 Linlon v5276 / 2 cores / nlsid 4，即 `/dev/video0` 那颗视频编解码器 | 规格表未列，现场在位 |
| NPU 算力 | 8 TOPS INT8 等 | 未跑负载 | 未验证（仅规格） |
| FPGA 资源 | 125K 逻辑 / 78,600 LUT / 9.3Mb BRAM / 400 DSP | 仅确认 manager 处于 operating；**无占用量工具报告** | 规格采信，占用量未验证 |
| QSPI FLASH | 256Mb | n25q256a 32768 Kbytes = 256 Mbit | 一致 |
| 以太网 | 1 路 10/100/1000Mbps | DWMAC1000 控制器，协商 100 Mb/s Full | 控制器一致，链路速率为现场实测 |
| TF 存储 | 32GB TF-CARD | 装的是 58.4 GiB SD 卡；另有 29.1 GiB eMMC | 与规格文档不符，以现场为准 |
| PCIe | Gen2 x4（完整版）/ x1（轻量版） | 无任何 PCI 设备枚举 | 未验证 |

## 4. 待确认事项

1. **型号不一致**：设备树自报 `FMQLMP FMQL100TAI`，而本仓库手册针对的是 `FMQL30TAI` / `JFMQL30TAI676H`（悟净）。两者关系（芯片步进差异、SKU 改名、还是不同产品线）需向复旦微确认；在确认前，手册里的 FPGA 资源与算力数字只应视为"FMQL30TAI 的官方规格"，不能直接当作本板的实测规格。
2. **FPGA 占用量**：手册给的是器件容量，不是当前 bitstream 的实际占用。需要一份来自厂商工具的 utilization 报告才能填上 SOP 3.4 要求的"设计实际占用"，本档案刻意留空。
3. **CPU 实际主频**：需厂商提供 OPP 表或固件侧频率方案；当前内核配置无法上报。
4. **以太网为何协商到 100M**：MAC 支持并广播 1000baseT，但对端只广播 10/100，链路 partner 侧需要查。
5. **`/mnt/wcis-emmc` 挂载不稳定**：第一批挂载、第三批未挂载，做实验文件存放前需确认。**追查结论**：不是挂载机制不稳——挂载由 `wcis-face-storage.service` 带 UUID 校验管理，每次开机必挂、每次关机必卸；第三批那次启动里 eMMC 压根没被枚举（服务零日志、内核无 mmcblk1、串口同时丢失、以 FAT 未正常卸载的硬复位收尾）。真问题是**采集期间板子今早重启了 8 次**（journal boots -7..0，06:17→13:12），"挂不挂得上"取决于落在哪次启动。附带一条待处理：SD 卡启动分区 `FAT-fs (mmcblk0p1): Volume was not properly unmounted ... Please run fsck.`，需一次 fsck（rootfs 同在这张卡）。
6. **NPU 无设备节点**：用户态通过 u-dma-buf + amvx 走，部署前应确认 icraft 的 config.toml 写法与所需权限。

## 5. 采集纪律声明

- 全程只读：未改配置、未重启、未终止任何进程或服务、未跑任何 benchmark 或推理、未采集密码/令牌/私钥。
- 未采集敏感信息；`rc.local` 等可能含凭据的文件未整份抓取，网络身份只取 `ip addr` 公开字段。
- 登录口令仅用于本次 SSH 认证，未写入任何文件、日志或本档案。
- 未把硬件信息推导为模型性能结论；所有算力数字要么标 `官方规格`，要么标 `未测量`。

## 相关页面

- [[硬件与基础运行环境档案]]
- [[硬件与基础运行环境信息采集]]
- [[psdev]]
- [[板端提取件台账]]
- [[板端我方代码与产物台账]]
