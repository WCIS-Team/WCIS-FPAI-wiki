---
tags: [SOP]
---

# 校机交叉编译环境搭建SOP

> **本页回答什么问题**：一台**没有管理员权限、不装容器、不装 WSL** 的 Windows 校机，怎么从零搭出能编 aarch64 板端件的环境——先决条件是什么、按什么顺序装、每一步"绿"长什么样、搭完的上限在哪。
> **分工**：本页只管**一次性搭建**。每轮怎么用（定路由→查闲→跑→读门禁→部署→写台账）在 [[交叉编译主机路由SOP]]——**已经搭好、只是要编一个东西的话，直接开那页的「三·补 照抄卡」**；输入件清单与哈希正本在 [[win无wsl交叉编译]] §3.1；L1 读数与全部踩过的坑在 [[校机无容器交叉编译]] 第五、六节。本页不复制那些表。
> **2026-10-16 做过一次"照抄复现"**：在 `D:\yzd\tmp\sop1016\` 新建第二个根，按本页七步重走，**七步全跑完**（第 7 步当时是她"现在就跑不等"破的门禁）。结果与全部偏差写在**第八节**；本页第三、四、六节的表**已按复现实测改过**；对不上旧版原文的地方在**第九节**逐列。**复现根事后按她的判定已送进 D 盘回收站**（可还原）。
> **同日更晚：她判「删除要 python=0 的门禁，跑」＋「归因实验做」**——门禁已从 `run-builds.sh` 里删掉（不再是 `FORCE=1` 那种破法，是**默认就不拦**，见第九节更正 8），现役根原地复跑 G/H 全绿且产物与锚**逐字节相同**，另起了一个只差路径长度的第三根把跨根字节差异**归因坐实**（第八节前半）；第三根随后按她「**只留一个能用的就行**」也送进回收站 ⇒ **校机盘上现在只剩 `D:\yzd\WCIS\crosswin` 这一个 crosswin 根**，编译与部署一律认它，两个实验根的读数只剩日志（第七节末两条）。本页凡"守门禁／破门禁"的旧说法都已按此改写，历史读数保留并标注。
> **一句话**：容器镜像里干的活只有五件事，五件事都能用"下载压缩包／从厂商 deb 剥／从出厂镜像削"替掉，所以环境不需要容器、也不需要 admin——**代价是这套环境只能编，不能跑**。

## 一、先决条件（这四条不满足就别往下走）

| 条件 | 校机实况 | 不满足时怎么办 |
|---|---|---|
| 一个当前用户可写的盘 | `D:\yzd\`（D 盘 2.0 T、实测可用 **1.7 T**）。一个完整根的实际用量（10-16 新根实测）：工具链压缩包 152 M ＋ 解压 **949 M** ＋ crosswin 树 96 M（不含产出）＋ kit 228 M ＋ pyroot 30 M ＋ uapi 6.9 M ＋ zlib 601 K ⇒ **整套约 1.4 G** | 换个可写目录，但**第六节那七处绝对路径要一起改**——不是旧版写的"四处" |
| 一个能跑脚本的 bash | `D:/yzd/MSYS2/usr/bin/bash.exe`（已在机上，用户级目录，不需要 admin）。10-16 实测 MSYS `3.6.10`／bash `5.3.20`，`uname` 报 `MSYS_NT-10.0-26200` | 装 MSYS2 到用户目录即可；**别用 WSL**——WSL 在校机上没有，且装了也用不上（编译侧不需要 Linux 内核） |
| cmake 与 ninja | `D:/yzd/MSYS2/mingw64/bin/` 里已有 cmake 4.4.4、ninja 1.13.2（10-16 复核未变） | **工具链自带 gcc 但不带 make**，所以生成器必须选 Ninja，别指望 Make |
| 出厂 SD 镜像可读（只为了削 donor #7/#8/#9） | 镜像在**开发机**，27.95 GiB。**削只需要一次**：削出来的 `py-sysroot.tar.xz`／`board-uapi.tar.xz`／`py-deps.tar.xz` 打进 payload，10-16 在新根解开后 md5 与开发机正本**五件全同** ⇒ 换机不必重削 | 这一件事是本 SOP 唯一不在校机做的动作：在开发机 WSL 以 root 只读挂载削包。**"无 WSL"指的是编译侧**，不是全流程不碰 WSL |

**admin 的边界**（本轮实际遵守的，A 级）：全程零安装器、零 `Program Files` 写入、零注册表、零服务、零 `dpkg`/`apt`。所有落点都在 `D:\yzd\` 与 `C:\Users\YiZhidi\` 之下。

## 二、为什么容器能整个省掉（选型理由，别重复推导）

| 镜像里提供的东西 | 无容器的替代物 | 为什么只能这样替 |
|---|---|---|
| aarch64 GCC | Arm GNU Toolchain **10.3-2021.07**，`mingw-w64-i686-aarch64-none-linux-gnu`，解压即用 | 版本必须对上板上 `libstdc++6 10.3.0-1ubuntu1~20.04`，符号版本上限才是 `GLIBC 2.31 / GLIBCXX 3.4.28 / CXXABI 1.3.11`；Windows 宿主包官方**只出 i686**（`x86_64` 那一档 404），i686 的 exe 靠 WoW64 跑 |
| 厂商 SDK 的头／库／cmake 包 | 两颗 arm64 deb 直接剥成 `kit/` | 只有 deb 里那份才是板端要用那份；从 apt pool 找等价物会串版本 |
| 板端 Python 3.8 开发件 | 从出厂镜像削 → `pyroot/`（donor #7）＋ #9 补 `libexpat.so.1`/`libz.so.1` | 板上装的是 `3.8.10-0ubuntu1~20.04.7`，**pool 已经不发 `.7`**；而链可执行件时 GNU ld 要看得见"`libpython` 自己的 `DT_NEEDED`"，工具链 sysroot 里那两颗是 x86-64 的 |
| 内核 UAPI 头 | 从出厂镜像削 → `uapi/`（donor #8） | Arm 工具链自带内核头数量 **0**；focal 的 `linux-libc-dev` 差一个 delta，不是板子那一份 |
| zlib 静态件 | 从 USTC `ubuntu-ports` 下 focal 的 `zlib1g-dev:arm64` 取 `libz.a` | 厂商 `OpenCVModules.cmake` 有 4 行把 zlib 写成宿主绝对路径 `/usr/lib/aarch64-linux-gnu/libz.so`，kit 一离开原始目录就链不上 |

## 三、搭建顺序（照抄，一次一条命令）

ssh 进去默认落 **cmd**：`$` 不展开、`;` 不是分隔符 ⇒ **一条命令只跑一个脚本文件**，复杂逻辑写进脚本再送；`--login` 不能省（PATH 里的 `/usr/bin` 来自 rc 文件）。

| 步 | 动作 | 命令（校机侧，除非标注） | 绿的样子 |
|---|---|---|---|
| 0 | 读现场 | `tasklist //FI "IMAGENAME eq python.exe"` ＋ **`df -h /d`** | python 计数**只是记账、不再拦构建**（10-16 晚她判「删除要 python=0 的门禁」，`run-builds.sh` 里那段 `REFUSE`/`exit 9` 已删，见第九节更正 8；计数仍打在日志第一行，用来事后解释"那轮跑得快／慢"）。**`wmic logicaldisk` 那条已作废——这台机上没有 `wmic`**（`command -v wmic` 空，Win11 26200 已删，见第九节更正 1） |
| 1 | 工具链落位 | **就在校机跑** `bash get-toolchain.sh`（脚本自带 curl＋断点续传＋大小核对＋md5） | 自我校验打出版本 `10.3.1 20210621`、`readelf` 可用；压缩包 `159,688,564 B` / md5 `9d82d7fa093421ddf9bad81f308dc17a`；**解压实测 17.5 s、解开 949 M**。armkeil 那条 URL 10-16 实测 HEAD **200**，所以校机能自己下——旧版写"在开发机下载再送"是错的（第九节更正 2）。**坑：脚本里那段"sysroot glibc 上限"原先只查 `libc/lib/`，那里只有 `ld-linux-aarch64.so.1`，四颗库全报 MISSING**；实体在 `libc/lib64/` 与 `libc/usr/lib64/`，本地源已改成三目录轮查（10-16 实测修后读数见第八节），**payload 里那份旧自检已在 10-16 晚重打时带上**（`pack-payload.sh` → 新 payload 见第 2 步；覆盖校机用的是单点解一个成员，不重跑 `run-presbuild.sh`，见第六节） |
| 2 | 脚本＋源码＋小 donor 送过去 | 开发机跑 `pack-payload.sh` → `scp` 到 `C:\Users\YiZhidi\` → runner 自己 `tar -xf` 到目标根 | `src-py 4  ref 3`（这两个数**才是判据**）；**`scripts` 那个数会随会话涨：旧日志里 25、10-16 复现时 39、10-16 晚重打后 42，别拿 25 当判据**（第九节更正 3）。**当前 payload ＝ `payload2.tar.xz` 17,742,872 B / md5 `2bfde4cb37cee7f07f773b349f9b41d4`**（10-16 第三次打；成员数与上一代**完全相同**＝非目录 104、`*.sh` 42，内容差三件：`run-builds.sh` 删门禁、`run-donors.sh` 删同一件事的注释、`get-toolchain.sh` 修 `from=` 标签）。**三代同链**：`54d49c8ef0bcda9751d72312655b0f0c`（17,738,644 B，10-15）→ `9e5778f4a7093c9168b27fcbf8e5fffb`（17,741,892 B，10-16 早）→ 现值；现值实体在开发机 `S:\apps\llm\agentwork\crosswin\payload2.tar.xz`（数据件，未随 D-54 收拢）。**实体副本 10-17 清点（公开更正）**：开发机只有最旧那代 `S:\work\WCIS\workenv\sopreplay\payload2-54d49c8e.tar.xz`（根按 D-54 收拢到此），`9e5778f4…` 那代**开发机侧没有实体**——它当时是被第三代原地覆盖的，改名留副本只做在校机侧（`C:\Users\YiZhidi\payload2-<前 8 位>.tar.xz`，两代都在）；此前本页与 [[状态源与决策记录#D-51 · python.exe 门禁整段删除、现役根原地复跑（同根重跑不变首次实测）、跨根字节差异用 Δ+4 单变量根归因结案（B→A）、盘上只留现役一个根|状态源与决策记录——D-51]] 写的"前两代两端都留实体副本"开发机那一半不成立。传输实测（10-16，17.7 MB 级）：走 scp **5.3 s**，两端 md5 相同；payload 里另带 `cmake 1  src 4  proj 1` |
| 3 | 两颗大 deb 落位 | 一次性放 `<根>\donor\`（不进 payload，体积原因） | md5 与本机正本逐字相同：`Icraft_3.39.0_onchip.deb` 9,192,096 B `2d1167db8a81f03d48827f53e1de16c4`、`IcraftMdzThirdParty.deb` 34,415,828 B `0cf4fcd5e87697998df934a889ad9445`（10-16 在新根重核一遍，两值复现） |
| 4 | 削包（**开发机 WSL，root**） | `bash carve-pysysroot.sh`／`carve-uapi.sh`／`carve-pydeps.sh` | 只读挂载必须 `-r -o 1075839488` ＋ `mount -o ro,noload`，`trap cleanup EXIT` 里 `umount`+`losetup -d`；出的包**必须无符号链接**（口径见 [[win无wsl交叉编译]] §2.2）。**这一步校机做不了，但只需要做一次**：产物由第 2 步的 payload 带过来，新根解开后五件 donor md5 与正本全同 |
| 5 | 三份输入装成树 | `D:/yzd/MSYS2/usr/bin/bash.exe --login <根>/run-donors.sh pre`（**只在默认根可用**，换根见第六节） | `rc_D=0 rc_E=0 rc_F=0 rc_J=0`：`PYROOT GATES ALL PASS`／`KIT READY 228M inventory: 948 files`／custom op 契约抄出／`UAPI GATES ALL PASS`。**但 `run-donors.sh`／`run-presbuild.sh`／`run-builds.sh` 三段把根写死成 `/d/yzd/WCIS/crosswin`**（五处，逐行见第六节）⇒ 在新目录照抄这条命令，**跑的是现役根，还会把它的 `kit/` 重做一遍** |
| 6 | zlib | **先单独跑 `bash get-zlib.sh`，再跑第 5 步** | `libz.a` 142,806 B、`readelf -h` 报 `ELF64 + AArch64`；四条引用改成 `${_IMPORT_PREFIX}/lib/libz.a`，闭包检查 `missing: 0`。**旧版说"已内含在第 5 步的 make-kit.sh 里"是错的**：`make-kit.sh:35` 只做存在性检查、缺了就 `FATAL: run get-zlib.sh first` 退出，`apply-zlib.sh` 才是它内部调的那半（第九节更正 4）。10-16 实测 USTC 池里 focal 那颗还在：`zlib1g-dev_1.2.11.dfsg-2ubuntu1.5_arm64.deb` 153,592 B |
| 7 | 真编译（半段二） | `… bash.exe --login … run-donors.sh build`；**换根时必须 `bash build.sh "$TC"` / `bash build-py.sh "$TC"`** | `rc_G=0 rc_H=0`：`ALL L1 GATES PASS` 且 `ALL L2 GATES PASS`。**坑：`build.sh:10`／`build-py.sh:16` 的工具链取 `${1:-默认}`，不吃 `TC=` 环境变量**，而 `run-builds.sh:18/22` 调它们时不带参数 ⇒ 换根后编译会**静默用回 `/d/yzd/tools/cross` 那颗旧工具链**。另外 `build.sh:13` 的 `MINGW=/d/yzd/MSYS2/mingw64` 写死、无法覆盖。**10-16 新根实跑**：python.exe＝4 的情况下按她「现在就跑不等」跑了（当时还是破门禁，事后门禁被整个删掉），`rc_G=0 rc_H=0`、六件**尺寸与现役根一字不差**，但**只有两件（纯 C 的那两件）md5 相同**（读数与归因见第八节）。**同日现役根原地复跑**：`rc_G=0 rc_H=0`，且 `build/yolov8n` 与锚 `yolov8n.prev` **md5 一字相同**（`2f929093…`）⇒ 同根重跑不变这条已经从推断升成实测。 |

## 四、"环境搭好了"的判据（三条同时成立才算）

1. **十段全绿**：A～J 各段 rc 全 0（读数正本在 [[win无wsl交叉编译]] 第一节）。红一段就不是"环境好了、只差跑"，而是输入不完整。**换根时这十段拆两半**：Z/D/E/F/J（zlib＋三份输入＋ABI 契约）不用编译器、当场就能自证；G/H 要 `-j 8` 编译，**不再受任何 python 门禁约束**（10-16 晚她判「删除要 python=0 的门禁」，`run-builds.sh` 里那段已删）⇒ 换根后这两段没有"就绪待跑"这个中间态，要么跑要么不跑。
2. **L1 产物 md5 命中基线** `2f9290936028cc0b2ddca5376490a03a`（`build/yolov8n`，6,408,568 B）。这条**只能当同根回归锚**用。**10-16 晚现役根原地复跑把它验实了**：`build.sh` 重编后 `build/yolov8n` 与根里的锚 `yolov8n.prev` **md5 一字相同**，L2 那五件的尺寸也没动 ⇒ "同一个根、同一套输入、重跑＝逐字节不变"是**实测**，不再是推断（kit 从 163 M 长到 228 M、donor 加 #9、payload 换代、门禁删除，这一串改动都没挪动产物）。**跨根那一半判负**：第二个根（`D:/yzd/tmp/sop1016`，27 字符）六件尺寸全同、4 件 md5 变（纯 C 两件不变）；第三个根（`D:/yzd/attr1016`，24 字符）又变、且变的是**同一批四件**——**所以这条判据的适用范围是"同一个根重编不变"，不得用作"换根／换机能复现"的证据**，跨根复现改判"编出通过同样门禁的件"＋第八节那条字节律。**另两条坑**：`run-builds.sh` 的第 I 段是拿 `yolov8n.prev` 比的，新根天生没有这个文件，它只打 `NOTE no yolov8n.prev` ⇒ 判据 2 **不会自证**，基线必须带到现场（`sop-build.sh` 已内建六件逐件比对）。
3. **零状态可复现**：`rm -rf zlib kit build` 后整条链重跑，产物 md5 不变（[[校机无容器交叉编译]] 第一节第 2 条，三条互不相同的路径各自产出同一个 md5）。**没跑过这一条，只能说"脚本这次跑通了"，不能说"这台机能重建环境"。** 10-16 在新根做了**输入侧那一半**：把 `zlib/kit/pyroot/uapi` 整体挪走（用 `mv` 不用 `rm`，可回退）后重跑四段，全 rc=0，计数 948/209/915 与现役根相同，抽样 7 个文件（含 `libicraft_zg330backend.so`、`libopencv_core.a`、`libpython3.8.so.1.0`、`Python.h`、`libz.a`）md5 **与现役根逐字节相同**。**产物侧那一半现在分两层都有读数**：*"重建输入能编出可用的件"＝新根验通（门禁全绿、六件尺寸与现役根一字不差）*；*"同一根重跑两次 md5 不变"＝现役根 10-16 晚验通*（原地复跑，L1 与锚同 md5）。跨根那半见判据 2——**不等，且已归因到编译期嵌入的绝对路径（A 级，字节律见第八节前半）**。

## 五、搭完的上限（无 admin 决定了做不到什么）

| 做不到 | 原因 | 于是这件事归谁 |
|---|---|---|
| 跑编出来的 aarch64 件 | 校机是 x86-64 Windows，WoW64 只带 x86 侧 | 板子（L2 起进程／L3 出框），见 [[验证方法学]] |
| 模型 → imodel（量化编译） | **iCraft CLI 不在这台机上**，而且它是 Windows 图形安装包、要 admin；就算装上也是 x86-64 的 | 开发机 `C:\Icraft\CLI v3.39.0`（唯一能出 ZG 档件的主机） |
| `dpkg -i` 装 donor | 无 admin，且我们**根本不需要装**——deb 只当打包材料 | 就地剥（第 5 步） |
| 自建 custom op | deb 里没有真头文件、`libcustomop.*.so` 导出 GLOBAL 符号 **0 个** ⇒ 接口与注册方式无定义来源 | 立案在 [[win无wsl交叉编译]] §3.5、第五节 5 |
| 换 GCC 9 代工具链（pybind11 身份那条干净路子） | Arm 9.3-2020.04 `mingw-w64-i686` 形态完全相同、也吃 WoW64，但**没下、没装、未验证** | 待做；现役替代是 `-DPYBIND11_BUILD_ABI='"_cxxabi1013"'`，那只是"声明兼容" |

## 六、换根／换机要改的七处路径（10-16 逐行实测）

旧版这一节写"四处"，漏了整条入口链。10-16 在新根复现时按 `grep` 数出来的就是这七处，`file:line` 是准的：

| # | 位置 | 现值 | 换根怎么办 |
|---|---|---|---|
| 1 | `run-donors.sh:13` | `D=/d/yzd/WCIS/crosswin` | 改成新根的 `crosswin` |
| 2 | `run-donors.sh:20` | `tar -xJf /c/Users/YiZhidi/payload2.tar.xz -C "$D"` | 只在 `$D/run-presbuild.sh` 不存在时才触发，通常不用改；传输落点换机才要改（`C:\Users\<用户>\`） |
| 3 | `run-presbuild.sh:5` | `cd /d/yzd/WCIS/crosswin \|\| exit 2` | 改 |
| 4 | `run-presbuild.sh:28` | `tar -xJf /c/Users/YiZhidi/payload2.tar.xz -C /d/yzd/WCIS/crosswin \|\| exit 7` | 改（一行里两处） |
| 5 | `run-builds.sh:4` | `cd /d/yzd/WCIS/crosswin \|\| exit 2` | 改 |
| 6 | `build.sh:13` | `MINGW=/d/yzd/MSYS2/mingw64` | **写死、没有覆盖口**。MSYS2 属"机器级"件，换根不用动，换机才需要 |
| 7 | `build.sh:10` 与 `build-py.sh:16` | `TC=${1:-/d/yzd/tools/cross/gcc-arm-10.3-…}` | 默认指向**共享**工具链。要用新根解压的那颗，只能把路径当**第 1 位置参数**传进去，`export TC=` 对这两个脚本无效 |

**两条由此而来的硬规矩**：

- **入口三段改完也活不过一次运行**：第 4 处那行每次跑 `run-presbuild.sh` 都无条件再解一遍 payload，会把我 sed 过的 `run-presbuild.sh` 本身还原成写死旧根的那份（而 bash 还在读这个文件）。**所以复现到新目录，正确做法不是"改 run-donors.sh 再跑"，是另起一个 payload 里没有的文件名当 wrapper**（本轮用的是 `sop-pre.sh`／`sop-re.sh`／`sop-build.sh`），在 wrapper 里按顺序直接调 `get-zlib.sh`／`setup-pysysroot.sh`／`make-kit.sh`／`probe-customop-abi.sh`／`setup-uapi.sh`／`build.sh "$TC"`——这些 stage 脚本自己全是 `HERE=$(dirname $0)`，天然可搬。要让补丁长期生效，就得**重打 payload**——**这条 10-16 晚已按她「重打」执行**：新 payload 17,741,892 B / md5 `9e5778f4a7093c9168b27fcbf8e5fffb`，内容与上一代的差集只有 `get-toolchain.sh` 这一处自检。覆盖校机**不是**重跑 `run-presbuild.sh`（它会无条件重解 payload、还会把 `kit/` 重做），而是在现役根里单点解一个成员：`tar -xJf payload2.tar.xz -C /d/yzd/WCIS/crosswin ./get-toolchain.sh`；该文件 md5 从 `758dca1894803000f60ac06e775c7176` 变成正本 `b87b50686a89e62b1c4854c4b3c1c10d`，`bash -n` 过，payload 里那份解出来跑自检要打三目录轮查后的真读数而非四行 MISSING。旧 payload 两端各留副本（开发机 `S:\work\WCIS\workenv\sopreplay\payload2-54d49c8e.tar.xz`、校机 `C:\Users\YiZhidi\payload2-54d49c8e.tar.xz`）。**单点解的代价**：包内多出的四件只进来了 `get-toolchain.sh` 这一件——覆盖后实测现役根 `ref` 仍是 **2**（`ref/icraft_op_support_table.txt` 没进去），`scripts` 数是 42 但**没逐件比对根里那 42 与包内那 42 是否同一集合** ⇒ **根的计数和包的计数从此不是一回事，判据只能看包内容、不能看某个根碰巧攒了多少脚本**。
- **想在旧根之外照抄第 5／7 步的命令＝在现役根上重跑**，`make-kit.sh` 会先把它的 `kit/` 抹掉。这条是这次复现里最贵的一条风险。

跨机不变的三件事：`ssh` 进去是 cmd 所以要跑脚本文件；中文输出是 GBK 所以先落文件再把 log 用 scp 拉回来（本轮全部这么做的，`iconv` 只在管道里临时用）；**第三条原来是"起构建前查 `python.exe` 的硬门禁"，10-16 晚已被她判删**——它数的是任何 python 进程，10-16 复现时读到 4 个（两个各占 29～31 GB 工作集，是她的批处理），于是第 7 步整段被挡、复现只做到"就绪"；她先破了一次（「1 现在就跑不等」，`FORCE=1`），当晚进一步判「删除要 python=0 的门禁，跑」⇒ `run-builds.sh` 里那段 `REFUSE`/`exit 9` 已整体删除，只留一行 `echo "python.exe processes: $n"` 当记账，`run-donors.sh` 头部同一件事的注释也删了；删完重打 payload（三代链见第三节第 2 步）并当场跑了现役根 G/H（python.exe＝4→6，一路没拦）。**换根要改的七处一条没动，删的只是门禁**。

**换根还会换产物，而且换多少字节是可以算的**（见第八节前半）：根路径以编译期字符串的形式进 C++ 件，所以**跨根的 md5 一定不同、尺寸不变**。这条决定了"换机能编出同一个字节串"这句话在本项目里**不成立**，能承诺的只有"换机能编出通过同样门禁的件"。字节律（10-16 晚实测）：**每个嵌入的出现点，根路径每长 1 字符就多 1 字节**——`.so` 里四出现点、Δ+4 ⇒ `.rodata` 正好 +16 B；纯 C 两件零出现点 ⇒ 跨任何根都逐字节相同。

## 七、没做的（事实，不含判断）

- 上板那一层全空（L2 的 `import`、L3 的跑图出框）；**L3 她 2026-10-15 明确判"不做"**，别自作主张排。
- **跨根字节律只验了两个 Δ（+4 与 0）**：Δ+4 那个根（`D:\yzd\attr1016`）是"拷贝现役根已建好的输入、只换根路径"，工具链、kit、pyroot、源码全同一份；**跨机（换一台校机、换一份 MSYS2）会不会有同一条律，没有读数**。第八节那条"每出现点每字符 1 字节"在 Δ+7 那根上是 4×7＝28 对上实测 32 的**四字节缺口**——那一根同时把工具链也搬了（前缀长 +12），属双变量，所以**不拿来配律**，只作历史读数保留（这两个根现在都不在盘上，见下面两条）。
- **`D:\yzd\attr1016` 已清掉**（10-16 深夜，她判「只留一个能用的就行」——归因根是实验品、编译从来不用它，现役根 `D:\yzd\WCIS\crosswin` 才是唯一那个）：**1,284 文件／263.2 MB** 整体进 D 盘回收站，**不是真删、可还原**。姿势＝第八节末那条 `SHFileOperation`＋`FOF_NOERRORUI`，**且严格照"先探针、后真树"走**：探针 `D:\yzd\tmp\rcprobe1`（5 文件／12,305 B）`rc=0`、`aborted=0`、0.5 s，路径消失＋回收站条目 28,453→28,459 —— **容量读数 `delta 0 MB` 不是"没进回收站"，是 0.1 MB 的显示精度把 12 KB 吃掉了，判据只能看条目数**。真树 **0.3 s** 返回 `rc=0`，条目 28,459→**29,744**（＋1,285＝1,284 文件＋1 个目录记录）、容量 **+263.2 MB** 与事前 `find` 穷举值一字相同，`$I` 里的还原位置＝`D:\yzd\attr1016`。清前清后都核过现役根未被动：`kit 948`／`pyroot 209`／`uapi 915`／`zlib 7`，`build/yolov8n` 与锚 `yolov8n.prev` 仍是 `2f9290936028cc0b2ddca5376490a03a`，入口三件脚本仍是第三代那三个 md5，`D:/yzd` 下 `*/crosswin` 只剩现役根这一个。**代价＝第八节那条字节律从此没有就地可复测的第二数据点**，读数只剩 `pl2-*.{log,raw}` 这批日志：`pl2-attr.log` 已按 D-54 收拢到 `S:\work\WCIS\workenv\sopreplay\`，`pl2-build.log`／`pl2-diff.raw`／`pl2-diff2.raw` 仍在 `S:\apps\llm\agentwork\sopreplay\`；要再测跑 `pl2-attr.sh`（在新根，它自带"目标根已存在就 `exit 3`"，根没了能直接重建）。
- **复现根已按她的判定清掉**（`D:\yzd\tmp\sop1016` 整体送进 D 盘回收站，含 `_trash-1016` 与解压的工具链副本）。实测清点：**27,825 文件／1,992.3 MB**，`SHFileOperation` 调用 **4 s** 返回 `rc=0`，回收站条目数 627→28,453、容量 +1,992.3 MB，`$I` 记录里的还原位置＝`D:\yzd\tmp\sop1016`。**不是真删，可还原**。这 1,992.3 MB 比第一节"整套约 1.4 G"大，是因为整个根里除了环境本身还装着 `donor/` 两颗大 deb（43.6 MB）、`_trash-1016` 四棵首轮树、那份 payload 副本、`build*` 产物与 `logs`——**没逐目录拆分，差额未穷举**。现役根 `D:\yzd\WCIS\crosswin` 事前事后都核过：kit 948／pyroot 209／uapi 915／zlib 7／L1 md5 仍是 `2f9290936028cc0b2ddca5376490a03a`，`D:\yzd\tmp` 回到清理前的 122 个条目。所以第八节那批新根读数**现在只有日志为证**（`S:\apps\llm\agentwork\sopreplay\`），要复跑得重建根。
- `uapi/` 至今没有消费者：仓里没有把 `-isystem $UAPI/usr/include` 挂进真实编译的脚本。
- 部署包没成形：这 6 件上板要连带什么（`kit/lib/aarch64-linux-gnu` 23 颗、`libcudadefault.so`、`Dynamic` 45 文件 5.0 M；`pyroot` **不带**）没有成文清单，落板路径未定。
- L1 件与 10-05 容器件那 **−191,792 B（−2.9 %）** 仍未归因。
- 第一节"换目录后要不要重装 MSYS2"**仍未实测**——本轮换的是根，MSYS2 用的还是同一份，所以这一条既没证实也没证伪。"pacman 在用户目录是否需要 admin"同样没测。
- **payload 三代都没有改入口那七处写死的路径**：10-16 晚的第一次重打只带上 `get-toolchain.sh` 的自检修正，当晚的第二次重打只带上删门禁那三件（`run-builds.sh`／`run-donors.sh`／`get-toolchain.sh` 的标签行）；**`run-donors.sh`／`run-presbuild.sh`／`run-builds.sh` 里那七处 `/d/yzd/WCIS/crosswin` 一个都没改** ⇒ 换根仍然要靠 payload 里没有的 wrapper。`build.sh:13` 的 `MINGW` 同样原样。
- **现役根的 G/H 已对着新 payload 复跑**（10-16 晚，她判「跑」之后）：`rc_G=0 rc_H=0`、`ALL L1 GATES PASS`＋`ALL L2 GATES PASS`、L1 与锚同 md5。但**第一节那十段 A～F/J 的绿读数仍属旧 payload**——本轮只单点解了三个成员，输入侧五段（Z/D/E/F/J）没有对着第三代 payload 重跑，虽然这三件脚本都不在那五段的路径上。

## 八、2026-10-16 照本页在新根复现的读数

复现对象：`D:\yzd\tmp\sop1016\`（`tools\cross\` ＋ `crosswin\`），与现役根 `D:\yzd\WCIS\crosswin` 并存、互不写入；跑完按她的判定整体送进 D 盘回收站。全部读数取自落盘日志（开发机侧 `S:\apps\llm\agentwork\sopreplay\` 的 `sop-probe.log`／`sop-r12.log`／`sop-pre.log`／`sop-re.log`／`sop-rdy.log`／`sop-ceiling.log`／`sop-build.log`／`sop-diff.raw`／`sop-diff2.raw`；10-16 晚那一批在 `pl2-apply.log`／`pl2-build.log`／`pl2-attr.log`／`pl2-diff.raw`／`pl2-diff2.raw`）。**上面那张分步表（步 0～7、判据 3）的 payload 侧读数都是在 10-15 那一份（`54d49c8e…`）上取得的**；她判「重打」后变成 `9e5778f4…`（`scripts 39→42`、`ref 2→3`、`get-toolchain.sh` 一处内容差），判「删除门禁，跑」后又是第三代 `2bfde4cb…`（成员数不变、三件脚本内容变）⇒ 表里凡是 `54d49c8e`／`39`／`ref 2` 都是**历史读数、不是现值**，现值见第三节第 1／2 步与 [[win无wsl交叉编译]] §3.1。**下面的「归因实验」小节是第三代 payload 上的实测**，不是那一批。

| 步 | 结果 | 关键读数 |
|---|---|---|
| 0 | **口径要改** | `wmic` 不存在；`df -h /d` 报 2.0 T／可用 1.7 T；python.exe **4**（4,336 K×2 ＋ 30,430,700 K ＋ 32,869,452 K） |
| 1 | 通 | 压缩包 md5 命中 `9d82d7fa…`；`tar -xf` 17.48 s；g++ `10.3.1 20210621`；readelf `2.36.1.20210621`；**解压 949 M**；armkeil 那条 URL HEAD **200** |
| 2 | 通 | **（上一代 payload，现值见第三节）** 两端 md5 同 `54d49c8e…`，scp 5.1 s；解开 `scripts 39  src-py 4  ref 2  cmake 1  src 4  proj 1`；**payload 内五件 donor md5 与开发机正本逐字相同** |
| 3 | 通 | 两颗大 deb md5 复现 `2d1167db8a81f03d48827f53e1de16c4`／`0cf4fcd5e87697998df934a889ad9445` |
| 4 | **校机做不了** | 靠 payload 复用，等价于已验（见第 2 步那行） |
| 5 | 通（要用 wrapper） | `rc_D=0 rc_E=0 rc_F=0 rc_J=0`：`PYROOT GATES ALL PASS` 209 文件／`KIT READY 228M inventory: 948 files` 闭包 `missing: 0`／custom op 契约抄出七行（`ImageMake`／`NearestUpsample`／`RGBADecoder`／`RGBDDecoder`／`SegPost`／`SingleChannelDecoder`／`WarpAffine`，provenance 里 `det_post` 与 `det_post_zg` 同为 `8928301f`）／`UAPI GATES ALL PASS` 915 文件（linux 711＋drm 28＋asm-generic 36＋alsa 44） |
| 6 | 通 | USTC 池今天有 `zlib1g-dev_1.2.11.dfsg-2ubuntu1.5_arm64.deb`，153,592 B → `libz.a` 142,806 B，`ELF64 / AArch64`，`members 15` |
| 7 | **通（破门禁跑的）** | 先做两份 preflight 的只读复刻＝**L1 缺 0、L2 缺 0**；再把新根工具链当 `$1` 喂进两份脚本，`rc_G=0 rc_H=0`、`ALL L1 GATES PASS`＋`ALL L2 GATES PASS`，六件**尺寸与现役根一字不差**（下表）。python.exe 当时＝4，是她给的破例 |
| 判据 3（输入侧） | 通 | 四棵树 `mv` 走后重跑：zlib/pyroot/kit/uapi 四段 rc 全 0，计数 948/209/915 与现役根同，**抽样 7 个文件 md5 与现役根逐字节相同** |
| 判据 3（产物侧） | **半通** | 重建后的输入**能编出通过全部门禁的件**（`rc_G=0 rc_H=0`）；"同一根重跑两次产物不变"没验（新根只编一次）。**判据 2 的跨根那一半判负**，见下面那张逐件比对表 |

修好后的工具链自检读数（新根那颗，`sop-ceiling.log`）：`libc.so.6` 最高标到 `GLIBC_2.33`、`libm.so.6` `GLIBC_2.32`、`libstdc++.so.6` `GLIBCXX_3.4.28`（＝板上上限）、`libgcc_s.so.1` `GLIBC_2.17`；`libc/lib/` 里确实只有 `ld-linux-aarch64.so.1`。**注意别读反**：sysroot 自报的上限高于板子 2.31，这不构成冲突——真正起作用的是链完之后对产物逐符号的那道 `GLIBC ≤ 2.31` 门禁，它一直是编译侧在把（[[校机无容器交叉编译]] 第五节）。**自检输出那个小毛病已经收掉**（10-16 晚）：`from=` 那栏原先打成 `from=liblib64/libc.so.6`（`${p#*libc/}` 剥掉 `libc/` 之后又多拼了个 `lib` 前缀，四行读数本身是对的、只是标签难看）；正本删掉那个前缀、重打进第三代 payload，解到现役根再跑一遍打印是 `from=lib64/libc.so.6`／`from=usr/lib64/libstdc++.so.6`，四行上限值与上面完全一致。

第 7 步的逐件比对（现役根基线 vs 新根产出，`sop-build.log` 第 I 段；六件尺寸两根**一字不差**）：

| 件 | 大小 | 现役根基线 md5 | 新根 md5 | 判定 |
|---|---|---|---|---|
| `build/yolov8n` | 6,408,568 | `2f9290936028cc0b2ddca5376490a03a` | `8ca2b8ca93259b68cd538c9c0bbe60ec` | **DIFFER** |
| `build-py/crosswin_pybind_ext.so` | 134,456 | `15dc77f678be08481ecff2d0d4dd79f4` | `bc745e9431954bdec0305845b0640d49` | **DIFFER** |
| `build-py/crosswin_pybind_ext_v1013.so` | 134,456 | `b10967adbe4e82792b12943f8bbaafc3` | `80eccdcad7508c2926e3ad08fb53f246` | **DIFFER** |
| `build-py/crosswin_numpy_ext.so` | 139,320 | `dd5291dbe52ef4de1cf70033d11fcc31` | `4e0e02eb36fd056cbca289fba9ea8e87` | **DIFFER** |
| `build-py/crosswin_capi_ext.so` | 10,192 | `147be14d6aac8ed61c6ff57a5a83e311` | 同值 | **SAME** |
| `build-py/crosswin_embed` | 15,944 | `446b11e772685dcc1cd50e29b3583b3a` | 同值 | **SAME** |

**门禁侧是全绿的，不是"编坏了"**：L1a `ELF64`＋`AArch64`、L1b `all 12 present`、L1c 用到 GLIBC 2.29／GLIBCXX 3.4.26／CXXABI 1.3.9；L2 五件 GLIBC 2.17／GLIBCXX 3.4.21／CXXABI 1.3.9、`PyInit_*` 齐、`crosswin_embed` 要 `libpython3.8.so.1.0`；pybind11 身份仍是 `cxxabi1014`（`_v1013` 那份按声明给出 `1013`），与前一轮一致。对容器件仍是 −191,792 B（那条未归因照旧）。

字节级取证（只读，`sop-diff.raw`／`sop-diff2.raw`）⇒ **根路径以编译期字符串的形式嵌进了 C++ 件**：

| 件 | 不同的字节数 | 件内 `D:/yzd/…` 绝对路径串（去重） | `.comment` md5 是否相同 |
|---|---|---|---|
| `build/yolov8n` | 724,423 | 5 条（**＝6 次出现**，那条冒号对里含两次；`…/kit/ModelzooDeps/aarch64/Static/lib:…/kit/lib/aarch64-linux-gnu`，＋`…/kit/include/icraft-xir/base/*.h`） | 相同 |
| `crosswin_pybind_ext.so` | 16,420 | 4 条（`…/pyroot/usr/include/pybind11/…`），`.rodata` 0x1991 → 0x19b1 | 相同 |
| `crosswin_numpy_ext.so` | 17,764 | 4 条（同上），`.rodata` 同样 +0x20 | 相同 |
| `crosswin_capi_ext.so` | **0** | **0 条** | 相同 |
| `crosswin_embed` | 0（md5 相同） | 0 条 | 未查 |

规律干净：**有绝对路径串的 4 件全变、一条都没有的 2 件（都是纯 C）全同**。两条排除：`.comment` 相同 ⇒ 不是编译器版本差；`build/yolov8n` 与 `crosswin_pybind_ext.so` 的动态段里**零条 `RUNPATH`/`RPATH`**（只查了这两件）⇒ 不是运行时搜索路径。**这一节当时留下的两个"没查完"，当晚由 Δ+4 那个根全部关掉（下面「归因实验」）**——包括我写错的这句：`.rodata` 反而**大** 0x20 B「解释不了」的依据是"`WCIS/crosswin` 比 `tmp/sop1016` 长 2 字符、4 条应当是 −8 B"，**长度比较本身就数错了**：整条根前缀是 `D:/yzd/WCIS/crosswin`＝20 对 `D:/yzd/tmp/sop1016/crosswin`＝27，方向是**变长**、不是变短。第九节更正 7 记这条。

### 归因实验（10-16 晚，她判「归因实验做」）：第三个根，只动路径长度

设计：`D:\yzd\attr1016\crosswin`＝**24 字符**（现役根 20 ⇒ **Δ+4**；复现根 27 ⇒ Δ+7）。输入**不是重建**，是从现役根 `cp -a` 七棵树（`kit` 948 文件／236,166,353 B、`pyroot` 209／30,238,624 B、`src` 45、`proj` 1、`cmake` 1、`src-py` 4、`ref` 2）＋42 个脚本，**`build/` 与 `build-py/` 刻意不带**（带了就会走增量、这次编译等于没发生）；工具链喂的是**同一颗** `/d/yzd/tools/cross/gcc-arm-10.3-…`（跟现役根 `build.sh` 的默认值同一个），所以**唯一变量是根路径的长度**。覆盖前逐件 md5 核对（`build.sh` `b6cc0b08…`、`build-py.sh` `9123c945…`、`ext_pybind.cc` `a03477e0…` 三对全同）。

结果：`rc_attr_L1=0 rc_attr_L2=0`，`ALL L1 GATES PASS`＋`ALL L2 GATES PASS`，六件尺寸与两根**一字不差**，md5 与两个根**都不同**（不是复现任一根，也不是第三个随机值——它落在字节律上）：

| 件 | 根前缀出现次数（两根各自 `grep -a -o -F` 数） | `.rodata` 尺寸 live → attr（Δ+4） | 整件 |
|---|---|---|---|
| `crosswin_pybind_ext.so` | live 4／attr 4 | 0x1991 → **0x19a1** ＝ **+16 B** | DIFFERENT（首个差异字节 #97＝program header 里的 filesz） |
| `crosswin_numpy_ext.so` | 4／4 | 0x1c81 → **0x1c91** ＝ **+16 B** | DIFFERENT（同上 #97） |
| `crosswin_capi_ext.so` | **0**／**0** | 同尺寸（纯 C，无这些串） | **IDENTICAL** |
| `crosswin_embed` | **0**／**0** | 同上 | **IDENTICAL** |
| `build/yolov8n` | 6／6 | **0x0b89a0 → 0x0b89a0 没动** | DIFFERENT（首个差异字节 #34209＝0x85c0，落在 `.dynsym`） |

**字节律（A 级）**：`.so` 那两件，`.rodata` 增长＝**嵌入出现点数 × 根路径字符差**＝4 × 4 ＝ 16 B，一字不差。四条串就是把 pybind11 头文件名嵌了进去（`…/pyroot/usr/include/pybind11/` 的 `cast.h`／`detail/class.h`／`pybind11.h`／`pytypes.h`，来自断言文本里的 `__FILE__`），attr 根里逐条同一份、只有前缀换掉。**零出现点的两件跨任何根都逐字节相同**——这就是"纯 C 那两件不变"的机制，不再是相关性。`.text`／`.dynstr`／`.dynsym`／`.comment`／`.eh_frame`／`.data`／`.bss` 全部同尺寸；`.comment` dump 的 md5 两根相同（`2ace3feb…`／`00ae0aa1…`）⇒ 编译器版本与命令行确实同一颗。

`build/yolov8n` 单独说，因为它**不吃 `.rodata`**：那 6 个出现点里 **2 个在 `.dynstr`**（偏移 0x2a7d0／0x2a809，正好在 0xf6a8＋0x1b190 之内），`.dynstr` 因此 0x1b190 → **0x1b198 ＝ +8 B ＝ 2 × 4**；**4 个在 `.rodata`**（0x3752f0／0x376288／0x377400／0x377488）但 `.rodata` 总尺寸没变——那一段有 64 字节对齐的余量，16 B 的增长被吸收。**"第一个差异字节出现在 `.dynsym`"这条当年看着像"连符号表都重排了"的怪事，现在有了机械解释**：`.dynstr` 里名字一挪，`.dynsym` 每一项的 `st_name` 偏移量就得改，所以符号表里成片的字节跟着动（该件总差异 691,202 B，远大于 8＋16 的实际内容变化）。这同时**修正**第八节旧表把 `yolov8n` 记成"5 条路径串"——`grep` 在二进制里会把 NUL 相邻的串连成一"条"，按前缀逐次计数是 **6 次**（那对冒号串里含两次）。

**Δ+7 那根的 32 B 不并进这条律**：复现根不只是换根，它把工具链也解压到 `D:/yzd/tmp/sop1016/tools/cross/…`（前缀比共享那颗长 12 字符），**双变量**，所以 4×7＝28 与实测 32 那 4 字节缺口不能拿来否证也不能拿来配律；Δ+4 这个根才是单变量的那一次。

**这两个根现在都不在校机的盘上**：复现根 10-16 晚按她「清进回收站」清掉，归因根 10-16 深夜按她「只留一个能用的就行」清掉（读数与验收见第七节最后三条）。本节上面那张表**全部取自落盘日志** `S:\work\WCIS\workenv\sopreplay\pl2-attr.log`／`pl2-diff.raw`／`pl2-diff2.raw`，不是"现场还能查"的东西。

续跑法（**10-16 用过两次，机制已换**）：换根编译要靠 payload 里没有的 wrapper，姿势是 `D:/yzd/MSYS2/usr/bin/bash.exe --login C:/Users/YiZhidi/<runner>.sh`——runner 里把工具链路径 `export` 好、调 wrapper、日志落文件再 scp 拉回（cmd 设不了环境变量，`TC` 不 export 就变成四行 MISSING，这是 10-16 真踩过的）。`sop-build.sh`（复现根那份）**曾经**自己数 python、非 0 且没有 `FORCE` 就 `exit 9`——**这段在 10-16 晚随现役根的 `run-builds.sh` 一起删掉了**，现在数了只打印；它还守根（不在指定根就 `exit 1`）、把新根工具链当 `$1` 传给两份 build 脚本、跑完逐件比 md5，并把 `build/yolov8n` 复制成 `yolov8n.prev` 让后续运行有锚。归因根用的是同形的新 wrapper `pl2-attr.sh`（多一道自检：目标根已存在就 `exit 3`，绝不覆盖）。

## 九、本轮公开更正

1. **第 0 步的 `wmic logicaldisk get caption,freespace` 在这台机上跑不通**——Win11 26200 已删 `wmic`（`command -v wmic` 空）。改判据为 `df -h /d`。（上一版把命令写出来时没在这台机上核过，属我的失误。）
2. **"工具链要在开发机下载再送过去"是错的**——`get-toolchain.sh` 头部注释就写着 `Runs on 校机 only`，它自带 curl；10-12 那颗 159,688,564 B 的包就是校机自己下的，10-16 实测 armkeil 的 URL HEAD 200。开发机下载只是"校机没网时"的兜底。
3. **`scripts 25` 这个判据数字过期了**——10-16 实测 39，10-16 晚重打 payload 后 42。真正稳定的是 `src-py 4`／`ref 2`（重打后 `ref 3`，多的是 `ref/icraft_op_support_table.txt`）；脚本数会随会话涨，不该当验收项。
4. **"zlib 已内含在第 5 步的 make-kit.sh 里"是错的**——`make-kit.sh:35` 只检查 `zlib/libz.a` 并在缺失时 `FATAL: run get-zlib.sh first` 退出；`get-zlib.sh` 必须**单独先跑**。内含的那半是 `apply-zlib.sh`（`make-kit.sh:186`）。所以步骤顺序从"5 里含 6"改成"6 在 5 之前"。
5. **"换机要改四处"数少了**——实测七处，且最要紧的三段入口脚本（`run-donors`／`run-presbuild`／`run-builds`）一条都不在旧清单里；照旧清单改完仍会在现役根上重跑并抹掉它的 `kit/`。
6. 新发现（不是更正，是原页完全没有的）：**`run-presbuild.sh` 每次无条件重解 payload，会覆盖被改过的脚本自身**；**`build.sh`／`build-py.sh` 的工具链只吃位置参数、不吃 `TC=` 环境变量**；**新根天生没有 `yolov8n.prev`，判据 2 不会自证**。
7. **判据 2 原来那句"这条是回归锚"写得不够硬，害它被当成跨根判据用**——10-16 新根实跑：六件尺寸一字不差、4 件 md5 变（纯 C 的两件不变），**跨根字节相同不成立**。已把判据 2 的口径收窄成"**同一个根**重编不变"，跨根只能承诺"编出通过同样门禁的件"。**当晚两条都升到 A 级**：同根重跑由现役根原地复跑验通（L1 与锚同 md5），跨根差异由 Δ+4 单变量根归因坐实（`.rodata` ＋16 B＝4 出现点 × 4 字符、零出现点的两件逐字节相同），不再是"只到相关性"。**同时公开我那句错话**：旧版写"`.rodata` 反而大 0x20 B 解释不了，因为 `WCIS/crosswin` 比 `tmp/sop1016` **长** 2 字符、4 条应当是 −8 B"——**前缀长度数反了**，整条根前缀是 20 对 27（变短的方向才是 −），所以那 32 B 从来不是反例；读数与推导见第八节「归因实验」。
8. **"python.exe 非 0 就不起构建"这条门禁已经不存在了**——她 10-16 晚的判定是「删除要 python=0 的门禁，跑」，`run-builds.sh` 里那段 `REFUSE`/`exit 9` 整体删掉、只留一行计数打印，`run-donors.sh` 头部与 `FORCE=1` 那两行说明一并删，删后重打进第三代 payload 并单点解回现役根（md5：`run-builds.sh` `c4931a64…`、`run-donors.sh` `44df857a…`、`get-toolchain.sh` `9dac906f…`，`bash -n` 三件全过，`grep -l 'exit 9' <根>/*.sh` 空）。**这一条推翻了我上一版写的"默认仍然守门禁、别改成默认放行"**——保留它的价值在于记录这条规矩为什么不再成立：它挡的一直是**算力抢占**、不是正确性，破门禁跑出来的六件门禁读数与不破时同构（10-16 两次都是 python.exe 非 0 跑的：复现根 4、现役根复跑 4→6），所以删掉它没有引入任何判定上的松动。`sop-build.sh` 那份 wrapper 的同一段也一并没了；**要数进程自己数，脚本不拦**。
9. **"清复现根进回收站"这件事在 ssh 会话里不能用 `Microsoft.VisualBasic.FileIO.FileSystem::DeleteDirectory(… SendToRecycleBin)`**——10-16 实测：它对 1,992 MB 的根挂 18 分钟、只吃了 1.2 s CPU、回收站零新增；换成一个 6 字节文件的探针目录**照样挂**，所以不是长路径、也不是体积，是它内部的错误对话框在没有桌面的会话里等不到应答。能用的姿势＝直接 P/Invoke `shell32!SHFileOperation`，`wFunc=FO_DELETE(3)`、`fFlags = FOF_SILENT(0x04) | FOF_NOCONFIRMATION(0x10) | FOF_ALLOWUNDO(0x040) | FOF_NOERRORUI(0x400)`——**`FOF_NOERRORUI` 才是关键**，加上之后同一条调用 0.1 s 返回。两条附注：① 这个旗标组合会**静默跳过**"进不了回收站"的项，所以第一次跑必须先拿探针目录验证"目标消失＋回收站条目增加"两件事同时成立，才敢指向真实的树（脚本 `S:\work\WCIS\workenv\sopreplay\recycle-shfo.ps1` 里写死了只认这两个路径的白名单）；② `$I` 记录是 version 2 布局，原始路径在**偏移 28**（大小 8 字节、删除时间 16 字节、路径字符数 24 字节），别按网上常见的"36 字节起"去解，我第一次就解成空串。

## 相关页面

- [[交叉编译主机路由SOP]]：搭完之后每轮怎么跑（含**后端档只用 ZG330** 那条；**环境已就绪时要敲的命令与判据在它的新「三·补 照抄卡」**，别再回本页找）
- [[win无wsl交叉编译]]：donor 九件清单与哈希、门禁读数、15 条公开更正
- [[校机无容器交叉编译]]：工具链选型与 L1 三道门禁的第一版
- [[工具链与素材进README]]：厂商容器路线与素材在 `fdw` 的哪一格
- [[板端内存上限与心跳日志]]：为什么禁止在板上编译
- [[验证方法学]]：L1／L2／L3 分层定义
