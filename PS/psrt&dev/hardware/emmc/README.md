# PS / eMMC 专题 Wiki

> 目标机：`192.168.1.113`（`ssh root@192.168.1.113`，免密已配）
> 平台：复旦微电子 FMQLMP FMQL100TA（ARM Cortex-A53 ×4，1GB DDR）
> 内核：linux-5.4.52-fmsh
> 记录时间：2026-10-27 ~ 2026-10-29

---

## ⚠️ 先澄清一件事：这里说的"提频"不是 CPU 频率

本文所有"25MHz → 50MHz"**指的是 eMMC 控制器的 SDIO 总线时钟（`sdio1` ciu clock）**，和 CPU 主频毫无关系。

板上两条时钟链完全独立：

```
CPU   : armpll_int → armpll → armpll_clk   1 GHz   （无 cpufreq，锁定不可调）
外设  : iopll_int → iopl_clk → sdio_mux → sdio_div → sdio0/sdio1   100 MHz
```

- CPU 侧**没有 cpufreq 接口**（`/sys/devices/system/cpu/cpu0/cpufreq` 不存在），频率由 ARM PLL 硬件锁定，软件改不了，本方案也不会去碰
- SDIO 时钟挂在 **IO PLL（`iopll`）** 上，跟 ARM PLL 是两条独立分支
- 改 `max-frequency` 只影响 `sdio_div`/`sdio1` 这一支，**CPU 主频一个字都不会变**

证据见 [03-寄存器证据.md](03-寄存器证据.md) 第四节时钟树。

---

## 从零重启任务，先看这个

如果你要接手这件事，按下面顺序读，20 分钟能到当前进度：

| 顺序 | 文件 | 你会得到什么 |
|---|---|---|
| 1 | [01-结论汇总.md](01-结论汇总.md) | 所有结论一页看完：能不能开 DMA、频率多少、瓶颈在哪 |
| 2 | [02-硬件与数据通路.md](02-硬件与数据通路.md) | eMMC 的数据到底走不走 PL，PS-PL 怎么连 |
| 3 | [03-寄存器证据.md](03-寄存器证据.md) | 每条结论背后的原始寄存器值和解码 |
| 4 | [04-性能实测.md](04-性能实测.md) | 实测吞吐、CPU 开销、以及"CPU 是否随速度线性"的答案 |
| 5 | [05-DMA启用方案.md](05-DMA启用方案.md) | **部分执行**：50MHz ✅，8bit ✅不可用，DMA/永久 DTB 待做 |
| 6 | [06-磁盘清理清单.md](06-磁盘清理清单.md) | **2026-10-31 全量重刷**：三分区现读（`/` 用 19G／剩 5.9G）＋可清项＋"要点头才清"项（含 `/usr/lib/modules/*/build` 那 1.1G）＋共享板删东西的六条纪律 |
| 7 | [07-踩坑与注意事项.md](07-踩坑与注意事项.md) | 已知的坑，动手前必读 |

---

## 当前状态一句话

**卡完全不是瓶颈（EXT_CSD 实测支持 52MHz/HS200/HS400），控制器也支持外部 DMA，但设备树把 `max-frequency` 钉在 25MHz、`bus-width` 钉在 4-bit、没给 `dmas`，所以现在跑 PIO / 25MHz / 4-bit / 11.8 MB/s，已经吃满总线 94%。任何软件层优化都不会更快，唯一有效动作是把总线本身变快：先提时钟到 50MHz（×2），再考虑 8-bit。**

**进展（2026-10-30）：50MHz 时钟已运行时实测通过 ✅** —— 用 configfs overlay 把时钟实时切到 50MHz，写 22.9 / 读 23.7 MB/s（×2），16MB 随机写读回 md5 一致，dmesg 无错误，直播全程未受影响。**DMA 也已运行时实测 ✅** —— 补 `dmas=<0x0a 0x01 0x00 0x00>` 后驱动切到 `Using external DMA controller.`（CTRL 0x10→0x30），证明本板 req=1 请求线接好、厂商 `mmc1 not support dma` 注释是错的；DMA 不改吞吐只省 CPU。**50MHz+DMA 稳定性压测 ✅** —— ~3.7GB 持续负载下 md5 一致、0 新增错误、挂载有效。**8-bit 实测不可用 ✅**。当前 50MHz+DMA 是 configfs 临时态（重启回 25MHz/PIO），仅剩"固化进永久 DTB"。

---

## 目录结构

```
S:\work\WCIS\wiki\PS\emmc\
├── README.md                          ← 你在这里
├── 01-结论汇总.md
├── 02-硬件与数据通路.md
├── 03-寄存器证据.md                    ← 含 EXT_CSD 实测 + 完整寄存器 dump
├── 04-性能实测.md
├── 05-DMA启用方案.md                  ← 部分执行：50MHz 已实测，永久 DTB/8bit/DMA 待做
├── 06-磁盘清理清单.md
├── 07-踩坑与注意事项.md
├── overlay\
│   ├── mmc1-clock-overlay.dts         ← 时钟 25→50MHz
│   ├── mmc1-dma-overlay.dts           ← 启用 DMA
│   ├── mmc1-both-overlay.dts          ← 两者合并
│   └── *.dtbo                         ← 已编译产物（194/227/257 字节）
└── scripts\
    ├── 01-build-dtc.sh                ← 在目标机编 dtc
    ├── 02-bench-mmc.sh                ← 吞吐 + CPU 测量
    ├── 03-test-overlay.sh             ← 运行时启用 + 自动回滚
    ├── 04-apply-dtb-permanent.sh      ← 永久改 DTB（带校验和备份）
    ├── 05-preflight-overlay.sh        ← overlay 机制预检（零风险，已跑通）
    ├── extcsd_read.c                  ← 只读读 EXT_CSD（CMD8），已编译可用
    └── 99-rollback.sh                 ← 一键回滚
```

**原始证据在 `..\hardware\emmc_evidence\`**（统一归入硬件档案）：

| 文件 | 内容 |
|---|---|
| `fmqlmp-verify.dtb.orig` | boot 分区上的原始 DTB（16079 B） |
| `fmqlmp-verify.dtb.decompiled.dts` | 反编译出的权威设备树源码 |
| `registers-20261029.txt` | 所有寄存器原始读数 + 解码 |
| `bench-20261029.txt` | 三轮性能实测原始输出 |
| `probe-20261029-boot72a8f941.txt` | **只读全量探测**：卡片身份 + EXT_CSD 512B + 全寄存器 + 时钟链 + 启动日志 |
| `50mhz-test-20261030-bootdb887f8e.txt` | **50MHz 运行时实测证据**：dmesg + ios + CLKDIV=0x1 + 基准 + 服务状态 |
| `8bit-test-20261030-bootdb887f8e.txt` | **8-bit 实测证据**：`switch to bus width 8 failed` + 自动回退 4-bit + md5 一致 |
| `dma-test-20261030-bootdb887f8e.txt` | **DMA 实测证据**：CTRL 0x10→0x30 + dmesg "Using external DMA controller" + vendor 注释误注结论 |
| `stress-50mhz-dma-20261030-bootdb887f8e.txt` | **50MHz+DMA 稳定性压测证据**：~3.7GB 负载、md5 一致、0 新增错误、挂载有效 |

---

## 环境稳定性警告 ⚠️

**这块板子今天（2026-10-29）重启了 8 次**（boot -7 到 boot 0，UTC 12:12 → 13:43）。次日（2026-10-30 凌晨 3:36 起）又已在新 boot `db887f8e-201b-47ca-bbc4-396c53a176a3` 上运行。

- 本次所有测量数据都取自 boot `dace9468-2d7d-4d71-8767-b001caf6267a`（12:49:13 – 13:42:58 UTC）
- **后续新增的探测与基线数据取自 boot `72a8f941-237d-4679-aa9d-1184783b734e`（13:43 UTC 起）**
- **50MHz 实测数据取自 boot `db887f8e-201b-47ca-bbc4-396c53a176a3`（2026-10-30）**
- 按 `hardware/硬件与基础运行环境档案.md` 的纪律：**任何后续性能测量都必须记录 boot ID**，否则数据不可比

```bash
cat /proc/sys/kernel/random/boot_id
uptime -s
journalctl --list-boots | tail -5
```

**`/tmp` 是易失的**——重启后清空。编译好的 dtbo 已固化到：

- 目标机：`/root/emmc-overlays/`（`mmc1-clock.dtbo` / `mmc1-dma.dtbo` / `mmc1-both.dtbo`）
- 本仓库：`emmc/overlay/*.dtbo`

dtc 在 SD 卡上，重启不丢：`/root/home/lili/linux-5.4.52-fmsh/scripts/dtc/dtc`

---

## 已完成 vs 待完成

| 项 | 状态 |
|---|---|
| 磁盘占用诊断、缓存清理清单 | ✅ 完成（见 06） |
| PS-PL 数据通路确认（eMMC 不走 PL） | ✅ 完成（见 02） |
| 控制器 DMA 能力（读 HCON/CTRL） | ✅ 完成（见 03） |
| 当前频率/总线宽度确认 | ✅ 完成（见 03） |
| 吞吐 + CPU 开销实测 | ✅ 完成（见 04） |
| dtc 工具链在目标机就绪 | ✅ 已编出 `scripts/dtc/dtc` |
| overlay 源文件编译验证 | ✅ 227 字节 dtbo 已生成并反编译核对 |
| **EXT_CSD 读取（卡支持什么频率）** | ✅ **完成**：`DEVICE_TYPE=0x57`，52MHz/HS200/HS400 全支持（见 03 §6） |
| **卡健康度** | ✅ 完成：`PRE_EOL=0x01`、磨损 0~10%，几乎全新 |
| **干净基线复测（boot 72a8f941）** | ✅ 完成：11.4~11.9 MB/s，CPU 0.57% |
| **overlay 机制预检（零风险）** | ✅ **通过**：时钟/DMA 两个 dtbo 均能注入→生效→回滚，驱动不受影响，8MB 数据 md5 一致 |
| **50MHz 时钟运行时实测（boot db887f8e）** | ✅ **完成**：CLKDIV 0x2→0x1，写 22.9 / 读 23.7 MB/s（×2），md5 一致，无错误，直播未受影响 |
| **8-bit 总线实测** | ✅ **已完成**：不可用（`switch to bus width 8 failed`，驱动回退 4-bit，无损坏） |
| **临时启用 DMA 实测（boot db887f8e）** | ✅ **完成**：补 `dmas` 后驱动切 `Using external DMA controller.`（CTRL 0x30），证明 req=1 线接好、厂商注释错；吞吐不变只省 CPU |
| **50MHz + DMA 稳定性压测（boot db887f8e）** | ✅ **完成**：~3.7GB 持续负载，md5 一致、0 新增 eMMC 错误、挂载有效 |
| **永久改 DTB（固化 50MHz + DMA）** | ⬜ 待执行，configfs 重启即失效 |

---

## 一句话风险提示

| 操作 | 风险 | 说明 |
|---|---|---|
| 读寄存器 / EXT_CSD / sysfs / dmesg | **零风险** | 纯只读，不动硬件状态 |
| 跑 `dd` 测速（写临时文件再删） | **极低** | 已做过多次，卡磨损 0~10% |
| 加 `dmas` / 改 `max-frequency` + rebind | **中等** | 必须 `systemctl stop wcis-face-storage.service`（不是 `umount`！）；失败则 eMMC 消失到下次重启，**root 在 SD 卡上，不会变砖** |
| 永久改 boot 分区 DTB | **中高** | 改错会导致 eMMC 永久起不来，必须先备份并 diff 校验 |
| 热写 `HCON`/`CLKDIV` 寄存器 | **危险** | 绕过驱动改硬件状态，可能挂死控制器并损坏已挂载的 ext4。**不要做** |
| 改 CPU 频率 | **不可能** | 无 cpufreq 接口，硬件锁定 |

详细风险和对策见 [07-踩坑与注意事项.md](07-踩坑与注意事项.md)。
