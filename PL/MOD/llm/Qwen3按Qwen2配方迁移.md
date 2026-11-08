# Qwen3按Qwen2配方迁移

> **本页回答什么问题**：厂商给 30TAI 板的 Qwen2-0.5B 那套配方——输入件、编译配置、驱动约定、板端运行库、上板件形态——逐条过到 Qwen3-Instruct 上：**哪几条照抄能用、哪几条必须改、哪几条照抄必炸**。"Qwen3-Instruct"＝`Qwen/Qwen3-0.6B`（0.6B 档 instruct 系本尊，纠名判据见 [[Qwen3按Qwen3配方迁移#一、先纠名：Qwen3 的 instruct 系就是不带后缀的 Qwen3-0.6B|Qwen3-Instruct按Qwen3配方迁移——一]] 与 [[状态源与决策记录#D-62 · Qwen3-Instruct 交付线立项：instruct 系＝Qwen3-0.6B 本尊、按路由 SOP 分工重跑收进 repos 子模块、不上板|状态源与决策记录——D-62]]）。
> **本页是"为什么"篇**：[[Qwen3按Qwen3配方迁移#三、SOP：阶段 0～7，逐条照抄|Qwen3-Instruct按Qwen3配方迁移——三]] 那份 SOP 回答"怎么做"，本页给出它每一步的存在理由；Qwen2 配方里没被 SOP 收编的项，本页写明为什么不收。
> **零运行**：2026-10-19 成文，本页不跑任何东西、不承载新读数；全部证据引自探索线（[[Qwen3按厂商Qwen2配方迁移]]、[[qwen3-0.6b]]——与 Qwen3-Instruct 是同一颗模型）的实测，出处以链接给出、数值不复制（D-20）。
> **判据等级**：A＝探索线实机实测原文（本页全是引用）；B＝厂商文件／源码直读；C＝推断（标明未实测）。
> 相关页：[[Qwen3按Qwen3配方迁移]]、[[Qwen3按厂商Qwen2配方迁移]]、[[qwen3-0.6b]]、[[NPU调用链]]。

## 一、Qwen2 配方是什么（先列全，再谈迁移）

厂商配方＝五件东西。**迁移的单位是"条"，不是"整套"**——第二节把每一件拆成可独立判定的条目：

| # | 配方件 | Qwen2 现值 | 出处 |
|---|---|---|---|
| R1 | 输入件 | ORT-GenAI builder 的 fp16 decoder 导出件（`genai_config.json` 直证：`type = "qwen2"`、每层一颗 `com.microsoft` 域 `GroupQueryAttention`） | B：[[Qwen3按厂商Qwen2配方迁移#一、TL;DR|Qwen3按厂商Qwen2配方迁移——一]] |
| R2 | 编译配置 | icraft toml 六键：`target zhuge`／`llm_mode true`／`max_prompt_length 32`／`max_tokens_length 512`／`qdtype fp16`／`pass_off icraft.MergeTransDataOpSeqPass` | [[Qwen3按厂商Qwen2配方迁移#八、复现所需文件位置|Qwen3按厂商Qwen2配方迁移——八]] |
| R3 | 驱动 | `qwen2_infer_decode_only_axi.py`：逐 token 灌 decoder 当 prefill（不用 prefill 网络）、首 token 位置 1 起、slot 0 永久零 pad、greedy 采样 | [[Qwen3按厂商Qwen2配方迁移#六、板上运行侧要改什么（B：直读厂商 qwen2_infer_decode_only_axi.py）|Qwen3按厂商Qwen2配方迁移——六]] |
| R4 | 板端运行库 | icraft cp38 wheel＋tokenizers 0.13.3（三处死 import 补丁） | [[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |
| R5 | 上板件形态 | `_ZG.json`＋`_ZG.raw` 一对（板上 `jr_path/decode/`），不是 `.imodel` 单文件 | [[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |

## 二、逐条判定：照抄、必须改、照抄必炸

判定取四值：**照抄**（原样可用）／**必须改**（不改走不通）／**照抄必炸**（不改则产出废件或崩）／**不动**（已知差异、实测无害）。D 段（驱动与板侧）在交付线**不上板**（D-62）期间不执行，登记在此为配方完整性与将来上板（指针在 [[Qwen3按Qwen3配方迁移#六、上板前置（本线不做，只登记指针）|Qwen3-Instruct按Qwen3配方迁移——六]]）。

### 导出段（输入件从哪来）

| 条 | 配方条目 | Qwen2 现值 | Qwen3-Instruct 的做法 | 判定 | 证据 |
|---|---|---|---|---|---|
| E0 | 权重获取 | 厂商直接给成品件 | 自下：**模型站官方工具**（ModelScope `snapshot_download`，`dl_qwen3.py`）；连不上先换国内同款站找同一颗、无果再查本机 mihomo 代理——全库下载规矩，不用 curl/wget 直拉权重 | 新增（非迁移项） | A（脚本实测）＋全库规矩 |
| E1 | 导出工具 | ORT-GenAI builder | 同一 builder，原生支持 `Qwen3ForCausalLM`（含 QK-Norm） | 照抄 | A：[[Qwen3按厂商Qwen2配方迁移#一、TL;DR|Qwen3按厂商Qwen2配方迁移——一]] |
| E2 | 导出参数 | fp16＋cuda | 同参数（`-e cuda` 只决定图的算子选择与 dtype，导出本身是 CPU 上的 torch trace） | 照抄 | A 命令／C 机制：[[Qwen3按厂商Qwen2配方迁移#二、导出：命令与产物（A，2026-10-12 在校机实跑）|Qwen3按厂商Qwen2配方迁移——二]] |
| E3 | QK-Norm 融合开关 | 无此结构、无此开关 | 必须带 `--extra_options fuse_qk_norm_gqa=false`，否则 per-head QK-Norm 被折进 GQA、icraft 没有对应算子 | 必须加 | 带旗标的导出与编译全程 A；"不带则折叠"＝B：[[qwen3-0.6b#五、怎么跑（逐条可抄）|qwen3-0.6b——五]] |
| E4 | cpu 导出变体 | 无此配方 | `fp16＋cpu` 会退化成 2125 节点 MHA＋显式 RoPE＋多出 `position_ids` 输入，icraft 过不去 | 别走 | A：[[Qwen3按厂商Qwen2配方迁移#二、导出：命令与产物（A，2026-10-12 在校机实跑）|Qwen3按厂商Qwen2配方迁移——二]] |

### 图改写段（Qwen2 配方里没有这一步——厂商件零改写直接编；Qwen3 全部新增）

| 条 | 配方条目 | Qwen2 现值 | Qwen3-Instruct 的做法 | 判定 | 证据 |
|---|---|---|---|---|---|
| G1 | 元数据 | 厂商件 IR 10／opset 21 直接过 parse | 压 IR 8／`ai.onnx` opset 17，否则撞 icraft 自带 ORT 的两道加载期校验 | 必须改 | A：[[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]]（9.2） |
| G2 | QK-Norm 算子域 | —（Qwen2 无 QK-Norm） | 57 颗 `SimplifiedLayerNormalization` 移入 `com.microsoft` 域；与 G1 是**捆绑验证**（三项一起过了加载期），G2 单独的必要性未单测，SOP 照带 | 必须改 | A 捆绑：同上（9.3） |
| G3 | embedding 存储 | 双份存储（Gather 与 MatMul 各一份），图内没有 fp16 `Transpose` | 转置副本写进 data 块、删全图唯一那颗 fp16 `Transpose`——`Unknown dtype 10` 的单点诱因；代价是数据块多一份转置副本（与厂商同形） | 必须改 | A 现象／B"唯一诱因"：同上（9.3、9.4） |
| G4 | 其余图差异 | — | GQA 的 `local_window_size=-1` 属性、第 12 个空输入槽、每层多一颗 `Split`、28 层／8 KV 头／head_dim 128：探索线已逐条回答，**全都不是拦截点** | 不动 | A：[[Qwen3按厂商Qwen2配方迁移#四、结构差异：Qwen3 相对厂商 Qwen2 少／多什么|Qwen3按厂商Qwen2配方迁移——四]] 与 [[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]] |

### 编译段

| 条 | 配方条目 | Qwen2 现值 | Qwen3-Instruct 的做法 | 判定 | 证据 |
|---|---|---|---|---|---|
| C1 | toml 键值 | R2 六键 | **逐键保持原值**，只改 `net_name` 与两条路径（`mk_parse_toml.py` 干的就是这件事） | 照抄 | A：[[Qwen3按厂商Qwen2配方迁移#八、复现所需文件位置|Qwen3按厂商Qwen2配方迁移——八]] |
| C2 | 五段顺序 | parse→optimize→quantize→adapt→generate | 前四段同序照跑；`generate` 挪到 mask0 补丁之后——未补丁的 `_ZG` 件在 Qwen3 上没有交付价值（见 D2） | 照抄＋一处挪位 | A：[[Qwen3-Instruct按Qwen3配方迁移#三、SOP：阶段 0～7，逐条照抄|Qwen3-Instruct按Qwen3配方迁移——三]] 阶段 3～4 |

### 驱动与板侧段（上板时才执行）

| 条 | 配方条目 | Qwen2 现值 | Qwen3-Instruct 的做法 | 判定 | 证据 |
|---|---|---|---|---|---|
| D0 | chat 模板 | Qwen2 ChatML 前缀直接可用 | Qwen3 模板默认走 thinking 分支，要显式关（`enable_thinking=False` 或改模板），否则首 token 就不是答案 | 必须改 | C（未实测）：[[Qwen3按厂商Qwen2配方迁移#六、板上运行侧要改什么（B：直读厂商 qwen2_infer_decode_only_axi.py）|Qwen3按厂商Qwen2配方迁移——六]] |
| D1 | prefill 方式 | 逐 token 灌 decoder、不用 prefill 网络 | 同一条路可走 | 照抄 | A：[[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |
| D2 | 位置与零槽约定 | 首 token 位置 1 起、slot 0 永久零 pad 且 mask 开着它 | **照抄必炸**：Qwen3 特有地退化成单字循环（per-head QK-Norm 令零槽不可忽略）；驱动侧往零槽填东西的两条路已实测全废，唯一已验证修法＝mask0 图级补丁 | 照抄必炸→必须改 | A：[[qwen3-0.6b#三、做到哪一步了（10-12）|qwen3-0.6b——三]] |
| D3 | token_dynamic_fm 喂法 | 只喂 2 个 fp32（厂商自己的 bug，PC Host 后端查不出宽度） | 必须喂 3 个（图声明 `fp32[1,3]`；这条对 Qwen2、Qwen3 两颗件都成立） | 必须改 | A：[[qwen3-0.6b#四、随时能跑吗|qwen3-0.6b——四]] |
| D4 | 结构硬编码 | 24 层／2 KV 头／head_dim 64 | 28 层／8 KV 头／head_dim 128（I/O 契约：56 个 past KV 张量 `[1,8,512,128]`） | 必须改 | A：[[Qwen3按厂商Qwen2配方迁移#六、板上运行侧要改什么（B：直读厂商 qwen2_infer_decode_only_axi.py）|Qwen3按厂商Qwen2配方迁移——六]] |
| D5 | KV 回喂 | 压缩回喂（`cache[i]=present[i+1]`，与图声明 `past_present_share_buffer: true` 不一致） | 原样回喂，已实测正确 | 必须改 | A：[[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |
| D6 | 采样与词表 | greedy；vocab／eos／pad 同值 | 同值不动 | 照抄 | A：[[Qwen3按厂商Qwen2配方迁移#六、板上运行侧要改什么（B：直读厂商 qwen2_infer_decode_only_axi.py）|Qwen3按厂商Qwen2配方迁移——六]] |
| D7 | 内存与 CMA 口径 | Qwen2 那套账 | Qwen3 的 KV 与驱动侧占用比 Qwen2 大一截；上板门禁先看 `CmaFree`、不与直播链同窗 | 属上板前置 | A：[[qwen3-0.6b#七、RAM 账与 OOM 会怎样（10-12 实测＋逐行读码）|qwen3-0.6b——七]] |

### 运行库与件形态段

| 条 | 配方条目 | Qwen2 现值 | Qwen3-Instruct 的做法 | 判定 | 证据 |
|---|---|---|---|---|---|
| L1 | 板端运行库 | icraft cp38＋tokenizers 0.13.3＋三处死 import 补丁 | 复用同一套，无需新补丁 | 照抄 | A：[[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |
| F1 | 上板件形态 | `_ZG.json`＋`_ZG.raw` 一对 | 同一形态（层数×头数不同） | 照抄 | A：[[qwen3-0.6b#一、qwen2 → 3-0.6b 的逐项对照|qwen3-0.6b——一]] |

## 三、照抄不改会死在哪一步（失败矩阵）

跳过哪条改写、死在哪一步、症状长什么样——除注明外均为探索线实测原文（A）：

| 跳过 | 死点 | 症状 |
|---|---|---|
| E3（不带 `fuse_qk_norm_gqa=false`） | parse 前 | QK-Norm 已被折进 GQA，icraft 没有对应算子（B：机制直读，未实测反例） |
| G1（不压 IR／opset） | icraft-parse 加载期 | `Unsupported model IR version: 10, max supported IR version: 8`；只压 IR 不压 opset 则 `Opset 21 is under development … till opset 17` |
| G3（不删 fp16 Transpose） | parse 形状推断 | `Unknown dtype 10`（10＝ONNX 的 FLOAT16；厂商件因 embedding 双存，图里根本没有这颗 Transpose） |
| D2（不打 mask0 就前向／上板） | 生成质量 | 25 步全部锁死同一 token（"往"）；同口径下 icraft 与 HF 逐 argmax 相同 ⇒ 件是忠实的、毒在约定本身 |
| D3（token_dynamic_fm 只喂 2 元素） | 板上第一次真跑 | `hardop.cpp:46 host_chunk byte_size:8 is diff from plddr_chunk byte_size:12`——PC Host 后端不查输入宽度，这条只有上板才暴露 |

出处：[[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]]（9.2、9.3）、[[qwen3-0.6b#三、做到哪一步了（10-12）|qwen3-0.6b——三]]、[[qwen3-0.6b#四、随时能跑吗|qwen3-0.6b——四]]。

## 四、结论：差集已固化成交付线 SOP

- Qwen2 配方迁移到 Qwen3-Instruct 的**充分差集**＝E3＋G1～G3＋C2 的挪位＋D0／D2／D3／D4／D5＋mask0 补丁；其余条目全部照抄。这组差集已逐条固化进 [[Qwen3按Qwen3配方迁移#三、SOP：阶段 0～7，逐条照抄|Qwen3-Instruct按Qwen3配方迁移——三]]：阶段 1＝E 段、阶段 2＝G 段、阶段 3～4＝C 段＋mask0、阶段 5＝数值验证；D 段留在该页第六节当上板前置。
- **两页分工**：要跑→SOP 页（照抄命令与判据）；要知道每步为什么存在、Qwen2 配方哪些不能原样用→本页。
- Qwen2 配方里**明确不收编**的三条：E4（cpu 导出变体，图结构离厂商件太远）、D2 的零槽约定（被 mask0 图级补丁取代）、D5 的压缩回喂（被原样回喂取代）。
- 本页属 [[状态源与决策记录#D-62 · Qwen3-Instruct 交付线立项：instruct 系＝Qwen3-0.6B 本尊、按路由 SOP 分工重跑收进 repos 子模块、不上板|状态源与决策记录——D-62]] 交付线的文档面，不新增决策、不承载读数；主机分工（校机导出／HF 基准、本机编译）照 [[交叉编译主机路由SOP#一、三台机各自能做到什么（路由的唯一依据）|交叉编译主机路由SOP——一]]。
