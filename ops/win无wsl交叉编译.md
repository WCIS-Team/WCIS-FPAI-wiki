---
tags: [SOP]
---

# win无wsl交叉编译

> **本页回答什么问题**：容器镜像里的交叉编译工作，有哪些已经能在 Windows 校机上不带 WSL、不带容器做完；组件一件件是什么（带哈希与体积）；下一轮怎么起；哪些环节还缺；以及这一路上写错/判错并被改掉的事。另回答一件常被问的：**一个模型用到哪些算子、缺哪些算子，能不能从校机那份 icraft deb 里读出来**（第七节，答案分三层，其中一层是不能）。
> **前置阅读**：[[校机无容器交叉编译]]（工具链选型、i686/WoW64、Ninja、sysroot 目录陷阱、ssh 进校机默认是 cmd —— 本页不重复那些，只接它后面的 donor 扩展）。**要一次性把环境搭出来看 [[校机交叉编译环境搭建SOP]]**；**下一轮要动手前先看 [[交叉编译主机路由SOP]]**（哪件事该在校机、哪件必须回本机，以及"后端档只用 ZG330"那条）。
> **主机口径**：所有编译动作在校机（`ssh school-guest`，Windows，无 WSL、无容器、无 admin）。镜像削包（`carve-*.sh`）只在开发机的 WSL 里跑，因为它要读 27.95 GiB 的出厂 SD 镜像。**"无 WSL"指的是编译侧**，不是指全流程都不碰 WSL。
> **数字来源**：本页每个读数都挂着留在 `S:\apps\llm\agentwork\crosswin\` 的日志（输入侧：`run-presbuild.raw`、`run-ef.raw`、`run-ef2.raw`、`run-uapi.raw`、`run-uapi2.raw`；编译侧：`run-l2fix-1015.txt`、`run-l2fix2-1015.txt`、`probe-l2-1015.raw`、`carve-pydeps.txt`）或校机 `D:/yzd/WCIS/crosswin/logs/` 里的同名日志；算子读数的原文在 `_opsurvey/`、`icraft_op_matrix_6col.tsv`、`op-t1-vs-t2.txt`（解析脚本 `parse-ops-table2.py`／`ops-table-diff2.py`），全表已另立 [[iCraft算子支持矩阵]]；`ref/icraft_op_support_table.txt` 那份是 10-15 第一遍的产物，**只 83 行可用，别再引用**（原因见 6.1 第 15 条）。判级见第八节。
> **本轮停在哪（2026-10-15）**：G/H 两段**都跑过了，全绿**（`rc_G=0`、`rc_H=0`、`RC L1=0 L2=0`、`MARKER builds=0`）。L1 那颗 `yolov8n` 与上一轮旧 kit 的 `yolov8n.prev` **md5 逐字节相同**，L2 五件过了全部静态门禁。仍然没做的只剩**上板**（L2 的 `import`、L3 的跑图出框）——校机执行不了 aarch64 二进制，这条链的数值正确性在这里证明不了（见第五节 1、4）。

---

## 一、结论：十段全绿（G/H 在 2026-10-15 跑通）

| 段 | 内容 | 状态 | 证据 |
|---|---|---|---|
| A | 读校机现场（python 进程数、磁盘） | ✅ 跑过 | `run-presbuild.raw` 段头：`python.exe processes: 2`、`D: 2.0T 225G 1.8T 12%`；10-15 起跑时 `run-l2fix2-1015.txt`：`python.exe processes: 0` |
| B | 保住已知好状态（`yolov8n.prev`、`kit.v1`） | ✅ 跑过 | 同上：`2f9290936028cc0b2ddca5376490a03a *yolov8n.prev`、`old kit moved aside: kit.v1 (163M)` |
| C | 解 payload 到构建树 | ✅ 跑过 | `run-presbuild.raw`：`scripts 25  src-py 4  ref 2`；10-15 那份 payload = 17,738,644 B / md5 `54d49c8ef0bcda9751d72312655b0f0c`（**10-16 已重打两次**＝现值 17,742,872 B / `2bfde4cb37cee7f07f773b349f9b41d4`，见 §3.1；这一行是那一代跑出来的历史读数，不改） |
| **D** | 装 Python 开发树 `pyroot/` + 门禁 | ✅ `rc_D=0` | `PYROOT GATES ALL PASS: /d/yzd/WCIS/crosswin/pyroot`（首跑 `rc_D=3`，原因见 2.2 与 6.2 第 2 行；10-15 为 donor #9 重跑一次，仍 0） |
| **E** | `make-kit.sh` 重建 kit + 全部门禁 | ✅ `rc_E=0` | `run-ef2.raw`：`KIT READY 228M / inventory: 948 files`（首跑 `rc_E=3`，见 6.1 第 3 条） |
| **F** | CustomOp ABI 探针 | ✅ `rc_F=0` | 校机 `logs/customop-abi-*.txt`；摘要在第三节 3.5 |
| **G** | `build.sh`＝厂商 demo 的 L1 回归 | ✅ `rc_G=0` | `run-l2fix2-1015.txt`：`ALL L1 GATES PASS bin=/d/yzd/WCIS/crosswin/build/yolov8n`，`SIZE=6408568`，md5 与 `yolov8n.prev` **完全相同**（`2f929093…`） |
| **H** | `build-py.sh`＝五个 cp38 件的 L2 | ✅ `rc_H=0` | 同上：`ALL L2 GATES PASS dir=/d/yzd/WCIS/crosswin/build-py`；读数在 3.7（首跑 `rc_H=4`，两处红都是**我的检查器写错**，见 6.1 第 9、10 条） |
| **J** | 装内核 UAPI 头 `uapi/` + 门禁 | ✅ `rc_J=0` | `run-uapi2.raw`：`UAPI GATES ALL PASS`（首跑 [4] 红，见 6.2 第 5 行） |

所以现在的**真实能力边界**是：kit、pyroot、uapi 三份输入在校机上过了验收，**并且已经在这套输入上编出了东西**——L1 那颗 `yolov8n` 与上一轮（旧 kit）那份 `yolov8n.prev` **md5 逐字节相同**（`2f929093…`，所以 948 文件的新 kit 没有改动 L1 产物），L2 五件过了全部静态门禁。与 10-05 容器件仍是 **−191,792 B（−2.9 %）** 那笔未归因的差（[[校机无容器交叉编译]] 第 4 条）。**这里能证明的到"编出来 + 静态契约对"为止**：校机是 x86-64 Windows，跑不了 aarch64 件，所以**数值正确性与 import 成功与否只能上板才能证**（第五节 4）。

---

## 二、怎么建立的：把"镜像里有的"逐件换成"校机上能直接用的"

容器镜像干的活拆下来只有五件事，每件各配一条无容器的替代路径：

| 镜像里的东西 | 替代物 | 为什么这样替 |
|---|---|---|
| aarch64 GCC | Arm GNU Toolchain **10.3-2021.07 `mingw-w64-i686-aarch64-none-linux-gnu`** | 版本对上板上 `libstdc++6 10.3.0-1ubuntu1~20.04`，符号版本上限就是 `GLIBCXX 3.4.28 / CXXABI 1.3.11 / GLIBC 2.31`；`i686` 包是 32 位 Windows 原生程序，靠 WoW64 直接跑，所以不需要 WSL |
| 厂商 SDK 的 cmake 包／头／库 | donor #1/#2/#4/#5 → `kit/` | 只有 deb 里那份才是板端要用的那份；从 apt pool 找等价物会串版本 |
| 板端 Python 的开发件（`Python.h`、`libpython3.8.a/.so.1.0`、pybind11、numpy 头） | donor #7 → `pyroot/` | 板上装的是 `3.8.10-0ubuntu1~20.04.7`，**pool 已经不发 `.7`（只剩 `.2` 和 `.18`）**，唯一字节相同的来源就是出厂镜像本身 |
| **`libpython3.8.so.1.0` 自己 `DT_NEEDED` 的那两颗（`libexpat.so.1`、`libz.so.1`）** | **donor #9 → 也落进 `pyroot/`** | GNU ld 链接可执行件时，要看得见"库的库"才肯链；工具链 sysroot 里的 `libexpat`/`libz` 是 x86-64 的，aarch64 版只能从板上取。**这一件是 10-15 补的，补之前嵌入件根本链不过去**（见 6.1 第 11 条） |
| 内核头（`linux/`、`drm/`、`asm/`） | donor #8 → `uapi/` | Arm 工具链自带内核头数量是 **0**；focal 的 `linux-libc-dev` 是"差一个 delta"，不是板子那一份 |

### 2.1 出厂 `.bin` 的布局（这一节是削包的物理前提）

`icraft_v3_ubuntu20.04_aarch64_sd_image.bin` 不是"直接就能 losetup 的磁盘"，`fdisk -l` 看不到分区表就是因为它前面多塞了 512 B 的 imageUSB 头：

```text
0            512 B   imageUSB 头（UTF-16 "imageUSB"），不属于磁盘
512          真磁盘的 MBR（0x55AA 落在 512+510）
             part0 FAT16  LBA 2048       -> 文件偏移 1,049,088      1 GiB
             part1 ext4   LBA 2,101,248  -> 文件偏移 1,075,839,488  27.95 GiB
```

ext4 魔数 `0xEF53` 在 `1,075,839,488 + 1024 + 56` 处校验通过，读法只有只读一条路：

```bash
losetup -f --show -r -o 1075839488 "$IMG"
mount -o ro,noload "$LOOP" "$M" || mount -o ro,norecovery "$LOOP" "$M"
```

`noload` 是必须的：不挂 journal 就不会因为挂载而改写镜像。`trap cleanup EXIT` 里 `umount` + `losetup -d`，退出时不留 loop。

### 2.2 donor 的打包口径（这里踩过最大的坑）

镜像里的 Debian 树到处是符号链接，**bsdtar（Windows 的 `tar`）建不出符号链接**，一条建不出来就整包失败。两份 donor 用了两种不同解法，区别要记住：

- `board-uapi.tar.xz`：打包时用 GNU tar `tar -h`（解引用符号链接 → 存成目标的普通副本），所以包里根本没有链接项，校机可以整包解开。
- `py-sysroot.tar.xz`：打包时用的是 `--hard-dereference`，**它只合并硬链接，不合并符号链接**，所以 `config-3.8-aarch64-linux-gnu/libpython3.8.so` 那条链接还是链接，而且它的目标（`libpython3.8.so.1`）不在包里，是一条**悬空链接**。板子上它本来也悬空。处置：解包时 `--exclude` 掉这条，然后手工把 `.so.1.0` 复制成那颗 dev `.so`，让 `-lpython3.8` 能用；复制件里的 SONAME 没动，所以链出来的二进制仍然要 `libpython3.8.so.1.0`——那是板子真有的文件。
- `ModelzooDeps` 的 `Dynamic`：解包后按归档自己的链接表（`bsdtar -tvf | grep ' -> '`）**逐条重放成字节副本**，跑 3 遍，再数剩余链接项为 0。
- `py-deps.tar.xz`（donor #9）：压根不打算带链接——板上那两条是 `libexpat.so.1 -> libexpat.so.1.6.11`、`libz.so.1 -> libz.so.1.2.11`，削包时**直接把实体文件按 ld 要找的 SONAME 名字存**（包里只有 `usr/lib/aarch64-linux-gnu/libexpat.so.1` 和 `.../libz.so.1` 两项，`bsdtar -tvf` 里链接项 0 条），落地就不需要重放。字节仍是板子那颗（md5 见 3.1）。

结论性的一句话：**Windows 侧的 donor 必须是"无符号链接"的**，要么打包时 `-h`，要么落地后重放，要么像 #9 这样从一开始就按链接名存实体。

---

## 三、有哪些组件

### 3.1 donor 清单（校机 `D:/yzd/WCIS/crosswin/donor/`）

| # | 文件 | 体积 (B) | md5 | 它给这条链带来什么 |
|---|---|---|---|---|
| 1 | `Icraft_3.39.0_onchip.deb` | 9,192,096 | `2d1167db8a81f03d48827f53e1de16c4` | iCraft 运行时与开发件：28 个 cmake 文件、386 个头、23 颗 `.so`、3 颗厂商 aarch64 可执行件 |
| 2 | `IcraftMdzThirdParty.deb` | 34,415,828 | `0cf4fcd5e87697998df934a889ad9445` | ModelzooDeps：aarch64 Static 445 文件 122 M（链接输入），aarch64 Dynamic 45 文件 5.0 M（要随件部署到板上的） |
| 3 | `zlib/libz.a`（`zlib1g-dev_..._arm64.deb` 里取出） | 142,806 | 见 [[校机无容器交叉编译]] | 填掉厂商 `OpenCVModules.cmake` 里 4 条绝对路径 `/usr/lib/aarch64-linux-gnu/libz.so` |
| 4 | `CustomOp_3.39.0_onchip.deb` | 314,660 | `17aec40637bde0a8497b590adcc5c1a4` | 板端 custom op 7 颗（DetPost／DetPostZG／GridSample／ImageMake／NearestUpsample／SegPost／WarpAffine）＋ 12 份 `_git_version.h` |
| 5 | `decoder-aarch64/`（三颗 + 一颗 `_git_version.h`） | 16,127,592 / 16,136,160 / 16,115,048 | `2eb99717fb968ef08be162a4699caddf` / `f98d95051a794015f63c7337cc2f175e` / `f2548fbdcec3b8681a289493b5fcf458` | RGBADecoder／RGBDDecoder／SingleChannelDecoder 三颗解码 custom op |
| 6 | `icraft-3.39.0-cp38-none-manylinux2014_aarch64.whl` | 1,795,311 | `ea3ef12de435121b3f0e265ee89c9e9d` | 5 个 `cpython-38-aarch64` 模块，用来验证 wheel 与 deb 是同一批件（结果：5 颗逐字节相同） |
| 7 | `py-sysroot.tar.xz` | 4,020,208 | `7b5a9321bd08af6e7135ef2580b350e2` | 板上 Python 3.8 的开发树：头 + `libpython3.8.a` + `libpython3.8.so.1.0` + numpy 1.23 头 + pybind11（从板上 torch 里取的） |
| 8 | `board-uapi.tar.xz` | 1,052,952 | `ef240bdb17816c05337ff83ae68e0fe1` | 板子的内核 UAPI 头：kernel 5.4.52，`linux-libc-dev 5.4.0-146.163` |
| **9** | `py-deps.tar.xz`（**10-15 新增**） | 94,716 | `4608d5a74a4ba5d6607ae39da7f2ef8d` | 让**嵌入件**能链上 `libpython3.8.so.1.0`：板子自己的 `libexpat.so.1`（157,760 B / `42e22a375c644472afbb5766836bd6a0`）和 `libz.so.1`（104,608 B / `dcfbfb673a272430285d45073ac53bbe`），按 SONAME 名字存的实体副本 |

> 台账里曾记 `py-sysroot.tar.xz` 为 `9ae43c91…`，那是削包迭代过程中的旧哈希；现值 `7b5a9321…` 在本机 `donor-in/` 与校机 `donor/` 两处一致。

两份大 deb（#1、#2）不在 payload 里，是第一轮就停在校机 `donor/` 的；payload 只带脚本、源码、`ref/` 和小 donor（含 #7/#8/#9）。

**payload 现在这份**（10-16 晚第二次重打）＝ **17,742,872 B / md5 `2bfde4cb37cee7f07f773b349f9b41d4`**。往前两代：`9e5778f4a7093c9168b27fcbf8e5fffb`（17,741,892 B，10-16 早，只带自检修正）与 10-15 那份 **17,738,644 B / md5 `54d49c8ef0bcda9751d72312655b0f0c`**。本页第一节 A～J 全部绿读数（含 G/H 编译侧）都是在**最旧那一代**上跑出来的，`run-l2fix2-1015.txt` 段头打了 #7 与 #9 的 md5。三代都留了实体副本（开发机 `S:\work\WCIS\workenv\sopreplay\payload2-54d49c8e.tar.xz`、校机 `C:\Users\YiZhidi\payload2-54d49c8e.tar.xz` 与 `…-9e5778f4.tar.xz`）。

重打的净变化只有两处：**内容差＝`get-toolchain.sh` 一个文件**（sysroot 上限自检从"只查 `libc/lib/`"改成 `libc/lib64`→`libc/usr/lib64`→`libc/lib` 三目录轮查），**成员多四件**（`scripts 39→42`：`build-live.sh`／`run-lastlog.sh`／`run-live.sh`；`ref 2→3`：`ref/icraft_op_support_table.txt`；总文件数 100→104，包因此 +3,248 B）。这四件是本次打包时开发机 `crosswin/` 源目录里已经存在的东西，被 `pack-payload.sh` 一起收了进来，不是本轮为修自检而写的。**覆盖校机时没重跑 `run-presbuild.sh`**（它会连 `kit/` 一起重做），只在现役根里单点解一个成员：`tar -xJf payload2.tar.xz -C /d/yzd/WCIS/crosswin ./get-toolchain.sh`，该文件从 `758dca1894803000f60ac06e775c7176` 变成正本 `b87b50686a89e62b1c4854c4b3c1c10d`、`bash -n` 过，payload 那份自检实测打出 `libc.so.6 GLIBC_2.33／libm.so.6 2.32／libstdc++.so.6 GLIBC_2.33＋GLIBCXX_3.4.28／libgcc_s.so.1 2.17`。**第三代（现值 `2bfde4cb…`）的内容差是三件脚本**：`run-builds.sh` 删掉 python.exe 那段 `REFUSE`/`exit 9`（她 10-16 晚判「删除要 python=0 的门禁，跑」）、`run-donors.sh` 删同一件事的两行说明、`get-toolchain.sh` 把自检里多拼的 `lib` 前缀去掉（`from=liblib64/libc.so.6` → `from=lib64/libc.so.6`，四行上限值没变）。**成员数一件没动**（非目录 104、`*.sh` 42），包 17,741,892 → 17,742,872 B。覆盖仍是单点解，一次解三件：`tar -xJf payload2.tar.xz -C /d/yzd/WCIS/crosswin ./run-builds.sh ./run-donors.sh ./get-toolchain.sh`，落点 md5 `c4931a64…`／`44df857a…`／`9dac906f…`、`bash -n` 三件全过、`grep -l 'exit 9' <根>/*.sh` 为空。**G/H 已对着第三代在现役根复跑**：`rc_G=0 rc_H=0`、`ALL L1 GATES PASS`＋`ALL L2 GATES PASS`，且 `build/yolov8n` 与根里的锚 `yolov8n.prev` **md5 一字相同**（`2f929093…`）——起构建时 python.exe 计数 4→6，照跑，这是"同根重跑逐字节不变"第一次拿到实测。归因实验与跨根字节律在 [[校机交叉编译环境搭建SOP]] 第八节。

### 3.2 校机上的目录

```text
/d/yzd/tools/cross/gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu/   工具链（只读）
/d/yzd/MSYS2/                                                                     bash --login、cmake 4.4.4、ninja 1.13.2、bsdtar
/d/yzd/WCIS/crosswin/
    donor/      ref/       src/      src-py/    cmake/    proj/    *.sh
    kit/        228 M，948 文件           <- make-kit.sh 的产物（旧的那份挪成 kit.v1，163 M）
    pyroot/     30 M，209 文件             <- setup-pysysroot.sh 的产物（10-15 加了 donor #9 的两颗库，206 -> 209）
    uapi/       915 文件                   <- setup-uapi.sh 的产物
    build/      yolov8n  6,408,568 B      <- build.sh 的产物，md5 与 yolov8n.prev 相同
    build-py/   五件（本轮已生成，见 3.7）
    logs/       每次跑各留一份，名字带时间戳
```

### 3.3 脚本职责表

| 脚本 | 干什么 | 退出码 |
|---|---|---|
| `run-donors.sh [all\|pre\|build]` | 唯一入口。`pre`＝不编译的半段（D/E/F/J），`build`＝编译的半段（G/H），默认 `all`。刻意跑**构建树里那份**，避免 `C:/Users/YiZhidi` 下的旧壳脚本驱动这一轮；构建树没脚本时先自动解一次 payload | 任半段非 0 则 1 |
| `run-presbuild.sh` | A 读现场 → B 保状态 → C 解 payload → D → E → F → J → G 段只列 kit 内容不做编译 | D/E/F/J 任一非 0 则 1 |
| `run-builds.sh` | 先查 `python.exe` 进程数：**不为 0 就 REFUSE，rc 9**；再跑 `build.sh`(L1) 和 `build-py.sh`(L2)，最后打 md5 对照 | REFUSE=9，缺 kit=2，编译/门禁红=1；`FORCE=1` 才跳过 ASR 门禁 |
| `setup-pysysroot.sh [PY_SYSROOT_TAR] [PY_DEPS_TAR]` / `gate-pyroot.sh` | 解 donor #7 + **#9** / 验收（见 3.4） | 0 / 门禁红 5 / 预检 2 |
| `setup-uapi.sh` / `gate-uapi.sh` | 解 donor #8 / 验收（见 3.6） | 0 / 门禁红 / 2 |
| `make-kit.sh <donor目录> <kit目录>` | 4 步剥 donor 成 kit，内含 `apply-zlib.sh`，末尾三道闭包门禁 | 0 / 3 |
| `probe-customop-abi.sh` | 只读：拿 readelf 把 custom op 的契约抄下来 | 0 |
| `build.sh` / `build-py.sh` | L1（厂商 demo 件）/ L2（**五个** cp38 件：pybind、pybind 的 `-DPYBIND11_BUILD_ABI` 变体、numpy、capi、embed） | L1：0/2/3；L2：0/2/3/4 |
| `carve-pysysroot.sh` / `carve-uapi.sh` / **`carve-pydeps.sh`** | **在开发机 WSL 里**只读挂镜像，削出 donor #7/#8/**#9** | 0 |
| `get-pysysroot.sh` | 备选路线：没有镜像可削时，在校机从 apt pool＋PyPI 现攒 `pyroot`（**版本对不上板**：pool 只有 `.2`/`.18`，板子是 `.7`）；10-15 也给它补了 `libexpat1`/`zlib1g` 两颗 | 结尾 exec 到 `gate-pyroot.sh` |
| `pack-payload.sh` | 把脚本＋源码＋`ref/`＋小 donor（含 #9）打成 `payload2.tar.xz` | 0 |
| `run-l2fix.sh` | **本轮实际用的驱动器**：解 payload → `setup-pysysroot.sh`（D）→ `run-builds.sh`（G/H）→ 列 `build-py`。`rc_D≠0` 就 `STOP` 不进编译 | 随内层 |
| `probe-l2.sh` | 只读：把 `[3]/[4]` 两道红的现场逐条打出来（dyn-syms 原文、带不带 `-W` 的 grep rc、每颗 kit 库里的 internals id、`__GXX_ABI_VERSION`）——本轮两处红的定性靠它 | 0 |

### 3.4 `pyroot/` 的门禁读数（D 段绿的是什么）

| 门禁 | 读数 |
|---|---|
| 树 | **`209 files, 30M`**（本轮加 donor #9 前是 206；再之前修复前是 205，差的就是手工补出来的 dev `.so`） |
| `pyconfig.h` | 只在 multiarch 路径：`usr/include/aarch64-linux-gnu/python3.8/pyconfig.h` **47,533 B**，与板子同尺寸 → 编译必须给**两个** `-I` |
| `libpython3.8.a` | **8,518,198 B**，与板子同尺寸；174 个成员；抽 `getbuildinfo.o` 验 `ELF64 + AArch64`（证明拿的是 arm64 包，不是 `all`/amd64） |
| `libpython3.8.so.1.0` | **5,381,512 B**，与板子同尺寸；`ELF64 + AArch64`；**SONAME = `libpython3.8.so.1.0`**；`Py_Initialize` 在这颗里定义 |
| dev `.so` | `config-3.8-aarch64-linux-gnu/libpython3.8.so` 是 `.so.1.0` 的字节副本（5,381,512 B）→ `-lpython3.8` 可用 |
| **[3b] `libpython` 自己的闭包**（10-15 新增，[gate-pyroot.sh:71](file:///S:/work/WCIS/workenv/crosswin/gate-pyroot.sh#L71)） | 它的 8 条 `DT_NEEDED`：`libexpat.so.1 libz.so.1 libpthread.so.0 libdl.so.2 libutil.so.1 libm.so.6 libc.so.6 ld-linux-aarch64.so.1` → 三道判定全 PASS：① **每条都看得见**（在 `pyroot` 或工具链 sysroot 里）② **8 条全在 `ref/board-libs.txt`**（=板上运行时真能解析）③ 逐颗验 `ELF64`/`AArch64`/`SONAME = 本名`：`libexpat.so.1` 157,760 B、`libz.so.1` 104,608 B 都过 |
| pybind11 | `detail/` 24 文件；`PYBIND11_INTERNALS_VERSION = 4`；厂商件里读到的 id 是 `pybind11_internals_v4_gcc_libstdcpp_cxxabi1013__` |
| numpy | `arrayobject.h` 在；METADATA `Version: 1.23.0`（板子跑的就是这颗） |
| 用途口径 | 只用于**建**扩展模块与嵌入件；它不是板子的运行时——板上的 `.so` 和标准库本来就在板上 |

### 3.5 CustomOp 探针读数（F 段绿的是什么）

版本钉：所有 `_git_version.h` 里 `MAJOR/MINOR/PATCH = 3/39/0`，**四个不同的 COMMITID**：`000ed65`、`555e5bc`、`7b2be3a`、`c4ce52f`（说明这些件不是同一次提交编出来的，跨库 ABI 只能靠 `MAJOR.MINOR.PATCH` 对齐来推）。哈希戳：`det_post`/`det_post_zg`/`image_make`/`nearest_upsample`/`seg_post`/`warpaffine` 同份 `8928301f`，`icraft-utils 2cb7181e`、`icraft-xir 1b466681`、`icraft-xrt 43e79a19`。

`libcustomop.DetPost.so`（365,424 B）的契约：`DYN / ELF64 / AArch64`，NEEDED = `libicraft_hostbackend.so`、`libicraft_buyibackend.so`、`libicraft_xrt.so`、`libicraft_xir.so`、`libicraft_utils.so`、`libstdc++.so.6`、`libgcc_s.so.1`、`libc.so.6`、`ld-linux-aarch64.so.1`，SONAME 就是自己的文件名，**导出 GLOBAL 符号 0 个**，按 `Create/Register/*CustomOp/*Factory` 筛出来的入口候选也是空。从 `libicraft_*` 引入的未定义符号里只看到日志设施（`icraft::detail::LogExcept::GetEntry()` 等）。

op 名在二进制里出现的次数（用来猜后端怎么挑库）：

```text
DetPost.so            175 DetPost            DetPostZG.so    173 DetPostZG | 5 DetPost
GridSample.so         129 GridSample         ImageMake.so    176 ImageMake
NearestUpsample.so    166 NearestUpsample    SegPost.so      168 SegPost
WarpAffine.so         167 WarpAffine         RGBADecoder.so   11 RGBADecoder
RGBDDecoder.so         11 RGBDDecoder        SingleChannelDecoder.so 11 SingleChannelDecoder
```

⇒ **能读契约，不能照抄契约**：厂商件不带可发现的入口符号（推测是构造函数自注册，但这是 B 级推测，没证），deb 里除 `_git_version.h` 外**没有真头文件**，所以"自己写一颗 custom op"这件事至今没有可用的接口定义。

### 3.6 `uapi/` 的门禁读数（J 段绿的是什么）

| 门禁 | 读数 |
|---|---|
| [0] 清单 | `linux 711 / drm 28 / asm-generic 36 / aarch64-linux-gnu-asm 37 / sound 20 / mtd 5 / misc 5 / alsa 44 / rdma 28`，PROVENANCE.txt 在 |
| [1] 与板子逐字节 | `linux/videodev2.h` **91,346 B**、`drm/drm.h` **32,201 B**、`linux/udmabuf.h` **643 B** —— 三项全对 |
| [2] 能否解析 | 交叉 `g++ -std=gnu++17 -fsyntax-only` 过 `videodev2 + media + udmabuf + drm + asm/ioctl` |
| [3] 真出件 | 出的 `.o` 是 `ELF64 + AArch64`，`.rela.text` 有 3 条重定位（示例 `R_AARCH64_ADR_PRE`） |
| [4] 布局常量 | `static_assert(V4L2_PIX_FMT_RGB565 == 0x50424752)`、`V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE == 9` 都过；可见 V4L2 宏 **982** 个；结构体尺寸只**打印不断言** |

包含方式（`-isystem`，两条都要）：`uapi/usr/include` ＋ `uapi/usr/include/aarch64-linux-gnu`。`usr/include/media` **不在镜像里**（`ABSENT`），依赖它的代码得另找源。

### 3.7 L1／L2 的编译读数（G、H 两段绿的是什么，2026-10-15）

**G 段（L1，厂商 demo 件）**：`aarch64-none-linux-gnu-g++ 10.3.1 20210621` + cmake 4.4.4 + ninja 1.13.2，配置里 `Found OpenCV: kit/ModelzooDeps/aarch64/Static (found version "4.5.5")`。出件 `build/yolov8n`，`SIZE=6408568`（容器参照 6,600,360，delta −191,792）。四道门禁：`ELF64 + AArch64`、`L1b NEEDED (all 12 present)`（另 `NOTE extra NEEDED: ld-linux-aarch64.so.1 libcudadefault.so librt.so.1`：前者和后者都在 `ref/board-libs.txt` 的 798 条里，**`libcudadefault.so` 出厂镜像里没有、是 kit 在部署时带上板的那颗**，md5 `b724664c…`，见 [[校机无容器交叉编译]] 第六节）、`L1c GLIBC=2.29 / GLIBCXX=3.4.26 / CXXABI=1.3.9 / GCC=4.5.0` 全在板子上限内、`ALL L1 GATES PASS`。段 I 的回归：`2f9290936028cc0b2ddca5376490a03a` 同时打在 `yolov8n.prev` 和 `build/yolov8n` 上——**948 文件的新 kit 编出的 L1 件与旧 kit 那份逐字节相同**。

**H 段（L2，五件）**，目录 `D:/yzd/WCIS/crosswin/build-py/`：

| 件 | 体积 (B) | NEEDED | 符号版本上限 | 关键判定 |
|---|---|---|---|---|
| `crosswin_pybind_ext.so` | 134,456 | `libstdc++.so.6 libm.so.6 libgcc_s.so.1 libc.so.6` | GLIBC=2.17 GLIBCXX=3.4.21 CXXABI=1.3.9 | 不链 `libpython`；导出 `PyInit_crosswin_pybind_ext` |
| `crosswin_pybind_ext_v1013.so` | 134,456 | 同上 | 同上 | 带 `-DPYBIND11_BUILD_ABI="_cxxabi1013"` 的那份，internals id 与厂商件逐字相同 |
| `crosswin_numpy_ext.so` | 139,320 | 同上 | 同上 | 同上 + **不引用任何 `PyArray_*` 符号**（函数表运行时由 numpy 提供） |
| `crosswin_capi_ext.so` | 10,192 | `libc.so.6` | GLIBC=2.17 | 纯 C-API：不链 `libpython`、导出 `PyInit_crosswin_capi_ext` |
| `crosswin_embed` | 15,944 | `libpython3.8.so.1.0 libdl.so.2 libm.so.6 libpthread.so.0 libc.so.6` | GLIBC=2.17 | `EXEC`；`binds Py_Initialize`；板子清单里确有 `libpython3.8.so.1.0` |

未定义符号侧（[6]）：`crosswin_pybind_ext` 175 条未定义、其中 98 条是 `Py*` 类；`numpy_ext` 174/98；`capi_ext` 10/6。剩下的非 `Py*` 只有 `__cxa_*`、`__assert_fail`、`_ITM_*`、`__gmon_start__` 这类，全部由 `NEEDED` 里的 `libstdc++/libgcc/libc` 提供——**没有一条指向 icraft**，所以这三颗扩展模块自身不依赖厂商库；它们与厂商 python 模块的唯一交点是 pybind11 internals 那一层（这句是按符号表推的，B 级）。

**pybind11 身份这件事测出来的结论（不是脚本红，是真的对不上）**：`__GXX_ABI_VERSION = 1014`（Arm 10.3 的 libstdc++），所以本工具链自然生成的 id 是 `pybind11_internals_v4_gcc_libstdcpp_cxxabi1014__`，而 kit 里 5 颗厂商 `cpython-38-aarch64` 模块全是 `...cxxabi1013__`（= GCC 9 那代 libstdc++ 的 ABI 号）。`PYBIND11_INTERNALS_VERSION` 两边都是 **4**，所以差的那一段就是 id 后缀。带 `-DPYBIND11_BUILD_ABI='"_cxxabi1013"'` 重编，产出件里读到的 id 与厂商**逐字相同**（`grep -aoE` 直读，见 `run-l2fix2-1015.txt` [4]），体积不变（134,456 B）。**这条是"声明兼容"，不是"证明兼容"**——见 4.3 与第八节 B 级。

---

## 四、怎么使用

### 4.1 一次性（已经做完，重装才需要）

工具链、MSYS2、cmake/ninja 的装法与大 deb 的落位都在 [[校机无容器交叉编译]]。新增的一次性动作只有削包，在**开发机 WSL 以 root** 跑：

```bash
bash carve-pysysroot.sh   # 出 donor/py-sysroot.tar.xz   (#7)
bash carve-uapi.sh        # 出 donor/board-uapi.tar.xz   (#8)
bash carve-pydeps.sh      # 出 donor/py-deps.tar.xz      (#9，10-15 新增)
bash pack-payload.sh      # 把脚本+源码+ref/+小 donor 打成 payload2.tar.xz
```

### 4.2 每一轮就两条命令

`ssh` 进校机默认落到 **cmd**，`$`、`;`、`&&` 都不可信，所以永远只跑脚本文件；`--login` 不能省（PATH 里的 `/usr/bin` 来自 rc 文件）。

```bash
# 半段一：不编译（解包 + 三份输入 + 门禁），CPU 影响可忽略，随时能跑
D:/yzd/MSYS2/usr/bin/bash.exe --login D:/yzd/WCIS/crosswin/run-donors.sh pre

# 半段二：真编译（L1 回归 + L2 五件）。她 ASR 批次在跑时会直接 REFUSE
D:/yzd/MSYS2/usr/bin/bash.exe --login D:/yzd/WCIS/crosswin/run-donors.sh build
```

单段想单独重跑：`bash run-presbuild.sh`（含 D/E/F/J），或 `bash build.sh` / `bash build-py.sh`。日志同时进终端和 `D:/yzd/WCIS/crosswin/logs/`，中文是 GBK，别在 ssh 管道里直接 `iconv`，先落文件再看。

**半段二在 2026-10-15 实跑过两次**，用的驱动器是 `run-l2fix.sh`（解 payload → D → `run-builds.sh`）：第一次 `rc_H=4`，第二次全绿。要复现的是这条，不是 `run-donors.sh build` 本身——后者的语义一样，只是当时改 donor（#9）必须重跑 D 段。

### 4.3 编译门禁的口径（判"能不能上板"用的是这套）

- **运行时闭包**：每颗件的每条 `DT_NEEDED` 必须命中 `ref/board-libs.txt`（**798 行**，出厂 rootfs 里加载器默认目录的 `.so` 名单，**零条 icraft/customop**）**或**落在 `kit/lib/aarch64-linux-gnu/`。E 段末读数：`checked 16 ELF, 0 with unresolved NEEDED`。
- **符号版本上限**：`GLIBC ≤ 2.31`、`GLIBCXX ≤ 3.4.28`、`CXXABI ≤ 1.3.11`。本轮实测余量：L1 件用到 `GLIBC 2.29 / GLIBCXX 3.4.26`，L2 五件只到 `GLIBC 2.17 / GLIBCXX 3.4.21 / CXXABI 1.3.9`。
- **链接期还要"库的库"可见**：链可执行件时 GNU ld 要求 `libpython3.8.so.1.0` 自己的 8 条 `DT_NEEDED` 也找得到，靠 `-L$PY/usr/lib/aarch64-linux-gnu -Wl,-rpath-link,同一个目录`（[build-py.sh:61](file:///S:/work/WCIS/workenv/crosswin/build-py.sh#L61)）+ donor #9 那两颗 aarch64 实体。缺任何一半都是 `undefined reference to XML_*/inflate*`。
- **扩展模块 vs 嵌入件**：扩展模块**不许** NEEDED `libpython`，且必须导出 `PyInit_<模块名>`；嵌入件**必须** NEEDED `libpython3.8.so.1.0` 并绑到 `Py_Initialize`。查这条**必须给 `readelf --dyn-syms -W`**——不带 `-W` 时长符号名被截成 `PyInit_crosswin_[...]`，门禁假红（见 6.1 第 9 条）。
- **numpy 扩展**：不许引用任何 `PyArray_*` 符号（函数表运行时由板上的 numpy 提供），且 `import_array` 必须显式包含 numpy 自己的 `arrayobject.h`（donor #7 里那颗 pybind11 是 2.6.2，它的 `numpy.h` **不带** numpy 头，见 6.1 第 10 条）。
- **pybind11 身份（10-15 改过口径）**：本工具链自然生成的 id 是 `pybind11_internals_v4_gcc_libstdcpp_cxxabi1014__`，厂商 5 颗件是 `...cxxabi1013__`——**两者天然不同，不是构建错误**。要拿厂商那份身份，就在编译时加 `-DPYBIND11_BUILD_ABI='"_cxxabi1013"'`；`build-py.sh` 因此同时产出 `crosswin_pybind_ext.so`（自然 id）和 `crosswin_pybind_ext_v1013.so`（厂商 id，导出同名 `PyInit_crosswin_pybind_ext`，**是替换件、不能与前一颗在同进程共存**）。**这个覆盖动作只是"声明"ABI 兼容，没有证明它**：真正的证明是板上同进程 `import` 两侧模块并互相传 pybind11 类型（L2 上板，见 5.4）。不覆盖也不换名的干净路子是改用 GCC 9 代的交叉工具链（Arm 9.3-2020.04 mingw-w64-i686，同一台校机、同一形态）。

### 4.4 起编译前的硬门禁

`run-builds.sh` 数 `tasklist` 里 `python.exe` 的个数，非 0 就 `REFUSE ... rc 9`。10-12 那一轮它拦下来过一次（计数 2），事后用 `Get-CimInstance` 查明那两颗是她的 `Oc-fired.py` 批次——**门禁报的是对的，不是误报**，`FORCE=1` 不是用来绕过真实冲突的。10-15 起跑时读到 `python.exe processes: 0`，门禁放行，`FORCE` 没用过。开发板上编译是禁止的（见 [[板端内存上限与心跳日志]]），这条链的产物要上板只能走部署。

---

## 五、还缺什么（事实，不含判断）

1. **上板那一层全空**：本轮编出的 6 件（L1 的 `yolov8n` + L2 的 5 件）**一次都没在板子上跑过**。L2 的板上 `import`、L3 的跑图出框与容器件逐条对齐都还没有。定义见 [[验证方法学]]。这一条是"编得出"与"用得上"之间唯一剩下的鸿沟，而且**校机跨不过去**（x86-64 Windows 执行不了 aarch64），只能靠部署。
2. **pybind11 身份只到"声明"**：`-DPYBIND11_BUILD_ABI='"_cxxabi1013"'` 让产出件里的 id 与厂商件逐字相同，但**没有实测过两侧模块在同进程互传 pybind11 类型**。干净的、不需要覆盖的路子是换 **GCC 9 代交叉工具链**（Arm 9.3-2020.04 `mingw-w64-i686-aarch64-none-linux-gnu`，形态与现役这颗完全一样、也吃 WoW64），本机没下、校机没装，**未验证**。
3. **`uapi/` 还没有消费者**：仓里没有把 `-isystem $UAPI/usr/include` 挂进真实编译的脚本（只有 `gate-uapi.sh` 自测用的 TU）。V4L2／udmabuf／drm 的真代码还没从这条链上过一遍。
4. **部署包还没成形**：这 6 件要上板得连带什么（`kit/lib/aarch64-linux-gnu` 的 23 颗、`libcudadefault.so`、`ModelzooDeps/aarch64/Dynamic` 那 45 文件 5.0 M、`pyroot` 是**不带**的）没有一份成文的清单，落板路径也没定；真要铺就按 [[板端我方代码与产物台账]] 的规矩逐件登记本地源＋板上路径＋md5。
5. **custom op 只能读不能写**：deb 无真头文件、导出 GLOBAL 为 0 ⇒ 自建 op 的接口与注册方式仍无定义来源。
6. **`usr/include/media` 缺**（不在出厂镜像里）。
7. **`ref/board-libs.txt` 是纯文件名清单**：不记路径、也不区分实体文件与符号链接（例：`ld-2.31.so` 与 `ld-linux-aarch64.so.1` 都在列）⇒ "板上能解析"这个判定目前是**按文件名命中**，没在板上复测过实际解析结果。
8. **numpy 只有头**（`core/include`），没有运行库；这保证头对版 1.23.0，不保证链接期有 `libnumpy` 之类。
9. **`kit/bin` 的三颗（`icraft` 411,632 / `icraft-run` 449,552 / `icraft-serve` 545,064）是从 deb 拷来的厂商件**，不是我们编出来的 ⇒ "镜像里的 CLI 也能在这里编"这件事仍未证。
10. **uapi 的 `linux` 目录计数两处不一致**：PROVENANCE 记打包 719 文件，门禁 [0] 数出 711 文件（其余各目录两处相同）。**未归因**（C 级），下轮重跑时先看这条要不要立案。
11. **另一头（imodel／`Yolov8n_ZG.raw`）不在校机**：那半在本机 `C:\Icraft\CLI v3.39.0` 出，两边不在同一主机（见 [[工具链与素材进README]]）。**校机上没有 CLI，所以"模型→imodel"这步无法在这里做**，这条链只接住"imodel＋host 源码→aarch64 件"这半段。
12. **L1 件与容器件那 −191,792 B（−2.9 %）仍未归因**：本轮只是又确认了一次这个数（`SIZE=6408568` vs 容器参照 6,600,360），段表／符号表比对没做。
13. **算子支持的真判据拿不到**：第七节那三层里，"某个模型的某个算子在 ZG330 上到底认不认"只有 CLI 的 `isOpSupported`／precheck 和板上 codegen 能定论，**这两样都不在校机**（校机没装 CLI，板子不许编译）。所以这条链上能给的算子结论只能是文档口径＋IR 名单口径。
14. **`gate-pyroot.sh` 第 4 节的 pybind11 版本号打印是坏的**（输出字面量 `MAJOR.MINOR.PATCH`；同块 internals 版本 4 的判定正常）。真实版本另从 donor #7 的 `pybind11/detail/common.h` 直读＝**2.6.2**。这条只影响日志一行，不影响任何 PASS/FAIL，所以**为了保住"绿读数＝当前这套脚本"的对应关系，本轮没动脚本**（见 6.2 末行）。

---

## 六、注意事项：这一路上被改掉的事

### 6.1 我自己写错／判错，已被证据推翻的（公开更正）

1. **kit 的库集合原先按 cmake 文件引用推**，会丢掉**只在运行时才需要**的 `.so`：旧 kit 只有 **9 颗** `.so`，现在把 deb 里所有 aarch64 `.so` 都拷，得到 **23 颗**（`libaxizg330aiu.so`、`libirpc_*`、`libmockzg330.so`、5 个 `cpython-38` 模块等 14 颗此前是被丢掉的）。cmake 引用数仍是 9、`missing: 0`，两条分开数。
2. **`libpython3.8.so.1.0` 的 SONAME 我按惯例写成 `.so.1`**，门禁红了。readelf 直读板子那颗：Debian focal 把**全名 `libpython3.8.so.1.0`** 当 SONAME。`gate-pyroot.sh` 与 `build-py.sh` 两处期望值都改成全名，并加了一条"板子清单里确实带这颗"的反查。
3. **`make-kit.sh` 把 `Dynamic` 整目录排除了**（`--exclude='*Dynamic*'`）。后果是第 5 步闭包检查红（`rc_E=3`）：`yaml-cpp-targets.cmake -> include` 找不到，当时只数到 `dynamic link entries: 2`，`dynamic 8 files 4.8M`。改成把 `Dynamic` 整棵拷进来后是 `45 files, 5.0M`、`missing: 0`。
4. **我说过"aarch64/Dynamic 里有 OpenCV"——错的**。OpenCV 的 Dynamic 项挂在 `x64/` 下；`aarch64/Dynamic` 只有 yaml-cpp 三兄弟（`libyaml-cpp.so`/`.so.0.8`/`.so.0.8.0`，各 1,658,184 B）。并且板子上**既没有 OpenCV 也没有 yaml-cpp**（板上那颗 `libyaml-0.so.2` 是无关的 C 库）。
5. **pybind11 internals id 的提取正则只吃掉一个尾下划线**（`...cxxabi1013_`），拿去 `grep -qF` 厂商那个双下划线结尾的 id，永远不可能命中。改成 `grep -aoE 'pybind11_internals[A-Za-z0-9_]*' | sort -u`。这个 bug 只在脚本里，没造成产物错误，但会让 H 段的判定假红。
6. **`--hard-dereference` 我当成"能把链接都展平"**——它只处理硬链接。所以 py-sysroot 的悬空 dev `.so` 没被它解决；解决它要靠 `tar -h`（uapi 用的就是这个）或落地后手工物化。
7. **runner 一律退 0**：`run-presbuild.sh`／`run-builds.sh` 结尾是 `echo`，最后一个命令的返回值被吞掉，分派器拿不到红。改成显式把各段 rc 拼起来判（`[ "$rc_d$rc_e$rc_f$rc_j" = "0000" ] || exit 1`）。
8. **`mv kit kit.v1` 的嵌套脚枪**：`kit.v1` 已存在时 `mv` 会把 `kit` 塞成 `kit.v1/kit`。加了存在性判断；重跑时它只打一行提示，不再动作（`make-kit` 本来就会清掉 `kit`）。
9. **`readelf --dyn-syms` 不加 `-W`，长符号名被截成 `PyInit_crosswin_[...]`**，我拿它当"模块没导出入口"的判据，于是第一次跑 H 段出了**三条假红**（`FAIL crosswin_pybind_ext exports PyInit_...` 等，`rc_H=4`）。定性靠 `probe-l2.sh`：同一条 grep 在不带 `-W` 时 rc=1、带 `-W` 时 rc=0，而 `cat -A` 打的原文确实是截断形状。产物从头到尾是好的。**[3]/[5] 两处都补了 `-W`**——这条不是风格问题，`-W` 在这里决定判定真假。
10. **我以为 donor #7 里 pybind11 的 `numpy.h` 会把 numpy 头一起带进来**——那颗 pybind11 是 **2.6.2**（板上 torch 里那份），它的 `numpy.h` 只做代理结构＋capsule import，**不 include numpy 自己的头**，所以 `import_array` 未声明，编译直接红。更细的一层：`import_array()` 展开成 `return NULL`，放进 pybind11 的 `PYBIND11_MODULE`（返回 void）里也不合法。处置：显式 `#include <numpy/arrayobject.h>`，再用一个返回 `int` 的小 helper 装 `import_array1(-1)`（[ext_numpy.cc](file:///S:/apps/llm/agentwork/crosswin/src-py/ext_numpy.cc)）。
11. **嵌入件链不上时我先当成"工具链 sysroot 缺库"**，实际缺的是 `libpython3.8.so.1.0` **自己的** `DT_NEEDED`：GNU ld 链可执行件要求"库的库"也可见。补了 `-L`/`-Wl,-rpath-link` 之后仍红，因为工具链 sysroot 里的 `libexpat`/`libz` 是 x86-64 的——**必须补 donor #9**（板子那两颗的 aarch64 实体）。所以这一条的教训是两半：链接开关 ＋ 输入件，缺一不可，而门禁 [3b] 现在把两半都单独验。
12. **`[4] internals id == 厂商` 第一条红我当成检查器过严**，实测才发现是真差异：`__GXX_ABI_VERSION = 1014`（Arm 10.3）对厂商件的 `cxxabi1013`。**这条与第 9 条方向相反**——第 9 条是脚本错、产物对，这条是脚本对、产物属性就是这样。当时的处置是把判定改成"自然 id 必须等于本工具链的 id"（这是可证的），把"等于厂商 id"移到覆盖编译的那一颗上，并把差异与后果原样打印出来。
13. **我说过（也写进过记录）"iCraft 没有公开算子表"**——**错的**。厂商 CLI 的 `docs/ops/` 里有 `spec.html` 总页＋114 张 per-op 页＋`framework.html` 表1（`Pytorch Op / Icraft Op / BUYI支持情况 / ZG330支持情况`）。读数与差距都立案在第七节。deb 里确实**不带**这些文档（deb 只有头和 `.so`），所以"从 deb 读算子支持"这条仍然不成立，但"没有算子表"这句话本身是错的。
14. **本页 §二 的 donor 编号曾与 §3.1 不一致**（`#6→pyroot`、`#7→uapi` vs 清单里的 #7/#8）。已按 §3.1 的编号统一（#7=py-sysroot、#8=board-uapi、#9=py-deps）。
15. **第 13 条更正之后我又漏了一层**：第一遍只数了 `framework.html` 的 4 列表（87 行），把落盘的 108 行原文对不上号的地方判成"长单元格换行的续行"——**不对**。真实原因是两条：① **同一张 HTML 里有第二张 6 列表（90 行，多 PaddlePaddle／Tensorflow 两列）**，我那 4 条对不上号的条件句（`input_L % output_L != 0` 等）就在这张里；② 落盘文本按 `|` 切列，而条件句里含逻辑或 `||` ⇒ `Conv1d/2d/3d`、`mean` 四行被切断丢掉（`ref/icraft_op_support_table.txt` 那份只有 83 行可用）。判据改成按 `<table>/<tr>/<td>` 解（`parse-ops-table2.py`），两表 10 处口径冲突已列进 7.1，逐字全表另立 [[iCraft算子支持矩阵]]。**教训：一份文档里"有几张表"要自己数，不能看到第一张像目标表就收工。**

### 6.2 环境硬约束（改代码前要先知道的）

| 约束 | 现象 | 处置 |
|---|---|---|
| **检查脚本不能用 `set -e`** | `gate-pyroot.sh` 里 `[ 测试 ]; g $? "…"` 的写法，第一次红就整篇断掉，输出被截一半，看起来像"脚本崩了" | 门禁类脚本去掉 `set -e`，累计 `fail` 在末尾统一退 5；这条已写进脚本注释 |
| **bsdtar 建不出符号链接** | `Can't create '.../libpython3.8.so': No such file or directory`、`.../Dynamic/lib/libyaml-cpp.so` 两处 | donor 侧无链接化（见 2.2）；`make-kit` 里解包报错改为容忍并打印 `NOTE` |
| **这个 MSYS2 没有 `cmp`** | 门禁里 `cmp` 报"未找到命令"（GBK 乱码一行），把一个真判定变成了假 WARNING | 用 `md5sum` 两两比（dev `.so` vs `.so.1.0`） |
| **ssh 进校机是 cmd** | `$VAR` 不展开、`;` 不是分隔符、`&&` 语义不同 | 一条命令只跑一个脚本文件；复杂逻辑写进脚本再送 |
| **写文件工具会吃掉转义** | 我在 heredoc 里的 C 字符串写了 `\\n`，落到校机变成**真换行**，交叉编译器报 `error: missing terminating " character`，J 段 [4] 红 | 字符串字面量留在**同一行**；改完**重新打包 payload**（否则解包会把坏副本再放回去）——这条是最容易被漏掉的：改本地文件 ≠ 改校机上正在跑的那份 |
| **Python 侧打补丁的两个坑** | `tr '\\n'` 过转义 → `AssertionError: 0`；bytes 字面量里放中文 → `SyntaxError: bytes can only contain ASCII literal characters` | 一次性补丁脚本走文本模式，别用 bytes |
| **`bsdtar -tv` 的字段布局** | 链接项在 `$9` 是路径、`$10` 是 `->`、`$11` 是目标（NF=11），是靠实测确定的，不是文档给的 | 重放链接表时按这个偏移取，别 `split()` 数下标 |
| **`readelf --dyn-syms` 默认截断长符号名** | 名字被折成 `PyInit_crosswin_[...]`，`grep PyInit_x` 直接不命中（6.1 第 9 条：本轮三条假红就是这么来的） | 凡是要拿符号名做判据的地方，一律 `--dyn-syms -W` |
| **带 NUL／非打印字节的日志被 `grep` 当二进制** | 本机 grep 这些 `.raw`/`.txt` 会说 `Binary file ... matches` 并只给一行 | `grep -a` 再管道 `tr -d '\0'`，否则读数取不全 |
| **链接可执行件要"库的库"也在搜索路径里** | 只给 `libpython3.8.so.1.0` 不够，ld 报它自己的 `DT_NEEDED`（`XML_*`／`inflate*` 那串 undefined） | `-L$PY/usr/lib/aarch64-linux-gnu -Wl,-rpath-link,同一目录` ＋ donor #9 的两颗 aarch64 实体 |
| **`gate-pyroot.sh` 里 pybind11 版本号那行打印是坏的** | 输出成字面量 `pybind11 = MAJOR.MINOR.PATCH`（sed 取的键名没展开成值）；同块的 `PYBIND11_INTERNALS_VERSION = 4` 是对的 | **本轮没改它**（改脚本就要重新打包复跑，而绿读数是这套脚本产生的）。版本号另行从 donor #7 的 `pybind11/detail/common.h` 直读：`2.6.2`。立案在第五节 14 |

---

## 七、算子口径：一个模型用到哪些算子、缺哪些算子

问题原话是"它用到哪些算子？缺少哪些算子？在校机的 Icraft deb 里头"。拆成三问，三问的答案来源不同，**其中一问在 deb 里读不出来**：

| 问 | 能不能答 | 从哪儿读 |
|---|---|---|
| ① iCraft 这个框架**认哪些算子**、ZG330 上哪些带条件 | **能**，但来源是 CLI 文档，不是 deb | `C:\Icraft\CLI v3.39.0\docs\ops\` |
| ② 编译器**内部有哪些算子节点** | **能**，从 deb 里那颗 `libicraft_xir.so` 的符号名读出来 | donor #1 解出的 `.so` |
| ③ **某个具体模型**用到哪些算子、缺哪些 | deb 里**读不出**——模型算子清单是 CLI 转换 imodel 时才产生的中间量 | 只能跑 CLI（本机 `C:\Icraft\CLI v3.39.0`）或看板上 codegen |

### 7.1 文档口径（① 的分母）

`docs/ops/` 实测：per-op 页 **114** 张，`spec.html` 总页里 `href="spec/*.html"` 出现 **208** 次、去重 **103** 个目标 ⇒ **11 张页不在索引里**；`spec.html` 正文里 "所有支持的算子" 出现 4 次。每张页都带器件标记：`QL100` 114/114、`30TAI` 114/114、页内出现"不支持" 16 张、`100TAI` 3 张。

`framework.html` 里其实有**两张表**（10-15 后半轮才发现，我第一遍只读了 4 列那张，更正见 6.1 第 15 条）：

| | 列 | 数据行 | ZG330 列 | BUYI 列 |
|---|---|---|---|---|
| 表1 | Pytorch Op \| Icraft Op \| BUYI \| ZG330 | 87 | 73 `√` ＋ 14 条件 | 72 `√` ＋ 15 条件 |
| 表2 | 多两列 PaddlePaddle、Tensorflow | **90** | **71 `√` ＋ 19 条件** | 69 `√` ＋ 21 条件 |

两表对 10 个键给的口径不一致：**6 行 Adaptive 池化**表1 写 `√`、表2 补了 `input_L % output_L != 0`／`input_H % output_H != 0 || input_W % output_W != 0` 并注名"此限制来自导出 onnx 格式模型的限制"；**PReLU** 方向相反（表1 带"alpha 为常数和 vector 外"的条件、表2 光一个 `√`）；Conv1d/2d/3d 那 3 处只是全角分号与空格的排版差。⇒ 取表2 当分母，全表逐字与限制清单落在 [[iCraft算子支持矩阵]]。

表1 那 14 行条件是：

```text
AvgPool2d/3d      count_include_pad=false（icraft 强制改成 true）、divisor_override<0
clamp             min/max 为 tensor
Conv1d/2d/3d      padding_mode != zeros
ConvTranspose2d   group != 1、padding_mode != zeros
div               除数不是常数标量
MaxPool1d/2d/3d   return_indices
pad               四维五维以外的输入、对 N/C 维 pad
PReLU             alpha 为常数或 vector 以外的情况   ← 表2 撤回
roll              shifts 为空、对最后一维滚动、对 C 维滚动
```

表2 多出来的是那 6 行 Adaptive 池化，共 19 条。⇒ 表观结论仍是"**ZG330 上没有整算子被禁，只有带参数级限制的算子**"，但 `Conv` 那条 `(pad_size != 0 || dilation != 1) && … > 2048` 的尺寸上限**只写在 BUYI 列**（ZG330 没写≠没约束，10-04 编译跑过 `ZhugePadLayoutPass`，仍以实测为准）。

### 7.2 IR 口径（② 的分子）

`libicraft_xir.so` 里没有裸的算子名字符串（`OP-ish tokens: 0`），名字挂在 **Itanium mangled name** 上：把 `_ZN6icraft3xir...<Name>NodeE...` 这类长度前缀编码扫出来，得到 **189** 个节点名（`libicraft_xir_serialize_flatbuffers.so` 少一些，**173**）。第一版扫法用 `[A-Za-z0-9_]{1,60}` 贪婪匹配和 `(?<!\w)` 边界，两次都数出 0，改成按长度前缀逐段解才成立（判据：`...INS0_11SoftmaxNodeE...` 必须解出 `Softmax`）。

文档名与 IR 名两边对齐（大小写与下划线折叠后）：**文档有、IR 没有的 8 个**：`MultiYolo, Region, Reorg, Route, SSDOutput, Swish, Unbind, Yolo`——除 `Swish`/`Unbind` 外全是**检测头类**（YOLO/SSD 的输出层）。**IR 有、文档没有页的 83 个**，但翻一遍就知道它们大多数**不是算子**：`Context/Pass/PassContext/Pattern/NetworkView/Value/Data/DataType/TensorType/…Target/…Mem` 这些是 IR 自身的设施类，真算子形的漏网样本是 `CumSum, GatherElements, IndexSelect, TopK, Exp, Ceil, Embedding, MatmulNBits, RopeDynamic, SimplifiedLayerNorm, SliceDynamic, GridNSample, Unfold, SwapOrder, PruneAxis` 这批。

### 7.3 读不出来那层（③）

**器件支持这件事不能从 `.so` 反推**——这是本轮的一条负结果：把 8 颗 `libicraft_*.so` 全扫一遍，`libicraft_hostbackend.so` 里能命中 16 个文档算子名（`Cast/Concat/Copy/Gather/Normalize/Region/Reshape/Resize/Sigmoid/Slice/Softmax/Squeeze/Tile/Transpose/Unknown/Where`），而 **`libicraft_zg330backend.so` 里 0 命中**：它导出的 32 个名字全是设施类（`ZG330Backend`、`ZG330Device`、`HardOp`、`HardOpInfo`、`LogicSegment`、`PhySegment`、`MemChunkInfo`…），一颗具体算子节点都没有。`xir`/`utils` 也是 0。⇒ **"ZG330 支持哪些算子"在 deb 里没有可枚举的真值来源**。

对照实跑：本项目的 `yolov8n` 在 ZG int8 档上是**零算子缺口**（host 侧只剩 Input/Output，`DetPostZG` 由 `@fpgat` 承担，见 [[板卡镜像实测取证]] 与记忆里的 D2 结论）——那是 CLI 前向跑出来的，不是这里推出来的。

### 7.4 custom op：能读契约，不能照抄契约

第三节 3.5 的读数不动：deb 里除 `_git_version.h` 没有真头文件，7 颗板端 op ＋ 3 颗解码 op 的 `导出 GLOBAL 符号 = 0`、入口候选为空。**自建一颗 custom op 目前仍没有可用的接口定义来源**（第五节 5）。

---

## 八、判级

- **A 级**：第一节状态表、第三节（含 3.7 的 L1／L2 全部读数、3.4 的 [3b] 闭包）、第四节门禁口径、第七节 7.1／7.2／7.3 的每一个计数（114 页／208 链接／103 去重／**两表 87 与 90 行**／ZG330 列 73 与 71 个 `√`、14 与 19 条件行／**两表 10 处口径冲突**／189 与 173 个节点名／8 与 83 的两侧差集／`zg330backend` 0 命中），以及第六节每一条"被推翻的事"——都有本轮日志或原文（`run-l2fix2-1015.txt`、`probe-l2-1015.raw`、`_opsurvey/*`、`icraft_op_matrix_6col.tsv`、`op-t1-vs-t2.txt`）且脚本可复跑。
- **B 级**：custom op 靠构造函数自注册（按"导出 GLOBAL 为 0"＋无任何入口候选推的）；**`-DPYBIND11_BUILD_ABI='"_cxxabi1013"'` 之后与厂商件真能同进程互传类型**（只证到 id 字符串逐字相同，没跑过同进程 import）；`cxxabi1013` ＝ GCC 9 代 libstdc++ 的 ABI 号（按版本号对应推的）；3.7 里"这三颗扩展模块与厂商 python 模块的唯一交点是 internals"（按未定义符号表推的）；`pyroot` 205→206→209 两次差值的归因（手工物化的 dev `.so` ＋ donor #9 的 3 个文件）；`kit.v1`→kit 的 163 M→228 M 归因；7.1 表观结论"ZG330 上没有整算子被禁"（样本只有 `framework.html` 那两张表，且两表对 10 个键互相矛盾——6 行 Adaptive 池化一张写 `√` 一张写带 onnx 限制、PReLU 一张有条件一张写 `√`；per-op 页的 16 处"不支持"字样没逐条对齐；"Adaptive 只在 output 不整除 input 时触发"是按公式推的）。
- **C 级**：uapi 里 `linux` 719 与 711 的差（未归因，见 5.10）；L1 件与容器件那 −191,792 B（未做段表／符号表比对）；7.2 那 83 个"IR 有文档无"的名单里**哪些是真算子、哪些是 IR 设施类**只做了目测分类，没逐个核。
- **D 级／未证**：一切"上了板子会怎样"——L2 的板上 `import`、L3 的出框与容器件逐条对齐、`crosswin_embed` 在板上跑起来、`uapi` 参与真实编译后的行为。**这些在没有上板读数之前不许当结论引用。** G/H 两段本身已从 D 级升到 A 级（10-15 跑通）。

---

## 相关页面

- [[校机无容器交叉编译]]：工具链与 kit 的第一版、L1 门禁读数、i686/Ninja/sysroot/cmd 四个原始坑
- [[校机交叉编译环境搭建SOP]]：把本页的组件与顺序收成"换一台机从零搭"那张表（含无 admin 的五条上限）
- [[工具链与素材进README]]：厂商的容器路线、素材在 `fdw` 的哪一格
- [[板卡镜像实测取证]]：出厂 rootfs 索引（`ref/board-libs.txt` 的分母来源）
- [[板端提取件台账]]：从板上取回来的东西（`.so` 清单等）
- [[板端我方代码与产物台账]]：产物真要上板时，本地源＋板上路径＋md5 的登记处
- [[板载接口与内核改造收纳进dev]]：`uapi` donor 服务的对象（V4L2／udmabuf／drm 那条线）
- [[板端内存上限与心跳日志]]：为什么禁止在板子上编译
- [[验证方法学]]：L1／L2／L3 分层定义
- [[交叉编译主机路由SOP]]：**下一轮动手前先看这页**（三台机分工与九步流程；环境已就绪时的路径／命令／判据在它的**三·补 照抄卡**）
- [[iCraft算子支持矩阵]]：第七节那两个计数的原文落地页
