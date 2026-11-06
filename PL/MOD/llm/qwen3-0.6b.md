# qwen3-0.6b

> **厂商 Qwen2 配方到 Qwen3-0.6B 的对照记录**。这页记的是**操作与对照**：厂商给 Qwen2-0.5B 的那套配方，在 Qwen3-0.6B 上逐条怎么落、
> 落到哪一步、哪些是实测、哪些还缺。原理级论证和证据分级在 [[Qwen3按厂商Qwen2配方迁移]]（第七、九、十节），
> 机器可抄的完整流程（含所有中间件在哪、字节数、每条命令）在 `S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\pipeline.md`——**那份是流程正本**（10-28 自 `workenv\qwen3\` 抬进库里；旧根那份 42 289 B／md5 `271f5c2394ce222adf8ea35e24e0baec` 仍在盘，与库内差三处＝入库后补的头部 wiki 路径、§8 路径对照、§9 凭据条，**以库内为正本**。这页原先写的根在 10-18 前叫 `ouroriginalrepo\test\qwen3\`，10-18 目录重组后统一写作 `workenv\`——那一步 `workenv/` 被 `.gitignore` 整目录排除、只本机一份，10-28 这一步把它抬进可推送的 repos 子模块），分脚本说明的 `README.md` 在 `S:\apps\llm\agentwork\qwen3\`（13 995 B，10-14 版，未入库）。这页不重复它们，只做"两边一一对上"的对照表＋状态。
> **校机路径（2026-10-18 变更）**：`D:\yzd\qwen3` → `D:\yzd\WCIS\MOD\qwen3`。本页下面的命令按旧路径原样保留（是当时实测原文），照抄前先换前缀；venv 换址后 `python.exe` 实测可用，细节见 [[Qwen3按厂商Qwen2配方迁移]] 开头。

## 一、qwen2 → 3-0.6b 的逐项对照

| 项 | 厂商 Qwen2-0.5B（板上 `/root/qwen2` 那套） | 我们导出的 Qwen3-0.6B `Q3V1` | 是否同形 |
|---|---|---|---|
| 导出器 | `onnxruntime_genai.models.builder`，`-p fp16 -e cuda` | 同，另加 `--extra_options fuse_qk_norm_gqa=false` | **是**，只多这一个选项 |
| 图内注意力 | `com.microsoft.GroupQueryAttention` ×层数 | 同 | 是 |
| QK-Norm | 没有（Qwen2 结构不带） | `com.microsoft.SimplifiedLayerNormalization` ×57（q/k 各一层×28 层减共享） | **Qwen3 多出来的**，已随 `fuse_qk_norm_gqa=false` 保留在原位 |
| embedding 存储 | 转置后存成初始化器，图内无 fp16 `Transpose` | 用 `detranspose_embed.py` 改成同形（多一份 311,164,928 B 转置副本） | 是（改写后） |
| 元数据 | onnx 标 ir 10／opset 21 | 降到 ir 8／opset 17（icraft 自带 ORT 只到 max IR 8） | **不同**，但不影响（厂商标 21 也能过，见迁移页 §9.2） |
| decoder 输入 | `@fp(32)[1,1]` ＋ `@fp(32)[1,3]` ＋ `n_layer×2`× `@fp(16)[1,2,512,64]` | `@fp(32)[1,1]` ＋ `@fp(32)[1,3]` ＋ 56× `@fp(16)[1,8,512,128]` | 是，只换维度 |
| decoder 输出 | logits ＋ 同数 present | logits(v_id 10105, `[1,1,151936]`) ＋ 56 present | 是 |
| `token_dynamic_fm` 语义 | 元素 0＝本步新 token 数、元素 1＝位置＝写槽＝mask 长度、元素 2 没人读 | 同（实测，见迁移页 §10.1） | **是，连"第 3 个值不读"都一样** |
| 首 token 位置 | 1 基、slot 0 永久零 pad | 同（`--pos-offset 1`） | **是** |
| 前置处理 | 不用 prefill 网络，逐 token 灌 decoder（`qwen2_infer_decode_only_axi.py:353-366`） | 同一条路可走 | 是 |
| KV 回喂 | 厂商驱动做了 `cache[i]=present[i+1]` 的压缩（与 `past_present_share_buffer: true` 不一致） | 我们**原样回喂**（不压缩），已实测正确 | **不同**，我们的做法才是对的 |
| ZG 件 | 1,314,012,420 B `.raw` ＋ 2,183,817 B `.json`，HardOp 1770 | 1,603,398,820 B `.raw` ＋ 2,676,018 B `.json`，**HardOp 2174** | 是（同一形态，层数×头数不同） |
| 板端运行库 | `icraft-3.39.0-cp38-none-manylinux2014_aarch64.whl` ＋ `tokenizers-0.13.3`，三处死 import 补丁 | 两条都要动：① **`tokenizers` 要升**——0.13.3 读不了 `model.merges` 写成**成对数组**（`["Ġ","Ġ"]`）的分词件，报 `ModelWrapper`；厂商 Qwen2 那颗 merges 是空格字符串（`"Ġ Ġ"`）所以当年在 0.13.3 下能用。升到 **0.20.3** 后板上同一颗直接可读（11-04 实测 `load OK`、`你好，世界`→`[108386,3837,99489]` 与本机 0.23.3 逐字相同）；四条对照与 `ignore_merges` 未取证那条正本＝台账 §卅六。② **`import icraft` 要拼包**——板上 pip 里是 3.33.1（`xir.so` 2024-12），系统 `.deb` 里的库是 3.39.0，旧绑定引用的 `icraft::xir::Params::load()` 在新库里已无此符号 ⇒ 直接 import 报 undefined symbol；解法＝3.39 的 `.so` ＋ 3.33 的 `__init__.py`／`.pyi` 拼成 `/root/icraft39`，靠 `PYTHONPATH` 生效（npuserv registry 的 qwen3 条目里 `env.PYTHONPATH` 就是它）。板上那颗件的逐文件清单与 md5 **从未取证**（11-06 想补时板 SSH 不可达），登记见台账 §卅六 | 否（两处都要改） |

## 二、约定：维持厂商的（她 10-12 定）——**这条的代价后来被实测推翻，见 2.1**

**决定：不消掉那个 +1 偏移，照厂商口径跑。** 即首 token 的位置/写槽/mask 都从 1 起，slot 0 永久是全零 pad 且 mask 仍打开它。

- 为什么本来就没得选：`token_dynamic_fm` 元素 1 取 0 **图跑不出来**——`op_id 4525 ReshapeNode` 期望 2048 元素拿到 1048576（动态维膨胀 512 倍）。
- 当时写的代价（**已作废**）：零 pad 参与 softmax 归一化，注意力输出整体乘 α=Σe^z/(Σe^z+1)，"数值与 HF 精确口径不等价、
  **argmax 排序不受影响**（两步实测都对齐，见迁移页 §10.2）"。
- 放弃的岔路：把 baked 的 `cos_cache/sin_cache` 在 `adapted.raw` 里整体平移一行消掉 pad。不做。
- `host_gen.py --pos-offset` 的默认值已改成 1，避免下一个人重新踩 op_id 4525。

### 2.1 公开更正：那句"argmax 排序不受影响"只在 teacher-force 下成立，自由生成下不成立

定这条口径时手里只有 teacher-force 的两步比对（两边喂的是同一串 token，所以零槽只影响数值、不影响单步排序）。
10-12 用修正后的驱动跑了自由生成，实测（A）：

- 校机 HF fp32/eager、同一个模型、同一个 11-token chat 前缀：`--pad-slots 0` 出通顺中文；
  `--pad-slots 1`（＝厂商口径）从**第一个生成 token** 起就锁死在 `99321`＝"往"，25 步全是同一个字。
- icraft 在同口径（`--pos-offset 1`）下 35 步 argmax 与 HF 的 `--pad-slots 1` **逐个相同** ⇒ **编译件是忠实的，
  病根就是那个被 mask 打开的全零槽本身**，不是件、不是位置偏移、不是回喂方式。
- 机理（B）：零 K ⇒ 分数恒 0，零 V ⇒ 分子不贡献，只给分母加 e^0＝1 ⇒ 注意力输出整体乘 α＝Σe^z/(Σe^z＋1)。
  Qwen3 的 per-head QK-Norm 把分数压在 O(1)，这一项就不再可忽略，28 层串进残差流后把分布带偏；
  Qwen2 没有 QK-Norm，分数动辄十几，e^0 无所谓——这解释了厂商那套在 Qwen2 上"能用"。

- **对照组（A，10-12 补测）**：拿**厂商自己的** `Qwen2-0.5B-decoder_adapted` 件、本机同一条 Host 前向、同一个 11-token chat
  前缀、同样 `--pos-offset 1`（＝零 pad 口径原样），27 步出的是 **`我是来自阿里云的超大规模语言模型，我叫通义千问`**，
  16 个生成 token 逐个不同、run-length 全为 1。⇒ **零 pad 不是这条流程的病，是 Qwen3 特有的病**；
  "厂商那套在 Qwen2 上能用"从推断升成实测。Qwen2 单步 28~32 s、`icraft-run` 峰 5,169 MB（Qwen3 是 40.9 s／6,025 MB）。
  读数与跑法＝`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\pipeline.md` §6 判定 4、产物 `compile/q2_chat_text.txt`。

**所以"维持厂商的"这条决定当时是在没量出代价的情况下做的，代价现在是已知的：Qwen2 没事、Qwen3 输出不可用。**

出路到 10-13 只剩一条（扫描过程＝`PIPELINE.md` §6 判定 5，脚本 `padfix.py` 在校机跑 HF fp32 替身）：
a 重导出成 0 基位置（要先破 op_id 4525 的 reshape 崩溃）＝与"把 mask 的第 0 槽关掉"**数值逐个相同**（25/25 id 一致，A）；
b **驱动侧**把 slot 0 填成 slot 1 或最新槽的 K/V 副本＝**已实测作废**（copy1 出 `واروال…` 一字循环、copylast 第一个生成位就是 stop token）；
c 用 prefill 网络一次吞 prompt＝治不了，decode 每步照样带着那个零槽；
**d＝只改 mask**：编译件里 mask 只有一个张量（`CausalMask` op_id 48 输出 v_id 180 `@fp(32)[1,1,512]`，
单步 dump 实测值 `[0, 0, -inf×510]`，A），28 层各自把它 **Add** 到分数上再 Softmax ⇒ 在 v_id 180 后插一个 `Add` 常数
（index 0＝-inf、其余 0）就等于已验证的 mask0。该 op 能配的只有 `prefill_max`／`fill_value`（icraft 3.39.0 xir docs），
没有"跳过第 0 槽"的旋钮 ⇒ **要重编五段**；手改 icraft IR json 能否过校验＝没试、没验（D）。跑不跑由她定。

**10-14：d 已做完并出了件，上面那句 D 级作废。** 实际用的不是 `Add` 常数（插常数要新增 `Params`、`adapted.raw` 就得重排），
而是在 v_id 180 之后插 **Slice＋Slice＋Concat** 三颗算子把第 0 格换成 `-inf`：
`X=Slice(M,[0,0,511]:[1,1,512])`（＝`M[511]`，除 cache 满那一步外恒为 `-inf`）、`T=Slice(M,[0,0,1]:[1,1,512])`、
`M'=Concat([X,T],axis=2)`，再把唯一消费者 op 4533 的输入从 180 改接到 M′。**零新常量、`.raw` 一字节不动**，所以只重跑 `generate`。
实测（A，本机）：dump 回 `M'`＝`[-inf, 0, -inf×510]`；`@hostt` 变体在 Host 后端 25 个生成 id 与校机 HF `mask0` 基准**逐个全等**，
解出"好的，用户问我是谁。我需要先确认用户的问题意图。用户可能是在测试我的回答能力，"；两变体单步 logits 逐位相同。
`generate` 出的件把这三颗折成 NPU HardOp（2174→2177，`SliceNode` 113→115、`ConcatNode` 56→57）。
**新算子的 `compile_target` 必须跟图内既有 113 颗 Slice／56 颗 Concat 一样标 `@zhuget(330)`**：板端 `libicraft_hostbackend.so`
里查不到 Slice/Concat 的 host 转发符号（同文件 CausalMaskNode/ReshapeNode/CopyNode 各 5 处，二者 0 处，B 级＝字节扫符号），
标 `@hostt` 的那份只在本机 Host 后端能跑。命令正本＝`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\pipeline.md` §4b，脚本 `compile/patch_mask0.py`（同一目录，10-28 入库）。
件内数值仍未验（本机没有能前向 ZG 的模拟器），边界：`e1=511` 那一步第 0 格会重新张开。

## 三、做到哪一步了（10-12）

| 环节 | 状态 | 实测数 |
|---|---|---|
| 导出 fp16/cuda＋禁 QK-Norm 融合 | 完成（校机） | `D:\yzd\qwen3\qwen3_fp16_cuda` |
| 两处结构改写 | 完成 | `compile/fmodel/q3_v1/` |
| parse／optimize／quantize／adapt | 完成，各约 50 s | `compile/jr_path/Q3V1/Q3V1-decoder_adapted.{json,raw}` |
| **generate 出 ZG 件** | **完成**（342 s，`Timer CodeGenFunc`） | `Q3V1-decoder_ZG.json` 2,676,018 B／`Q3V1-decoder_ZG.raw` 1,603,398,820 B；2235 算子里 **HardOp 2174**；`_ZG.raw` 是 `.json`＋`.raw` 一对，不是厂商那种 `.imodel` 单文件——与 `/root/qwen2/jr_path/decode/` 里那两个文件的命名完全一致 |
| PC 出 token（Host 前向） | 完成，**长链也跑通了** | 单步 40.9~48 s；11-token chat 前缀＋24 生成＝35 步整链，与 HF 同口径 **argmax 35/35 逐个相同**（A）；峰 `PeakWorkingSet64` 6,025 MB，产物 5.9 GB |
| teacher-force 逐步对数 | 完成，43 步 | 两边喂同一串 token：corr **0.999922~0.999994**、argmax 41/43（A，`compile/logits_teach43/` ＋ `cmp_chain.py`）。那串 token 出自当时还带 bug 的驱动，不影响本行的保真度结论——它测的是"同一输入两边输出差多少" |
| 生成质量 | **在厂商口径下不可用**，见 §2.1 | `compile/fix_texts.txt`：去掉零槽通顺、留着零槽 25 步全是 `99321` |
| 零槽填法扫描（10-13） | 完成（校机 HF fp32 替身 5 口径＋本机单步 dump mask） | 只有"关掉第 0 槽"和"0 基无 pad"两种通顺，且两者 25/25 个 id 逐个相同；驱动侧填槽两种全废；10 条 prompt 测试集：前者十条全通顺（distinct 21~24），厂商口径 3 条 0 token＋3 条一字循环。`compile/padfix_*.json`、`compile/maskprobe/` |
| **图级 mask 补丁（10-14）** | **完成，并已 `generate` 出补丁件**（未补丁原件留 `Q3V1-decoder_ZG.unpatched.*`） | 三颗 `@zhuget` 算子（Slice/Slice/Concat）把 v_id 180 的第 0 格换成 `-inf`，零新常量、`.raw` 不动；HardOp 2174→2177；`_ZG.raw` md5 与件内 `params_md5` 相等（`1081ddd7…`）；`@hostt` 变体 25/25 id 与 HF `mask0` 全等、单步 40.5~44.0 s、`icraft-run` peakWS 6,024 MB。产物 `compile/gen_mask0/`（6.0 GB） |
| **ZG 件的数值验证** | **Qwen3 这颗仍未验，但"上板"这条路 10-14 已经通了** | 没有能在 PC 上跑 ZG HardOp 的模拟器（`mock://zg330` 不前向，`run_llm.exe` 是 WL170 件）——**要验只能上板**。注意：PC 上验的是 `adapted` 阶段，不是 `_ZG` 件。**10-14 更新**：同一颗位流下、同一支驱动骨架，**厂商 Qwen2 的 `_ZG` 件已经在板上出通顺中文** ⇒ 剩下的不是"板子能不能跑 ZG 件"。**10-28 更正本行末三件事**：件本身 10-14 已拷板、并就地过一次 `apply`（台账 `#208`～`#213`）；改结构（28 层／8 KV head／head_dim 128）与 `token_dynamic_fm` 喂 3 元素两处已在库内 `patch/q3_infer_board.py` 做完（未验）⇒ **只剩"把驱动推上板并点火"这一件**，而那一步的先决条件是 CMA／整机内存（见 §七 第 5 条与台账 `#213` 那两个极值） |
| 装板 | **10-14 点火通了**（用的是厂商 Qwen2 的 `_ZG` 件，不是我方 Qwen3 那颗）；死因 10-13 已定位＝当时板上位流里没有 NPU，10-14 换回 `aca4612b…` 后同一支 bisect 四步全过 | 10-12 的 bisect（每步独立进程）走到 STEP1 `openDevice(...)` 就把整机带走：网络＋串口同时零输出、`bisect.log` 停在 `STEP0 OK`、只能断电。当时板子是空的（load 0.00、`MemAvailable` 747 MB、CMA 剩 61 MB、dmesg 零条 OOM）⇒ 不是内存。**10-13 第四次同签名**（起跑前 `fpga0/state`＝`operating`、load 0.03、`CmaFree` 130 MB、串口抓 7 min 零行 printk）⇒ "state 不是 operating 就别跑"这条门禁作废，真因见 §四 第 3 条。**10-14 实测闭环**：起跑前 `md5sum /mnt/boot/BOOT.bin`＝`aca4612b…` ⇒ `STEP1 OK 1.4s`、`STEP2 OK 4.3s`、`STEP3 OK 64.4s`、`STEP4 OK 132.1s`，全程串口有 printk、网络没断 ⇒ 归因升成 A。我方 Qwen3 那颗 1.6 GB 件**10-14 18:09–18:13（板钟）已拷板**（本行原写"仍从没拷过"，10-28 按板上 `ls` 与 put 记录两侧 md5 更正，台账 `#208`～`#210`）；同晚 18:32–18:43 就地跑四档预检，s1／s2／s3 全 `exit=0`、`apply` 75.1 s ⇒ **编程已过、生成从未执行**（板上没有 Qwen3 驱动，`put.log` 里没有驱动件的 put 行） |
| **板上真跑（10-14，厂商 Qwen2）** | **通，本项目第一次在 ZG330 上出 token** | 20 个生成 token、`Total time: 7.08 s`、`2.83 tokens/s`、`247.71 ms/token`、`Answer: 我是阿里云开发的超大规模语言模型，我叫通义千问。`、首 token id `104198`。**两处新事实**：① 厂商驱动喂 `token_dynamic_fm` 只给 2 个 fp32，ZG 件 v_id 1 声明 `[1,3]`＝12 B ⇒ 板上抛 `hardop.cpp:46 host_chunk byte_size:8 is diff from plddr_chunk byte_size:12`（本机 Host 后端不查宽度，所以 PC 上看不出来），补成 3 元素即通；② **ZG 运行时吃 CMA**：`CmaFree` 130,784 → apply 时 104,580 → 一轮真推理最低 **8,860 kB**（≈122 MB，`CmaTotal` 262,144），`MemAvailable` 最低 386,740 kB、零 OOM、`VmHWM` 673 MB ⇒ 以前那条"要不要 CMA 不知道（D）"现在有答案。**厂商报的 4.68 tokens/s／199 ms 我方没复现**（2.83／247.71），那颗数零条件说明，只并列不作回退证据（B）。取证＝台账 §十四 `#196`／`#197`。**2026-11-01 复核板况**：该件**已不在板上**——10-28 按她指示出库（`/root/qwen2` 1.7 G→496 K，删前六件 md5 两侧逐字相等，见台账 §廿一 末），板上现只剩驱动与日志；**本机正本完整**，当日复算 `Qwen2-0.5B-decoder_ZG.json` 2,183,817 B／`24bf0b6b3d5990056fc66229a88f1020`、`.raw` 1,314,012,420 B／`2b107ec676de2b4dc35b772402b25b92`、`tokenizer.json` 7,028,015 B／`1c74fd33061313fafc6e2561d1ac3164`、`config.json` 659 B／`ac22e24237a5c688f861b4aaf45df9a9`，与台账 `#160`／`#161`／`#164` 三行逐字相同 ⇒ 要重跑得先重推 1.3 GB（≈3.6 min @6 MB/s） |

## 四、随时能跑吗

分两层，答案不一样：

**能随时跑（本机，一条命令）**：PC 侧出 token ＋与 HF 对数。

```
cd S:/apps/llm/agentwork/qwen3/compile
python ../host_gen.py --json jr_path/Q3V1/Q3V1-decoder_adapted.json ^
  --raw jr_path/Q3V1/Q3V1-decoder_adapted.raw ^
  --work gen_fixed35 --prompt 151644,872,198,105043,100165,11319,151645,198,151644,77091,198 ^
  --max-new 24 --pos-offset 1 --dump-format SFB
```

`gen_fixed.ps1` 是带 1 s 内存采样和残留进程清理的同一条命令（10-12 实跑 35 步）。

条件是：本机 `C:\Icraft\CLI v3.39.0` 在、`compile/jr_path/Q3V1/` 那两个 adapted 件在（1.53 GB raw ＋ 2.3 MB json）、
`inputs.txt` 用绝对路径、**空闲物理内存 ≥6 GB**（见 §7.1）。每 token 40.9~48 s，S 盘剩 ~499 GB，一步约 170 MB dump。
HF 基准那条要校机（`ref_hf.py`），但只是比对时才需要。
**注意**：这是 x86 CPU 上的 Host 后端，只证明图和数值对，不代表 NPU 上的速度；厂商报 Qwen2-0.5B 是 199 ms/token。

**10-14 更新：第 3 样已经不是阻塞了**——厂商 Qwen2 的 `_ZG` 件当天在板上跑通（20 token／2.83 tokens/s／答案通顺），
所以下面这三样里只剩 1 和 2 是 Qwen3 自己缺的，第 3 样已解除并有实测背书（取证＝台账 §十四 `#196`／`#197`）。
**还多出一第 4 样（10-14 板上才发现的）**：驱动喂 `token_dynamic_fm` 必须给 **3 个 fp32**——ZG 件把 v_id 1 声明成 `[1,3]`（12 B），
厂商脚本 `:364`／`:416` 只喂 2 个（8 B）⇒ 板上直接抛 `hardop.cpp:46 … host_chunk byte_size:8 is diff from plddr_chunk byte_size:12`。
**本机 Host 后端不查输入宽度，所以这条 PC 上永远看不出来**；我方 Qwen3 的图同样声明 `[1,3]`，改驱动时要一起补。

**10-12 之前缺的是三样**：

1. 1.6 GB 件从没传过板（传输验收口径已备好，A：本机 `md5sum` 对 `_ZG.raw` 实算与件自带 `params_md5` **逐字相等**，所以传完只要重算一次 `.raw` 的 md5 就能定论）。
   **10-14 更正这一行的值**：现上板的那颗是**打过 mask 补丁的件**，`params_md5`＝`1081ddd7…`／2,679,171＋1,603,399,624 B（PIPELINE §8）；
   这里原来写的 `ec18ebf7…`／1,603,398,820 B 是**未补丁原件**，已改名留档为 `Q3V1-decoder_ZG.unpatched.*`。
2. 板上侧的驱动脚本要按我们的序列改（`/root/qwen2/qwen2_infer_decode_only_axi.py` 那份会压缩 KV，我们要原样回喂）。
3. ~~**`openDevice` 一步把整机楔死**~~ ⇒ **10-14 已解除并跑通**：门禁现场复核＝`aca4612b…`（含 NPU）后，同一支 `qwen_bisect.py` 四步全过
   （`STEP1 OK 1.4s`／`STEP2 OK 4.3s`／`STEP3 OK 64.4s`／`STEP4 OK 132.1s`），厂商 Qwen2 的 `_ZG` 件补宽喂料后出 20 个 token、
   `2.83 tokens/s`、`247.71 ms/token`、`Answer: 我是阿里云开发的超大规模语言模型，我叫通义千问。`，**串口全程有 printk、网络一次都没断**
   ⇒ 上面那句归因（位流没 NPU）从推断升成实测。取证＝台账 §十四 `#196`／`#197`，命令与判据＝PIPELINE §7。
   原 10-13 归因（保留）：**那四次挂死当时板上跑的位流里没有 NPU**。
   板侧 python 与厂商件本身是好的：python 3.8.10 ＋ icraft ＋
   tokenizers 0.13.3 ＋ numpy 1.23.0，`from icraft import xir,xrt,host_backend,buyibackend,zg330backend` 和
   `pyrtutils.*` 全部 import 通（A，10-12）；驱动**必须从 `/root/qwen2` 里跑**（`sys.path.append("./modelzoo_utils")` 是相对路径）。
   旧门禁"`fpga0/state` 不是 `operating` 就别跑"**10-13 实测作废**：那次 `state`＝`operating`、`status` 节点不存在、
   dmesg 只有两行 fpga 注册、板子空闲（load 0.03／`MemAvailable` 743 MB／`CmaFree` 130 MB／零条 OOM），STEP1 照样把机器带走。
   `operating` 只说"PL 里有设计在跑"，不说是哪份设计。
   真因两条都已取证（A）：[[位流构建与SDI信号检测]] §4.2 实测 **"NPU 是 PS 通往 PL 的唯一 AXI 端点"**，
   位流里删掉它，`0x4000_0000` 就没有从设备，访问＝互连挂住＝零 printk、只能断电；
   而 [[BOOTbin位流替换手术]] 在 10-10 把**不含 NPU 的纯视频位流**灌进了 `/mnt/boot/BOOT.bin`，
   §6.8.10（10-12 21:15）当时记着"该位流未上板、板上 `BOOT.bin` 仍是上一份（MD5 `fd15bb85…`）"，
   那份新件 `ai7030_lite_pd1` 同样不含 NPU（**10-13 更新**：带状态导出的那颗当日 15:30 已上板，见台账 §十七 `#187`，
   md5 `0f4f00e1…`，它**也不含 NPU** ⇒ 本节归因不变；**10-14 更新**：`0f4f00e1…` 上板 1.5 h 后就被那条会话自己的 `restore.py` 换回了厂商原版，
   **现装 `aca4612b…` 含 NPU ⇒ "板上没有 NPU"这个前提已经解除**，四次挂死的归因照旧成立，但那是当时的事）。
   ⇒ 四次挂死（10-10 `sdi_probe`／10-11 整驱动／10-12 bisect／10-13 bisect）
   **全在 10-10 手术之后，是同一件事**，与内存、CMA、驱动写法无关。
   **恢复不需要厂商、不需要 JTAG**：`mount -t vfat -o rw /dev/mmcblk0p1 /mnt/boot` ＋ `cp /mnt/boot/BOOT.bak /mnt/boot/BOOT.bin` ＋
   `sync` ＋ 重启（卡上 `BOOT.bak`／`BOOT.bak2` 完好，本地另有 `S:\apps\llm\agentwork\board_BOOT.bin` MD5 `aca4612b566738350a8c5edac0db1929`）。
   换回厂商位流后 NPU 就在了；SDI 探测不回退（10-05 在厂商位流下 `sdi_probe` 读到过 `0x88 fetch_cnt=140`，A），
   代价是拿不到我方那条 DDR 状态导出通道（**10-14 实测：现装＝厂商原版，这条通道已经关了**——`#185` 的 `/root/sdi_stat.py` 打印
   `PL status writer ABSENT: magic=0x00000000`；它 10-13 15:30～17:02 那 1.5 h 在板上是活的，读法与字段表见台账 §十七）。
   **10-14：这次"换回"已经由另一条会话的发布脚本自己做掉了**（不是我方下手，取证见台账 §十四"现装位流"），
   要不要再换回我方那颗＝改 PL 现场＋改引导镜像 ⇒ **仍由她定，我不擅自动手**。
   点火前的新门禁＝**核 `/mnt/boot/BOOT.bin` 的 md5**：`aca4612b…`＝厂商原版**含 NPU、可以跑＝10-14 现装**；`0f4f00e1…`＝没 NPU（我方纯视频＋状态导出），别跑；`fd15bb85…`＝没 NPU（我方纯视频），别跑；`611ea706…`＝10-09 那颗，也没 NPU。**`fpga0/state` 那条判据已作废，只认 md5。**

## 五、怎么跑（逐条可抄）

```
# ── 校机：导出（务必带 fuse_qk_norm_gqa=false，否则 QK-Norm 被折进 GQA，icraft 没有对应算子）
ssh school-guest "cd /d D:\yzd\qwen3 && venv\Scripts\python.exe -m onnxruntime_genai.models.builder ^
  -i D:\yzd\qwen3\Qwen3-0.6B -o D:\yzd\qwen3\qwen3_fp16_cuda -p fp16 -e cuda -c D:\yzd\qwen3\cache_dir ^
  --extra_options fuse_qk_norm_gqa=false"
# 本机收下导出件
ssh school-guest "tar -cf - -C D:\yzd\qwen3 qwen3_fp16_cuda" | tar -xf - -C S:/apps/llm/agentwork/qwen3/compile/fmodel

# ── 本机：两处结构改写（顺序不能反；绝不就地追加 .data，前面阶段的 .data 是硬链接，写穿会毁原件）
cd S:/apps/llm/agentwork/qwen3
python meta_variant.py --dst q3_o17sln --opset 17 --sln-ms
python detranspose_embed.py --src compile/fmodel/q3_o17sln --dst compile/fmodel/q3_v1
python mk_parse_toml.py --name Q3V1 --fm q3_v1

# ── 本机：五段编译（cwd 必须是 compile/；判成败看日志有没有 stepTo faild／fatal，别只看 rc）
cd compile
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" parse    Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" optimize Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" quantize Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" adapt    Q3V1_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" generate Q3V1_parse.toml --log_path Q3V1_gen_log

# ── 本机：PC 前向出 token（--pos-offset 1 ＝ 第二节的厂商口径）
python ../host_gen.py --json jr_path/Q3V1/Q3V1-decoder_adapted.json ^
  --raw jr_path/Q3V1/Q3V1-decoder_adapted.raw ^
  --work gen_chain2 --prompt 1427 --max-new 8 --pos-offset 1 --dump-format SFB

# ── 校机＋本机：数值校验（比对必须 --teacher，否则两边从 step 1 就因 argmax 不同而分叉）
ssh school-guest "cd /d D:\yzd\qwen3 && venv\Scripts\python.exe ref_hf.py --model D:\yzd\qwen3\Qwen3-0.6B ^
  --simulate 1427,124674 --teacher --dump-logits D:\yzd\qwen3\logits --out D:\yzd\qwen3\ref_teach.json"
python cmp_logits.py --icraft compile/gen_chain2/step1/logits.npy --icraft-format npy ^
  --hf compile/reflogits_sim/logits_teach_step1.npy
```

喂料契约（定版，A）：`input_ids` `@fp(32)[1,1]`；`token_dynamic_fm` `@fp(32)[1,3]`＝
［本步新 token 数，RoPE 位置＝KV 写槽＝mask 长度，没人读的值］；56× past KV `@fp(16)[1,8,512,128]` 未用位置填 0。
`--dump_ftmp "<v_id 列表>"` 生效（要 57 个出 57 个）；**SFB 一律拓宽成 fp32**（logits 607,744 B＝151936×4、
KV 2,097,152 B＝524288×4）⇒ 回喂必须显式转回 fp16，不能逐字节拷；拓宽无损（实测回写 maxdiff 0.0）。
**prompt 阶段的 argmax 必须丢掉**：`--prompt` 那串逐 token 喂，只有**最后一个** prompt token 那步的 argmax 才是第一个生成 token
（`host_gen.py:252` 与 `ref_hf.py` 的贪心分支此前都每步 `append`，见 §六 第 7 条）。

板上 bisect（1 s 心跳落 eMMC、断电后现场还在；配套 `board/mem_watch.sh`、`board/sercap.ps1` 抓串口 printk）：

```
cd /root/qwen2 && cap.sh --as 2G --tag qb_s1 --interval 1 -- python3 /root/qwen2/qwen_bisect.py 1   # openDevice
cd /root/qwen2 && cap.sh --as 2G --tag qb_s2 --interval 1 -- python3 /root/qwen2/qwen_bisect.py 2   # CreateFromJsonFile 建图
cd /root/qwen2 && cap.sh --as 2G --tag qb_s3 --interval 1 -- python3 /root/qwen2/qwen_bisect.py 3   # lazyLoadParamsFromFile 读 1.22 GiB
cd /root/qwen2 && cap.sh --as 2G --tag qb_s4 --interval 1 -- python3 /root/qwen2/qwen_bisect.py 4   # initSession + apply（给 NPU 编程）
```

## 六、途中修正的事（错过、后来用实测纠正的，别再重新发现一遍）

1. "厂商脚本只给 2 个值，第 3 个填 0 是推断" → **元素 2 是图上真的没有消费者**（`[1,1,0]` 与 `[1,1,1]` 的 logits 逐位相同），网络声明本来就是 `[1,3]`，不矛盾。
2. "present 与 past 同 dtype 同 shape，dump 可以逐字节回喂" → 错，**SFB 一律 fp32**，必须 fp32→fp16。`cmp_logits.py` 的 sfb 分支原来按 `<f2` 读，已改成按字节数判 dtype。
3. "step 1 只对上 35%，链可能有 bug" → 错，是**比对口径错**：HF 侧贪心用自己的 argmax 往下喂，两边 step0 就差 0.12 logit（fp16 噪声）而分叉。加 `--teacher` 后 corr 0.999759、argmax 一致。**多 token 比对一律 `--teacher`**。
4. "`--pos-offset 0` 失败是喂料格式没对" → 错，是图表达不了元素 1＝0（op_id 4525）。这条直接定了第二节的口径。
5. 早期把 `run_llm.exe` 当 PC 前向 → 那是 WL170 件，ZG 档不能用。
6. "单步约 7 分钟" → 那是整图 dump（约 4.4 GB）那一跑的数；`--dump_ftmp` 收窄后实测 **40.9~48 s**。
7. **驱动自己的序列 bug**（10-12 找到并修）：`host_gen.py` 每步都 `seq.append(nxt)`，把 prompt 阶段第 i 步的 argmax 当成
   第 11＋i 个输入喂了回去——输入流被打乱。`ref_hf.py --simulate` 的贪心分支同一个病。两处都改成
   `if i >= len(prompt)-1: append`（`host_gen.py:252`、`ref_hf.py` 的 simulate 循环），docstring 里写清了规则。
   **后果：修之前那条 43 步链的"输出乱码"是驱动的病，不是模型的病**，我一度把它归给零 pad 槽，那条归因当时的证据是污染的。
8. "退化是零 pad 槽造成的" → 这个结论**方向对、证据当时不成立**。干净的证据是修完驱动后的三条：同一模型同一前缀，
   HF 侧 `--pad-slots 0` 通顺、`--pad-slots 1`（厂商口径）锁死 `99321`，而 icraft 同口径 35 步与 HF 的 `--pad-slots 1`
   逐个 argmax 相同（A）。见 §2.1。
9. "逐 token 带缓存的喂法可能不如整段重算" → 错，实测 `--simulate --pad-slots 0 --pos-base 0` 第 10 步的 top5 与
   `--chain` 整段重算的 top5 **逐字相同**（A）⇒ 增量这条路等价，喂法没有系统性偏差。顺带定了第二条旋钮的死刑：
   固定 `--pad-slots` 时 `--pos-base` **完全不改变结果**（p1b1≡p1b0、p0b0≡p0b1），那个 +1 偏移自我抵消、不是变量。
   这两条负断言正是排查 §2.1 那个 bug 时用的工具：位级相同 ⇒ 分叉必然在序列构造侧，不在模型侧。

## 七、RAM 账与 OOM 会怎样（10-12 实测＋逐行读码）

### 7.0 先拆一个前提：原样回喂不比厂商的压缩多占一个字节

两边喂进图的都是 512 槽**全量**张量（56×`[1,8,512,128]` fp16 ＝ 56 MiB），压缩只是把 present 的第 i+1 槽抄到自己
的第 i 槽，抄完照样整个 1 MiB 张量回喂（`:388`）。省不下来，多的那 56 张切片拷贝（每步约 56 MiB 读写）纯属 CPU 开销。

数值上两种做法**等价**（B，逐槽推演，未在板上验）：第 i 步厂商缓存＝`[K_0..K_{i-1}, 0, K_i]`、我们＝`[0, K_0..K_i]`，
都是 i+1 个真 key ＋恰好一个全零 key 落在 mask 开的 0..i+1 里；全零 K ⇒ 分数恒为 0、全零 V ⇒ 分子不贡献，
与那个洞在第几槽无关，两边只差 softmax 分母里同样多的那一项 e^0。前提条件是唯一一条：present 由 past 整体拷贝再覆写
单槽。要是图里 present 不从 past 拷贝，厂商那份会在槽 i 留下上一步的旧值＝重复 key，我们这份不受影响——这也是选原样回喂的
另一个理由。

### 7.1 PC 侧：Host 后端稳态 4.2 GB、收尾瞬时峰值 6.0 GB（A，本机实测）

`chat32.ps1` 每 1 s 采 `Get-Process` 的 WS/PeakWS/Private，样本 `compile/rss_chat32.csv`；机器 16 核／31.3 GB 物理内存。
每步是一个**新的** `icraft-run.exe` 进程（`host_gen.py:180` 的 `subprocess.call`），三步曲线一致：

| 阶段 | 工作集 | 步内用时 |
|---|---|---|
| 进程起来 | 0.55 GB | 0~3 s |
| 平台期（读 json＋建图） | 0.76 GB | 4~19 s |
| 爬坡 | 1.06 → 2.25 → 3.76 GB | 20~34 s |
| 稳态（真在算） | **4.20~4.25 GB** | 34~47 s |
| 收尾瞬时峰值 | **5.29~6.02 GB**（`PeakWorkingSet64` 记到 6,025 MB） | 48~50 s |

10-12 修完驱动后重跑的那条 35 步链（`compile/gen_fixed35_rss.csv`，1,476 s）**峰一样是 6,025 MB**、maxWS 5,872、
python 侧仍只有 41 MB ⇒ 这条曲线与链长无关，"≥6 GB 空闲"是硬门槛。

父进程 python 只有 36~41 MB。判读：`.raw` 是 1.53 GB fp16，爬坡增的 3.44 GB ≈ 它的 fp32 宽度（3.06 GB）＋余量
⇒ **Host 后端把参数整体搬进 RAM 并拓宽成 fp32，不是流式**（B：量级对上了，没读实现）。收尾那约 1.8 GB 的瞬时峰**未归因**。
实操含义：本机这条路的门槛不是磁盘是内存，**起跑前要留有 ≥6 GB 空闲**；且它一步吃满 16 核，别和她那批 ASR／直播链挤同一时刻。

### 7.2 板子侧：驱动自己要多少（A，逐行读 `qwen2_infer_decode_only_axi.py`）

| 项 | Qwen2-0.5B | **Qwen3-0.6B** | 出处 |
|---|---|---|---|
| `kv_cache` 常驻 | 48×[1,2,512,64] fp16 = 6 MiB | 56×[1,8,512,128] fp16 = **56 MiB** | `:272 _prepare_kv_cache` |
| 喂进去的输入拷贝 | 6 MiB | **56 MiB** | `:298 Tensor(v.astype(np.float16), …)`，`astype` 默认 `copy=True` ⇒ 无条件再拷一份 |
| 读回来的输出拷贝 | 6 MiB | **56 MiB** ＋ logits 0.6 MiB | `:171 Tensor2Numpy` 里 `np.zeros(shape)` 新建 |
| **三份同时存活** | ≈18 MiB | **≈170 MiB** | 上三行之和 |
| `import icraft+xir+pyrtutils` | — | **46.5 MiB RSS／217.7 MiB VmSize** | A，板上 10-11 `bisect.log`：`STEP0 OK 2.4s 222920 kB 47640 kB 47640 kB` |
| `Tokenizer.from_file`（7.0 MB 的 tokenizer.json） | — | **≈30 MiB** | B：本机 tokenizers 0.22.2 实测 18→51 MB；板上是 0.13.3，没重测 |
| **驱动侧合计** | ≈95 MiB | **≈245 MiB 匿名页** | |

权重那 1.6 GB 走 `lazyLoadParamsFromFile`（`:207`），**驻不驻留是这件事唯一的未知项**，只有真跑一次才知道。
两条反证支持"不驻留"（B）：1.6 GB > 整板 993 MB，驻留则根本起不来；厂商给 30TAI 报 4.68 tok/s＝他们确实在这块板上跑通过。
若真驻留 ⇒ 一定 OOM。

### 7.3 OOM 会怎样：两种死法，症状和处理完全不同

| | ① 常规 oom_kill | ② 换页撞坏 DMA（可疑，非 OOM） |
|---|---|---|
| 触发 | 非 CMA free 撞 `min_free_kbytes`＝22,528 kB（A，10-12 板上 `cat /proc/sys/vm/min_free_kbytes`），且回收与换页都拿不出页 | 缓冲页被换出后物理地址变了，而运行时按 `/dev/mem` 物理地址（`npu=0x40000000&dma=0x80000000`）编程硬件，或它压根从 CMA 拿页而 CMA 不够 |
| 症状 | 内核 SIGKILL 掉 RSS 最大的那个；**板子活着**，SSH 照常，`dmesg` 留 `oom-kill`／`Killed process` | **网络与串口同时零输出**，没有 printk，只能断电 |
| 谁被杀 | 不一定是我们：5.4 内核 oom_score 线性，另一个会话那个 **387 MiB 的 ASR python** 比我们 245 MiB 的排名靠前 ⇒ 我们的 run 大概率先被换页（swappiness=10），真正挨刀的是她那条链 | — |
| 证据 | 历史 12 次都死在"非 CMA free 撞 min"这条线上；**本次开机（uptime 25,776 s，dmesg 完整从 0.000000 起）零条 OOM 记录**，这条负断言这次成立（A） | 10-11 20:17 第一次给 Qwen2 点火＝板子从网络消失、COM6 回车 0 字节。**归因已换、这条要公开更正**：②这个"换页撞坏 DMA"的假设**不是那四次挂死的原因**——10-13 定位、10-14 实测证实的是**板上位流不含 NPU**（同一支 `qwen_bisect.py 1` 在 `aca4612b…` 位流下 **1.4 s 通过**，串口全程有 printk）。②作为一种**死法仍然成立**（症状确实与①不同），只是**没有实例归到它头上**；10-11／10-12／10-13／10-13 四次全部归位流那条（A） |

**处置口径（按代价从小到大）**：
1. 换页这条风险有便宜的堵法：跑之前 `swapoff -a`（此刻 SwapUsed 只有 5 MiB，代价极低、可逆），或给驱动 `mlockall`。作用是把②换成①——宁可被 SIGKILL 留下现场，也不要静默搬错页。动板子全局状态，要不要做由她定。**10-14 校准**：真跑那轮**没做 `swapoff`、没 `mlockall`**，`SwapTotal` 1,048,572 kB 而采样期间 `SwapFree` 只在 1,048,060～1,048,316 kB 之间动（＝**最多用掉 512 kB**，`mem_watch.log` 1 s 采样），跑完板子照常可达 ⇒ 这条降为"可选保险"，不再是点火的先决条件。
2. 让路：把 `max_decode_length` 512→128，三份 KV 从 170→43 MiB（改 `_prepare_kv_cache` 的 `seq_len` 和回喂张量形状）。代价＝上下文只剩 128 token，厂商 `max_tokens_length` 也是这个量级。
3. 省掉两份拷贝：`:298` 的 `astype(..., copy=False)`（缓存本来就是 fp16，拷了个寂寞）＋present 直接当下一步 past，别中间数组。驱动侧从 245→大约 120 MiB。
4. 清场跑：先停另一个会话的 ASR／直播链再起 Qwen3，拿回它那 387 MiB 与 CMA。这条要她点头，我不碰对方进程。
5. ~~**这条是 D**：不知道它要不要，要多少~~ ⇒ **10-14 有答案了：要，一次约 122 MB（A）**。厂商 Qwen2 件真跑一轮时 `CmaFree` 从 **130,784 kB**（起跑前，本次开机 mali/MVX 占走之后的余额）掉到最低 **8,860 kB**，STEP4 给 NPU 编程那一刻先掉到 104,580。⇒ **上板门禁要先看 `CmaFree` 而不是 `MemAvailable`**，且**不能与另一条会话的直播链同窗**（那条链也吃 CMA，10-12 那次实测余额只剩 15 MiB＝分不到的那档）。注意 `CmaFree` 会自己漂：STEP4 结束后 8 min 的采样里回到 **123,416 kB**，而她这次提问时再读是 90,404 kB，**没回到 130,784、也没归因**（另一会话的链起停过，不写"泄漏"）。
6. **10-14 实测：这套账不用减了**——厂商 Qwen2 件（驱动侧 ≈95 MiB 匿名页）真跑一轮 `MemAvailable` 最低 **386,740 kB、零 OOM、`VmHWM` 673 MB**，`lazyLoadParamsFromFile` 读完 1.22 GiB 权重 RSS 只 546 MB ⇒ **惰性加载确实不整颗驻 RAM**。Qwen3 驱动侧 ≈245 MiB 比它多 150 MiB，照这条曲线外推还剩 ≈236 MB 余量（**B：外推，不是实测**） ⇒ 上面 1～4 条（`swapoff`／砍 `max_decode_length`／省拷贝／清场）**从"可能要办"降为"不必先办"**，只有 CMA 那条（第 5）是真门槛。**10-28 公开更正本条后半**：那句"1～4 条降为不必先办"是按 Qwen2 那轮的外推做的，而 **Qwen3 自己的四档预检（10-14，`apply` 75.1 s、连生成都没跑）实测就把两项同时压到个位数 MB**——5 s 心跳记到 `CmaFree` 最低 **80 kB**（lazy-load 窗口）、`MemAvailable` 最低 **5,020 kB**（apply 窗口，同窗 `CmaFree` 2,440 kB，台账 `#213`）。⇒ 点火前 1～4 条要重新拿出来判（至少第 4 条清场——做不做由她定），第 5 条的"CMA 是门槛"从推断升成实测。那 130 MB CMA 的归属当场没取证（s0～s2 同一步 `CmaFree` 恒 130,776 不动，只有 s3 掉下去），别写成运行时的固有开销。

## 相关页面

[[Qwen3按厂商Qwen2配方迁移]] · [[NPU调用链]] · [[位流构建与SDI信号检测]] · [[BOOTbin位流替换手术]] · [[板端我方代码与产物台账]] · [[板卡镜像实测取证]]
