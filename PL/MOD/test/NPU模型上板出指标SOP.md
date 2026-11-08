---
tags: [SOP]
---

# NPU模型上板出指标SOP

> 定稿 2026-10-15。这页只管一件事：**把一个厂商 YOLO 件从 `.pt` 变成板子上的 AP 与延迟读数，中间有哪几步、每一步用什么判"过了"**。第一次照这套走完全是 yolov8n int8（[[板卡镜像实测取证#十八、YOLOv8n 第一次上板出数（D-31 队列第 ① 项，2026-10-05）|取证——十八]]，AP@[.5:.95] 0.331／NPU 骨干 12.416 ms），第二次是 512×960 档（[[板端我方代码与产物台账#7.2 960×512 输入尺寸档对照包（2026-10-05 上板，尚未跑）|台账——7.2]]，产物已就位）。
>
> **"这是不是完全复刻厂商的、只是搬到板子上？"——模型侧是的，只有两处偏离，别把它说成"全照厂商"**：
> ① 厂商 `postprocess_yolov8.hpp` 的 Linux 分支**不写 per-image 结果 txt**（`saveRes` 整个关在 `#ifdef _WIN32` 里），照原样在板上跑**一个 txt 都产出不了**，而厂商自己的 `calAP.py` 只吃 txt ⇒ 必须打补丁，改的只是输出格式；
> ② 编译**不在厂商工程目录里跑**（那张 toml 的 `jr_path` 会原地覆盖上一版基线五段产物）。
> 除这两处外，toml 的每一个键、量化配方、demo 源码、评测脚本、GT 标注全是厂商包里的原样。视频那条链不是"复刻"，见 [[魔改厂商视频流程部署记录]]。
>
> **10-30 加第十节「换模型的影响面」**：问她"换 NPU 上跑的模型要不要重做位流／改时序"，答案分三层——**位流一般不动、时序完全不碰、换的是 eMMC 上那两个件＋yaml 四处**；只有碰到位流里没有的 CustomOp 硬算子／硬件 YUV2RGB／多路 SDI ／新自研 PL IP 才要重做位流（那时才涉及时序）。另把 `view_except_op_ids` 那条列进坑清单第 14 条。

## 一、六个阶段与各自的"过了"判据

| 阶段      | 在哪台机       | 产物                    | 判"过了"的口径（不是退出码）                       |
| ------- | ---------- | --------------------- | ------------------------------------- |
| 1 选件与定档 | 本机         | 一份 `.pt`＋一张 toml      | 后端档＝**ZG330**；形状有官方现成 `.pt`，不自己重导     |
| 2 编译    | **本机（唯一）** | `imodel/` 五段 json＋raw | 五段文件全在；日志里无 `[F]`／`捕获到错误码`            |
| 3 结构门禁  | 本机         | 一张读数表                 | 输入形状对；`compile_target` 分布对；算子缺口＝0（**这一格是检测类口径，LLM 不成立：见第四节的 LLM 补条**） |
| 4 板端可执行 | 校机         | aarch64 ELF           | `saveRes` 补丁两处都在；NEEDED 闭包过静态门禁       |
| 5 上板    | 本机→板       | `/root/…` 一整套         | 逐文件本地 md5＝板上 md5；`chmod +x`           |
| 6 跑出数   | **板子（唯一）** | 每图一个 txt → AP／延迟      | 冒烟 30 张零空文件 → 全量 RC=0 且 txt 数＝list 行数 |

三台机谁能做什么的总路由在 [[交叉编译主机路由SOP]]；**板上禁止编译**是硬规矩（993 MB 里 256 MB 是 CMA 池，编译会把现役链挤死，见 [[板端内存上限与心跳日志]]）。

## 二、阶段 1：选件与定档

后端档先定，因为 **imodel 与后端绑死**——布衣档的件在悟净上加载不了（[[交叉编译主机路由SOP#一·补 后端档：只用 ZG330（2026-10-15 审计，此后默认）|路由 SOP——后端档]]）。本项目一律 ZG330。

形状这一档**不用自己导模型**，厂商 `2_compile/fmodel/` 里就两颗：

| 文件 | 大小 B | 对应 toml 里 |
|---|---|---|
| `yolov8n_640x640.pt` | 12,897,510 | `inputs = [1, 640, 640, 3]` |
| `yolov8n_512x960.pt` | 12,901,640 | `inputs = [1, 512, 960, 3]`（顺序是 N-H-W-C，**w×h 写出来是 960×512**） |

换档只改这两个键（形状＋`.pt` 路径），量化配方一个字不动，这样两次跑的差才是**单变量**。校准配方（`saturation="kld"`＋`per="channel"`＋`forward_mode="image"`＋`batch=1`＋**9 张**）为什么是厂商配方里最薄的一环、以及"量化只留校准集与输入尺寸两条轴"的判据，见 [[状态源与决策记录]] 的 D-32。

### 阶段 1→2 之间还有一道前端摄取门（自己导的件才要过）

上面"形状有官方现成 `.pt`，不自己重导"对 YOLO 成立；LLM／生成式这类**自己导 ONNX** 的件，在 parse 之前先撞摄取层，四件事一次只改一件：

| 查什么 | 判据 | 撞过的样子 |
|---|---|---|
| ir／opset 声明 | 厂商文档只给 opset **11／14／17**＋ir **8**＋ONNX ≤1.13.1；生成侧默认给 ir10／opset 21～22 | parse 直接拒收 |
| 自定义域 | 融合归一化算子要落在 `com.microsoft` 域 | 留在 `ai.onnx` 域＝不认识 |
| 导出档 | 只有 `-p fp16 -e cuda` 给融合算子；`-e cpu` 是另一张图 | cpu 档＝2,125 节点 `MultiHeadAttention`＋显式 `RotaryEmbedding`＋多出 `position_ids`，过不去 |
| fp16 `Transpose` | 权重转置要在图外做完 | `Unknown dtype 10`（dtype 10＝ONNX FLOAT16） |

四条的实读出处、改字段的脚本（`meta_variant.py`／`detranspose_embed.py`）与"opset 会随工具版本自己往上漂，每轮导出都要重看这两个字段"，见 [[LLM上板要求与候选模型对照]] 第三节。**这一门检测类整条链没撞过，所以本页原本一个字没有。**

## 三、阶段 2：编译（本机 `icraft` CLI）

```
cd S:\apps\llm\agentwork\build\icompile_v8n_512x960
"C:\Icraft\CLI\bin\icraft.exe" compile config\ZG\Yolov8n_int8_512x960.toml   > compile.log 2>&1
```

**工作区必须是自包含的**（`config/ZG/*.toml`＋`config/customop/yolov8.toml`＋`fmodel/`＋`qtset/coco/`＋`qtset/coco.txt`＋`imodel/`＋`logs/`），全部路径写工作区相对。厂商那张 toml 的 `jr_path = "../3_deploy/imodel/ZG/int8/"` 会把上一版五段产物**原地覆盖掉**，所以搬之前先整目录备份（含 `MD5SUMS.txt`），编完再对备份逐文件 `md5sum -c` 确认厂商目录没动。

要抄的键（其余保持厂商原样）：

| 段 | 键 | 值 |
|---|---|---|
| `[parse]` | `net_name`／`inputs`／`network` | 自己起名（决定最终产物 `<net_name>_ZG.json`）；`[1,512,960,3]`；`fmodel/*.pt` |
| | `inputs_layout`／`inputs_dtype`／`image_channel_order` | `NHWC`／`UINT8`／`rgb`，**别改**——板上 demo 喂的就是 uint8 NHWC RGB |
| | `pre_scale`／`pre_mean`／`pre_method` | `[255,255,255]`／`[0,0,0]`／`nop`：÷255 是**烘进图里**的，不在 demo 里做 |
| `[quantize]` | `forward_list` | `"./qtset/coco.txt"`——**厂商那份尾随空格要去掉**（见第六节坑 2） |
| `[adapt]` | `pass_on`／`custom_config` | `customop.DetPostZGPass`／`config/customop/yolov8.toml`（这张里的 `thr_f = 0.1` 就是门限口径，旁边注释写着"测精度时改为 0.001"，**改不改都要在指标页写明用的是哪个**） |
| 每段 | `jr_path`／`json`／`raw` | 全部指向工作区 `./imodel/` |

耗时约 2 分钟（9 张校准图、`batch=1`）。

## 四、阶段 3：结构门禁（读 json，不看退出码）

编译完必须逐条读，因为**编译器 fatal 时上层 `icraft` 仍然 `exit 0`**（坑 3）。

```
python - <<'EOF'
import json,io,collections
d=json.load(io.open(r"imodel\Yolov8n512x960_ZG.json",encoding="utf-8"))
ops=d["ops"]
print(d["name"], len(ops), d["params_bytes"], d["params_md5"])
print(collections.Counter(o["compile_target"] for o in ops))
print([o["inputs"][0]["dtype"]["shape"] for o in ops if o["_type_key"]=="icraft::xir::Output"])
EOF
```

要落进记录的四行读数：

1. **输入形状**：`ops[0]`（`icraft::xir::Input`，`@hostt`）的 `shape` 必须正是你要的那一档。
2. **节点数与归属**：yolov8n ZG int8 这一档＝**122 节点**＝`HardOp` 119 个 `@zhuget(330)` ＋ `customop::DetPostZG` 1 个 `@fpgat` ＋ Input/Output 2 个 `@hostt`。两档实测**逐 op 同序同归属**，也就是**零算子缺口**（10-04 那次真编译得到的 D2 答案，见 [[iCraft算子支持矩阵]] 与 [[算子缺口处理]]）。
3. **头图形状**：640 档是 80×80／40×40／20×20×192，960×512 档是 64×120／32×60／16×30×192（NHWC，通道数不变）。
4. **`params_bytes`**：640 档 4,722,587 B，960×512 档 4,878,235 B（多 155,648 B，**成因未核**，别写成"权重大了"——权重是同一颗网络）。

`@fpgat` 那个 `DetPostZG` **不代表它跑在 PL 上**：它的 `hard_time` 是 1.5e-05 ms 量级，实际由 CPU 侧的 customop 实现执行，读延迟时别把它算进"NPU 时间"（口径见 [[NPU调用链#三、走不走硬件后处理，由什么决定|NPU调用链——三]]）。

### 补条：LLM 件会把上面第 2 行读反（10-30 加）

`算子缺口＝0` 这一格在 LLM 上不成立，而且**容易被读成"有 59 个缺口"**。Qwen3-0.6B-Instruct 的 `_ZG.json` 直读＝**2,238 个 op／`@zhuget(330)` 2,177／`@hostt` 61**；这 61 个里 `Input`／`Output` 各 1（端点，本来就在 host），`SliceDynamic` 56（KV cache 拼接，28 层 × K/V），再加 `Gather`／`RopeDynamic`／`CausalMask` 各 1。**这四类是图合同规定在 host 跑的算子，不是缺口**：`RopeDynamic`／`CausalMask`／`SliceDynamic` 在厂商算子文档里连行都没有（`docs/ops/` 全树＋[[icraft.v3.39.0_支持算子表]] 那 117 行，命中 0，A），`Gather` 有行但 ZG330／ZG30S／BY 三格全 `×`＋备注"Host 回退"。⇒ **拿算子支持表当 LLM 的 D2 分母，必然得出"缺口 59 个"这种错账**（登记口径见 [[算子缺口处理]] 第 7 节"设计性 host 回退"那条）。

所以 LLM 件的"过了"要换成两条问法：

1. **host 清单逐名对**——比"扣掉端点后的条数"更硬的判据是这四类名字的**集合与条数**跟上一版一致；名字或条数变了才是要查的事，变了就要单独归因，别顺手记成退化。
2. **合同字段对**——`CausalMask` 的 `fill_value`、`token_dynamic_fm` 的宽度（`@fp(32)[1,3]`＝12 B，厂商驱动只喂 8 B 会在板上直接抛 `byte_size diff`）这两处**本机 Host 后端不查**，只有上板才暴露。

明细（58 条输入的图合同表、D2 三态标注、读脚本）在 [[LLM上板要求与候选模型对照]] 第四、五、七节。

## 五、阶段 4：板端可执行（厂商 demo 源码）

**ZG330 侧唯一可用的官方 demo 源是 `3_deploy/BYZG/src/yolov8n.cpp`**；同目录的 `yolov8_plin.cpp` 硬 `cast<BuyiDevice>` 且自身编不过，属布衣，别拿它试悟净。

两处 `saveRes` 补丁（`post_detpost_hard` 与 `post_detpost_soft` 的 `#elif __linux__` 分支各一处，把 `visualize` 换成 `saveRes(output_res, resRoot, name)`）。补丁副本在 `S:\apps\llm\agentwork\yolov8_deploy\BYZG\src\`，**仓库原件未改**。

交叉编译走校机（现在的正路，见 [[校机无容器交叉编译]]）。10-05 那颗是在 podman 容器里出的，脚本仍在 `S:\work\WCIS\workenv\yolov8_deploy\build-v8-zg.sh`，两条路的差异：

```
# 容器路线（当时用的）
MSYS_NO_PATHCONV=1 podman run --rm --entrypoint /bin/bash `
  -v /mnt/s/apps/llm/agentwork/yolov8_deploy:/mnt/deploy `
  -v /mnt/s/work/WCIS/fdw/04_ICraft/v3.39/icraft_v3.39.0:/mnt/mdzdeb:ro `
  localhost/fpai-ub2004:tts-saved /mnt/deploy/build-v8-zg.sh
```
容器里每次都要先解 `IcraftMdzThirdParty.deb` 拿 `/ModelzooDeps/aarch64/Static`（aarch64 静态 OpenCV＋yaml-cpp），脚本用 `ln -sfn` 建软链；`cmake -S BYZG -B build/ZG_plin -DLINUX_AARCH64=ON -DCMAKE_BUILD_TYPE=Release`，只 `--target yolov8n`。

产物门禁（A 级口径）：`file` 要 ARM aarch64；`aarch64-linux-gnu-readelf -d` 的 **NEEDED 必须含 `libicraft_zg330backend.so`**，六颗 `libicraft_*`（hostbackend／buyibackend／zg330backend／xrt／xir／utils）板上都在位。**`ldd` 在板上全解析≠能跑**（见 [[魔改厂商视频流程部署记录]] 第八节坑 1）。

## 六、阶段 5：上板

推法就是 paramiko SFTP＋逐文件 md5 对比（脚本 `S:\work\WCIS\workenv\board-v8eval-push.py` 与 `board-v8eval960-push.py`，板上路径／大小／md5／用途／启动方式全部登记在 [[板端我方代码与产物台账#七、YOLOv8n 官方 demo 上板评测包（2026-10-05，D-31 队列"v8n 上板"的执行体）|台账——七]]）。

四条必须照做的：

1. **imodel 单独一个目录**。demo 的 `getJrPath` 是在 `imodel.dir` 里匹配**任何**含 `ZG.json` 的文件名并推出同名 `.raw`，两个档放一起就歧义。
2. **yaml 从厂商 `3_deploy/cfg/yolov8_ZG_int8_demo.yaml` 逐字抄**，只改绝对路径＋`show: false`；`conf: 0.1`／`iou_thresh: 0.65`／`fpga_nms: true`／`number_of_head: 3`／`mmuMode: true`／`ocm_option: -1` 不动。要出"新档对照"，就用最小 diff 生成副本（10-15 那次只改 `imodel.dir`／`res`／`log_path` 三行）。
3. **图片集只上一次**：`/root/v8eval/coco/val2017/`（5000 张，788 MB）与 `list.txt`（5000 行，取自厂商 `3_deploy/io/cocoval_2017.txt`，与 GT 逐一对上、零缺零多）是共用的，换档不重推。
4. `chmod +x` 别忘了，SFTP 不保权限。

## 七、阶段 6：跑

**起跑前门禁三查**（顺序不能换）：

```
md5sum /mnt/boot/BOOT.bin          # 位流里有没有 NPU——没有则 openDevice 一摸 AXI 窗口就整机楔死、零 printk
                                   # 这条路径随开机变（10-14 起 `/mnt/boot` 常不挂，目录里只剩 AA.bin/BOOT_NEW.bin）
                                   # No such file ≠ 位流没了。等效判据改看日志：
grep -E 'Device Name|Device Protocol' /tmp/live.log | tail -2   # 出现 `Device Name: zg330aiu` ＋ `Device Protocol: axi` ＝位流含 NPU
                                   # 这三行是 NPU 运行时自己打的，10-14 08:37:53 实测在 `/tmp/live.log` 里（台账 `:668`，A）
                                   # ⇒ 前提＝直播链这轮起过；链从没起过就没这份日志，这条判据取不到读数，别读成"位流没 NPU"
stat -c %y /tmp/live.stat; grep -c udmabuf /proc/*/map_files 2>/dev/null | head   # NPU 归谁
free -m; grep Cma /proc/meminfo; cat /sys/kernel/debug/rmem/udmabuf   # 内存余量
                                   # 跑 LLM 必须单盯 CmaFree：同场跑里 MemAvailable 全程最低 386,740 kB，CmaFree 却掉到 8,860 kB
```

NPU 这一条是硬约束：**两条链都是用户态 `mmap` 同一片物理窗口（`0x40000000`／`0x80000000`）加 `/dev/udmabuf0`，没有任何内核驱动做互斥**，并发没有保证；所以直播链在跑时不插评测（[[板卡镜像实测取证#18.1 先说清一件事：直播链不是被这次评测挤掉的|取证——18.1]]）。判活别看 `ps`——`setsid`／nohup 的包装进程会留在表里，裸 `ps` 也看不到真正的链；可信读数是 `live.stat` 的 `unix` 在不在走＋`map_files` 里 `udmabuf` 计数。BOOT.bin 这条门禁的**路径本身随开机变**（`/mnt/boot` 挂不挂不固定），另一条等效判据是看板上日志有没有 `Device Name: zg330aiu`（[[板卡镜像实测取证#十、SDI 取图链路四步检查表（2026-09-30 实测口径）|取证——十]]）。

内存这一条对 LLM 要换判据：**`free -m` 不够，必须指名 `CmaFree`**。两场实测：Qwen2 厂商件一轮真推理 `CmaFree` 最低 **8,860 kB**，同场 `MemAvailable` 全程最低 **386,740 kB**（A）——只看 `free -m` 会把"CMA 见底"读成"还有几百 MB"；我方 Qwen3 那颗 1.6 GB 件 10-14 四步 bisect 的 5 s 心跳更狠，lazy-load 窗 `CmaFree` 从 130,532 kB 掉到 **80 kB**、apply 窗 `MemAvailable` 只剩 **5,020 kB**（同窗 `CmaFree` 最低 2,440），**两个极值不在同一窗**。所以起跑前加一条 `grep Cma /proc/meminfo`，并且不与另一条会话的直播链同窗（直播链也吃 CMA）。逐行留底在 `repos/lang/llm/Qwen3-0.6B/pipeline.md` 第 6 节的读数块与 [[板端内存上限与心跳日志]]。

跑法两步，**永远先冒烟再全量**：

```
cd /root/v8eval && ./yolov8n cfg/eval_smoke.yaml     # 30 张，验通路
cd /root/v8eval && ./yolov8n cfg/eval_full.yaml      # 5000 张，约 6 分钟
```

冒烟的判据不是"跑完了"，而是：**txt 数＝30、零字节文件为 0、分数区间跨开门限**（10-05 那次 0.126–0.953，说明 `conf 0.1` 真的生效了）。全量的判据是 `RC=0` ＋ `out/` 里 txt 数＝list 行数。

回收用 `board-v8eval-pull.py`：板上 `tar -czf` → SFTP → 本地与板上 md5 对比 → `extractall(..., filter="data")` → 删板上 tar。

## 八、阶段 7：出指标与写口径

```
cd S:\apps\llm\agentwork\v8eval
python calAP.py out --classAP
```

`calAP.py` 与 `instances_val2017_yolo.json` 用 `os.link` 硬链接进工作目录，不复制、不污染厂商 `3_deploy/metrics/evaluate/` 原件。**GT 的 category id 从 0 起**，所以**绝对不要加 `--coco91`**（加了等于把类号整体挪错位，指标会莫名偏低）。

三个数不能混为一谈，写进任何表都要标来源：

| 数 | 是什么 | 640×640 那次的读数 |
|---|---|---|
| AP@[.5:.95] | 官方 `calAP.py` 在全 5000 张上的精度 | **0.331**（AP50 0.462／AP75 0.359；small 0.148／med 0.367／large 0.483；AR@100 0.412） |
| NPU 骨干 `hard_time` | 逐图各计一次的**推理**耗时 | mean **12.416 ms**（n=5000，p50 12.230，max 37.909）；Data 1.611 ms、DetPostZG 0.839 ms |
| 评测吞吐 | 含 JPEG 解码／前处理／写 txt 的整条链 | 369 s／5000 张＝**13.5 张/s**，与上面那个 12.4 ms **不是一回事** |

指标口径（int8＋官方 9 张校准集＋`conf 0.1`）在 [[板卡镜像实测取证#18.4 由此得到的三条口径|取证——18.4]]；换门限或换校准集必须重跑并改那一节。**`AP small 0.148` 不是量化掉的**——那是 640 输入分辨率的天花板，与量化算法无关（见同一页 18.4 第 2 条，以及 [[板卡镜像实测取证#18.6 "能不能和直播一样高清"这个问题里的误会，以及两条路各自的上限|取证——18.6]]）。

`conf` 这一项有个已翻过两次的弯：**detpost 的 yaml 键不生效、门限是回写硬件寄存器的**，判据以扫描实测为准（[[板卡镜像实测取证#12.3 对 12.2 第 2 条的再更正（A 级，2026-10-04 扫描实测）|取证——12.3]]、[[板卡镜像实测取证#十三、conf 门限扫描（D-31 队列第 ② 项，2026-10-04 实测）|取证——十三]]）。

## 九、坑清单（模型侧，全部踩过或已在源码里核实）

| # | 现象 | 根因 | 绕法／判据 |
|---|---|---|---|
| 1 | 编译一次，上一版基线没了 | 厂商 toml `jr_path` 直指 `3_deploy/imodel/ZG/int8/` | 自建工作区；先备份＋`md5sum -c` 回验 |
| 2 | 容器里量化段 fatal `File ./qtset/coco.txt does not exist`，Windows 却正常 | `forward_list = "./qtset/coco.txt "` 的**值带尾随空格**；Win32 吃尾空格、Linux 不吃 | 抄 toml 时去掉尾随空格（Windows 下两者等价） |
| 3 | 明明 fatal，脚本却以为成功了 | `icraft`（父进程）在子命令 fatal 后**仍 `exit 0`**；`sh -lc '…; echo EXIT=$?'` 还会再吞一层 | 判据只有两条：五段文件在不在＋日志里有没有 `[F]`／`执行以下命令时捕获到错误码` |
| 4 | 容器出不来 ZG 档最终 imodel | `tts-saved` 那份 amd64 包的 codegen 只带布衣，`icraft-generate` fatal `libicraft_zhuge_codegen.so does not exist` | ZG 档 imodel **只能本机 Windows CLI 生成**；容器/校机只负责板端二进制 |
| 5 | 想拿 md5 验收"两边编的是同一个东西" | 跨平台 `.raw` 大小一致却几乎全字节不同，`.json` 的 scale 差到小数第 8 位 | **结构类结论（节点数、归属）跨平台稳；字节／md5 类不跨平台比** |
| 6 | 板上跑完，结果目录是空的 | `saveRes` 关在 `#ifdef _WIN32` 内 | 阶段 4 的两处补丁 |
| 7 | 想给悟净用 `yolov8_plin.cpp` | 它硬 `cast<BuyiDevice>` 且自身编不过 | ZG 侧只有 `yolov8n.cpp` 一份适用 |
| 8 | 换了 imodel 目录，加载的还是上一版 | `getJrPath` 按"文件名含 `ZG.json`"匹配，目录里两个就撞 | 一档一目录 |
| 9 | 评测把直播挤挂了／或被直播挤挂 | 无内核互斥 | 起跑前查 `live.stat`＋`udmabuf` 计数；不在并发窗口里跑 |
| 10 | 远程 `for` 循环里 `wc`/`awk` 报错、`$(…)` 变成怪数 | Git Bash 对双引号内的 `$(…)`／`$f` 先展开一层 | 远端命令一律**本地单引号**；awk 程序用双引号 |
| 11 | `sh: 1: time: not found`（rc 127） | 容器／板端的 `sh` 是 dash，没有 `time` | 用 `date +%s` 自己夹，或 `/usr/bin/time`（板上有） |
| 12 | 加了 `--coco91` 后 AP 莫名掉 | GT 的 category id 从 0 起，不是 COCO-91 | 不加；`calAP.py <txtDir> --classAP` 就够 |
| 13 | 在板上顺手编译探针 | 993 MB／CMA 262,144 kB，编译必挤死现役链，且会 OOM | 编译一律搬校机／本机（[[板端内存上限与心跳日志]]） |
| 14 | 换了模型，启动就崩或跑错图 | **`view_except_op_ids` 是逐模型、逐编译器版本的**，照抄上一版必然错 | 换模型必须重新确认这串（见第十节） |

## 十、换模型的影响面：位流／时序／runtime 各动哪一层

**一句话**：换模型**不动位流、不碰时序**，PS 侧换两个件（`_ZG.json`＋`_ZG.raw`）再改 yaml 几行就够——**除非**新模型碰到位流里没有的东西。

### 10.1 三层各自装什么（判断的唯一依据）

| 层 | 装什么 | 换模型动不动 |
|---|---|---|
| **位流**（PL，`BOOT.bin`） | NPU 的 **1 个 ZG330 iCore**、若干 **CustomOp 硬算子**（ImageMake／DetPost／硬 NMS…）、视频通路 PL 逻辑 | **一般不动** |
| **模型件**（eMMC `jr_path/decode/`） | 算子图 `_ZG.json` ＋ 权重 `_ZG.raw` | **换的就是这个** |
| **PS 侧 runtime** | 12 件 `libicraft_*.so` ＋ 驱动脚本 ＋ yaml | 不动（但位流必须是**含 NPU** 那颗） |

### 10.2 已实测的换模型动作清单（换输入尺寸档那次，台账 #24）

**yaml 只改四处，C++ 一行没改**（B，源码；读数见 [[板卡镜像实测取证#十一、960×512 模型上板实验（2026-09-30）|取证——十一]]）：

1. `jsons`／`raws` → 指向新件
2. `net_w`／`net_h` → 新输入尺寸
3. **`view_except_op_ids` → 必须重新确认**

第 3 条是唯一真正容易踩空的：ImageMake 零拷贝那一跳要**反查输入张量在 PL DDR 的编译期物理地址**，前提是输入算子被 `viewExcept` 看穿——源码注释原话「PLIN 工程，基本需要保证输入算子被 view 掉，否则无法获取到 phy addr」（[[NPU调用链#二、执行 YOLO 的七跳|NPU调用链——二]] 第 6 跳）。而这串 **op id 逐模型、逐编译器版本都不同**：v3.36 的 640×352 是 `[0,671,663,692,605]`，v3.39 的 960×512 变成 `[0,671,663,675,660]`——同一条 Input→Cast→Add→Reshape→Cast 链，编号重排了。**不重新确认＝启动崩或跑错图，而且不报错。**

### 10.3 这四种情况必须换位流（此时才谈时序）

| 情况 | 为什么 | 证据／去哪看 |
|---|---|---|
| 模型用到位流里没有的 **CustomOp 硬算子** | 硬算子固化在 PL 逻辑里，图声明了但位流没例化 ⇒ 加载／运行失败 | 方案表两条 demo 明标「**需要 CustomOp1 位流**」（[[解决方案汇总.xlsx - sln列表]]） |
| 走**硬件 YUV2RGB**（webcam 那条） | 色彩转换是 PL 逻辑 | 矩阵注「ZG 配套位流要求硬件 YUV2RGB」 |
| **多路 SDI 输入** | 多路是位流本体差异（`[单路/多路]` 写在 issue 的位流版本串里） | [[NPU多模型并发与厂商案例]] |
| 上新自研 PL IP（VFPGA／硬 SRC 等） | 那是加硬件，必然重做位流＋跑时序 | [[3-FPGA组件下沉]] |

**判据一句话**：看新件里 `compile_target` 有没有出现**位流里没有的硬算子**。`@zhuget(330)` 是「要 NPU 硬件」的标准归属——普通算子由 iCore 自己算，**不需要** CustomOp；只有真正的硬算子才绑位流。

### 10.4 时序

**换模型完全不碰时序。** 时序是 Vivado 综合＋实现的产物，固化在位流里；换的是 eMMC 上两个数据文件，与 PL 布线时延无关。**只有改 RTL 或换位流时才需要重跑 Vivado 并重过 `report_timing_summary`。** 另有一条容易误会的：**NPU 自身频率调不了**（`--frequency` 空转，strings 直证，见 [[NPU调用链]] 第四节）。

### 10.5 照抄：换模型五步

```
① 本机编译新模型 → _ZG.json + _ZG.raw（五段，target zhuge／ZG330 档）
② 拷上板 eMMC，两侧 md5 核对（.raw 的 md5 应等于 json 内 params_md5）
③ 改 yaml：模型路径、net_w/net_h、view_except_op_ids（重新确认，别抄上一版）
④ 过两道门：位流 md5 是含 NPU 那颗；CmaFree 够（不看 MemAvailable）
⑤ 起 runtime 加载 —— 位流、时序、C++ 全不动
```

唯一「不重来就不行」的是 ③ 的 op id 与 ④ 的位流身份，其余真就是塞进去。
