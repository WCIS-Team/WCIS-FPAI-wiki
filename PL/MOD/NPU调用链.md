# NPU调用链

> **本页回答什么问题**：板子上那颗 NPU 到底是被哪一行代码、通过什么接口调起来的；数据怎么进去、结果怎么出来；以及"内核里看不到 NPU"为什么和"一直在用 NPU"同时成立。
> **前置阅读**：[[芯片]]（AIU 在芯片里的位置）、[[板子（除芯片）]]（PL DDR 与 GT 的板级归属）。板端取证清单与两条公开更正登记在 [[板卡镜像实测取证]] 第十二节。
> **判据等级**：A＝板上实测原文，B＝厂商源码或手册直证，C＝推断。源码路径都相对 `S:\apps\llm\agentwork\build\fpai_demo_app`（厂商 `fpai_demo_app.rar` 解包件，口令见 [[板端我方代码与产物台账]] 的登记口径）。

## 一、TL;DR

- NPU（厂商在芯片层叫 **AIU**，在运行时层叫 **Icore**）**从 2026-09-29 通路跑通那天起就一直在用**，日志 `[ICORE][0][Buff1] icore=…ms` 就是它每层耗时。
- 调它的不是内核驱动，是 icraft 包带的用户态库 `libaxizg330aiu.so`：它自己 `open("/dev/mem")` 把物理地址窗口 `mmap` 进进程，再 `open("/dev/udmabuf0")` 拿 PS DDR 的 DMA 缓冲。**所以 Linux 侧查不到它**——`/proc/iomem` 只列被驱动 claim 过的地址，用户态直访不需要 claim。**10-05 用 strace 实证（A）**：映射长度＝udmabuf **128 MiB**、`/dev/mem` 两个窗口各 **16 MiB**（基址就是 URL 里的 `npu=0x40000000`／`dma=0x80000000`）；库内**没有任何自有 `ioctl`**；附到跑着的直播进程 14 s，`ioctl`/`mmap` 计数为 **0** ⇒ 推理路径不在系统调用上。
- 现役这条链**一次内存拷贝都没有**：摄像头帧由 PL 直接搬进 NPU 输入张量在 PL DDR 的编译期物理地址，NPU 就地读。
- 硬件后处理（DetPost）产检测框，**置信度阈值 `conf` 是两级串联的过滤**：既回写硬件里的量化门限 `data_thr`，又在 CPU 侧对反量化后的乘积分再筛一遍（12.3 更正，扫描读数见 [[板卡镜像实测取证#十三、conf 门限扫描（D-31 队列第 ② 项，2026-10-04 实测）|板卡镜像实测取证——十三]]）。

## 二、执行 YOLO 的七跳

| 跳 | 干了什么 | 出处（B 级＝源码直证） |
|---|---|---|
| 1 | yaml 里 `pipeline -> device` 那串 URL（形态 `axi://zg330aiu?npu=0x40000000&dma=0x80000000`）被读进 `fpai_cfg.device_url` | `examples/1_single_input+ai/PLin+SingleNet+HDMI/src/sdicamera+yolov5+hdmi.cpp:113` |
| 2 | `Device::Open(device_url)`：**按 URL 的 host 名运行时加载** `libaxi<host>.so`，`zg330aiu` → `libaxizg330aiu.so`（另一颗 `libaxiql100aiu.so` ＝ Buyi/QL100）。A 级证据：`ldd` 显示三颗二进制都不链接它，库内含字面量 `/dev/mem`、`/dev/udmabuf0` | 同上 `:182`；板上取证见 [[板卡镜像实测取证]] 12.1 |
| 3 | 库把 URL 里两个**物理基址**对应的窗口 mmap 进用户态。**寄存器面**＝`device.defaultRegRegion().read/write`；**PS DDR 侧 DMA 缓冲**＝`device.getMemRegion("udma").malloc()`。**映射长度已实测（A，10-05 strace）**：`/dev/udmabuf0` → **128 MiB**（134,217,728），`/dev/mem` 两次各 **16 MiB**（偏移 `0x40000000` 与 `0x80000000`，正好是 URL 里 `npu=`／`dma=` 那两个基址），权重 `.raw` 只读映射 8,976,737 B | API 用法散在 `deps/modelzoo_utils/include/et_device.hpp`、`pipeline/io/input/sdicamera.hpp`；syscall 原文见 [[板卡镜像实测取证#十四、strace 抓 NPU 调用序列（2026-10-05）|板卡镜像实测取证——十四]] |
| 4 | **装模型**：`Network::CreateFromJsonFile(json)` 读编译产物 JSON（算子图）＋ `lazyLoadParamsFromFile(raw)` 读权重 → `viewExcept(view_except_op_ids)` 把列表里的算子从网络里"看穿"掉 | `deps/modelzoo_utils/include/icraft_utils.hpp:649-650`；`ai_example/yolov5_npu_actor.hpp:202` |
| 5 | **建会话**：`Session::Create<ZG330Backend, HostBackend>`，每个内存 chunk 调一次 `apply()` 把图下发到设备。注意 yaml 里 `run_backend` 那串**不驱动这条分叉**——`yolov5_npu_actor.hpp:207` 把后端名硬编码成 `"zg330"` | `icraft_utils.hpp:674-711`；`yolov5_npu_actor.hpp:211` |
| 6 | **输入零拷贝**（整条链最巧的一跳）：从 `forward_info->value_map[v_id]->phy_addr` **反查**出 NPU 输入张量在 **PL DDR** 的编译期物理地址 → 写进 ImageMake 基址寄存器 `0x80000400 + 0x114` → 硬件把 SDI 帧直接搬进那个地址 → `Tensor::setData(memchunk, phy_addr - chunk->begin.addr())` 包一个指向 PL DDR 的张量交给 `forward()`。**前提**是源码注释那句"PLIN 工程，基本需要保证输入算子被 view 掉，否则无法获取到 phy addr"——这就是换输入尺寸必须重认 `view_except_op_ids` 的原因 | `pipeline/actor/sdicamera_input_actor.hpp:95-118`（日志 `Imagemake output{}, plddr addr={:#x}`）；`et_device.hpp:989-1099` |
| 7 | **推理与取结果**：`forward()` → `waitForReady()`（**轮询，不是中断**）→ `device_.reset(1)`；`[ICORE]` 日志里 `icore=` 包住这三段，`wait=` 是排队等空档。类名 `MultiYolov5IcoreActor` | `yolov5_npu_actor.hpp:112/278/285/302/331/367/368/372-376` |

**两跳配套动作**（不属于"跑一次 YOLO"，但少了它就没有输入、也没有框）：

| 配套 | 干了什么 | 出处 |
|---|---|---|
| 取帧 | 把目标地址 `>>3` 写进 `0x40080050`，再往 `0x40080004` 写 1 触发搬运，然后轮询 `0x40080058`（**bit0 = done、bit2 = error**；出错且未 done 时软件走 `0x70` 软复位并等 `0x74` bit0）。**`>>3` 的解释更正（2026-10-15）**：代码就是 `memchunk->begin.addr() >> 3` ⇒ 该寄存器以 **8 B（64 bit 字）为单位**（低 3 位恒 0）；原文猜的"512 bit 总线＝64 字节一拍"与 `>>3` 对不上（那应是 `>>6`） | `pipeline/io/input/sdicamera.hpp:249-293` |
| 出框 | 模型 JSON 里带 `customop::DetPostZG` 算子 → 解码与 NMS 在 NPU 侧那一步产出，PS 只做坐标回映射与画框 | `include/NetInfo.hpp:217-228`；`sdicamera+yolov5+hdmi.cpp:287` |

## 三、走不走硬件后处理，由什么决定

| 说法 | 结论 | 证据 |
|---|---|---|
| yaml 的 `detpost: true` 是开关 | **错**（已公开更正） | 分叉只看**网络 JSON 里有没有 `DetPostNode`/`DetPostZGNode`**：`NetInfo.hpp:219/225` 据此设 `DetPost_on`，`sdicamera+yolov5+hdmi.cpp:287` 判它。yaml 那个键只被读进 `Yolov5Config::DETPOST`（`yolov5_npu_actor.hpp:35`）再在 `PrintYolov5Config` 打印一遍（`:60`），**没有任何消费者** |
| 置信度阈值 `conf` 是 CPU 后处理参数 | **半对（10-04 再更正：它两处都筛）** | **硬件那一处**：`updateDetpost`（`et_device.hpp:666-697`）在 yaml `conf` 与 DetPost 算子的 `data_thr` 不一致时 `setAttr("data_thr")` **把新值回写进硬件算子＝改 NPU 侧量化门限**，公式 `scale = ln(1/conf_new−1)/ln(1/conf_orig−1)`（`calculate_scale`，`et_device.hpp:653-664`）。**CPU 那一处**：同一个 `yolov5_cfg.CONF` 还作为 `THR_F` 传进 `post_detpost_plin`（`src/sdicamera+yolov5+hdmi.cpp:290-292`），在 `get_cls_bbox` 里对 `sigmoid(obj)×sigmoid(cls)` 的乘积分再筛（`ai_example/postprocesses.hpp:495` 起）。**两版模型自带的 `data_thr` 也确实不同**（`[-15,-18,-19]` vs `[-14,-17,-19]`，从各自 JSON 直接读，`NetInfo.hpp:100-112` 在回写**之前**打印），所以"检测框计数不可跨版本比大小"有**两个**独立来源，实测对照见 [[板卡镜像实测取证#十三、conf 门限扫描（D-31 队列第 ② 项，2026-10-04 实测）|板卡镜像实测取证——十三]] |
| `fpga_nms` 决定要不要 NMS | 半对 | 它只影响 `post_detpost_plin` 内部选硬 NMS（寄存器 `0x100001C00`）还是 CPU NMS，不决定走不走 DetPost |

## 四、两种设备 URL，以及 socket 到底是什么

**先把名词钉死**：`axi://…`、`socket://…` 里的前半段是一个 **URL scheme**（"这套地址该怎么解析"的标记），**不是一种网络协议**。真正的传输在库里实现。

| scheme | 谁当客户端 | 谁持有 NPU | 源码位置 |
|---|---|---|---|
| `axi://zg330aiu?npu=…&dma=…` | **板子自己**（aarch64 Linux 分支） | 本板 PL 里的 AIU，寄存器直接 mmap | `icraft_utils.hpp:530-544`（`#elif defined(__aarch64__)` 分支） |
| `socket://<name>@<ip>:9981?npu=&dma=` | **PC**（`_WIN32` 或 x86 Linux 分支，编译期就分好了） | 另一台持有 AIU 的机器，本板只是客户端 | `icraft_utils.hpp:476/484`（Win）与 `:511/519`（x86 Linux） |

三条必须同写的限定（都是这轮才查清的，**上一轮我说"＝从另一台机器远程用这块板的 NPU"说满了**）：

1. **`socket://` 只在 x86/Windows 编出来的工具里生成**，板端 aarch64 分支永远是 `axi://`。所以它的正确读法是"PC 当客户端去连一台服务端"，而不是"板子可以被远程调用"。
2. **厂商给的 ZG330 远程目标不是真板**：Python 侧拼的是 `socket://haps-zg330@{ip}:5001`（**HAPS** ＝ Synopsys HAPS 硬件原型平台，厂商在没有真板时跑 ZG330 位流的仿真机）；`icraft-run --help` 的示例同样写 `ZG330,socket://haps-zg330@192.168.124.24:5001;Host`。端口 **9981 是 Buyi/QL100 那条**的默认。Python 侧 aarch64 的 zg330 分支是 `TODO` → 直接 `NotImplementedError`（`pyrtutils/icraft_utils.py:88/96-103`，B）。
3. **本板上没有任何进程在听这两个端口**（A：`ss -ltnp` 只有 `127.0.0.53:53` 与 `0.0.0.0:22`）。

那"服务端"的料在不在板上？在——`/usr/lib/aarch64-linux-gnu/` 里有 `libirpc_core.so`（355,328 B）、`libirpc_port_tcp.so`（166,912 B）、`libirpc_port_pcie.so`（171,864 B），头文件 `/usr/include/icraft-irpc/` 给出结构：`core/{client,codec,server}.{hpp,tpp}` ＋ `port/{base,pcie,tcp}` ＋ `utils/{crc,safemap,threadpool}.hpp`（A，`ls -R`）。符号表里能读出协议形态（A，`nm -D`）：`irpc::client::getNewPktID`、`runReceiver_wait`、`runReceiver_async`、`isReceiverRunning`、`test_echo`、`irpc::server::async_wait`——**带包序号、带 CRC、请求-响应式的自定义 RPC，跑在 TCP 之上**（还有 PCIe 端口的实现，说明同一套帧也能走 PCIe）。**结论**：想让 PC 远程用这块板的 NPU，得自己写一个链接 libirpc 的服务端程序把 `axi://` 设备暴露出去，**厂商没给 example**（C：可行性的上限就在这，没实测）。

## 五、板上现成的离线推理工具 icraft-run（新发现，后续实验的手术台）

`/usr/bin/icraft-run`（449,552 B，属 `icraft` 包，A）是厂商的单张图推理 CLI，`--help` 实测读到的关键参数：

| 参数 | 帮助文本原话里的含义 | 对我方的用处 |
|---|---|---|
| `--json`／`--raw`／`--imodel` | 算子图／权重／整模型 | **不碰 SDI 采集通路**就能跑一次 NPU，做精度与门限实验比 demo 干净 |
| `--input` | 图片或 `.ftmp` 文件（必填） | 静态图输入 → 结果可复现，是回归基线的前提 |
| `--backends` | 示例清一色是 `Host` 或 `socket://…`；文本写"Only Support Host/BY/ZG330 backend" | **板上跑得通，A 级实测（2026-10-04）**：`--backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host"`。两个必要条件：① **必须带 `;Host`**，只写 `ZG330,axi://…` 会在 `Session::bindToBackendsByOrder` 处 fatal——`Check failed: (is_bound) is false, Op is NOT bound to any backend, op_id = 0, type_key = icraft::xir::InputNode`（`Input`/`Output` 两个算子的 `compile_target` 是 `@hostt`，没有 Host 后端就没人接）；② URL 里有 `&`，shell 侧必须整体加引号。跑通时的头部日志：`Device Protocol: axi`／`Device Name: zg330aiu`／`icore: FMSHZGV3TECH-AID - 24160628`／`device: 25122301`。**单张 352×640 图整网 12.8 ms，其中硬件段 5.37 ms**（`DetPostZG` 自己 0.080 ms）。**2026-10-30 补**：`--backends Host`（不带 ZG330）能直接吃 `_ZG`＝generate 档的件并逐层落 ftmp ⇒ generate 段的回归不必上板；实测读数、三条边界与复现命令见 [[官方demo教程与skill审计]] §3 |
| `--precheck` | 算子支持性预检 | 与既有口径一致：算子能不能跑的真值来自 precheck，不来自文档 |
| `--frequency` | 设 ICore 时钟，浮点，单位 MHz，默认 **860** | 但 strings 里有 `ZhugeDevice does not support setting clock frequency now`（A）→ **ZG330 上改不了频率**，860 MHz 只是显示值 |
| `--dump_format` | `SFB/SFT/SQB/SQT/HQB/HQT`，不传就不 dump | 分层导出中间特征图（量化前后对比）——算子级对数与量化排查的官方入口 |
| `--ocmopt` | strings：`Ocm optimization parameter is only supported on ZhugeDevice` | **OCM**（on-chip memory，NPU 片上缓存）优化是 Zhuge 专属能力 |
| `--save_snapshot`／`--load_snapshot`、`--merge_hardop`、`--compress`、`--close_mmu`、`--fake_qf`、`--wait_time` | 见 `--help` | **2026-10-30 分两档**：`--fake_qf`、`--save_snapshot` 有官方文档口径了（前者**仅对 HostBackend 有效**、后者**只支持 BY 阶段的网络**，所以别指望用它省掉板上 132 s 的 `apply`；原文行号与两种使用场景见 [[官方demo教程与skill审计]] §3 边界 3、§7）；`--merge_hardop`／`--compress`／`--close_mmu`／`--wait_time` **仍未逐个验证**，记在此处备查 |

**分层 dump 实测（2026-10-04，A）**：`--dump_format HQB --dump_output` 会把**每一个中间特征图**按 `v_id` 落成裸 int8、无文件头（`H`＝host、`Q`＝quantized、`B`＝bytes），落点是 `<cwd>/.icraft/logs/<网络名>/ftmpHQB/<v_id>.ftmp`。尺寸就是张量字节数：输入 `879.ftmp`＝675,840（1×352×640×3 uint8），三个检测头 1,351,680／337,920／84,480（＝44×80×384 等）。**一个坑**：只给 `--dump_output` 不给 `--dump_format` 会**建出三个 0 字节文件**（默认 `dump_format` 是空串，"不传就不 dump"，但目录与文件名已经先建好），看着像写坏了其实是没有格式参数。**这条组合起来就是"改一次门限／换一颗模型不用重编 C++"的离线通路**：JSON 与 raw 直接喂、图直接进 NPU、中间结果按层落盘，PC 侧拿 numpy 就能逐层对数。它替代不了在线链（没有 SDI 采集、没有 ImageMake 零拷贝那一跳），但精度与量化排查该走它。

**同目录还有一颗 `libicraft_pl_sim.so`（203,872 B，A）** ＝ PL 仿真后端，进一步说明厂商的"远程/仿真"路线是给 PC 侧准备的。

## 六、术语表（按她这轮问到的顺序）

| 术语 | 一句话定义 | 在这条链里的位置 |
|---|---|---|
| AIU／Icore | 厂商对 PL 里那颗神经网络加速硬件的两个称呼（芯片层 vs 运行时层） | 日志 `icore=`、URL `zg330aiu` |
| mmap | 把一段地址（文件或**物理内存**）直接映射进进程地址空间，之后读写指针＝读写那块地址，省掉 `read()`/`write()` 的系统调用与拷贝 | `open("/dev/mem")` 之后 `mmap` 出 PL 的寄存器窗口与 PL DDR 窗口 |
| open | POSIX 里"按路径拿到一个文件描述符"的系统调用；`/dev/mem`、`/dev/udmabuf0` 都被当文件开 | 上面那颗库干的头一件事 |
| strace | Linux 的调试工具：附加到进程上，把它每一次系统调用（`open`/`mmap`/`ioctl`/`read`…）连参数和返回值打印出来 | **10-05 已装并跑通（A）**：启动期抓到完整 open/mmap 序列（第 3 跳的长度就是这么来的），稳态附到直播进程上 14 s **零 ioctl／零 mmap** ⇒ 推理循环全靠解引用。它只看 syscall 面，**寄存器写了什么值它永远看不到**；原文与一处公开更正见 [[板卡镜像实测取证#十四、strace 抓 NPU 调用序列（2026-10-05）|板卡镜像实测取证——十四]] |
| vsync 节流 | 摄像头每帧结束会给一个"垂直同步"信号，等于告诉你"下一帧几时好"。SDI 摄像头 30 fps ⇒ 每 33.3 ms 一次。采集侧必须等它，所以 `cam_wait(32.9ms)` 把整条流水线卡在 30.06 fps | 日志 `[Input][0] T(33.2ms)=…+cam_wait(32.9ms)`；**所谓"去掉 vsync 测 NPU 极限吞吐"就是不让它等帧、连续喂** |
| 零拷贝 | 数据不经过 CPU 复制，由 DMA 直接搬到消费者要的位置 | 第 6 跳：帧搬进 NPU 输入张量的编译期物理地址 |
| PLIN／PSIN | 采集通路在 PL 侧完成（现役这条）／输入从 PS 侧（V4L2 等）进来 | 判据差别见 [[板卡镜像实测取证]] 第十节 |
| data_thr | DetPost 算子上的量化门限属性，`conf` 回写它就改在这里 | 第三节 |

## 七、PS 侧内存与 PL 侧内存的分层（2026-10-15 新增，答"权重到底驻在哪里"）

起因是三条我自己的措辞被人追问，追问是对的——**"993 MB 的板跑不动 1.3 GB 档"这句话从一开始就问错了资源**。分层事实与三条更正如下。

### 7.1 分层事实（厂商文档原文，B 级）

`C:\Icraft\CLI v3.39.0\docs\axizg330aiu\index.html`《一 设备资源》把 `axi://zg330aiu` 这颗设备拆成四块：

| 区域 | 文档原话 | 归属 |
|---|---|---|
| MemRegion `udma` | "使用一块系统的 CMA 空间实现的交换空间，**用于操作系统和 PL DDR 之间的数据交换**" | PS 侧 RAM 里划出来的一块中转站 |
| MemRegion `plddr` | "NPU 和 PL 所共同使用的 **PL DDR** 内存" | PL 侧独立 DRAM |
| MemRegion `ocm` | "NPU 内部的 OCM 内存" | NPU 片内 |
| RegRegion `npu` | "NPU 上的寄存器区域" | 挂载点默认 GP0＝`0x4000_0000`，DMA 默认 GP1＝`0x8000_0000` |

同一套说法在布衣（QL100T）页也有，只是它多一个 `ocm` 之外的名字 **ETM**（`docs\buyibackend\index.html`：`compressFtmp`"显著减少网络在 ETM 上（即 PL DDR）的内存占用"、`getDepolySize`"获取 session 在 etm 占用的总内存字节大小"）——**ZG330 后端的 API 也在用 ETM 这个词**（`zg330backend.pyi` 里 `instr_phy_addr` 写的是"指令在 etm 上的真实物理字节地址"），所以 `plddr`＝ETM＝PL DDR 是同一块，B 级。

数据放哪的判据在《软件排布和硬件排布》（`docs\demo\samples\customop\others\layout.html`，B 级）：

> 软算子在 CPU 或 GPU 上计算，输入输出以及参数存储在 **PSDDR** 上…；硬算子在 NPU 或 PL 上计算，输入输出及参数存储在 **PLDDR** 上…

### 7.2 一次 Qwen2 推理里，每样东西落在哪

| 东西 | 落在哪 | 证据与级别 |
|---|---|---|
| 权重 1,314,012,420 B（1.224 GiB） | **PL DDR**，不在 PS 侧进程里 | 文档口径 B；**A 级反证**：`lazyLoadParamsFromFile` 之后进程 `VmRSS` 只有 546,768 kB，1.224 GiB 装不进去；板上异常原文出现 `plddr_chunk byte_size:12`（台账 #196，A） |
| 图的输入张量（v_id1 等） | PL DDR 的 `plddr_chunk`，由 `host_chunk` 喂进去 | 同一条异常原文，A |
| PS→PL 的中转缓冲 | `udma` ＝系统 CMA（本板 256 MiB）里切的一块 | `dmesg: cma: Reserved 256 MiB at 0x30000000`＋`CmaTotal 262,144 kB`（A）；跑一轮 `CmaFree` 130,784→**8,860 kB**＝吃掉约 122 MB（A） |
| NPU 片内常驻 | `ocm`，由 `ZG330Backend.ocmOptimize(option)` 选方案 | API 存在（A，`zg330backend.pyi`）；`initSession` 默认传 `ocm_option=1`＝全局评分法（A，厂商 `icraft_utils.py:139`） |
| KV cache 的 numpy 数组（PS 侧那份） | PS 进程 RSS | Qwen2＝48×`[1,2,512,64]`fp16＝**6 MiB**；Qwen3＝56×`[1,8,512,128]`fp16＝**56 MiB**（B：按图声明的 shape 算的字节数，未上板） |

### 7.3 三条公开更正（我写错的措辞）

1. ~~"993 MB 板跑不了 1.3 GB 档"~~。**993 MB 是 PS 侧 Linux 可见内存**（bootargs `mem=1024M` 封顶＋CMA 256 MiB 扣减 ⇒ `MemTotal 1,017,708 kB`，A 级读数），而权重的归属地是 PL DDR，两者不是同一块内存，拿 PS 内存去否定 1.3 GB 档不成立。**真正会约束"装不装得下"的是 PL DDR**：手册口径 2 GB（B，见 [[板子（除芯片）]]），Qwen2 的 1.224 GiB 占 61.2 % 且实测跑通（A），我方 Qwen3-0.6B 的 1.493 GiB 占 74.7 %——**剩下的余量够不够放 INSTR＋FTMP＋KV，现在只有文档口径、没有实测判据**，开口项见 [[哪些要跟厂商要]] 第三节。
2. ~~"惰性加载 ⇒ 不整颗驻 RAM"~~。准确说法是**不整颗驻进程 RSS**。权重读进来之后交给 PL DDR，而 PL DDR 是**易失的独立 DRAM**（掉电即失，也不是位流配置存储器）——所以"PL 又没持久化储存"这句是对的，正因如此每次起 session 都要把 1.224 GiB **重放一遍**，这就是 `apply()` 132.1 s 的用途（时长 A 级，机制 B 级）。件本体（`.raw`）的持久化位置是 eMMC 上的文件，不是 PL。
3. **"PL 的峰值 RSS"这个指标本身不存在**（这是提问口径的澄清，不是我方写错的东西）：RSS 是 PS 侧**按进程**的量，PL 侧没有进程、也没有 `/proc`。这条链上能给的只有三样：PS 侧峰值 `VmHWM`＝**673,848 kB**（A，STEP4 末）；PS↔PL 中转池 `CmaFree` 最低 **8,860 kB**（A）；PL 侧各段占用要靠 `ZG330Backend.logic_segment_map`（init 时生成）／`phy_segment_map`（apply 后生成）逐段读 `byte_size`——**探针脚本 `S:\work\WCIS\workenv\qwen3\board\q3_probe.py` 已写好、未执行**（10-15 卡在位流身份门禁，见 [[板端我方代码与产物台账]] #200）。

### 7.4 CMA 是什么（一句定义＋板上判据）

**CMA＝Contiguous Memory Allocator，内核预留的一块"物理地址连续"的内存池**。DMA 描述符要的是物理地址，普通 `malloc` 出来的页在物理上是散的，所以驱动要么在运行时凑连续页、要么用开机时就预留好的这块。本板开机预留 256 MiB（`dmesg: cma: Reserved 256 MiB at 0x0000000030000000`，A），`/proc/meminfo` 的 `CmaTotal 262,144 kB` 是总额、`CmaFree` 是仅剩的实时读数；用户态通过 `/dev/udmabuf*` 拿到它（视频链与 `udma` 用的是同一池，**占用方未逐一归因**；**11-03 空载低读数那部分已结案＝页缓存，见本节末尾的结案段**）。

**11-02 把这笔账算平了（A，板上现读）**：

| 项 | 读数 | 出处 |
| --- | --- | --- |
| 池子大小 | `CmaTotal 262,144 kB`＝256 MiB，**编译期常量**：`CONFIG_CMA_SIZE_MBYTES=256` 且 `CONFIG_CMA_SIZE_SEL_MBYTES=y`；**DT 里没有 `linux,cma` 节点**、bootargs 里**没有 `cma=`** | `/proc/config.gz`、`/proc/device-tree/`、`/proc/device-tree/chosen/bootargs` |
| `udmabuf0` 静态占用 | DT `udmabuf@0/size`＝**0x08000000＝128 MiB**；`dmesg` 实测 `phys address = 0x30100000`、`buffer size = 134217728`（在 CMA 窗 `0x30000000–0x3FFFFFFF` 内） | `dmesg` 6.24 s 三行 |
| 空载余量 | `CmaFree 130,768 kB`＝**127.7 MiB**，与算式 `262,144 − 131,072 ＝ 131,072 kB` 只差 **304 kB**（别的零碎）⇒ **池子的一半被 `udmabuf0` 开机就端走了** | 同上两列 |

⇒ 所以"空载还剩 130 MB"不是"池子被视频链动态占着"，而是 **`udmabuf0` 那 128 MiB 开机就被划走**。11-02 两种态都抓到过：`gop15` 那版链在跑时**一个进程都没映射 `udmabuf`**、`CmaFree` 仍是 130,768 kB（划走但不映射）；换成 `mvx6` 那版后 `wcis_camera_owner` 把整段 128 MiB map 进来、`CmaFree` 落到 96,528 kB。⇒ **这 128 MiB 不管谁用都已经不在池子里**，映射与否只影响"谁在用"。

**一处更正（我 11-02 上一轮说错了）**：我曾说"ERNIE `apply` 借走的 126 MiB ≈ 就是 `udma` 那 128 MiB"。**这条不成立**——`udmabuf0` 开机就分配完了，`apply` 期间再掉的 126 MiB 是**第二次**分配，占用方**没归因**（`CONFIG_CMA_DEBUGFS` 没开，`/sys/kernel/debug/cma` 不存在）。能确定的只有量级：ERNIE 借 **126 MiB**、Qwen3 `s3` 借 **128 MiB**、Qwen2 真推理借 **119 MiB**，三者都在"把剩下那半吃光"的量级上。

**"借还"不等于"加载完就还"（11-02 澄清）**：ERNIE 一条命里的 `CmaFree` 是四段——`apply` 期谷底 **1,532 kB** → `apply` 结束回弹 **23,608 kB** → 真推理 24 步时 **6,260 kB**（进程未退，见台账 §廿九 那条）→ **进程退出**才回到 128–129 MB。⇒ **只要会话活着，CMA 里就有 100+ MiB 被它按着**；"借还"指的是不跨进程常驻，不是"装完就还"。所以"能不能同窗"要按**会话存活期**算，不能按"加载那一刻"算。

**同一天更晚一轮补一条冲突（17:02–17:47 UTC，未归因，别当已解决）**：KV 常驻探针那一轮（`e41_kvres.py`，`Watchdog` 从建会话前一直采样到收尾）里，`apply` 带 12 步**全程看不到 `CmaFree` 低于空载值 130,660 kB**（唯一例外是主机往返最重的 A2 档，谷底 124,312 kB）。⇒ 上面那句"`apply` 期谷底 1,532 kB／按着 100+ MiB"**在这条探针路径上没复现**。候选解释＝`.raw` 参数上传路径不同（`lazyLoadParamsFromFile` 何时真搬权重）／同窗占用方不同／探针与现役对话链的加载序列不同——**三条都没验**，读数与口径差的正本＝[[KV常驻设备侧实测]] 第三节与第六节。**但"借 126 MiB"这件事本身没有被否掉**：同一块板 20:50 UTC 复查时 `CmaFree` 只剩 **3,544 kB**（我 17:47 收尾时读到 130,660 kB），也就是空载基线之上又被按住 **124.1 MiB**（`130,660 − 3,544 ＝ 127,116 kB ÷ 1024 ＝ 124.1 MiB`），占用方**未归因**——当时板上只有 `klar/voice_gateway.py`／`klar/console.py` 两颗进程（18:11 起）在跑，没有 `e41_` 类任务，且 `grep -l udmabuf /proc/[0-9]*/maps` **零命中**⇒ 不是 `udmabuf` 映射，是另一条路。**"串行是唯一无风险优化"这个结论不受影响**（那是门禁设计，不依赖具体借用量级），但**起跑门禁现在不满足**：`CmaFree ≥ 126 MiB` 在这一刻过不了。

**⇒ 上面两处"未归因"（本段的 124.1 MiB 与下一节窗口裁剪那轮的 11,104 kB）11-03 结案，见紧接下面的结案段。**

**11-03 结案：那些"空载只剩几 MB／十几 MB"的 `CmaFree`＝页缓存，不是占用（A）**。取证脚本＝`S:\work\WCIS\workenv\ernie\board\cma_attr.sh`（板上 2 s 采样，73 行落 `/tmp/cma_attr/sample.txt`；本地副本 `workenv/ernie/logs/cma_attr_readback_1103.txt`）。跑的是现役窄读探针 `e41_narrow.py`、`E41N_STEPS=4`。

| 板钟（UTC） | 事件 | `CmaFree` | `MemFree` | `Cached` |
| --- | --- | --- | --- | --- |
| 09:07:07 | 起手（前一小时刚读过两颗 ≈1.0 GB 的 `.raw`） | **3,660 kB** | 79,320 kB | — |
| 09:07:09–09:09:06 | 会话存活期（60 行采样） | **0～12 kB** | 46,924～88,984 kB | — |
| 09:09:08 | 会话退出那一刻 | **30,900 kB** | 436,516 kB | — |
| 09:09:29 | 退出 +20 s | **30,936 kB** | 434,524 kB | — |
| 退出后数分钟 | `echo 3 > /proc/sys/vm/drop_caches`（手动一次性命令，板上没落盘，时刻按会话顺序推） | **130,188 kB** | 631,092 kB | 348,108→**54,136 kB** |
| 09:49:09 | 分支冒烟又读了一遍 `E42-decoder_ZG.raw` 之后复看 | **32,780 kB** | 352,748 kB | 320,812 kB |

三条判据：

1. **它跟着页缓存走，不跟着进程走**：`drop_caches` 后 30,936→130,188 kB（同刻 `Cached` 348,108→54,136 kB、`MemFree` 330,372→631,092 kB），再读一遍 `.raw` 又掉回 32,780 kB ⇒ **空载 `CmaFree` 低 ≠ 池子被按住**：那些页是可回收的，CMA 分配器本来就能把它们抢回来——这也解释了 [[窄读KV回抄实测]] 那条"`CmaFree` 3,968 kB 起手 `apply` 照通、12 步数值全等"。**不是泄漏、不需要重启**。（本节"板上口径"那条"`CmaFree` 是这块池唯一的实时余量读数"要按此打折：它混着可回收页缓存，判"够不够"得连 `Cached` 一起看，或先 `drop_caches` 取基线。）
2. **直播链判否**：本开机周期（`up 15:39`）链从未起过——`/root/live.disabled` 在、`pgrep` 无 `wcis_*`／`camera_owner`、`/tmp/live.stat` 不存在、`/sys/kernel/debug/dma_buf/bufinfo` 在 73 行采样里**每行 0 objects** ⇒ 那些低读数与视频通路无关。
3. **`udmabuf0` 一直都在**：73 行每行 `udma_dev=1`。**由此更正窗口裁剪那一轮（11-03 01:14 收尾）写的"无 udmabuf 设备"**：准确口径是**零颗动态 udmabuf 实例**，出厂 DT `udmabuf@0` 那颗静态的（128 MiB，开机 +6.35 s 建，phys `0x30100000`）从开机即在、`/dev/udmabuf0` 一直在。同源的另一条错法：**`lsmod | grep udma` 空不等于"没有"**——u-dma-buf 3.2.5 是**内建**，`lsmod` 不列内建模块，那条负证据当初无效（更正已回写进 [[编译窗口裁剪实测]] §八）。

**结案的范围要说清（别把它当成 11-02 那条冲突的答案）**：页缓存这条只解释**空载低读数**（11,104／3,544／3,660／32,780 kB 那几个），**不解释**上面 17:02–17:47 那轮"`apply` 带 12 步全程 `CmaFree` 不动在 130,660 kB"——那一轮的困难方向是**看不到下降**，与页缓存把它压低的效应相反，三条候选解释仍未验。**会话期的借用量级本轮也没分离出来**：会话存活期 `CmaFree` 打到 0～12 kB，但那里面既有真分配也有读盘新增的页缓存，要分开必须**会话中途** `drop_caches`（本轮没做）。⇒ 本节"ERNIE 借 126 MiB／Qwen3 借 128 MiB／Qwen2 借 119 MiB"三个数**降级为量级参考**（B）：与"会话期把余量打到近 0"这条一致，但都没做缓存基线。

两条板上口径，别踩：

- **`MemAvailable` 不能当起跑门禁**——CMA 那 256 MiB 不在 `MemAvailable` 的账里（10-10 那批 OOM 就是被这条误判的，见 [[板卡镜像实测取证]] 的内存段）。
- **`CmaFree` 是这块池唯一的实时余量读数**，且**上限天然只有 128 MiB**：视频链不在、什么模型都不跑时它也是 `130,768 kB`，不是 256 MB。

**"CMA 还能优化吗"——三条能动的路，都到内核/DT 层（未执行，要她点头）**：

1. **扩池（`CONFIG_CMA_SIZE_MBYTES`）**：要重编内核。代价＝**直接从 PS 可用的 754,920 kB 里再切**（`mem=1024M` 固定），LLM 省不了 PS 内存、只是把 CMA 的余量做大；**本机不做内核编译**这条纪律下不可行。
2. **缩 `udmabuf0`（DT `udmabuf@0/size`）**：理论上这是唯一有真实收益的一条，但**11-02 实测否掉了"它超配"这个前提**——现役视频链 `wcis_camera_owner` 把 `/dev/udmabuf0` **整段 128 MiB 映射进来**（`/proc/2774/maps`：`7f64000000-7f6c000000 rw-s /dev/udmabuf0`，`0x8000000`＝128 MiB，A）。所以缩 DT 会直接改观视频链的工作缓冲，**不是"改个数字"**。
   链路对 CMA 的净占用也量到了（A）：链路四进程在跑、22 s 内 12 次采样 `CmaFree` **恒定 96,528 kB**（零波动）；更早那版链（`gop15`）在跑时读到 130,768 kB ⇒ 两版链的 CMA 用量差 **34,240 kB**，且现役这版会把 `udmabuf0` 打开。**结论：要缩必须先改视频链自己的缓冲布局，风险与收益都比"改个 DT 数字"大得多；暂不做。**
3. **运行时不可调**：`u-dma-buf` 3.2.5 是内建驱动、`/sys/module/udmabuf/parameters/` 不存在，`/sys/class/udmabuf/` 也没有；CMA 侧 `CONFIG_CMA_DEBUGFS` 没开。⇒ **没有任何 sysfs/模块参数能改大小**（A）。
4. **唯一无风险的"优化"是串行**：LLM 一次借 126–128 MiB（**量级参考，见本节结案段**），正好等于空载那半（127.7 MiB）⇒ 只要同窗没有视频链，就不会见底。这就是 `113.txt` 协议＋起跑前 `CmaFree ≥ 126 MiB` 门禁在做的事，不需要动内核或 DT。**这条门禁 11-03 起降级为建议**：[[窄读KV回抄实测]] 读到过 `CmaFree` 3,968 kB 起手 `apply` 照通、12 步数值全等；而低读数本身多半是可回收页缓存（本节结案段），所以**别拿单次 `CmaFree` 当硬闸**——起跑前读一次、连同 `Cached` 一起看，或直接先 `drop_caches` 取基线再判。


### 7.5 每步到底搬了什么（答"CMA 中转啥／有没有算子回退 CPU"，2026-11-02）

**算子分布（A，图直读）**：ERNIE 那颗 **1,373** ＝ **1,332 颗 `@zhuget(330)`（NPU）** ＋ **41 颗 `@hostt`（CPU）** ⇒ **97.0 % 在 NPU，3.0 % 在 host**。41 颗的组成：`SliceDynamic`×36（每条 KV 一颗）＋ `Input`／`Gather`／`RopeDynamic`／`CausalMask`／`Output` 各 1。Qwen3 同形：2,177 ＋ 61（`SliceDynamic`×56 ＋ 5 个端点，见 [[LLM上板要求与候选模型对照]] §五）。

⇒ **不是"算子不支持才回退"**：这 41 颗是 LLM 图的合同件（`RopeDynamic`／`CausalMask`／`SliceDynamic` 在官方算子文档里 0 命中），且**每张量一次、不在层内循环**里。结论要分两句说：**图没有完全跑在 NPU 上（97 % NPU／3 % host）；但 CPU 那 3 % 不是性能来源**，真正的 CPU 时间是驱动侧的 `argmax`（8.0 ms/步）＋ padfix 拷槽。

**每步的数据流（A，驱动与图直读）**：

| 方向 | 内容 | 量 |
|---|---|---|
| 上行（42 路） | 1 个 token（4 B）＋ `[1, past_len, 0]` 三值（12 B）＋ **40 条 `[1,8,512,128] fp16` KV 输入**（36 条被 `SliceDynamic` 消费＋4 条零死输入 v_id 38–41） | **40.000 MiB**（`40 × 1,048,576 ＝ 41,943,040 B`，＋16 B 端点） |
| PL 内 | 1,332 颗 `@zhuget(330)` 跑完 **18 层**（＝那 36 条 KV／2） | — |
| 下行（37 路） | logits ＋ **36 条 present** | 整块读 **36.197 MiB**（`36 × 1,048,576 ＋ 206,848 ＝ 37,955,584 B`）；**11-03 起现役 daemon 只读新写那一槽 ⇒ 实际 0.268 MiB**（`36×8×256 ＋ 206,848 ＝ 280,576 B`），整步 463.10 → 437.35 ms（−5.56 %），正本＝[[窄读KV回抄实测]] |
| PS 上 | padfix（`slot0=slot1`）＋ 切槽 ＋ `argmax` | 8.0 ms |

**三处公开更正（写于 11-03；实测轮次＝11-02 17:02–17:47 UTC 板钟；本节初版也写于 11-02）**：上行**不是 36.0 而是 40.000 MiB**——42 路输入里的 KV 是 40 条（含 4 条无人消费的死输入，那条 parser 输入条数门槛的绕过方案欠的债就在这，见 [[ERNIE-4.5-0.3B-PT]] §四），我上一版按"被消费的 36 条"记了；下行**不是 36.0 而是 36.197 MiB**——漏加 logits 那 206,848 B；层数**不是 28 而是 18**（28 是 Qwen3-0.6B 的层数，被我错挂到这颗 0.3B 上；`36 条 KV ÷ 2 ＝ 18` 这条自己就能核，config 级直读在同页 §二）。三处的算式都列在上表，可复核。

⇒ **CMA 中转的是这每步上行 40.000／下行 36.197 MiB 的 KV 往返，不是图**。图与权重（742.2 MiB）全在 `plddr`（PL DDR），`SEGMAP phy` 直读 A 级。之所以要过 CMA：PS 侧那份 KV 是 numpy 数组（物理散页），DMA 引擎只认物理连续地址。**（11-03 更正这一句的适用面：下行已经缩到 0.268 MiB/步——`e41_chatd.py` 现在只读回新写那一槽，见上表最后一行；上行那 40.000 MiB 仍是整份缓存逐步重喂，没缩。）**

**"KV 常驻设备、只出入 1 token"——已实测（11-02 17:02–17:47 UTC，五档跑通＋两档撞门禁），机制成立但净亏，判不做（A）**。上一版这里写的是"文档支持，实测未做（C）"，现在改成实测结论；五档对照读数、两道厂商门禁与复现命令正本在 [[KV常驻设备侧实测]]，此处不复制表格，只记结论与那三条风险的落地：

1. **原地覆盖**：风险成真，且是**静默错数**——present 与 past 绑同一块 chunk 时，12 步链在第 4 步锁死到 token 23，`argmax` 只对 4/12、`top1−top2` 间隙只对 1/12（对照档逐位全等）。**排掉覆盖也没修好**：present/past 分成两块、每步在设备内 `copyFrom` 的那一档同样只对 3/12、第 3 步就偏 ⇒ 错数不止来自原地覆盖。**她给的 63 步 oracle 未执行**（分叉落在第 3～4 步，12 步逐位指纹足以判死；要翻案照新页第八节把 `STEPS` 换成 63）。
2. **padfix**：不进图也不需要重编——设备侧用 `MemChunk.copyFrom` 自拷 `slot0=slot1` 实测 **3.38 ms/步**（比主机侧读回＋拷槽的 42.85 ms 便宜一个量级）；但**省下的这点（39.47 ms）远小于 `forward` 涨上去的 128.15 ms**，净亏。
3. **4 KB 对齐**：**成立**（`defaultMemRegion().malloc(n, False, 4096)` 直接可用，本轮 `_align_probe2.py` 实测四个对齐档全部 `mod 4096 ＝ 0`）。真正卡人的是它旁边那道：**厂商只允许绑 `plddr` 上的 chunk**（`zg330backend.cpp:1127`），想绑到 CMA/`udma` 区直接抛异常 ⇒ "KV 常驻"只能常驻在 PL DDR，而那条路上 `forward` 就是变慢。**这就是"CMA 还能优化吗"的封口答案**：CMA 侧省得下来（会话期 `CmaFree` 零消耗，130,660 kB 全程不动），但收益换不到时间，反而慢 18.5–24.1 %。

**还有一条意外的坑（A）**：`forward(inputs, outputs)` 传进去的用户 chunk **必须同批 `userConnectNetwork` 绑过**；没绑的 chunk（A2 档：37 路全不绑）会**静默返回错数**——第 0 步 `top1` 就和 8 个现役档全部不同（19.6094 vs 20.0938），12 步 `argmax` 只对 1/12。⇒ 用两类接口时"绑"与"读"要成套，别混。

## 八、边界与不做的项

- **极限吞吐不测**（她 2026-10-04 的决定，理由＝怕把板子卡死）。我把风险如实记在这里供复看：最坏情形是轮询循环打满一个核＋PS DDR 带宽被吃满，表现为 SSH 变慢、日志暴涨；`pkill` 掉 demo 即恢复，**没有不可逆动作**。但**按她的决定不做，别重开**。
- **多路 SDI 输入不做**（同轮决定：我方只有一路摄像头，没有多路设备）。
- **NPU 频率调不了**（strings 直证，第四节表 `--frequency` 行）。
- 仍未取证的只剩一处（C）：取帧那步 `>>3` 是否对应 512 bit 总线＝64 字节一拍的地址压缩。**syscall 层看不到它**——它是一次落在已映射窗口内的 MMIO 写，要判只能 gdb 断在写寄存器处，或拿到 linlon-v5／AIU 的寄存器手册。原来的"两个物理窗口的映射长度"与"库内除 `open` 外有无额外 `ioctl`"已在 10-05 补成 A（[[板卡镜像实测取证#十四、strace 抓 NPU 调用序列（2026-10-05）|板卡镜像实测取证——十四]]）。
- **VPU（`/dev/video0`）不提供这条链的任何一环**：它是采集通路之外的编解码 IP，现役 demo 里没有任何进程开它。**硬编本身已由厂商 `vpu::Encoder` API 实测跑通**（10-05，A：720p H.264 ≈217–230 fps、1080p ≈110 fps，同配置码流逐字节确定），**但没接进直播链**——率控项设了不生效、`buffer_count` 只能 6，见 [[板卡镜像实测取证#十五、VPU 硬编取证（D-31 队列第 ③ 项，2026-10-05）|板卡镜像实测取证——十五]]。

## 相关页面

- [[KV常驻设备侧实测]]：本页 §7.5 那句"判不做"的五档对照读数、两道厂商门禁与复现命令
- [[板卡镜像实测取证]] 第十二节：板端 A 级取证清单与两条公开更正
- [[板端我方代码与产物台账]]：插桩的 `hdmi_display_actor.hpp`、部署脚本与 960×512 三件套
- [[哪些要跟厂商要]]：本页第七节里"B 级文档口径、没有实测判据"的那几项（PL DDR 容量、段分配、`apply` 能否省掉）就是那张清单的第三条
- [[组件选型与复用边界]] 第七节：模型选型与必须验证的候选（D-30 定了 v8n 主／v5s 备）
- [[接口契约与数据通路]]：自研 PL IP 准备走的寄存器面（与本页的 `/dev/mem` 直访是**两条不同的路**）
