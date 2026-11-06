# Qwen3-0.6B 按厂商 Qwen2 配方迁移

> **本页回答什么问题**：厂商给 30TAI 板的那份 Qwen2-0.5B 输入件到底是什么格式、由什么工具产出；Qwen3-0.6B 能不能用同一个工具产出同格式的文件；已经做到哪一步、还差哪一步。
> **判据等级**：A＝本次在实机上跑出来的原文读数（命令与输出都记在本页），B＝厂商文件／源码直读，C＝推断。凡 C 级都写明"未实测"。
> **测试主机**：学校公共机 Win11-HV1（EPYC 24 核、125 GB、无 GPU），`D:\yzd\qwen3`，venv＝python 3.12.15 ＋ torch 2.14.1＋cpu ＋ transformers 5.19.0 ＋ onnxruntime 1.31.0 ＋ onnxruntime-genai 0.17.1 ＋ onnx 1.23.2。**板子自 2026-10-11 起不可达，本页没有任何板上读数。**
> **路径已变（2026-10-18）**：校机那套已整体迁到 `D:\yzd\WCIS\MOD\qwen3`，页内所有 `D:\yzd\qwen3` 命令都是**当时的实测原文、未改**；照抄前把前缀换成 `D:\yzd\WCIS\MOD\qwen3`。迁移后 venv 的 `python.exe` 实测仍 import torch 2.14.1＋cpu／transformers 5.19.0／onnxruntime 1.31.0（A），但 `venv\Scripts\` 里 34 个 `.exe` 启动器有 32 个字节里嵌着旧绝对路径解释器（B，按 `yzd.{1,3}qwen3` 计数），实测 `accelerate.exe`／`normalizer.exe`／`f2py.exe` 三只一律 `error: uv trampoline failed to canonicalize script path`、RC=1（A）——其余 29 只是同机制推断。本页流程只经 `python.exe -m …` 起，不碰这些启动器。
> 相关页：[[1-NPU模型部署]]（选型表与本页要更正的两行）、[[NPU调用链]]、[[算子缺口处理]]、[[板端我方代码与产物台账]]。

## 一、TL;DR

- **厂商那份输入件不是 icraft 的产物，是微软 ORT-GenAI 的导出件**。直证（B）：`fmodel/qwen2_exported_model_cuda/genai_config.json` 里 `session_options.log_id = "onnxruntime-genai"`、`type = "qwen2"`；图里每层一颗 `GroupQueryAttention`（com.microsoft 域）＋ `SkipSimplifiedLayerNormalization`。所以"卡 `icraft-llm-genai` 组件"这个旧结论作废——**从来不需要那个组件，需要的是 genai 的 builder**（见 §二）。
- **onnxruntime-genai 0.17.1 的 builder 原生支持 `Qwen3ForCausalLM`**，含 QK-Norm，因此"Qwen3 现在不能迁"（我 10-11 的旧判断）也作废。**已产出 Qwen3-0.6B 的同格式文件并数值验证通过（A）**。
- 产出后还做了一步"对齐厂商约定"（opset 22→21、符号维 `kv_cache_dim`→字面 128），对齐前后 logits 读数**逐位相同**（A），所以这一步不改变数学。
- **没做的只剩一步**：`icraft compile`。它的可行性证据在 §五，风险点列在 §六，跑在哪台机器归她定（禁止在板上编译）。

## 二、导出：命令与产物（A，2026-10-12 在校机实跑）

三个变体都成功，`RC=0`：

```powershell
# 变体 A（数值验证用）
D:\yzd\qwen3\venv\Scripts\python.exe -m onnxruntime_genai.models.builder `
  -i D:\yzd\qwen3\Qwen3-0.6B -o D:\yzd\qwen3\qwen3_fp32_cpu -p fp32 -e cpu -c D:\yzd\qwen3\cache_dir

# 变体 B（编译候选：与厂商文件同 dtype、同 GQA 路线，且禁止把 QK-Norm 折进 GQA）
... -m onnxruntime_genai.models.builder `
  -i D:\yzd\qwen3\Qwen3-0.6B -o D:\yzd\qwen3\qwen3_fp16_cuda -p fp16 -e cuda -c D:\yzd\qwen3\cache_dir `
  --extra_options fuse_qk_norm_gqa=false

# 变体 C（弃用）：-p fp16 -e cpu → 走不了 GQA，退化成 2125 节点的 MultiHeadAttention＋显式 RotaryEmbedding＋多出 position_ids 输入
```

| 变体 | dtype | attention 路线 | 节点数 | 权重字节 | 用途 |
|---|---|---|---|---|---|
| A `qwen3_fp32_cpu` | fp32 | GQA | 520 | 2,405,171,200 | 数值验证基准 |
| **B `qwen3_fp16_cuda`** | **fp16** | **GQA** | **520** | **1,202,585,600** | **icraft 编译候选** |
| C `qwen3_fp16_cpu` | fp16 | MHA＋显式 RoPE | 2125 | 1,202,585,600 | 结构离厂商文件太远，弃 |

**为什么 `-e cuda` 能在无 GPU 的机器上跑**：builder 的 `ep` 只决定图的算子选择与 dtype，导出本身是 CPU 上的 torch trace（C：从 `models/builders/base.py` 的能力表 `is_gqa_supported = {("cpu", FLOAT), ("cuda", FLOAT16), ...}` 读出的机制归属，未在别的机器复核）。

**依赖坑**：0.17.1 的 wheel 没声明 builder 的依赖，直接跑会 `ModuleNotFoundError: No module named 'onnx_ir'`；补 `uv pip install onnx-ir gguf`（实测装到 `onnx-ir==1.0.0`、`gguf==0.19.0`）才能 `import builder`。旧文档里的 `convert_hf_to_onnx` 在这个版本已删除。

## 三、数值验证：导出的图确实是 Qwen3-0.6B（A）

`verify_onnx.py`：同一 prompt（`请用一句话介绍量子计算。`，7 token）分别跑 HF fp32 CPU（`use_cache=False`）与 ONNX CPU EP，先 prefill，再把 ONNX 自己产出的 `present.*` 当 `past_*` 喂回走一步 decode——这条恰好复刻板端脚本的 decode-only 循环。

| 图 | prefill maxabs／relmax／cos | decode maxabs／relmax／cos | top-5 与 argmax |
|---|---|---|---|
| A fp32 | 0.00003 ／ 0.00000 ／ 1.000000 | 0.00003 ／ 0.00000 ／ 1.000000 | 与 golden 完全一致（`[220, 4710, 109539, 1406, 62926]`→`[109539, 220, 11622, 105321, 14880]`） |
| B fp16 | 0.02215 ／ 0.00151 ／ 0.999999 | 0.01941 ／ 0.00103 ／ 0.999999 | 与 golden 完全一致 |
| B 对齐后（`_v`） | 与 B 逐项相同 | 与 B 逐项相同 | 同上 |

B 用的是 fp16 的 CPU kernel——顺带证明这颗 `GroupQueryAttention` fp16 图在 ORT 1.31 CPU EP 上能跑通。

## 四、结构差异：Qwen3 相对厂商 Qwen2 少／多什么

### 4.1 模型本身（A：`config.json` ＋ 两份 `genai_config.json` 直读）

| 项 | Qwen2-0.5B-Instruct | Qwen3-0.6B |
|---|---|---|
| 层数 | 24 | **28** |
| 注意力头／KV 头 | 14 ／ 2 | **16 ／ 8** |
| head_size | 64 | **128**（显式，不等于 hidden/heads＝64） |
| hidden | 896 | 1024 |
| MLP intermediate | 4864 | 3072 |
| QK-Norm | 无 | **每层 2 颗 RMSNorm**（`model.layers.i.attn.{q,k}_norm.layernorm.weight`，共 56 颗） |
| attention bias | 有 | **无** |
| vocab | 151936 | 151936（同） |
| context_length | 32768 | 40960 |
| eos／pad／bos | `[151645,151643]`／151643／151643 | 同 |
| 权重字节 | 1,264,529,152（embed 与 lm_head **各存一份** 272,269,312） | 1,202,585,600（**只存一份** 311,164,928，tie 生效） |

### 4.2 图签名（A：`diff_graphs.py` 对两份 `model.onnx`）

厂商已验收的 Qwen2 图：opset `('',21)+('com.microsoft',1)`、299 节点、50 入／49 出、无 `position_ids`、每层 `qkv_proj/MatMul → qkv_proj/Add → GroupQueryAttention`。

我们的 Qwen3 图（B 变体，520 节点／58 入／57 出）与它的差，分两类：

**（一）导出器版本差异，不是 Qwen3 的差异**——已全部就地修掉或已知无害：
- opset 22 → 21（0.17.1 在 `base.py:135` 硬写 `opset_imports={"": 22}`）；
- `past/present.*.key|value` 最后一维是符号名 `kv_cache_dim`（`base.py:200` 起，注释写明"为了同一份导出兼顾量化后的 KV"）→ 改成字面 128。**共替换 112 处（56 入＋56 出）**；
- GQA 多一条属性 `local_window_size = -1`、输入槽从 11 个变 12 个（多一个空的 v_bias 可选输入）——**这两项没动**，是留给编译阶段的不确定项；
- 每层多一颗 `Split`（packed qkv 拆回 q/k/v）。

**（二）Qwen3 真实差异**：每层 `Reshape → SimplifiedLayerNormalization → Reshape` 两组（q_norm、k_norm），无 qkv bias 的 `Add`，层数 28，KV 形状 `(1, 8, seq, 128)`。

修完的图与厂商图**同级对照**：

```
opset [('', 21), ('com.microsoft', 1)]        # 两份一致
in2   past_key_values.0.key float16 [batch_size, 8, 'past_sequence_length', 128]   # 厂商：[..., 2, ..., 64]
out0  logits float16 [batch_size, 'sequence_length', 151936]                        # 与厂商同形
has position_ids: False                                                             # 与厂商同
```

`vendorize.py` 只改 protobuf 里的 opset 与维度字段，权重一个字节没重写（`model.onnx.data` 是 copy 过去的），所以对齐前后 verify 读数逐项相同就是这一步的正确性判据。

## 五、icraft 侧的已知事实（B：直读她本机那次真编译留下的阶段日志）

`C:\Icraft\CLI v3.39.0` 编厂商 Qwen2 时留下的 `.icraft/logs/Qwen2-0.5B/Qwen2-0.5B-decoder_parse.log` 里，parse 阶段命中的 pattern 只有这 11 种：`Input`、`Gather`、`MatMul`、`Add`、`GroupQueryAttention`、`SkipSimplifiedLayerNormalization`、`SimplifiedLayerNormalization`、`Sigmoid Mul`、`Mul`、`Output`；`GroupQueryAttention` 在 parse 里被展开成 xir 原语，展开后全图 op 类型计数含 `Slice 240 / Reshape 240 / Matmul 169 / Multiply 144 / Add 144 / Transpose 120 / Cast 73 / SimplifiedLayerNorm 49 / Tile 48 / SliceDynamic 48 / Neg 48 / Concat 48 / Softmax 24 / SiLU 24 / Expand 24 / RopeDynamic 1 / CausalMask 1 / Gather 1 / Input 1 / Output 1`，且**该 parse 日志里搜 unsupported／fallback／custom／warning／cpu impl 全部为空**。

由此：
- `SimplifiedLayerNormalization` 本身是被支持的一等公民（layer 0 的 `input_layernorm` 就是它，展开成 `SimplifiedLayerNormNode`）→ Qwen3 的 QK-Norm 落在同一条路径上（C：形态相同，未实测）。
- 那台机器上 GQA 被展开后 **host 侧没有残留算子**，说明 ZG 的 LLM 路线不依赖 `icraft-llm-genai`（B）。
- ~~真正的未知项是：`Split`（厂商图里没有这个 ONNX 算子）、GQA 上多出的 `local_window_size` 属性、第 12 个空输入槽、28 层／8×128 的头维是否触碰 tiling 或 OCM 上限。这四条只能由 `icraft-parse` 单独跑一次来回答。~~ **10-12 已答：四条都不是拦截点**，带着它们整条链路一路跑到了 adapted，见第九节。
- 阶段可以单跑：`icraft compile <toml> --dry_run` 实测打印出的是五条文命令，第一条就是 `icraft-parse --framework "onnx" --jr_path ... --llm_mode --max_prompt_length "32" --max_tokens_length "512" --net_name ... --network ... --network_exdata ... --quantized --target "zhuge"`（A，10-12 本机 dry_run 原文）。**所以先只跑 parse 就能拿到算子答案**；Qwen2 那次的 parse 产物是 `Qwen2-0.5B-decoder_parsed.json` 1,036,616 B ＋ `.raw` 1,263,614,652 B，日志时间戳 19:55→19:56，据此估**一两分钟、1.2 GB 中间件**（C：未对 Qwen3 实测，层数多 17％、节点多 74％，可能要翻倍）。

## 六、板上运行侧要改什么（B：直读厂商 `qwen2_infer_decode_only_axi.py`）

| 位置 | 现值 | 改法 |
|---|---|---|
| `:222-224` | `n_layers=24`、`n_kv_heads=2`、`head_dim=64` | 28 ／ 8 ／ 128 |
| `:22-24` `ModelConfig` | `config_path`、`decode_json`、`decode_raw` 三条路径 | 指向 Qwen3 的 tokenizer 目录与 `Qwen3-0.6B-decoder_ZG.{json,raw}` |
| `:26` `max_decode_length=512` | 不用改数值，但**显存代价变了**（下条） | |
| `:31` `vocab_size`、`:492` `eos_id` | 151936／151643 | 同值，不动 |
| 采样 | greedy | 同，不动 |

**内存口径（C，未上板）**：每层每 KV 张量在 `max_decode_length` 下是 `1×8×512×128×fp16 = 1,048,576 B`，56 个张量 ≈ **56 MiB**；Qwen2 是 48 个 `1×2×512×64×fp16 = 128 KiB` ≈ 6 MiB。也就是说光 feed 字典就比 Qwen2 多约 50 MB，而每步 `run_decode` 还会把 56 个 `present.*` 从设备上取回成 numpy 再转成 Tensor（`:451`、`:290-299`）。对照板上已知的闸门：993 MB 里 256 MB 是 CMA，匿名页额度只有 700～825 MB（见 [[板端内存上限与心跳日志]]）。**这是上板前必须先在 PC 侧算清、再在板上实测的第一项。**

**速度预期（C，纯推算）**：decode-only 模式下每步 KV 读取量与序列长度成正比，Qwen3 是 Qwen2 的 9.33 倍／token（`2×28×8×128×2 B ＝ 114,688 B` 对 `12,288 B`）。README 记的 Qwen2 实测 4.68 tok/s 不应外推到 Qwen3。

**chat template**：Qwen3 默认模板会走 thinking 分支，接入时要显式关掉（`enable_thinking=False` 或改模板），否则首 token 就不是答案。此条**未实测**。

## 七、遗留与更正登记

- **更正 1**：[[1-NPU模型部署]] 第 97 行与第 139 行"Qwen2-0.5B 卡的是工具链变体／等 llm-genai"——作废。厂商路线不需要 `icraft-llm-genai`；缺的是 ORT-GenAI builder 产出的输入件，且该输入件 Qwen2、Qwen3 都已能产出。
- **更正 2**：我 10-11 判的"Qwen3-0.6B 现在不能迁＝缺 genai 格式输入件"——作废，同上一条。
- 顺手记一笔读数错误：我曾按 hidden/heads 推 Qwen3 的 intermediate 与 head_dim，实际 `intermediate_size=3072`（不是 3584）、`head_dim=128` 是配置里显式给的、不等于 `1024/16`。
- ~~**未做**：`icraft compile`（跑在哪台机器待她定，禁止在板上编）；板上任何一步（板子 10-11 起不可达）；Qwen2 第一次点火的复跑。~~ **10-12 更新**：parse／optimize／quantize／adapt 四段已在本机跑通（第九节）；仍未做的只剩 `generate`（出 ZG imodel，跑在哪台机器要定）、板上任何一步（板子 10-11 起不可达）、Qwen2 第一次点火的复跑。

## 八、复现所需文件位置

校机 `D:\yzd\qwen3\`：`Qwen3-0.6B\`（ModelScope 快照 1.415 GB）、`qwen3_fp16_cuda_v\`（**编译候选**，`model.onnx` 247,199 B ＋ `model.onnx.data` 1,202,585,600 B）、`qwen3_fp32_cpu_v\`（验证基准）、`venv\`、脚本 `dl_qwen3.py`／`export_a.ps1`／`export_b.ps1`／`verify_onnx.py`／`diff_graphs.py`／`vendorize.py`／`account.py`。
本机 `S:\apps\llm\agentwork\qwen3\`：同名脚本副本 ＋ `compile\Qwen3-0.6B_decoder.toml`（照厂商 toml 逐键克隆，只改 `net_name` 与两条路径，`llm_mode true`／`target zhuge`／`max_prompt_length 32`／`max_tokens_length 512`／`qdtype fp16`／`pass_off icraft.MergeTransDataOpSeqPass` 全部保持原值），`compile\fmodel\qwen3_exported\` 已放好 ONNX 与 data（`model.onnx` 247,199 B ＋ `model.onnx.data` 1,202,585,600 B），派生件见第九节末尾的清单。

## 九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose

### 9.1 `run_llm.exe` 这条路对 30TAI 不成立（A）

- `run_llm.exe` 的导入表只有 `icraft_wl170backend`、`icraft_xrt_wl`、`icraft_hostbackend_wl` 三颗后端库；changelog 原话是"支持 ZG30S 浮点核的编译、量化、指令生成和 run_llm 运行链路"。ZG330（＝30TAI／悟净）不在它的后端集合里。
- 不上板的前向也堵：官方 `zg330backend` 页写 `mock://zg330` "只包含内存分配功能，用于不上板生成快照……无法进行前向操作"，同页只在 `save_snapshot` 示例里出现它。
- 所以 PC 上出 token 的等价路径是 `icraft-run --backends Host` 跑 **adapted 阶段**的 json＋raw：x86 HostBackend 支持全部 builtin 算子（A，`docs/start/running.html` 的后端能力表），而 adapted 阶段的 json 里 **一个 HardOp 都没有**（A，本轮实测 2795 个算子的直方图），HardOp 是 `generate` 才塞进去的。

### 9.2 加载期元数据：分流开关不是元数据（A）

同一个 `icraft-parse`、同一份 toml 形状，只改声明：

| 输入件 | 结果 |
|---|---|
| 厂商 Qwen2 原文件 IR 10／opset 21 | parse rc=0，`prefill`＋`decoder` 各 json 1.04 MB、raw 1.26 GB |
| 厂商文件改成 IR 8（opset 仍 21）＝`VIR8` | parse rc=0，raw 1,260,542,652／1,263,614,652 B |
| 厂商文件改成 IR 8＋opset 17＝`VIR8O17` | parse rc=0，同上尺寸 |
| 我们 Qwen3 导出件 IR 10 | `Unsupported model IR version: 10, max supported IR version: 8`（`model.cc:147`） |
| 我们 Qwen3 导出件 IR 8／opset 21 | `Opset 21 is under development … Current official support for domain ai.onnx is till opset 17`（`model_load_utils.h:57`） |
| 上面两条各自的"只移域不改 opset"变体 | 依旧同一加载期报错，移 `SimplifiedLayerNormalization` 到 `com.microsoft` 不改变结论 |

⇒ 厂商文件在 IR 8 和 opset 17 下都照过，说明**它从没进过那颗老 ORT**；我们的图一进就撞 IR／opset 两道校验。我们的导出件要往下走，得先把 `ir_version` 压到 8、`ai.onnx` 压到 17（`vendorize.py` 里已写死 IR 8）。

### 9.3 真正的拦截点：`Unknown dtype 10`（A 现象，B 归因）

IR 8＋opset 17＋57 个 QK-Norm 移入 `com.microsoft` 之后，加载过了，死在 `Exception info : Unknown dtype 10`（10＝ONNX 枚举里的 FLOAT16）。现象细节：

- 位置在 `network_input` 这个 Input 节点打完之后，**第二个 `Pattern :` 行都没打出来**（A，`.icraft/logs/Q3O17SLN/*_prefill_parse.log` 全文 3823 行只有一条 Pattern）。
- 字符串 `Unknown dtype ` 在 `icraft_onnx_parser.dll` 里紧挨着 `ox_shape_infer.cpp`、`[ORTMANAGER assignValue]`、`no value info`、`[Shape infer]`（A：直接扫 DLL 字节）。⇒ 是 icraft 自己的 ORT 形状推断器在把 OrtValue 的 elem_type 映射成内部 dtype，那个 switch 没有 fp16 分支。
- 两边的 dtype 集合完全相同（输入 int64×2＋fp16×56／48、初始化器全 fp16、value_info 只有 int32/int64/fp16，A：`chk_dtypes.py`），所以不是"我们用了个怪 dtype"。

图里**唯一的 fp16 `Transpose`**：`/model/embed_tokens/Transpose`，perm `[1,0]`，输入是初始化器 `lm_head.MatMul.weight` fp16 `[1024,151936]`，唯一消费者是 `/model/embed_tokens/Gather`（A）。厂商 Qwen2 之所以没这问题：它**把 embedding 存了两份**——`model.embed_tokens.weight` `[151936,896]` 直接喂 Gather、`lm_head.MatMul.weight` `[896,151936]` 喂 MatMul，各 272,269,312 B，图里一个 `Transpose` 都没有（A）。

归因等级说明：本轮是"去掉这个节点之后整条链路就通了"的单变量证据（A），但没单独验证"保留 opset 21 只去 Transpose"的组合，所以**"这个 Transpose 是唯一诱因"只算 B**；待测项登记在 9.7。

### 9.4 改法与产物（A）

`detranspose_embed.py`：读出 `[1024,151936]` 的 fp16 权重 → `np.ascontiguousarray(w.T)` → 追加到 `.data` 尾部 4096 对齐偏移 1,202,585,600 → 新增外部初始化器 `model.embed_tokens.weight` `[151936,1024]` → 删掉 Transpose 节点和它的 value_info → `Gather.input[0]` 改指向初始化器。回读逐元素相等。代价：**数据块从 1,202,585,600 B 变 1,513,750,528 B**（多存一份 311,164,928 B 的转置副本，跟厂商同形）。源文件绝不能就地追加——前面几步的 `.data` 是硬链接，写穿链接会毁掉原件，脚本里因此一律新建文件。

产物（`compile\jr_path\Q3V1\`）：

| 文件 | 大小 | 说明 |
|---|---|---|
| `Q3V1-prefill_parsed.json`／`.raw` | 1,286,056／1,505,119,988 B | parse |
| `Q3V1-decoder_parsed.json`／`.raw` | 1,281,405／1,532,890,868 B | parse |
| `Q3V1-decoder_optimized/quantized/adapted.json` | 1,105,196／1,113,166／2,330,428 B | 三段各 rc=0，各约 50 s |
| `Q3V1-decoder_adapted.raw` | 1,532,919,484 B | Host 前向用的就是这个 |

adapted decoder 网络（A）：2795 个 xir 算子，`Reshape 1045／Transpose 280／Matmul 197／Slice 113／SimplifiedLayerNorm 113／Split 29／Softmax 28／SiLU 28／CausalMask 1／RopeDynamic 1 …`，**HardOp 0 个**；`compile_target` 是 61 个 `@hostt` ＋ 2734 个 `@zhuget(330)`。

I/O 契约（A，跟厂商 Qwen2 同形，只是维度换成 8×128／28 层）：

- decoder 输入 58 个：`@fp(32)[1,1]`（input_ids）、`@fp(32)[1,3]`（token_dynamic_fm）、56× `@fp(16)[1,8,512,128]` layout `***C`（past KV）。
- decoder 输出 57 个：`@fp(16)[1,1,151936]`（logits，v_id 10105）＋ 56× `@fp(16)[1,8,512,128]`（present KV）。
- prefill 是同一张图的 `[1,32]` 版：输出 `@fp(16)[1,32,151936]`。

喂数据口径（A，见第十节：已用 adapted json 的连线＋SFT 实测件反推出完整语义，原来那句"第三个值填 0 是推断"作废）。厂商脚本 `:415-417` 给的是 `decode_seq_len=1`、`token_dynamic_fm=[[1, seq_pos]]` fp32、`input_ids` fp32。**它只有 2 个值，而 json 声明 `[1,3]`，这不是矛盾**：**厂商脚本 `qwen2_infer_decode_only_axi.py` 的 2 值 `[[1, seq_pos]]` 与网络声明的 `[1,3]` 不是矛盾**：`token_dynamic_fm` 被 1 个 Reshape、1 个 RopeDynamic、2 组 SliceDynamic、1 个 CausalMask 整体消费，第 0 个元素单独切出来进 RopeDynamic，第 1 个元素同时是 RoPE 绝对位置、KV 写入槽号、CausalMask 有效长度，**第 2 个元素图上没有任何消费者**（喂 `[1,1,0]` 与 `[1,1,1]` 的 logits 逐元素相同）。`:270-274` KV 用 `np.zeros((1, n_kv_heads, max_decode_length, head_dim))`；`:290-299` 只有 idx 0/1 走 `float32` ＋ `xir.Layout("*C")`，其余走 fp16。另外厂商这个脚本压根不用 prefill 网络——`:353-366` 的 `process_prompt_character_by_character` 是拿 decode 网络把 prompt 一个 token 一个 token 灌进去当 prefill 用，所以 PC 侧出 token 只需要 decoder 这一张图。

### 9.5 作废的方法：裁层 bisect（A）

`shrink_layers.py` 裁出来的图不能用作归因证据：用**同一个脚本**裁厂商 Qwen2（2 层、35 节点、IR 10、元数据与原件一致）产出的 `T0`，在 `Parsing 22%` 处段错误（`错误码-1073741819`）。也就是说裁剪本身产出不合法图，"层数／头维是不是闸门"当时用这条路测不出任何结论。有效的是本轮这种**单点结构改写＋已知能过的图做对照**。

### 9.6 复现命令（本机，逐条可抄）

```
# 0) 元数据：ir 8 / ai.onnx opset 17 / QK-Norm 移入 com.microsoft
python meta_variant.py --dst q3_o17sln --opset 17 --sln-ms
# 1) 消掉 fp16 Transpose（厂商形态：embedding 存两份）
python detranspose_embed.py --src compile/fmodel/q3_o17sln --dst compile/fmodel/q3_v1
# 2) 生成 parse-only toml（照 Qwen3-0.6B_decoder.toml 克隆，只改 net_name 与两条路径）
python mk_parse_toml.py --name Q3V1 --fm q3_v1
# 3) 四段编译（cwd = compile/）
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" parse    Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" optimize Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" quantize Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" adapt    Q3V1_parse.toml
# 4) PC 前向：绝对路径的输入清单，否则报 File "... does not exist!"
python mk_feed.py --json S:/apps/llm/agentwork/qwen3/compile/jr_path/Q3V1/Q3V1-decoder_adapted.json ^
                  --out S:/apps/llm/agentwork/qwen3/compile/feed1 --token 1427 --pos 1
"C:/Icraft/CLI v3.39.0/bin/icraft-run.exe" --json ...adapted.json --raw ...adapted.raw ^
  --input S:/apps/llm/agentwork/qwen3/compile/feed1/inputs.txt --backends Host ^
  --dump_output --dump_format SFT --log_path .../rundef --log_time
```

脚本清单（`S:\apps\llm\agentwork\qwen3\`）：`meta_variant.py`（元数据变体，`.data` 走硬链接）、`detranspose_embed.py`、`mk_parse_toml.py`、`mk_feed.py`、`chk_opset.py`（opset／ir／算子域直方图）、`chk_dtypes.py`（每个容器的 elem_type 分布）、`shrink_layers.py`（已判定不可用于归因，见 9.5）、`vendorize.py`、`fix_ir.py`、`verify_onnx.py`、`diff_graphs.py`、`account.py`、`dtxt.py`（读官方 html 文档用），以及第十节的 `host_gen.py`／`ref_hf.py`／`cmp_logits.py`／`chk_dynamic.py`／`chk_tdf.py`。

### 9.7 待测与未做

- 保留 opset 21、只去 Transpose：过／不过？——决定 9.2 那句要写成"我们的图必须 ≤17"还是"必须改结构"。
- `generate` 出 ZG 件：**10-12 已跑完**（`icraft.exe generate Q3V1_parse.toml`，342 s）→
  `Q3V1-decoder_ZG.json` 2,676,018 B／`Q3V1-decoder_ZG.raw` 1,603,398,820 B，2235 算子里 **HardOp 2174**。
  但**ZG 件的数值一点没验**（本机没有能前向的 ZG 模拟器），只有上板才知道。操作记录见 [[qwen3-0.6b]]。
- ~~Host 前向的 logits 对不对~~：已解决，见第十节（A 级：与 HF fp32 eager 基准 corr 0.9996／0.9998，两步链 argmax 一致）。
- 板上侧一切（板子 10-11 起不可达）。

## 十、10-12 Host 前向跑通＋与 HF 数值对齐（A）

### 10.1 `token_dynamic_fm` 的真实语义（A）

`chk_tdf.py` 直读 adapted json：v_id 1（`@fp(32)[1,3]`）的消费者是 `16 Reshape`、`20 RopeDynamic`、`42/43 SliceDynamic`、`62 CausalMask` 等——即整个 `[1,3]` 张量被原样送进 RoPE 与 mask，只有第 0 个元素另走一条 `SliceDynamic(begin/end [0,0,0]-[1,1,1]) → Cast` 的支路当"本步新 token 数"。

- **元素 1 一身三职**：RoPE 绝对位置 ＋ KV 写入槽号 ＋ CausalMask 有效长度。
- **元素 2 没有消费者**：喂 `[1,1,0]` 与 `[1,1,1]` 的 logits 逐元素相同。
- 槽号实测：`[1,1,0]` 那步 present 相对 past 只有 slot 1 变化（1024 个非零＝8 头×128）；下一步 `[1,2,0]` 只有 slot 2 变化。`gen_chain2/step0|step1` 的 feed↔present 差分。
- **元素 1 = 0 跑不出来**：`stepTo faild, op_id = 4525, op_type = icraft::xir::ReshapeNode … shape '[1, 8, 2, 8, 1, 16]' is invalid for input of size 1048576`（期望 2048 元素，拿到 2048×512）——动态维取 0 时切片长度反过来膨胀 512 倍。这不是喂料格式错，是图本身的限制。

后果（A）：厂商导出件锁死"首 token 从元素 1 = 1 起、slot 0 永久留全零 pad，而 mask 仍然打开这个 pad"。该 pad 会参与 softmax 归一化，等于把注意力输出整体乘 α=Σe^z/(Σe^z+1)；**argmax 排序不受影响**（10.2 实测两边 top 序一致），但数值与 HF 精确口径不等价。要不要把 baked 的 `cos_cache/sin_cache` 在 `adapted.raw` 里整体平移一行来消掉这个 pad，是一个未做的岔路——**10-12 她判"维持厂商的吧"，该岔路关闭**，`host_gen.py --pos-offset` 默认已改成 1。

### 10.2 与 HF 基准的数值对齐（A）

HF 侧＝校机 `D:\yzd\qwen3\Qwen3-0.6B`，`transformers 5.19.0`／`torch 2.14.1+cpu`／fp32／`attn_implementation='eager'`／device cpu。比对必须 **teacher-force**：两边 step 0 的 argmax 本来就差 0.12 个 logit（fp16 噪声量级），各自贪心下去会从 step 1 分叉，所以校机用 `ref_hf.py --simulate 1427,124674 --teacher` 按 icraft 的喂入序列重算。

| 步 | 喂入 | icraft argmax | HF argmax | 是否一致 | corr | meanabs | maxabs | top100 重合 |
|---|---|---|---|---|---|---|---|---|
| 0 | 1427（pos 1） | 124674 | 88778 | 否，但互为对方第 1 名 | 0.999638 | 0.0894 | 0.4456 | 97/100 |
| 1 | 124674（pos 2） | 1427 | 1427 | **是** | 0.999759 | 0.0697 | 0.4492 | 98/100（top10 前 9 名同序） |

对照组：位置 0 的场景（`--zeropast 1427:0`）与 step 0 的 corr 只有 0.176 ⇒ 上面的匹配不是"任何两个 logits 向量都长这样"。

### 10.3 dump 口径与 KV 回喂（A）

- `--dump_ftmp "<v_id 列表>"` 在 3.39.0 上生效：请求 57 个就出 57 个文件，不必整图 dump（整图那步约 4.4 GB）。
- **SFB 一律把值拓宽成 fp32**，与 json 声明无关：logits 607,744 B＝151936×4，present KV 2,097,152 B＝524288×4。⇒ **回喂不能逐字节拷贝**，必须显式 fp32→fp16。
- 拓宽是无损的：dump 的值全部落在 fp16 网格上（`np.all(a == a.astype(np.float16).astype(np.float32))` 为 True），SFT 文本与 SFB 回读最大差 4.96e-05，两边 logits argmax 相同。⇒ 实测 fp32→fp16 回写后与原值 maxdiff **0.0**，链式回喂是零损失往返。

### 10.4 复现命令（icraft 走本机、HF 走校机，逐条可抄）

```
# 本机：两步链（--pos-offset 1 ＝ 厂商约定；element 1 = 0 会在 op_id 4525 挂）
cd S:/apps/llm/agentwork/qwen3/compile
python ../host_gen.py --json jr_path/Q3V1/Q3V1-decoder_adapted.json ^
  --raw jr_path/Q3V1/Q3V1-decoder_adapted.raw ^
  --work gen_chain2 --prompt 1427 --max-new 1 --pos-offset 1 --dump-format SFB
# 校机：HF 侧同约定基准（--teacher ＝ 按给定 token 喂，不用自己的 argmax）
ssh school-guest "cd /d D:\yzd\qwen3 && venv\Scripts\python.exe ref_hf.py --model D:\yzd\qwen3\Qwen3-0.6B --simulate 1427,124674 --teacher --dump-logits D:\yzd\qwen3\logits --out D:\yzd\qwen3\ref_teach.json"
# 本机：比对（驱动会把每步 logits 另存成 step<N>/logits.npy）
python cmp_logits.py --icraft compile/gen_chain2/step1/logits.npy --icraft-format npy ^
  --hf compile/reflogits_sim/logits_teach_step1.npy
```

Host 后端本机单步 46~48 s（fp16、CPU）。新增脚本：`host_gen.py`（多 token 链驱动，`read_dump()` 按"文件字节数／json 元素数"判 dtype）、`chk_dynamic.py`＋`chk_tdf.py`（只读探针：RopeDynamic/SliceDynamic/CausalMask 属性、v_id 1 的全部消费者）、`ref_hf.py`（HF 基准，`--prefixes`／`--zeropast`／`--chain`／`--simulate [--teacher]`）、`cmp_logits.py`（argmax 互排名＋maxabs/meanabs/rms/corr＋topk 重合）。

### 10.5 本节未解

- 真实生成质量：这个 +1 约定（slot 0 零 pad 参与归一化）会不会让长文本退化，没测。手头的弱证据（C）：HF 侧从裸 token id 1427 起按同约定贪心，4 步内塌成重复 88778——但输入是裸 id、不是 chat 模板，不能当结论。
- 平移 `cos_cache/sin_cache` 消掉 pad：未做，见 10.1 末。
