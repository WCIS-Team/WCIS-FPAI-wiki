# LLM上板要求与候选模型对照

> **本页回答什么问题**：一颗 decoder-only LLM 要变成悟净（ZG330）上能加载的 `_ZG` 件，中间有哪**四道门**、每道门拿什么判"过了"；以及换成候选 **ERNIE-4.5-0.3B-PT** 时哪些结论能直接复用、哪些必须重跑。末尾第八节是本页与 [[NPU模型上板出指标SOP]]／[[算子缺口处理]] 的**双向 gap 清单**。
> **判据等级**：A＝本页从编译产物／官方件／板上读数直取（读数的脚本都写出来了，可复跑）；B＝厂商文档原文照录；C＝按已测比例外推，**未实测**。
> **分工（一个事实只写一处）**：编译命令与逐阶段读数＝`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\pipeline.md` 与 [[Qwen3按Qwen3配方迁移]]；器件级算子表正本＝[[iCraft算子支持矩阵]] 与 [[icraft.v3.39.0_支持算子表]]；检测类全流程＝[[NPU模型上板出指标SOP]]；缺口分级与四条路径＝[[算子缺口处理]]。本页不复制它们的内容，只做"LLM 这一类模型的合同"＋候选对照＋gap。

## 一、TL;DR

1. **LLM 在 ZG330 上"过不过"不由算子支持表决定**。Qwen3-0.6B 那颗件 2,238 个节点，落 NPU 的 2,177 个语义只有 **15 种**，逐一对官方 117 行表全是 `√`；留在 host 的 61 个里，除 `Gather` 与 Input／Output 两个端点外全是 LLM 路径专用算子（`RopeDynamic`／`CausalMask`／`SliceDynamic`），**这三个名字在官方算子文档里根本不存在**（`C:\Icraft\CLI v3.39.0\docs\ops\` 全树命中 **0**，A）。
2. ⇒ **"`@hostt` 多"≠"缺口大"**。[[NPU模型上板出指标SOP]] 阶段 3 那句"算子缺口＝0"对检测类成立，对 LLM 会把 61 个 host 节点误判成 59 个缺口。判 LLM 要用第七节那六行读数。
3. 真正卡住我们的三道墙全在**算子之前**：ONNX 前端（ir／opset／域）、导出后端（`-e cpu` 退化）、图合同（`token_dynamic_fm` 宽度）。三者**退出码都查不出来**。
4. **ERNIE-4.5-0.3B-PT 对照**：算子面无新面孔（是那 15 种的子集），红利＝KV 从 56.0 MiB 降到 **9.0 MiB@512 窗口**（张量 112→72＝进/出各 56→36；容量 56/9＝**1/6.22**，§6.2）＋省掉 QK-Norm 换域整步。原先写在第一条的"坑"（genai 给 Ernie4_5 打 `interleaved=1` 与 HF 冲突）**10-30 已判为误读并作废**：ERNIE 的 `rotate_half` 是相邻配对形＝正是 interleaved，且导出件对 HF 基准 PREFILL cos＝**0.999999**、top5 逐字相同（A，§6.5）。**10-31 这两条也关了**（A）：符号轴改回定长 128、opset 22→17，五段编译全通（`E41-decoder_ZG.json` 1,637,490 B＋`.raw` 1,054,488,148 B，`params_md5` 与 `.raw` 的 md5 逐字节相等），算子归属 **1332 上 `@zhuget(330)`／41 落 `@hostt`**；但上面那句"降到 9.0 MiB"只到导出面——平铺债把每张抬成 Qwen3 的几何，**编译面 36.0 MiB、每步喂入 40.0 MiB＝Qwen3 的 1/1.4**（§6.2）。整条链的读数与复跑＝`repos\lang\llm\ERNIE-4.5-0.3B-PT4icraft430tai\pipeline.md`，型号与状态＝[[ERNIE-4.5-0.3B-PT]]；**门 4（板）零读数、未执行**。
5. **"10-19 交付线重跑了一遍"这句话要打折**（10-30 结案，A）：那条线喂进编译的三份 ONNX 与 10-12 探索线**逐字节相同**，所以它编出来的 `Q3I-decoder_ZG.raw` 与板上那颗 `Q3V1-decoder_ZG.raw` 是同一颗（md5 全等，两颗 `_ZG.json` 只差网络名）；它自己新导出的 `q3i_fp16_cuda` **从没进过 icraft**，而它与现役图的差别恰好只有"KV 宽度符号化"这一件事（112 条张量、1,232 B）。数值无害（权重逐刀相等），但**"整条链可复现"目前只有编译段的证据**。

## 二、四道门（顺序不能倒：前一道不过，后面一道读数都拿不到）

| 门 | 卡什么 | 判"过了"的口径 | Qwen3-0.6B 我方件实况 | 换 ERNIE 要重跑什么 |
|---|---|---|---|---|
| **1 前端摄取** | ONNX 的 ir／opset／算子域／dtype | parse 段日志无 `[F]`／`捕获到错误码`，五段产物齐全（退出码不可作数） | ir10／opset21 → 改到 ir8／opset17 ＋ QK-Norm 换 `com.microsoft` 域才过（`pipeline.md:61`／`:65`，A） | 10-30 件已导出（§6.5）：ir10／opset **22** ⇒ 改元数据那步照跑且**目标档要按 22 重算**；**换域那步确认不需要**（图里 0 颗 q_norm／k_norm，A）；**新增未知＝KV 第 4 轴是符号轴** |
| **2 图合同** | decode-only、输入签名、KV 定长 | 输入条数与形状逐条对上，且喂进去的**字节宽度**对 | 58 入／57 出；KV `@fp(16)[1,8,512,128]`×56；`token_dynamic_fm @fp(32)[1,3]`＝12 B（A） | 层数 28→18、KV head 8→2 ⇒ **输入条数与张量形状全变**（10-30 直读 38 入／37 出，A），驱动与 yaml 按第六节重算 |
| **3 算子归属** | 哪些节点在 `@zhuget(330)`、哪些回 host | 第五节那张表＋第七节六行读数 | 2,177 `@zhuget(330)`／61 `@hostt`，NPU 侧 15 种语义全 `√`（A） | 导出段直读只剩 **13 种**语义（少 `Reshape`／`Split` 两整类，A）；但 **(16Q／2KV／head_dim 128) 这个组合我方从未编过** ⇒ 门 3 仍是预判 |
| **4 板端资源** | 位流里有没有 NPU、CMA 池、盘容量 | 起跑前三查，**门禁看 `CmaFree` 不看 `MemAvailable`** | 件 `.raw` 1,603,399,624 B；10-14 预检 `CmaFree` 最低 **80 kB**、`MemAvailable` 最低 **5,020 kB**（`pipeline.md:357`／台账 `#213`，A） | `.raw` 外推 ≈970 MB（C，算式 §6.3）；盘 `/` 空闲 6.4 G（`pipeline.md:363`，A）够放 |

## 三、门 1 明细：ONNX 前端的硬门限

- **B**：`docs/ops/framework.html` 原文——opset 支持 **11／14／17**，ir version **8**，ONNX version 最高 **1.13.1**。生成侧现在默认给 ir10／opset 21～22，所以 `meta_variant.py`（ir 10→8、`ai.onnx` opset→17）是**必经**的一步，不是可选优化。
- **A**：`-p fp16 -e cpu` 出来的件退化成 **2,125 节点的 `MultiHeadAttention`＋显式 `RotaryEmbedding`＋多一个 `position_ids` 输入，icraft 过不去**（`pipeline.md:51`）。只有 `-e cuda` 那条路给的是 `GroupQueryAttention` 融合算子。⇒ 这条**不是性能选择，是"能不能进前端"的选择**。
- **A**：图内 fp16 `Transpose` 报 `Unknown dtype 10`（dtype 10＝ONNX 的 FLOAT16，parse 不认）——这是 10-12 那次唯一撞到的结构性卡点。
- **C（未决）**：opset 21 只去 `Transpose` 能否过 parse，仍挂着（`pipeline.md:486` 任务 #8）。**这条直接决定换候选时"改元数据够不够"**，现在不能当已知。
- **A**：opset 会随工具版本自己往上漂——10-12 探索线的导出是 247,199 B／ir10／opset **21**，10-19 交付线同一颗模型重导是 248,431 B／ir10／opset **22**（`compile/fmodel/q3i_fp16_cuda/` 与 `export/q3i_fp16_cuda/` 直读）。所以每轮导出都要重看这两个字段，不能照抄上一轮。

## 四、门 2 明细：decode-only 图合同（`repos/lang/llm/Qwen3-0.6B/board/Q3I-decoder_ZG.json` 直读，A）

| 输入 | 类型 | 语义 | 踩过的坑 |
|---|---|---|---|
| v_id 0 `input_ids` | `@fp(32)[1,1]` | 单 token ⇒ **这张图是 decode-only，没有 prefill** | — |
| v_id 1 `token_dynamic_fm` | `@fp(32)[1,3]`＝**12 B** | RoPE 位置＝KV 写槽号＝mask 有效长度；**第 3 个元素图上没有消费者** | 厂商驱动只喂 2 个（8 B）⇒ 板上第一次真直接抛 `hardop.cpp:46 … host_chunk byte_size:8 is diff from plddr_chunk byte_size:12`（`pipeline.md:18`，A）。**本机 Host 后端不查输入宽度，这条只有上板才暴露** |
| v_id 2～57 past KV ×**56** | `@fp(16)[1,8,512,128]` | 28 层 ×（K,V），**定长 512** | 窗口是编译期烘死的，改长度＝重编 |
| Params `cos_cache`／`sin_cache` | `@fp(16)[512,128]` | RoPE 查表，行数＝窗口 | — |

**host 侧 61 个节点的构成**（A）：`SliceDynamic` 56（每层 KV 写槽切片）、`Gather` 1（词表查表）、`RopeDynamic` 1、`CausalMask` 1（`fill_value = "-inf"`）、`Input` 1、`Output` 1。

- `Gather` 在官方表里标 **`× Host 回退`**（ZG330／ZG30S／BY 三档全 `×`）⇒ **embedding 落 host 是合同设计，不是缺口**。[[算子缺口处理]] §10.1 行 268 说"`embedding` 是 LLM 头号风险"——风险成立，但**落点早就定在 host**，不需要路径①②③④ 任何一级。
- `-inf` 同理：§10.1 行 266 把它列为悟净上唯一被实测证实的语音类硬缺口（whisper 行 167，平台 `30`）。在 LLM 路径里它由 host 的 `CausalMask` 承担 ⇒ **不是缺口，代价是 mask 构造不占 NPU**。

## 五、门 3 明细：NPU 侧 15 种语义 × 官方表（D2 三态标注，A）

读法：`HardOp.name` 才是语义（`_type_key` 恒为 `icraft::xir::HardOp`，官方表里 `HardOp` 那行标 `—`、是容器）。下表计数＝`Q3I-decoder_ZG.json` 直取；状态列＝对 [[icraft.v3.39.0_支持算子表]] 的 ZG330／ZG30S／BY 三格。

| 件内语义 | 节点数 | 官方表行名 | ZG330 | ZG30S | BY | 备注 |
|---|---|---|---|---|---|---|
| Reshape | 765 | Reshape | √ | √ | √ | 布局搬运产物，非原图算子 |
| Transpose | 280 | Transpose | √ | √ | √ | 同上 |
| Matmul | 197 | Matmul | √ | √ | √ | 算式见下 |
| Multiply | 168 | Multiply | √ | √ | √ | BY 侧限"输入须满足广播规则" |
| Copy | 142 | Copy | √ | √ | √ | 恒等／contiguous |
| Add | 140 | Add | √ | √ | √ | Sub 经 Add 实现 |
| Slice | 115 | Slice | √ | √ | √ | — |
| SimplifiedLayerNorm | 113 | **LayerNorm** | √ | √ | √ | C：名字映射是我做的——表里没有 `SimplifiedLayerNorm` 行，按 ONNX 名 `LayerNormalization（及融合）` 对齐 |
| Cast | 58 | Cast | √**条件** | **×** | × | ZG330＝动态维度或非{BF16,FP16,TF32,FP32,SInt8}→Host。本件 58 个全落 `@zhuget` ⇒ 都站在条件成立侧；**ZG30S 这颗不支持**，选位流时看这条 |
| Concat | 57 | Concat | √ | √ | √ | — |
| Neg | 56 | Neg | √ | √ | √ | — |
| Split | 29 | Split | √ | √ | √ | — |
| Softmax | 28 | Softmax | √ | √ | √ | BY 侧标 FPGA 加速路径 |
| SiLU | 28 | SiLU | √ | √ | √ | 官方行名 `SiLU`，ONNX 侧是 `Sigmoid+Mul` 融合 |
| Expand | 1 | Expand | √ | √ | √ | — |

**件内计数与 config 层数互相咬合的三条算式**（A，也是自检：任何一条不吻合就说明图被裁过或重复）：

- `Softmax` 28 ＝ `SiLU` 28 ＝ `num_hidden_layers` 28；
- `Matmul` 197 ＝ 28×7 ＋ 1（每层 q／k／v／o＋gate／up／down，＋1 个 `lm_head`）；
- `SimplifiedLayerNorm` 113 ＝ 28×4 ＋ 1（每层 2 个残差 norm ＋ Qwen3 特有的 q_norm／k_norm，＋末层 1 个）。另有 `Neg` 56 ＝ 28×2，**条数与 KV 张量数相同但成因未核**，别写成"KV 取负"。

**这张表的分母有洞**（A）：`RopeDynamic`／`CausalMask`／`SliceDynamic` 在 `docs/ops/`（framework.html ＋ spec 114 页）**命中 0**，它们只在 `docs/xir/` 作为 C++ 节点类出现（`docs/xir/index.html:236`、`:237`、`:492`、`:493`），`llm_mode` 这个开关也只在 `docs/parse/index.html:430-432`（原文：bool，"表示网络是否为LLM模型，默认False，在解析LLM模型时需要配置为True"）。⇒ **官方 117 行表只能覆盖 NPU 侧那 15 种语义，host 侧的 LLM 专用算子不在它的分母里**，照表比对必然得出"缺口 59 个"。

## 六、候选对照：三颗，config 级

### 6.1 逐键

| 键 | 厂商 Qwen2-0.5B（`genai_config.json`） | Qwen3-0.6B（我方件 `board/config.json`） | ERNIE-4.5-0.3B-PT（ModelScope `master/config.json`） |
|---|---|---|---|
| architectures | qwen2（type 字段） | `Qwen3ForCausalLM` | `Ernie4_5ForCausalLM` |
| hidden_size | 896 | 1024 | **1024** |
| intermediate_size | 件里没有这个键（未取） | 3072 | **3072** |
| head_dim | head_size **64** | 128 | **128** |
| num_attention_heads | 14 | 16 | **16** |
| num_key_value_heads | 2 | 8 | **2** |
| num_hidden_layers | 24 | 28 | **18** |
| vocab_size | 151936 | 151936 | **103424** |
| rope_theta | 未取 | 1,000,000 | **500,000** |
| 最大位置 | context_length 32768 | 40960 | **131072** |
| tie_word_embeddings | 未取 | true | true |
| torch_dtype | 未取 | bfloat16 | bfloat16 |
| rms_norm_eps | 未取 | 1e-06 | 1e-05 |
| **QK-Norm** | 无 | **有**（q_norm／k_norm，宽＝head_dim） | **无**（A：HF `modeling_ernie4_5.py` 里 `q_norm`／`k_norm` 命中 0） |

三行都 A（各自件直读）。**Qwen3 与 ERNIE 在 hidden／intermediate／head_dim／Q head 数上完全相同**，差别集中在层数、KV head 数、词表、rope_theta 与上下文标称长度——这决定了下面两笔账。

### 6.2 KV 账（每层 2 张，每张 ＝ kv_head × 窗口 × head_dim × 2 B）

- Qwen3-0.6B：28×2 ＝ **56 张**，每张 8×512×128×2 ＝ 1,048,576 B ⇒ 58,720,256 B ＝ **56.0 MiB**（件内 56 个 `SliceDynamic` 对上，A）
- ERNIE-0.3B：18×2 ＝ **36 张**，每张 2×512×128×2 ＝ 262,144 B ⇒ 9,437,184 B ＝ **9.0 MiB** ＝ Qwen3 的 **1/6.22**——**这笔红利只到导出面**（10-31 更正）：编译时 parser 只认 Qwen3 那套几何，K／V head 被平铺成 8 ⇒ 每张 1,048,576 B、36 张＝37,748,736 B＝**36.0 MiB**，再加 4 条必须喂的死声明，**每步喂入 41,943,056 B ＝ 4＋12＋40×1,048,576 ＝ 40.0 MiB**（A：`E41-decoder_adapted.json` ＋ 三个步目录逐目录实测）＝ Qwen3 那 56.0 MiB 的 **1/1.4**（58,720,256÷41,943,056＝1.3998）⇒ **门 4 的 CMA／带宽预算按 8 头算，不按 2 头算**
- 厂商 Qwen2-0.5B：24×2 ＝ 48 张，每张 2×512×64×2 ＝ 131,072 B ⇒ 6,291,456 B ＝ **6.0 MiB**（C：shape 按 genai 约定推，件内没逐个数过）

### 6.3 参数量与 `.raw`（算式都给出来，因为"0.3B"是档位名不是数）

- ERNIE 参数量＝**360,748,032 ≈ 0.36 B（10-31 升到 A：`model.safetensors` 头部 164 张量逐张求和，全 BF16）**。同一算式（原先把 embedding 写成 103,424×1,024＝105,905,664，少 512 个元素，正确值 105,906,176）＝embedding 105,906,176（tie ⇒ 只算一份）＋每层[q 1,024×2,048＝2,097,152 ＋ k 1,024×256＝262,144 ＋ v 256×1,024＝262,144 ＋ o 2,048×1,024＝2,097,152 ＋ MLP 3×1,024×3,072＝9,437,184 ＋ 2 个 norm 2×1,024＝2,048]＝14,157,824，×18 ＝ 254,840,832 ＋ 末 norm 1,024 ＝ 360,748,032，与件直读**逐元素相等**。
- 同一算式给 Qwen3：155,582,464 ＋ 28×(2,097,152＋1,048,576＋1,048,576＋2,097,152＋9,437,184＋2,048＋256) ＋ 1,024 ＝ **596,049,920 ≈ 0.6 B** ⇒ 与官方"0.6B"对得上，说明这套算式可用。
- `.raw` 外推**已作废**（10-31）：ERNIE 编译件实测到案＝`E41-decoder_ZG.raw` **1,054,488,148 B ≈ 1,005.6 MiB**（`.json` 1,637,490 B，`params_md5` 与 `.raw` 的 md5 逐字节相等＝`6c0fe5afb0d744a9dfdd20c5959b1007`，A）。按新参数算式重算倍数：1,054,488,148 ÷（360,748,032×2＝721,496,064）＝ **1.462**，多出的 **332,992,084 B 成分未核**（别写成"权重就是这些"；原那句 1.345 是拿 Qwen3 自己的算式比的，两颗不同件）。板 `/` 空闲 6.4 G（A）装得下。

### 6.4 ERNIE 线的四个坑与两个红利

**坑**

1. **~~`interleaved` 打架~~（10-30 判为我误读，公开更正，作废）**：这条原来写"genai 打 `interleaved=1`、HF 是 `rotate_half` ⇒ 非 interleaved，两边必有一边错"。**错在后半步**：`rotate_half` 这个名字在两家 HF 实现里指的不是同一件事——Qwen3 那份是 `x1=x[:, :d//2] / x2=x[:, d//2:]`（半轴切分＝non-interleaved），ERNIE 那份（`models/ernie4_5/modeling_ernie4_5.py:107`）是 `x1=x[..., 0::2] / x2=x[..., 1::2]` ＋ `stack((-x2, x1)).flatten(-2)`，**把 (0,1)(2,3) 相邻配成一对再转＝就是 interleaved**，源码里还留着 `# Interleave them instead of usual shape` 的注释。genai `models/builders/ernie.py:14` 那句无条件赋值因此与 HF **一致**，不是冲突。数值面同时否证了原断言：PREFILL cos＝0.999999／relmax＝0.00114／top5 与 HF 逐字相同（§6.5，A）——若 rope 约定真错了一位，对不可能是这个数。**原结论指向的方法仍有效**：这类错只在数值层、结构门禁抓不到，所以候选模型必须先跑 HF 基准，10-30 就是靠它把坑本身和坑的判定一起关掉的。同文件 `:19-20` 的 `compression_ratio` 分支对这颗不触发（官方 config 里没有这个键，A）。
2. **128K 是标称、不是可用**：`max_position_embeddings` 131,072，genai 因此把 **整张 128K 的 rope 表烘进件里**（10-30 直读 `cos_cache`／`sin_cache` 各 `fp16 (131072, 64)`＝16,777,216 B，两颗合计 33,554,432 B ≈ **32 MiB＝`.data` 的 4.4 %**，A）；而窗口本身是编译期烘进图的（`token_dynamic_fm`／KV 定长），`rope_theta` 5e5 同样烘死 ⇒ 想要长窗口＝重编，不是改参数。**要降本只能在编译段裁表**，导出段没有这个旋钮。
3. **~~PT＝pretrain 底座~~（10-30 判为我误读，公开更正）**：这条原来写"这颗是预训练底座、没有 instruct 档、指令跟随不保证"。**`-PT` 在这个家族里根本不是 pretrain 的缩写**——官方卡片原话：`"-Paddle" models use PaddlePaddle weights, while "-PT" models use Transformer-style PyTorch weights`（PT＝PyTorch 权重格式，与 Paddle 格式相对）。同一张卡片的 Model Overview 两行并排：`ERNIE-4.5-0.3B is a text dense **Post-trained** model` ＋ `Training Stage | **Posttraining**`；而底座那颗是**另一个 id** `ERNIE-4.5-0.3B-Base-PT`（`is a text dense Base model`／`Training Stage | Pretraining`）。⇒ **我方导出的这颗本来就是对话档**，"换 Instruct 重导"这个动作没有对象：`baidu` org 全表列举（37 个模型、30 个含 ERNIE）里 0.3B 只有 `Base-PT`／`Base-Paddle`／`PT`／`Paddle` 四档，**没有任何 Instruct／Chat 档**；卡片 §3 说 LLM 的 SFT＋DPO／UPO 后训练已经做进这批件里。要换成"更差"的倒是有——`Base-PT` 才是裸底座。
4. **~~(16 Q／2 KV／head_dim 128) 这个组合我方从未编过~~→ 10-31 结案：编过了**（A）⇒ 门 3 对 ERNIE 不再是预判：1373 算子＝**1332 颗 `@zhuget(330)`＋41 颗 `@hostt`**（`SliceDynamic`×36 ＋ `Input`／`Gather`／`RopeDynamic`／`CausalMask`／`Output` 各 1；1332＋41＝1373，Qwen3 现役那颗同形）。**但过门的不是原生形态**：parser 只认 Qwen3 那套几何，K／V head 被平铺成 8，所以实际编过的是 16/**8**/128，**这颗自己的 2 头形态一次都没编过**（[[算子缺口处理]] §2 的纪律照守："理论可部署"不许写成"已部署"）。

**红利**

1. **没有 QK-Norm** ⇒ `pipeline.md:61`／`:65` 那次"把 `LayerNormalization` 移进 `com.microsoft` 域"的改写整步不需要；`SimplifiedLayerNorm` 按算式从 113 降到 **18×2＋1＝37**（10-30 导出件直读＝`SimplifiedLayerNormalization` 1 ＋ `SkipSimplifiedLayerNormalization` 36＝**37**，A，算式与实物对上）。
2. **KV 降到 1/6.22**（§6.2）＋层数 28→18 ⇒ 单 token 的 KV 搬运与 `SliceDynamic` 条数同步降到 36。

### 6.5 10-30 第一步实测：校机导出 ＋ 对 HF 基准（A，全部读数与复跑命令＝`repos\lang\llm\ERNIE-4.5-0.3B-PT4icraft430tai\pipeline.md`）

第一步按她的口径只做两件事——"校机导出"＋"对 HF 基准"，**没进 icraft、没上板**。

| 项 | 读数 |
|---|---|
| 权重下载 | ModelScope 官方工具，12 件合计 734,582,404 B＝**700.55 MiB**；`model.safetensors` 721,514,672 B（A：校机 `D:\yzd\WCIS\MOD\ernie\ERNIE-4.5-0.3B-PT` 直读）。耗时 118.7 s＝本轮终端读数、**日志未落盘**，别当可复核数（B） |
| 导出 | `python -m onnxruntime_genai.models.builder -i …ERNIE-4.5-0.3B-PT -o …ernie_fp16_cuda -p fp16 -e cuda`，**EXIT=0**、约 20 s；**不需要** Qwen3 那句 `--extra_options fuse_qk_norm_gqa=false`（日志 `Extra options: {}` 且照样出融合 `GroupQueryAttention`，A） |
| 图 | ir10／opset (ai.onnx **22**, com.microsoft 1)／producer `onnxruntime-genai/0.17.1+83de55a`；**210 节点／130 初始化器／38 入／37 出**（Qwen3 现役是 520／256／58／57）；`GroupQueryAttention` 18 颗、`kv_num_heads=2`、`num_heads=16`、`scale=0.0883883`（＝1/√128）、`do_rotary=1`、**`rotary_interleaved=1`** |
| 算子种类 | **13 种**（Qwen3 15 种），比 Qwen3 少 `Reshape`（112 颗）与 `Split`（28 颗）两整类；`MatMul` 91＝18×5＋1（融合 qkv ⇒ 每层 5 颗，非 7 颗） |
| `model.onnx` | 103,511 B／`6f07fa164050bb4785584b90d0bb458e` |
| `model.onnx.data` | 755,105,792 B／`788afdcb6bfd2502ceda667bcf0d1aac`；**10-31 按张量级对账更正**：权重字节＝360,748,032×2＝**721,496,064**（`model.safetensors` 的文件字节 721,514,672 里有 **18,608 B** 是它自己的头部与对齐，别当权重用）＋两颗 rope 表 33,554,432 ＝ 755,050,496 ⇒ **实物多 55,296 B**（＝27,648 个 fp16，成分未核）。旧版那两条"36,688 B 未核／算式少 19,632 B"是同一个错的两面（36,688＋18,608＝55,296；19,632＝18,608＋1,024，那 1,024 B＝少写的 512 个元素） |
| HF 基准 PREFILL | 7 token 提示，fp32 HF vs fp16 ONNX：`maxabs=0.02105`／`relmax=0.00114`／`cos=0.999999`；top5 `[23, 44284, 2, 93919, 269]` **两侧逐字相同**，`MATCH_TOP1 True` |
| HF 基准 DECODE | 1 token 步进（喂上一步 `present.*`）：`maxabs=1.56689`／`relmax=0.12047`／`cos=0.991060`，top1 同、top5 从第 3 位起顺序不同 ⇒ 与 [[qwen3-0.6b]] 那一步同量级，**是 fp16 累加差不是图错** |

⇒ **门 1 的"换域那步不需要"、门 2 的"输入条数与形状全变（38／37）"从预判升成直读**；门 3 在 10-30 晚～10-31 也走过了（读数指回 pipeline §7，状态见 [[ERNIE-4.5-0.3B-PT]]）。**门 4 此后已通**（11-01 板上 `precheck=True`、逐 token 与 PC 对上、63 步 oracle），读数与判定见 §6.6。

**新冒出的一条**：这颗件的 KV 第 4 轴是**符号轴** `kv_cache_dim`（36 进＋36 出全部如此），与 Qwen3 **现役那颗的烘死 `dim_value: 128`** 不同、与 10-19 那次没进过编译的重导同形（opset 22 带的变化，见 [[Qwen3按Qwen3配方迁移]] 编译段）。所以"符号轴 icraft 吃不吃"这条老 open 问题**在 ERNIE 线上是必经的**，绕不过去；照 Qwen3 现役的做法是把轴改回定长再编（改法未对 ERNIE 验证）。

### 6.6 门 4 的实测横表：三颗 LLM 的 PS 内存与 CMA（数据正本＝[[板端我方代码与产物台账]] §21.1）

**本页只写判定与口径，数字一律引台账，不复制**。三颗同板、同 `CmaTotal`＝262,144 kB、空载 `CmaFree` 约 130 MB：

| 模型 | 走到哪一步 | 危险度 | 判定 |
| --- | --- | --- | --- |
| 厂商 Qwen2-0.5B | 真推理 20 token | 中 | CMA 谷底 8,860 kB，PS 峰值 673 MB ⇒ **1.3 GB 权重靠惰性加载，没整颗驻 RAM** |
| 我方 ERNIE-4.5-0.35B | 探针到 `apply`（另有真推理读数） | 中 | CMA 谷底 **1,532 kB** 比 Qwen2 低一个量级，但 PS 只到 505 MB ⇒ **CMA 更紧、PS 更松** |
| 我方 Qwen3-0.6B | **只到 `apply`，零生成** | **高** | `CmaFree` **80 kB** ＋ `MemAvailable` **5,020 kB** ⇒ **两边同时贴底，只差没死** |

三条口径（写进本页是因为它们决定"能不能引用这个数"）：

1. **门禁看 `CmaFree` 不看 `MemAvailable`**：三颗的 CMA 都是"借还"（跑完回弹到 128–129 MB），所以起跑前 ≥126 MiB 就够，但**同窗不能有第二条吃 CMA 的链**（直播／VPU 也吃）。
2. **谷底是采样点，不是真值**：2 s（ERNIE）／5 s（Qwen3）间隔抓到的最低点，真实谷底可能更低 ⇒ 只能当**上界**引用，不能写成"运行时固有开销"。
3. **Qwen3 那行的"危险度＝高"不等于它会挂**：s3 那一档整机没死，只是把余量吃光；**零生成**意味着真解码还要再叠 56 MiB KV ＋ 每步 CMA 分配，那一步从未执行过 ⇒ 该行不能当成"Qwen3 能在这块板上生成"的证据。

## 七、判"过了"的六行读数（LLM 版，替代 SOP 阶段 3 那句"算子缺口＝0"）

| # | 读数 | 过了的样子（Qwen3 件实测） |
|---|---|---|
| 1 | 输入条数与逐条形状 | 58 入／57 出；`input_ids [1,1] fp32`、`token_dynamic_fm [1,3] fp32`、56 条 KV `[1,8,512,128] fp16` |
| 2 | `compile_target` 分布 | 2,177 `@zhuget(330)` ＋ 61 `@hostt`，**且 host 只允许出现那 6 类** |
| 3 | NPU 侧语义集合 | 15 种，逐一对官方表 `√`（第五节表） |
| 4 | host 侧专用算子 | `RopeDynamic`／`CausalMask`／`SliceDynamic`／`Gather` ＝ 合同规定，**不登记为缺口** |
| 5 | per-layer 算式咬合 | Softmax＝SiLU＝层数；Matmul＝7×层数＋1；SimplifiedLayerNorm＝4×层数＋1（有 QK-Norm）或 2×层数＋1（无） |
| 6 | `.raw` 字节数＝json 里 `params_bytes` | 1,603,399,624 B 两侧相等（A） |

取数脚本（可复跑，无需板子）：

```
python -X utf8 -c "
import json,io,collections
d=json.load(io.open(r'board/Q3I-decoder_ZG.json',encoding='utf-8'));ops=d['ops']
print('ops',len(ops),collections.Counter(o['compile_target'] for o in ops))
print(collections.Counter(o['name'].split('::')[-1].replace('Node','') for o in ops
      if o['_type_key']=='icraft::xir::HardOp').most_common())
print(collections.Counter(o['_type_key'].split('::')[-1] for o in ops if 'host' in o['compile_target']))
"
```

## 八、双向 gap（"那个 SOP 缺什么／这次缺什么"）

### 8.1 既有两页缺的 11 条

| # | 缺的那条 | 该落在哪 | 为什么算缺 |
|---|---|---|---|
| 1 | 阶段 3 的"算子缺口＝0"对 LLM 不成立 | [[NPU模型上板出指标SOP]] 阶段表那格 `:16`（正文在 `:58`） | 61 个 `@hostt` 会被读成 59 个缺口，而 `Gather` 官方标的是 `× Host 回退` |
| 2 | 没有"前端摄取门"（ir／opset／域／`-e cpu` 退化／fp16 `Transpose`） | 同上，阶段 1～2 之间 | LLM 上这是**第一道墙**，撞过四次；检测类整条链没撞过，所以页里一个字没有 |
| 3 | 没有"图合同"这一层 | 同上，阶段 3 | 合同那节只有"输入形状对"一句；LLM 是 58 条输入＋宽度必须对上 |
| 4 | 起跑门禁的**代码块**里只有 `md5sum /mnt/boot/BOOT.bin` | 同上，阶段 6 那三查（`:117`） | 等效判据（`/mnt/boot` 挂不挂随开机变 ⇒ 改看日志 `Device Name: zg330aiu`）**正文 `:122` 已经写了**，代码块里没有 ⇒ 照抄那行的人会拿到 `No such file` 并误判成"位流没了"。缺的是"把等效判据并进可抄的那三行" |
| 5 | 内存门禁只写 `free -m` ＋ `rmem/udmabuf` | 同上，阶段 6 | LLM 实测两个数**各自都会到个位数 MB，但不在同一窗**：`CmaFree` 最低 80 kB 在 lazy-load 窗、`MemAvailable` 最低 5,020 kB 在 apply 窗（同窗 `CmaFree` 2,440 kB）；厂商 Qwen2 真跑一轮时 `CmaFree` 8,860 kB 而 `MemAvailable` 还有 386,740 kB ⇒ 判据要**指名 `CmaFree`**，`free -m` 那行会给出"还有几百 MB"的错结论 |
| 6 | 缺口登记表只有"一个缺口一行"，没有"设计性 host 回退"这一类 | [[算子缺口处理]] §7（`:131`） | `RopeDynamic`／`CausalMask`／`SliceDynamic`／`Gather` 无处登记，要么被塞成缺口、要么整个消失 |
| 7 | §10 的 Qwen2 行预判已被实测推翻还挂着 | [[算子缺口处理]] §10（`:251`） | 原文判"第一位是工具链变体 `3.33.1-llmgenai`、本地没有这个包"；实际用 genai 0.17.1 ＋ icraft 3.39.0 就出了 `_ZG` 件，并在板上过一次 NPU 编程 |
| 8 | "`embedding` 是 LLM 头号风险"没有对应处置条目 | [[算子缺口处理]] §10.1（`:268`） | 风险成立但落点＝host 是设计；条目里没写这句，下一个人还会去补硬算子 |
| 9 | `-inf` 那条只写了 whisper，没写 LLM 路径怎么绕开 | [[算子缺口处理]] §10.1（`:266`） | 我方件里 `-inf` 由 host `CausalMask` 承担，零改写通过——这是**同一风险的另一种已验证答案** |
| 10 | 官方 117 行表覆盖不到 LLM 专用算子，任何页都没写 | [[iCraft算子支持矩阵]] §一 或本页 §5 | A：`docs/ops/` 全树命中 0；拿那张表当 LLM 的 D2 分母必然错 |
| 11 | 缺"跨机验收边界"一节 | [[NPU模型上板出指标SOP]] 一、总路由 | LLM 链每步产物跨机传（校机导出→本机改写＋编译→板子跑），`.data` 硬链接、opset 改写、推送逐文件 md5 这些环节在检测类 SOP 里不存在 |

### 8.2 这次缺的 9 条

| # | 缺的 | 现状 |
|---|---|---|
| 1 | **零个 token** | Qwen3 件过了 NPU 编程，但板上没有 Qwen3 驱动 ⇒ "件内数值在 NPU 上对不对"仍未答（`pipeline.md:17`） |
| 2 | **板端 profiling 零次** | NPU 侧占比最大的是 `Reshape` 765＋`Transpose` 280＝**搬运类**，不是计算；没有耗时占比，按 [[算子缺口处理]] §5 的门槛 2 就没资格谈路径④，也没法判"要不要把搬运下沉到 PL" |
| 3 | **opset 21 未决** | 任务 #8（`pipeline.md:486`）：换候选时到底改元数据还是改结构，现在不知道 |
| 4 | `.raw` 多出的约 411 MB 成分未核 | 所以 ERNIE 的 970 MB 只能是 C，不能当盘容量结论 |
| 5 | 空载 `CmaFree` 那 130 MB 是谁占的没取证 | `pipeline.md:357`／台账 `#213`；s0～s2 同跑 lazy-load 却一动不动，当场 dmesg 已随重启冲掉 |
| 6 | **ERNIE 只走完了门 0（导出＋HF 基准），四道门零读数** | §6.5：10-30 件已在盘（图／数值两项过）、**但没喂过 icraft** ⇒ 门 3／门 4 仍无读数；门 1 还多了一条未知＝这颗的 KV 第 4 轴天生是符号轴（那条与 #9 末句是同一个问题，现在绕不过去了） |
| 7 | 窗口只有 512 | 更长／更短窗口对板端 CMA 与 `.raw` 的影响一次都没测过（`cos/sin_cache` 行数与 KV 第三维都是编译期烘的） |
| 8 | D2 表未按 §7.1 的四列形态登记 | 本页第五节是"件内实读"，缺 [[算子缺口处理]] §7.1 那套"原图算子→最终去向→三态→**诸葛侧依据**"里的 `ZhugeLayoutPass::*_layout` 依据名 |
| 9 | **流程正本 §8 产物清单那三处对不上——①②10-30 已改进 `pipeline.md`，③同日结案** | ① `:439` 原记"ir10／opset21"，盘上 `compile/fmodel/qwen3_exported/model.onnx` 实为 **ir8**／opset21（247,199 B 字节相等）；ir10 原文逐字节留底两份＝同目录 `model.onnx.ir10.bak` 与 `q3_ir10/model.onnx`（都 `bc4b36a2…`）⇒ 原件被就地改写过，**那条命令行没留档**。② `:440` 那行"字节＝同上"**错**：`q3_o17sln/model.onnx` 实为 **248,054 B**，＋855 B 全部来自 `--sln-ms` 换域（只换域的 `q3_slnms` 同为 248,054、只改 ir 的 `q3_ir10` 仍 247,199 ⇒ opset 21→17 自身 0 B）。③ **交付线那三份 ONNX 就是探索线那三件的字节**（`07caf0e3`／`05cb26f2`／`0665e4e0` 逐一对平）——反证：`meta_variant.py --src` 指到新导出件跑出 249,286／`8ee9e248`，与盘上那份对不上。新导出 `q3i_fp16_cuda`（248,431／ir10／opset22）与旧那份差 1,232 B，**全部**＝112 条 KV 张量（56 进 `past_key_values.*`＋56 出 `present.*`）的第四轴 `dim_value: 128` → `dim_param: "kv_cache_dim"`（11 B×112＝1,232 对平），而节点 0 处不同、初始化器 0 处不同、`.data` 6＋6 刀 0 处不等 ⇒ **交付线从没编过自己新导出的那张图**，`Q3I-decoder_ZG.raw`＝`Q3V1-decoder_ZG.raw`＝板上那颗 `1081ddd7…`，两颗 `_ZG.json` 只差 offset 202 起的名字串。数值上无害（权重逐刀相等），但两件事因此成立：D-62"证整条链可复现"在 ONNX 段**拿不出独立字节证据**；而**唯一没进过 icraft 的正是那张把 KV 第四轴符号化的新图**——现役那颗是烘死的定长 `@fp(16)[1,8,512,128]`，**符号轴编译器吃不吃、会不会让 KV 变成长度可变，一次都没测**（门 2 那条"KV 定长"的判据对它尚未成立） |

## 九、这颗件到底"绑"什么——器件档 vs 板（10-30 结案）

**她问的原话**：这个做出来的模型是对所有 icraft 支持的 NPU 都能用，还是只能 ZG 架构，还是只能这块板？

**三句答**：

1. **绑架构＋核，不绑板**（A）：编译产物只在网络头记一个 `ai_target`——`repos/lang/llm/Qwen3-0.6B/board/Q3I-decoder_ZG.json`（2,679,170 B）逐字段直读＝`ai_target="@zhuget(330)"`、`framework_kind=ONNX`、`framework_version=opset17`、`icraft_version=v3.39.0`、`icraft_xir_version=3.39.0.0`、`llm_mode=True`、`swap_mode=False`、`params_bytes`／`params_md5`＋`ops`。逐个字在这整份 json 里命中 **0**：`40000000`／`80000000`／`axi://`／`zg330aiu`／`ql100`／`wolong`／`ZG340`／`ZG30S`／`device_name`／`board` ⇒ **板级的东西一个都没写进件里**，写进去的只有"诸葛核、330 这一档"。
2. **跨架构不可能**（B＋A）：`compile_target.h` 的目标类是 `HostTarget`／`FPGATarget`／`CustomTarget`／`BuyiTarget`／`ZhugeTarget`／`WolongTarget`，其中**只有 Zhuge 与 Wolong 带核号**——`ZhugeTargetNode{ WISE_ENUM_CLASS_MEMBER(Core, ZG330, ZG340, ZG30S ); Core core = Core::ZG330; }`、`WolongTargetNode{ Core, WL340, WL30S; 默认 WL340 }`（`C:\Icraft\CLI v3.39.0\docs\xir\_cppapi\program_listing_file_icraft-xir_core_compile_target.h.html` 逐行直取，A）。**Buyi 那颗类没有核枚举**＝另一套 codegen 与另一套设备类；换架构＝重编，且算子归属表要按那一档重判。`target='zhuge'` 的 toml 不写核号，所以 330 是**默认值落到件里**（A：件内读数就是 `(330)`）。
3. **"绑档"不等于"绑这块板的地址映射"**（B）：`docs/axizg330aiu/index.html` 原文——`Device::Open("axi://zg330aiu")` 的 URL 参数 `npu`（NPU 挂 GP0 的起始地址，默认 `0x40000000`）与 `dma`（默认 `0x80000000`）是**开设备时按进程给的**，那句"如果不能把 NPU 和 DMA 放到 GP0 和 GP1 的起始位置，则需要将 Device 的 URL 参数设置到其真正的位置"。⇒ 换一块把 NPU 集成到别的地址的板，改的是**主机侧 URL**，不是件。

### 9.1 但"同档换板就能跑"这件事**一次都没测过**（C，别当已知）

| 未知 | 现状 |
|---|---|
| 3.39.0 给了哪几颗设备的运行时 | `docs/` 顶层只有 `axizg330aiu`／`axiql100aiu`／`socketzg330aiu`／`socketql100aiu` 四个设备页 ＋ `hostbackend`／`zg330backend`／`buyibackend`（A：目录直读）⇒ **ZG340／ZG30S／WL340／WL30S 在 3.39.0 里没有对应的设备运行时**。枚举里能写，盘上跑不了 |
| 官方算子表按器件分列 | 列是 `ZG330_ZG340 \| ZG30S \| BY` 三格（§5 那张表）：**ZG330 与 ZG340 共享一列**、ZG30S 会分家——例子里最刺眼的是 `Cast`＝`√条件 / × / ×`（`:60`）。⇒ 同列的 ZG340 理论上算子面一致，**没有任何一颗 ZG340 件被我方编过或跑过** |
| 板级三道门 | 位流里有没有 NPU（[[板端我方代码与产物台账]] 与 `Device Name: zg330aiu` 那条判据）、CMA 池大小（我们这颗件 lazy-load 窗 `CmaFree` 最低 80 kB）、aarch64 运行时与盘容量 ⇒ **这三条与"档"无关、每换一块板都要重跑**（门 4，§二） |

### 9.2 一句话口径（可以对外说的版本）

**件绑"诸葛 ZG330 这一档核"，不绑悟净这块板**；同一 iCraft 版本给同档另一块板，理论上只要按那块板的 AXI 集成地址改 Device URL、并重新过量流／CMA／盘三道门——**这条路径我方零次实测**。换到 Wolong／Buyi 架构＝重编，且 3.39.0 根本没有那几颗的设备运行时。

## 相关页面

[[NPU模型上板出指标SOP]] · [[算子缺口处理]] · [[iCraft算子支持矩阵]] · [[icraft.v3.39.0_支持算子表]] · [[Qwen3按Qwen3配方迁移]] · [[Qwen3按厂商Qwen2配方迁移]] · [[qwen3-0.6b]] · [[交叉编译主机路由SOP]] · [[板端我方代码与产物台账]] · [[状态源与决策记录]]
