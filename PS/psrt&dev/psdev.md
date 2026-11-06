---
tags: [index]
---

# [docstree](/docstree)
# dev
根据使用的开发板型号,修改impl_constraints.xdc文件的管脚约束。

(1)悟净开发板

set_property PACKAGE_PIN U6 [get_ports FMC_HPC_GBTCLK0_M2C_C_P] ## WUJING BOARD
set_property PACKAGE_PIN U5 [get_ports FMC_HPC_GBTCLK0_M2C_C_N]

(2)悟净开发板Lite

set_property PACKAGE_PIN R6 [get_ports FMC_HPC_GBTCLK0_M2C_C_P] ## WUJING LITE BOARD
set_property PACKAGE_PIN R5 [get_ports FMC_HPC_GBTCLK0_M2C_C_N]

## 完整版
![1787890661831885.png](/1787890661831885.png)
S:\work\WCIS\fdw\03_FMQL30TAI-悟净开发板手册\悟净开发板（完整版）硬件使用手册V1.0_嵌赛.pdf
| 分类          | 项目        | FMQL30TAI                                           |
|-------------|-----------|-----------------------------------------------------|
| 产品定位        | 架构        | CPU + NPU + FPGA 异构融合                               |
|             | 应用场景      | FPAI 轻量化端侧 / 边缘智能算力                                 |
|             | 总算力       | 8 TOPS @ INT8                                       |
| 处理器系统       | 处理器核心     | 4核处理器（最高1GHz）                                       |
|             | 一级缓存      | 32KB指令缓存、32KB数据缓存                                   |
|             | 二级缓存      | 1MB                                                 |
|             | 片上存储      | 256KB                                               |
|             | DMA通道     | 8通道                                                 |
|             | 外部DDR支持   | DDR3/DDR3L/LPDDR2（支持ECC）                            |
|             | 外部静态存储    | 2×Quad-SPI, NAND, NOR                               |
|             | 通用外设      | UART, CAN, I2C, SPI, GPIO, SD/SDIO等                 |
|             | 高速通信外设    | 2×USB, 2×Gigabit Ethernet                           |
|             | 安全特性      | 专用安全处理器、专用安全算法硬核RSA/AES/SHA-256/SM4用于验签和解密、支持安全启动   |
| NPU AI加速引擎  | AI架构      | 1个 ZG330 iCore                                      |
|             | AI算力      | 8 TOPS @ INT8<br>4 TFLOPS @ FP16<br>2 TFLOPS @ TF32 |
|             | 计算精度      | INT8 / FP16 / BF16 / TF32                           |
|             | 算子支持      | CNN、Transformer等                                    |
|             | 功耗管理      | 支持电源软切换与自适应时钟门控                                     |
| 可编程逻辑（FPGA） | 逻辑资源      | 125K                                                |
|             | LUT数量     | 78,600                                              |
|             | BRAM容量    | 9.3 Mb                                              |
|             | DSP单元数量   | 400                                                 |
|             | PCIe      | Gen2 x4                                             |
|             | 高速接口通道数   | 4                                                   |
|             | 高速接口最高速率  | 12.5 Gbps                                           |
| 功耗          | 典型功耗      | ~8W                                                 |
| 封装信息        | 封装形式      | FCBGA676                                            |
|             | 封装尺寸      | 27×27 mm                                            |
|             | 焊球间距      | 1.0 mm                                              |
|             | HPIO/HDIO | 150 / 100                                           |

### led
impl_constraints.xdc: #LED1, BANK13 set_property PACKAGE_PIN J1 [get_ports {led[0]}] #LED2, BANK13 set_property PACKAGE_PIN M6 [get_ports {led[1]}]
ai7030_edif_top.v:184
rx_sdi.v:204   assign led2 = locked2;          // 这是 sd_rx_reset_control 的 .locked
rx_sdi.v:255   assign led1 = rx_usrclk_cnt[25];
## 轻量版
| 分类        | 项目    | FMQL30TAI676H 悟净开发板（轻量版）                                 |
|-----------|-------|----------------------------------------------------------|
| 产品概述      | 架构    | CPU + NPU + FPGA 异构融合                                    |
|           | 核心芯片  | FMQL30TAI (FCBGA676, 27×27 mm, 1.0 mm 焊球间距)              |
| 处理器系统     | 处理器核心 | 4核应用处理器（最高主频 1 GHz）                                      |
|           | 缓存与存储 | L1: 32KB 指令 + 32KB 数据; L2: 1MB; 片上: 256KB                |
|           | DMA   | 8 通道                                                     |
| 存储系统      | DDR   | PS 侧 1GB DDR3; PL 侧 2GB DDR3                             |
|           | Flash | 256Mb QSPI FLASH (PS 端)                                  |
|           | 外部存储  | 32GB TF-CARD                                             |
| NPU AI 加速 | AI 架构 | 1 个 ZG330 iCore                                          |
|           | AI 算力 | 8 TOPS @ INT8; 4 TFLOPS @ FP16; 2 TFLOPS @ TF32          |
|           | 计算精度  | INT8 / FP16 / BF16 / TF32                                |
|           | 算子支持  | CNN、Transformer 等                                        |
| 可编程逻辑     | 逻辑资源  | 125K (LUT 数量 78,600)                                     |
|           | 存储与计算 | BRAM 容量 9.3 Mb; DSP 单元 400                               |
| 时钟管理      | 时钟源   | PS 侧 50MHz; PL 侧 200MHz                                  |
| 网络与通信     | 以太网   | 1 路 10/100/1000Mbps 以太网 (PS 端)                           |
|           | USB   | 4 路 USB2.0                                               |
|           | 串口    | 2 路 USBUART                                              |
|           | PCIe  | 1 路 PCIe x1                                              |
|           | 光纤通信  | 1 路 SFP                                                  |
| 视频接口      | SDI   | 2 路 SDI 输入                                               |
|           | HDMI  | 1 路 HDMI 输出                                              |
| 通用外设与监测   | 模拟接口  | 5 路 XADC 接口                                              |
|           | 调试接口  | 1 路 PS_JTAG; 1 路 PL_JTAG                                 |
|           | 扩展接口  | PL 端 16 路通用 GPIO 接口                                      |
| 人机交互      | 指示与输入 | 1 路 PS MIO LED; 4 路 PL LED<br>1 路 PS MIO KEY; 2 路 PL KEY |
| 安全特性      | 硬件安全  | 专用安全处理器; 专用安全算法硬核 RSA/AES/SHA-256/SM4; 支持安全启动            |
| 功耗与电气     | 典型功耗  | ~8W                                                      |
|           | IO 资源 | HPIO 150 / HDIO 100                                      |
## 外设
### wire
com
wan
#### Connection
无 RTC 保持时重启回 1970／出厂值，
日志时间戳、`make` 依赖、https 证书三处一起错；
`date -s` 之后必须 `hwclock -w` 才留得住 
> DHCP + sshd（改 /etc/rc.local

### sd(tf)
防止不同厂商扇区数不一样选择64g而非镜像的32g
|---|---|
| 目标卡 | Disk 2 · Generic STORAGE DEVICE（USB）· **62,723,719,168 B = 58.42 GiB** |
| 镜像裸数据 | **31,914,983,424 B = 29.72 GiB**；开头 **512 B 私有头不参与比对**
| 写入方式 | 锁卷 + 卸除（`LOCK+DISMOUNT` 成功，卷句柄握到写完），非文件级复制 |
| 校验方式 | 握卷句柄**逐块回读全卡 + SHA256 比对**，等价于 imageUSB 的 *Post Image Verification*，但覆盖 100% 数据而非抽样 |
| 结果 | **MATCH**，全 29.72 GiB 一致，用时 **18.0 分钟**，速率稳定在 28 MiB/s |
| 卡上分区表 | boot signature **`0x55AA`**（有 MBR）；p1 `type=0x0E` startLBA **2,048** 1.00 GiB；p2 `type=0x83` startLBA 2,101,248 26.08 GiB；容器 122,507,264 扇区 |

####  本次校验全过程记录 -> S:\apps\llm\agentwork\verify-20260926-032045.log
目标: Disk 2  Generic STORAGE DEVICE  62,723,719,168 B  Bus=USB  PartitionStyle=MBR
镜像裸数据 31,914,983,424 B，私有头 512 B 不参与比对
  LOCK+DISMOUNT 成功: \\?\Volume{79b18eaa-b900-11f1-b510-ecaf13adfec4}（句柄握到写完）
--- 卡上的分区表 ---
  boot signature = 0x55AA  (0x55AA = 有 MBR)
  p1 type=0x0E startLBA=2,048 sectors=2,097,152 (1.00 GiB) endLBA=2,099,200
  p2 type=0x83 startLBA=2,101,248 sectors=54,687,500 (26.08 GiB) endLBA=56,788,748
  container = 62,723,719,168 bytes = 58.42 GiB = 122,507,264 sectors
  卷句柄已释放
#### image
    SD卡刻录完成后，会显示FAT分区

    FAT分区用于存放启动开发板所需要的相关配置文件BOOT.bin/Image/fmqlmp-verify.dtb/uEnv.txt等，icraft_v3_ubuntu_sd_image.bin中包含的FAT分区文件来源于下载站，对其中的Linux内核镜像Image进行了更新，添加了声卡驱动，目的是支持USB声卡以及USB摄像头。
    SD卡启动开发板（板载ubuntu系统）FAT分区必须包含以下四个文件：
        BOOT.bin，启动引导文件，由FSBL+user.bit+bl31.elf+u-boot打包生成。
        fmqlmp-verify.dtb ，设备树二进制文件，告诉内核：板子有什么硬件（串口、网口、Flash、I2C、时钟等）。
        Image，Linux内核镜像。
        uEnv.txt，环境变量配置文件。
S:\work\WCIS\wiki\board_extract
#### Burn
dd
### MCP001 - Microphone & Speaker
[uac1.0-audio10.pdf](/uac1.0-audio10.pdf)
48kHz I/O
# official online docs
[模型信息汇总.xlsx](/fdw/模型信息汇总.xlsx)
[解决方案汇总.xlsx](/fdw/解决方案汇总.xlsx)
[faq共建.docx](/fdw/faq共建.docx)

