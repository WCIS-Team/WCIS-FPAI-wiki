# 官方demo教程与skill审计

> **本页回答什么问题**：2026-10-30 落进 `repos/official/` 的这批官方 demo／tutorial／参考实现＋随仓 skill，对照我方**已经记录在案**的 NPU 结论——哪几条要改判、哪几条厂商开口项可以就地关闭、哪一处是两份官方正本互相矛盾的**新增冲突**。
> **判据等级**：**A**＝本机／板上实测读数（命令与产物在第十一节）／**B**＝厂商文档或官方仓库原文（一律给到 `文件名:行号`）／**C**＝按已知比例外推／**D**＝零读数。
> **分工（一个事实只在一处）**：算子支持表正本＝[[iCraft算子支持矩阵]]（CLI 网页那份）与[[icraft.v3.39.0_支持算子表]]（PDF 那份），本页只登记**这两份互斥的那一格**；板上产物与 md5＝[[板端我方代码与产物台账]]；开口清单本体＝[[哪些要跟厂商要]]；多模型并发判定＝[[NPU多模型并发与厂商案例]]；编译链与 `[run]` 参数口径＝[[NPU调用链]]。
> **两件事说在页头**：① 本轮全部实测在**本机 Windows＋Icraft CLI 3.39.0** 完成，**没上板、没在校机编译**；② 结论推翻的三条我方旧记录（`_ZG` 件只能在板上跑／PC 侧验不了 generate 段／快照待定）都改判了，但**推翻它们靠的既是我方自己的读数也是厂商原文**，不是新猜的。
> **2026-10-31 追加轮**：她裁"num-audit 支持带空格文件名＝**要**"与"场景1＝**在校机跑**"。前者已做，工具侧两条结论与由此挖出的**同名双副本**问题在第十二节；后者**没跑成**，卡的是校机入口（第九节第 2 条）。
> **2026-10-31 第二次追加（回她这四句）**："1 是有的"＝**她对，我上一版写错了**，x86_64 Linux 包在 `largefiles/04_ICraft/` 里（TL;DR 第 8 行＋第九节第 2 条的更正与实测）；"反正我本机的 wsl 有装"＝**实测不成立**，WSL 里没 iCraft，她记的那套装在 Windows 侧；"2 要改"＝**AGENTS.md 第四节校机那行已按实测改**（第十节第 6 行记改动与两件剩余）；"两套分别在哪里"＝**两套是两个不同 release**（3.31 的 gitee 个人镜像 clone ／ 3.39 面向 WL170(400TAI) 的 ModelScope 包，名册、来源、落盘时间见第二节那一格，TL;DR 第 9 行）；"4 能在校机跑吗能就跑"＝我当时答**"跑不了"，这句错了**，见下面第三段。

> **2026-10-31 第三次追加（回她"不是找到 deb 了吗／本机 cli 是哪个版本／校机真的没容器吗／你能不能重建"）**：
>
> 1. **我第二遍犯了同一类错，这条先记账**：上一段那句"校机跑不了"的证据面只有 **C 盘与 PATH**，而本仓自己的 [[交叉编译主机路由SOP]] 第一节的表就写着工具链在 `D:\yzd\WCIS\crosswin`。逐条实测（`workenv/gate/schoolcross.txt`）：`aarch64-none-linux-gnu-gcc.exe --version` **RC＝0** 出 `10.3.1 20210621 (arm-10.29)`；MSYS2 的 `usr\bin\bash.exe`／`mingw64\bin\cmake.exe`／`mingw64\bin\ninja.exe` 三个 `Test-Path` 全 True；crosswin 根在（`kit` 948 件／`pyroot` 209／`src` 45／`donor` 10／`logs` 31），产物还在——`build\yolov8n` 6 408 568 B（2026-10-16 06:33）、`build-py` 五件（pybind 134 456／numpy 139 320／capi 10 192／embed 15 944，尺寸与 [[校机交叉编译环境搭建SOP]] 第八节那张 md5 表逐字对得上）；D 盘可用 **1 571.9 GB**。⇒ **交叉编译（板端 aarch64 二进制／cp38 扩展模块）照旧走校机，不需要容器、不需要 WSL、也不需要那颗 deb。**
> 2. **"找到 deb 就能在校机交叉编译"这个前提不成立**，两问两答：① 那颗 `Icraft_3.39.0_amd64.deb` 是"x86_64 **Linux** 上跑的 iCraft CLI"，校机是 Windows，没有 `dpkg`、没有 Linux 运行时可装它；② 更硬的一条**我方早就实测过**——本机 podman 里那枚 `localhost/fpai-ub2004:tts-saved`（Ubuntu 20.04，内含 ICraft 3.39.0、build 号与 Windows 那份同为 `431be90`）跑 `icraft compile config/ZG/Yolov8_int8.toml`，parse／optimize／quantize／adapt 都过，**generate fatal 缺 `libicraft_zhuge_codegen.so`** ⇒ 这份 amd64 包的 codegen 只带布衣，**ZG 档 imodel 只能本机 Windows CLI 出**（判据正本＝[[NPU模型上板出指标SOP]] 第九节坑 4，取证＝[[算子缺口处理]] 第 180–185 行那张两列对照）。⇒ 就算给校机装上 deb，也出不了我方那颗件。
> 3. **本机 CLI＝3.39.0**（她问的那句的直接回答）：`icraft --version` 直读「Icraft 版本: 3.39.0」＋「CLI 版本: 3.39.0.0-431be90(2608211646)」，exe 的 `FileVersion` 3.39.0.0、`CompanyName` Shanghai Fudan Microelectronics Group；`C:\Icraft\CLI` 与 `C:\Icraft\CLI v3.39.0` 两份的 FileVersion／ProductVersion／build 号**完全相同**＝同一颗包装了两次，MACHINE 级 PATH 只挂 `C:\Icraft\CLI\bin`（取证 `workenv/gate/localcraft.txt`／`localcraft2.txt`）。
> 4. **校机确实没容器**（这半句上一版没说错，且找过了不只是 PATH）：`docker version` CommandNotFound、PATH 里 docker／podman／nerdctl／containerd／gcc／cmake／make 全空（`where.exe` 七次"用提供的模式无法找到文件"）、`wsl.exe` 虽在 `C:\Windows\System32\` 但 `wsl --status` RC＝50／`wsl --version` RC＝1 都报未安装、服务表只匹配到 `HvHost`（Stopped／Manual），Program Files 与 Program Files (x86) 里无 Docker／Podman／WSL／Linux／VMware／VirtualBox 类目录，当前用户无 Linux／容器类 Appx 包。
> 5. **"能不能重建"＝校机这台我重建不了**，三条各自独立的硬闸：`whoami /groups` 令牌＝`Medium Mandatory Level`（S-1-16-8192）、组只有 `Users`＋`Remote Desktop Users`，而 `net localgroup administrators` 的成员只有 `Administrator` 与 `SuRongbin` ⇒ `Get-WindowsOptionalFeature -Online` 直接报 "requires elevation"，开不了 WSL／虚拟机平台；`SecondLevelAddressTranslationExtensions`＝**False** ⇒ 宿主没给这台 VM 透传嵌套虚拟化，WSL2 与容器要的那个轻量 Utility VM 起不来（`HypervisorPresent`＝True 只说明它自己跑在 hypervisor 下）；C 盘只剩 **19.5 GB**（对照：deb 919.4 MB 还在 965.3 MB 的 zip 里、解包合计 1 037.2 MB，Windows 那份 CLI 是 4.56 GB）。要在校机开 WSL，只能她给管理员凭据**＋**在宿主那台 EPYC 主机上给这台 VM 打开嵌套虚拟化——后者我从 VM 里面碰不到。
> 6. **真要 Linux x86_64 上的 iCraft，两条入口本来就存在，不用新建**：① 本机 podman——`podman.exe` 在 `C:\Users\takomi\AppData\Local\Programs\Podman\`，`podman machine list` 出 `podman-machine-default`／wsl／8 CPU／2 GiB（记账值）／100 GiB、LAST UP 10 天前，那枚 `fpai-ub2004:tts-saved` 就在里面；本机 WSL 另有 Ubuntu **26.04**（`/` 可用 **943 GB**，但厂商 readme 写的是 20.04、wheel 是 cp38 而它只有 python 3.14）。② 中转机 102（`ssh deb-h61`）——Debian 13、`Linux 6.12.111+deb13-amd64`、`podman=/usr/bin/podman`＋crun 现役、`/` 可用 **102 G**、`https://registry-1.docker.io/v2/` 回 **401**（匿名握手成功＝可达）、`mirrors.aliyun.com` 回 200，`podman images` 现在是空的 ⇒ 起一枚 `ubuntu:20.04` 就是厂商那一档系统。**这两条我一步都没做**（起 machine、拉镜像都算装东西），列在第十节第 5 行等她点头。
> 7. **于是第九节那两条的真实落点也跟着变了**：第 1 条（`thr = 0.001` 重编＋全量评测）＝**本机重编（只能本机，见第 2 点）＋板子跑 5000 张**，按 [[NPU模型上板出指标SOP]] 第八节那条实测口径 369 s／5000 张＝13.5 张/s ⇒ **6.2 分钟／档**，两档 ≈ 12.4 分钟——跟校机一点关系没有；第 2 条（`fake_qf = true` 场景1 的逐层 ftmp 对比）＝Host 后端 `icraft run`，本机已经跑通过（第十一节那三条复现命令就是本机跑的）。⇒ **"校机跑不了"本来就不该用来按住这两条**；按住它们缺的只是"要不要现在开重编、要不要现在占板子 6.2 分钟×2"这一个决定（第十节第 1 行已按此改写）。


> **2026-10-31 第四次追加（她裁"1 开跑，2 开跑"）**：两条都已开跑，记录在第九节之后的"九·补"里——第 2 条出数（补 1：128／185 层逐层对比，rel_rms 最大 2.22%、余弦全部 ≥0.999）；第 1 条本机半出件＋Host 冒烟过（补 2：三颗编译证明确定性，IR 只差 DetPostZG 一处 `data_thr`／`thr_f`，131 个 ftmp 里 128 个逐字节相同），**板端 5000 张全量一张没跑**——`113.txt` 读到 `test==on`，且新件上板要她明说"上"。两套教程的目录与路径已在 TL;DR 第 9 行与第二节。

> **2026-11-01 第五次追加（第 1 条的板端那半补跑完）**：`113.txt` 起手读 `test==off` ⇒ 按约定写 `test==on`、跑完恢复 `off`。新件上板跑满 5000 张，**AP@[.5:.95] = 0.358、AP50 = 0.511**（对照现役 0.331／0.462），与厂商 0.363 的差从 **0.032 收到 0.005**。另有一条顺带查明的硬证据：**板上那颗 0.331 基线件与我们 10-31 编的 ctrl 件 md5 完全相同**（json `c4cc09fc…`／raw `09f59e39…`）⇒ 两档之间只差门限，不是"不同的网络在比"。过程与边界见补 2 末尾新增的「板端」小节，板上件登记在 [[板端我方代码与产物台账]] 廿七。

## 一、TL;DR

| # | 原来记的 | 现在判 | 证据 |
|---|---|---|---|
| 1 | `哪些要跟厂商要.md:17`／`:109`（原口径"PC 侧只能核到 adapted/quantized，`_ZG` 件必须上板才知道"——这两行现在写的就是本条改判注，原句已被覆盖） | **改判（作废）**：`_ZG` 件本机 Host 后端直接跑通，还能逐层出 ftmp；从 adapted 到 generate 那段**不再是黑盒** | A（本机自跑）＋B（BY 官方仿真工程出厂就是 `stage: g`＋`run_backend: host`） |
| 2 | `板端我方代码与产物台账.md:197`：出指标那轮 `thr_f=0.1` 一律未动 | **口径缺一半**：厂商要求测精度时编译 toml 与评测 yaml **两处都改 0.001** ⇒ 0.331 是"0.1 门限档"读数，**不能与厂商 0.363 相减** | B（`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:708-709`＋官方 BY demo 出厂即 0.001） |
| 3 | 官方 demo 自带的 imodel 可以拿来当输入件 | **不能跨版本**：demo 那颗是 v3.33.1 件，3.39.0 runtime 直接拒（`swap_mode` 由 `null` 变 boolean）⇒ **demo 的件只读不跑，要跑得自己重编** | A（本机 `icraft run` 日志 `[fatal] 26003`） |
| 4 | 快照（`--save_snapshot`）能不能省掉板上 132 s 的 `apply`＝要问厂商 | **就地关闭**：官方写明快照**只支持 BY 阶段的网络**，ZG 档用不了 ⇒ 这条不是"待确认"，是"此路不通" | B（`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 2_2 icraft tools.md:398`） |
| 5 | 单设备多 Session／多路并发＝要问厂商 | **半关闭**：厂商参考实现口径已经是"单核阻塞 NPU ＋ 一个有序调度器，不许开互相竞争的 forward 线程"，ZG 通常 2 路 | B（`profile-30tai.md`＋`README.md` 支持矩阵） |
| 6 | 两份 3.39.0 官方算子表一直并存、没对齐 | **新增冲突**：`LogSoftmax` 一格，PDF 写 ZG `×`（Host 回退）、CLI 网页写 `√`。除此之外两份不矛盾，只是粒度不同 | A（两份一手件本次都直读复验） |
| 7 | "里头有个 skill 教怎么编译模型" | **说法要拆**：10 个 SKILL.md **没有一个教 `icraft compile`**；9 个 `fpai-ref-design-*` 已装可用，1 个 `fpai-integrate-model-icraft336` 被自己的适用条件排除 | A（本次跑通其脚本）＋B（各 SKILL.md 正文） |
| 8 | 我上一版写的"本仓没有 x86_64 Linux 版 iCraft CLI"（第九节第 2 条） | **公开更正：有**。`largefiles/04_ICraft/v3.39/icraft_v3.39.0/30TAI&100TAI.zip` 里 `Icraft_3.39.0_amd64.deb` 919.4 MB，厂商 readme 写明"Ubuntu20.04-amd64／在amd64上交叉编译arm64需要此安装包"；3.36.1 同形态散件也在盘上。⇒ "校机跑不了"的原因只剩"那台是 Windows 子机、没装 iCraft 也没装 WSL"，不是"仓里没入口" | A（zip 36 条目逐条大小＋ar/control 流式解析）＋A（本机 WSL 与校机 VM 两侧 RC 实测）；错因与门禁覆盖面见第十二节 |
| 9 | 我上一版写的"两套教程来源与 release 盘上无从考证" | **考证出来了**：A＝`wiki/PL/MOD/modrt/tutorial-runtime/docs/` 是 **3.31**（带 `.git` 的 gitee 个人镜像 `mxh-spiger/tutorial-runtime`，分支 `tt3.31.0`，10-29 04:50 落盘，唯一含 ZG/30TAI 那条线）；B＝`repos/official/tutorial/icraft_tutorial/WL/` 是 **3.39 且只面向 WL170(400TAI)**（ModelScope `AIBS/icraft_tutorial` v3.39.0，10-30 14:06 落盘，12 件＝10 `.md`＋2 PDF）⇒ 那 3 条裸名（10-18 写下）行号对上的是 **B 那一版** | A（`git remote -v`／`git blame`／目录创建时间／逐句字节比对，脚本都在 `workenv/gate/`） |
| 10 | "厂商要求测精度时两处都改 `thr = 0.001`"（本表第 2 行的依据句） | **适用范围出现版本差，待裁**：3.31 那份无条件，3.39-WL 那同样两句都加了"（BUYI 场景）"，且同文件写"WL170 无 DetPost"。我方那颗是 `_ZG`＋`customop/DetPost` ⇒ 第 2 行的改判**要不要维持**取决于读法，收法见第十节第 8 行（两档各重编各评测，别赌适用性） | B（两份一手件逐字节比对，相似度 0.935／0.928） |
| 11 | 我上一版那句"第 1／2 两条**校机跑不了**所以没开跑"（第九节，也是当时按住这两条的唯一理由） | **公开更正：这句站错了地方。** 校机的交叉编译环境整套在 **D 盘**且本轮实跑通（`aarch64-none-linux-gnu-gcc.exe --version` RC＝0 出 10.3.1，`D:\yzd\WCIS\crosswin` 的 `kit`／`pyroot`／`build\yolov8n` 都在），我上一版只查了 C 盘与 PATH；但这两条本来也不归校机——**重编只能本机 Windows CLI**（Linux amd64 那份的 codegen 只带布衣，ZG 档 `icraft-generate` fatal 缺 `libicraft_zhuge_codegen.so`），**5000 张全量在板上**（实测口径 369 s／5000 张＝13.5 张/s ⇒ 6.2 分钟／档），场景1 的 ftmp 对比是 Host 后端、本机已跑通。⇒ 缺的只是"开不开跑"这个决定，不是主机 | A（`workenv/gate/schoolcross.txt` 逐条 RC 与件数；坑 4 一手取证＝[[算子缺口处理]] 第 180–185 行两列对照） |

## 二、这批素材里到底有什么

| 位置 | 实况（清点于 2026-10-30） |
|---|---|
| `repos/official/` 顶层 | 5 个目录＋1 份笔记：`benchmark/`、`demo/`、`fpai_reference_design/`、`tutorial/`、`Nuscenes_v1.0-mini_subset/` |
| `tutorial/` | 7 个仓库：`demo_for_icraft_by`、`demo_for_icraft_wl`、`icraft_tutorial`、`runtime_demo_for_icraft_zg_cpp`、`runtime_demo_for_icraft_zg_py`、`tutorial-model_export`、`yolov5_demo_for_icraft_zg` |
| `demo/` | 3 个：`03_图像分类部署示例工程 image_cls_resnet18`、`Icraft-ModelZoo-yolov5`、`llm_frontend_cpp` |
| `fpai_reference_design/examples/` | 4 大类（`0_datapath`／`1_single_input+ai`／`2_pcie_hostin+ai`／`3_multi_inputs`）下 16 个示例工程目录 |
| SKILL.md | 共 10 份（`find repos/official -name SKILL.md` 直数）＝`.agents/skills/` 9 份＋`skills/fpai-integrate-model-icraft336` 1 份 |
| **两套教程正文＝两个不同 release**（本轮定案，上一版只数到"不同"没数到"哪个版"） | **A＝`wiki/PL/MOD/modrt/tutorial-runtime/docs/`，iCraft 3.31 教程**：15 件全 `.md`；它是个**带 `.git` 的嵌套 clone**（`git -C <该目录> remote -v`＝`https://gitee.com/mxh-spiger/tutorial-runtime.git`，分支 `tt3.31.0`，HEAD `d36fa96`＝2025-12-09「docs: 📝更新下载站链接」），盘上落的时间是 **2026-10-29 04:50**；`wiki/PL/MOD/modrt/tutorial-runtime/readme.md:1` 自证"# tutorial 3.31 使用教程"。**ZG/30TAI 那条线只有它有**（独有 `Part 1_5 ZG Usage.md`）。**B＝`repos/official/tutorial/icraft_tutorial/WL/`，iCraft 3.39、面向 WL170(400TAI)**：目录内 **12 件＝10 件 `.md` ＋ 2 份 PDF**（`400TAI Runtime API Manual(Icraft v3.39).pdf` 2 389 kB／`Icraft_v3.39.0_支持算子列表.pdf` 131 kB）——上一版记的"10 件"只数了 `.md`；不是 git 仓库、厂商包直接落盘（**2026-10-30 14:06**），父级 `repos/official/tutorial/icraft_tutorial/README.md:1` 自证"# tutorial 3.39 使用教程（WL170 / 400TAI）"，同文件第 7 行指向 ModelScope `AIBS/icraft_tutorial` 的 `v3.39.0/WL`；另有 `repos/official/tutorial/icraft_tutorial/configuration.json`（`{"framework":"Pytorch","task":"other"}`）。**两份 6 件同名、0 件字节相同**（4 件 A 更长 ＋11／＋109／＋145／＋351 行，2 件 B 更长 64／72 行），章节号错位：A 另有 `Part 1_2 Icraft迁移手册.md`／`Part 5 fpga-op.md`／`Part 6 Self-Troubleshooting.md`／`Part 7 FAQ.md`，B 另有 `Part 1_2 Icraft Terminology.md`／`Part 5 Self-Troubleshooting.md`／`Part 6 FAQ.md`／`readme.md`。**本轮逐句比对补上一条要紧的**：本页引的那几句话里 **3 句在两份里逐字节相同**（快照／场景1／`fake_qf` 仅 HostBackend），只有 `thr` 那两句 **3.39 多了"（BUYI 场景）"限定** ⇒ 裸名引用会把**行号**指到另一版，文字层面本轮引的只有 `thr` 那一条受版本差影响（对照与相似度读数在 `workenv/gate/sentcmp.txt`，`thr` 那条的后果记在第九节第 1 条）。B 那份 `Part 0 env_setup.md` 还有 **2 处 `../BUYI/` 相对路径指向同仓的 `BUYI/` 目录、而盘上没有那一份**（顶层只有 `WL/`）⇒ 这套教程我们只拿到 WL 半套。引用侧的后果与"哪份是正本"见第十二节最后两条与第十节第 7 行。**这两个目录在各自子库里都既没被跟踪、也没被 `.gitignore` 忽略**（`git ls-files` 空、`git status` 是 `??`、`git check-ignore` RC＝1）⇒ 一次 `git add -A` 会把它们整片扫进提交；而 A 那份自带 `.git`，加进去会写成 **gitlink（mode 160000）但 wiki 库没有 `.gitmodules`**（实测 `wiki/.gitmodules` 不存在）——那是个指不回任何提交的坏指针，正对着第七节防 `git add -A` 那条。逐件行数／md5 见 `workenv/gate/dupcmp.txt`，名册与时间戳见 `workenv/gate/twosets.py`／`mtimes.txt`。 |

**新东西只有三样**，其余跟我方已 vendored 的重叠：

1. `icraft_tutorial` 那份**不是**更全的教程——它只有 `WL/`（卧龙/400TAI）一条线，**没有** `Part 1_5 ZG Usage`；我方 `wiki/PL/MOD/modrt/tutorial-runtime/docs/` 那 15 页反而含 ZG 专章。这件事 [[算子表00_说明]] 第 2 节早就写过了，本次是复验。
2. `tutorial-model_export`（mmlab／detectron2／timm／paddle 四套**框架侧导出**案例）是真正的新资产——我方编译链输入侧只见过 `.onnx` 与 TorchScript `.pt` 两个口（`状态源与决策记录.md:681` 那条 B 级负断言的依据就是这个），导出改图的手法以前没有系统资料。
3. `benchmark/.../Icraft_Icore_Metrics_V3.7.1.xlsx` 给了**厂商报性能时用的列格式**（`Ocmopt`／`No_mergeops`／`total_time`／`hard_time`／`delta_time`／`Quantization`／`Dataset`），我方对外报数要么对齐这套列，要么自己那套写清口径。

## 三、改判 1：`_ZG` 件在 PC 上就能跑（本轮最值钱的一条）

### 3.1 我方实测（A）

同一颗 yolov8n ZG int8 件（640×640，输入格 `In: — / Out: (0|1,640,640,3)`），本机 `icraft run` 逐档跑，`backends = "Host"`。下表 `total_time` 全是**实测**，逐条对应落盘日志（`workenv/zghostsim/`）：`parsed`＝`run_v8n_parsed.log`、`adapted`＝`run_v8n_adapted.log`、`_ZG`＝`run_v8n_host.log`、dump 档＝`run_v8n_dump.log`：

| 加载的档位 | 件（json／raw B） | `total_time` | `[fatal]` 命中 |
|---|---|---|---|
| `parsed`（float） | 142,868／12,609,128 | 589.564 ms | 0 |
| `adapted` | 342,186／3,334,445 | 1443.802 ms | 0 |
| **`_ZG`（generate 段）** | 304,217／4,722,587 | 2593.433 ms | 0 |
| `_ZG` ＋ `dump_format="SFB"` | 同上 | 见 3.3 的坑 | 0 |

三档件件跑通，**`DetPostZG` 这颗 customop 也有 Host 转发**（`opId: 486 opType: DetPostZG wall: 269.861 ms`）——这条以前我方是当作"板上有、PC 上没有"来用法的。
逐层特征图导出：**131 个 `<opId>.ftmp`**（`workenv/zghostsim/logs_dump/Yolov8n/ftmpSFB/`），这就是分层对数的 golden，以前以为只有板子上才拿得到。
耗时比：`2593.433 / 589.564 = 4.40`，即 ZG int8 件在 CPU 上比 float 件慢 4.4 倍——**这是 CPU 上跑定点模拟的代价，不是板上性能**，不许拿去当 12.4 ms 那档的对照。

### 3.2 厂商原文（B）

- `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 1_5 ZG Usage.md:350`：「仿真工程适用于加载icraft编译出来的各阶段网络（**p/o/q/a/g**），获得各阶段的仿真结果」；同文件 `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 1_5 ZG Usage.md:293-299` 写全了 `stage`（p/o/q/a/g）、`run_backend`（zg330/buyi/**host**，「仿真则配置为host」）与「如果为仿真则该 ip 无效」。
- 官方 **BY** 教程的 C++ 仿真工程出厂配置就是这一档：`demo_for_icraft_by/Example3_quick_start_C++/cfg/yolov5s.yaml:13` `stage: g`、`:15` `run_backend: host`（`:16` 把 `# run_backend: buyi` 注释掉留着切换）。
- 官方 **ZG** 部署工程相反：`yolov5_demo_for_icraft_zg/deploy/cfg/yolov5s_psin.yaml:8-9` 是 `stage: g` ＋ `runbackend: zg330`。**注意键名两边不一样**（BY＝`run_backend`，ZG 部署件＝`runbackend`，少一个下划线），照抄另一份的 yaml 会静默不生效。

⇒ 结论：`_ZG` 件 PC 可仿真是**厂商文档与出厂配置双重支持的常规用法**，我方把"上板才能验 generate 段"记成事实，是自己没照着做。

### 3.3 三条边界，别把这条改判用过头

1. **Host 后端不校验输入张量字节宽度**（`哪些要跟厂商要.md:81` 已吃过教训：同一份 8 B 输入 Host 一声不响，ZG 后端 `hardop.cpp:46` 直接打回）。所以 Host 上跑 `_ZG` 只覆盖**数值**，不覆盖**硬件契约**——`host_chunk byte_size` 那类只有板子拦得住。
2. `dump_format="SFB"` 那轮 `total_time` 打印成 `0.007 ms`，而逐 op 的 `wall` 是真读数。**求和行在这种开关组合下不可信（B：现象复现，机制未归因）**，计时一律以不带 dump 的那轮为准。
3. 官方 `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 2_2 icraft tools.md:204` 写明 `fake_qf` **仅对 HostBackend 有效**；`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 2_2 icraft tools.md:398` 写明**快照目前只支持 BY 阶段的网络**——所以"PC 上快速复现 ZG 会话、省掉 132 s `apply`"这条捷径**没有**，逐层 ftmp 有、快照没有。

## 四、改判 2：精度那一刀砍在 thr 口径上

厂商的测精度规程是两处门限都要 0.001：

- `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:708`「如果用了customop/Detpost，请检查**模型编译时** `config/customop/toml` 中 thr 是否设置为 **0.001**」
- 同文件 `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:709`「请检查**精度测试时** `cfg/test.yaml` 中 thr 是否设置为 **0.001**」

官方仓库里这两档的出厂实况：

| 件 | 出厂值 | 出处 |
|---|---|---|
| BY 教程 customop toml | **`thr_f = 0.001`** | `demo_for_icraft_by/compile/config/customop/yolov5.toml:10`、`yolov5_plin.toml:11` |
| ZG 教程 customop toml | `thr_f = 0.1` | `yolov5_demo_for_icraft_zg/compile/config/customop/yolov5.toml:4` |
| 参考实现里的 ModelZoo 克隆 | `thr_f = 0.1` | `examples/3_multi_inputs/MultiPSin+MultiNets+Save2File/model_compile/yolov5_7.0/yolov5_7.0_icraft/2_compile/config/customop/yolov5.toml:9` |
| 我方出指标那轮 | `thr_f = 0.1`（编译期，烧进图）＋ `conf: 0.1`（运行期） | `板端我方代码与产物台账.md:197`、`:153`（#51 逐字抄厂商 `yolov8_ZG_int8_demo.yaml`） |

⇒ **判**：官方"演示档"（ZG demo）就是 0.1，官方"要数字档"（BY 教程、Part 4 规程）是 0.001。我方那轮 0.331 **两处都是 0.1**，按厂商口径它是"0.1 门限档的 AP"，**不能与厂商 0.363 直接相减**——那条减法以前只被当作"参照系不同"（`状态源与决策记录.md:490` 的 D-32 不触发判定是对的），现在多一条更硬的理由：门限档位不同。

厂商自己的 int8／float 基准就在同一张表里（`benchmark/benchmark/icraft3.7.1/Icraft_Icore_Metrics_V3.7.1.xlsx`·`cv-det`，yolov8_n、输入 `1*3*640*640`、`kld-pc`、`coco2017val`）：

| 档 | `mAP50-95` | `mAP50` | 量化损失（mAP） |
|---|---|---|---|
| float／parsed | 0.373 | 0.530 | — |
| int8 | 0.363 | 0.518 | 0.373 − 0.363 ＝ **0.010** |
| 16bit | 0.368 | 0.524 | 0.373 − 0.368 ＝ **0.005** |
| mix | 0.364 | 0.518 | 0.373 − 0.364 ＝ **0.009** |

⇒ 厂商口径下这颗模型的量化损失是 **0.010 这个量级**；我方 0.032（0.363 − 0.331）的差额里混着**芯片（BY 100TAI vs ZG 30TAI）、icraft 版本（3.7.1 vs 3.39.0）、校准集（官方 9 张）与门限档（0.1 vs 0.001）**四个变量，一个都没对齐。[[板卡镜像实测取证]] 第十八节那轮的"精度下降"格**继续留空**，留空的理由从"float 基线未测"改成"float 基线未测**＋门限档未对齐**"。

## 五、改判 3：demo 自带的 imodel 跨不过版本

官方 ZG 教程随仓带了真件（不是 LFS 指针）：`yolov5_demo_for_icraft_zg/compile/imodel/yolov5s/yolov5s_ZG.json`（301.0 KB）＋ `.raw`（9.4 MB），件头 `ai_target:"@zhuget(330)"`、`icraft_version:"v3.33.1"`、`params_md5:"659816a2f2ff8c4b4baf3d72af8bdb22"`。

本机拿 3.39.0 的 `icraft run --backends Host` 加载它：**当场失败，日志 `[fatal] 26003` ＋ `SetAnsiMode failed ... 执行以下命令时捕获到错误码26003`**，栈顶是
`Unable to read key "swap_mode" from json{... "swap_mode":null ...}` ＋ `type must be boolean, but is null`。
同一颗件用 skill 自带的 `inspect_model_artifacts.py` 验，**`ok=true`**（`params_md5` 与 RAW 实算 md5 一致）。

⇒ 两条一起读：**完整性检查通不过的版本不兼容，是这个脚本抓不到的**。所以：
1. 官方 demo 的 `_ZG` 件**只能当参考实现读，不能当输入件跑**；要用就照它的 toml 自己重编（`yolov5s_ZG.toml` 与 `runtime_demo_for_icraft_zg_py` 都在）。
2. 我方 [[板端我方代码与产物台账]] 的"版本"列继续填**实际用于编译的 tag**（这条规矩本身在 `任务卡与台账规范.md:113`），跨版本引用任何件都要带"件内 `icraft_version` ≠ runtime 版本"的警示。

## 六、四条厂商开口项就地关闭

| 开口项 | 现在的处理 | 出处 |
|---|---|---|
| #6 全套（`_ZG` 件数值基准／前向模拟器） | **前提作废、范围缩到两问**：①③ 两问（PC 能不能验、`precheck` 口径）我方已自答；留下 **② Qwen 板端逐层基准**（改图要对照物）与 **④ 手工往 IR 加算子的正规做法**（`@zhuget(330)` 标签） | `哪些要跟厂商要.md:105-115` |
| #3④（快照能不能省掉 `apply`） | **撤**：快照只支持 BY，ZG 无此路 | `wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 2_2 icraft tools.md:398` |
| #5①（`ocm_option`／`speedmode`／`compressFtmp` 是什么） | **撤语义之问，留取值之问**：三者定义厂商写全了（`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 1_5 ZG Usage.md:293-295`：算子合并加速／etm 内存优化／0-不优化、1~3 三种方案、4 遍历全部）。**但 `-1` 不在文档取值集内**，而官方 ZG 部署件出厂就是 `ocm_option: -1`（`yolov5s_psin.yaml:6`），我方 #51 也照抄了它 ⇒ 剩下的问题只有一个：`-1` 到底等于哪一档 | `哪些要跟厂商要.md:94` |
| #7 的 PS↔PL 对齐那一半 | **有官方口径可先按它做**：相机／显示／PS-DMA 的 chunk 用 **128 B** 对齐，ETM／权重／FTMP 等页级分配用 **4096 B**；`SLOT_NUM` 是缓冲深度、不是相机数。位流与 PL 工程本体仍然照旧要 | `profile-30tai.md` 的 Physical topology and memory 一节 |
| #8②（单设备多 Session） | **半关闭**：厂商参考实现的口径是"单核阻塞 NPU ＋ 一个有序调度器，不要开互相竞争的 forward 线程来假装并行"；支持矩阵原文"一个 NPU scheduler 调度，BY 通常 4 路、ZG 通常 2 路" | `profile-30tai.md`＋`fpai_reference_design/README.md` |

多模型那条的判定与三本账不在本页展开，见 [[NPU多模型并发与厂商案例]]。

## 七、skill 判定：能不能拿来直接用

### 7.1 分簇结论

| 簇 | 位置 | 判定 |
|---|---|---|
| 9 份 `fpai-ref-design-*`（integrate-model／prepare-model／integrate-psin／integrate-plin／optimize-runtime／board-debug／debug-customop／validate-datapath／package-delivery） | `fpai_reference_design/.agents/skills/` | **能用，且已经装进会话**（九条都在本会话可用技能清单里）。路由也对：本 checkout 的示例是 `FunctionalActor`（21 个文件命中）＋`BaseActor` **0 命中**，`profile-30tai.md` 把我们这颗板定成 `30tai`＝ZG/Zhuge/`-DTARGET_CHIP=ZG`/`USE_ZG330_BACKEND` |
| 1 份 `fpai-integrate-model-icraft336` | `fpai_reference_design/skills/` | **不能用，且是它自己排除的**：SKILL.md「Confirm scope」第 2 步要求所选示例仍用 `BaseActor`/`BufferManager`，本 checkout 零命中 ⇒ 第 3 步 stop 规则触发（"If the example has migrated to a different released Pipeline API, stop"）。它是上一代分支的遗留 |

**没有一个 skill 教编译。** `prepare-model` 干的是"把已编译的 bundle 冻成契约"，还明令**禁止**为了让旧 bundle 可读而重写 TOML（`prepare-model/references/model-contract.md:15-16`）。真正的编译规程在教程正文（`Part 2_1 compile.md`、`Part 1_5 ZG Usage.md`），这两页我方已有。

### 7.2 脚本实测可用，但验收口径要自己补

`inspect_model_artifacts.py` 跑我方那颗 `_ZG`：`RC=0`、`ok=true`、`target_check` 匹配 ZG、`operation_count 122`、json md5 `c4cc09fcb5e7c35267f716f7f2d6f34c`／raw md5 `09f59e39596e0caa338a762dbce0102a`——**与台账 #49/#50 逐字相同**，等于用厂商脚本把我方的哈希复核了一遍。

但它的 `ok` 只等于"JSON 能读 ＋ RAW 非空非 LFS ＋ target 匹配"（脚本 206-229 行，`return 0 if report["ok"] else 2` 在 235 行），**SKILL.md 声称要拒的"JSON 声明的 size/hash 不匹配"根本没实现**——`collect_digest_fields` 只把件里的 `params_md5` 列出来，从不与实算值比对。第五节那颗 3.33.1 件被判 `ok=true` 而 runtime 加载失败，就是这个缺口的实证。**⇒ 脚本当清点与哈希登记工具用，判定权留在我们自己手里。**

### 7.3 真闸门是版本，不是 skill 内容

两条 skill 线都钉在 **Icraft 3.36.1 functional 线**，我方 CLI 是 **3.39.0**。它自己的 `version-routing.md` 规定：Network 检查／切分 API、Session 与 MemChunk 语义、硬算子 wait/poll、图合并与 ETM/FTMP 编译开关、日志与 profiling 开销、Release 编译档、位流与 CustomOp 兼容性——**任一项变了就要拿冻结基线重做工件与契约评审**。第五节那条 `swap_mode` 就是这项的实证。⇒ 用这套 skill 的前提是先做一次 3.36.1↔3.39.0 的能力对照表，不是直接照它的步骤走。

### 7.4 顺手捡到的官方运行时约定（`llm_frontend_cpp`，B）

`demo/llm_frontend_cpp/src/runner/qwen7b_wl170_runner.cpp` 把 LLM 上板的几条约定写成了代码，与我方独立摸出来的一致，可以当"官方也这么做"的背书：三元素 fp32 `dynamic_fm`（`:159` prefill＝`{prompt_length, 0, 0}`、`:224` decode＝`{position, 1, 0}`）；输入张量**另建** `TensorType(FP32, shape, Layout("*C"))` 而**不复用图里的 TensorType**（`:177-183`，理由写在注释里：图类型带 `@chunk` 内存型，会把普通 Host 张量当用户 chunk）；`forward(inputs)` **不显式传 outputs**（`:197`，注释说传了会超时）；输出逐个 `waitForReady(60s)`（`:199`）后 `device->reset(1)`（`:216`）；prefill 与 decode 两个 Session 共用一次 `openDevice`（`:128-129`）；LLM 侧 `disableOcmOptimize()`＋`enableTimeProfile(false)`（`:122-123`）；用裸 `WL170Device` 而非 `getICluster(0)`（`:111-115`，注释：后者会让 1K prefill 在 `check_op` 里忙等、`layerCount` 不动）。
⚠ 同目录 `config/qwen2_0.5b.json` 里的 `"run_backend": "host"` **不能引用**成"厂商也在 Host 上跑 ZG 的 LLM 件"——`src/model/model_spec.h` 全文 46 行里没有 `run_backend`／`backend_type`／`dtype`／`ip` 任何一个字段，`src/` 下这两个键名零命中，那是份从没被解析过的遗留配置。

> **代码侧补充（2026-11-02）**：该仓的完整工程解读（来源与取证边界、代码地图与 LOC、128/512/1K 三档配置、四项能力、自述读数与局限、**三处代码与自述不一致**、取证命令）见 `[[纯C++Qwen2.5-7B推理服务]]`。那三条更正以该页 §7 为准：① 设备选择上本仓 `AGENTS.md:26` 的说法与 `qwen7b_wl170_runner.cpp:111-125` **相反**；② tools 定义是**无条件清空**（`model_service.cpp:130`），不是"体积大才丢"或"`<512` 才丢"；③ `max_tokens ≥ 256` 硬写在 `openai_server.cpp:223`，**只作用于 HTTP 路径**。本节 7 条运行时约定的正本仍是上文，不复制。

## 八、两份 3.39.0 算子正本对齐：117 vs 90，真冲突只有一格

我方现在并存两份**同为 v3.39.0 的官方算子支持表**，来源不同、一直没对齐过：

| 正本 | 来源 | 粒度 | 行／名数 |
|---|---|---|---|
| [[iCraft算子支持矩阵]] 第四节 | CLI 网页 `C:\Icraft\CLI v3.39.0\docs\ops\framework.html` 的表2 | 一行一个**框架入口** | 90 行；去重后 61 个算子名，其中 `小粒度算子集合` 是桶标签不是算子 ⇒ **有效 60** |
| [[icraft.v3.39.0_支持算子表]] | 官方 PDF `Icraft_v3.39.0_支持算子列表.pdf`（11 页，含 ZG330/340、ZG30S、BY 三列） | 一行一个 **XIR 算子** | **117**（含 `HardOp`/`Unknown`/`Unsupport` 三个内部／标记行，有效 114） |

键名归一后：**交集 60｜只在 PDF 57（算式：117 − 60 ＝ 57）｜只在 CLI 0**（61 − 桶标签 1 ＝ 60 全部落在 PDF 里）。
⇒ **结构关系清楚了：CLI 网页表是 PDF 表在"框架入口"层上的子集投影，PDF 才是全集**。以前把两份当"谁新谁旧"来犹豫是没有必要的。

冲突分三档，只有第一档是真矛盾：

| 档 | 处数 | 说明 |
|---|---|---|
| **ZG 列真冲突** | **1** | `LogSoftmax`：PDF 写 `×`（备注原文「Host 回退」），CLI 网页写 `√` |
| 只有 BY 列冲突 | 10 | `Argmax`／`BatchNorm3d`／`ChannelShuffle`／`Einsum`／`InstanceNorm3d`／`PixelShuffle`／`Squeeze`／`Stack`／`Sum`／`Unstack`：两份 ZG 都是 `√`，BY 一边 `√` 一边 `×` ⇒ 非本板，只登记 |
| 粒度差（不是矛盾） | 21 行／13 个（算子,列）对 | PDF 在同一格只写 `√`，CLI 网页把限制条件写全（如 `Conv2d`「padding_mode != zeros 的其他 pad 形式不支持」、`Pad`「不支持四维五维以外的输入；不支持对 N、C 维 pad」）。ZG 列 11 个、BY 列 2 个 ⇒ **限制条件仍以 CLI 网页那份为准**，[[iCraft算子支持矩阵]] 第二节的"以 6 列为准"结论不变 |

`LogSoftmax` 这一格本次**两份一手件都重新直读复验**：PDF 第 3 页第 57 行 `LogSoftmax | LogSoftmax | log_softmax | × | × | Host 回退`、第 9 页 BY 表同行 `×`；CLI `framework.html` 的表1／表2 两处 `LogSoftmax` 格都是 `√ √`（我方 [[iCraft算子支持矩阵]] 第四节 `LogSoftmax` 那行抄的正是后者）。

**现役影响＝零（B 级推断，不是穷举实证）**。能拿出的两条：① 本轮改判之后 `wiki/` 全库检索 `LogSoftmax|log_softmax` 命中 **10 处／4 页**（4＋4＋1＋1＝10：本页 4、[[iCraft算子支持矩阵]] 4、[[算子表00_说明]] 1、[[README|README]] 目录行 1），**除那张表的自身一格外，没有任何一页把 `LogSoftmax` 当"我方某颗模型用过的算子"写进结论**；② 巡检报告里我方 `Yolov8n_ZG` 的 **Host/IO 侧算子清单**（`io_process_ops` 3＋`host_ops` 2＋`detpost_ops` 1）中 `Softmax` 命中 **0**。**没做的那步要说清**：全图 122 个算子的逐条名册没穷举过（`repos/official` 全仓检索一次 20 s 超时），所以"yolov5s／Qwen 链路也都没用到"是推断。但它是"两份官方正本互相矛盾"的**唯一实证**，所以：判某算子支持性时，**先 precheck、再按名核对两份，两份不一致就记成开口项**——这条比"信哪一份"更重要，已并进 [[iCraft算子支持矩阵]] 第一节·补。

## 九、下一步（按收益排序，本轮一条都没开跑）

1. **`thr_f = 0.001` ＋ `conf: 0.001` 重编重测一轮 yolov8n ZG int8**——这才让 0.331 与 0.363 落在同一门限档上可比；代价＝一次重编＋一次全量评测（板上 5000 张那一轮的历史耗时是端到端 73.8 ms/张）。
   **2026-10-31 她的裁法是"4 能在校机跑吗能就跑"，我上一版答"校机跑不了⇒ 没开跑"——那句已作废（见 TL;DR 第 11 行）**：这一条**根本不归校机**。重编只能在本机 Windows CLI 做（Linux amd64 那份的 codegen 只带布衣，ZG 档 `icraft-generate` fatal 缺 `libicraft_zhuge_codegen.so`，一手取证＝[[算子缺口处理]] 第 180–185 行、判据正本＝[[NPU模型上板出指标SOP]] 第九节坑 4），5000 张那一半在板上跑；校机在这条链路里的角色只是**出板端 aarch64 二进制**，而那套环境实测还在（`workenv/gate/schoolcross.txt`：`D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-gcc.exe --version` RC＝0 出 `10.3.1 20210621 (arm-10.29)`，`D:\yzd\WCIS\crosswin` 的 `kit` 948 件／`pyroot` 209 件／产物 `build\yolov8n` 6 408 568 B 都在，D 盘可用 1 571.9 GB）。⇒ 真正没开跑的原因＝缺"要不要现在开重编、要不要现在占板子"这个决定（第十节第 1 行与第 8 行）。同一天还查出一件影响这条前提的事：**厂商两版教程对同一句话的适用范围写法不一样**——
   - 我方一直在引的 3.31 那份：`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:708-709` 是无条件句「如果用了customop/Detpost，请检查模型编译时config/customop/toml中thr是否设置为0.001」；
   - 本次落库的 3.39-WL 那份：`repos/official/tutorial/icraft_tutorial/WL/Part 4 性能分析及优化.md:562-563` 同样两句都加了限定「（BUYI 场景）」，且同文件第 568 行补了「WL170 无 DetPost，直接按网络输出 Value 的 dtype/layout 读取并反量化即可」。3.39-WL 那份 `repos/official/tutorial/icraft_tutorial/WL/Part 1_2 Icraft Terminology.md:11` 定义「布衣(BY)架构为100TAI产品对应的NPU架构」，`BuyiBackend` 即那一侧的后端。
   ⇒ 两种读法：① 加限定只是因为 **400TAI(WL170) 没有 DetPost**，这条对"用了 DetPost 的场景"仍然成立，我方那颗是 `_ZG`＋`customop/DetPost`，落在覆盖的一侧（**这样 TL;DR 第 2 行的改判不动**）；② 厂商在 3.39 把这条正式绑到 BY 侧 ⇒ 我方 ZG 档该不该用 0.001 **没有一手依据**，"0.331 与 0.363 不可比"这条改判的依据弱一档。**盘上没有第三份能仲裁**：遍历 `repos/official` 全部 `.md`，带这句话的只有 WL 那一份（3.39 的 ZG/30TAI 教程线根本没落库），3.31 那份也不是 3.39。⇒ 省事的收法是**别先赌适用性**：真要跑就在同一批里把 `thr=0.001` 与现役 `thr=0.1` 各重编一颗、各跑一遍全量评测，两档数一起落账。板时代价有算式：5000 张 × 73.8 ms/张 ＝ 369 000 ms ≈ **6.2 分钟**／档，两档 ≈ 12.4 分钟；两次重编都在 PC 上、不占板子。这条列在第十节第 8 行等她定。
2. **`fake_qf = true` 的场景1 对比**（`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:698`：以 adapted 为 golden 验 generate 是否正确）——现在 PC 上有 131 个 ftmp 可比，这一刀**不需要板子、不需要新件**，是我方第一次能给 generate 段立数值回归的机会。
   **2026-10-31 她裁定"在校机跑"，当天核实＝校机跑不了；但本页上一版给的理由是错的，本轮公开更正。更正之后还有第三次更正（见本节末"更正 3"）：'校机跑不了'这三个字用错了对象——这一条要跑的 `icraft run` 是 Host 后端，本机已经跑通过，根本不需要换主机。**
   - **校机那端（A，逐条 RC）**：三个 ssh 别名（`school-guest`／`school-guest-lan`／`school-guest-pc2`）都落在同一台 **Windows 11 虚拟机**——`hostname`＝`Win11-HV1`、`whoami`＝`win11-hv1\yizhidi`、`Win32_OperatingSystem.Caption`＝`Microsoft Windows 11 专业工作站版`、`Win32_ComputerSystem`＝Microsoft Corporation／Virtual Machine、`Win32_Processor`＝AMD EPYC 9654 96-Core（VM 里分到 **物理核 24／逻辑核 24**）、物理内存 125 GB ⇒ 硬件与 AGENTS.md 第四节那台对得上，但 ssh 进去的是它的**子机、且是 Windows**。这台机上 `where icraft` RC＝1（空）、`if exist C:\Icraft` 判 `NO`、`wsl -l -v` RC＝1（"未安装适用于 Linux 的 Windows 子系统"）——**既没有 iCraft，也没有 WSL**。这四处更正已回写 AGENTS.md 第四节（她当次裁"2 要改"）。
   - **更正 1（我上一版写错的实质结论）**：上一版那句"本仓也**没有 x86_64 Linux 版 CLI**"**是错的**。错因＝只在 `repos/official` 里找（那里确实只有两颗 arm 板端件 `Icraft_3.33.1_onchip.deb`／`CustomOp_3.33.1_onchip.deb`），**没查 `largefiles/`**。x86_64 Linux 包在盘上，一共两版：`largefiles/04_ICraft/v3.39/icraft_v3.39.0/30TAI&100TAI.zip`（965.3 MB／36 条目／解包合计 1037.2 MB）里有 `Icraft_3.39.0_amd64.deb` **919.4 MB**、`CustomOp_3.39.0_amd64.deb` 3.5 MB、`icraft-3.39.0-cp38-none-manylinux2014_x86_64.whl` 2.3 MB、`DecoderDLL/linux-x64-release/lib/x86_64-linux-gnu/` 三颗 `libcustomop.*Decoder.so` 各 18.4 MB（同目录 aarch64 那三颗各 15.4 MB）；3.36.1 那套散件同样齐（`Icraft_3.36.1_amd64.deb` 925.2 MB＋`icraft-3.36.1-cp38-none-manylinux2014_x86_64.whl` 2.4 MB）。以上 MB 都是**字节数 ÷ 1 048 576**。（取证脚本 `workenv/gate/pkgs.py`。）
   - **厂商原话（B）**：`largefiles/04_ICraft/v3.39/icraft_v3.39.0/readme.md:15-21` 三行原文是「#### 30TAI&100TAI/Icraft_3.39.0_amd64.deb（在amd64上交叉编译arm64需要此安装包）」／「Icraft安装包Ubuntu20.04-amd64版」／「安装命令：`sudo dpkg -i Icraft_3.39.0_amd64.deb`」（卸载 `dpkg -r Icraft`）；`.deb` 里的 `control.tar.xz` 解出来是 `Package: Icraft`／`Version: 3.39.0`／`Architecture: amd64`／`Maintainer: FMSH-TX`／`Secion: utils`／`Installed_Size: 20`，**无 `Depends` 字段**（那两个键名还写错了，dpkg 认的是 `Section`／`Installed-Size`）。取证是流式的：`workenv/gate/debcontrol.py` 按 ar 头只取 328 B 的 control 成员，919 MB 的 `data.tar` 一个字节都没读、没落盘。⇒ 这颗包正是"在 x86_64 Linux 上为 arm 板编译"那个入口，zip 名字里的 `30TAI` 就是我方板那一档。
   - **工具侧连带结论**：`num-audit.py` 的 `build_index()` 把 `largefiles` 写进了 `os.walk` 的排除名单，所以"全仓搜不到"这类负断言**门禁工具本来就看不见 `largefiles/`**——我上一版那句错话不会被任何一项检查抓出来。这条记进 [[交付物数字审计num-audit]] 坑 7。
   - **更正 2（她那句"我本机的 wsl 有装"实测不成立）**：`wsl -l -v` RC＝0 只列出 `Ubuntu`（Stopped，v2）与 `podman-machine-default`（Stopped，v2）；进 Ubuntu 内 `uname -m`＝x86_64、`lsb_release -rs`＝26.04、`python3 -V`＝3.14.4、`command -v icraft`→NONE、`dpkg -l | grep -i icraft`→空、`command -v python3.8`→NONE ⇒ **WSL 里没装 iCraft**；她记的那套装在 **Windows** 侧（本机有两份：`C:/Icraft/CLI/bin` 与 `C:/Icraft/CLI v3.39.0/bin`，`where icraft`→`C:\Icraft\CLI\bin\icraft.exe`）。
   - **更正 3（第三次追加，我上一版的"校机跑不了"只查了 C 盘和 PATH）**：`where.exe gcc/cmake/make` 报"用提供的模式无法找到文件"、`C:\` 顶层没有 `msys64`，我就写成了"编译优先在校机只对通用工具链成立"——**而本仓 [[交叉编译主机路由SOP]] 第一节的表明写着工具链在 `D:\yzd\`**。补测（`workenv/gate/schoolcross.txt`）：D 盘存在且可用 **1 571.9 GB**；`D:\yzd\tools\cross\gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu\bin\aarch64-none-linux-gnu-gcc.exe --version` **RC＝0**、`10.3.1 20210621 (arm-10.29)`；`D:\yzd\MSYS2\usr\bin\bash.exe`／`mingw64\bin\cmake.exe`／`mingw64\bin\ninja.exe` 三个 `Test-Path` 全 True；`D:\yzd\WCIS\crosswin` 整套在（`kit` 948 件、`pyroot` 209、`src` 45、`donor` 10、`logs` 31，另有一批 `run-*.sh`／`build*.sh` 脚本正本），产物 `build\yolov8n` **6 408 568 B**（2026-10-16 06:33）、`build-py` 五件（134 456／139 320／10 192／15 944，尺寸与 [[校机交叉编译环境搭建SOP]] 第八节 md5 表一致）。⇒ **校机不能做的只有两件事：跑 iCraft（那要 Windows CLI 或 Linux x86 装包）和跑容器**（非管理员＋SLAT 未透传，见下一句）；**交叉编译照旧走它**。
   - **"能不能在校机重建一个 Linux／容器"＝不能，三条各自独立的硬闸（实测）**：`whoami /groups` 令牌＝`Medium Mandatory Level`（S-1-16-8192）、组只有 `Users`＋`Remote Desktop Users`，`net localgroup administrators` 成员只有 `Administrator`／`SuRongbin` ⇒ `Get-WindowsOptionalFeature -Online` 报 "requires elevation"；`Win32_Processor.SecondLevelAddressTranslationExtensions`＝**False** ⇒ 宿主没给这台 VM 透传嵌套虚拟化，WSL2／容器起不来（`HypervisorPresent`＝True 只表示它自己跑在 hypervisor 下）；C 盘可用只有 **19.5 GB**。真要开，得她给管理员凭据**＋**在宿主那台 EPYC 主机上改这台 VM 的嵌套虚拟化设置，后者我从 VM 里面碰不到。
   - **所以这一条现状**：入口**在盘上就有**（919.4 MB 的 amd64 `.deb`），但装它也不解决这一条——那颗包装在校机上装不了（Windows），装在本机 WSL／102 上又出不了 ZG 档（坑 4）；而这一条要的 `icraft run` **本机 Windows CLI 已经跑通过**（第十一节三条复现命令就是本机）。剩下的两处对不上照旧记着：厂商 readme 写 **Ubuntu 20.04**、本机 WSL 是 **26.04**；wheel 是 **cp38**、WSL 的 python 是 **3.14.4 且没有 python3.8**。搬 Windows 那份到校机 VM 则要写 4.56 GB（本机 `C:\Icraft` 实测 6 939 件／4.56 GB，其中 `CLI\bin` 525 件／4.27 GB）。落点列在第十节第 1／5 行等她定，**没装、没搬、没起机器、没往共享机上写任何东西**。
3. **Host float 基线**（`parsed` 档 640×640 已在 PC 上跑通）＋同口径评测，把"精度下降"那格真正填上；前提是先对齐前处理与 NMS，不是改配置。
4. **Qwen 那条链把 Host 逐层 ftmp 用起来**：改图（插 `Slice`/`Concat`）之后先在 PC 上对 `_ZG` 件做逐层回归，再上板看 token——省下的是"每次改动都要占板子一次"的排队。
5. 版本对照表（3.36.1↔3.39.0 的 Network／Session／MemChunk／硬算子 wait／ETM-FTMP 开关／CustomOp 兼容性七项），做完才轮到按 7.3 用 skill 的流程。
6. 向厂商剩下的两问：Qwen 板端逐层基准、手工往 IR 加算子的正规做法；`ocm_option: -1` 的取值。

## 九·补 2026-10-31 开跑记录

她 2026-10-31 的裁法「1 开跑，2 开跑」＝把第九节第 1、2 两条真正跑起来。本节记当天跑出来的东西，原始命令与产物都在 `workenv/zghostsim/`。

### 补 1　第 2 条：adapt↔generate 逐层对比（已出数）

**判据是厂商写的，不是我方自创（B）**：`wiki/PL/MOD/modrt/tutorial-runtime/docs/Part 4 性能分析及优化.md:695-699` 原文——「false(默认)，表示对特征图进行截位操作」／「true，表示不对特征图进行截位操作」／「**场景1： 如果要对比adapt 和 generate的结果，应设置fake_qf = true，将adapt结果作为golden，验证generate是否正确**」，紧接 `:699` 是场景 2「对比generate和runtime上板结果 ⇒ 设 fake_qf = false」。⇒ 这一跑就是厂商的场景 1：adapted 当 golden、generate 当被测。

**跑法**（本机 `C:\Icraft\CLI\bin\icraft.exe` 3.39.0，Host 后端，两侧喂同一张 `qtset/000000000139.jpg`）：

| 角色 | toml | 加载的件 | 落盘 |
|---|---|---|---|
| golden | `run_v8n_adapt_dump_qf.toml` | `Yolov8n_adapted.json/.raw` | `logs_adaptdump/`，185 个 `ftmp` |
| 被测 | `run_v8n_zg_dump_qf.toml` | `Yolov8n_ZG.json/.raw` | `logs_zgdump/`，128 个 `ftmp` |

两份都 `fake_qf = true`、`dump_format = "SFB"`（float32 裸数组、无头）。ZG 那 128 个张量在 adapted 侧全部存在、**字节尺寸逐一相同**（同尺寸＋数值同量级＝v_id 对齐成立，不用另做对齐）。
**adapted 多出的 57 个**是 ZG 图里被 HardOp 合并掉的中间量 ⇒ PC 侧能逐层看的只有 **128／185＝69%**。

**结果（A，逐层见 `workenv/zghostsim/ftmpcmp2.csv`，前 25 行见 `ftmpcmp2.txt`）**：

| rel ＝ 最大绝对差／golden 最大绝对值 | 层数 |
|---|---|
| 0（逐元素完全相同） | 2（都是输入图像本身：`Input 0` 与 `HardOp 908`） |
| 0 ～ 1e-3 | 1 |
| 1e-3 ～ 1e-2 | 42 |
| 1e-2 ～ 5e-2 | 79 |
| ≥ 5e-2 | 4 |

| rel_rms ＝ RMS(差)／RMS(golden) | 层数 |
|---|---|
| < 1e-3 | 3 |
| 1e-3 ～ 5e-3 | 28 |
| 5e-3 ～ 1e-2 | 33 |
| 1e-2 ～ 5e-2 | 64 |
| ≥ 5e-2 | 0 |

余弦相似度：最小 **0.999784043**、中位 **0.999957777**、128／128 层 ≥ 0.999。⇒ **126／128 层与 adapted 不是逐元素相同，但没有一层是"另一个张量"**。

最差的几层都落在 20×20 的三个检测头分支上：

| v_id | 算子 | shape | rel（单元素最差） | rel_rms |
|---|---|---|---|---|
| 469 | HardOp 868 | 1,2,20,20,32 | **7.38%** | 2.02% |
| 479 | HardOp 931 | 1,2,20,20,32 | 6.76% | 1.11% |
| 475 | HardOp 869 | 1,2,20,20,32 | 6.25% | 1.61% |
| 453 | HardOp 866 | 1,3,20,20,32 | 5.22% | 1.87% |
| 360／2029 | HardOp 880／896 | 1,4,20,20,32 | 2.27% | **2.22%（全图最差 RMS 口径）** |

**两处必须先还原、否则会把存储假象当误差（A）**：

1. **通道 padding 写 FLT_MAX 哨兵**。三个 80 通道的分类头（v_id 399／431／463，形状 `1,4,80,80,32`）实际是 **4×32＝128 个槽、只有前 80 个有效**，ZG 侧把第 80～127 槽写成 `3.402408e+38`，adapted 侧同位置是未初始化垃圾（实测有 337804／239824 这类值，不是哨兵）。按 ZG 侧哨兵位置剔除后，逐列哨兵占比正好是"前 16 列 0.25、后 16 列 0.5"，与"padding＝第 3 个 tile 的后 16 槽＋第 4 个 tile 整块（16＋32＝48 槽，128−48＝80）"完全吻合。
2. **输入层 uint8 被按 int8 存**。ZG 侧把 `136` 写成 `-120`、`170` 写成 `-86`（差 256），`int8→uint8` 回转后两侧**逐元素完全相同**（rel＝0、cos＝1.000000000）。非 `fake_qf` 那轮（`logs_dump/`）写的是正确值，所以这是 `fake_qf` 路径下的 dump 编码问题，不是计算问题。

不还原这两处会看到什么：3.4e38 的"误差"和输入层余弦 −0.35——我第一遍就是这么读的，判读已按上面两条改正。

**这条跑不完（A）**：两轮都在 `op_id = 486`、`customop::DetPostZGNode` 抛 `Exception info : 暂不支持"@fp(32)"`（上层 `stepTo faild`，`det_post_zg_hostbackend.cpp:161`），`[fatal] 1`。⇒ **厂商场景 1 的做法在这颗件上走不到 DetPost 的输出**。128 层全在它之前落盘，所以对比不受影响；但这两轮没生成 `_run_io.log`（崩在收尾前），v_id→算子的映射取自 `logs_dump/Yolov8n/Yolov8n_run_io.log`（不带 `fake_qf` 的那次完整跑）。

**这条改判了什么**：以前 `_ZG` 件只能整体黑盒对（跑一次得一个结果），现在 **generate 段有逐层数值基线**——误差随深度增长、头部最大、RMS 口径不超过 2.22%、方向与量级都符合 int8 量化误差的样子。**但它不是"通过不通过"**：厂商没给"一致"的量化门限，所以它的用处是**回归基线**（换配置、换版本时复跑 `ftmpcmp2.py`，看哪一层开始漂），而不是一个合格判据。边界也要写清：只覆盖 128／185 层、DetPost 自身不在内、只测了一张图（不是统计量）。



### 补 2　第 1 条：`thr_f = 0.001` 重编＋板端 5000 张（本机半 10-31 出数；板端半 11-01 补跑，**已出 AP**）

**这条要凑的是什么**：0.331 是在编译期 `thr_f = 0.1` 与评测 `conf = 0.1` 两处都是 0.1 的档位上测的，厂商 0.363 按第四节那条测精度规程属 0.001 档 ⇒ 想相减，两处都得先换到 0.001。第 1 条＝重编一颗 0.001 的件＋板端 5000 张全量。

**本机这半做完了（A）**。工作区 `S:\apps\llm\agentwork\build\icompile_v8n_640_thr0001\`，连编三颗：

| 颗 | 配置 | 用途 | `Yolov8n_ZG.json` | `Yolov8n_ZG.raw` |
|---|---|---|---|---|
| ctrl | `config/ZG/Yolov8n_640_ctrl.toml`（`thr_f = 0.1`） | 对照 | 304,217 B／md5 `c4cc09fcb5e7c35267f716f7f2d6f34c` | 4,722,587 B／md5 `09f59e39596e0caa338a762dbce0102a` |
| ctrl2 | 同上、输出目录改 `ctrl2` | 确定性复跑 | 与 ctrl 逐字节相同 | 同左 |
| thr0001 | `config/ZG/Yolov8n_640_thr0001.toml`（`thr_f = 0.001`） | 实验件 | 304,221 B／md5 `b1a172ca00634ca7ffda70c067621820` | 与 ctrl 逐字节相同 |

三颗都十件齐全；日志按 `\r` 切成 4 673 条非空逻辑行后，`[F]`／`[E]`／`fatal`／`错误码` **0 命中**（`icraft` 的退出码不可靠，判过方式仍是"十件齐全＋切行扫日志"）。ctrl 与 ctrl2 **十件逐件 md5 相同** ⇒ 编译确定性成立，后面的差全是配置差；ctrl 的五个阶段尺寸也与第 3.1 节基线逐字对上（parsed 142,868／12,609,128、adapted 342,186／3,334,445）。

**图差只有一处（A）**：`Yolov8n_ZG.json` 递归结构比对**只有 4 个值不同**，全在同一个算子——`ops[120]`、`op_id 486`、`_type_key = customop::DetPostZG`：

| 字段 | ctrl（0.1） | thr0001（0.001） |
|---|---|---|
| `data_thr[0..2]` | `[-11, -8, -6]` | `[-35, -25, -20]` |
| `thr_f` | 0.10000000149011612 | 0.0010000000474974513 |

其余 121 个算子一个字没动，`Yolov8n_ZG.raw` 4,722,587 B **md5 相同**；JSON 只大 4 B，就是这串数字变长后的字符差。⇒ 0.001 这一刀只动检测后处理门限，**不碰任何特征图计算**。

**Host 冒烟也跑了（A）**：同一张 `qtset/coco/bus.jpg`、两个 `[run]`（Host 后端、`dump_format = "SFB"`），两条都是 rc＝0 且走完 `DetPostZG → Output`（SUMMARY 里 `DetPostZG` 的 `total_wall` 两轮分别是 134.518／147.209 ms）。各出 **131 个 ftmp**，其中 **128 个逐字节相同**，不同的只有 DetPost 的三个输出：

| v_id | 声明 shape | ctrl 落盘 | thr0001 落盘 |
|---|---|---|---|
| 1490 | 1,80,80,192 | 0 B | 284,800 B |
| 1491 | 1,40,40,192 | 4,000 B | 152,800 B |
| 1492 | 1,20,20,192 | 36,800 B | 60,000 B |

三个输出都是 `storage_dtype = @sint(8)`、`scale = 1`，落盘形态是"int8 域整数按 float32 写"的**变长**数组（声明 shape 相同、实际长度随门限变）。长度随门限下降而涨、内容从第 0 个元素起就不同 ⇒ 编译期门限确实活到了输出，不是只改了一张表头。

**顺带把补 1 那条 abort 的适用范围钉死（A）**：这一轮两条 Host 跑都没撞 `暂不支持"@fp(32)"`——它只在 `fake_qf = true` 那条路上出现（补 1），**挡的是场景 1，不挡第 1 条**。

**（这一段的读数停在 10-31；11-01 已补跑，结果见本节末「板端」）板端那半当时没跑，卡两道各自独立的闸（A）**：① `ssh deb-h61 'cat /home/user/Desktop/113.txt'` 读到 **`test==on`**（2026-10-30 20:00 UTC 读），按约定这一轮不碰板子，占用方不是本会话；② 就算空着，新 imodel 上板也要她明说"上"。备好的东西一步没往板上推：`S:\apps\llm\agentwork\yolov8_deploy\cfg\eval_full_conf0001.yaml` 与 `eval_smoke_conf0001.yaml` 跟原文件**各差 3 行**（`imodel.dir` → `/root/v8eval/imodel_thr0001`、`res` → `out_conf0001*`、`conf` 0.1 → 0.001）；件要拷去 `/root/v8eval/imodel_thr0001/`。按第八节口径 369 s／5000 张 ⇒ **一档 ≈ 6.2 min**。

**为什么"重编"不能拿 yaml 的 `conf` 顶替（B＋C）**：板端驱动的 `updateDetpost()` 在 `yaml.conf` 与算子自带 `thr_f` 不一致时，按 `scale = ln(1/conf_new−1) / ln(1/thr_f−1)` 去乘 `data_thr` 再整数截断（`repos/official/demo/Icraft-ModelZoo-yolov5/fpai_demo_app/deps/modelzoo_utils/include/et_device.hpp:653-697`，本机逐行直读；同一机制的已回查记录＝`wiki/man/NPU调用链.md:38`）。按这颗件算：scale＝ln(999)/ln(9)＝**3.14339956**，ctrl 的 `[-11,-8,-6]` 若只改 yaml 会变成 **`[-34,-25,-18]`**（`static_cast<int64_t>` 向零截断），而真按 0.001 重编出来是 **`[-35,-25,-20]`** ⇒ **差 1～2 个 int8 LSB，不是同一颗件**。反过来，thr0001 件配 `conf = 0.001` 时 `netinfo.thr_f == conf`，`updateDetpost` 整段跳过、编译出来的门限原样用。这既解释了厂商为什么要求两处都改，也给板端留了一条可验证的预测：`ctrl 件＋conf 0.001` 的读数应当≈但≠`thr0001 件＋conf 0.001`。

**边界**：① 本机这半只证明"图变了、输出变了、特征图没变"，**没证明精度会变成多少**——那要板端 5000 张（11-01 已补上，见下）；② Host 冒烟只一张图，是机制证明不是统计量；③ `data_thr` 与 `thr_f` 的精确换算式（我算到 ≈`logit(thr_f)`／该头 scale 同量级）**没当已验证公式用**（C）。

#### 板端那半（2026-11-01 11:06–11:27 UTC，A）

**先查明一件事：板上的基线件就是我们的 ctrl 件。** `/root/v8eval/imodel/Yolov8n_ZG.json` md5 **`c4cc09fcb5e7c35267f716f7f2d6f34c`**（304,217 B）、`.raw` **`09f59e39596e0caa338a762dbce0102a`**（4,722,587 B），与 10-31 编的 ctrl 件**逐字节相同** ⇒ 0.331 那颗基线件不是"厂商另一颗网络"，就是同一张图、同一个 `thr_f = 0.1`。这一条把两档的可比性从"看起来是同一个模型"抬到"字节相同"，也顺手证明我们的重编能复现板上原件。

**COCO 图已不在板上，所以改成 5 批上传。** `/root/v8eval/coco/val2017` 这个目录**不存在了**（10-31 那轮磁盘清理清掉了，见 [[板端我方代码与产物台账]] 廿四），根分区只剩 948 MB／97%。本机 `S:\apps\llm\agentwork\coco\val2017` 有全套 5000 张（788 MB，逐批 `ls | wc -l` ＝ 1000），一次推上去会把盘吃穿 ⇒ 改成 **5 批 × 1000 张**：推一包 163 MB 的 tar → 解到 `/root/v8eval/coco_chunk/` → 跑 → 删图 → 下一批，峰值占用 ≈165 MB。五批的产物都按 `res:` 写进同一个 `out_conf0001/`，合起来仍是 5000 张。

| 批 | 图数 | 结果文件累计 | `RC` | 备注 |
|---|---|---|---|---|
| 0 | 1000 | 1000 | 0 | 首批兼当格式验证 |
| 1 | 1000 | 2000 | 0 | 计时 **88.6 s／1000 张**（含装载）＝ 11.3 张/s |
| 2 | 1000 | 3000 | 0 | |
| 3 | 1000 | 4000 | 0 | |
| 4 | 1000 | 5000 | 0 | 跑完整批后当场删图，盘回到 891 MB |

- **冒烟 30 张先跑过**（`eval_smoke_conf0001.yaml`，3.49 s 含装载）：`conf 0.001` 出 **4,103** 个框，同一批 30 张的旧档（`conf 0.1`）是 **291** ⇒ 14 倍，门限确实活到了运行时。
- **全量**：5000 个文件、**713,474** 个框（142.7/张）、**0 个空文件**；`out_conf0001/` 42 MB，取回包 36,188,160 B md5 `b5d34198e7d54a71450f9533213c7e26`（本机落盘后逐字节复核相同）。
- **比 0.1 档慢的这点对得上因**：13.5 张/s → 11.3 张/s，框数从 8.7/张涨到 142.7/张，后处理变重。量级方向成立，但不是同刻对照（10-04 与 11-01 隔了四周、同刻负载不同）⇒ 只当解释，不当测量结论（C）。

**AP（A，本机 `calAP.py`，与 10-04 那轮同一份 `instances_val2017_yolo.json`、同一套 `--classAP` 口径）**

| 档 | 编译 `thr_f` | 评测 `conf` | AP@[.5:.95] | AP50 | AP75 | APs | APm | APl |
|---|---|---|---|---|---|---|---|---|
| 现役（10-04，件 md5 `c4cc09fc…`） | 0.1 | 0.1 | 0.331 | 0.462 | 0.359 | 0.148 | 0.367 | 0.483 |
| 本件（11-01，件 md5 `b1a172ca…`） | **0.001** | **0.001** | **0.358** | **0.511** | **0.384** | **0.174** | **0.394** | **0.508** |
| 厂商（口径见第四节） | 0.001 | 0.001 | 0.363 | — | — | — | — | — |

⇒ **与厂商的差从 0.032（相对 9.7%）收到 0.005（相对 1.4%）**。此前把 0.331 与 0.363 相减得出的"差 0.032"，主因不是件有问题，而是**档位没对齐**——0.1 门限把小目标、低分框先筛掉了，APs 从 0.148 掉到 0.174 这一格最能看出方向。

**这一档的边界（别读过头）**：① 这一跑同时改了**编译件**与**运行时 `conf`**（两处 `thr_f`），两个因素**没拆开**；要拆得再跑一档 `ctrl 件＋conf 0.001`（≈ 10 分钟板时），那一档的读数若已接近 0.358，就说明"重编"这件事对方程没有增益、`updateDetpost` 的运行时换算够用——补 2 上半段算出的 `[-34,-25,-18]` vs `[-35,-25,-20]` 那 1～2 个 LSB 到底值多少 AP，正卡在这个对照上。**2026-11-01 晚她裁这一档不跑了**（原话"后面的不跑了，反正重编不会有错，对吧？那不管他有没有实际增益，都够了"）⇒ 对照**没做**，"换重编件"与"改 `conf`"两处改动的各自贡献**至今没拆开**，0.358 里"重编"值多少 AP 停在 C。她那句问话本身我答的是**件不会编错**（A：`.raw` 与现役件逐字节相同、121 个算子没动、IR 只差 DetPostZG 的 `data_thr`／`thr_f` 四处、五批 5000 张全 `RC=0`），这条**不等于**增益已归因；② 0.331 是 10-04 的量、0.358 是 11-01 的量，**不是同一天背靠背**（件 md5 相同把"模型不同"这条排除了，但驱动／runtime 版本与同刻负载没重核）；③ 厂商 0.363 的测法（前处理、`iou_thresh`、是否 fpga_nms）**我没有逐项对齐**，只对齐了教程要求的两处 `thr_f` 与数据集、AP 脚本口径。

## 十、需要你决定

| # | 事项 | 我的建议 | 状态 |
|---|---|---|---|
| 1 | 要不要现在开跑第九节 1／2 两条（**本轮改写过：上一版写的"校机跑不了"用错了对象，见 TL;DR 第 11 行**） | 2 先跑（不占板子、不需新件、当天出结果）；1 要占板子，等 NPU 空档 | **2026-10-31 晚更新：第 2 条已出数（补 1）；第 1 条本机半已出件＋Host 冒烟过（补 2），板端半卡 `113.txt = test==on` 与上板授权两道闸。**2026-11-01：板子空出来后已补跑，读数见补 2「板端」。**下面这段是当时的判断，留着不改。** 当时的口径：**两条都已裁、都还没跑，但缺的是决定、不是主机**：第 2 条她裁"在校机跑"⇒ 实测校机没有 iCraft（`where icraft` 空），可这一条要的是 Host 后端 `icraft run`，**本机已跑通过**（第 3.1 节四档＋131 个 ftmp 就是它出的）⇒ 落点只剩第 5 行那个"在哪台跑"的形式问题；第 1 条她裁"能在校机跑吗能就跑"⇒ 这条根本不经过校机：**重编只能本机 Windows CLI**（Linux amd64 那份 codegen 只带布衣，ZG 档 `icraft-generate` fatal 缺 `libicraft_zhuge_codegen.so`，正本＝[[NPU模型上板出指标SOP]] 第九节坑 4），全量 5000 张在板上，按第八节实测口径 369 s／5000 张＝13.5 张/s ⇒ **6.2 分钟／档**、两档 ≈ 12.4 分钟。另外这句话本身的适用性两版教程写法不一致＝第 8 行 |
| 2 | `哪些要跟厂商要.md` 的 #6 是"作废"还是"缩范围保留" | 缩范围保留 ②④ 两问，别整条删——删了以后没人知道我们为什么能自己验 | 已按"缩范围保留 ②④"落地 |
| 3 | 要不要把 [[iCraft算子支持矩阵]] 与 PDF 表正式合并成一张 117 行的总表（BY 限制仍从网页表带过来） | 先不合并，保持两页＋本页第八节的对照；合并会让"哪格来自哪份一手件"变糊 | 已按"不合并"落地 |
| 4 | 要不要给 num-audit 的 `REF` 正则加"文件名内含空格"支持 | 建议加——加了那 8 处厂商引用才能回到 B 项自动回查，否则一直是人眼核 | **她 2026-10-31 裁"要"，已做**：空格只在反引号内被接受，写法与顺带挖出的双副本问题记在第十二节 |
| 5 | **场景1（`fake_qf = true` 的 adapt↔generate 对比）在哪跑——本轮已收窄成"本机跑不跑"**（前两次改写：先问"有没有 x86_64 Linux 版 CLI"（前提错），再问"校机能不能跑"（对象错）） | 本机就是答案：第 3.1 节那四档就是本机 `C:\Icraft\CLI\bin\icraft.exe`（**实测 3.39.0／build `3.39.0.0-431be90(2608211646)`**）的 `icraft run` 跑出来的，`--save_snapshot`／ftmp 都用过 ⇒ 这一条**零安装**。其余三条本轮也各有实测读数，留着只为"确实要 Linux x86 侧 iCraft"的别的需求：① 本机 podman **已经有** Linux 侧入口——`podman.exe` 在 `C:\Users\takomi\AppData\Local\Programs\Podman\`、`podman-machine-default`（wsl／8 CPU／2 GiB 记账值／100 GiB，LAST UP 10 天前），里面的 `localhost/fpai-ub2004:tts-saved` 就是 Ubuntu 20.04＋ICraft 3.39.0 同 build；**但它在 ZG 档 `icraft-generate` fatal**（坑 4）⇒ 起机器只为这一条不划算；② 本机 WSL Ubuntu 26.04（`/` 可用 **943 GB**）——厂商 readme 写 **`largefiles/04_ICraft/v3.39/icraft_v3.39.0/readme.md:15-21`＝Ubuntu20.04-amd64**、盘上是 26.04；wheel 是 **cp38**、里面 python 是 3.14.4 且没有 python3.8；`.deb` 的 control **无 `Depends`**，装了能不能跑要实测；③ 中转机 102（`ssh deb-h61`）＝真 Linux：`Linux 6.12.111+deb13-amd64`、podman＋crun 现役、`/` 可用 102 G、`registry-1.docker.io/v2/` 回 **401**（可达）、`mirrors.aliyun.com` 回 200、`podman images` 现在为空 ⇒ 起一枚 `ubuntu:20.04` 就是厂商那一档；④ 校机 VM＝**已排除**（没 iCraft、没容器，而且我重建不了：非管理员＋`SecondLevelAddressTranslationExtensions` False＋C 盘 19.5 GB） | 建议**本机当场跑**（要跑的话一句话就行）。**没装、没搬、没起 podman machine、没拉镜像、没往校机写任何东西**——起机器和拉镜像都算装东西，按她"安装前先确认前提"的规矩等她点头 |
| 6 | ~~AGENTS.md 第四节的校机口径要不要按实测改~~ | 建议补实况那句，并把 Linux 侧入口让她口述一次记进 [[校机代理与GitHub登录SOP]]（那页是校机 ssh 定义的正本） | **她当次裁"2 要改"⇒ 已改两轮，本轮又改第三轮**：那一行现在写明 ① ssh 进去的是 Windows 11 子机（`Win11 Pro for Workstations`／build 26200、`Win11-HV1`、`win11-hv1\yizhidi`、EPYC 9654 24 物理核／24 逻辑核、125 GB、`HypervisorPresent` True）；② 没 iCraft、没 WSL、**没有任何容器运行时**，且我重建不了（非管理员＋SLAT 未透传＋C 盘 19.5 GB）；③ **但交叉编译照旧走它**——`D:\yzd\WCIS\crosswin`＋`D:\yzd\MSYS2`＋Arm GNU 10.3 整套实测在（gcc RC＝0、产物 `build\yolov8n` 6 408 568 B、D 盘可用 1 571.9 GB），正本指向 [[交叉编译主机路由SOP]] 与 [[校机无容器交叉编译]]；④ iCraft 模型编译在本机 Windows CLI（3.39.0／`431be90`），ZG 档只能它出。**两件剩余项一件关闭一件收窄**：~~第二节干活纪律第 4 条"优先校机，其次本机"要不要跟着改~~ ⇒ **不用改**（那条讲的正是交叉编译，校机确实还是首选——上一版我以为要改，是因为我把"没容器"读成了"没编译能力"）；② 那条"Linux 侧仅 CPU 校机的入口"仍缺：三个 ssh 别名实测全落 `Win11-HV1`，仓里没有第二个校机入口 ⇒ 要的是**宿主那台 EPYC 主机**的入口，还是这台子机就够（她一句定），记的位置在 [[校机代理与GitHub登录SOP]] |
| 7 | **两套官方教程定不定正本**（本轮有证据了，问题变成"按什么引"） | 上一版建议"定 WL 为正本"现在**不能那么定**：A＝**3.31**（gitee 个人镜像 `mxh-spiger/tutorial-runtime`，含唯一的 `Part 1_5 ZG Usage.md`＝我方 30TAI/ZG 那条线）；B＝**3.39、只面向 WL170(400TAI)**，而 3.39 的 ZG/30TAI 教程线在盘上**根本不存在**（遍历 `repos/official` 全部 `.md`，带 ZG 口径的只有 A）。建议改成"**不分正本、按版本各自引**"：引 ZG/30TAI 操作口径 ⇒ 只能引 A 并标"3.31"；引 3.39 的结论 ⇒ 引 B 并标"3.39-WL(400TAI)"，两句都带全路径（第十二节定死的那条）。第十二节那 3 条裸名现在**有依据就地改**：它们写于 2026-10-18，行号 52／116 精确对上 B 那份（A 那份是 77／135），而当时盘上两份都还没落（A 是 10-29、B 是 10-30）⇒ 引的一直是**线上 3.39 版正文**，改成 B 的全路径就是如实还原 | 未裁。**改法已备好、一个字没动**（裁完就一次改齐 3 条） |
| 8 | **`thr = 0.001` 这条要求到底适用不适用我方 ZG 件**（新开，卡着第 1 行那条重编） | 3.31 那份是无条件句，3.39-WL 那两份同样位置都加了"（BUYI 场景）"、且同文件写"WL170 无 DetPost" ⇒ 两种读法与后果记在第九节第 1 条。建议**别先赌适用性**：同一批里 `thr = 0.001` 与现役 `thr_f = 0.1` **各重编一颗、各跑一遍全量评测**，两档数一起落账（板时算式 5000 张 × 73.8 ms/张 ≈ 6.2 分钟／档；重编都在 PC 上、不占板）；同时把这条版本差追加进 [[哪些要跟厂商要]]，问"ZG 档用 `customop/DetPost` 时 thr 该不该 0.001" | **2026-10-31 晚：已按这行建议把两颗都编了**——`thr_f = 0.1` 对照（ctrl／ctrl2 确定性复跑）与 `thr_f = 0.001` 实验件都出了十件，IR 只差 DetPostZG 的 `data_thr`／`thr_f`，Host 冒烟 128／131 层逐字节相同（补 2）；**板端两档全量一张都没跑**（`113.txt = test==on`）。**2026-11-01 更新：0.001 这一档已跑完全量 5000 张，AP 0.358／AP50 0.511（见补 2「板端」）；0.1 档仍是 10-04 的 0.331，两档的件 md5 已核成同源。向厂商问版本差那条还没发。同一轮她裁 `ctrl 件＋conf 0.001` 那一档不跑 ⇒ 本行"两档各跑一遍"的建议只落了一半，"重编"与"改门限"的增益归因停在 C（补 2 边界 ①）。** |
| 9 | **A 那份 3.31 教程（带 `.git` 的个人镜像）在库里怎么处置**（新开） | 现状是个隐患：它在 `wiki/PL/MOD/modrt/tutorial-runtime/`、既没被跟踪也没被忽略（`git status` 是 `??`、`git check-ignore` RC＝1）⇒ 一次 `git add -A` 就把它写成**没有 `.gitmodules` 条目的 gitlink**（mode 160000、指不回任何提交；wiki 库确实没有 `.gitmodules`）。三条：① 在 `wiki/.gitignore` 里**具名**排除该目录并在注释写清原因（正是第七节那条规矩的正解）；② 登记成真子模块（要新建 `.gitmodules`，而且上游是个人镜像，不建议）；③ 挪出入库路径（但她说过这批素材"先留着"） | 未裁，`.gitignore` 一个字没改 |


## 十一、本轮实测的落盘位置与命令

| 产物 | 位置 |
|---|---|
| Host 仿真四档的 `[run]` 配置与日志 | `workenv/zghostsim/`（`run_v8n_host.toml`／`run_v8n_parsed.toml`／`run_v8n_adapted.toml`／`run_v8n_dump.toml`／`run_zg_host.toml` 与同名 `.log`；ftmp 在 `logs_dump/Yolov8n/ftmpSFB/`） |
| 第 1 条（`thr_f = 0.001` 重编＋Host 冒烟）的配置、日志与三颗件 | `S:\apps\llm\agentwork\build\icompile_v8n_640_thr0001\`：`config/ZG/Yolov8n_640_{ctrl,ctrl2,thr0001}.toml`、`config/customop/yolov8_{ctrl,0001}.toml`、`{ctrl,ctrl2,thr0001}_compile.log`、`run_{ctrl,thr0001}.toml` 与同名 `.log`；件在 `imodel/{ctrl,ctrl2,thr0001}/`，ftmp 在 `logs/run_{ctrl,thr0001}/Yolov8n/ftmpSFB/`。板端 yaml 备件（未上板）＝`S:\apps\llm\agentwork\yolov8_deploy\cfg\eval_{full,smoke}_conf0001.yaml` |
| 两份算子正本的对齐脚本与原始差异表 | `workenv/opdiff/compare_ops3.py`、`workenv/opdiff/opdiff.md` |
| skill 检查脚本的报告 | `workenv/skilltest/ours_v8n_zg.json`、`vendor_yolov5s_zg.json` |
| 门禁读数与双副本取证（2026-10-31 追加轮） | `workenv/gate/`：`red.txt`／`green.txt`（自证两件的输出）、`audit.txt`（本页门禁摘要）、`checkmd.txt`（全库 `check-md.py` 全量输出）、`dupcmp.py`＋`dupcmp.txt`（两套教程的逐件行数／md5／同句落点对照，末两段对比新旧 `REF` 的匹配结果）、`dupscan.py`（全库扫裸名引到这 6 件同名文件的地方，出 3 条）、`resolvecheck.py`（`resolve()` 对裸名的落点逐件核验）、`rungate.py`（一次跑完红／绿／交付物三件并列出逐项读数）。复现：`python -X utf8 workenv/gate/dupcmp.py > workenv/gate/dupcmp.txt`（工作目录＝仓库根） |
| 同一轮第二次追加（回答"两套分别在哪里"／"1 是有的"／"2 要改"／"4 能在校机跑吗"） | `workenv/gate/` 本轮新增的脚本（产物同名）：`twosets.py`＋`twosets2.py`（两套教程的名册／字节／md5／父目录／`git ls-files`＋嵌套 `.git` 的 remote、分支、HEAD）、`mtimes.py`＋`mtimes.txt`（两份落盘的创建／修改时间，用来判"裸名写下时盘上有哪一份"）、`pkgs.py`（全仓 `.deb`／`.whl`／`.exe`／`.zip` 清点＋`30TAI&100TAI.zip` 36 条目逐条大小＋vendor readme 前 40 行）、`debcontrol.py`＋`debcontrol.txt`（流式取 amd64 `.deb` 的 control 成员）、`wslcheck.py`＋`wslcheck.json`（本机 WSL 发行版与 Ubuntu 内 icraft／python 实测）、`schoolguest.py`＋`schoolguest.txt`（`ssh school-guest` 八条命令的 RC 与解码后读数）、`prov.py`＋`prov.txt`（三条裸名引用的 `git blame` 日期＋两份里同一句话的行号）、`sentcmp.py`＋`sentcmp.txt`（逐句 strip 后字节比对与 `SequenceMatcher` 相似度）、`envsetup.py`＋`envsetup.txt`、`envwhere.py`＋`envwhere.txt`（全仓 `env_setup` 件的名册与口令行／百兆行行号，用来确认"只有两份副本"）、`rungate2.py`／`rungate3.py`＋`rungate3.txt`（改完后的门禁重跑：红／绿／交付物／SOP＋`check-md`，`rungate3.py` 修的是 `send2trash` 对混合分隔符路径报 `ProcessLookupError`、要把 `--json` 落在交付物旁边的 `.audit.json` 立刻进回收站）、`checkmd2.py`＋`checkmd2.txt`（全库 `check-md.py` 只看我这两页的命中行）、`bcount.py`＋`bcount.txt`（带 `--json` 跑本页，打印 B 项每条最终解析到的路径与 PASS／WARN 分布，第十二节那组落点数字出自它）。跑法同上：`python -X utf8 workenv/gate/<名>.py`，产物写在同目录 |
| 同一轮第三次追加（回答"不是找到 deb 了吗／本机 cli 是哪个版本／校机真的没容器吗／你能不能重建"） | `workenv/gate/` 再新增：`localcraft.py`＋`localcraft.txt`（`C:\Icraft` 顶层名册、两份 CLI 的 `bin` 全件清单、exe `VersionInfo`、`icraft --version`／`-v`／`version`／`--help` 四条 RC）、`localcraft2.py`＋`localcraft2.txt`（`where icraft` 与 MACHINE／USER 级 PATH 里含 Icraft 的条目，两份目录的版本逐条对读）、`schoolenv.py`＋`schoolenv.txt`（校机 22 组读数：PATH 里九个可执行文件、`docker version`、`wsl --status`／`--version`、服务表、`Win32_ComputerSystem`／`Win32_Processor`／`Win32_OperatingSystem`、C 盘剩余、administrators 组成员、C 盘顶层目录、Program Files 容器类目录、Appx、两个功能开关的提权报错、`winget`、代理键、三个站点的连通）、`rebuild.py`＋`rebuild.txt`（三个 ssh 别名逐条比 hostname／令牌／SLAT／盘余；本机 `where docker`／`podman`、`podman machine list`、`wsl -l -v`、WSL Ubuntu 内工具与根盘；102 的系统／podman／crun／镜像表／两个 registry 的 HTTP 码）、`schoolcross.py`＋`schoolcross.txt`（**关掉上一版漏掉的那一面**：全部文件系统盘、`D:\yzd\...` 十一处 `Test-Path`、工具链 bin 名册与 `--version` 实跑、crosswin 顶层 70 行与逐子树件数／最后写入、`build`／`build-py` 产物尺寸、yizhidi 的组）。**这一组全是只读探测**：没装、没搬、没起机器、没在共享机上写过一个字节 |

复现（本机，`icraft` 在 `C:\Icraft\CLI\bin`，工作目录切到 `workenv/zghostsim/`）：

```bash
icraft run run_v8n_host.toml     # 我方 _ZG 件在 Host 上跑通，出 SUMMARY
icraft run run_v8n_dump.toml     # 同上＋逐层 ftmp（计时行在这种开关下不可信）
icraft run run_zg_host.toml      # 官方 demo 那颗 3.33.1 件 ⇒ 26003，版本不兼容实证
```

## 十二、本页的门禁读数与工具侧结论

- `python -X utf8 wiki/format/check-md.py`：本页 **0 条**问题；全库基线本轮改判后是 **483 条／266 组**（改判前 484／267，少的这一条是 [[哪些要跟厂商要]] 补上的"相关页面"节，其余都不是本轮引入的）。
- num-audit 自证 `RED=1`／`GREEN=0` 之后跑本页：**FAIL 0／WARN 12**，退出码 0（**本刻全量**：A1 1 条 PASS、A2 0 条、A3 2 条 WARN、**B 36 条＝FAIL 0／WARN 10／PASS 26**、C 0 条；第三次追加当时记的是 FAIL 0／WARN 10、B 34 条＝WARN 8／PASS 26，差额见本段末；取证脚本 `workenv/gate/bcount.py`→`bcount.txt`，它带 `--json` 跑本页并逐条打印每个引用最终解析到的路径）。B 项 36 条的落点分布：这套教程 **17 条**＝3.31 那份 **14**（`Part 4`×6／`Part 2_2`×4／`Part 1_5 ZG Usage`×3／`tutorial-runtime/readme.md`×1）＋3.39-WL 那份 **3**（`README.md`×1／`WL/Part 4`×1／`WL/Part 1_2 Icraft Terminology.md`×1），另有 **2 条**带全路径引到 `largefiles/04_ICraft/v3.39/icraft_v3.39.0/readme.md` 且 **PASS**——这两条是下一条"负断言不在覆盖面"的正面例外：`resolve()` 的第一支"原样拼根"不看索引，所以 `build_index` 排除 `largefiles` 只打掉**裸文件名**那一支，带全路径的引用照样能打进 `largefiles`；本轮第三次追加又加进 **4 条**（`wiki/SOP/交叉编译主机路由SOP.md`×3＋`wiki/SOP/校机交叉编译环境搭建SOP.md`×1，2 PASS／2 WARN）。十二条 WARN 逐条确认过：**两条 A3**＝第 3.1 节表格 `parsed`／`adapted` 那两行的 `total_time`——工具按行判，第 3.1 节开头那句"全是实测＋逐条对应日志文件名"落在表头行、没落到数据行，所以标注在段里、不在行里，读数本身对过日志（`run_v8n_parsed.log` 589.564／`run_v8n_adapted.log` 1443.802）。**十条 B**＝"被引区间找不到本句的 ≥6 字符 ASCII 标识符"：教程 `Part 4` 那条 1 处（引到 708–709 行）、教程 `Part 2_2` 那条 3 处（本页三个不同句子都引 398 行）、[[状态源与决策记录]] 第 490 行（D-32 不触发判定那一行）1 处、[[任务卡与台账规范]] 第 113 行（"ICraft 版本列必须填实际 tag"）1 处、`哪些要跟厂商要.md` 第 81 行与第 94 行各 1 处（类型同上：引用句里没有可自动比的 ASCII 标识符，行号直读内容对得上）、**第三次追加新增 2 处**——都是同一串 `wiki/SOP/交叉编译主机路由SOP.md:12` 被抓了两次：本节这句自引一次（话里带着这串，工具当它也是一条引用）、本节末条那次实引一次；工具打出的区间实得是「| 编译工具链 | Arm GNU **10.3-2021.07**（i686-…」，与本句同一条，逐字对得上，属同一类标识符匹配不到而非指错——按 [[交付物数字审计num-audit]] 的口径逐条打印区间，内容全部对得上。**这一段本身的写法是工具抓出来的**：它第一版把教程引用写成了裸文件名，当轮读数 FAIL 1／WARN 9，那条 FAIL 正是"裸名解析到 WL 那份、595 行越界"，另有一条 398 行的裸名解析到 WL 后落在一行算子计时日志上（只报 WARN、不报指错）——即下面第 4 条的现场证据，改成带全路径后才是现在这组数。**补 1／补 2 之后多出来的两条 B 都是 PASS**：补 1 那句引的 3.31 `Part 4 性能分析及优化.md` 695–699 行（教程引用 A 那份 13→14 条）＋补 2 那句引的 `wiki/man/NPU调用链.md` 第 38 行。WARN 从 8 变 10 的两条是 `哪些要跟厂商要.md` 第 81／94 行，类型与本段已列的十条同一类、不新增类别；它们上一版没被列进那"八条"，**为什么本刻多出来我没有取证**——这页与相邻页可能被另一条会话动过，以本刻读数为准。
- **空格文件名这条已根治（2026-10-31，她裁定"要"）**：`REF` 现在分两支匹配——**反引号内**允许空格（`[^`\n|]{1,140}?` 再跟扩展名），**反引号外**仍不允许空格，所以散文里相邻两个词不会被吃成文件名。本页那 8 处厂商引用因此从"第 N 行"改回带全路径的 `文件:行号`，重新进 B 项自动回查（本轮最后一次全量：B 项 34 条里 **16 条是这两套教程的引用**，13 条落 `wiki/PL/MOD/modrt/tutorial-runtime/docs/` 那份、3 条落 `repos/official/tutorial/icraft_tutorial/WL/` 那份——**落点由路径写死，不再由 `hits[0]` 决定**）。单位测试五种写法实测（`workenv/gate/dupcmp.txt` 末两段）：① 带全路径的空格名放进反引号 ⇒ **整条命中**，回查 wiki 那份；② 只写文件名也放进反引号 ⇒ 一样命中，但按 `hits[0]` 落到 WL 那份（就是下一条的事）；③ **散文里不带反引号**的空格名（"见某某 md:398 那句"）⇒ 仍只吃到最后一个空格之后的片段，**照旧是一条假 FAIL**——所以这条改动把责任从工具转移到了写法：**空格名必须包进反引号**；④ 同一行两个代码片段（片段一 `a.md` 数字、片段二 `b.md` 数字）⇒ 各自命中，不会把中间那个词吃进文件名；⑤ 表格单元格里放反引号空格名 ⇒ 单元格内正常命中，竖线被排除在字符类外，两列不会被连成一个文件名。写法口径已记进 [[交付物数字审计num-audit]] 坑 5 与坑 6。
- **根治顺带挖出一条更危险的（同名双副本，本体记在第二节）**：`resolve()` 的次序是"原样拼根 → 当绝对路径 → 全仓按文件名取 `hits[0]`"，而 `os.walk` 在本仓把 `repos/` 排在 `wiki/` 之前 ⇒ **裸文件名一律命中 `repos/official/tutorial/icraft_tutorial/WL/` 那一份**（实测 6 件同名文件 `hits` 全＝2、解析结果全是 WL；`Part 1_5 ZG Usage.md` 因 `hits`＝1 才落到 wiki 那份）。同一句话在两份里的行号差，本轮逐件直读：

| 句子 | 3.31 vendored 那份 | `repos/official/…/WL/` 那份（3.39） | 两份文字是否相同（strip 后逐字节，`SequenceMatcher` 相似度） |
|---|---|---|---|
| `Part 4 性能分析及优化.md` thr＝0.001（编译期 toml） | 708 | 562 | **不同**：3.39 多了「（BUYI 场景）」，相似度 0.935 |
| `Part 4 性能分析及优化.md` thr＝0.001（评测 cfg/test.yaml） | 709 | 563 | **不同**：同上，相似度 0.928 |
| `Part 4 性能分析及优化.md` 场景1 `fake_qf = true` | 698 | 552 | 相同（1.000） |
| `Part 2_2 icraft tools.md` `fake_qf` 仅对 HostBackend 有效 | 204 | 271 | 相同（1.000） |
| `Part 2_2 icraft tools.md` 快照只支持 BY 阶段的网络 | 398 | 462 | 相同（1.000） |
| `Part 0 env_setup.md` 出厂默认口令那一行 | 77 | 52 | 同句（两份都有"用户名：root，密码：fmsh"） |
| `Part 0 env_setup.md` 百兆全双工那一行 | 135 | 116 | 相同（1.000） |

  ⇒ 上面这些引用若写成裸文件名，后果分两种：**4 条报假 FAIL**（WL 那份 `Part 4` 只有 595 行，本页 `:708-709`／`:708`／`:709`／`:698` 四处一律"行号越界"）；**2 条静默指错**（`Part 2_2:204` 在 WL 那份是 `cos_targetvalue` 那行参数表、`:398` 是一行算子计时日志——行号在范围内，工具比不出"指到了别的段落"）。**所以口径定死：引这两套教程一律带全路径。**
- **上一版那条"考不出证"的账，本轮考证出来了（2026-10-31 第二次追加）**：全库那 **3 条**裸名引 `Part 0 env_setup.md`（[[状态源与决策记录]] 第 374 行引 `:52`、`PS/psrt/rt/rt.md:47` 与 `todo/dev/板子（除芯片）.md:97` 各引 `:116`）——
  - **写下时间**：`git blame` 三条都落在 **2026-10-18**（`4c07739`「D-60…」与 `bfe10a4`）；
  - **当时盘上没有任何一份副本**：3.31 vendored 那份的目录创建时间是 **2026-10-29 04:50**（`.git` 04:48），3.39-WL 那份是 **2026-10-30 14:06**（`workenv/gate/mtimes.txt`）；现在全仓同名件也只有这两份（`workenv/gate/envwhere.txt`）⇒ 10-18 那次阅读的来源只能是**线上教程**，不是本地文件；
  - **行号只对上 3.39 那一版**：52＝"用户名：root，密码：fmsh"那行、116＝"选择 `100mbps` 全双工"那行，都在 `repos/official/tutorial/icraft_tutorial/WL/Part 0 env_setup.md` 里；3.31 那份同一句在 77／135（逐行核验 `workenv/gate/envsetup.txt`）。
  ⇒ 结论：这 3 条**一直引的是 3.39 版正文**，正则改正则之后它们"通过"也不是巧合——`resolve()` 的 `hits[0]` 恰好落回同一个 release。**待她裁第十节第 7 行后就地改成带全路径的形式（一个字还没改）**，那才是把"靠巧合通过"变成"写明版本"。
- **本轮我自己犯的实质错，门禁抓不出来（工具侧结论，本体记在 [[交付物数字审计num-audit]] 坑 7）**：上一版第九节第 2 条那句"本仓也没有 x86_64 Linux 版 CLI"是**错的**，而它没被任何一项检查报出来——因为 `num-audit.py` 的 `build_index()` 在 `os.walk` 里排除了 `largefiles`（实测源码那一行 `dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "largefiles")]`），B 项只回查**已写成 `文件:行号` 的引用**，不校验"我搜过哪些目录"这类负断言。⇒ 口径：**"本仓没有 X"这种句子不在门禁覆盖面内，必须自己把搜索面写出来**（`repos/official`／`largefiles`／`workenv`／`source` 是四个互不覆盖的地方，我上一版只看了第一个）。这条与她"任何模型条目必须落到 config 级实测证据"是同一条纪律的文档版。

- **同一类错本轮犯了第二次，这次漏的是"远端主机的另一半盘"**：上一版那句"校机跑不了"的四条 RC 全部来自 **C 盘与 PATH**（`where.exe gcc／cmake／make` 各报"用提供的模式无法找到文件"、`C:\` 顶层目录 11 个里没有 `msys64`）——**而这套环境的调用方式本来就是绝对路径**：`wiki/SOP/交叉编译主机路由SOP.md:12` 那行写的编译工具链就是"Arm GNU 10.3-2021.07（i686-host，靠 WoW64 跑）＋ cmake／ninja ＋ 九件 donor"，`wiki/SOP/交叉编译主机路由SOP.md:4` 那句"盘上只剩 `D:\yzd\WCIS\crosswin` 一个根，卡上所有路径就是它"，`wiki/SOP/校机交叉编译环境搭建SOP.md:41` 那行连 bash 都是 `D:/yzd/MSYS2/usr/bin/bash.exe`。⇒ **口径再加一条：判"某台机上没有 X"要过三面——所有盘（`Get-PSDrive -PSProvider FileSystem`）、PATH、以及本仓自己写给那台机的那页路由文档**；`where` 找不到只证明"PATH 里没有"，`C:\` 顶层看不到只证明"C 盘没有"。这条与上一版那条同体，已一并写进 [[交付物数字审计num-audit]] 坑 7。
