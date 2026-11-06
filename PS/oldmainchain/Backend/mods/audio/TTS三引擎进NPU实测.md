# TTS三引擎进NPU实测

> **（第一轮记录，2026-10-30）** 本轮只测了板上现成的三件（Matcha 声学 / Vocos 声码器 / Piper），结论是"三道门、无一死于算子不支持"。**第二轮 [[TTS同量级候选进NPU横评]] 已用 10 个候选重测并推翻了本页的一条结论**：本页曾写"四模型共同硬缺口 `Gather`／`Pow`"，那是因为只查了 `workenv/crosswin` 的 91 行**映射表**；完整算子面是 `docs/ops/spec` 的 **114 页**，`Gather`/`Pow`/`Sin`/`Tile`/`Where`/`Conv1d` **全都有**。以第二轮为准。

> **本页回答什么问题**：把板上现成的三个神经 TTS 模型（matcha-icefall-zh-baker 声学模型、vocos-22khz-univ 声码器、Piper zh_CN-huayan）**逐个喂给真实的 iCraft 3.39.0 编译器**，看它们在 parse 阶段死在哪一步、死因是什么类型，并回答"官方 NPU 上 TTS 全军覆没"与我方 Pi/Mat 引擎能不能上板。
>
> **结论先行**：**三个模型没有一个能过 parse**，但**没有一个死在「算子不支持」**——它们分别死在 **opset 版本门 / 输入维度门 / 算子级 ShapeInfer**。这三道门与官方 TTS 失败记录（fastspeech2 的 `gather,tile,where,exp,round,convTranspose`）**不是同一类原因**，因此"官方不行 = 我方也不行"这个推论不成立。
>
> 证据等级：**A** = 本机实测、命令与输出可复现（本页第二～六节全部是 A）；**B** = 官方一手文档但未在本机复跑；**C** = 机制推断。**本页没有 D 级结论**。

## 1. 测试对象与口径

| 模型 | 文件 | 体积 | 图上节点数 | 参数量 | 输入 |
|---|---|---|---|---|---|
| matcha-icefall-zh-baker（声学） | `model-steps-3.onnx` | 75.6 MB | 4802 | ≈18.57 M | 4 个：`x`、`x_length`、`noise_scale`、`length_scale` |
| vocos-22khz-univ（声码器） | `vocos-22khz-univ.onnx` | 53.9 MB | 272 | ≈13.46 M | 1 个：`mels` `[?,80,?]` |
| Piper zh_CN-huayan（VITS 全家桶） | `zh_CN-huayan-medium.onnx` | 63.2 MB | 2755 | ≈15.65 M | 3 个：`input`、`input_lengths`、`scales` |
| （参照）Kokoro v1.0（VITS+HiFiGAN） | `kokoro-v1.0.onnx` | 325.5 MB | 4543 | ≈81.15 M | 3 个：`input_ids`、`speed`、`style` |

板上正本路径：`/mnt/data/models/tts-matcha/matcha-icefall-zh-baker/model-steps-3.onnx`、`/mnt/data/models/tts-matcha/vocos-22khz-univ.onnx`（matcha 那套是 2026-10-29 布下去的，见 [[ARM CPU TTS性能测试]] 与 `repos/HA4FPAI/docs/MEASUREMENTS.md`）；Piper 在 `/root/ttsbench/models/piper/`。**Kokoro 只做算子面参照，没有进 parse 实测**（它的输入是多输入、且体积 325 MB，本轮先测前三个）。

编译器：`C:\Icraft\CLI v3.39.0\bin\icraft-parse.exe`，CLI 版本 `3.39.0.0-431be90(2608211646)`，后端 `zhuge`（= ZG330 = FMQL30TAI = 悟净，我方目标后端）。

复现目录：`S:\work\WCIS\workenv\.tmp_matcher\`（临时产物，按约定不进库）。

## 2. 三道门：三个模型各自死在哪

### 2.1 第一道门：ONNX opset 只认 11 与 17

板上三个模型的原始 opset 是 **14 / 15 / 15**，iCraft 直接拒收：

```
[warning] opset only support 11,17 now
[fatal] ShapeInfer Error : Failed to load model with error:
  ... Unsupported model IR version: 14, max supported IR version: 8
```

两个约束同时存在：**opset ∈ {11, 17}** 且 **IR version ≤ 8**（iCraft 自带 ORT 只到 max IR 8）。sherpa-onnx / piper 生态导出的模型默认是 opset 14~15、IR 8~12，**默认就落在门外**。

处置：本机用 `onnx` 把 opset 改写为 11、IR 降到 8 后，模型即可被加载并进入真正的 ShapeInfer（下面三道门的后续都是在改写后的 `*_op11.onnx` 上测的）。**这一步是纯元数据改写，不动图结构**——它只是把模型送进下一道门，不代表模型已经能编。

### 2.2 第二道门：`inputs` 必须配全每一个输入，且 layout 只认 NHWC / NDHWC / FD

三个模型的输入个数分别是 **4 / 1 / 3**，而 CLI 的 `--inputs` 是**按 `;` 分隔逐输入**配置的。少配一个就 segfault，不是报错：

```
[warning] Icraft-Parser: toml has 1 inputs, but model has 4 inputs!
Segmentation fault
```

`--inputs_layout` 的合法值只有 `NHWC` / `NDHWC` / `FD`（`NCHW` 直接报 `input_layout only support NHWC NDHWC and FD`）。并且**当 layout 是 NHWC 时，输入尺寸必须给满 4 维**：

```
Exception info : Check failed: (origin_input_[index].size() == 4) is false
input[0]'s origin shape must own 4 dim
```

这是本轮最费时间的一处：TTS 模型的自然输入是 2 维（`[?,?]`）或 3 维（`[?,80,?]`），必须先**人为补成 4 维**才能过参数校验。补维本身会改变语义（除非后面在图上补 Reshape），所以**这不是纯参数问题，是图改写工作量**。

### 2.3 第三道门：过去参数校验之后，三个模型分别死在算子级 ShapeInfer

这才是真正的技术结论。三份报错原文：

| 模型 | 死在哪 | 报错原文 | 失败类型 |
|---|---|---|---|
| **Matcha** | `/encoder/Range` → `Unsqueeze` | `Error Node (/encoder/Unsqueeze) has input size 2 not in range [min=1, max=1]` | **算子输入个数超出 iCraft IR 定义**（ONNX 的 `Unsqueeze` axes 是输入张量，iCraft 只接受把它当属性/单输入） |
| **Vocos** | `/backbone/embed/Conv` | `Op (Conv) [ShapeInferenceError] Attribute dilations has incorrect size` | **Conv 属性形态不兼容**（1D 卷积被当成 2D 属性长度校验） |
| **Piper** | `/Gather_1` | `indices element out of data bounds, idx=1 must be within the inclusive range [-1,0]` | **Gather 的常量索引越界**：iCraft 用补维后的 shape 做 ShapeInfer，与模型原本的 2 维语义不一致 |

三条都不是"算子没实现"，而是**算子已实现但形态/属性/维度语义与 iCraft 的 IR 定义不一致**。这个区别决定了处置成本：

- **算子没实现** → 只能走 CPU fallback 或写 FPGA 硬算子（最贵，见 [[算子缺口处理]]）；
- **算子已实现但形态不合** → 可以**改图**（补 Reshape、拆 1D 为 2D、把常量索引改成合法域）在本机/校机纯软件完成，**不需要动 FPGA**。

## 3. 与官方 TTS 失败记录的关系（关键区分）

官方《模型信息汇总》里 TTS/语音那一批的失败原因（一字不改）：

| 模型 | 部署阶段 | 阶段细节 / 备注原文 |
|---|---|---|
| fastspeech2 | 不支持 | `icraft不支持算子：gather,tile,where,exp,round,convTranspose` |
| tacotron2 | 不支持 | `声码器导出失败` |
| hifigan | 不支持 | `icraft不支持算子：conv1DTranspose` |
| CosyVoice1 / CosyVoice2 | 不支持 | `算子不支持` |
| DeepFilterNet3 | 不支持 | `adapt时转置卷积不支持ifm_valid_channel == group && group == ofm_valid_channel分支` |
| GTCRN | 不支持 | `adapt时，stride!=1的conv2dtranspose算子出现数组越界报错` |
| FRCRN | 不支持 | `conv_transpose1d 算子不支持` |
| whisper | 不支持 | `icraft不支持算子：-inf` |
| SenseVoice | 不支持 | `算子不支持, 编译bug, 运行bug, 速度慢, 不支持测精度` |
| qwen2-audio | 不支持 | `不支持导出, 算子不支持` |
| osum | 不支持 | `不支持导出`（源码权重问题，导出需大量修改） |

**两边不是同一类失败**，逐条对照：

| 官方失败类型 | 我方本轮实测到的 | 是否同一类 |
|---|---|---|
| 算子完全不存在（gather/tile/where/exp/round） | 我方的 Gather/Range/Pow/Sin/Where 等同样**不在 iCraft 91 行算子表里**（见 §4） | **是**，这一条是共同的硬缺口 |
| 导出阶段就失败（tacotron2 声码器、osum 权重） | 我方三个模型**都能正常读入 ONNX**，导出不是问题 | 否 |
| `conv1DTranspose` / `conv_transpose1d` 不支持 | Matcha 的 `ConvTranspose` 是 **2D**（表里有 `ConvTranspose2d` 且带条件），Vocos 里没有反卷积 | 否 |
| adapt/quantize 阶段越界（GTCRN、DeepFilterNet3） | 我方**还没走到 adapt/quantize**，parse 就停了 | 未知，未测 |

**所以"官方 TTS 全不行 ⇒ 我方也不行"这个推论不成立**：官方那一批多数死在**算子不存在**与**导出**两条；我方这三个死在**opset 门 + 输入维度门 + 算子形态/属性不合**。后两类在原理上可修。

## 4. 算子面硬缺口（config 级实测，不是推断）

把三个 ONNX 图的算子逐个与 iCraft 3.39.0 的 91 行算子表（`workenv/crosswin/icraft_op_matrix_6col.tsv`，正本在 [[iCraft算子支持矩阵]]）比对，**四个模型共同的硬缺口只有两个**：

| 算子 | Matcha | Vocos | Piper | Kokoro | iCraft 表 |
|---|---|---|---|---|---|
| `Gather` | 152 | 1 | 168 | 169 | **无** |
| `Pow` | 71 | 10 | 39 | 62 | **无** |

其余缺口按模型分散（Matcha：`Sin/Neg/Where/Reciprocal/Range/Tile/Ceil/CumSum`；Piper：`ScatterND/GatherElements/GatherND/NonZero/CumSum`；Kokoro：`TopK/If/Loop/Atan/Floor`）。

**这两条与官方 fastspeech2 的报错原文（`gather,tile,where,exp,round`）直接重合** —— 这不是巧合，而是 iCraft 3.39.0 的算子表**确实没有 gather / pow / tile / where / exp / round 这类"非矩阵乘加密集型"算子**。91 行表里能查到的只有 conv/pool/norm/激活/矩阵乘/逐元素加减乘除/slice/concat/reshape 这些。

> **注意口径**：iCraft 的 `exp` 在表里也没有，但 `Softmax`（内部含 exp）和 `Softplus` 是 √。所以"模型里出现 `Exp`"不等于"一定编不过"——要看它能不能被折叠进 Softmax/Softplus。本轮三个模型的 `Exp` 出现次数分别是 13 / 1 / 6，**不足以判定**，属于未测。

## 5. 回答"Piper / Matcha 进 NPU 能不能行"

分四档回答，不合并：

| 档 | 判断 | 依据 |
|---|---|---|
| **① 直接编译上板** | **不行** | 三个模型都没过 parse（§2.3 三条实测报错），比 §3 官方那批更早死 |
| **② 改图后编译** | **有可能，但要动图** | 三道门里有两道（opset/IR、输入 4 维）是**纯元数据+补维**，可自动做；第三道（ShapeInfer 形态）需要**逐个算子改图**：Matcha 的 `Unsqueeze` 要退回属性形式或换等价写法；Vocos 的 1D Conv 要包成 2D；Piper 的 `Gather` 常量索引要落进合法域。工作量按"图改写"估，不是按"写硬算子"估 |
| **③ 硬缺口补齐** | **要额外工作** | 共同缺 `Gather` / `Pow` 两个算子。这两个在 TTS 里承担的是**位置编码与采样温度**这类非主流计算，改图（用查表、用常量折叠、用等价的多项式近似）比写 FPGA 硬算子便宜得多，符合 [[算子缺口处理]] §1 的成本顺序 |
| **④ 量化后精度** | **未测，不承诺** | parse 都没过，谈不上 quantize。但已有旁证不乐观：官方 SenceVoiceSmall / conformer 两个 ASR **入库后仍标"精度低（by int8 量化精度差）"**，bert_cls 在 ZG int8 从 94.76% 掉到 41.84%。**量化是独立的一道门，不能因为算子修好了就假设精确保得住** |

**结论一句话**：**不是"官方不行所以我方也不行"，而是"我方现在卡在更早的一道门（opset/维度/图形态）；这道门可以修，修完还要过 Gather/Pow 和量化两道门"**。**不要因为官方 TTS 全灭就放弃我方路线，也不要因为三道门可修就承诺能上板**。

## 6. 本轮实测的边界（哪些没测）

| 项 | 状态 | 说明 |
|---|---|---|
| `adapt` / `quantize` / `generate` 阶段 | **未测** | parse 未过，后续阶段进不去 |
| 板端 RTF | 未测本轮 | 已有读数在 [[ARM CPU TTS性能测试]]：matcha t3 RTF 1.40–1.62、piper 2.90–3.52（**都是 CPU-only**） |
| Kokoro parse | 未测 | 只做了算子面比对 |
| opset=17 路线 | 未测 | 本轮只走 opset=11；17 是另一条合法路径，未验证 |
| 预检 CSV（`xx_precheck.csv`） | 未产出 | 三次失败都停在参数校验或 ShapeInfer，没走到预检落盘。**预检 CSV 是比本页更强的证据，下一轮必须拿到** |

## 7. 复现命令（可照抄）

```bash
# 0) 取模型（板 -> 本机）
scp root@192.168.1.113:/mnt/data/models/tts-matcha/matcha-icefall-zh-baker/model-steps-3.onnx .
scp root@192.168.1.113:/mnt/data/models/tts-matcha/vocos-22khz-univ.onnx .
scp root@192.168.1.113:/root/ttsbench/models/piper/zh_CN-huayan-medium.onnx .

# 1) 过第一道门：opset 11 + IR 8（纯元数据改写）
python -X utf8 -c "
import onnx
for f in ['model-steps-3.onnx','vocos-22khz-univ.onnx','zh_CN-huayan-medium.onnx']:
    m=onnx.load(f); del m.opset_import[:]
    m.opset_import.append(onnx.helper.make_opsetid('',11)); m.ir_version=8
    onnx.save(m,f.replace('.onnx','_op11.onnx'))"

# 2) 过第二道门 + 撞第三道门：逐模型 parse
"C:\Icraft\CLI v3.39.0\bin\icraft-parse.exe" --framework onnx \
  --net_name matcha --network "S:/work/WCIS/workenv/.tmp_matcher/matcha-model-steps-3_op11.onnx" \
  --log_path "S:/work/WCIS/workenv/.tmp_matcher/logs" --jr_path "S:/work/WCIS/workenv/.tmp_matcher/out/matcha" \
  --inputs "1,600,1,1;1,1,1,1;1,1,1,1;1,1,1,1" \
  --pre_method "nop;nop;nop;nop" --pre_scale "nop;nop;nop;nop" --pre_mean "0;0;0;0" \
  --channel_swap "nop;nop;nop;nop" --inputs_layout "nhwc;nhwc;nhwc;nhwc" \
  --inputs_dtype "fp32;fp32;fp32;fp32" --target zhuge
```

判过了的标准：`rc=0` + `jr_path` 下出现 `*_parsed.json` / `*_parsed.raw` + `.icraft/logs/<net_name>/` 下出现 `*_precheck.csv`。**本页三个模型一条都不满足。**

## 8. 下一步（按成本顺序，不跳级）

1. **拿预检 CSV**：把 `--inputs` 与图真实维度对齐（或在图前插 Reshape 把 2/3 维补成 4 维），目标是让 parse **跑完**并落盘 `precheck.csv`。那份 CSV 会逐条列出"不支持算子 + 原因 + 哪个组件不支持"，比本页的手工比对强一个档。
2. **只改图、不写硬算子**：按 §5 ② 修 `Unsqueeze` / 1D Conv / Gather 常量索引三处，验证能否推翻 §2.3 的三条报错。
3. **补 Gather/Pow**：先评估能否用常量折叠/查表去掉，去不掉再谈 [[算子缺口处理]] 路径②（CPU fallback）。
4. **量化门**：只有前三条都过了才进入，且必须带 §5 ④ 的悲观预期。

## 相关页面

- [[iCraft算子支持矩阵]]——91 行算子表正本与本轮比对的分母
- [[算子缺口处理]]——缺口分级与"什么时候才许写 FPGA 硬算子"的成本门槛
- [[ARM CPU TTS性能测试]]——同一批模型在板上的 CPU-only 读数（matcha RTF 1.40–1.62、piper 2.90–3.52）
- [[模型信息汇总]]——官方 TTS/ASR 那一批的原始判定与失败原因原文
- [[00_模型清单与性能]]——对外可下载的 53 个模型工程清单（内含 EcapaTDNN / CAMpplus / bert_cls 的西文读数）
- [[1-NPU模型部署]]——A3「转换成功?」判定处即本页的上一道关卡
