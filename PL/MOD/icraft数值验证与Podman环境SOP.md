---
tags: [SOP]
updated: 2026-10-31
---

# icraft数值验证与Podman环境SOP

> **本页回答什么**：在手上有 iCraft `_ZG` 件时，如何**在容器里（不是板上）**用与板端同 build 的 icraft 复跑、`--dump_format` 给出的**是不是**真实数值（**是**），以及怎么用 `Session.forward` 直读张量。附一条照着能跑的 Podman 环境清单。
>
> 证据等级：**A** = 本机/容器/板端实测且命令可复现。2026-10-31 按本页逐节复跑过一遍（第 2~5 节全部重跑），下方标注与复跑结果一致。

## 1. 环境：容器 `zgbuild` 已就绪，不要重新装

| 项 | 值 |
|---|---|
| 宿主 | Windows 11 + **Podman 6.1.4**；机器 `podman-machine-default`（WSL 型、8 核 / 2 GiB / 100 GiB 磁盘） |
| 容器 | **`zgbuild`**，镜像 `localhost/fpai-ub2004:tts-saved`（4.64 GB，2026-10-09 建） |
| 系统 | **Ubuntu 20.04.6 LTS + Python 3.8.10**（icraft 的 cp38 ABI 必需） |
| icraft | **3.39.0 全套**：`/usr/bin/{icraft,icraft-run,icraft-parse,icraft-optimize,icraft-adapt,icraft-generate}` |
| **icraft-run build** | **`3.39.0.0-a7cb8d5(2608220045)`**；板端为 `(2608220046)` ⇒ **同一 build，只差时间戳尾号** |
| 挂载 | `S:\` → `/mnt/s`（读写工作区） |
| 交叉工具链 | `/usr/bin/aarch64-linux-gnu-gcc` |
| 补装（本机加的） | `numpy 1.24.4` / `onnxruntime 1.16.3` / `onnx 1.17.0` |

**启动与进入**：

```bash
podman machine start                    # 机器若未起
podman start zgbuild
MSYS_NO_PATHCONV=1 podman exec zgbuild bash -c '<命令>'
```

> **Git Bash 必踩的坑**：`podman exec` 会把容器内的 `/mnt/s/...` 路径当成本机路径改写成
> `C:/Users/.../node_modules/@dsh-ops/bash-win32-x64/mnt/s/...` ⇒ 一律加 **`MSYS_NO_PATHCONV=1`**。

**与它无关的两条**：`largefiles/交叉编译环境ubuntu20.04_container.tar`（746 MB）就是 `ubuntu20.04_container` 基础镜像，**不需要 `wsl --import`**；宿主上那个 16 GB 的 WSL `Ubuntu`（26.04 + py3.14）**装不了 icraft**（ABI 不匹配），别拿它试。

## 2. 复跑 `_ZG` 件（Host 后端，容器内）

```bash
MSYS_NO_PATHCONV=1 podman exec zgbuild bash -c '
cd /mnt/s/work/WCIS/workenv/.tmp_matcher/vocos_chain/gen &&
icraft-run --json vocos_native_ZG.json --raw vocos_native_ZG.raw --network vocos \
  --input /mnt/s/work/WCIS/workenv/.tmp_matcher/board_run/input_correct_1_1_600_80.bin \
  --backends Host --log_time'
```

判据：`total_hard_time: 0.000 ms`（Host 是纯软件，硬件段必然为 0）、`total_time` 在 **3.7–4.2 s** 量级（x86 上；2026-10-31 两次实测 **3776.9 / 3740.0 ms**，wall 4.8–5.3 s。同一台机器上有别的 icraft 任务并发时会涨到 6–7 s，别当性能数）。

**输入文件必须按网络声明的 4D 形状做**：vocos 声明 `[1,1,600,80]`（NHWC）。真实梅尔谱是 559 帧 ⇒ 要在时间维补零到 600 再写文件（`192000` 字节）。

> **同输入两次跑，Host 后端不保证逐位相同**（A，2026-11-01，ERNIE E41 上量的）：42 路 feed 逐件 md5 相等，两个独立进程的 logits 差 **|Δ| 均值 0.177、最大 0.668**（103,424 个输出，fp16 网格 0.0078～0.0156 ⇒ 约 10～20 ULP）。⇒ 拿 Host 当金标准时，判据要落在 **argmax ＋ top1−top2 间距**上，间距小于这个抖动的步不要当硬判据；"两次跑逐位相同"这句话在 Host 上不成立。同一颗件在片上 ZG330 反而逐次可复现（同条件两次跑、11 步 logits 极值逐位相同）。依据与逐项读数：[[板端我方代码与产物台账]] §25.2。

> **路径别抄错**：`board_run/` 下有两个 192000 字节的 600×80 文件。`input_1_1_600_80.bin` 是**旧的错序列**（与正确输入 corr **0.360**、其输出对 golden 的 corr 只有 **0.0207**），照着它会得到"NPU 算错了"的假象。要与 §4b 的正确构造一致，用 **`input_correct_1_1_600_80.bin`**（与 `mel.reshape(80,559).T` 补零后逐元素相同，输出对 golden corr **0.8959**）。

> **这颗输入现在有正本**（2026-11-04 补）：`workenv/.tmp_matcher/make_correct_input.py`（自定位，不写死任何根）。跑 `python -X utf8 workenv/.tmp_matcher/make_correct_input.py` ⇒ 重建 `board_run/input_correct_1_1_600_80.bin`（192000 字节，本机 ORT 1.24.2 出 `134809a8…`）＋ `board_run/golden_mel.bin`（559×80，`4a682254…`），stdout 自检四项：帧数 559、首 559 行逐元素 `== mel.T`、尾 41 行全零、"错序列 vs 本件"corr＝**0.358**。上面记的 0.360 与之差 0.002 ⇒ 那颗 `input_1_1_600_80.bin` 本身没留正本、构造复现不到逐位，本节能复跑的只有正确输入这颗。
>
> **§2 这条链目前还开不了**：`vocos_chain/gen` 的 `vocos_native_ZG.json`／`.raw` 在 PC 侧已丢（板侧 `/root/vocos_run/imodel/` 有，md5 已记在 [[板端我方代码与产物台账]]）；`vocos_chain/gen/fm/vocos_native/ftmpHQB` 那三份转储倒是有等价幸存——`ref_ok/` 与 `npu_out_fm/` 两处逐文件 md5 全等，就是下面 §3 记的 `9f6c53b5…`／`f6a85c6e…`／`c0ceb485…`，只缺件本身。

## 3. `--log_io` 能看到张量拓扑（推荐用这个）

```bash
... --backends Host --log_io --log_path ./logsio
# 产物: logsio/<network>/<network>_run_io.log
```

它逐 op 打印 `In: (v_id|shape)` / `Out: (v_id|shape)`，能直接读到**输出张量的 v_id 与形状**，例如 vocos：

```text
HardOp 1344 In: (2117|1,513,600)  Out: (804|1,513,600)
Output 144  In: (796|1,513,600)+(800|1,513,600)+(804|1,513,600)  Out:
```

⇒ 三个输出的 v_id 是 **796 / 800 / 804**，形状 `[1,513,600]`（=[batch, freq, time]）。**这是查 v_id 最快的手段，比翻 JSON 快**。

## 4. `--dump_format` 给的是不是真值（**给**；2026-10-31 复核后与旧版结论相反）

**`--dump_output` 对这个 build 是空操作**：同一份输入、`--dump_format HQB`，加与不加 `--dump_output` 各跑一次，**188 个 dump 的 md5 清单逐个相同**；输出节点 796/800/804 又与 `Session.forward` 直读的张量、与 `.tmp_matcher/npu_out_fm/` 那三份（板侧落盘，来源见 `final_evidence.py`）逐字节相同（`9f6c53b5…` / `f6a85c6e…` / `c0ceb485…`）。

```bash
icraft-run --json vocos_native_ZG.json --raw vocos_native_ZG.raw --network vocos \
  --input <§2 那份正确输入> --backends Host --dump_format HQB --log_path ./pairC
# 再加 --dump_output 跑一遍写 ./pairD：188 个 .ftmp 的 md5 全同
```

**所以"只有 11 个离散值"从来不是 dump 的毛病**：那 11 个值（`0…88.1875` 的等比阶梯）是这张 int8 网络 mag 输出的**真实内容**——`Session.forward` 直读同样是 11 个值、同一个值域。旧版把"两次不同输入的值集合相同"读成"dump 只给 scale 表"，错在比的是**值集合**而不是**数值**：量化输出本来就会落在同一把阶梯上，值集合相同 ≠ 数值相同。

> **别用 v_id=0 验证这件事**：v_id 0 是 InputNode，它原样吐输入（`dtest`/`dtest0` 两份 `0.ftmp` 与输入文件逐字节相同，`equal_to_input=True`），这条只证明 dump 通路没坏，证明不了中间节点给不给真值。要验就拿 796 这种中间/输出节点。

> **`--dump_format HQB` 单独用会 dump 全部 188 个节点**，而且各按自己的**存储类型**写盘：量化中间张量是 1 字节/元素（如 307200 B = 307200 元素），输出节点是 4 字节/元素（1231200 B）。读之前先拿字节数除元素数确认 dtype，别一律当 fp32。

> **收窄 dump 会让 `total_time` 失真**：只 `--dump_ftmp 796` 时汇总行是 **0.008–0.027 ms**，实际 wall 仍有 ~5 s。判性能只能用不带 dump 的那种跑法。

> 只想快速看某层有没有算出东西，也可以走 Python API（见 §5），两条路结果**逐位相同**。

## 4b. **本轮踩过的四条错误链（按修复顺序，每条都伪装成"NPU 算错了"）**

| # | 表象 | 真因 | 怎么验 |
|---|---|---|---|
| 1 | "dump 只有 11 个离散值" | **假警报**：11 个值就是 mag 的真值（量化阶梯），dump 一直给真值 | 直读张量比对：`Session.forward` 与 dump 逐位相同（§4） |
| 2 | "NPU 输出与输入无关、是坏的" | ① + 输入布局反了 | 见 #3 |
| 3 | "mel 要 `.T`" | **`golden_mel.bin` 是 `(80 mel, 559 frame)`，`reshape(80,559)` 直接用，不转置** | CPU ONNX 对照：`reshape(80,559)` → corr **1.000000**；`.T` → **0.016749** |
| 4 | "`Session.forward` 是坏 API（段错误）" | **`CreateFromJsonFile` 不加载参数字节** | 加载前 HardOp 的 instr/params `hasData=0/273`，`autoLoadParams(.raw)` 后 `273/273` |

**两个正确的输入构造**（等价，按目标选）：

```python
# 给 CPU onnxruntime：要 [1, 80, 559]
mel = np.fromfile("golden_mel.bin", np.float32).reshape(80, 559)      # 不转置
out = sess.run(None, {"mels": mel[None].astype(np.float32)})

# 给 icraft（NHWC [1,1,600,80]，W=时间,C=mel）：
frame_major = mel.T                       # (559,80)
pad = np.zeros((600, 80), np.float32); pad[:559] = frame_major
pad.reshape(1, 1, 600, 80)                # 喂给网络
```

`corr(旧错误输入, 正确输入) = 0.360` —— **布局错了之后所有比对都无意义**，这是 0.02 vs 0.90 的差距来源。

## 4c. **`--fake_qf` 是定案"损失是否来自量化"的最快手段（本轮用它定案）**

```bash
# 同一输入，跑两遍：正常量化 vs 绕过量化
icraft-run ... --dump_format HQB --dump_output --log_path ./qf_norm
icraft-run ... --dump_format HQB --dump_output --log_path ./qf_fakeqf --fake_qf
```

vocos `_ZG` 件实测（与 CPU 浮点参考比，元素级 corr）：

| 输出 | 正常量化 | **`--fake_qf`** | 不同值数（正常→fake） |
|---|---:|---:|---|
| mag | 0.89592 | **0.99886** | 11 → **40445** |
| cos | **0.11976** | **0.86949** | 38 → **130081** |
| sin | **0.12189** | **0.87233** | 41 → **111857** |

**读法**：`--fake_qf` 一关，cos/sin 从 0.12 跳到 0.87、mag 到 0.999 ⇒ **损失几乎全部来自 int8 量化**，不是 NPU 硬件、不是 API、不是输入布局。

**但注意边界**：fake_qf 的 cos/sin 只到 **0.87**，**没到 1.0** ⇒ 除了量化还剩一部分实现差异（`Cos`/`Sin` 算子近似或 `--merge_hardop` 融合误差）。**验收线 corr>0.99 因此未达成。**

**已定位的量化缺陷**（vocos 实例）：`Cos`/`Sin` 的输入角度在 ZG 图里是 `sint8` + scale `0.45043343`，而真角度范围 `-158.75…170.89 rad` ⇒ `angle/scale` 达 `-352…379`，sint8 只有 `-128…127` ⇒ **2.3% 饱和、其余绕回**（实测隐式 wrap 计数 `min=-1 max=1`、22.3% 元素非零）。`scale` 写成 `600*0.45043343`（长度量纲）用在角度上本就可疑。

## 5. 直读 tensor 的 API 路线（**已通，关键是一行**）

`.pyi` 类型存根在 `/usr/local/lib/python3.8/dist-packages/icraft/*.pyi`。**最小可用序列**：

```python
import numpy as np
from icraft import xir, xrt, host_backend
from icraft.zg330backend import ZG330Backend

net = xir.Network.CreateFromJsonFile(JSON)
net.autoLoadParams(RAW)                       # ←←← 唯一的关键，缺了必段错误
in_tt = net.ops[0].outputs[0].tensorType()     # ← InputNode（@fp(32)），别取 net.ops[1]

dev  = xrt.Device.Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000")
sess = xrt.Session.Create([ZG330Backend, host_backend.HostBackend],
                          net.view(0), [dev, xrt.HostDevice.Default()])
sess.apply()
inp = xrt.Tensor(np.ascontiguousarray(x, np.float32), in_tt)
outs = sess.forward([inp])
for t in outs:
    h = t.to(xrt.HostDevice.MemRegion())       # ← 必须搬回 host 才读得到
    nb = h.dtype().bytes(); buf = bytearray(nb); h.read(buf, 0, nb)
    v = np.frombuffer(bytes(buf), dtype=np.float32)
```

**两个致命细节**：

1. **`autoLoadParams(.raw)` 必须有**。`CreateFromJsonFile` 只解析图、不加载参数（`net.params_bytes` 还会照报 `.raw` 的大小，极具迷惑性）。缺了它 `forward()` 读未映射内存 → **SIGSEGV**，而不是报错。
2. **输入 TensorType 取 `net.ops[0].outputs[0]`**。取 `net.ops[1]` 拿到的是 HardOp 的 `QuantizedType`，同样引发问题。

**已证伪的误用**（别再试）：裸 `Tensor()` 直接 `setDType`；`Session.CreateByOrder(view,[be],[dev])` 传实例；`setFakeQf` 当类方法调；`net.view()` 无参。

**双后端是必需的**：`[ZG330Backend, HostBackend]`。只给 `HostBackend` 会 `op_id=1341 HardOpNode 未绑定`（HardOp 只能 ZG330 接、Input/Output 只能 Host 接）。

**正确性交叉验证**：Python API 的结果与 `icraft-run --dump_output` **逐位相同**（`max|d|=0`），这本身就是对 session 装配最有力的证明。

**2026-10-31 在容器里补验的几条**（同一条链，只用 Host 后端：`CreateWithBackends(view,[HostBackend.Init().Create(HostBackend, view, dev)])`）：

- 参数加载三种写法都在（`xir.pyi:5585 / 5716`）：`autoLoadParams` / `lazyLoadParamsFromFile` / `loadParamsFromFile`。我这边验的是 **`lazyLoadParamsFromFile`**；跳过参数加载后 `forward()` 必 **SIGSEGV（退出码 139）**，位置就在 forward 调用那一行——这是"段错误"的**唯一**充分原因，与本页 §5 开头那句一致。
- `forward([inp])` 与 `forward([inp], outs)` **两种重载都通**；双参版本返回 `None`，结果填进预分配的 tensor（`chunk = dev.defaultMemRegion().malloc(tt.bytes(), True, 4096)`，注意是 `bytes()` 不是存根里没有的 `storageBytes()`）。双参版本只在 **Host-only session** 上验过，板上双后端 session 下未验。
- `sess.stepTo(last_op, [inp])` **不会段错误**，报的是 `Check failed: (index_map.count(op_id)) is false / Op: op_id = 188 is not in the session!`——`net.view(0, len(net.ops))` 建的 view 里没有那个 id。
- **比对前要先对齐帧数**：输出是 `[1,513,600]`、golden/ONNX 参考是 `[1,513,559]`（真实梅尔 559 帧，尾部 41 帧是补零）。必须 `reshape(513,600)[:, :559]` 再比；直接按扁平数组比 mag 的 corr 会掉到 **0.076**（对齐后是 **0.896**），能凭空造出"NPU 算错了"。

## 6. 板上跑 NPU 的正确命令（对照）

```bash
icraft-run --json <model>_ZG.json --raw <model>_ZG.raw --network <name> \
  --input <4D输入文件> \
  --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" --log_time
```

- **`ZG330,` 前缀 + `;Host` 结尾，两者缺一不可**；只写 `ZG330` 会 `op_id=0, InputNode 未绑定` 后段错误；只写 `axi://...` 会 `Only Support Host/BY/ZG330 backend`。
- 真 NPU 的 `total_hard_time` 非 0（vocos 实测 9.499–9.503 ms，三次稳定）。

## 7. 判据速查

| 想知道什么 | 看哪里 | 通过标准 |
|---|---|---|
| 网络能否加载 | `CreateFromJsonFile` 不抛异常 | — |
| 输出有哪些、v_id 多少 | `--log_io` 日志的 `Output` 行 | — |
| 硬件是否真参与 | `total_hard_time` | NPU：非 0；Host：恒 0 |
| **数值对不对** | `--dump_ftmp <v_id>`（§4）或 `Session.forward` 直读（§5） | 先 `reshape(513,600)[:, :559]` 对齐帧数再算 corr；vocos 实测 mag 0.896 / cos·sin 0.12（量化损） |
| **dump 给的是不是真值** | 与 `Session.forward` 直读的张量比 md5 | 逐位相同才算数；别拿 v_id=0 验（InputNode 原样吐输入） |

## 相关页面

- [[TTS同量级候选进NPU横评]]——本 SOP 的证据来源（§6.1b NPU 读数、§6.1c 端到端 RTF、§6.1d dump 根因）
- [[iCraft算子支持矩阵]]——算子面正本（注意 91 行是映射表，完整面是 114 个 spec 页）
- [[NPU模型上板出指标SOP]]——上板出指标的另一条线
- [[哪些要跟厂商要]]——第九条记着 `Mul` 广播与 `Unsupport` 无前向两个待问项
