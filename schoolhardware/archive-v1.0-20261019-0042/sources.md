# Hardware Archive - Information Sources (SOP 2 / MOD 硬件与基础运行环境信息采集)

- Collected (local): 10/19/2026 00:42:25  (China Standard Time (08:00:00))
- Host: Win11-HV1
- OS caption: Microsoft Windows 11 专业工作站版
- Collector: hw_collect.ps1 (SOP 2 - MOD) v1.0
- Tooling: PowerShell 5.1.26100.9711; Get-CimInstance / Get-ComputerInfo / Get-Volume

## Source-classification legend (SOP 4 step4)
- official_spec    : vendor datasheet / official document (NONE used here)
- system_report    : OS / firmware reported values via WMI/CIM
- tool_report      : output of installed tools on the guest
- field_measurement: values measured by an executed benchmark (NONE performed)
- unverified       : cannot be confirmed from this guest alone

## Per-deliverable classification
- device.json    : identity/system_report, hardware_summary/system_report
- system.json    : os/system_report
- software.json  : software/tool_report
- resources.json : cpu/memory/storage/accelerators = system_report; runtime_limits = tool_report

## Raw logs
All original guest command output is under raw_logs/ (incl. reprobe.txt from the
second targeted pass). Field-level classification is recorded as a "_meta.source"
or per-group "source" in each JSON.

## Important notes / scope limits
1. DEVICE IS A VIRTUAL MACHINE. Manufacturer=Microsoft Corporation, Model=Virtual
   Machine, BIOS=VRTUAL-1, HypervisorPresent=True. The CPU model string
   (AMD EPYC 9654 96-Core) is the HOST CPU exposed to the guest; this VM is
   assigned 24 vCPUs. Memory is reported as 3 virtual DIMMs. Treat all "physical"
   fields as virtualized allocations, not bare-metal specs.
2. OS SELF-REPORT DISCREPANCY. Win32_OperatingSystem.Caption says
   "Microsoft Windows 11 专业工作站版" (Windows 11 Pro for Workstations), build
   10.0.26200, while Get-ComputerInfo.WindowsProductName reported
   "Windows 10 Pro for Workstations". The build number (26200) confirms Windows 11
   24H2; the WindowsProductName value is a known WMI reporting quirk. Recorded as
   system_report with the discrepancy flagged.
3. GPU/NPU/FPGA. Only the Hyper-V synthetic video adapter is present; nvidia-smi was
   not found, so there is no discrete GPU/NPU passthrough. FPGA resource figures
   require vendor tools (Vivado/Quartus) which were NOT executed (SOP forbids
   installing/running heavy tooling for collection only). Marked not_detected.
4. Python is NOT installed: only the Microsoft Store redirector stub is on PATH.
5. MSYS2 gcc/g++ were not present at D:/yzd/MSYS2/usr/bin (no usable C/C++ compiler
   found on this guest).
6. NO benchmarks were run. This archive contains only device/baseline enumeration,
   per SOP scope. zram and Linux cgroup memory limits are not applicable on Windows
   (marked not_supported / not_applicable).
