# os

> **本页回答什么问题**：目标板开机后**运行在什么系统之上**——发行版与内核、内核模块现状、文件系统与分区、包管理与已装软件、时间与日志、启动与服务。
> **本页不回答**：板级接口与 PS／PL 归属在 [[板子（除芯片）]]；芯片规格在 [[芯片]]；USB 音箱麦克风一体机在 [[音频]]；串口接线与 PC 侧工具在 [[工具链与素材进README]]（⚠ 旧文还指过「环境搭建与快速上手」，**那一页已由她亲自删除**（嫌啰嗦），2026-11-01 核定：44 处引用指着它、盘上与 git 全史均零命中 ⇒ **判定作废、不再重建**；串口与网络两节的实体内容现住本页第六节与台账 `#204`～`#207`）。
> 口径规则：同一项同时有板端实测（E5）与镜像取证（E2）两个值时，**以板端实测为准并把旧值并记**；本页不复制 [[板卡镜像实测取证]] 的完整清单，只留与板端命令直接相关的事实。
>
> **本目录的草稿 `rt.md` 已于 2026-11-01 删除**（86 行，原为本页成文前的原始笔记）。删前逐块核过"别处有没有"，9 块全部有归属、且其中一块（podman 容器导入与自检 5 条命令）**原先只在它这里有**，已先迁进 [[交叉编译环节#5.1 本地编译环境（podman）|交叉编译环节——5.1]] 再删。逐块去向见本节末「附：rt.md 逐块去向」。唯一没有落点的是它开头那行 `未安装 netron`——纯本机状态备注，不构成项目事实，未保留。备份留在 `workenv/rt.md.deleted-20261101.bak`（2,913 B）。

## 一、发行版与内核

| 项 | 值 | 来源 |
|---|---|---|
| 发行版 | Ubuntu 20.04.4 LTS (Focal Fossa)，aarch64 | E5（2026-09-30，`/etc/os-release`）；E2 同 |
| 主机名 | `U.FMSH`（出厂默认） | E5；E2 同 |
| 内核 | `Linux 5.4.52`；`/proc/version` = `Linux version 5.4.52 (fmsh@fmsh-virtual-machine) (gcc version 7.5.0 (Linaro GCC 7.5-2019.12)) #3 SMP Fri Mar 13 13:44:29 CST 2026` | E5 |
| 内核串旧值（并记） | 镜像取证记镜像内 `Image` 的串是 `5.4.52-fmsh-sdk-v2025.04`——构建者、`#3`、构建时刻与本板实到的 `5.4.52` 一致，差异只在 localversion 段 | E2；本页以 E5 为准 |
| 时区 | `Etc/UTC`（`timedatectl`：RTC time `n/a`） | E5 |
| Python | 3.8.10（`/usr/bin/python3`） | E5 |
| glibc | 2.31 | E2 |
| 目标 ABI | glibc 2.31／libstdc++-9／Python 3.8（cp38）——交叉编译产物与预编译 wheel 都按这一档选 | E2，见 [[交叉编译环节]] |

## 二、内核模块（含一条对镜像取证结论的更正）

- 运行内核 `5.4.52`，`/lib/modules/5.4.52/` 与它同名；`modinfo` 实读 `u-dma-buf.ko` 的 vermagic = `5.4.52 SMP mod_unload aarch64` → 与运行内核**匹配**。
- 板上 `.ko` 一共只有 3 个（`find /lib/modules/5.4.52 -name '*.ko'`）：`u-dma-buf.ko`、`mali_kbase.ko`、`amvx.ko`（另有一份旧目录 `5.4.52-gce01ed384`，里面也是同样这 3 个文件；只有与运行内核同名的那份会被用到）。`lsmod` 实到三个**都在加载**：`amvx`（196608 B）、`mali_kbase`（462848 B）、`u_dma_buf`（28672 B，被使用 2 次）。（E5，2026-09-30）
- 出厂 `/etc/modules` 就写这三个名字（E2，提取件 `26_system_identity.txt`）→ 开机加载它们是出厂预期行为，不是我方手动插的。
- **更正**：[[板卡镜像实测取证#四、对软件栈的硬约束（这一节最影响设计）|板卡镜像实测取证——四、对软件栈的硬约束（这一节最影响设计）]] 第 1 条"出厂镜像加载不了任何外部内核模块"是按**厂商板 journal 里出现过的内核串（`v2024.02`／`v2025.04`）**（E2）推的；本板运行的 `5.4.52` 与模块目录、vermagic 都对得上，三个模块都在加载（E5，2026-09-30），出处页已就地加注。
- 更正后的口径：**"一个驱动能不能用"看板上有没有对应 `.ko`**——出厂只带这 3 个；其余 `=m` 或 `not set` 的项在板上都**没有 `.ko` 文件**，也没有与运行内核匹配的编译树，所以照样不可用——但原因是"镜像里没装"，不是"模块机制坏了"。
- `/lib/modules/5.4.52/` 下**没有 `build`／`source` 符号链接** → 要自己编模块得先找到与运行内核完全一致的内核树；板上几处源码树（含另一棵 `5.4.52-gce01ed384`）的情况见 [[板载接口与内核改造收纳进dev]] 第八节。

## 三、文件系统与分区

| 项 | 值 | 来源 |
|---|---|---|
| 根文件系统 | `/dev/mmcblk0p2`，ext4，rw | E5（`mount`） |
| 分区结构 | FAT16 启动分区（`Image`／`BOOT.bin`／比特流／`uEnv.txt`）＋ ext4 根；板端 `/boot` 目录为空——启动分区不挂载到它 | E2／E5 |
| fstab | 出厂占位 `# UNCONFIGURED FSTAB FOR BASE SYSTEM` → 根由内核 `root=` 挂 | E2 |
| 根分区容量 | 26G 中已用 6.9G（29%，2026-09-30，`df -h`） | E5 |
| 镜像与扩容 | 镜像整盘 29.72 GiB、换大卡不自动扩容、MBR 在偏移 512 处已由卡上实读确认——细节全在 [[板卡镜像实测取证]] 第一节 | E2 |

## 四、包管理与已装软件

- apt 源（E5，2026-09-30 实读）：`/etc/apt/sources.list` = USTC 镜像的 `ubuntu-ports`（focal 五条：main／restricted／universe／multiverse 及 updates／backports／security／proposed）；`/etc/apt/sources.list.d/armnn-ubuntu-ppa-focal.list` 另有 launchpad armnn PPA 的 deb 行。**arm64 换源必须走 `ubuntu-ports` 路径**（arm64 在 Ubuntu 的 ports 归档，不在主归档）。
- 已装包：E2 记 dpkg 550 包；2026-09-30 板端 `dpkg-query -W` 计 578 条。**"我方唯一新增的软件包是 `neofetch`"这句作废过两次**：先是 2026-10-05 又 `apt install strace`（`5.5-3ubuntu1`，走 USTC 源，A，用来抓 NPU 的 open/mmap 序列，见 [[板端我方代码与产物台账]] #23、[[板卡镜像实测取证#十四、strace 抓 NPU 调用序列（2026-10-05）|板卡镜像实测取证——十四]]），那时净增 2 个；**同日应她要求把 `neofetch` 卸载**（`apt-get remove --purge`，A：`which neofetch` 返 rc=1、`dpkg -l neofetch` 报 no packages found、包数 579→**578**），所以**当前净增只剩 1 个＝`strace`**。
- **孤儿包已清（2026-10-04 21:17 UTC，应她"apt-get autoremove"）**：`apt-get autoremove -y` 实删 **24 个**，apt 自报**释放 66.1 MB**（A，原文时刻取自 `/var/log/apt/history.log`，`End-Date` 21:17:13）。清掉的正是 neofetch 当初拖进来的显示类依赖：`chafa`／`libchafa0`、`ghostscript`／`libgs9`／`libgs9-common`／`libijs-0.35`／`libjbig2dec0`、`imagemagick-6-common`／`libmagickcore-6.q16-6`／`libmagickwand-6.q16-6`／`liblqr-1-0`、字体四包（`fonts-droid-fallback`／`fonts-noto-mono`／`fonts-urw-base35`／`poppler-data`）＋`gsfonts`、`libcups2`／`libavahi-client3`／`libavahi-common-data`／`libavahi-common3`／`libidn11`、`libpaper1`／`libpaper-utils`。
- **`dpkg-query -W` 计数只掉 17（578→561），不是 24**——差额 7 个是**带配置文件残留的包，remove 不 purge，仍以 `rc` 状态留在 dpkg 库里**（A，`dpkg -l | grep '^rc'` 恰好 7 行＝上面那三包字体＋`gsfonts`＋`imagemagick-6-common`＋`libpaper1`＋`poppler-data`）。**所以拿 `dpkg-query -W` 数包做验收时必须记住它把 `rc` 也算进去**；**这批 `rc` 残留同日已 purge 掉，见下面两条**。
- **`rc` 残留已 purge（同日，应她"把 rc 残留的配置文件也 purge 掉"）**：命令＝`apt-get purge -y $(dpkg -l | awk '/^rc/{print $2}' | tr '\n' ' ')`。四条验收全中（A）：**`dpkg -l | grep -c '^rc'` = 0**、**`dpkg-query -W` 从 561 掉到 554＝正好 578−24**、`apt-get check` 无坏依赖、`apt-get -s autoremove` 仍 0 待删。清掉的实际内容＝**23 份 conffile／247,750 B**（`dpkg-query -W -f='${Conffiles}'` 逐个 `stat` 求和，大头是 `/etc/ImageMagick-6/*.xml` 16 份＋`/etc/ghostscript/{fontmap,cidfmap}.d/*.conf` 6 份）。**apt 自报的是"0 B of additional disk space"**——这不是矛盾：包体在 remove 那一步就释放了，purge 只拿 conffile，而 conffile 不进 `Installed-Size` 记账，所以**别拿那句当"purge 没起作用"的证据**。**`fontconfig` 触发器会不会被 purge 重跑——已经取证，见下面两条；上一轮那句"没有任何可观测后果"说反了**。
- **触发器跑了，而且 autoremove 和 purge 各跑一遍**（A，读于板钟 2026-10-04 21:51 UTC，原文取自 `/var/log/dpkg.log`）：`21:17:11 trigproc libc-bin` → **`21:17:12 trigproc fontconfig:arm64 2.13.1-2ubuntu3`** → `status installed`，落在 `apt-get autoremove -y` 的 `End-Date 21:17:13` 之内；purge 那次留了完整激活现场——**`21:43:26 purge fonts-noto-mono` → `status config-files` → `status triggers-pending fontconfig:arm64 2.13.1-2ubuntu3` → `21:43:29 startup packages configure` → `trigproc fontconfig:arm64` → `status installed`**，与 `history.log` 里 `Commandline: apt-get purge -y fonts-droid-fallback fonts-noto-mono fonts-urw-base35 gsfonts imagemagick-6-common libpaper1:arm64 poppler-data`、`End-Date 21:43:29` 逐秒对上。**七个包的 purge 只产生一次 `trigproc`**：挂起的触发器被合并成一次执行（B，dpkg 的 coalescing 行为，没读源码核实）。
  - **触发器定义与动作有原文**：`/var/lib/dpkg/info/fontconfig.triggers`＝三条 `interest-noawait`（`/usr/share/fonts`、`/usr/share/ghostscript/fonts`、`/usr/share/texmf/fonts`）；`fontconfig.postinst` 第 5 行 `if [ "$1" = triggered ]`、第 8 行 `fc-cache -s -v 1>/var/log/fontconfig.log 2>&1`（**triggered 分支不带 `-f`＝只做增量重建**，带 `-f` 的那条在第 18 行的 configure 分支）。**后果不是零，是一次 `fc-cache` 增量重建，而且它自己落了日志。**
  - **副作用读数（A）**：`/var/log/fontconfig.log` 1,825 B、mtime `21:43:29.595`，25 行把 `truetype/{noto,droid}`、`type1/{gsfonts,urw-base35}`、`opentype/urw-base35`、`cMap`、`cmap` 逐个报 `skipping, existing cache is valid: 0 fonts`，末两行 `/var/cache/fontconfig: cleaning cache directory` ＋ `fc-cache: succeeded`；`/var/cache/fontconfig` 目录 mtime `21:43:29.547`、现存 19 项（18 颗 `*-le64.cache-7` ＋ `CACHEDIR.TAG`）；`fc-list` 现在 **6 个**，全在 `/usr/share/fonts/truetype/dejavu/`（DejaVu Sans／Serif／SansMono 各 Book＋Bold）。**所以"字体链坏没坏"以后不用猜——看 `/var/log/fontconfig.log` 的 mtime 加 `fc-list` 计数**（`/etc/fonts` 248 KB 原样、`python3 -c 'import cv2'`＝4.6.0 照旧这两条仍然成立）。
  - **为什么 purge 也会激活触发器＝C，机制没取到**。`fontconfig.triggers` 盯的三个路径都在 `/usr/share`，而 purge 实删的 23 份 conffile 全在 `/etc` 下，按字面读法不该激活；候选解释是 dpkg 对 removal 类操作按"该包曾在 interest 路径下有文件"来激活，**没读 dpkg 源码，别当结论用**。
- **purge 留下一批删不掉的目录，原因已取证——上一轮那条"目录全空"是错的，作废**：`/usr/share/fonts/truetype/{noto,droid}`、`/usr/share/fonts/{type1,opentype}/urw-base35`、`/usr/share/fonts/type1/gsfonts`、`/usr/share/fonts/cMap`＋`cmap`、`/usr/share/poppler/cMap/Adobe-{GB1,CNS1,Japan1,Japan2,Korea1}`。**错在哪：`ls` 不带 `-A` 看不见隐藏文件。**`find -mindepth 1` 数出来**每个目录里都还剩一颗 `.uuid`（36 B，内容是一个 UUID）**，所以 dpkg 当时那句 `directory ... not empty so not removed` 挡它的就是这颗标记文件——**目录从来没空过**。
  - **`.uuid` 是 fontconfig 自己写的目录标签文件**（A，不用推测：`/usr/share/fonts/truetype/noto/.uuid` 内容 `c39a93aa-4737-4dd2-a55a-3085d2a73ba3`，`/var/cache/fontconfig` 里就有同名的 `c39a93aa-...-le64.cache-7`；`/usr/share/poppler/cMap/Adobe-GB1/.uuid` 的 `95f24a6e-...` 同样有对应 cache 文件）。`dpkg -S` 对这些 `.uuid` 报 no path found＝不属于任何包。**时间线也对**：除 `truetype/.uuid` 与 `truetype/dejavu/.uuid` 是镜像构建期的 `2026-03-13 03:13:50`，其余 9 颗 mtime 全落在 `2026-09-28 16:06:05.8–16:06:06.2`＝那一次 `trigproc fontconfig`（`dpkg.log` 第 10028 行）的同一秒。
  - **壳目录已按她"2要删"清掉（板钟 2026-10-04 23:11 UTC，A）**。两条命令：`find /usr/share/fonts /usr/share/poppler -name .uuid -not -path "*/dejavu/*" -delete` ＝**实删 16 颗**；`find /usr/share/fonts /usr/share/poppler -mindepth 1 -type d -empty -delete` ＝**实删 15 个目录**（`truetype/{noto,droid}`、`type1/{gsfonts,urw-base35}`、`opentype/urw-base35`、`cMap`、`cmap`、清空后一起走的父目录 `type1`＋`opentype`、`/usr/share/poppler/cMap` ＋五个 `Adobe-*`；`-delete` 隐含 `-depth`，所以父目录跟着走）。**删完只剩 `/usr/share/fonts/truetype/dejavu`（6 颗 ttf ＋它自己的 `.uuid`）与 `/usr/share/poppler` 那颗空父目录**（`-mindepth 1` 把它自己排除了，没另动）。**"先删 `.uuid` 才删得动目录"这一刀把机制反向证实了**——dpkg 那句 `not empty so not removed` 挡它的就是那颗标签文件，**这条从 B 提到 A**。**同时更正我上一轮写的"11 颗 `.uuid`／396 B"：实数是 17 颗**（`/usr/share/fonts` 树 12 ＋ poppler 树 5），`ls` 视野里全隐身。回归读数：`^rc` 仍 0、`dpkg-query -W` 仍 **554**、`apt-get check` rc=0、`fc-list` 仍 **6**、`cv2` 4.6.0、`/usr/share/fonts` **2912→2840 KB**（省 72 KB＝目录块＋标签文件）；临时清单 `/tmp/uuid-todelete.txt` 用完已 `rm`，不入台账。
  - **验收顺带跑出的一条（A 读数／B 解释）**：`/var/cache/fontconfig` 的条目从 19 **涨到 21**。我为了验收跑了 `fc-list`，而它会让 libfontconfig 惰性重建——被删掉的两颗现存目录（`/usr/share/fonts`、`truetype`）因为 `.uuid` 没了就**新生成一对 UUID 与 cache 文件**，而**已删目录留下的旧 cache 不会被自动回收**。所以**光删目录不等于缓存干净**，要清得 `fc-cache -f -v` 重扫（本轮没做，不在批准范围）。这也说明一条口径：**`fc-list` 不是只读命令**，别拿它当"看一眼"的零成本探针。
  - 一条没解释的读数（C）：`/usr/share/poppler/cMap/*` 不在 `fonts.conf` 的扫描面里——那里只有 `<dir>/usr/share/fonts</dir>`、`<dir>/usr/local/share/fonts</dir>`、`<dir>~/.fonts</dir>` 三条，`/etc/fonts/*.conf` 与 `conf.d/` grep `poppler|cMap` 零命中——可它照样有 `.uuid` 和对应 cache 文件。候选解释是当年 `cMap`／`cmap` 是指向 `/usr/share/poppler/cMap` 的软链、被 fc-cache 顺着打了指签；现在实测这些路径都是真目录且 inode 各异（132568／132569／132574），`cMap` 与 `cmap` 两颗 `.uuid` 值也不同（`e509c326-…` vs `896a7be5-…`）。**链路本身没取证**。顺带一条同源读数：那次 `fc-cache` 对 `/usr/share/fonts/*` 每个子目录都报了两遍，第二遍是 `skipping, looped directory detected`，最终 `succeeded`＝没坏，只是它自己重复访问。
- **清完的回归检查（A）**：`apt-get -s autoremove` 现在 **0 个待删**、`apt-get check` 无坏依赖；现役链的工具全部照旧——`ffmpeg 4.2.7-0ubuntu0.1`、`arecord 1.2.2`、`python3 -c 'import cv2'` → **4.6.0**、`v4l2-ctl` 在（那颗工具不认 `--version`，别拿它当坏证据）。**直播进程没被这次卸载影响**（时间线否证与 `ldd` 依赖闭包见 [[板卡镜像实测取证#十八、YOLOv8n 第一次上板出数（D-31 队列第 ① 项，2026-10-05）|板卡镜像实测取证——十八]]）；**同一台 pid 83796 在 purge 之后 3 min 35 s（21:47:04）进了 `ImageMake Timeout` 错误态、`live.stat` 停更**——同形故障在卸载之前的 17:51 就出现过一次，判因果不成立，读数与判活口径的修订都在十八。根分区 8.6 G 用／16 G 空。
- 离线 `.deb`：`/var/cache/apt/archives` 存有厂商离线安装的包；2026-09-30 实测 163 个，E2 清单记 143 个，差值原因未差分。
- Python 侧：`icraft` 装在 `/usr/local/lib/python3.8/dist-packages/icraft/`（pip 装入，非 apt 包；模块没有 `__version__` 属性）；root 下 `python3 -c "import torch"` **失败**（E5），E2 记 torch 1.9.0 位于 `/home/fmsh/.local`（非系统 site-packages）——**跑 torch 要换用户或补 PYTHONPATH**。
- 镜像里预装的全部清单（ffmpeg 4.2.7、v4l-utils 1.18.0、OpenCV 4.6.0.66、alsa-utils 1.2.2、u-dma-buf、icraft、torch……）逐条在 [[板卡镜像实测取证#五、镜像里已经装好的东西（到板第一天不需要 apt）|板卡镜像实测取证——五、镜像里已经装好的东西（到板第一天不需要 apt）]]，本页不复制。
- `apt-daily.timer`／`apt-daily-upgrade.timer`／`unattended-upgrades` 出厂就在（E2）→ 联网时会自动更新；离线现场它们会反复失败刷日志（要控住按 systemd 常规禁。此项**未实测**）。

## 五、时间与日志

- **没有可用时钟源**：`hwclock -r` → `hwclock: Cannot access the Hardware Clock via any known method`（E5，2026-09-30）；每次启动 `hctosys: unable to open rtc device (rtc0)`（E2）。原因链（RTC 走 I2C 而 dtb 全 disabled、内核无 `RTC_DRV_*`）在 [[板子（除芯片）]] 与 [[板卡镜像实测取证]]。
- 后果：**开机时间回落，`date` 不可信**——要时序的自测数据自己打 `CLOCK_MONOTONIC` 或与 PC 对时；跨启动排序靠 boot id，不靠时间戳。
- journal 时间戳在厂商板上大量冻在 `2023-03-02 20:58`（97 个 boot 记录里只有 5 个带启动横幅）——统计口径见 [[板卡镜像实测取证#六、厂商板子的运行痕迹（journal 统计）|板卡镜像实测取证——六、厂商板子的运行痕迹（journal 统计）]]。
- rsyslog 刷屏（E2）：`omfile` 反复 suspended／resumed，原因是 `/var/log` 属 `root:107` 且 755，rsyslog 降权到 `syslog` 写不进——纯软件问题，改属主即可，不是硬件故障。
- `loglevel=8` 写在 bootargs 里（见下节）→ dmesg 比常规详细得多，也在吃内存与日志体积。

## 六、启动与服务

- 启动链：`BOOT.bin`（U-Boot）→ `uEnv.txt`（`bootcmd=run loadbit; run uenvcmd`）→ `Image`＋dtb → 根挂 `/dev/mmcblk0p2`。`loadbit` 是否空转、`download.bit` 命名约束在 [[板子（除芯片）]] 第四节。
- bootargs 实读（E5，`/proc/cmdline`）：`console=ttyPS0,115200n8 earlycon=uart8250,mmio32,0xe0004000 loglevel=8 root=/dev/mmcblk0p2 rootwait rw clk_ignore_unused mem=1024M`——`mem=1024M` 是硬顶（内存预算账见 [[板卡镜像实测取证#二、板子身份实测表（E2）|板卡镜像实测取证——二、板子身份实测表（E2）]]），串口参数与 [[工具链与素材进README]] 的 COM6 口径一致。
- systemd 引导，`rc-local.service` 已 enable → `/etc/rc.local` 开机执行。**出厂版本**（E2，提取件 `26_system_identity.txt`）做四件事：改 MAC（`ae:59:f4:2d:3a:99`）、起 `systemd-resolved`、`timeout 5 dhclient` **之后又写静态 `192.168.126.49/24`**、起 `sshd`——DHCP 与静态两套叠在同一文件里。⚠ **出厂那句 `timeout 5 dhclient` 是个坑**：它只给那颗 dhclient **5 秒**；跨网段旧租约下它 INIT-REBOOT `REQUEST(旧IP)`，路由器 NAK 快能 4 秒内转 DISCOVER 拿到（2026-03-13 实测），但 **Windows ICS 对不认识 REQUEST 不回话**，5 秒内到不了 DISCOVER 就被 timeout 杀——**无地址、断**；且它与 ifupdown 的 dhclient 并存形成双客户端。`Killed old client process`＋`DHCPRELEASE` 是 `dhclient -r` 才有，不是开机裸 dhclient。机制、证据与根治见 [[1-Linux初始化#三、首启联网（仅 COM，空白镜像起手）|1-Linux初始化——三、首启联网]] 的「出厂 `timeout 5 dhclient` 的坑」小节。**我方现用版**（台账 #205）已把它和 `timeout 30 dhclient` 一起删掉，改走"DHCP 优先／静态兜底"（含启动 300 秒后的 DWMAC 保护），两版备份在 [[板端我方代码与产物台账]] #18，操作背景与命令细节见 [[板端我方代码与产物台账]] **#204～#207**（本页第六节上文即其读数）。
- 网络：`/etc/network/interfaces.d/eth0` 写死 `dhcp`（E2）；`sshd` 允许 root 口令登录（E2）；登录方式与串口接线见 [[工具链与素材进README]]、口令值按 D-27 只在 [[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]] 一处。
- `/etc/modules` = `u-dma-buf`、`mali_kbase`、`amvx`（E2；E5 确认三个都在跑，见第二节）。
- 出厂 init.d：alsa-utils、cron、dbus、hwclock.sh、kmod、networking、procps、rsyslog、ssh、unattended-upgrades、x11-common（E2）。
- **无 X server、无 Wayland 合成器** → `cv2.imshow`、GTK／Qt 窗口都起不来，结果只能落文件、stdout 或网络（[[板卡镜像实测取证#四、对软件栈的硬约束（这一节最影响设计）|板卡镜像实测取证——四、对软件栈的硬约束（这一节最影响设计）]] 第 5 条）。

## 七、我方对板端 OS 的改动（归口，2026-10-11 起）

**这一节是"改了板子系统本身什么"的唯一归口**：判据＝动到 OS 层才算——内核参数／swap／开机脚本／系统包／系统 Python／`/usr/local/bin`。纯我方脚本落在 `/root/` 下的不算，那些归 [[板端我方代码与产物台账]]。以前这类操作散在第三节、第四节、[[板端内存上限与心跳日志]] 五／六节和已作废的「环境搭建与快速上手」§3.2，以后**再改 OS 层只往这一节加行**，并在台账登文件行。

| 改了什么 | 落点与读数 | 怎么生效 | 复核 |
|---|---|---|---|
| **加 1 G swap**（她 10-11 的指令"新增 swap=1g"） | `/swapfile` **1,073,741,824 B**、`-rw------- root:root`，`mkswap` 报 UUID `2c68205f-c4ca-4513-af5e-75f0003b403b`；`/proc/swaps` 一行 `/swapfile file 1048572 0 -2`；`free -m` → `Swap: 1023 0 1023` | `swapon /swapfile`（手动已生效）＋ `/etc/rc.local` 里的兜底行（见下） | **A**（`/proc/swaps`、`free`、`stat` 直读） |
| **`vm.swappiness=10`**（她 10-11 的指令） | `/etc/sysctl.d/99-swappiness.conf` 一行 `vm.swappiness = 10` | `systemd-sysctl` 开机读 `/etc/sysctl.d/`＝Ubuntu 标准机制；当场用 `sysctl -w` 应用 | **A**（`sysctl vm.swappiness` 回 10） |
| **`/etc/rc.local` 加 swapon 兜底行** | 现用版 **999 B／md5 `795cafdd0e9169a7412e48250fe25ca5`／`-rwxr-xr-x`**（原 925 B 版备份在 `/root/rc.local.bak-swap-20261011`＝`5706fc37…`，与台账 `#18` 的 `rc.v2` 同 md5）。新行＝`swapon /swapfile 2>/dev/null \|\| echo "swap-activate: swapon failed rc=$?"`，位置在**"开机 300 s 以后不再配网"那道 `UP>300 → exit 0` 之前** ⇒ 任何时刻启动都跑得到它。`bash -n` 通过，`rc-local.service` 出厂就 enabled | 下一次上电自动执行 | **C**：**没有实跑过一次重启来验证挂上**，只验证了脚本语法与放置位置。**10-12 她裁"不验"** ⇒ 不专门为它安排一次重启，这一条**就停在 C、不按 A 报**；只在因别的缘故上电后顺手看 `/proc/swaps` |
| **心跳与内存上限工具** | `hb.sh`（`#166`）／`cap.sh`（`#167`）本体在 `/root/funasr/asr/`，并在 **`/usr/local/bin/` 各建一根同名软链**——这一步是 OS 层的（改了系统可执行路径） | 软链即时生效，任何 shell 直接 `hb.sh`／`cap.sh` | A（`hb.sh status` 实测能起停） |
| **系统包净增 `strace`** | `5.5-3ubuntu1`，走 USTC 源（`#23`）；`neofetch` 同日已卸载并 autoremove＋purge 干净 | apt | A，细节全在第四节 |
| **第三方 Python 只进 venv** | `/root/funasr/venv/`（`#87`），**funasr 这条线的包一个都没进系统 `/usr/bin/python3`**；不 `activate`、不改 `PATH`、不写 `/etc/profile`。**此句只管 funasr**——板侧 LLM 分词那条线是例外，见下一行 | 一律用绝对解释器路径 `/root/funasr/venv/bin/python` | A。**理由是这台板子还有另一条会话在用系统 Python（TTS）**，动它就是动别人的环境 |
| **系统 `tokenizers` 0.13.3 → 0.20.3**（2026-11-04 03:43:33 UTC） | 就地 `python3 -m pip install --no-index --no-deps /root/tkwhl/tokenizers-0.20.3-cp38-cp38-manylinux_2_17_aarch64.manylinux2014_aarch64.whl`（2,893,923 B／`fc747d88688d1b1609b670feb04ce53a`，PyPI cp38/aarch64 轮子）。pip 现场读数＝`Successfully uninstalled tokenizers-0.13.3`＋`Successfully installed tokenizers-0.20.3`，随后 `python3 -c "import tokenizers;print(tokenizers.__version__)"` → `0.20.3`。**0.13.3 本身也是 pip 装进系统 Python 的**（10-14 厂商 Qwen2 demo 那次，轮子 `#158` 已于 10-31 从板上删） | 无服务要重启，装完即可 import | A（pip 两行＋版本回读）。**动的是系统 site-packages，不在 venv 里**——与上一行 funasr 的「只进 venv」是两条线各自的决定，别再当成一条。为什么要升＝0.13.3 读不了 `model.merges` 写成成对数组的分词件，正本＝台账 §卅六；上板件登记同节 §一 |
| **journald 上限 256M**（2026-10-31，她"journald 配个合适的上限"） | **drop-in `/etc/systemd/journald.conf.d/99-wcis-size.conf`**（739 B）：`SystemMaxUse=256M`／`SystemMaxFileSize=32M`／`SystemMaxFiles=20`／`RuntimeMaxUse=32M`／`MaxRetentionSec=1month`。**出厂主文件 `/etc/systemd/journald.conf`（1042 B，2022-04-21）一个字节没动**，备份 `<同名>.bak-20261031`（1042 B，与原文件逐字节相同） | `systemctl restart systemd-journald`（已执行）；drop-in 是 systemd 的标准叠加机制，**下次开机自动生效** | **A**——判据是 journald 自己启动打印的那行：`System Journal (…) is 48.0M, max 256.0M, 207.9M free.`（2026-10-31 11:36:35 UTC 板上原文）。⚠ **`systemctl show systemd-journald` 在 systemd 245 不暴露这些属性**（只回 `RuntimeMaxUSec=infinity`），`systemd-analyze verify <某.conf>` 也不支持 .conf（报 `Invalid argument` 是用法错不是语法错）⇒ **只认 journald 那行日志** |
| **板端时区 UTC → Asia/Shanghai**（2026-11-03，她「设板子时区」） | `/etc/localtime` 软链由 `/usr/share/zoneinfo/Etc/UTC` 改为 `/usr/share/zoneinfo/Asia/Shanghai`；`/etc/timezone` 内容写 `Asia/Shanghai`。读数：`date` → `Tue Nov  3 17:16:24 CST 2026`（改前同一时刻是 `09:16 UTC`）；`readlink -f /etc/localtime` → `/usr/share/zoneinfo/Asia/Shanghai`；`klar_executor.py --do '现在几点'` → `现在 17:16`（改前回 `09:10`） | **`timedatectl set-timezone Asia/Shanghai` 在这块板上会失败**：报 `Failed to set time zone: Access denied`（它走 D-Bus 找 systemd-timedated，被拒），而且失败时 `timedatectl` 自己一度显示已切到 CST、实际 `/etc/localtime` 仍是 Etc/UTC ⇒ **别信 timedatectl 的显示，只认 `readlink -f /etc/localtime` 与 `date`**。实际生效靠手动改软链：`ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime`。**Python 进程会缓存时区**，改完必须 `systemctl restart klar-voice-gateway` 才见效 | **A**（`readlink -f /etc/localtime`＋`date`＋`现在几点` 三处直读一致）。**回滚**：`ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime && echo Etc/UTC > /etc/timezone` 再重启 gateway |
| **板端时区按旧裁复原**（2026-11-04，重烧后回潮；见 D-1793769822） | 113 于 2026-11-04 被重新烧写，`/etc/localtime` 回到 `Etc/UTC`（`date` 实证 05:22 UTC）⇒ 按上一行旧裁**原样复原**：`ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime`＋`echo Asia/Shanghai > /etc/timezone`，**timedatectl 依旧不试**（旧裁 Access denied 仍有效）。改后 `date` → `Wed Nov  4 13:22:39 CST 2026`，`readlink -f /etc/localtime` → `.../Asia/Shanghai` | **Python 缓存时区**：重启对象换成了现役三单元 `lang-server-{http,voice,loop}`（上一行写的 `klar-voice-gateway` 已随语音链迁档退役，见 D-1793760298）| **A**（`date`＋`readlink`＋板端 `try_command("现在几点")` → 「现在 13:23」三处一致）。**回滚**同上行 |
| **lang-server 0.1.1 deb接管旧语音服务**（2026-11-04） | 新包代码/usr/lib/lang-server，配置/etc/lang-server，私有venv与模型/var/lib/lang-server；三unit改由/lib/systemd/system提供，服务用户lang-server附audio组。apt新增lang-server、python3-venv、python3.8-venv，并按版本依赖升级7个Python3.8系统包（20.04.7→20.04.18，解释器仍3.8.10），未做全量upgrade或系统pip安装 | 旧/etc手工unit和旧server移到root-only备份；新三服务active/enabled、全带--no-warm，模型下载oneshot成功结束；循环输出改到可写cache | A：板内/局域网health、四端口、PID稳定、私有venv依赖与五组模型文件通过；未构造或运行模型。完整路径、备份和回滚入口见[[Ubuntu20.04语音服务deb迁移与启动SOP#本次落点与读数\|Ubuntu20.04语音服务deb迁移与启动SOP——本次落点与读数]] |

**journald 这条的数字与理由（为什么是 256M，不是别的数）**：

- **出厂默认等于不设限**：`journald.conf` 的 `SystemMaxUse` 是**注释**状态 ⇒ 实际默认是 `min(盘 10%, 留 SystemKeepFree)`。`/` 是 26G 的 SD 卡 ⇒ **允许 journal 吃到 2.6G**。这就是它反复回涨的根因（10-31 当天 `vacuum` 到 137M，几小时后又涨回 224M）。
- **实测增速（A，10-31 板上）**：`journalctl --since "-60min" | wc -c` ＝ **3,135,385 B ＝ 3.0 MiB/h 原始文本** ⇒ **约 72 MiB/天**（journal 二进制通常再乘 1.3–1.6）。当时那 225 M 存量 ≈ **2.5 天**。
- **取值**：**256M ≈ 3.5 天**——够对上"昨天／前天发生了什么"这类排障问题，又不至于在 26G 的盘上留一个几 G 的黑洞。想更省就改 `128M ≈ 1.8 天`。
- **`RuntimeMaxUse=32M` 的理由**：`/run` 是 **100M tmpfs（内存盘）**，运行期 journal 攒在那儿等于吃内存；实测 `/run/log/journal` 现在是 **0**，但存档模式下切换时会短暂用到。
- **回滚**：`rm /etc/systemd/journald.conf.d/99-wcis-size.conf && systemctl restart systemd-journald`——因为改的是 drop-in，**出厂主文件从未被改过**，回滚不涉及任何"恢复原值"的动作。
- **规程**：清理流程本身已写成 [[板端磁盘清理SOP]]（第七节就是这条）。

**没做的事**（写清楚免得被当成做过）：`/etc/fstab` **没动过**（出厂全文就一行 `# UNCONFIGURED FSTAB FOR BASE SYSTEM`，根是靠内核 `root=` 挂的，这块板上从没验证过 fstab 会被执行 ⇒ 不拿它当持久化机制，swap 的开机激活走 rc.local）；`apt-daily.timer`／`unattended-upgrades` **没关**；**rsyslog 仍在跑**（`ForwardToSyslog=yes` 是出厂默认，`/var/log/syslog` 那份文本日志也在写，本页只限了 journal、没限 syslog）；CPU governor／频率 **没动**（板上内核没有 cpufreq 节点，见 [[板端内存上限与心跳日志]]）；除此之外**没改过任何内核参数**，`/etc/sysctl.d/` 里我方只放了 `99-swappiness.conf` 一支。

**swap 这条的作用边界（决定它该被怎么读，三条都是这轮定的口径）**：

1. **它是垫，不是提速通道**。eMMC 直写实测 **17.6 MB/s**（`dd` O_DIRECT）／**19.7 MB/s**（`fdatasync`）（A，2026-10-11 板上直读）⇒ 一次 400 MB 的换出再换回，光是页搬回来就要 **约 22 s**。所以**任何"性能不够就靠 swap 补"的方案都不成立**，它换来的只是"OOM killer 之前有一段缓冲、不至于当场整机挂死"。
2. **有了 swap，512 MiB 的 `VmHWM` 门禁含义变了**：进程现在可以把页甩到盘上而不再当场被杀，**峰值 RSS 单看会偏乐观**。所以 `asr_chain.py` 的心跳与停止行同时报 `vm_swap_mib`（本进程被换出量）＋`majflt`（主缺页计数，一次从 swap 读回页就是毫秒级 stall，直接进 `asr_ms` 尾巴）＋系统级 `swap_used_mib`／`mem_avail_mib`。**读 RSS 必须和这两列一起读**，单报一个数就是误导。**四件战役的实测**：`VmSwap` 全 **0.0 MiB**、系统 `SwapUsed` 最大 **0.5 MiB**、`majflt` 7／0／0／0 ⇒ **这条链在 993 MB 上不需要换页就跑得完**，这两列目前是零读数；**但规则不撤**——多档同装（`env_probe` 五档合计 ≈1.23 GB RSS）或叠上 Qwen2 那 1.3 GB 参数体时，零读数不代表下一个任务也是零。
3. **swap 不保护 CMA**。[[板端内存上限与心跳日志]] 第四节那条归因（装 232 MB 权重能把 `CmaFree` 从 96 MB 压到 **0 kB**，最像的挂死机制）说的是一块 256 MB 的**连续物理页池**，换页机制碰不到它——`/proc/meminfo` 的 `CmaFree` 依旧是更早报警的那一列。**战役实测（A）**：四件的 `CmaFree` 运行最小值 **63,756／27,504／19,984／0 kB**，最长那件把它打到 **0** 而板子毫发无损、四件零错误 ⇒ **CMA 见底不足以单独挂死**，第四节已按这条收窄归因；这一列仍然要盯，但盯的理由变了（用户态 malloc 碰不到它，会碰它的是厂商 NPU／Mali 驱动，那半侧本轮没测）。

**顺带更正两处旧说法**：① `MemTotal` 993 MB 里 **256 MB 是 CMA 池**，所以 `MemAvailable` 不能当起跑门禁（这条 10-10 就记过，见 [[板端内存上限与心跳日志]] 第四节），`#105` 那个"avail>700 才起跑"的门限没有预测力；② 那句"**无 swap 是她 10-11 的硬指令、测试期性能第一**"（D-43 与 [[板端内存上限与心跳日志]] 第三节都这么写）**已被她 10-11 的新指令推翻**，现状态＝有 1 G swap＋`swappiness=10`，见 [[状态源与决策记录#D-44 · 板上加 1 G swap＋swappiness=10（推翻 D-43 的"不加 swap"），ASR 后端改回离线 Paraformer（推翻 D-42 ①），并把 OS 侧改动归口成一节|状态源与决策记录——D-44]]。

### 附：`rt.md` 逐块去向（2026-11-01 删前核查）

| rt.md 原块 | 判 | 现在在哪 |
|---|---|---|
| `未安装 netron` | **无落点，不保留** | 纯本机状态备注（netron 是模型可视化工具，厂商页里当用法出现）；不构成项目事实 |
| `# diskmgr`：32G/64G TF 卡、防厂商扇区数不足 | 有 | `PS/psdev.md:100`（"防止不同厂商扇区数不一样选择64g而非镜像的32g"）＋`:107` 卡上分区表实测 |
| 同块：空余空间建 1G swap 分区 | 有，**且已实现方式不同** | 本页第七节：实际落成 **`/swapfile` 文件**（1,073,741,824 B），不是独立分区 |
| 同块：`ps 1g == pl 2g` | 有 | [[板子（除芯片）]]:26-27（PS 侧 DDR3 **1GB**／PL 侧 DDR3 **2GB**） |
| `# connect`：CP210x、putty `115200n8` | 有 | 本页第六节 bootargs 实读（`console=ttyPS0,115200n8`）＋[[板端内存上限与心跳日志]]:172-173（本机 COM6＝Silicon Labs CP210x → 板 `/dev/ttyPS0`） |
| 同块：`root` 口令 | 有 | 按 **D-27** 单点记账，值只在 [[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]] 那一处 |
| 静态 IP 不可用 → 改 DHCP＋固定 MAC | 有 | 本页第六节（出厂 `rc.local` 改 MAC `ae:59:f4:2d:3a:99`＋静态 `192.168.126.49/24`；我方现用版＝DHCP 优先／静态兜底）＋台账 **#204～#207**（`interfaces.d/eth0` 钉 MAC、`dhclient.conf` 两轮、租约改名） |
| 板载网口只支持百兆 | 有 | [[板子（除芯片）]]（5 处，含"`100Mbps` 全双工"口径） |
| 无 RTC → 重启回 1970，`date -s` 后要 `hwclock -w` | 有 | 本页第五节（`hwclock -r` 报无时钟源、`hctosys: unable to open rtc device`，原因链指 [[板子（除芯片）]]） |
| `## check` 那张"待实测"表（CPU/glibc/python/torch/磁盘/-mcpu/网速） | **已过期，不保留** | 绝大部分早有读数：本页第一／四节＋[[板卡镜像实测取证]]；`-mcpu` 那条仍挂 **D-09**（待核对官方手册） |
| `## oom`：放弃 funasr／心跳日志／OOM 后走 COM 看内核 | 有 | ① ASR 改判见 [[板端FunASR链路操作与可调参数]]:9-10（10-30 "不再是现役"）＋台账 §廿四（10-31 删模型）；② 心跳日志见 [[板端内存上限与心跳日志]]；③ "挂死瞬间只有串口能看到内核 printk" 同页 :188 |
| `# 交叉编译容器` ＋ `## 导入与自检`（podman 5 条） | **原先只在这里，已迁移** | **[[交叉编译环节#5.1 本地编译环境（podman）\|交叉编译环节——5.1]]**（那份 `环境搭建与快速上手` 不存在，本页是唯一现存副本，删前先迁） |
