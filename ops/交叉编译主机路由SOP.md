---
tags: [SOP]
---

# 交叉编译主机路由SOP

> 定稿 2026-10-15。**这是"以后要交叉编译任何东西时照抄的那张流程表"**，不重复构建环境的细节（怎么从零搭环境在 [[校机交叉编译环境搭建SOP]]，组件哈希与读数在 [[win无wsl交叉编译]] 与 [[校机无容器交叉编译]]）。
> **10-16 晚加了「三·补 照抄卡」**：她判"现在要进行交叉编译，而不是建立交叉编译环境"⇒ 环境已经就绪时，路径／入参／命令／门禁读数／取件／上板登记在那一节，不用再回七步搭建页。**盘上只剩 `D:\yzd\WCIS\crosswin` 一个根**，卡上所有路径就是它。
> 一句话：**能搬走的搬去校机，只有 CLI 与 x86 数值路搬不走的留本机，"跑起来"这件事只能板子做。**
> **11-02 补第三类"留本机"的活**：**不吃 iCraft kit 的通用 aarch64 程序**（源码自带 `configure`／Makefile），路是**本机 WSL ＋ focal gcc-9，全程免 root**——见下面「二·补」。（这条不推翻上面的路由：吃 kit／cp38 扩展的件照旧走校机，板上照旧禁止编译。）

## 一、三台机各自能做到什么（路由的唯一依据）

| | 校机（`ssh school-guest`，WIN11-HV1，yizhidi） | 本机（开发机，S: 盘） | 板子（悟净／ZG330） |
|---|---|---|---|
| 系统／架构 | Windows 11 + MSYS2，**x86-64** | Windows 11 + WSL，**x86-64** | Ubuntu 20.04，**aarch64**（4×Cortex-A53，993 MB RAM） |
| 编译工具链 | Arm GNU **10.3-2021.07**（i686-host，靠 WoW64 跑）＋ cmake 4.4.4／ninja 1.13.2 ＋ 九件 donor | 无 aarch64 交叉工具链 | gcc 9.3（**禁止使用**） |
| **iCraft CLI** | **没有**（只有 deb 里的头与 `.so`，`icraft` 可执行文件是 x86-64 的、且未装） | **有**：`C:\Icraft\CLI v3.39.0` | 没有（板上只有运行时 `libaxizg330aiu.so` 与 `icraft-run`） |
| 能产出什么 | aarch64 二进制／`.so`／cp38 扩展模块（**编译＋静态门禁**） | 模型五段产物（imodel／json／raw）、Host 后端前向数值 | 真跑、真帧、真延迟 |
| 看得到结果吗 | 看得到文件、ELF 头、符号、NEEDED；**看不到运行**（架构不对，跑不了 aarch64 ELF） | 看得到算子级 `compile_target`、量化读数、逐层 dump | 看得到一切，但**编译会把链挤死**（见 [[板端内存上限与心跳日志]]） |
| 什么时候会撞车 | 她的 ASR 批次（`python.exe`）在跑时会**抢 CPU**，但**不再拦构建**（10-16 晚她判「删除要 python=0 的门禁」，见第三节第 2 步） | — | 直播链／另一会话的部署在跑时不许抢 |

## 一·补 后端档：只用 ZG330（2026-10-15 审计，此后默认）

路由之前先定后端档，因为**imodel 与后端是绑死的**：布衣档的件在悟净上加载不了，反之亦然。审计过我方全部 iCraft 编译，**没有一件走过布衣**：

| 模型线 | 用的配置 | 产物 | 判据 |
|---|---|---|---|
| yolov8n | `2_compile/config/ZG/Yolov8_int8.toml`、`Yolov8_8_plin.toml` | `3_deploy/imodel/ZG/int8`、`ZG/int8_plin`（`Yolov8n_parsed/_optimized/_quantized/_adapted/_ZG`） | 目录里**只有 `ZG` 一支**，`find 3_deploy/imodel -type d` 零个 `BY` |
| yolov8n 512×960 | 同上 ZG 档换尺寸 | `Yolov8n512x960_ZG.{json,raw}` | 文件名后缀 `_ZG` |
| yolov5s PLIN | `config/ZG/` | `yolov5s_plin_960x512_ZG.{json,raw}`、`352x640_ZG` | 同上，且板上 `run_backend: zg330` |
| Qwen2／Qwen3 | `target = 'zhuge'`（＝ZG330） | `Q3V1-decoder_ZG.{json,raw}`、厂商 Qwen2 的 `_ZG` 件 | 10-14 板上跑通的就是这一档 |

**所以记录里只保留 ZG 一档的数**，三条口径同时生效：

1. 仓库里那两份 `3_deploy/metrics/logs/BY_int8|BY_mix`（2025-07-16，布衣 100TAI）是**厂商随工程附带的日志，我们从未复现**——只能当量级与方向参考，不得当本板读数引用，也不得填进任何耗时／精度表（[[算子缺口处理]] §7、D-32 第 2 项已按这条写）。
2. `2_compile/config/BY/` 那四张 toml 与 `Yolov8_16.toml`/`Yolov8_mix.toml` 是**厂商素材**，不是待办；悟净上想要 mix 档＝自己造厂商没走过的配置。
3. 算子表里的 **BUYI 列照抄保留**（那是厂商表的原样，删了就变成我们改写厂商文档），但引用时必须带"非本板"三个字——真判据看 ZG330 列与编译器实测，见 [[iCraft算子支持矩阵]]。

*易混的一处*：板端可执行件的 `DT_NEEDED` 里**有** `libicraft_buyibackend.so`（厂商 demo 的链接清单就带这颗，L1b 那 12 项一个不能少）。那是**链接期依赖**，不是后端选择——别拿它当"我们编了布衣档"的证据。

## 二、路由表：一类需求走哪条

| 需求 | 校机 | 本机 | 板子 | 备注 |
|---|---|---|---|---|
| 板端 C++ 可执行（demo／actor／探针） | ✅ **主路** | ❌ 没工具链 | 🚫 禁止编译 | 产物形态见 [[win无wsl交叉编译]] §3.7 |
| 板端 Python 扩展／嵌入件（cp38） | ✅ **主路** | ❌ | 🚫 | 需 donor #7/#8/#9 |
| **板端 aarch64 通用件**（源码自带 `configure`／Makefile，**不吃 iCraft kit**） | 绕远（那条链的输入是 kit／pyroot／uapi，与本需求无关） | ✅ **主路**：本机 WSL ＋ focal gcc-9，**免 root**、脚本一键 | 🚫 禁止编译 | 配方＝`repos/lang/tts/ekho-linux:scripts/build-cross-aarch64.sh`（说明见其 `README.md` §5）；为什么留本机见「二·补」 |
| 模型 → imodel（量化编译，出 json／raw／params） | ❌ **没有 CLI** | ✅ **唯一** | ❌ | 量化校准、逐层 dump 也只能本机 |
| 算子缺口判定（`compile_target`／`--precheck`） | ❌ | ✅ | 可选（codegen 侧印证） | 见 [[iCraft算子支持矩阵]] 第五节 |
| 精度／数值基线（PC 侧前向） | ❌ | ✅ `icraft-run` Host 后端 | ✅ 最终判据 | 校机那个 qwen3 venv 是 **torch CPU 基准**，不是 iCraft 前向 |
| 上板部署＋跑＋取证 | 只做"交叉部署"的发包端 | ❌ 不下大资源 | ✅ | 产物必须当场登记进 [[板端我方代码与产物台账]] |
| 位流／Vivado | ❌ | ✅（10-14 她授权，只在 `npu_merge_1014` 副本） | ❌ | 见 [[位流构建与SDI信号检测]] |

## 二·补 免 root 的第三种活：通用 aarch64 程序（2026-11-02 补）

> 路由表前两行是"要 iCraft 的 kit 才编得出来"的板端件，产物形态是 BYZG 那条链。**这一类不是**：程序自己带 `configure`／Makefile，不链任何 `libicraft_*`，只用板子上现成的 `libespeak-ng.so`／ALSA 一类系统库。对它的正确路由是**本机 WSL**，不是校机——校机那条链的全部输入（kit／pyroot／uapi／donor）跟它没关系，搬过去只是白搬。

**配方在仓库里，不在本页**：`repos/lang/tts/ekho-linux` → `scripts/build-cross-aarch64.sh`（2026-11-02 加，提交 `70c2e6c`，161 行）；给人读的说明在同仓 `README.md` §5 *Building for a board (aarch64)*。本节只记**它为什么这么写**与**判据**，数字不复述。

**一行跑法**（WSL 里，仓根）：

```bash
scripts/build-cross-aarch64.sh                              # 默认只出 ekho-worker
TARGETS="ekho-worker ekho-server" scripts/build-cross-aarch64.sh
BOARD=root@192.168.1.113 scripts/build-cross-aarch64.sh     # 顺带把产物送板上
```

可覆盖的变量：`SRC`（源码根，默认脚本上一级）、`WORK`（默认 `~/ekho-cross-root`，**全部下载与解包都在这里面**，所以不用 sudo）、`BOARD`（默认 `root@192.168.1.113`）、`TARGETS`／`JOBS`。外部依赖只有 `curl`／`tar`＋`xz`／`ssh`（到板取 espeak-ng 头与 `.so`）。

**四个坑（脚本存在的全部理由，每条都是实测撞出来的）**：

| 坑 | 现象 | 解法 |
|---|---|---|
| 交叉工具链的 glibc 必须与板子同期 | 用发行版自带的 gcc-15 交叉（glibc 2.43）**能链上，板上加载就死**：`GLIBC_2.38 not found`／`GLIBCXX_3.4.32 not found` | 取 **focal 的 gcc-9 交叉**（sysroot 上限 GLIBC_2.30 ≤ 板子 2.31），解包到 `$WORK/toolchain` |
| 板图里没有 libsndfile 的头与静态库 | 板上只有 `libsndfile.so.1`，链不上 | 本机交叉编一个**静态、只留 WAV/PCM** 的 libsndfile 再链入（顺带甩掉全部编解码依赖） |
| 板子的 `libespeak-ng.so` 自身还依赖 pcaudio／sonic／asound／pulse | 这些在板上、不在交叉 sysroot 里，链接期报未定义 | 链接加 `-Wl,--allow-shlib-undefined`，留给板子的加载器运行期解析；最终 `NEEDED` 只剩 `libespeak-ng.so.1`／`libpthread`／`libm`／`libgcc_s`／`libc` |
| `scp` 不带执行位 | 落地不可执行，`Popen` 直接 EACCES | 板上 `chmod +x`（脚本替你做） |

**判"能不能上板"只看三样**（与「三·补」第 6 步同一套口径，只是参照集小得多）：

1. `readelf -d <bin>` 的 `NEEDED` 每一项在板上都存在（板外跑不了交叉件，**别指望 `ldd`**）；
2. `readelf -V <bin>` 引用的最高 `GLIBC` 版本 ≤ 板子的 **2.31**；
3. 板上起得来、出 WAV／出声——**这一步只有板子能给**，静态门禁全绿不等于能跑。

**边界（别照着这一节乱搬）**：吃 iCraft kit／`libicraft_*`／cp38 扩展的件**不属于这一类**，照旧回校机（[[win无wsl交叉编译]]）；板上仍然**禁止编译**——这条路只解决"在哪编"，不解决"在哪跑"。本类的实测读数（板端启动、每句耗时、常驻与一次性产物逐字节相同）在 [[实时伪tts]]。

## 三、SOP（照抄，按顺序）

1. **定后端档，再定路由**：本项目一律 **ZG330**（一·补节）；把 toml 或 `--backends` 写到 `BY`/布衣上，产出的件在悟净上加载不了。然后对照第二节，先判断这件事属于"编译"还是"模型编译"还是"跑"。判错的代价最大——把 imodel 编译往校机上找会直接撞墙（无 CLI）。
2. **看校机在跑什么**（10-16 晚她判「删除要 python=0 的门禁，跑」之后，**这一条不再是门禁**，只是记账）：
   ```
   ssh school-guest "tasklist //FI \"IMAGENAME eq python.exe\""
   ```
   数出来非 0 **照样起构建**——`run-builds.sh` 里那段 `REFUSE`/`exit 9` 已删（读数和归因见 [[校机交叉编译环境搭建SOP]] 第八节、第九节更正 8）。计数仍打在日志第一行，用途只剩一个：事后解释那一轮为什么慢。**这条删的是算力礼让，不是安全规矩**：停止只准用驱动脚本的 `--stop`、**不许关任何控制台窗口**（关了会连坐杀掉分隔的 worker——校机实测 4/4），这条照旧有效。
3. **准备输入**：脚本＋源码＋donor 打成 `payload*.tar.xz`，从本机 `tar -cf - … | ssh` 或 `scp` 单文件送到校机；**落盘后逐个 `ssh school-guest "dir <路径>"` 确认并核 md5**（`dir` 只列第一块盘；`.raw` 不能跨平台 md5 验收）。
4. **校机跑输入侧**：`D:/yzd/MSYS2/usr/bin/bash.exe --login D:/yzd/WCIS/crosswin/run-donors.sh pre`（`--login` 不能省，PATH 靠 rc 文件）。`bsdtar` 在 Windows 建不出符号链接，解包报非零是**预期**，只点名单个成员解。
5. **校机跑编译侧**：`… run-donors.sh build`（10-15 实跑用的是 `run-l2fix.sh`）。日志同时进终端与 `logs/`，中文是 GBK：**先落文件再看**，管道里直接 `iconv` 会把整条管道带走；含 NUL 的日志 `grep` 要 `-a`。
6. **读静态门禁**（判"能不能上板"的口径，全在 [[win无wsl交叉编译]] §4.3）：NEEDED 闭包命中 `ref/board-libs.txt`(798 行) ∪ `kit/lib`；`GLIBC ≤ 2.31`／`GLIBCXX ≤ 3.4.28`／`CXXABI ≤ 1.3.11`；扩展模块禁 NEEDED libpython 且导出 `PyInit_*`（查这条**必须** `readelf --dyn-syms -W`，不带 `-W` 名字被截断会假红）；pybind11 的 internals id 与厂商件不同是**天然差异**，不是错误。
7. **模型那一半回本机**：`icraft compile config/ZG/*.toml` → 逐段读 `compile_target` 定缺口 → 需要数值就 `icraft-run --backends "ZG330,axi://…;Host"`（`;Host` 必带）＋ `--dump_format HQB --dump_output`。
8. **交叉部署**：产物从校机取回本机（或直送板），**上板前 `md5sum` 逐个核**；板上只跑不编。
9. **写台账**：任何落到板子的文件，当场在 [[板端我方代码与产物台账]] 加一行（本地源路径＋板上路径＋大小＋md5＋用途＋启动方式），行号先 `grep` 现值再 ＋1。

## 三·补 照抄卡：环境已经就绪，这一轮就是编一个东西

> 上面九步回答"这件事该给谁干"；这一节回答**"站到校机前面的时候，手要敲哪几条命令"**。路径、入参、判据、取件、登记全部按 **2026-10-16 晚之后的现役状态**写：盘上只剩 `D:\yzd\WCIS\crosswin` 一个 crosswin 根（`attr1016`、`tmp\sop1016` 两个实验根已送进 D 盘回收站，可还原）。**这一节不含任何搭环境的动作**——七步与验收判据在 [[校机交叉编译环境搭建SOP]]，只有那条链红了才回那页。

### 0. 开工前三问（答错的代价最大）

| 问 | 怎么判 | 不是怎么办 |
|---|---|---|
| 环境就绪了吗 | `dir D:\yzd\WCIS\crosswin\kit` 在、`D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-g++.exe` 在 | 回 [[校机交叉编译环境搭建SOP]] 第三节按七步搭；**别在本页找建环境的命令** |
| 要编的是哪一类件 | 板端 C++ 可执行／`.so` → `build.sh`；cp38 Python 扩展／嵌入解释器 → `build-py.sh`；**模型 → imodel 不在这台机上**；**不吃 kit 的通用程序 → 不在校机编，回本机 WSL 走「二·补」那个脚本** | 模型那一半校机**根本没有 iCraft CLI**，回本机 `C:\Icraft\CLI v3.39.0`（第二节）；通用程序别往校机搬，那条链的输入跟它无关 |
| 后端档 | 一律 **ZG330** | 布衣档的件在悟净上加载不了（一·补节） |

### 1. 现场路径（照抄，Windows 与 MSYS 两种写法都给出）

| 角色 | Windows | MSYS（脚本里用的） |
|---|---|---|
| 现役根 | `D:\yzd\WCIS\crosswin` | `/d/yzd/WCIS/crosswin` |
| 工具链（10.3-2021.07，i686 宿主包靠 WoW64 跑） | `D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu` | `/d/yzd/tools/cross/` 同名 |
| bash | `D:\yzd\MSYS2\usr\bin\bash.exe` | `D:/yzd/MSYS2/usr/bin/bash.exe`（**`--login` 不能省**，PATH 里的 `/usr/bin` 来自 rc 文件） |
| cmake 4.4.4／ninja 1.13.2 | `D:\yzd\MSYS2\mingw64\bin` | `build.sh:13` 把它写死成 `MINGW=/d/yzd/MSYS2/mingw64`，**没有覆盖口**（工具链自带 gcc 但不带 make ⇒ 生成器只能选 Ninja） |
| payload 正本 | `C:\Users\YiZhidi\payload2.tar.xz` | 17,742,872 B／md5 `2bfde4cb37cee7f07f773b349f9b41d4`（三代链见环境页第三节第 2 步） |
| 两颗大 deb（donor，不进 payload） | `D:\yzd\WCIS\crosswin\donor\` | 只在重建 `kit/` 时才用得到 |

### 2. 把这一轮的活送进根（改的永远是开发机那份正本）

开发机正本＝`S:\apps\llm\agentwork\crosswin\`：`src/`（厂商 BYZG demo 树：`src/src/*.cpp`＋`modelzoo_utils/`）、`src-py/`（cp38 四件源）、`proj/CMakeLists.txt`（target 定义）、`cmake/crosswin-toolchain.cmake`、`ref/`（门禁比对照表）、脚本本体。

- **一批件**：`tar -cf - src proj | ssh school-guest "cd /d/yzd/WCIS/crosswin && tar -xf -"`；**单文件**：`scp`。**落盘后逐个 `ssh school-guest "dir <路径>"` 确认＋`md5sum` 核**（`dir` 只列第一块盘；`.raw` 不能跨平台 md5 验收；scp 的**本地源路径**带盘符会失败，远端带盘符 10-16 拉日志时可行）。
- **覆盖 payload 里的成员＝单点解**：`tar -xJf payload2.tar.xz -C /d/yzd/WCIS/crosswin ./build.sh` 这种点名解一条。**绝不重跑 `run-presbuild.sh`**——它无条件再解一遍 payload，而且 `make-kit.sh` 会先把现役 `kit/` 抹掉。要让补丁长期生效就 `pack-payload.sh` 重打。

新增一个 C++ target 要动哪几处（**10-16 深夜已按这张表在现役根实跑过一轮：改 1／2／3 三处、链接清单不动 ⇒ `ALL L1 GATES PASS`，全部读数见下表之后**）：

| # | 位置 | 现值 | 为什么必须一起改 | 实跑判定 |
|---|---|---|---|---|
| 1 | `proj/CMakeLists.txt:15` | `set(TARGET_NAME yolov8n)` | `:42` 按 `src/src/${TARGET_NAME}.cpp` 取源文件，所以新名要按这个约定放源码 | **要改，改了这一处就够 CMake 侧** |
| 2 | `build.sh:34`（preflight 清单） | `"$SRC/src/yolov8n.cpp"` | 不改就 `[0] preflight` 直接 `FATAL missing` / `exit 2` | **要改**（实测三个模式各只命中 1 处，`sed` 定点安全） |
| 3 | `build.sh:68` | `find "$BUILD" -maxdepth 1 -type f -name 'yolov8n*'` | 不改就找不到产物；**模式必须带引号**（不带引号会被 bash 拿 `$HERE` 下的杂散同名文件展开掉，这条踩过） | **要改** |
| 4 | `proj/CMakeLists.txt:43-45` | `Icraft::HostBackend BuyiBackend ZG330Backend` ＋ `${OpenCV_LIBS}` ＋ `libyaml-cpp.a` | 动了链接清单就要重跑 L1b，比对 `ref/expected-needed.txt` 那 12 项 | **不用改也能过**：本轮源件（一个只用 `std::string`／`fopen` 的最小件）**不引用任何厂商符号，12 项 NEEDED 仍然全部留在产物里** ⇒ 那 12 项是链接清单给的，不是源码引用给的。真把清单删掉才会红 |
| 5 | `proj/CMakeLists.txt:11` | `if(NOT EXISTS "${CROSSWIN_SRC}/src/yolov8n.cpp")` → `FATAL_ERROR` | **这张表原先漏了这一处**。它是"厂商源在不在"的检查，不是"新 target 源在不在"的检查 | **本轮没咬**（`src/src/` 里 `yolov8n.cpp` 仍在）；只有把 `src/` 换成不含厂商 demo 的新工程时它才会拦，那时候要么改这行、要么留一份占位的 `yolov8n.cpp` |
| 6 | `build.sh:17`＋`:71` | `REF_SIZE=6600360`（10-05 容器件）与 `delta=$((sz-REF_SIZE))` | 这一行是**记账**、不是门禁，换 target 后它照样打数但意义变了 | 本轮新 target 打出 `SIZE=20248 delta=-6580112`——**这个 delta 不进门禁、别拿它判红** |

实跑读数（`t1-round.sh`，日志 `<根>\logs\t1-20261016_063256.log`；最小件 `cxx_probe1016.cpp` 走 `src/src/` 约定）：

- 编译侧：`MARKER RC_BUILD_T1=0`、`ALL L1 GATES PASS  bin=…/build/cxx_probe1016`。产物 **20,248 B**／md5 `fff6359f8f6ecf78bc3f7a28f5a07585`，`ELF64 + AArch64 + Type: EXEC`。
- NEEDED **14 项**＝那 12 项全在 ＋ 多 `libcudadefault.so`／`librt.so.1`（L1b 判 `PASS` 并打 `NOTE extra`）；`yolov8n` 同段多的是 3 项（多一颗 `ld-linux-aarch64.so.1`）。
- 上限（L1c）按件本身走：新件要 `GLIBC 2.17／GLIBCXX 3.4.21／CXXABI 1.3.9／GCC 3.0`，`yolov8n` 要 `2.29／3.4.26／1.3.9／4.5.0`——**两条都在板子的给得起范围内，判据不变**。
- 还原：`build.sh` 与 `proj/CMakeLists.txt` 的 md5 回到改前（`b6cc0b08…`／`fde4f25b…`，日志打 `SAME`）、`.t1bak` 零残留、探针源件已挪出根（`C:\Users\YiZhidi\cxx_probe1016.cpp.kept`）。
- 还原后重跑 `build.sh`：`RC_BUILD_BACK=0`、`SIZE=6408568 delta=-191792`、`build/yolov8n` md5 **回到锚** `2f9290936028cc0b2ddca5376490a03a` ⇒ "同一个根重编逐字节不变"**第二次复现**（首次是当晚原地复跑那一轮）。
- **公开更正一条（我自己的预测错了）**：写卡时我预判"新 target 不引用厂商符号 ⇒ `ld --as-needed` 会把六颗 icraft 库丢掉 ⇒ L1b 判 MISSING 变红"。实跑**相反**：NEEDED 12 项一项没少。机制没查（没看链接行有没有 `--as-needed`），所以这条只到"预测被否证"，别引用成"NEEDED 与源码引用无关的机制证明"——那是同一轮里"换 target 不改链接清单就能过 L1b"这个**现象**的读数，机制标 C。
- 本轮是**直接调 `build.sh`**（卡上第 3 节"单跑 L1"那条）。若改走 `run-builds.sh`，它第 I 段那句 `md5sum yolov8n.prev build/yolov8n` 在换 target 后比的是不存在的文件——按读脚本只会多打一行报错、不进 `RC` 判定，**这条没实跑，标未实测**。

cp38 扩展／嵌入件：源码放进 `src-py/`，在 `build-py.sh:69-79` 那五条 `run` 之后照抄一条（C++ 件＝`-O2 -std=c++14 -fPIC -fvisibility=hidden -shared $INC`，用到 numpy 再加 `$NPY`；纯 C 件去掉 `-std`；要链 libpython 的嵌入件加 `$LINKPY`），再把新件名加进 `build-py.sh:114` 的产物清单和 `:127` 的扩展模块契约循环。**同样未实测。**

### 3. 跑

| 目的 | 命令（开发机侧照抄） |
|---|---|
| **只跑编译半段（L1＋L2，最常用）** | `ssh school-guest "D:/yzd/MSYS2/usr/bin/bash.exe --login D:/yzd/WCIS/crosswin/run-donors.sh build"` |
| 只跑 L1（或只跑 L2） | ssh 进去默认是 **cmd**（`$` 不展开、`;` 不是分隔符），别在命令行里拼 `cd … && bash …`。**写一个 payload 里没有的脚本名**当 wrapper（例：`this-run.sh` 内容 `cd /d/yzd/WCIS/crosswin && bash ./build.sh`），送过去再 `--login` 调它 |
| 换根／换工具链副本时 | `bash build.sh /d/yzd/tools/cross/<那棵树>`、`bash build-py.sh /d/yzd/tools/cross/<那棵树>`——**工具链只吃第 1 位置参数**（`build.sh:10`／`build-py.sh:16` 是 `${1:-默认}`），`export TC=…` 对这两个脚本无效，不传就静默用回 `/d/yzd/tools/cross` 那颗 |
| 重建输入（kit／pyroot／uapi） | `… run-donors.sh pre` —— **平时不要跑**，它会重做 `kit/` |

日志：脚本自己 `exec > >(tee -a …)`，落在 `<根>\logs\build-*.log`／`build-py-*.log`／`run-donors-*.log`。中文是 **GBK**：先落文件再看（`ssh school-guest "type <路径>" | tr -d '\r'` 或 scp 拉回），管道里直接 `iconv` 会把整条管道带走；含 NUL 的日志 `grep` 要 `-a`。

### 4. 读静态门禁（"能不能上板"的口径全在这一格，产物存在不算数）

**L1（`build.sh`，退出码 0 全绿／2 preflight 或 configure·build 失败／3 门禁红）**

- `ALL L1 GATES PASS  bin=…`，同段 `:71` 打 `SIZE=` 与容器参照 6,600,360 B 的 delta（现役根这件是 6,408,568 B，差 −191,792 B，口径见 [[校机无容器交叉编译]]）。
- L1a ELF64＋AArch64；L1b `ref/expected-needed.txt` 那 **12 项一个不能少**（缺＝起不来＝红；多出来的是记账，但板上必须真有）；L1c `GLIBC ≤ 2.31`／`GLIBCXX ≤ 3.4.28`／`CXXABI ≤ 1.3.11`。
- 回归锚 `build/yolov8n` md5 `2f9290936028cc0b2ddca5376490a03a`：**只能当"同一个根重编不变"的锚**（10-16 晚现役根原地复跑验实）。锚对不上先查根路径与工具链路径有没有换——**跨根字节不等是已知规律**（编译期嵌了绝对路径，字节律在环境页第八节前半），不是环境坏了。

**L2（`build-py.sh`，退出码 0 全绿／2 preflight／3 编译失败／4 门禁红）**

- 五件逐件跑 `[2]`～`[6]` 段：ELF64＋AArch64、NEEDED 闭包命中 `ref/board-libs.txt`(798 行) ∪ `kit/lib/aarch64-linux-gnu/`、三条版本上限。
- 扩展模块（`_pybind_ext`／`_numpy_ext`／`_capi_ext`）**禁止** NEEDED `libpython*`，且必须用 `readelf --dyn-syms -W` 查到 `PyInit_<模块名>`——**不带 `-W` 长名字被截断，会出假红**；numpy 件不得链任何 `PyArray_*`（那张函数指针表是 import 时取的）。
- pybind11 的 internals id 天然＝`pybind11_internals_v4_gcc_libstdcpp_cxxabi1014__`（这颗工具链 `__GXX_ABI_VERSION` 是 1014），厂商件是 `…1013__`（GCC 9 构建）⇒ **这不是错误**。要与厂商件在同一进程里换 pybind11 类型，就上 `crosswin_pybind_ext_v1013.so`（`-DPYBIND11_BUILD_ABI='"_cxxabi1013"'` 那一颗）：它是**同一个模块的另一种构建，上板是替换 `crosswin_pybind_ext.so`，不是并排摆着**。
- 嵌入件 `crosswin_embed` 必须 NEEDED `libpython3.8.so.1.0` 且绑到 `Py_Initialize`。

### 5. 取件回本机

`scp school-guest:D:/yzd/WCIS/crosswin/build/yolov8n .`（cp38 那五件在 `…/build-py/`）。**两端 `md5sum` 相同才算取件完成**；产物归开发机正本目录下，交付快照另放。
**这条命令本身没跑过**：10-16 实跑的是"拉日志回来"（同形、远端带盘符可行），产物一直留在校机根里没取过——开发机 `crosswin\` 下**没有** `build`／`build-py` 两个目录（刚 `ls` 过）。真取的时候第一件事就是核这条命令对不对，别默认它能过。

### 6. 上板（只有她要点的时候；**板上禁止编译**是硬规矩）

1. 动板子前先读占用登记：`ssh deb-h61 'cat /home/user/Desktop/113.txt'`，非 `off` 就不测。
2. SFTP 传过去，**现场 `md5sum` 逐个核**（`.raw` 这类不跨平台核）。
3. 当场在 [[板端我方代码与产物台账]] 加一行：本地源路径＋板上路径＋大小＋md5＋用途＋启动方式，行号先 `grep` 现值再 ＋1（页里写死的旧计数一律不信）。
4. 跑起来＝L3，只有板子能给。

### 7. 三条别踩（每条都是实测代价）

- **不许关任何控制台窗口**：关了会连坐杀掉分离启动的 worker（校机实测 4/4）；她那批 ASR 的停止只准用它驱动脚本的 `--stop`。
- **不在开发板上编译**：993 MB 里 256 MB 是 CMA 池，匿名页额度只有 700～825 MB，编译必把现役链挤死（[[板端内存上限与心跳日志]]）。
- **不在现役根之外照抄 `run-donors.sh`**，也不重跑 `run-presbuild.sh`：入口三段把根写死成 `/d/yzd/WCIS/crosswin`（换根要改的七处见环境页第六节），在别的目录跑这条＝**在现役根上重跑并抹掉它的 `kit/`**。

> 这一节里已经跑过的：第 3 节第一行那条命令、第 4 节全部判据、第 2 节"送过去＋单点解成员＋两端 md5 核"（10-16 晚现役根原地复跑，L1＋L2 全绿、产物与锚逐字节相同）、**第 2 节"新增 C++ target"那张表（10-16 深夜实跑，含那条被否证的 `--as-needed` 预判）**。**还标着未实测的两处**：新增 cp38 扩展／嵌入件那三处改动（`build-py.sh:69-79`／`:114`／`:127`——只跑过厂商那四件）、第 5 节那条取件命令（只拉过日志，开发机 `crosswin\` 下没有 `build`／`build-py` 两个目录）；第 6 节的上板动作本轮**零部署**。
>
> 顺带一条现场事实（10-16 深夜 `ls` 现役根 `src/src/`）：里面**本来就有三颗 `.cpp`**（`yolov8n.cpp`、`yolov8_plin.cpp`、`yolov8n_multi_thread_plin.cpp`，另加两颗 `.hpp`）——payload 与本机正本一致。所以想试"换 target"又不写新源码，把 `TARGET_NAME` 改成那两颗 PLIN 件的名字就行，同一张表同样适用。

## 四、什么算"这一轮做完"

编译类任务的完成判据是**第 6 步全绿**，不是"产物存在"。第 9 步之后仍然测不出前向数值与真延迟——那是 L3，只有板子能给；在板上跑之前，任何"能跑／精度是多少"的话都不许写进结论（判级按 [[验证方法学]]）。

## 相关页面

- [[校机交叉编译环境搭建SOP]]：**一次性搭环境**（无容器、无 admin）的先决条件、顺序、验收判据与上限
- [[win无wsl交叉编译]]：环境的建立、九件 donor、L1／L2 读数、全部踩过的坑
- [[校机无容器交叉编译]]：容器路线的第一版与 −191,792 B 的差值口径
- [[实时伪tts]]：**通用 aarch64 件**（ekho）这条路（「二·补」）的实测读数与交付形态；本节只讲路由与坑，数字在那页
- [[iCraft算子支持矩阵]]：算子层的分母与"某个模型缺什么"怎么取
- [[板端内存上限与心跳日志]]：为什么禁止在板上编译
- [[验证方法学]]：L1／L2／L3 分层定义
- 记忆条目 `build-deploy-host-policy`：本 SOP 的偏好来源（10-12 定"编译一律校机"，10-15 补"剩下的回本机"）
