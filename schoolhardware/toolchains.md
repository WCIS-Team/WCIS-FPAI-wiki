# 校机（WIN11-HV1）工具链位置与用法

- 采集时间：2026-10-19 06:17（UTC+8）；2026-10-20 16:14 复测确认
- 档案版本：1.1（取代 00:42 的 v1.0）
- 证据：`toolchains.json`、`raw_logs/raw/toolchains_reprobe.txt`、`raw_logs/raw/cross_gcc_version.txt`

## 结论

校机上实际有两套可用的 C/C++ 编译器：MSYS2 `mingw64` 的 x86_64 原生 GCC 16.2.0，以及 `D:\yzd\tools\cross` 下的 aarch64 交叉 GCC 10.3.1。两者都不在 PATH 中，必须用绝对路径调用，或在脚本里临时把目录加进 PATH。`make`、`cmake`、`ninja`、`meson`、autotools、`gdb`、`git`、`perl` 均不在 PATH；`python`/`python3` 只是 Microsoft Store 的转发壳，没有真实解释器。2026-10-20 用同一脚本重采一遍，两套编译器、版本串与目录全部复现，结论不变。

## 1. 原生编译器（x86_64-w64-mingw32）

| 项 | 值 |
| --- | --- |
| 根目录 | `D:\yzd\MSYS2`（活动前缀 `mingw64`） |
| gcc | `D:\yzd\MSYS2\mingw64\bin\gcc.exe` |
| cc / c++ / g++ | 同目录下的 `cc.exe`、`c++.exe`、`g++.exe` |
| target | `x86_64-w64-mingw32` |
| 版本 | `cc.exe (Rev6, Built by MSYS2 project) 16.2.0` |

只有 `mingw64/bin` 装了编译器。`mingw32`、`clang64`、`clangarm64`、`ucrt64`、`usr/bin` 这些前缀的 bin 目录存在，但里面没有 gcc/g++/clang/cc/cpp。

调用示例：

```
D:\yzd\MSYS2\mingw64\bin\gcc.exe -O2 -o hello.exe hello.c
```

实测踩坑：用 `-fopenmp` 编译出的程序在运行时依赖 `libgomp-1.dll`。如果启动时 PATH 里没有 `D:\yzd\MSYS2\mingw64\bin`，进程会停在“找不到 DLL”的错误对话框上，表现为 0 CPU、长时间不返回。跑这类程序前先 `set PATH=D:\yzd\MSYS2\mingw64\bin;%PATH%`。

## 2. 交叉编译器（aarch64-none-linux-gnu）

| 项 | 值 |
| --- | --- |
| 根目录 | `D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu` |
| gcc | `...\bin\aarch64-none-linux-gnu-gcc.exe` |
| target | `aarch64-none-linux-gnu` |
| 版本 | GNU Toolchain for the A-profile Architecture 10.3-2021.07 (arm-10.29)，GCC 10.3.1 20210621 |

这是 i686 宿主（mingw-w64）构建的 Arm GNU Toolchain，在 x64 Windows 上可直接运行。它不在 PATH 中。调用示例：

```
D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-gcc.exe -O2 -c foo.c
```

本轮只确认了编译器自身可执行并打印版本，没有用交叉产物上板运行，因此“能编出可用的板端二进制”仍属未验证。

## 3. 缺失或未验证的工具

| 工具 | 状态 | 说明 |
| --- | --- | --- |
| make / cmake / ninja / meson | 不在 PATH | 只探测了 PATH，不等于机器上没有；MSYS2 的 `usr/bin` 未逐一枚举 |
| autoconf / automake / pkg-config | 不在 PATH | 同上 |
| gdb | 不在 PATH | 同上 |
| git | 不在 PATH | MSYS2 通常自带 `usr/bin/git.exe`，本轮未验证 |
| python / python3 | 只有 Store 转发壳 | `C:\Users\YiZhidi\AppData\Local\Microsoft\WindowsApps\python.exe`，没有真实解释器，pip 也因此不可用 |
| perl / go / node / rustc / cargo | 不在 PATH | 未验证是否装在非 PATH 目录 |
| pacman | 不在 PATH | MSYS2 的包管理器一般在 `usr/bin`，本轮未验证 |
| 包管理器 | 仅 winget | `C:\Users\YiZhidi\AppData\Local\Microsoft\WindowsApps\winget.exe` |

## 4. 复现命令

在任一 PowerShell 或 cmd 中：

```
D:\yzd\MSYS2\mingw64\bin\gcc.exe --version
D:\yzd\MSYS2\mingw64\bin\g++.exe --version
D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-gcc.exe --version
where.exe make cmake ninja git python pacman
```

完整输出见 `raw_logs/raw/toolchains_reprobe.txt`；交叉编译器的完整版本串单独存在 `raw_logs/raw/cross_gcc_version.txt`（`reprobe` 对交叉链只记录了 `-dumpmachine` 的 target，没抓 `--version`，后者是 2026-10-20 补跑的）。
