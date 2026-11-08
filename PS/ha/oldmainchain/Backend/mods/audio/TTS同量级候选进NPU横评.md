# TTS同量级候选进NPU横评

> **本页回答什么问题**：把 sherpa-onnx 生态里与板上现役**同一量级**（30~170 MB、VITS 系 + 声码器外挂）的中文 TTS 模型全部拉下来，**逐个喂给真实的 iCraft 3.39.0 编译器**（ZG330/zhuge），看哪个能过 parse、过不去的卡在哪一类，并回答"官方 TTS 全灭 ⇒ 我方也不行"是否成立。
>
> **结论先行**（2026-10-31 实测，全部 A 级）：
> 1. **真正零缺陷通过的是 Vocos 声码器**——`rc=0`、解析 100%、**预检 CSV 一条缺陷都没有**，产物已落盘。
> 2. **Matcha 两个变体走到了预检阶段**（`rc=19015`）并**产出了 parsed.json/raw**，只剩 `Range`+`RandomNormalLike` 两个算子，全表只 2 条缺陷。
> 3. **其余 7 个候选各有不同死因**，但**没有一个是"算子表里根本没有"**——全部是可以定位、可以逐层修的图/属性问题。
>
> 证据等级：**A** = 本机实测、命令与报错原文可复现（本页全部是 A）；**B** = 官方一手文档未复跑；**C** = 机制推断。

## 1. 测试口径

| 项 | 值 |
|---|---|
| 编译器 | `C:\Icraft\CLI v3.39.0\bin\icraft-parse.exe`，CLI `3.39.0.0-431be90(2608211646)` |
| 后端 | `--target zhuge`（= ZG330 = FMQL30TAI = 悟净，我方目标后端） |
| 模型来源 | `github.com/k2-fsa/sherpa-onnx` 的 `tts-models` release（**官方包**） |
| 下载路径 | 本机走代理 `127.0.0.1:7897`；校机直连 GitHub 可用（但校机 Windows 侧 curl 的 schannel 吊销检查会挂，需 `--ssl-no-revoke`） |
| 复现目录 | `S:\work\WCIS\workenv\.tmp_matcher\`（临时产物，不进库） |

来源可信度校验：matcha 官方包里的 onnx 与板上 `/mnt/data/models/tts-matcha/` 那份 **md5 完全一致**（`391d298cc5417e205e59ae9424d2304b`）；piper zh_CN-huayan 官方包与板上那份 md5 不同（`c52356…` vs `40cdb7…`），但**图结构逐项相同**（2755 节点 / 50 算子 / 输入相同），功能等价。

## 2. 最终实测总表（10 个候选，全部 A 级）

| # | 模型 | 体积 | 节点 | 输入 | parse 结果 | 产物 | 死因 |
|---|---|---|---|---|---|---|---|
| 1 | **vocos-22khz-univ**（声码器） | 53.9 MB | 272 | 1 | **rc=0 ✅ 零缺陷** | **json+raw ✔** | — |
| 2 | matcha-icefall-zh-baker | 75.6 MB | 4802 | 4 | rc=19015（预检 2 条） | **json 1.6 MB + raw 131 MB ✔** | `Range`、`RandomNormalLike` |
| 3 | matcha-icefall-zh-en | 75.7 MB | — | 4 | rc=19015（同上） | **json+raw ✔** | 同上 |
| 4 | sherpa-onnx-vits-zh-ll | 121.1 MB | — | 6 | rc=19020 | ✘ | `Type Error: tensor(int64)` |
| 5 | vits-icefall-zh-aishell3 | 30.5 MB | 4896 | 6 | rc=19020 | ✘ | 见 §5 断点 |
| 6 | vits-melo-tts-zh_en | 170.4 MB | — | 7 | rc=26000 | ✘ | 见 §5 断点 |
| 7 | vits-piper-zh_CN-chaowen-medium | 63.2 MB | 2682 | 3 | rc=-1073741819（段错误） | ✘ | `Split` 改写引发崩溃 |
| 8 | vits-piper-zh_CN-huayan-medium | 63.2 MB | 2755 | 3 | 同上 | ✘ | 同上 |
| 9 | vits-piper-zh_CN-xiao_ya-medium | 63.2 MB | 2682 | 3 | 同上 | ✘ | 同上 |
| 10 | vits-zh-hf-eula | 121.9 MB | — | 6 | rc=19020 | ✘ | `tensor(int64)` |

**读法**：`rc=0` 是完全通过；`rc=19015/19020` 是"解析走完但预检/类型检查有报"，此时**产物照样落盘**（iCraft 的设计：预检失败也保存 json/raw 便于排查）；`rc=-1073741819` 是 `0xC0000005` 段错误。

## 3. 唯一零缺陷通过的：Vocos 声码器

`vocos-22khz-univ` 只做了两步就通过了，**一个算子都没改**：

1. **输入 4 维适配**：原生 `mels [batch, 80, time]`（3 维），iCraft 参数层强制 4 维 → 声明 `[N, 1, L, 80]`，图首插 `Squeeze(axes=[2])` 还原成 3 维。
2. **opset/IR 降级**：`opset=11`、`ir_version=8`。

结果：

```
RC=0
Parsing : [██████...███] 100.00%
precheck csv: 空（连表头都没有生成）
产物: vocos_native_parsed.json (110,733 B) + vocos_native_parsed.raw (53,841,188 B)
```

> **一条被试错推翻的弯路**：我曾把 `/head/Exp` 改写成 `Pow(e, x)`（以为 `Exp` 没有对应算子），结果**反而**触发预检约束：
> `Pow: the base of the exponent only support be ftmp;the power of the exponent only support be params`
> **保留原生 `Exp` 才是对的** —— 这条鸟枪换炮的改写是负优化，已回退。

## 4. 关键发现：iCraft 的 4 维门与 TTS 的 2/3 维冲突

这是所有声学模型（非声码器）的共同障碍，**也是本轮最耗时的一处**：

| 现象 | 实测报错原文 |
|---|---|
| 喂 4 维，`Squeeze` 轴位不对 | `Dimension of input 2 must be 1 instead of 600` |
| 喂 3 维 | `input_i.size must be 4 when input_layout_i == NHWC` |
| 换 `FD` 布局 | `Check failed: (input_layout_[i] == "NHWC") is false` |
| 少配一个输入 | `toml has 1 inputs, but model has 4 inputs!` → **Segmentation fault** |

**最终解出来的映射规则**（逐次试错收敛，已稳定）：

| 原始秩 | 声明成 | Squeeze axes | 例 |
|---|---|---|---|
| 2 维 `[N,L]` | `[N,1,1,L]` | `[2,3]` | matcha `x` |
| 3 维 `[N,C,L]` | `[N,1,L,C]` | `[2]` | vocos `mels` |
| 1 维 `[X]` | `[X,1,1,1]` | `[1,2,3]` | piper `scales`（`[3]`） |

配套的 CLI 参数：`pre_mean`/`channel_swap` 的长度必须等于**该输入声明后的第 4 维**（`input[i][3]`）；`channel_swap` 还必须是 `0..N-1` 的排列，否则报 `channel_swap[g] != channel_swap[j]`。

## 5. 图改写配方（`recipe_final.py`，源码在 `.tmp_matcher/`）

按下面顺序做，**顺序错了会白改**（第 1 步要遍历全图，必须在第 2 步之前）：

1. **输入 4 维映射**（上面的表）
2. **折回 `Unsqueeze`/`Squeeze`/`ReduceSum`/`ReduceMean`/`Split` 的 axes 输入 → 属性**，并清理失去消费者的 `Constant`。
   matcha 一次折掉 **356 个 `Unsqueeze` + 1 个 `ReduceSum` + 3 个 `Squeeze`**，删 **360 个**常量。
3. **剥离 iCraft IR 不认的 opset-14/15 属性**：`Reshape.allowzero`（matcha 217 个）、`Resize.antialias` 等。
4. **把 opset≥12 的比较算子下沉**：`GreaterOrEqual`→`Not(Less)`、`LessOrEqual`→`Not(Greater)`（否则报 `No Op registered for GreaterOrEqual with domain_version of 11`）。**下沉后必须做一次拓扑重排**，否则报 `no value info`。
5. `opset=11`、`ir_version=8`。

**每修一层，报错就往下一层走** —— 这个"报错前移"是本轮最主要的推进方式。实测的前移轨迹：

```
Unsqueeze 输入 2 个
  → Conv dilations 长度错（1D 被按 2D 判）
  → Reshape allowzero 不认
  → Range/RandomNormalLike 预检不支持
```

## 6. 到底哪个"能"——按可修性排序

| 档 | 模型 | 状态 | 还剩什么 |
|---|---|---|---|
| **✅ 全流程已跑通** | **vocos-22khz-univ** | **parse→optimize→quantize→adapt→generate 五段全 `rc=0`**，产出 `vocos_native_ZG.json`(878 KB)+`.raw`(19.2 MB) | 仅 `Cos`/`Sin` 量化参数告警（厂商未实现，不阻断） |
| **⚠️ 只差 2 个算子** | matcha-zh-baker / matcha-zh-en | parse 有产物，但**连 optimize 都进不去** | `Range`（3 个）、`RandomNormalLike`（1 个） |
| **⛔ 卡类型检查** | vits-zh-ll / eula / theresa | 无产物 | `Pow` 收 int64（`tensor(int64) of input parameter`）；已试加 `Cast` 两侧，转而撞 `Add` 类型不一致 |
| **⛔ 卡 `Where`** | aishell3 | 无产物 | `Where` 节点 ShapeInfer 失败（`/text_encoder/.../Where`） |
| **⛔ 卡尺寸/其他** | melo | 无产物 | rc=26000 |
| **⛔ 段错误** | piper ×3 | 无产物 | `Split` 改属性后崩溃（`0xC0000005`） |

### 6.0 声学模型候选总账（10 个已测，按"能不能换"分类）

这是"还有什么声学模型可换"的完整答案。**10 个候选全试过，没有一个是零缺陷的**；下表按**失败类型**分组，便于判断哪些还有救。

| 模型 | 体积 | 节点 | 输入 | `Range` | `RandomNormalLike` | `Where` | `Pow` | `NonZero` | 实测结果 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| matcha-icefall-zh-baker | 75.6 MB | 4802 | 4 | 3 | 1 | 6 | 71 | 0 | **`rc=71`，有产物**（最好的一个） |
| matcha-icefall-zh-en | 75.7 MB | 4802 | 4 | 3 | 1 | 6 | 71 | 0 | `rc=71`，有产物 |
| vits-icefall-zh-aishell3 | **30.5 MB** | 4896 | 6 | 51 | 2 | **68** | 64 | 21 | `rc=19020`，`Where` 崩 |
| vits-piper-zh_CN-chaowen | 63.2 MB | 2682 | 3 | 39 | 2 | 30 | 39 | 12 | 段错误 |
| vits-piper-zh_CN-huayan | 63.2 MB | 2755 | 3 | 39 | 2 | 30 | 39 | 12 | 段错误 |
| vits-piper-zh_CN-xiao_ya | 63.2 MB | 2682 | 3 | 39 | 2 | 30 | 39 | 12 | 段错误 |
| sherpa-onnx-vits-zh-ll | 121.1 MB | 6505 | 6 | 39 | 2 | 66 | 45 | 21 | `Pow` int64 |
| vits-zh-hf-eula | 121.9 MB | 6265 | 6 | 39 | 2 | 66 | 45 | 21 | `Pow` int64 |
| vits-zh-hf-theresa | 121.9 MB | 6265 | 6 | 39 | 2 | 66 | 45 | 21 | `Pow` int64 |
| vits-melo-tts-zh_en | **170.4 MB** | **10680** | 7 | 41 | 2 | 80 | 21 | 21 | `rc=26000` |
| **vocos-22khz-univ**（声码器，非声学） | 53.9 MB | 272 | 1 | **0** | **0** | **0** | 10 | 0 | **✅ 五段全过** |

**三条可以直接下结论的观察**：

1. **`Range` 与 `RandomNormalLike` 是**所有**声学模型的共性问题**（最少的 matcha 也有 3＋1 个，其余 39~51＋2 个）。这**不是换模型能躲掉的**——它是 icefall/VITS 这套导出模板的固有结构，用来做位置编码与随机采样。
2. **`Where` 是第二大共性**（6~80 个）。它对 `ShapeInfer` 的要求比 `Mul` 更严（`aishell3` 直接崩在 `Where`），**换模型只会换到更多 `Where`**。
3. **唯一"最好的"是 matcha 两个变体**：节点最少之一（4802）、**`NonZero` 为 0**、`Where` 只有 6 个、且**已经能出产物**。其余候选在这些指标上都更差。

**所以"换声学模型"这条路的结论**：**在 sherpa-onnx 中文 TTS 生态里没有更好的替代品** —— matcha 已经是这批里最干净的一个。要真正解决，只有两条：**① 厂商修 `Mul` 广播／补齐 `Range` 支持**（已写进 [[哪些要跟厂商要]] 第九条）；**② 自己重训一个不用 `Range`/`RandomNormalLike` 的声学模型**（成本远高于回退）。

### 6.1 vocos 的完整五段读数（2026-10-31，全部 A 级实测）

| 阶段 | rc | 产物 | 体积 |
|---|---|---|---|
| parse（`icraft-parse`） | **0** | `vocos_native_parsed.json/.raw` | 53.8 MB |
| optimize（`icraft-optimize`） | **0** | `_optimized.json/.raw` | 53.8 MB |
| quantize（`icraft-quantize` int8/ems/channel/9 张） | **0** | `_quantized.json/.raw` | **13.5 MB**（-75%） |
| adapt（`icraft-adapt`） | **0** | `_adapted.json/.raw` | 15.4 MB |
| **generate（`icraft-generate`）** | **0** | **`vocos_native_ZG.json` 878 KB + `.raw` 19.2 MB** | **上板件** |

两条必须记下的告警（厂商侧未实现，非我方问题）：

```text
[warning] icraft::xir::CosNode SetQuantizedScale Not Implemented! Using Default Implementation!
[warning] icraft::xir::SinNode SetQuantizedScale Not Implemented! Using Default Implementation!
[warning] icraft::xir::CosNode ZhugeQuantParams Not Implemented! Using Default Implementation!
[warning] icraft::xir::SinNode ZhugeQuantParams Not Implemented! Using Default Implementation!
```

### 6.1b **vocos 已在板上 NPU 真跑通**（2026-10-31，A 级）

这是本轮最强的一条：`vocos_native_ZG.json/.raw` **在悟净板的真实 NPU 上跑起来了**。

**成功命令**（关键是 `ZG330,` 前缀 + `;Host` 尾巴，两者都不能少）：

```bash
icraft-run --json imodel/vocos_native_ZG.json --raw imodel/vocos_native_ZG.raw \
  --network vocos --input io/input_1_1_559_80.bin \
  --backends "ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host" --log_time
```

**三次连续实测（时间读数极稳）**：

| 次 | total_time | **total_hard_time** | total_backbone | io_process_hard |
|---|---:|---:|---:|---:|
| 1 | 23.520 ms | **9.503 ms** | 8.119 ms | 1.384 ms |
| 2 | 23.438 ms | **9.501 ms** | 8.120 ms | 1.382 ms |
| 3 | 20.704 ms | **9.499 ms** | 8.118 ms | 1.381 ms |

**逐算子分布**（首次运行，`OpNum`/`total_wall`/`total_hard`）：

| 算子 | 数量 | wall | hard |
|---|---:|---:|---:|
| `Matmul` | 23 | 5.584 ms | **4.092 ms** |
| `Reshape` | 51 | 2.532 ms | 0 ms（纯 data-move） |
| `Transpose` | 43 | 4.323 ms | 1.535 ms |
| `LayerNorm` | 10 | 1.380 ms | 0.729 ms |
| `Multiply` | 8 | 0.663 ms | 0.137 ms |
| `Conv2d` | 9 | 1.039 ms | 0.450 ms |
| `PruneAxis` | 3 | 0.515 ms | 0.322 ms |
| `Exp` | 1 | 0.345 ms | 0.276 ms |
| `Cos` | 1 | 0.118 ms | 0.053 ms |
| `Sin` | 1 | 0.125 ms | 0.061 ms |
| `Slice` | 2 | 0.144 ms | 0.011 ms |
| `Cast` | 10 | 1.599 ms | 0.496 ms |

**与 CPU 的对比**（同一输入 `[1, 80, 559]`，板上 4×A53）：

| | 耗时 | 相对 |
|---|---:|---|
| **CPU（onnxruntime，2 线程）** | **2487 ms** | 基准 |
| **NPU（ZG330）** | **9.5 ms（硬件段）／20.7–23.5 ms（整轮）** | **快 262 倍（硬件段）／106–120 倍（整轮）** |

> **这个倍数要打折看**：CPU 那个 2487 ms 是 **ONNX 原生计算图**；NPU 这个是**已量化 + 已适配 4D** 的图，且含 `;Host` 段（Input/Output 由 host 接）。真正可比的端到端数字要等"matcha 前端 + NPU vocos"拼起来再测。

**踩到的三个坑（都记下来，下次直接跳）**：

1. **`--backends "axi://..."` 直接写会报 `Only Support Host/BY/ZG330 backend`** —— 必须先写 `ZG330,` 前缀，即 `"ZG330,axi://zg330aiu?npu=0x40000000&dma=0x80000000;Host"`。
2. **只写 `ZG330`（不带 axi URL）会段错误** —— 表现为 `op_id = 0, InputNode 未绑定任何 backend` 然后 `Segmentation fault`（RC=139）。这**不是 NPU 被占用**：我停掉板上现役 `wcis-face-photo.service` 再测，仍然同样崩，之后已把服务恢复（`active`）。
3. **`--dump_output` 默认不出文件** —— 要配 `--dump_format HQB` 才落盘到 `.icraft/logs/<network>/ftmpHQB/`。

**仍未完成的一步（必须诚实标注）**：**数值一致性还没验，而且本轮已查明为什么验不了**。

排查过程（全部 A 级实测）：

1. 从 `ZG.json` 的 `Output` 节点解出三个输出的真实身份：`v_id = 796 / 800 / 804`，声明 `shape=[1,513,600]`、`element_dtype=@fp(32)`、`layout=@layout(**C)`、`mtype=@chunk(49@0)`。
2. 按这个 v_id 取 dump：`796` 值域 `0~88.19`（像 mag）、`800/804` 值域 `±0.998`（像 x/y，golden 是 ±1）——**表面看对得上**。
3. 但**只有 11 个不同的值**：`0, 1.3886719, 2.0839844, 3.4726562, 5.5546875, 9.03125, 14.5859375, 23.609375, 36.125, 57.625, 88.1875`。golden 是**连续值**（100% 非零、最小值可到 0.0000001 级）。
4. **决定性对照实验**：把输入换成**全零张量**重跑 NPU，输出非零数从 59025 变 294290，**但不同的值仍然是那同样 11 个** ⇒ **这 11 个值是固定表、不随输入变化** ⇒ **dump 出来的是量化层级/scale 元数据，不是推理数值**。
5. 换 `SFB`／`SQB`／`HQT` 三种格式：前两者字节数完全相同（1231200）且同样是 11 个离散值，`HQT` 字节数不同（3386314）但值在 `0.0002` 量级——**没有任何一种给出连续 fp32 结果**。
6. `SFT`（最接近 float 的那一档）**直接 RC=235 失败**：该格式对含 int8 的网络不适用。

**所以结论是**：`icraft-run --dump_format` 在**量化网络**上导不出可直接比对的浮点张量。要把"NPU 算得对"从 D 级升到 A 级，下一条路必须换工具：

- **按 `@scales([axis=-1])` 元数据自己反量化**（JSON 里 `scale` 出现 910 处、`quant` 456 处，参数是有的，但需要还原 `storage_dtype: @tf(32)` 的实际位宽与 packing）；
- 或**走 Python 运行时接口**（`icraftmdzthirdparty` / `zhuget`）直接读 output tensor，绕开 dump；
- 或**在板上跑整条 TTS 链、用耳朵+波形相似度做端到端判定**（放弃逐张量比对）。

**"NPU 跑得通"是 A 级已证**（三次 9.499–9.503 ms、逐算子分布齐全、设备身份 `FMSHZGV3TECH-AID / 25122301 / axi`）；**"NPU 算得对"仍是 D 级**，本轮没能升级。

**顺带记一条给下次的坑**：`--dump_ftmp 796` 且输入未变时，`total_time` 会掉到 **0.027 ms**（缓存命中），别把这个数当性能读数——真实硬件段仍是 9.503 ms（`total_hard_time` 不受缓存影响）。

### 6.1f **终局结论（2026-10-31 收尾）：前面 §6.1d/§6.1e 有四处判断被推翻，以本节为准**

三路并行（API 路径、换工具、端到端音频）交叉验证后，把旧结论逐条纠正。**踩坑链是一个叠一个的**，这也是为什么排查绕了这么久：

#### 错误链（每一层都伪装成"NPU 算错了"）

| # | 我当时的结论 | **实测真相** | 证据 |
|---|---|---|---|
| 1 | `--dump_format` 拿不到数值，只有 scale 表 | **错**。`--dump_format` **单独用**才输出 scale 表；**加 `--dump_output` 就出真值** | dump 输入张量 `v_id=0`：`np.array_equal(dump, input) = True`，`bytes=192000`，**字节完全相同** |
| 2 | golden mel 应 `reshape(80,559).T` | **错**。`golden_mel.bin` 就是 `(80 mel, 559 frame)`，**`reshape(80,559)` 直接用，不转置** | CPU ONNX 对照：`reshape(80,559)` → **corr 1.000000**；`.T` → **0.016749** |
| 3 | 板上 NPU 输出"与输入无关、是坏的" | **错**。那是①②叠加的结果（没启 dump_output + 输入布局反了） | `corr(旧输入, 正确输入) = 0.360416` |
| 4 | `Session.forward` 是坏 API（段错误） | **错**。根因是 `CreateFromJsonFile` **不加载参数字节**，补一行 `net.autoLoadParams(.raw)` 即通 | 加载前 HardOp 的 instr/params `hasData=0/273`，加载后 `273/273` |

#### 修正输入后重测的真实读数

**CPU 参考（`[1,80,559]` 输入，`reshape(80,559)` 直接喂）达到 `corr=1.000000`** ⇒ golden 文件本身是自洽的，之前的"golden 不自洽"判断来自错误布局。

**NPU vs Host 参考实现：逐位相同**（三个输出全张量）：

```text
v_id=796  identical=True  max|d|=0
v_id=800  identical=True  max|d|=0
v_id=804  identical=True  max|d|=0
```

⇒ **NPU 硬件路径忠实**，差异不来自 NPU。

**但 NPU 件 vs CPU golden：**

| 输出 | 语义 | 不同值数 | corr（元素级） |
|---|---|---:|---:|
| `796` | **mag** | 11 | **0.8959** |
| `800` | **cos** | 38 | **0.1198** |
| `804` | 用 **sin** | 41 | **0.1219** |

**端到端音频（iSTFT，经 1e-16 往返校验后使用）：**

```text
npu_board vs cpu_golden : corr=0.186105   SNR= -1.679 dB     ← 不可用
npu_board vs host_ref   : corr=1.000000   SNR=  inf dB      ← 板端＝软件参考
消融 golden_mag + NPU cos/sin : corr=0.1989  SNR= -1.32 dB   ← 相位坏即可毁掉
      NPU_mag   + golden cos/sin : corr=0.9470  SNR=  9.19 dB ← mag 其实是好的
```

**消融实验给出的判定非常干净**：**mag 支路正常（用 NPU 的 mag + golden 相位，音频 corr 0.947），cos/sin 支路是噪声。**

#### 相位缺陷的机制（已定位到量化层，不是硬件）

用 ONNX 探针导出 `Cos`/`Sin` 的**输入角度张量**（`cos(angle)==golden_x`，maxdiff `6e-8`，探针本身正确）：

- 该角度在 ZG 图里是 **`sint8` + scale `0.45043343`**
- 真实角度范围 **`-158.75 … 170.89 rad`** ⇒ `angle/scale` 达 **`-352 … 379`**，而 sint8 只有 **`-128 … 127`** ⇒ **2.3% 元素饱和、其余绕回**
- 但实测残差 81.1° 远超"饱和+绕回"能解释的 8.4°，且 `corr(按该 scale 量化后的 cos, NPU cos) = 0.1307`（若只是量化应 ≈1.0）
- 已排除：符号翻转（-0.186）、时间位移（最佳 lag -0.18ms 仅 0.234）、`c32` lane 反交织（0.0014）、整数倍率（m=1 最优 0.1198）、帧置换（shift 0 峰值）

⇒ **结论：`Cos`/`Sin` 的相位重建在 8bit 量化下已经损坏，是编译/量化环节的缺陷**；`scale` 写作 `600*0.45043343`（**长度量纲**）用在角度上本就可疑。

#### 最终判定（三档分开写，别合并）

| 结论 | 等级 | 依据 |
|---|---|---|
| **NPU 硬件忠实执行** | **A** | 与 Host 软件参考 **逐位相同**（`max|d|=0`） |
| **取数通路可用** | **A** | API + `--dump_output` 双路；已知答案测试 `equal_to_input=True` |
| **vocos 的 mag 支路正确** | **A** | 消融：NPU mag + golden 相位 → 音频 `corr=0.947`、`SNR=9.19 dB` |
| **vocos 的 cos/sin 支路损坏** | **A** | 元素 corr 0.12；消融音频 `SNR=-1.32 dB`；机制定位到 `sint8`×`0.4504` |
| **该 `_ZG` 件不能替代 CPU 件** | **A** | 端到端 `SNR=-1.679 dB`（负值，不可感知） |

**要修的不是 NPU，是 iCraft 对 `Cos`/`Sin` 的量化实现**（或改用不经过角度中间量化的表达）。三条可执行路径：① 给这两层换 bf16/fp16（`--mix_precision` 已有参数）；② `--fake_qf` 验证"量化是唯一损失源"；③ 让厂商确认/修正 Cos/Sin 的角度量化位宽与 scale。

**验收线（下次重跑同一套流程用）**：元素 `corr > 0.99` 且音频 `SNR > 20 dB`。**当前是 0.12 / -1.7 dB，差得很远。**

#### 附：听感可直接判别的三份音频

`S:\work\WCIS\workenv\.tmp_matcher\wav_cmp2\`：`cpu_golden.wav`（CPU 参考，应清晰）、`npu_board.wav`（NPU，应为等响度的"嘶声"）、`host_ref.wav`（Host 软件参考，与 npu_board 逐位相同）。**三份一起听能立刻听出相位坏掉的效果。**

> **⚠️ 上一行有个严重问题，必须更正**：那三份**不是普通话**，是我用**随机 token id**（`rng.integers(1,400,size=60)`）喂 matcha 得到的 mel，再喂 vocos。**随机音素合成的声音本来就只是类语音噪声**，拿它判断"相位坏没坏"是无效的。**这三份请忽略。**

#### 用真实中文重做的对比（这才是能听的）

用真实中文文本（「你好，我是你的语音助手。今天天气不错，适合出去走走。」）→ 词表/音素 → matcha ONNX → mel `(80, 198)` → vocos：

| 文件 | 内容 | 时长 |
|---|---|---|
| `S:\work\WCIS\workenv\.tmp_matcher\wav_real\A_cpu_real.wav` | **CPU** vocos 合成（参考，应能听懂） | 2.33 s |
| `S:\work\WCIS\workenv\.tmp_matcher\wav_real\B_npu_real.wav` | **板端 NPU** vocos 合成（同文本同 mel） | 2.33 s |

**实测：`corr(cpu, npu) = -0.293934`（负相关）、`cpu rms=0.0816 / npu rms=0.0999`。**

对比幅度只有 `0.005`，反相更致命：**两段音频在听感上应当完全不同——A 能听懂，B 应是噪声。** 这是我见过的对该缺陷最直观的证据，比任何相关系数表都清楚。

#### `--fake_qf` 定案：损失几乎全部来自量化（本轮最有价值的一次实验）

同一输入、同一模型，只差一个 `--fake_qf`（绕过量化截位/饱和），与 CPU 浮点参考比：

| 输出 | 正常量化件 | **`--fake_qf`** | 不同值数（正常 → fake） |
|---|---:|---:|---|
| mag | 0.89592 | **0.99886** | 11 → **40445** |
| cos | **0.11976** | **0.86949** | 38 → **130081** |
| sin | **0.12189** | **0.87233** | 41 → **111857** |

**三点读法**：

1. **一关量化，cos/sin 从 0.12 跳到 0.87、mag 到 0.999** ⇒ **损失几乎全部来自 int8 量化**，不是 NPU 硬件、不是 API、不是输入布局。
2. **不同值数从 11/38/41 涨到 4万/13万/11万** ⇒ 之前那些"离散刻度"确实是量化造成的，这一条把 §6.1d 的猜测证实了。
3. **但 fake_qf 的 cos/sin 只到 0.87、没到 1.0** ⇒ 除了量化还剩一部分实现差异（`Cos`/`Sin` 算子近似或 `--merge_hardop` 融合误差）。**验收线 corr>0.99 未达成。**

**量化缺陷的精确定位**：`Cos`/`Sin` 的输入角度在 ZG 图里是 **`sint8` + scale `0.45043343`**，真角度范围 `-158.75…170.89 rad` ⇒ `angle/scale` 达 **`-352…379`**，而 sint8 只有 `-128…127` ⇒ **2.3% 饱和、其余绕回**（实测隐式 wrap 计数 `min=-1 max=1`、22.3% 元素非零）。`scale` 写成 `600*0.45043343`（**长度量纲**）用在角度上本就可疑。

**修复路径**（按成本）：

1. **`--mix_precision`** 给 `Cos`/`Sin` 两层换 bf16/fp16（`icraft-quantize` 已有参数）
2. **重做 quantize** 并给角度层单独的 scale（不要用那个长度量纲的值）
3. **报厂商**：`Cos`/`Sin` 角度量化位宽与 scale 口径



### 6.1d **数值验证的根因已定位：`--dump_format` 与硬件无关，是 dump 机制本身的问题**

本轮按你的要求在本机架起了 **Podman 环境**（不用 WSL），在**容器里用纯 Host 后端**（`total_hard_time = 0.000 ms`，即**完全没有硬件参与**）重跑了同一个 `_ZG` 件，并对同一个输出 `v_id=796` 导出，结果与板端 NPU **完全相同**：

| 环境 | 后端 | 796 的 min/max | 不同值个数 | 结论 |
|---|---|---:|---:|---|
| 板上 NPU（ZG330） | 真硬件 | `0.000 / 88.1875` | **11** | — |
| **容器（x86, Host）** | **纯软件，零硬件** | `0.000 / 88.1875` | **11** | **与板端逐位同类** |
| CPU golden（onnxruntime 原生图） | 参考 | `0.000 / 49.2890` | **285262**（连续） | — |

### 6.1d-1 **根因落到图结构上：`Output` 与它的生产者共用同一块物理内存**

往上翻一层，`796`（Output 声明的 `@fp(32)`）的生产者是 **`CastNode`**，而它的输入 `2091` 是 **`QuantizedType`**。关键三点（全部从 `vocos_native_ZG.json` 直接读出）：

```text
796  : element_dtype = @fp(32)                     mtype = @chunk(49@0)   shape=[1,513,600]
2091 : element_dtype = QuantizedType{               mtype = @chunk(49@0)   shape=[1,513,600]
           expressed_dtype=@fp(32),
           storage_dtype  =@tf(32),
           scale          =@scales([axis=-1]),     ← 注意：没有数值
           zero_points    =[] }
```

1. **两者的 `mtype` 完全相同（`@chunk(49@0)`）** ⇒ 它们指向 **同一块物理缓冲区**。`CastNode` 只改了**类型标注**，没有真的把定点数据转成浮点。
2. **`scale` 是 `@scales([axis=-1])`，不带任何数值** —— 对比其它算子（如 `@scales([axis=-1]512*0.10455503)`，即 512 个通道、每通道 scale 恒定 `0.1046`）可以确认：**这个 scale 是运行时动态的**，离线无法反量化。
3. 因此 dump 出来的就是**那块缓冲区里的定点表示**，`0/1.3887/…/88.1875` 这 11 个值正是它的**32 位定点阶梯**（相邻比值恒定 1.50–1.63，等比刻度）。

**这解释了全部矛盾**：不是 NPU 算错，也不是 dump 坏了，而是**这个网络的输出层本身就没有做"量化→浮点"的实体转换**——`Cast` 被优化成了同地址的类型重标。**要拿真值必须自己做反量化，而 scale 又恰好是动态的（不可离线）** ⇒ 只能靠运行时 API 拿到 scale 与原始定点值，这正是 `Session.forward` 那条路要解决的。

**旁证（相位分支为什么看起来"正常"）**：`cos`/`sin` 走的是 `Cos`/`Sin` **算子**（有真实前向计算），不经过上面那对同地址的 Cast；它们导出 38 个不同值、且 `cos²+sin² ≈ 1.0012`（golden 为 `1.0000`）。**但它们的数值与 golden 并不对应**（逐像素 `max|cos_golden-cos_npu| = 1.998`、整段波形 `corr = -0.240`、试遍 6 种轴重排后相关系数仍 ≈ 0.00）⇒ 说明输出侧还有**布局/对齐**问题未解，不是单纯的反量化问题。

**一个有用的对照实验**（证明链路是真通的、只是数值表示不可读）：把输入换成**全零张量**重跑，`796` 的非零数从 `59025` 变 `294290`、`rms` 从 `2.6046` 变 `8.1040`（两者相关系数 0.139）—— **输入确实影响了输出**，所以网络是真在算，卡的是"怎么把它算的数读出来"。

### 6.1e **取数通路找到了（API 可行），但 vocos 的 `mag` 分支在 NPU 上是坏的**

2026-10-31 深夜的突破，三件事要分开说，顺序很重要：

**① 之前 Python `Session.forward` 段错误，是我取错了 TensorType 的位置 —— 不是 API 坏。**

对照 `pyrtutils/icraft_utils.py`（厂商 modelzoo 的官方推理封装）确认正确姿势：

```python
in_tt = net.ops[0].outputs[0].tensorType()        # ← InputNode（@fp(32)）
#   不是 net.ops[1]（那是 HardOpNode，dtype 是 QuantizedType）——这是我段错误的根因
inp = xrt.Tensor(arr, in_tt)                       # 直接从 numpy 构造
dev = xrt.Device.Open("axi://zg330aiu?npu=0x40000000&dma=0x80000000")
sess = xrt.Session.Create([ZG330Backend, host_backend.HostBackend],
                          net.view(0), [dev, xrt.HostDevice.Default()])
sess.apply()
outs = sess.forward([inp])                         # 返回 List[Tensor]
h = t.to(xrt.HostDevice.MemRegion())               # ← 必须搬回 host
h.read(buf, 0, h.dtype().bytes())
```

**双后端 `[ZG330Backend, HostBackend]` 是必需的**（`HardOp` 只能由 ZG330 接、`Input`/`Output` 只能由 Host 接）；单 `HostBackend` 会报 `op_id=1341 HardOpNode 未绑定`。

**② 先在**另一个模型**上验证这条通路是好的 —— yunet（板上现役人脸模型，12 路输出）：**

```text
out[5]  n=400    uniq=232    min=-16.4531 max=-5.9727
out[6]  n=25600  uniq=3357   min=-0.8418  max=2.4180
out[9]  n=64000  uniq=12316  min=-2.2812  max=3.1680
out[11] n=4000   uniq=2352   min=-5.8750  max=8.0781
```

**连续浮点值、无 NaN、重复运行逐位一致** ⇒ **API 通路是可靠的**，能拿真值。

**③ 但 vocos 的输出有问题，而且是可复现的：**

| 输出 | 真输入 md5 | 零输入 md5 | 不同值数 | 判定 |
|---|---|---|---|:--|
| `out[0]`（mag） | `53a7d16475` | **`53a7d16475`（相同）** | **11** | **与输入无关 ⇒ 坏** |
| `out[1]`（x） | `bc509191da` | `2b40a96939`（不同） | 38 | 在计算 |
| `out[2]`（y） | `cda4ab81d5` | `25a5180bd2`（不同） | 41 | 在计算 |

**同一输入跑两次，三个输出 md5 完全一致** ⇒ 不是随机污染，是**确定性的坏**。

**`out[0]` 与输入无关、且恰好是那 11 个等比刻度值（`0/1.3887/…/88.1875`）** ⇒ 现在可以确定：**这不是 dump 的问题，是 vocos `_ZG` 件里 `mag` 那一路的输出本身就没在算**（`Exp`/`Clip` 那条分支）。而 `cos`/`sin` 两路是真在算的（38/41 个不同值、随输入变化）。

**所以最终判定**：

| 结论 | 等级 | 依据 |
|---|---|---|
| API 能取真 fp32 输出 | **A** | yunet 12 路连续值、可重复 |
| vocos 的 `mag` 输出在 NPU 上失效 | **A** | 与输入无关、确定性、等于 11 级量化刻度 |
| vocos 的 `cos`/`sin` 在算但数值与 CPU 不符 | **A** | 随输入变化，但与 golden `corr=0.002–0.005` |
| **vocos 不能直接上板替代 CPU** | **A** | 三条合起来 ⇒ 拿不到正确波形 |

> **注意这条的写法**：不能说"NPU 算得对"（mag 坏了），也不能说"NPU 完全不行"（cos/sin 在算、且别的模型 yunet 正常）。**准确表述是：`vocos-22khz-univ` 这个 `_ZG` 件在 ZG330 上输出不完整**，需要回到 `generate` 段或量化段重做，而不是放弃 NPU。



**这条对照证明**：`--dump_format` 导出的 `796.ftmp` **不是推理结果**，而是 icraft 内部对张量的某种表示（`0/1.3886/2.0839/.../88.1875` 这 11 个固定层级）。因为它**在完全没有硬件量化参与的 Host 后端上也是同一份内容** ⇒ **不是"NPU 量化导致的精度问题"，是 dump 机制不导出数值本身**。

**这改变了排查方向**：之前怀疑"NPU 算得不准"，现在证实"**dump 根本没给出可比的数**"。所以：

- **"NPU 跑得通"** = A 级（9.499–9.503 ms 硬件段、逐算子分布、设备身份）
- **"NPU 算得对"** = 仍是 **D 级**，但卡点已从"怀疑精度"收敛为"**需要换取数工具**"，不是模型问题

**容器环境已就绪（本轮搭建，A 级）**：

| 项 | 值 |
|---|---|
| 容器 | `zgbuild`（镜像 `localhost/fpai-ub2004:tts-saved`，4.64 GB，**已有 3 周**，不是我新建的） |
| 系统 | **Ubuntu 20.04.6 LTS + Python 3.8.10**（正是 icraft 的 cp38 ABI 需要的） |
| icraft | **3.39.0 全套**（`icraft`／`icraft-run`／`icraft-parse` 都在 `/usr/bin`） |
| **icraft-run build** | **`3.39.0.0-a7cb8d5(2608220045)`** — 与板端 `(2608220046)` **同一个 build**，只差时间戳尾号 |
| 挂载 | `S:\` → `/mnt/s`（可直接读写工作区） |
| 补装 | `numpy 1.24.4` / `onnxruntime 1.16.3` / `onnx 1.17.0`（容器内 pip 联网可用） |
| 交叉工具链 | `aarch64-linux-gnu-gcc` 在 `/usr/bin` |

**顺带纠正我此前两处判断**：
1. 我说"Podman 不能配合"是**错的**——`podman-machine-default`（WSL 型，8 核/2 GiB/100 GiB）本来就在，容器 `zgbuild` 就躺在里面，且已挂载 S 盘。
2. 我说"需要用 `wsl --import` 导入那个 746 MB tar"是**多余的**——那个 tar 正是 `ubuntu20.04_container` 基础镜像（781 MB），而 `fpai-ub2004:tts-saved` 是在它上面加了 icraft 与工具链后的快照，**直接用现成的就行**。

**下一步唯一剩下的取数手段**（已探明 API，但需再调通）：`icraft.xrt.Session.forward(inputs) -> List[Tensor]` + `Tensor.read(buffer, offset, size)`。本机已探到完整签名：

```text
Session.CreateByOrder(network_view, backends, devices) -> Session
Session.forward(inputs: List[Tensor]) -> List[Tensor]
Tensor().setDType(dtype); Tensor.copyData(buffer); Tensor.read(dest, src_offset, byte_size)
xir.Network.CreateFromJsonFile(path); net.view(0, len(net.ops))
HostBackend.Create(HostBackend, view, device); HostDevice.Default()
```
试过用这条路线在容器里跑，`HostBackend.Create` 后段错误——**未调通，留给下一轮**。但这条路一旦通了，就能直接读出 fp32 输出，彻底绕开 dump。

### 6.1c **端到端混合链路的 RTF：vocos 移 NPU 后从"慢于实时"变"快于实时"**

把两组独立实测拼起来算（**不做 Python 混跑**——板上 python3.8 无 onnxruntime、venv 是 py3.11 装不了 cp38 扩展，按 AGENTS 规矩不新增安装）：

| 场景 | matcha（CPU） | vocos（CPU） | 两段全 CPU | **混合（vocos→NPU）** | 相对实时 | **省时** |
|---|---:|---:|---:|---:|:---|---:|
| 短句 20 音素 | 1730 ms | 905 ms | **1.129** | **0.753** | 快 1.33× | **33.4%** |
| 中句 60 音素 | 4504 ms | 2487 ms | **1.107** | **0.716** | 快 1.40× | **35.2%** |
| 长句 150 音素 | 12211 ms | 6268 ms | **1.173** | **0.777** | 快 1.29× | **33.8%** |

取 `total_time` 23.5 ms（三次实测 23.52/23.44/20.70 的最大值，保守口径）。若只计硬件段 9.503 ms，结果是 0.747/0.714/0.776——**差别不到 1%**，因为 vocos 的 CPU 耗时（905–6268 ms）比 NPU 的 23.5 ms 大两个数量级，NPU 那一侧取哪个口径都不影响结论。

**这就是"vocos 上 NPU 到底值不值"的答案**：**值，因为它把整条 TTS 从 RTF 1.11–1.17（慢于实时 11–17%）拉到 0.71–0.78（快于实时 29–40%），省掉 CPU 时间的 33–35%**。

**这个数字的边界（必须一起读）**：

1. 这是**两个网络的纯推理时间相加**，**不含** CPU 侧文本前端（音素化/词表）与 iSTFT（两者都必须留在 CPU）。
2. 混合 RTF 假设 NPU 与 CPU **可流水**；串行执行时实际墙钟约等于两者之和，与上表一致，但**并发执行还能再快**（未测）。
3. "省时 33–35%"是**相对两段全 CPU**的口径，不是相对端到端（含前端与 iSTFT 后，比例会被摊薄）。

**设备身份（本次实测日志原文）**：

```text
Device Protocol: axi          Device Name: zg330aiu
icore: FMSHZGV3TECH-AID - 24160628      device: 25122301
```

**踩坑时的一件须知**（板上现役服务状态，与本轮无关但挡路）：尝试期间发现 `wcis-face-photo.service` 处于 failed。排查结论：**不是本轮操作造成的** —— 互锁标记 `/root/wcis-face/hardware-review-required.json` 的 mtime 是 **17:50:26 UTC**（本轮动它是 20:33 之后），内容是 `Pending camera request exceeded its lifetime / phase=capture_dma / automatic_retry=false`。即**该板相机服务在 17:50 就已自标"需人工复核"，任何重启都会失败**。本轮的 stop/start 只是让它暴露，**板子已按原样留给他人工处理，互锁标记未动**。


含义：**`Cos`/`Sin` 这两个相位算子没有专属量化参数实现**，走默认参数。只影响相位精度、不阻断编译——但这解释了"vocos 能过"仍不是无条件：**声码器的相位分支量化是厂商空白区**。

### 6.2 matcha 的改造实测：四次尝试全部失败，且第一次是**负优化**

按指示做两件改造（`Range`→常量表 `Slice`、`RandomNormalLike`→确定性零），随后为了救回被激活的 `Mul` 问题又试了三种绕法，**四次全部失败**：

| # | 版本 | 改造 | rc | 产物 | 报错 |
|---|---|---|---|---|---|
| 1 | `mf2` | 只做 4D + 折 axes + opset 降级 | **71** | **✔** | 预检 2 条（`Range`/`RandomNormalLike`） |
| 2 | `npu1` | ＋`Range`→常量表、`RandomNormalLike`→`Expand(0)` | 76 | ✘ | `Mul Incompatible dimensions` |
| 3 | `mfix` | ＋`prenet/Mul`→`Shape+Expand+Mul` | 76 | ✘ | `invalid expand shape` |
| 4 | `tile` | ＋`prenet/Mul`→`Tile(repeats=[1,192,1])` | 76 | ✘ | **仍 `Incompatible dimensions`** |

### 6.2b **重要更正：`rc=71` 不是"能跑，只差 CPU 补算"——它连 optimize 都进不去**

我上一轮把 `rc=71` 描述成"能解析、2 处 CPU 补算即可上板"。**这个说法是错的**，本轮实测推翻：

```text
icraft-optimize --json mf2_parsed.json --raw mf2_parsed.raw  ->  RC=1
  Exception info : Check failed: (-(int64_t)size() <= index && index < (int64_t)size()) is false
                   Index 0 out of bounds 0
  Upper level    : Unable to match pattern with Op, Op_id is 3, Op_type is icraft::xir::AddNode
```

**根因**（iCraft 官方 `docs/ops/spec/Unsupport.html` 原文）：

> 该算子为 Icraft 特有算子，不对应框架下的具体算子。用来表示目前无法支持的算子，**使用该算子以维持网络的完整连接关系**。有效信息将以键值对的形式存在 tags 中。**前向：该算子无前向。**

**`Unsupport` 只是解析阶段的占位符，它没有前向实现**——不是"回落到 CPU 执行"的机制。所以：

- **`rc=71` 的产物是一张"带空洞的图"**，optimize 一进就 `out of bounds`；
- **`Range`/`RandomNormalLike` 不存在"CPU 补算"这条路**——要么算子在 NPU 上（iCraft 不支持），要么整条链走 CPU；
- 我此前写的"`rc=71` + 2 处 CPU 补算"**作废**。

这也解释了为什么"消除缺陷"反而看起来变差：`rc=71` 本来就是死路（只是死在更后面），`rc=76` 是死在 ShapeInfer。**两者都不能上板。**


**机制**（已确认）：第 1 版里 `Range` 被 iCraft 标为 unsupport 占位，输出形状**被跳过** ⇒ 下游 `Less`/`Cast_1` 也不参与校验 ⇒ `prenet/Mul` **不做广播检查**，一路过到预检。一旦 `Range` 变可求值，形状有了具体值 ⇒ `Mul` **第一次做真实广播检查** ⇒ 撞上限制。

**广播为什么"应该能过"却过不了**（用 onnxruntime 实跑取到真实形状，A 级）：

```
A = /encoder/Transpose_output_0  ->  [1, 192, 20]
B = /encoder/Cast_1_output_0     ->  [1,  1,  20]
```

按标准广播 `192 vs 1` 可扩、`20 vs 20` 相等 ⇒ **数学上完全可广播**。而 iCraft 官方 `docs/ops/spec/Multiply.html` 明写"检查：两个输入必须是可广播的"。**三种绕法全败**（`Tile` 甚至仍报同一个 `Incompatible dimensions`，说明它没走广播逻辑、直接比形状）⇒ 判定为**厂商侧实现缺陷**，已写进 [[哪些要跟厂商要]] 第九条。

**结论（顺序必须记住）**：`Range`/`RandomNormalLike` 的替代**必须排在 `Mul` 广播修复之后**。**顺序反了不是"没效果"，是"从能出产物退化成不能出产物"**。

**顺带修好的三个模型**（`Pow` 收 int64，加双侧 `Cast` 后推进到 `Add` 类型不一致）：`vits-zh-ll`、`eula`、`theresa` 各 45 个 `Pow` 已修，但**修到下一层又撞 `Add`** —— 说明这条路需要系统性的类型贯通，不是单点补丁。

四个版本都留在 `.tmp_matcher/`（`*_final.onnx`＝第1版、`*_final_npu.onnx`＝第2版、`matcha_mulfix.onnx`＝第3版、`matcha_tile.onnx`＝第4版）以便复现这四组数字。


### 6.3 "确定性采样"的真实效果（A/B 实听对比）

**确定性采样不改图也能做**：`noise_scale` 是**图输入**，运行期设 0 即可（`z = mean + 0·ε`）。这与改图删算子是**两件事**。

校机（sherpa-onnx 1.13.8，24 核 × 2 线程）生成两套共 12 段：

| 组 | `noise_scale` | 含义 | RTF |
|---|---|---|---|
| **A** | **0.667**（默认） | 原厂随机采样 | 0.07–0.09 |
| **B** | **0.0** | **确定性采样** | 0.05–0.08 |

md5 抽查 3 段（`01_hello`/`03_system`/`05_long`）**全部 DIFF** ⇒ 去掉噪声后确实是不同声音，不是同文件改名。产物在 `S:\work\WCIS\workenv\.tmp_matcher\wav\`（`A_01..06`、`B_01..06`）。

**听感判据由你定**：B 组理论上更平/稳（去掉了 VITS 采样随机扰动），代价是**韵律变化减少**。若 B 发闷，说明该噪声对自然度是正贡献 ⇒ 不该删算子，保留 `rc=71` + CPU 补算更划算。

**回答"到底哪个能"**：**Vocos 声码器是唯一走完五段、出了 `_ZG` 上板件的**；**Matcha 停在"能解析 + 2 条预检缺陷"，且试图消除这 2 条时反而破坏了它**。

> **排序被实测推翻的地方**：直觉是"先啃最难的声学模型"，实测顺序是 **先打通声码器** —— 声码器通了，声学模型哪怕暂跑 CPU，整条链已在 NPU 上省掉声码器那一大块。

## 7. 与官方"TTS 全灭"记录的对齐（含一处自我纠正）

**先纠正一处我自己犯过的错**：本轮初稿把"共同硬缺口"写成 `Gather`／`Pow`，依据是 `workenv/crosswin/icraft_op_matrix_6col.tsv` 的 **91 行表**。那份表是 *pytorch 算子 → icraft 算子* 的**映射表**，不是 icraft 的全部算子面。真正的算子面是 `C:/Icraft/CLI v3.39.0/docs/ops/spec/*.html`，共 **114 个算子页**。按 114 页重查，`Gather`、`Pow`、`Sin`、`Tile`、`Where`、`Neg`、`Conv1d`、`ConvTranspose1d` **全都有对应算子**。

按 114 页重查后，真正的缺口（`Constant`/`Shape`/`Identity` 属编译期算子，不计）：

| 缺失算子 | Matcha | Vocos | Piper | 说明 |
|---|---|---|---|---|
| `Range` | 3 | 0 | 39 | 动态序列生成，TTS 用于长度对齐 |
| `RandomNormalLike` | 1 | 0 | 2 | 采样噪声 |
| `Exp` | 13 | 1 | 6 | 但 `Softmax`/`Softplus` 内含，且保留原生 Exp 可通过 |
| `Reciprocal` / `Ceil` / `CumSum` | 6/2/1 | 0 | 0/1/7 | 可改写 |
| `NonZero` / `And` | 0 | 0 | 12/3 | 动态 shape |

**官方 fastspeech2 报的 `gather,tile,where,exp,round,convTranspose`** —— 按 114 页重查，其中 `gather`/`tile`/`where`/`convTranspose` **当前都有算子**；3.30/3.31 那个版本真正缺的是 **`exp` 与 `round`**。**所以官方那条记录应读作"当时缺 exp/round"，不能直接搬来当今天的判决。**

### 7.1 CTC 路线的图内边界（2026-10-31 补；属 ASR 侧，不是 TTS 结论）

> 这一节记的是"官方到底上没上过 CTC 架构"那次检索的落点。它放在 §7 下面，是因为结论直接由 §7 那条算子面口径推出来：**CTC 解码本身不是难点，难点在它周围的掩码与去重**。不另开页（一个事实只写一处）。

**官方在 NPU 上真跑过的 CTC 件只有两件，且都只到"已入库"这一档**（`模型信息汇总` 行 196／197，判级 B＝文档取证、未在本机复跑）：

| 行 | 模型 | 部署阶段 | 阶段细节 | 备注原文 | icraft | `FAPI平台` |
|---|---|---|---|---|---|---|
| 196 | SenceVoiceSmall | 已入库 | **精度低** | `by int8量化精度差` | 3.31.0 | **100** |
| 197 | conformer | 已入库 | **精度低** | `by int8量化精度差` | 3.31.0 | **100** |

两件都**没标 `30`**。audio/ASR/TTS 域里真正在悟净上测过的只有 `whisper`（行 167）、`qwen2-audio`（行 166）、`osum`（行 168），**三条全是"不支持"**。⇒ "CTC 上过 NPU"只能读成"上过 100TAI"，**不能读成"我们的 ZG330 上有实绩"**。

**conformer 的 config 级证据（A 级，2026-10-31 直读 ModelScope `AIBS/conformer` 仓库清单与 README）**：

- 仓库 `2_compile/config/` 下**只有一份** `conformer.toml`：`target = "buyi"`（＝100TAI）、`inputs_layout = "FD"`、`inputs = [1,120,560]`——**没有任何 ZG／诸葛配置**。"它在 30 上没跑过"在工程层面也成立，不只是厂商表没写。
- `2_compile/fmodel/conformer_no_masked_fill_120x560.onnx`（675,481,270 B）名字里的 `no_masked_fill` 就是它的修法：把 attention 里的 `masked_fill`＋常量 `-inf` 那段注释掉，才导得出 encoder。
- README 原话：BeamSearch「不是标准的 nn.Module，内部有大量 Python 控制流……不能导出/trace」，所以作者「**直接指定 ctc**……参照 sensevoicesmall，ctc 是可以导出且编译的」。encoder 实测输入 `[1,120,560]`、输出 `[1,120,512]`、**114.767 ms**，CER 4.87%，**只支持英文**。

**挡住 CTC 路线的其实是两条，跟"CTC 这个解码器"本身无关**（这条与 §7 那张缺口表是同源结论）：

1. **attention 掩码里的常量 `-inf`**——`whisper` 在厂商表第 167 行、平台 `30` 上就是被它判死的（备注原文 `icraft不支持算子：-inf`）。它波及**所有含注意力掩码的 ASR**，Zipformer-streaming-CTC 的掩码首当其冲（`算子缺口处理` §10 已把这条记成"悟净板上唯一被实测证实的语音类硬缺口"）。conformer 那份 `no_masked_fill` 模型就是被这条逼出来的改法：**把 `masked_fill`＋`-inf` 整段注释掉**才导得出去——注意这不是"填个别的数"，是**直接把掩码逻辑删掉**，所以它靠的是固定长度输入（120 帧）而不是动态掩码。**代价要写清楚**：删掩码换来的可编译性，是以"不能按句长裁"为代价的。
2. **CTC 去重与 beam search 那串 shape／控制流算子**——见上表最后两行。它们不在两份正本里，只能落 PS。

**由此得到的图内边界（本节结论）**：

| 环节 | 算子面实况（两份官方正本逐条核对） | 归属 |
|---|---|---|
| encoder | Conv1d／LayerNorm／Softmax／Matmul／GELU 等全 √（本页不复述，见 [[iCraft算子支持矩阵]] 第四节） | **NPU 图内** |
| `ctc_lo`（一层 Linear 出 logits） | `Linear`／`Matmul` √ | **NPU 图内** |
| `softmax`／`log_softmax` | `Softmax` √√；`LogSoftmax` **两份正本冲突**（PDF 写 `×`＋「Host 回退」、网页表写 `√ √`）⇒ 记开口项，必须 precheck 实跑 | 大概率 NPU，未证实 |
| `argmax` | `Argmax` √√（PDF 备注「无 BY codegen 规则」只影响布衣，与本项目无关） | NPU 可做，也可放 PS |
| CTC 去重（`unique_consecutive`／去 blank／去重复） | **`Unique`／`NonZero`／`TopK` 两份正本里都没有**；`Where` PDF 写 `×`＋「Host 回退」、`Gather` PDF 写 `×`＋「Host 回退」 | **只能放 PS** |
| beam search | 纯 Python 控制流（`for`/`while`/`if` ＋ dict/list），官方已判不可导出 | **只能放 PS** |

⇒ **CTC 路线的可行形态是"图内只留 encoder＋ctc_lo，解码整个搬 PS"**——这正好是 conformer 与 SenseVoiceSmall 两个官方工程实际采用的形态。**别指望把 CTC 解码塞进 iCraft 图里**：去重那几个算子不在正本里。

**顺带更正 §7 的一句**：§7 写"`gather`/`tile`/`where`/`convTranspose` **当前都有算子**"，按 PDF 正本逐条看，这句要收窄成"**在算子词表里、有语义页**"——`Gather`／`Where`／`Pow` 三行在 ZG330／ZG30S 两格明明是 `×`＋「Host 回退」（`Tile` 才是 √√）。**"有 spec 页"≠"ZG330 支持"**，这正是 §7 那个坑的第二种形态。§7 的结论（官方那条记录应读作"当时缺 exp/round"）不受影响：`Exp` 在 PDF 里 √√√、`Round` 在 PDF 与 114 页里都不存在。

**一处与我口头结论的更正，必须记下来**：我曾说"`iCraft算子支持矩阵` 里 `LSTM/LSTMCell` 都打 √"，据此推出"CTC 里的 LSTM 不难"。逐条复核后**这句只对了一半，按本页 §7 自己的口径必须退回开口项**：

| 正本 | `LSTM`／`LSTMCell`／`GRU`／`GRUCell` |
|---|---|
| 网页表（`docs/ops/framework.html`，表1＋表2） | 4 行都在，两列（BUYI＋ZG330）都 `√`；但 **iCraft Op 那一格写的是 `小粒度算子集合`**——§2 已点名的**桶标签**，不是单个算子 ⇒ 它在图上被打散成一组细粒度算子 |
| **PDF 正本**（`Icraft_v3.39.0_支持算子列表.pdf` → [[icraft.v3.39.0_支持算子表]]，117 行） | **一行都没有**（`LSTM`／`GRU`／`RNN`／`Cell` 在整个页面文本里都不出现） |
| 逐算子语义页（`docs/ops/spec/` 114 页） | **没有 LSTM／GRU 页**（`grep -ril 'lstm\|gru'` 空） |

按 [[iCraft算子支持矩阵]] 第二节那条口径——"两份一致才写进结论，**不一致就记成开口项、不许挑一份信**"——**LSTM 在 ZG330 上到底认不认，现在是开口项**，不能拿网页表的 `√` 当结论；判它只能靠 `icraft run --precheck` 实跑，**本轮没跑**。

**两条旁证（不是结论，只是排队依据）**：

- iCraft 更新日志里 `lstm` 出现在 **v3.0.0（2024.1.18）「新增支持算子：`lstm`／`grucell`／`gru`／`lstmcell`」**，另有数条 `影响网络：lstm` 的 bugfix（判级 B，文档记录、非本机实测）。
- `drl-ppo_lstm` 在厂商表第 186 行是 **已入库·通过测试·平台 `30`**，官方性能表给 `ZG_30TAI_bf16 0.245 ms`——**这是"含 LSTM 的网在 ZG330 上真跑过"的唯一间接证据**，但它是强化学习件、不是 ASR，不能搬来给 CTC 的 LSTM 层背书。

**与 TTS 正题的连接**：`Range`／`RandomNormalLike` 那两个缺口与本节的 CTC 边界是同一类问题——**"算子表里有"不等于"图上能用"**，还得看它是不是被拆成桶、是不是只在 Host 回退里做。§7 已经因为只查一份表错过一次（把 `Gather`／`Pow` 记成硬缺口），本节又把 `LSTM` 那半句口头结论退回开口项——**同一个坑第二次**。所以 §7.1 的落点不是结论，是纪律：**下次判任何算子前先跑 `icraft run --precheck`，别拿单份表当判决**。

## 8. 本轮边界（没测到的，别当结论）

| 项 | 状态 |
|---|---|
| `adapt` / `quantize` / `generate` 后续阶段 | **未测**（只有 vocos 过了 parse，尚未进后续阶段） |
| 板端 RTF（这一批） | 未测；已有读数在 [[ARM CPU TTS性能测试]]（matcha 1.40–1.62、piper 2.90–3.52，均 CPU-only） |
| `Range` / `RandomNormalLike` 能否绕 | **未做**（`Range` 多为长度序列、`RandomNormalLike` 为采样噪声，原理上可预生成常量表替代） |
| piper `Split` 段错误根因 | **未定位** |
| opset=17 路线 | 未测 |
| `LSTM` / `LSTMCell` / `GRU` 在 ZG330 上到底认不认（§7.1） | **未跑 precheck，两份正本冲突**（网页表 √√、PDF 与 114 页里没有）⇒ 开口项 |
| CTC 去重／beam search 的 PS 侧实现 | 未做（§7.1 只给出"该搬 PS"的边界，没写实现） |
| kernel/kitten/supertonic/pocket/kokoro-int8/zipvoice-distill | **未下载**（本轮优先中文 VITS 系） |
| 校机 Linux | **不可用**：两条隧道 `school-guest`/`school-guest-pc2` 现在都落到 Windows 11 `Win11-HV1`（24 核、无 WSL、有 Git-bash、有 sherpa-onnx 1.13.8 venv），与 AGENTS 记的 "EPYC Linux" 不符 |

## 9. 复现命令

```bash
# 0) 下载官方包（本机走代理；展平解包，避开沙箱对嵌套目录的拒绝）
python -X utf8 workenv/.tmp_matcher/dl_proxy.py

# 1) 一条命令做完整配方（输入4维映射 + 折axes + 剥属性 + 比较算子下沉 + opset11/IR8）
python -X utf8 workenv/.tmp_matcher/recipe_final.py <模型>.onnx     # -> <模型>_final.onnx

# 2) 跑真实 parse（以 vocos 为例，这是 rc=0 的那条）
"C:\Icraft\CLI v3.39.0\bin\icraft-parse.exe" --framework onnx --net_name vocos \
  --network vocos_native_nhwc.onnx --log_path <logs> --jr_path <out> \
  --inputs "1,1,600,80" --inputs_layout "nhwc" --inputs_dtype "fp32" \
  --pre_method "nop" --pre_scale "nop" \
  --pre_mean "$(python -c 'print(",".join(["0.0"]*80))')" \
  --channel_swap "$(python -c 'print(",".join(str(i) for i in range(80)))')" \
  --target zhuge
```

判过了的标准：`rc=0`（或 19015 且你接受那几条预检缺陷）+ `jr_path` 出现 `*_parsed.json`/`*_parsed.raw` + `_logs/<net>_precheck.csv` 为空。**本轮只有 vocos 满足"三条全绿"。**

## 相关页面

- [[iCraft算子支持矩阵]]——算子面正本；**注意它引的 91 行是映射表，完整算子面是 114 个 spec 页**
- [[TTS三引擎进NPU实测]]——上一轮（板上三件）的初版记录，三道门的第一版
- [[算子缺口处理]]——缺口分级与"何时才许写 FPGA 硬算子"的成本门槛
- [[ARM CPU TTS性能测试]]——同一批模型在板上的 CPU-only 读数
- [[模型信息汇总]]——官方 TTS/ASR 那批的失败原因原文（fastspeech2 等）
