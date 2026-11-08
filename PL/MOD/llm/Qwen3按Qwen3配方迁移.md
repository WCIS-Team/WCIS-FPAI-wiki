# Qwen3按Qwen3配方迁移

> **本页回答什么问题**：把 Qwen3 家族 0.6B 档的 instruct 系模型按已验证的 Qwen3 配方完整重跑一遍——校机导出、本机改写＋编译＋mask0 补丁、数值验证——产出**交付线**的干净产物：`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\`（脚本与基准件入库、体积件挡库外）与"要上板"的文件对。**本线不上板**（立项判定 [[状态源与决策记录#D-62 · Qwen3-Instruct 交付线立项：instruct 系＝Qwen3-0.6B 本尊、按路由 SOP 分工重跑收进 repos 子模块、不上板|状态源与决策记录——D-62]]）。
> **判据等级**：A＝本线自己跑出来的原文读数；A₀＝探索线（[[Qwen3按厂商Qwen2配方迁移]]／[[qwen3-0.6b]]，同一颗模型）已实测、本线照抄的判据；B＝厂商文件／官方仓库页直读；C＝推断（标明未实测）。
> **与流程正本的关系**：`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\pipeline.md` 是探索线的流程正本（全部实测数在那里；10-28 自 `workenv\qwen3\` 入进库，旧根那份仍在盘、以库内为正本）；本页是**交付线的 SOP**，只写"这一轮照抄什么、绿在哪里"，原理与历史读数一律链接过去、不复制。
> 相关页：[[Qwen3按厂商Qwen2配方迁移]]、[[qwen3-0.6b]]、[[交叉编译主机路由SOP]]、[[板端我方代码与产物台账]]、[[NPU调用链]]。

## 一、先纠名：Qwen3 的 instruct 系就是不带后缀的 Qwen3-0.6B

（B：官方仓库页直读——[Qwen/Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B)、[ModelScope 同名](https://www.modelscope.cn/models/Qwen/Qwen3-0.6B)、[qwenLM/qwen3](https://github.com/qwenLM/qwen3)、[Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)）

- Qwen3 家族的命名跟 Qwen2 **不是一套**：**`Qwen/Qwen3-0.6B`（2504 发布）本身就是 instruct 系**，带混合思考模式（`/think`／`/no_think` 软开关）；真·底座是 `Qwen3-0.6B-Base`。
- **官方不存在独立的 `Qwen3-0.6B-Instruct` 仓库**；2507 刷新从 4B 档起才拆成 Instruct／Thinking 两支。
- 推论：GGUF 基准线（`benchmark.html` 的 `qwen3_06b_q4km`，requant 源＝官方 `Qwen/Qwen3-0.6B-GGUF`）与 NPU 探索线（`dl_qwen3.py` 下载的 `Qwen/Qwen3-0.6B`）**是同一颗模型**；benchmark 那个 `-Instruct` 标签按"instruct 系"理解成立，她已判不改。我 10-18 曾按 Qwen2 的命名习惯判"NPU 线是 base"，**判反了，作废**（D-62 记录在案）。
- 本页文件名按她的原话保留；页内"Qwen3-Instruct"一律指 `Qwen/Qwen3-0.6B`。

## 二、这条线与探索线（Q3V1）的关系：同模型、新命名空间、收成交付件

- 探索线已经把这颗模型走通到 **`_ZG` 件＋mask0 图级补丁**，全部读数在 [[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]] 与 [[qwen3-0.6b#三、做到哪一步了（10-12）|qwen3-0.6b——三]]。
- 本线**不重推导、不碰探索树**：用全新命名空间 `Q3I`（net_name／fmodel／jr_path 全换新）把同一条配方从头重跑——目的是 ①证整条链可复现、②产出干净的交付件、③把"要上板的文件"收进 `repos/lang/llm/Qwen3-0.6B/`。
- 分工照 [[交叉编译主机路由SOP#一、三台机各自能做到什么（路由的唯一依据）|交叉编译主机路由SOP——一]]：**校机＝权重快照＋导出＋HF 基准；本机＝结构改写＋编译＋Host 前向验证**（校机没有 icraft CLI，模型编译唯一落本机；后端档一律 ZG330）。
- **不上板**：板上驱动的改造（结构参数、喂 3 元素 `token_dynamic_fm`、CMA／位流门禁）不在本线，指针见第六节。

## 三、SOP：阶段 0～7，逐条照抄

> 路径约定（**2026-10-28 现值**）：校机根＝`D:\yzd\WCIS\MOD\qwen3`（快照与 venv 已在位、迁移后实测可用）；本机脚本现役正本＝`S:\work\WCIS\repos\lang\llm\Qwen3-0.6B\`（`compile/` 24 件＋`board/` 8 件＋`patch/` **2 件**）；`S:\work\WCIS\workenv\qwen3\`＝未入库那批（`pipeline.md` 零点名的探路脚本，含 `board\q3_probe.py`；`board\q3_infer_board.py` 已在 10-28 按她"要补"复制成库内第 19 件 `patch\q3_infer_board.py`，workenv 那份是同源的旧副本）留此，10-28 当场未删；盘上该根 10-28 上午 64 件、下午复算 **69 件**（多的 5 件是本轮给台账 `#213` 补的留底 `board\hb_q3_s{0..3}.log`＋`board\run1_1014_headtail.txt`，不是新脚本；"未入库＝根件数−并入 19 件"这笔账的完整算式在库内 `README.md` 状态节，别在这儿再记一份）；本机编译树（数据件）＝`S:\apps\llm\agentwork\qwen3\compile\`（10-28 实测该根与十二个目录都在）；icraft CLI＝`C:\Icraft\CLI v3.39.0`。凭据一条都不出现在本页（口令按 [[状态源与决策记录#D-27 · 凭据单点记账：全库只记一次，其余页面用链接指过去|状态源与决策记录——D-27]] 单点记账，本线也用不到）。
> **10-28 这一批改了什么、没改什么**：命令块里 **5 处**（3 处 `cd`＋2 处 `host_gen.py` 全路径）从 `workenv\qwen3\` 改指库内 `repos\lang\llm\Qwen3-0.6B\compile\`——改的是位置不是内容，那 18 件复制后与 workenv 源件 **md5 逐字节全等 18/18**（10-28 实测）。**本轮没有重跑管线**，所以"在新目录下跑通"属未实测；参数、判据、读数一律沿用 10-18／10-19 的原值，没动。阶段 6 那条 `cp` 花括号列表保留原样（它是 10-18 的历史动作，源就在 workenv）。

### 阶段 0 · 前置检查（校机＋本机，五分钟）

```
# 校机：她的 ASR 批次在不在跑（记账不拦截，门禁已按 D-51 删除）
ssh school-guest "tasklist //FI \"IMAGENAME eq python.exe\" /FO CSV /NH"
# 校机：快照在不在（10-18 迁移后已在 D:\yzd\WCIS\MOD\qwen3）
ssh school-guest "dir D:\yzd\WCIS\MOD\qwen3\Qwen3-0.6B"
# 校机：venv 三件套能不能 import（迁移后实测可用，读数见迁移页开头）
ssh school-guest "cd /d D:\yzd\WCIS\MOD\qwen3 && venv\Scripts\python.exe -c \"import torch,transformers,onnxruntime_genai;print('venv-ok')\""
# 本机：CLI 在不在、版本对不对
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" --version
```

绿的样子：三条校机命令无报错（`venv-ok` 打出来）；`icraft.exe --version` 报 3.39.0。快照不在就先 `ssh school-guest "cd /d D:\yzd\WCIS\MOD\qwen3 && venv\Scripts\python.exe dl_qwen3.py"`（正本 10-28 起在库内 `compile\dl_qwen3.py`，10-18 时写作 workenv；目标路径已写死新根，A₀）。
**Host 前向（阶段 5）起跑前另有一条内存门禁：空闲物理内存 ≥6 GB（A₀：探索线实测峰 6,025 MB）。**

### 阶段 1 · 校机导出（fp16/cuda，QK-Norm 禁融合）

```
# 先把本线要用的脚本正本推过去（库内 compile/ 是正本；校机那份可能是旧根时代的，覆盖成同版）
cd S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile
tar -cf - verify_onnx.py ref_hf.py padfix.py | ssh school-guest "tar -xf - -C D:\yzd\WCIS\MOD\qwen3"
# 导出到全新目录 q3i_fp16_cuda（探索线的 qwen3_fp16_cuda 一个字节都不动）
ssh school-guest "cd /d D:\yzd\WCIS\MOD\qwen3 && venv\Scripts\python.exe -m onnxruntime_genai.models.builder -i D:\yzd\WCIS\MOD\qwen3\Qwen3-0.6B -o D:\yzd\WCIS\MOD\qwen3\q3i_fp16_cuda -p fp16 -e cuda -c D:\yzd\WCIS\MOD\qwen3\cache_dir --extra_options fuse_qk_norm_gqa=false"
# ONNX 侧数值验证（fp16 图跑 ORT CPU EP，对 HF golden）
ssh school-guest "cd /d D:\yzd\WCIS\MOD\qwen3 && venv\Scripts\python.exe verify_onnx.py D:\yzd\WCIS\MOD\qwen3\q3i_fp16_cuda"
```

- **`fuse_qk_norm_gqa=false` 必须带**（A₀：不带则 per-head QK-Norm 被折进 GQA，icraft 没有对应算子）；`-p fp16 -e cpu` 那条会退化成 MHA 路线，不要走（A₀）。
- 绿的样子：`RC=0`；`q3i_fp16_cuda\` 里 `model.onnx`＋`model.onnx.data`＋`genai_config.json`，尺寸与 [[Qwen3按厂商Qwen2配方迁移#二、导出：命令与产物（A，2026-10-12 在校机实跑）|Qwen3按厂商Qwen2配方迁移——二]] 那张表的 B 变体行同值；`verify_onnx.py` 打出的 prefill／decode top-5 与 golden 完全一致。

### 阶段 2 · 取回本机＋导出修约与两处结构改写（顺序不能反）

```
ssh school-guest "tar -cf - -C D:\yzd\WCIS\MOD\qwen3 q3i_fp16_cuda" | tar -xf - -C S:/apps/llm/agentwork/qwen3/compile/fmodel
cd S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile
python vendorize.py --src S:/apps/llm/agentwork/qwen3/compile/fmodel/q3i_fp16_cuda --dst S:/apps/llm/agentwork/qwen3/compile/fmodel/q3i_exported
python meta_variant.py --src S:/apps/llm/agentwork/qwen3/compile/fmodel/q3i_exported --dst q3i_o17sln --opset 17 --sln-ms
python detranspose_embed.py --src S:/apps/llm/agentwork/qwen3/compile/fmodel/q3i_o17sln --dst S:/apps/llm/agentwork/qwen3/compile/fmodel/q3i_v1
python mk_parse_toml.py --name Q3I --fm q3i_v1
```

- **先修约导出件（vendorize.py，10-19 本线实测补上的必经步骤）**。校机原始导出件 ir_version=10、KV 张量 head_dim 是符号维度（`kv_cache_dim`），直接喂 icraft 会让 adapted json 里 56 个 past-KV 输入变负 shape（`[1,8,512,负值]`），阶段 5 的 host_gen 在 seed_past 崩（`negative dimensions are not allowed`，10-19 实测）。`vendorize.py` 一次修三处，ir 10→8、opset→21（meta_variant 随后压到 17）、KV 符号维度替换成 `genai_config.json` 的字面 `head_size`（128），`.data` 复制不重写。
- `meta_variant.py` 做 opset→17、QK-Norm 的 SLN 移进 `com.microsoft` 域（57 颗），`.data` 走硬链接不复制。`detranspose_embed.py` 消掉全图唯一那颗 fp16 `Transpose`（icraft `Unknown dtype 10` 的单点解法），代价是 data 块多存一份转置副本（A₀，机制与字节读数在 [[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]]）。
- **绝不就地追加 `.data`**（A₀，前面阶段的 `.data` 是硬链接，写穿会毁原件）；三个改写的 `--dst` 都是全新目录，保持这样。
- 绿的样子，vendorize 打 `DONE_VENDORIZE` 且 `q3i_exported\model.onnx` 为 247199 bytes（与探索线 `qwen3_exported` 逐字节一致，md5 `07CAF0E39637A1F36914549AE91407BA`）；后两段各打 `DONE`／`out … bytes`；`fmodel\q3i_v1\` 里 `model.onnx`＋`model.onnx.data`（后者比导出件大约 311 MB，A₀）；`compile\Q3I_parse.toml` 生成。

### 阶段 3 · 四段编译（本机，cwd 必须是 compile/）

```
cd S:/apps/llm/agentwork/qwen3/compile
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" parse    Q3I_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" optimize Q3I_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" quantize Q3I_parse.toml
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" adapt    Q3I_parse.toml
```

- 判成败**看日志**有没有 `stepTo faild`／`fatal`，别只看 rc（A₀：icraft fatal 时父进程可能 exit 0）。
- 本线在这一步**不跑** `generate`——未补丁的 `_ZG` 件没有交付价值，直接进阶段 4 出补丁件（探索线留过 `.unpatched` 备份，那是它先跑了五段的历史路径；若手滑先跑了 generate，照探索线第 4b 节先备份再重跑）。
- 绿的样子：四段各 rc=0、日志干净；`jr_path\Q3I\` 出 `Q3I-decoder_{parsed,optimized,quantized,adapted}.{json,raw}` 四对（prefill 那对只到 parse，同探索线）；adapted 的 json 里 HardOp 计数为 0（A₀）。

### 阶段 4 · mask0 补丁＋出补丁件（必经步骤，不是可选项）

**为什么必须**：厂商口径（slot 0 永久全零 pad 且 mask 开着它）在 Qwen3 上实测退化成单字循环，Qwen2 没事——机理与读数见 [[qwen3-0.6b#三、做到哪一步了（10-12）|qwen3-0.6b——三]]；唯一已验证的修法就是图级关掉 slot 0（探索线判定：驱动侧填法全废）。**不带补丁的件＝不可用件。**

```
cd S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile
# 1) 打补丁（第三个参数＝三颗新算子的 compile_target，必须 @zhuget(330)：板端 host 运行时没有 Slice/Concat 转发符号）
python patch_mask0.py S:/apps/llm/agentwork/qwen3/compile/jr_path/Q3I/Q3I-decoder_adapted.json S:/apps/llm/agentwork/qwen3/compile/jr_path/Q3I/Q3I-decoder_adapted_mask0zg.json "@zhuget(330)"
# 2) 写 generate 用 toml（全文见下）
# 3) 出补丁件（约 6 分钟，A₀：342 s）
cd S:/apps/llm/agentwork/qwen3/compile
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" generate Q3I_gen_mask0zg.toml --log_path Q3I_gen_mask0zg_log
# 4) 件完整性自校：两边 md5 必须逐字相等
md5sum jr_path/Q3I/Q3I-decoder_ZG.raw
grep -o "\"params_md5\"[^,]*" jr_path/Q3I/Q3I-decoder_ZG.json
```

> **10-30 出库**：上面 4) 与下面「本机：要上板的文件对」那条 `cp` 吃的 `jr_path/Q3I/Q3I-decoder_ZG.raw`（以及库内 `board/` 那份同名副本）已进回收站——它与 `jr_path/Q3V1/` 那颗 md5 逐字相同，留两份 1.6 GB 没有意义。出库的账与"以后怎么按 `Q3I` 这名重推板"＝`repos\lang\llm\Qwen3-0.6B\pipeline.md` §8 末行，别处不重复。这段命令本身没作废：重跑 3) 的 `generate` 就会把 `.raw` 再生出来；不想重跑（约 6 分钟）就拿正本 `jr_path/Q3V1/Q3V1-decoder_ZG.raw` 复制改名。

`Q3I_gen_mask0zg.toml` 全文（16 行，照探索线 `Q3V1_gen_mask0zg.toml` 逐键换名；`[parse]` 段是 icraft 要的声明、`[generate]` 段指到补丁 json＋未补丁 adapted raw）：

```toml
[parse]
net_name = 'Q3I'
framework = 'onnx'
network = './fmodel/q3i_v1/model.onnx'
network_exdata  = './fmodel/q3i_v1/model.onnx.data'
jr_path = './jr_path/Q3I/' 
max_prompt_length = 32
max_tokens_length = 512
target = 'zhuge'
llm_mode = true
quantized = true

[generate]
json = './jr_path/Q3I//Q3I-decoder_adapted_mask0zg.json'
raw = './jr_path/Q3I//Q3I-decoder_adapted.raw'
jr_path = './jr_path/Q3I/'
```

- **patch_mask0.py 里写死了 Q3V1 的两个定位数（`MASK_V = 180`、`CONSUMER = 4533`）并带断言**：同模型同编译器重跑，op/v_id 大概率原样，但**不保证**。断言失败不是坏事（脚本会拒绝而不是改错图）——那时用 `masktrace.py`／`fmtrace.py`／`dump_mask.py`（10-28 起也在库内 `compile/`）重新定位 CausalMask 输出与它的唯一消费者，改脚本头部两个常数再来。
- 绿的样子：补丁脚本打出 mask 形状与三个新 v_id（记下来，阶段 5 要用）；`generate` 日志无 `fatal`；`Q3I-decoder_ZG.raw` 实算 md5 ＝ `Q3I-decoder_ZG.json` 里的 `params_md5` **逐字相等**（A₀ 判据）；HardOp 计数比探索线未补丁件多 3（A₀：Slice +2／Concat +1）。

### 阶段 5 · 数值验证（语义探针＋25 token 链＋HF 基准）

```
# 1) 单步语义探针：180＝原掩码；VX,VT,VM 换成阶段 4 补丁脚本实际打出的三个新 v_id
cd S:/apps/llm/agentwork/qwen3/compile
python S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile/host_gen.py --json jr_path/Q3I/Q3I-decoder_adapted_mask0zg.json --raw jr_path/Q3I/Q3I-decoder_adapted.raw --work probe_q3i_mask0 --prompt 151644 --max-new 0 --pos-offset 1 --extra-dump "180,VX,VT,VM"
# 2) 25 token 链（11-token chat 前缀＝"你是谁？"，与 padfix 测试集同题，A₀）
python S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile/host_gen.py --json jr_path/Q3I/Q3I-decoder_adapted_mask0zg.json --raw jr_path/Q3I/Q3I-decoder_adapted.raw --work gen_q3i_mask0 --prompt 151644,872,198,105043,100165,11319,151645,198,151644,77091,198 --max-new 25 --pos-offset 1 --dump-format SFB
# 3) 校机：HF fp32/eager 替身跑 mask0 口径 25 步（同模型同前缀）
ssh school-guest "cd /d D:\yzd\WCIS\MOD\qwen3 && venv\Scripts\python.exe padfix.py --model D:\yzd\WCIS\MOD\qwen3\Qwen3-0.6B --variant mask0 --steps 25 --out padfix_mask0_25.json"
```

- 绿的样子：① 探针 dump 里 M′＝`[-inf, 0, -inf×510]`（首格关掉、其余不动，A₀）；② `gen_q3i_mask0\tokens.txt` 的**生成段 25 个 id** 与校机 `padfix_mask0_25.json` 的 ids **逐个全等**（A₀ 判据：探索线 25/25），解码应为通顺中文。
- 喂料口径全照 [[qwen3-0.6b#五、怎么跑（逐条可抄）|qwen3-0.6b——五]]（`--pos-offset 1` 锁死、SFB 拓宽回喂要显式转 fp16、prompt 段 argmax 必须丢）。
- 单步 40～48 s 量级、25 步约 20 分钟（A₀）。更深的 teacher-force 逐步对数可选，姿势同探索线。

### 阶段 6 · 拉回本地，拼装 repos/lang/llm/Qwen3-0.6B

```
# 校机 → 本地：导出件进 export/、基准件进 ref/
ssh school-guest "tar -cf - -C D:\yzd\WCIS\MOD\qwen3 q3i_fp16_cuda" | tar -xf - -C S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/export
ssh school-guest "tar -cf - -C D:\yzd\WCIS\MOD\qwen3 padfix_mask0_25.json" | tar -xf - -C S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/ref
# 校机快照 → board/ 的 tokenizer 配套（config.json 与 tokenizer.json）
ssh school-guest "tar -cf - -C D:\yzd\WCIS\MOD\qwen3\Qwen3-0.6B config.json tokenizer.json" | tar -xf - -C S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/board
# 本机：要上板的文件对（补丁件）
cp -p S:/apps/llm/agentwork/qwen3/compile/jr_path/Q3I/Q3I-decoder_ZG.json S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/board/
# 下一行 10-30 起吃空：那颗 .raw 已出库（口径见本页编译段"10-30 出库"，正本＝jr_path/Q3V1/，复制改名即可）
cp -p S:/apps/llm/agentwork/qwen3/compile/jr_path/Q3I/Q3I-decoder_ZG.raw  S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/board/
# 本机：脚本收进交付目录（workenv 被排除在仓库外，这里给它们唯一的库内副本）＋toml＋链读数
mkdir -p S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile
cp -p S:/work/WCIS/workenv/qwen3/{vendorize,meta_variant,detranspose_embed,mk_parse_toml,patch_mask0,host_gen,verify_onnx,ref_hf,padfix,dl_qwen3}.py S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile/
cp -p S:/apps/llm/agentwork/qwen3/compile/Q3I_parse.toml S:/apps/llm/agentwork/qwen3/compile/Q3I_gen_mask0zg.toml S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/compile/
cp -p S:/apps/llm/agentwork/qwen3/compile/gen_q3i_mask0/tokens.txt S:/apps/llm/agentwork/qwen3/compile/gen_q3i_mask0/steps.json S:/work/WCIS/repos/lang/llm/Qwen3-0.6B/ref/
# 交付清单（Git Bash，照 vpu-live 的 MANIFEST.md5 姿势；10-28 修两处：清单不含自己、md5sum 加 -t）
cd S:/work/WCIS/repos/lang/llm/Qwen3-0.6B && find . -type f ! -name MANIFEST.md5 | sort | xargs md5sum -t > MANIFEST.md5
```

- 目录布局与入库口径见 `repos/lang/llm/Qwen3-0.6B/README.md`：**入库＝README、MANIFEST.md5、脚本、toml、基准与读数 json；库外（`repos/.gitignore` 挡）＝`*.onnx`、`*.onnx.data`、`*.raw`、`*.safetensors` 等体积件**——`Q3I-decoder_ZG.raw` 约 1.6 GB，绝不进 git。
- 五段中间件（parsed／optimized／quantized／adapted 四对）**不进交付目录**，正本留在本机 `compile\jr_path\Q3I\`；要复现按本页阶段 2～4 重跑。
- 权重快照不回传本地：留在校机 `D:\yzd\WCIS\MOD\qwen3\Qwen3-0.6B`（`dl_qwen3.py` 可重下）。
- **10-28 收口又并进来 18 件**（上面那条 `cp` 花括号列表是 10-18 当时的 10 件，按历史原样留着没重写）：`compile/` 从 12 件并到 **24 件**（18 `.py`＋4 `.ps1`＋2 `.toml`）、`board/` 从 4 件并到 **8 件**（多的是板侧 `mem_watch.sh`／`qwen_board.py`／`sercap.ps1`／`ser_probe.ps1`）、新目录 `patch/qwen3_infer_pad3.py`、根级流程正本 `pipeline.md`。逐件路径＋字节＋md5 见库内 `README.md` 与 `MANIFEST.md5`。
- **清单不能有自指行**（10-28 查出）：10-18 版第 2 行给 `MANIFEST.md5` 自己记了 `90e4b3292e01810a310c7cfcbea65cb4`；而按上面改前的那条命令，重定向先截空再 `find`，自指行只可能是空文件的 `d41d8cd98f00b204e9800998ecf8427e`——**两个值不同，那一版不是这条命令直接产出的**（怎么产出的未考）。10-28 起用带 `! -name MANIFEST.md5` 的口径：实算 **45 行覆盖 45 件**（同目录 `find . -type f`＝46 件，多的那件就是清单自己）、`md5sum -c MANIFEST.md5` 报 **45 个 OK、0 个不 OK**、清单本体 **2 675 B**。分目录数＝根 2＋`board/` 8＋`compile/` 24＋`export/q3i_fp16_cuda/` 6＋`patch/` 2＋`ref/` 3（算式 2+8+24+6+2+3＝45）。**`-t` 不是可省的**：Git Bash 的 `md5sum` 默认二进制模式，产出的行是 `<md5> *<路径>`，与库内 10-18 起沿用的文本模式（两个空格）逐行不同——去掉 `-t` 重跑会把 44 行旧值全部改写成带 `*` 的形态（10-28 实测：那版 `git diff --stat` 对 `MANIFEST.md5` 报 89 行变更＝44 删＋45 加；换回 `-t` 后只剩 5 行变更＝3 加＋2 删）。本库内没有 `__pycache__`，所以不用额外排除。

### 阶段 7 · git 提交（先子模块、后主库指针）

```
cd S:/work/WCIS/repos
git status                 # 确认体积件全被挡住、没混进任何凭据
git add -- Qwen3-0.6B-Instruct          # 10-28 改：只 add 本线目录，`git add -A` 会把别条线的未提交件一起扫进来
git commit -m "qwen3-0.6b-instruct: deliverable line (scripts, tomls, refs, patched ZG board pair, manifest)"
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push
cd S:/work/WCIS
git add repos wiki
git commit -m "docs: Qwen3-Instruct migration SOP (D-62); bump repos pointer"
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push
```

主库那笔同时带上本页、[[README]] 目录行与 D-62。**`git status` 里若出现 `*.raw`／`*.onnx.data` 就是 ignore 规则没挡住，停下来先补规则再提交。**

## 四、判据汇总（一表看完"做完"长什么样）

| 阶段 | 主判据 | 不过怎么办 |
|---|---|---|
| 0 前置 | venv-ok＋CLI 3.39.0＋（阶段 5 前）空闲 ≥6 GB | 快照缺就 `dl_qwen3.py`；内存不够别起 Host 前向 |
| 1 导出 | RC=0＋verify top-5 与 golden 一致 | 检查 `fuse_qk_norm_gqa=false` 带没带 |
| 2 改写 | vendorize 的 `DONE_VENDORIZE`＋out 247199 bytes；三个 `--dst` 全新目录；`q3i_v1` 的 data 比导出件大约 311 MB | 别就地追加 `.data`；vendorize→meta_variant→detranspose 顺序别反 |
| 3 编译 | 四段日志无 `stepTo faild`／`fatal`；adapted 无 HardOp | 看日志定位，别信 rc |
| 4 补丁 | 断言通过＋`_ZG.raw` md5＝json 内 `params_md5` | 断言失败＝重定位 180/4533（见阶段 4） |
| 5 验证 | M′ 首格 `-inf`＋生成段 25/25 与 padfix mask0 全等 | 分叉先查喂入序（prompt 段 argmax 必须丢） |
| 6 拼装 | MANIFEST.md5 齐全；`git status` 无体积件 | 补 ignore 规则再提交 |

## 五、已知坑（探索线全踩过，链接过去，别重新发现）

- 导出件**必须先过 `vendorize.py` 再喂 `meta_variant.py`**，校机原始导出件 ir=10 且 KV head_dim 是符号维度，跳过会让 adapted json 的 past-KV 输入变负 shape、阶段 5 host_gen 在 seed_past 崩（10-19 本线实测，修复后与探索线 `qwen3_exported` 逐字节一致）
- 导出：QK-Norm 融合开关、`-e cpu` 退化路——[[Qwen3按厂商Qwen2配方迁移#二、导出：命令与产物（A，2026-10-12 在校机实跑）|Qwen3按厂商Qwen2配方迁移——二]]
- icraft 加载期两道校验（IR 8／opset 17）与 fp16 Transpose 单点——[[Qwen3按厂商Qwen2配方迁移#九、10-12 本机实测：从导出件跑到 adapted 全通，唯一的结构卡点是一个 fp16 Transpose|Qwen3按厂商Qwen2配方迁移——九]]
- 喂料契约（`token_dynamic_fm` 三元素语义、`--pos-offset 1` 锁死、SFB fp32 拓宽）——[[qwen3-0.6b#五、怎么跑（逐条可抄）|qwen3-0.6b——五]]
- prompt 段 argmax 必须丢（驱动序列 bug 的教训）——[[qwen3-0.6b#六、途中修正的事（错过、后来用实测纠正的，别再重新发现一遍）|qwen3-0.6b——六]]
- Host 前向内存账（稳态 4.2 GB／峰 6.0 GB）——[[qwen3-0.6b#七、RAM 账与 OOM 会怎样（10-12 实测＋逐行读码）|qwen3-0.6b——七]]
- tar over ssh 的 Windows 侧姿势、scp 盘符坑——[[交叉编译主机路由SOP#三、SOP（照抄，按顺序）|交叉编译主机路由SOP——三]]

## 六、上板前置（本线不做，只登记指针）

**10-28 现状**：模型件不缺、也不用重编——`/root/qwen3/` 那三件（`Q3V1-decoder_ZG.{json,raw}`＋`config/qwen3/tokenizer.json`，台账 `#208`～`#210`）10-14 就已在板上，同晚四档预检 s1／s2／s3 全 `exit=0`、`apply` 75.1 s ⇒ **件过过 NPU 编程**；但**生成从未执行**（板上没有 Qwen3 驱动）。真要上板时缺的是驱动侧与板侧现场：① 驱动按 Qwen3 结构改（层数／KV head／head_dim／q_proj 宽度，厂商那份是 Qwen2 硬编码）——库内 `patch/q3_infer_board.py` 已做完、**没推上板也没跑过**；② `token_dynamic_fm` 喂 **3 个** fp32（板上 `#196` 那条对 Qwen3 同样成立，本机 Host 后端查不出这个宽度差）——同一件里 `:173`／`:185` 已补；③ 起跑门禁看 `CmaFree` 不看 `MemAvailable`，**10-28 加硬**：Qwen3 预检那一跑连生成都没跑，`CmaFree` 就到过 **80 kB**、`MemAvailable` 到过 **5,020 kB**（台账 `#213`）；④ 位流 md5 门禁。全部口径与实测数在 [[qwen3-0.6b#四、随时能跑吗|qwen3-0.6b——四]] 与流程正本第 7 节；上板当天任何落板文件按 [[板端我方代码与产物台账]] 当场登记。
