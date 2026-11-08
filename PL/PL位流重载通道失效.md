# PL位流重载通道失效

本页记 2026-10-10 这一轮的取证结论：**厂商提供的三条 PL 位流运行时重载通道，在这块板子上全部失效——而且用厂商自己那份已知可用的位流去测，同样失效。**

这不是我们位流的问题。**这是可以直接发给厂商的问题单**，问法、数据、对照实验都在下面。取证标记沿用 [[官方demo时序基线与器件库补丁]]：**A** = 正本/实测，**B** = 推断，**C** = 边界或未取证。

**一句话：`fpga loadb`／`fpga load` 在 u-boot 里返回 `Error 1`（`fpga info` 显示 `No Device Function Table.`），Linux 侧 `fpga_manager` 的 firmware 路径返回 `Timeout waiting for PCFG_DONE`，而出厂 `uEnv.txt` 里那条 `loadbit` 指向的是一个 `fatload` 根本读不到的分区。我们没有 JTAG，因此目前没有任何一条可用通道能把自己出的位流写进 PL。**

---

## 一、被测对象与环境（A，全部现场实测）

| 项 | 值 | 来源 |
|---|---|---|
| 板型 | **FMQL30TAI** | U-Boot 自报 `CPU: FMQL Plus FMQL30TAI, Revision Code:9` |
| 设备树型号字符串 | `FMQLMP FMQL100TAI` | `/proc/device-tree/model`，**厂商没改，与真实型号不符** |
| 器件 | `7z030ffg676` | 位流头 `b..7z030ffg676` |
| 内核 | `5.4.52-fmsh-sdk-v2025.04 #3 Fri Mar 13 13:44:29 CST 2026` | `uname -a` |
| U-Boot | `2020.07-gd24dcccd-dirty (Oct 31 2025 - 14:58:27 +0800)` | 串口 |
| ATF | `BL31: v2.3():44391da-dirty`，Built `Dec 10 2025` | 串口 |
| FSBL | `Version: 4.51` / `Procise SVN 31684` / Build `Dec 10 2025 20:29:22` | 串口 |
| 引导分区 | `/dev/mmcblk0p1`，**FAT16**，卷标 `NO NAME`，512 MB | `mount -t vfat` |
| 根分区 | `/dev/mmcblk0p2`，ext4，14 GB | `/proc/mounts` |
| 控制台 | **UART0 `serial@e0004000` = `ttyPS0`，In/Out/Err 三者同口** | 串口 `In: serial@e0004000` |

### 我们要刷的位流（A）

```
ai7030_full_pd1_20261009_201512.bit   5 980 029 B
头部：ai7030_edif_top;UserID=0XFFFFFFFF;Version=2018.3.1; b 7z030ffg676 c 2026/10/09 d 20:14:59
综合：synth_design Complete!   实现：write_bitstream Complete!
时序：WNS +0.104 ns，TNS 0，51 904 个端点 0 失败
```

---

## 二、三条通道，逐条实测（A）

### 通道 1：U-Boot `fpga loadb`（出厂 `uEnv.txt` 指的那条）

出厂环境变量原文：

```
bootcmd=run loadbit; run uenvcmd
loadbit=mmc rescan && fatload mmc 0:2 0x10000000 download.bit && fpga loadb 0 0x10000000 $filesize
```

**先说一个与位流无关的独立缺陷：`fatload mmc 0:2` 读不到东西。** 分区 2 是 `root=/dev/mmcblk0p2` 那个 **ext4** 分区，`fatload` 只认 FAT。位流该放的是分区 1（FAT16，U-Boot 的 `uenvcmd` 里 `fatload mmc 0:1 … Image` 就是证明）。

我们把它改成 `fatload mmc 0:1 0x10000000 video_only.bit` 后，`fatload` 本身**成功**：

```
fmsh> fatload mmc 0:1 0x10000000 video_only.bit
5979868 bytes read in 251 ms (22.7 MiB/s)
fmsh> fpga loadb 0 0x10000000 5979868
Command 'loadb' failed: Error 1
```

**但 `fpga loadb` 失败。** 于是我们把 U-Boot 拉进提示符（`Hit any key to stop autoboot`），做了对照实验 —— **换成板子自己那份 `ai7030_top_disable_icap.bit`（2025-12-30，出厂同款）**：

```
fmsh> fatload mmc 0:1 0x30000000 ai7030_top_disable_icap.bit
5980604 bytes read in 393 ms (14.5 MiB/s)
fmsh> fpga loadb 0 0x30000000 5980604
Command 'loadb' failed: Error 1
```

**A：厂商自己那份位流，一样 `Error 1`。所以与位流无关。**

设备描述符（`fpga info`）：

```
fmsh> fpga info
FMSH Device
Descriptor @ 0x000000003ffdc440
Family:        	FMQL PL
Interface type:	Device configuration interface (FMQL)
Device Size:   	5979916 bytes
Cookie:        	0x0 (0)
Device name:   	FMQL30TAI
No Device Function Table.
```

**`No Device Function Table.` 是要害** —— `u-boot/common/fpga.c` 的 `fpga_lookup_fn()` 找不到该设备的函数表。

### 通道 2：U-Boot `fpga load`

`load` 与 `loadb` 的差别是：`loadb` = "Load device from bitstream buffer (Xilinx only)"，`load` = "Load device from memory buffer"。两条都试了：

```
fmsh> fpga load 0 0x10000000 5979868
Command 'load' failed: Error 1
```

`load` 会阻塞很久（数十秒）才返回，所以现场一度像是挂死；实际是超时返回。**A：`load` 与 `loadb` 同样 `Error 1`。**

### 通道 3：Linux 侧 `fpga_manager` firmware 加载

驱动是内建的，且注册成功：

```
dmesg: [1.589056] FPGA manager framework
dmesg: [1.592554] fpga_manager fpga0: FMSH FMQL FPGA Manager registered
/proc/misc: 61 fpga0          →  /dev/fpga0  是 crw 10:61
/sys/class/fpga_manager/fpga0/  属性：device firmware flags key name of_node power state status subsystem uevent
```

按标准 firmware-loader 用法放文件再写 `firmware` 属性：

```
fmsh> # mount ... ; cp video_only.bit /lib/firmware/
root@…: echo video_only.bit > /sys/class/fpga_manager/fpga0/firmware
dmesg: fpga_manager fpga0: writing video_only.bit to FMSH FMQL FPGA Manager
dmesg: fpga_manager fpga0: Invalid bitstream, could not find a sync word. Bitstream must be a byte swapped .bin file
```

第一次报"找不到同步字"。我们按它说的做了字节序转换（Zynq 位流在 BOOT.bin 里按 **32 bit 字字序翻转**存放，见 [[板卡镜像实测取证]]），生成 `66 55 99 AA …` 开头的 `.bin` 再试：

```
dmesg: fpga_manager fpga0: writing video_only.bin to FMSH FMQL FPGA Manager
dmesg: fpga_manager fpga0: Timeout waiting for PCFG_DONE
dmesg: fpga_manager fpga0: Error after writing image data to FPGA
/sys/class/fpga_manager/fpga0/state  →  write complete error
```

**同步字这次找到了、数据也写进去了，但 `PCFG_DONE` 一直没置位。**

再做同样的对照 —— **换成板子自己那份位流**：

```
dmesg: fpga_manager fpga0: writing board_own.bin to FMSH FMQL FPGA Manager
dmesg: fpga_manager fpga0: Timeout waiting for PCFG_DONE
```

**A：同样超时。所以与位流无关。**

补充一条：`/sys/class/fpga_manager/fpga0/state` **只读**，写 `0`／`1` 全部 `Permission denied` —— 标准 `fpga_manager` 状态机（`operating`→`off`→重置）没有实现。

### 唯一确认好用的通道：FSBL 从 BOOT.bin

```
Preparing initialize file BOOT.bin......
Load boot header info (offset:0x20~0x48)success!
Image ID verified success!!!
Checksum verified success!!!
Boot header validate success, this is a valid image!!!
...
Prepare downloading bitstream.....
Download the PL bitstream is done at the 628.83 ms
```

**FSBL 每次开机都能成功把 PL 位流配进去。问题只在于那 4 路并行流程之外没有别的入口。**

---

## 三、我们已排除的可能（A，避免厂商重复劳动）

| 假设 | 排除依据 |
|---|---|
| 位流格式/字节序不对 | 换成厂商自己那份位流，同样失败；且字节序已按 `BOOT.bin` 的实际格式（4 字节字序翻转）转换过 |
| 位流长度不对 | `fpga info` 报 `Device Size: 5979916`，我们按此长度补齐（交换版与不交换版各一份）重试，仍 `Error 1` |
| `fatload` 失败导致命令没跑 | 串口实测 `5979868 bytes read in 251 ms`，`fatload` 成功，失败发生在其后的 `fpga loadb` |
| `loadbit` 那行本来就空转 | **成立**，且已在 [[板卡镜像实测取证]] 第七节登记过；本轮再次确认并给出了原因 |
| 我们改 `uEnv.txt` 改坏了启动 | 无关。`uEnv.txt.bak` 原样保留；且把 `loadbit` 指向一个**存在**的文件后，串口能看到 `fatload` 成功、`loadb` 失败，说明命令确实被执行了 |
| 内核/驱动没编进去 | `FPGA manager framework` 与 `fpga_manager fpga0: … registered` 都在，`/dev/fpga0`（10:61）存在 |

---

## 四、需要厂商回答的问题

### 4.1 主要问题（阻断项）

> **Q1. 这块 FMQL30TAI 上，除了 JTAG 和 FSBL 引导，还有没有官方支持的 PL 位流重载通道？如果有，需要满足什么前提？**
>
> 我们按三种方式都试过并失败，且**用你们出厂那份 `ai7030_top_disable_icap.bit` 做对照，同样失败**：
> - U-Boot `fpga loadb 0 <addr> <size>` → `Command 'loadb' failed: Error 1`
> - U-Boot `fpga load 0 <addr> <size>` → `Command 'load' failed: Error 1`
> - Linux `echo <file> > /sys/class/fpga_manager/fpga0/firmware` → `Timeout waiting for PCFG_DONE`
>
> `fpga info` 显示 `No Device Function Table.`、`Cookie: 0x0 (0)`。这是预期的吗？这台机器上 `fpga` 命令是不是没有正确编入？

> **Q2. `Device Size: 5979916 bytes` 是什么含义？是要求位流数据必须正好等于这个长度吗？**
> 我们按此长度补齐后（交换/不交换两种字节序都试过）仍然 `Error 1`，想确认这个字段是约束条件还是仅供显示。

> **Q3. `fpga_manager` 的 `Timeout waiting for PCFG_DONE`：已知问题吗？**
> 是否需要先做某个前置动作（例如通过 SLCR 复位 `devcfg`、或先 `echo` 特定值到某个寄存器）才能让 `PCFG_DONE` 正常置位？
> 另外 `/sys/class/fpga_manager/fpga0/state` 只读（写 `0`/`1` 都是 `Permission denied`），标准状态机是否有意做成只读？

> **Q4. 出厂 `uEnv.txt` 里 `loadbit=… fatload mmc 0:2 …`，而分区 2 是 ext4，`fatload` 读不到。这行是针对别的板型写的吗？**
> 如果换成 `mmc 0:1`（FAT16）就能走通，那是否意味着这条路本来是通的、只是分区号抄错了？我们实测 `fatload mmc 0:1` 成功、`fpga loadb` 失败 —— 所以即便修正分区号，`fpga` 命令本身仍然是坏的，对吗？

### 4.2 次要问题

> **Q5.** 设备树 `model = FMQLMP FMQL100TAI`，但 U-Boot 自报 `CPU: FMQL Plus FMQL30TAI`。出厂镜像是不是该改一下？我们在写资料时以哪个为准？

> **Q6.** 位流头部 `UserID=0XFFFFFFFF`（未授权 Vivado 的默认值），而你们出厂位流是 `UserID=53210711`。带 `0XFFFFFFFF` 的位流在这颗硅片上能正常配置吗？

> **Q7.** 我们另有一个问题：`AI_Mate.edif` 链进 `ai7030_edif_top` 后 `opt_design` 报 `ZGolo/pl_araddr[*]` 等 109 个 FDCE 无驱动（`Opt 31-430` / `Opt 31-67`），PS7 与 EDIF 的 `pl_*` 接口连接完整、BD 重新生成后字节一致。是否需要特定板型或配置的 EDIF？什么条件下该用 `AI_Mate_no_detpost.edif`？（去掉 NPU 后我们已能出位流，见 [[位流构建与SDI信号检测]]。）

---

## 五、附：现场信息与命令，供厂商复现

### 串口（COM6 / CP210x / 115200 8N1），按任意键可停在 `fmsh>` 提示符

启动流程（实测，略去内核日志）：

```
====PSOC FSBL BOOTING ....... ====
====FSBL Version: 4.51 ====
====Procise SVN Version: 31684  Release Date: 2025/09/25 14:30:00====
Preparing boot device initialization......
SD Boot Mode
Preparing initialize file BOOT.bin......
Load boot header info (offset:0x20~0x48)success!
Image ID verified success!!! / Checksum verified success!!!
Boot header validate success, this is a valid image!!!
Image Header Table Offset 0x8c0 / Partition Header Address: 0x280
Number of Partitions: 0x4
Prepare downloading bitstream.....
Download the PL bitstream is done at the 628.83 ms
...
NOTICE:  ATF running on FMQLP30TAI/0x49 v9/FAM1b.9 at 0xe1fe0000
NOTICE:  BL31: v2.3():44391da-dirty   Built : 20:05:14, Dec 10 2025

U-Boot 2020.07-gd24dcccd-dirty (Oct 31 2025 - 14:58:27 +0800)
CPU: FMQL Plus FMQL30TAI, Revision Code:9
Model: FMQLMP FMQL100TAI
DRAM:  1 GiB
Loading Environment from SPI Flash... SF: Detected n25q256a ...
*** Warning - bad CRC, using default environment
In:    serial@e0004000
Out:   serial@e0004000
Err:   serial@e0004000
MMC:   dwmmc@e0043000: 0
```

**A：`Loading Environment from SPI Flash... *** Warning - bad CRC, using default environment`** —— SPI Flash 里的 u-boot 环境变量区 CRC 是坏的，U-Boot 在用**默认环境**。随后 `envboot` 会 `env import -t <addr> <size>` 把 FAT 上的 `uEnv.txt` 导进来（串口可见 `Importing environment from uEnv.txt`），所以我们改 `uEnv.txt` 是生效的。这条 CRC 坏掉本身也值得厂商看一眼。

### U-Boot 完整命令表里与本问题相关的部分

```
fpga      - loadable FPGA image support      ← 唯一入口
fatload / fatwrite / ext4load / mmc
clk       - CLK sub-system
```

`fpga` 子命令（`fmsh> fpga` 无参打印）：

```
Usage:
fpga [operation type] [device number] [image address] [image size]
fpga operations:
  dump	[dev] [address] [size]	Load device to memory buffer
  info	[dev]			list known device information
  load	[dev] [address] [size]	Load device from memory buffer
  loadp	[dev] [address] [size]	Load device from memory buffer with partial bitstream
  loadb	[dev] [address] [size]	Load device from bitstream buffer (Xilinx only)
  loadbp	[dev] [address] [size]	Load device from bitstream buffer with partial bitstream(Xilinx only)
```

二进制里能看到的相关符号/字符串（`strings /mnt/boot/u-boot`）：

```
fmsh_fpga_descs   fpga_xilinx   fpga_loadbitstream   fpga_dev_info   fpga_add
devcfg@e0040000   fmsh,fmql-devcfg-1.0
fpga_rst_ctrl   csu_devcfg   fmqlmp_slcr_devcfg_disable   fmqlmp_slcr_devcfg_enable
%s: Timeout wait for PCAP to complete
%s: Timeout wait for FPGA to config
%s: FPGA support not initialized!
FPGA image is corrupted or invalid
```

**B：`fmqlmp_slcr_devcfg_disable/enable`、`fpga_rst_ctrl`、`csu_devcfg` 这些符号说明厂商在 U-Boot 里改过 FPGA 加载流程（要经 SLCR 复位 devcfg、走 PCAP）。`Timeout wait for PCAP to complete` 这条错误串存在，但我们没看到它被打印出来 —— 只看到笼统的 `Error 1`。想请教这条路径的预期调用顺序。**

### 内核侧

```
/proc/misc                      → 61 fpga0
/dev/fpga0                     → crw------- 1 root root 10, 61
/sys/bus/platform/drivers/     → fmql_fpga_manager, of-fpga-region
/sys/bus/platform/devices/     → e0040000.devcfg
dmesg                          → fpga_manager fpga0: FMSH FMQL FPGA Manager registered
```

内核配置（板载 `34_kernel_config_from_Image.txt`）：`CONFIG_FPGA=y`、`CONFIG_FPGA_MGR_FMQL_FPGA=y`、`CONFIG_FPGA_BRIDGE=y`、`CONFIG_FPGA_REGION=y`、`CONFIG_OF_FPGA_REGION=y` —— **全内建，没有模块化缺口。**

### 复现命令清单

```sh
# 1. Linux 侧
cp my.bit /lib/firmware/video_only.bit
sync
echo video_only.bit > /sys/class/fpga_manager/fpga0/firmware
dmesg | tail -3                       # → Timeout waiting for PCFG_DONE

# 2. U-Boot 侧（串口，按任意键停在 fmsh>）
fatload mmc 0:1 0x10000000 video_only.bit
fpga loadb 0 0x10000000 5979868       # → Command 'loadb' failed: Error 1
fpga info                             # → No Device Function Table.
```

---

## 六、我们这边的替代方案（若厂商短期无回复）

**A**：唯一确认可用的通道是 FSBL 从 BOOT.bin 灌位流。我们已经把 BOOT.bin 的位流分区边界定位清楚，可以做字节级替换：

```
BOOT.bin  0x000000..0x02D9EF   FSBL
          0x02D9F0..0x5E18CB   ← PL 位流，5 979 828 字节
          0x5E18CC..           填充（48 字节 FF）
          之后                 BL31(ATF) … u-boot
```

定位方法：把板载 `ai7030_top.bit` 的 payload（偏移 192 起，5 979 828 字节）**按 4 字节字序翻转**后，其前 256 字节在 BOOT.bin 的 `0x2DA18` 精确命中；减去 40 字节的差得到起点 `0x2D9F0`。

我们的位流 payload 比槽位多 40 字节，末尾是 `20 00 00 00`（7 系位流的空操作 dummy 命令，厂商那份同样以此结尾），**裁掉末尾 10 个 dummy 字即可精确填满**。

**安全网**：原始 `BOOT.bin` 已留两份（SD 卡上 `BOOT.bin` + `uEnv.txt.bak` 同目录、本地另存），且 U-Boot 有 `fatwrite`，万一新 BOOT.bin 起不来，可以在 `fmsh>` 提示符下从串口写回去，无需拆卡。

**但这属于改厂商引导镜像，仍然更希望厂商直接给一条受支持的重载通道。**

---

## 相关页面

- [[位流构建与SDI信号检测]] — 我们自己的位流是怎么构建出来的（本页 Q7 的上下文）
- [[板卡镜像实测取证]] — `loadbit` 空转的原始推断与 BOOT.bin 字节序翻转的发现
- [[板载接口与内核改造收纳进dev]] — 内核侧改造方案（其中"Linux 侧能下比特流"一条已被本页推翻，见该页修订）
- [[官方demo时序基线与器件库补丁]] — 器件库补丁怎么装