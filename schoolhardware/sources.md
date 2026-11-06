# 硬件档案信息来源（SOP 2 / MOD 硬件与基础运行环境信息采集）

- 采集时间（本地）：2026-10-19 06:17:56（China Standard Time, UTC+8）；2026-10-20 16:14:00 复测
- 采集时间（UTC）：2026-10-18T22:17:56Z；2026-10-20T08:14:00Z 复测
- 主机：WIN11-HV1（Hyper-V 虚拟机）
- 采集器：`hw_collect_v2.ps1`（SOP 2 - MOD，修正版重采）
- 档案版本：1.1（取代 00:42 的 v1.0，旧文件在 `archive-v1.0-20261019-0042/`）
- 工具：PowerShell 5.1.26100.9711；Get-CimInstance / Get-ComputerInfo / Get-Volume；gcc 16.2.0（基准）

## 来源分级（对应 SOP 步骤 4）

- official_spec：厂商数据表或官方文档（本次未使用）
- system_report：操作系统/固件通过 WMI/CIM 报告的值
- tool_report：校机上已装工具的输出
- field_measurement：实际执行基准测得的数值
- unverified：仅凭这台虚拟机无法确认

## 各文件的来源

- `device.json`：identity / hardware_summary = system_report
- `system.json`：os = system_report
- `software.json`：software = tool_report
- `resources.json`：cpu / memory / storage / accelerators = system_report；runtime_limits = tool_report
- `toolchains.json`：编译器探测 = tool_report（按绝对路径逐个执行）
- `benchmarks.md` 与 `raw_logs/bench_run*.json`：field_measurement

## 与 v1.0 的差异

1. v1.0 的 `software.json` 写“未找到 C/C++ 编译器”，原因是只查了 `D:/yzd/MSYS2/usr/bin` 且按文件名在 PATH 里解析。v1.1 按完整路径探测，确认 `D:\yzd\MSYS2\mingw64\bin\gcc.exe`（GCC 16.2.0）可用。
2. v1.1 新增交叉编译器：`D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-gcc.exe`（GCC 10.3.1，target aarch64-none-linux-gnu）。
3. v1.1 新增 `toolchains.json`，记录 MSYS2 各前缀的编译器分布、PATH 中的构建工具和包管理器。
4. v1.1 新增有界基准：`benchmarks.md`、`raw_logs/bench.json`、`raw_logs/bench_run1..3.json`。v1.0 没有跑任何基准。

## 2026-10-20 复测

5. 2026-10-20 16:14 用同一脚本从头复跑一遍：设备 JSON（device/system/software/toolchains）与 10-19 版本逐字段一致、只差采集时间戳；基准单次读数落在 10-19 三次的范围内（`benchmarks.md` 复测表）。交付物的结论因此验证成立。
6. 交叉编译器补抓了 `--version` 完整串（`aarch64-none-linux-gnu-gcc.exe (GNU Toolchain for the A-profile Architecture 10.3-2021.07 (arm-10.29)) 10.3.1 20210621`），存 `raw_logs/raw/cross_gcc_version.txt`；`toolchains_reprobe.txt` 里它只有 `-dumpmachine` 的 target 行。
7. `software.json`/`toolchains.json` 的 `prefixes_with_compilers` 被收集器留成空数组，是脚本逻辑瑕疵（`note` 文字本身写对了）；顶层交付物按 note 修正为 `["mingw64"]`，`raw_logs/` 里的机器原始输出按原样保留。

## 重要说明与范围限制

1. 设备是虚拟机。Manufacturer=Microsoft Corporation、Model=Virtual Machine、BIOS=VRTUAL-1、HypervisorPresent=True。CPU 型号串（AMD EPYC 9654 96-Core）是宿主机 CPU 暴露给虚拟机的值，本机分到 24 个 vCPU；内存报告为 3 条虚拟 DIMM。所有“物理”字段都应理解为虚拟化分配，不是裸机规格。
2. 操作系统自报名称有出入。`Win32_OperatingSystem.Caption` 是“Microsoft Windows 11 专业工作站版”，build 10.0.26200；`Get-ComputerInfo.WindowsProductName` 报“Windows 10 Pro for Workstations”。build 26200 对应 Windows 11 24H2，后者是已知的 WMI 显示问题，按 system_report 记录并标注差异。
3. GPU/NPU/FPGA。只有 Hyper-V 合成显卡；`nvidia-smi` 不存在，没有独显或 NPU 直通。FPGA 资源数据需要 Vivado/Quartus 报告，本次没有运行，标记 not_detected。
4. Python 没有真实安装，PATH 里只有 Microsoft Store 的转发壳，pip 不可用。
5. `software.json` 里 `build_tools_path` 的 null 只表示“不在 PATH”，不等于“机器上没装”。例如 git、make、cmake 可能存在于 MSYS2 的 `usr/bin`，本轮没有逐一枚举。
6. zram 与 Linux cgroup 内存限制在 Windows 上不适用，分别标记 not_supported / not_applicable。
7. 采集时后台有明显负载（`fdtd-solutions` 约 12.6 GB 内存，`LoadPercentage` 快照 100），基准读数在共享、有竞争的条件下取得，只能作量级参考。

## 原始日志

校机命令输出全部在 `raw_logs/raw/`：computerinfo、os、processor、physicalmemory、physicaldisk、volume、videocontroller、pnp_devices、services、processes_top、nvidia_smi、python、pip_list、toolchains_reprobe，共 14 个文本；2026-10-20 复测补了 `cross_gcc_version.txt`（交叉编译器完整版本串），共 15 个。

`raw_logs/` 根下另有结构化结果（device/system/software/resources/toolchains）和基准 JSON（`bench_run1..3.json` 为 2026-10-19 三次、`bench.json` 为 2026-10-20 复测单次；`gcc.log`、`bench_stdout.txt` 为空壳证据）。
