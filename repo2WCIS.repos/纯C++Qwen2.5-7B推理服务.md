# 07 · llm_frontend_cpp：纯 C++ 的 Qwen2.5-7B NPU 推理服务 + Agent Demo

> 一句话：**一个 C++17/20 二进制，把 Qwen2.5-7B-AWQ 跑在 icraft WL170（卧龙）NPU 上，运行时零 Python，自带一个手写的 OpenAI 兼容 HTTP/SSE 服务，外加一个单轮 agent demo。**
>
> 本文是对 `repos/official/demo/llm_frontend_cpp` 的解读，清点于 **2026-11-02**（分支 `v3.38.0`，HEAD `6d31d11`，2026-07-30）。凡标「自述」的读数来自该仓 README/AGENTS.md，**本轮没有在板上复核**；标「已核」的是本轮直接读代码/配置得到的。

---

## 1. 来源与取证边界

| 项 | 实况（2026-11-02 实测） |
|---|---|
| 路径 | `repos/official/demo/llm_frontend_cpp`（与 `03_图像分类部署示例工程 image_cls_resnet18`、`Icraft-ModelZoo-yolov5` 同级） |
| 体积 | 18 MB（**不含模型权重**；权重约 15 GB，在板卡侧，README 明写不在仓内） |
| remote | `https://www.modelscope.cn/RoxyGrey/llm_frontend_cpp.git` |
| 分支／提交 | 检出 `v3.38.0`；另有 `master`（`origin/HEAD`）、`main`；提交区间 2026-07-08 → 2026-07-30 |
| 提交作者 | `llm_frontend dev <dev@local>`（本地化署名，无真人/组织信息） |
| 构建目标 | `qwen_frontend`（`CMakeLists.txt:2`），三套分支：MSVC x64 文本工具 / aarch64 交叉编译 / Host 后端纯文本 |
| 语言标准 | Windows/MSVC 用 C++17（`/utf-8`），aarch64 用 C++20（`AGENTS.md:103`） |

**三条边界，引用前必须记住：**

1. **它不"官方"**。「官方」这个归类是**推断**，不是事实：仓里没有任何厂商署名、版本号或 FMSH 发布包特征，能佐证的只有两处环境痕迹——构建机账号 `fmsh@192.168.28.128`、服务板 `192.168.125.201`（root 免密）。这两台都**不是**我方 113 板，也不是校机。⇒ 当作「厂商侧人员用私人 ModelScope 号发的工程」看，别当厂商发行件引。
2. **它不能脱离那块板跑**。完整推理需要 WL170 NPU + 板载权重；Windows 上只有 `--text-only` 那条路（tokenizer/前端工具）可跑，NPU runner 会被编成 `qwen7b_wl170_runner_stub.cpp` 直接抛 `WL170 runtime is unavailable in this build`。
3. **本机 git 有坑**：`config/qwen25_tokenizer.json`（7,031,645 B）走 git-lfs，本机 lfs filter 起不来，对该仓跑 `git status` 会以 `fatal: config/qwen25_tokenizer.json: clean filter 'lfs' failed` 失败。要动这个仓的版本控制，先处理 lfs。

---

## 2. 代码地图

`src/` 共 **8,259 行**（其中 `src/text/unicode_data.cpp` 一份就占 5,197 行，是 Unicode 数据表，不承载逻辑）：

| 目录 | 行数 | 职责 |
|---|---|---|
| `src/text/` | 6,242 | 自写 BPE tokenizer（直读 HF `tokenizer.json`）、ChatML 模板、prompt 编码、unicode |
| `src/server/` | 677 | 手写 HTTP/SSE：`/v1/chat/completions` + `/v1/responses`，原生 socket，**不用 httplib/crow/boost** |
| `src/runner/` | 405 | `IModelRunner` 接口 + `qwen7b_wl170_runner`（NPU 实现，PIMPL）+ Windows 用 stub |
| `src/app/` | 267 | `main.cpp`：`--text-only` / 交互 / `--serve`（`--model`、`--host`、`--port`、`--api-key`） |
| `src/service/` | 216 | `ModelService`：上下文级联裁剪、tools 门控、推理调度、流式回调 |
| `src/model/` | 199 | `ModelSpec`（JSON 配置加载）、模型发现 |
| `src/generation/` | 161 | `Generator`：prefill+decode 循环、EOS 检测、超长 prompt 硬夹 |
| `src/conversation/` | 92 | 多轮对话容器、消息体 |

外围：

| 目录 | 内容 |
|---|---|
| `config/` | 7 份配置：`qwen2_5_7b.json`(1171 B)、`_128`(1174)、`_512`(1219)、`_1k`(1223)、`qwen2_0.5b{,_board}.json`(847/868)，加 7 MB 的 `qwen25_tokenizer.json` |
| `modelzoo_utils/` | icraft SDK 头 14 件 `.hpp`（`et_device.hpp`、`icraft_utils.hpp`、`PicPre.hpp`、`NetInfo.hpp`…）＋ `pyrtutils/` 的 Python 参考实现 10 件（**仅作对照，不进运行时**）＋ 1891 行的 `C++_API_reference.md` |
| `demo/` | `agent_demo.py`（**只用 stdlib**：json/subprocess/sys/urllib）＋ `tasks.md`（实测可用话术）＋ `README.md` |
| `tools/` | `align_vs_python.py`、`align_post_vs_python.py`（tokenizer/采样对齐）、`qwen7b_1k_{cli,server}.py`、`test_2round_decode.py` |
| `third_party/` | vendored `nlohmann/json.hpp` |

---

## 3. 请求链路与四条硬契约

```
HTTP / CLI
  → OpenAiServer              /v1/chat/completions、/v1/responses、SSE 全生命周期
  → ModelService.complete     上下文级联裁剪 + tools 门控 + 编码
     → PromptEncoder          ITokenizer + IChatTemplate → token ids
     → Generator              prefill + decode 循环 + 采样 + EOS
        → IModelRunner        Qwen7BWl170Runner（icraft session.forward + KV 管理）
```

四条契约（都已核，行号在 `src/` 下）：

| 契约 | 位置 | 要点 |
|---|---|---|
| `IModelRunner` 四方法 | `src/runner/model_runner.h` | `init() / reset() / prefill(ids) / decode(token,pos) → logits`，NPU 实现全在这层，上层不碰 SDK |
| 上下文级联裁剪 | `src/service/model_service.cpp:27-131` | 超长时依次丢：旧对话轮次 → system/developer 消息（>500 字符换 80 token 精简提示词）→ 截断用户输入，保证小上下文也**不返 400** |
| 硬夹而非抛错 | `src/generation/generator.cpp:20-37` | `hard_floor = max(1, max_context_length - 8)`，超长 prompt 从尾部裁到 floor 后继续跑 |
| 路径双兼容 | `src/server/openai_server.cpp` | 同时接 `/v1/*` 与 `/*`（CC Switch 转发时会把 `/v1` 前缀去掉）；`developer` 角色映射为 `system` |

---

## 4. 三档上下文配置（配置差异已核）

上下文长度是**编译计算图时固定的属性**，进程内换不了；换档＝换一份图 + 换一份 config。

| 档 | 图路径 | `max_context_length` | `max_new_tokens` | `system_prompt` | 状态（自述） |
|---|---|---|---|---|---|
| 128 | 板端绝对路径 `/mnt/qwen2.5_7b_128_new/Qwen2.5-7B-AWQ-*-WL.{json,raw}` | 128 | 64 | 空 | **最稳、输出质量最好**，默认工作档 |
| 512 | 相对 `model_512/Qwen2.5-7B-AWQ-512x512-*-WL.{json,raw}` | 512 | 256 | Qwen 默认 "You are Qwen, created by Alibaba Cloud…" | 可用，agent demo 用这一档；AWQ 量化质量比 128 差，重复退化常见 |
| 1K | 相对 `model_1k/Qwen2.5-7B-AWQ-1024x1024-*-WL.{json,raw}` | 1024 | 256 | 同上 | **不可用**：图能编、prefill 正常（~10 s），但加载权重的 `session.apply()` 有时卡在 `memcpy` 不返回，无稳定复现规律 |

三档共用同一套模型几何（`config/qwen2_5_7b_128.json`）：`n_layers=28`、`n_kv_heads=4`、`head_dim=128`、`vocab_size=152064`、`eos=[151645]`、`kv=fp16`、`input=fp32`、`sampling.method=greedy`。

⚠ **`qwen2_0.5b.json` / `qwen2_0.5b_board.json` 是遗留配置**：里面有 `"backend_type": "icraft"` 与 `"run_backend": "host"` 两个键，而 `src/model/model_spec.h`（46 行，字段逐个核过）**没有这两个字段**，`src/` 下这两个键名零命中 ⇒ 从没被解析过。别拿它当「厂商也在 Host 上跑 LLM」的证据。

---

## 5. 它宣称做到了什么（逐项落到代码）

### 5.1 纯 C++ 无依赖推理
BPE tokenizer 直读 HF `tokenizer.json`（不需要 `tokenizers`/`transformers`）、ChatML 模板渲染（含 `<|im_start|>` 与 `<tool_call>` 块）、prefill+decode 两段式、KV cache 跨 decode 步骤复用、贪心采样、EOS 检测——全在一个二进制里。依赖只有 nlohmann/json（已 vendor）和 icraft SDK 头。

### 5.2 自研 OpenAI 兼容服务
手写 HTTP/SSE，含上下文自适应裁剪；工具调用提取做了**四层 fallback**（`src/server/openai_server.cpp:261` 起）：`<tool_call>` 标签（含未闭合容错，开放/闭合标签各四种别名 `:318-319`）→ bare JSON 的 `name`/`cmd` → markdown `bash/shell/python` 代码块（`:402-404`）→ Python 代码自动包 `python3 -c`。提取出的工具名统一改写为 `shell_command`（`:361`），并强制 `max_tokens ≥ 256`（`:223`）。

### 5.3 接进 Codex（经 CC Switch）
`instructions` 注入为 system、`developer`→`system`、去重重复 system；把 Codex 11,000+ token 的 developer prompt 换成 ~80 token 精简提示、13 个工具 schema（约 30 KB）换成单一 shell 工具、剥掉 `<environment_context>` 块；Responses SSE 补齐完整事件序列（`created → in_progress → output_item.added → output_text.delta/done → output_item.done → completed`），`id` 前缀 `fc_`、`call_id` 前缀 `call_`。
**但它自己承认端到端 agent 循环没跑通**，对外只宣称单轮 demo 可用。

### 5.4 单轮 agent demo
`demo/agent_demo.py`：`用户一句话 → 模型产出 tool_call → ssh root@192.168.125.201 真跑 → 结果回传 → 模型一句话总结`，全程两次模型调用。客户端另做两层确定性纠错（`echo("hi")`→`print("hi")`、补 `python3 -c` 前缀）。板子地址/API key/模型 id/SSH 用户都在文件顶部常量区。

---

## 6. 局限：自述读数与现象

| 项 | 读数／现象 | 出处 |
|---|---|---|
| decode 速度 | ~0.7 s/token（生成 60 token ≈ 45 s） | README（自述） |
| 服务初始化 | 45–60 s（7B 权重加载到 NPU） | README／AGENTS（自述） |
| 512 档 | `apply` ~60 s、prefill ~4 s、decode ~0.7 s/tok | AGENTS（自述） |
| 1K 档 | `apply` 随机卡 `memcpy`；成功与失败交替 | AGENTS（自述） |
| 采样 | **只有 greedy**，`top-k`/`top-p`/`temperature` 收参但不生效 | README（已核：`ModelSpec` 只有 `sampling_method`/`top_k` 字段，路径仍走贪心） |
| 并发 | 单请求串行，第二个请求排队 | README |
| 工具面 | 实际只有**一个** shell 工具；无文件编辑/搜索/浏览 | README |
| 上下文 | 最高 512；128 最稳 | README |

**最值得记的一条：greedy ⇒ 完全确定性。** 相同 prompt+参数每次输出逐字相同，所以「失败」不是概率事件，而是「这个措辞能不能把模型引到正确路径」。作者据此把演示话术分成了 ✅/❌ 两类（`demo/tasks.md`），并观察到：英文系统提示词 >500 字符会被替换、示例里带嵌套引号（`python3 -c 'print(42)'`）会把 tokenized 序列搞坏、进而连吐 256 个 `!` 到上限。

其余现象：shell/Python 函数混淆（`echo("hi")`）、漏 `python3 -c` 前缀、措辞敏感（`Write…then run it.` vs `write…and run it` 结果完全不同）、复述 `<tools>` 定义后直接 EOS、输出 markdown 代码块而非 `<tool_call>`、bare JSON 被 EOS 截断。

---

## 7. 代码与自述不一致的三处（本轮核出来的）

这三处是**引用这个仓时最容易踩的坑**，都对着原文核过：

1. **`AGENTS.md:26` 与它自己的代码矛盾。** AGENTS.md 写「Session 必须用 `getICluster(0)` 绑定设备，这是 load-bearing；用裸 `WL170Device` + 两参 `forward` 会导致 decode logits 永不 ready」。而代码 `src/runner/qwen7b_wl170_runner.cpp:111-125` 的做法**正好相反**，注释说 `getICluster(0)` 会让 1K prefill 在 `check_op` 里忙等（NPU `layerCount` 不推进），裸设备才能让 prefill 跑完。⇒ **以代码为准**，别引 AGENTS.md 那句。
2. **tools 定义是「无条件清空」，不是「体积大才丢」。** README 局限 4 说「客户端 tools 总体积较大时服务端会丢弃」，AGENTS.md 说「`max_context_length < 512` 时丢弃」；代码 `src/service/model_service.cpp:127-132` 是 `std::string effective_tools; // always empty — rely on system prompt only`——**任何档位都清空**，只靠系统提示词约束工具行为。
3. **`max_tokens` 下限 256 是无条件的**（`src/server/openai_server.cpp:223`，在请求解析里，**只作用于 HTTP 路径**）：128 档 config 自己写的是 `max_new_tokens: 64`，走 HTTP 请求会被顶到 256；走 CLI 一次性推理则按 config 的 64。

---

## 8. 与我们项目的关系

**（1）我方 wiki 已经引用过它，且引的位置是对的。** `wiki/PL/MOD/官方demo教程与skill审计.md` §7.4 把它按「厂商原文（B）」类证据收进来，逐条记了 7 条运行时约定（三元素 fp32 `dynamic_fm`、输入张量另建 `TensorType` 而不复用图里的、`forward()` 不显式传 outputs、输出逐个 `waitForReady(60s)` 后 `device->reset(1)`、prefill/decode 两 Session 共用一次 `openDevice`、`disableOcmOptimize()`＋`enableTimeProfile(false)`、用裸 `WL170Device`）。**这 7 条与当前代码逐条对得上**（`src/runner/qwen7b_wl170_runner.cpp:108-131`），**正本在那页，此处不复制**——只补上面第 7 节那三条代码侧更正。

**（2）它是目前盘上唯一一份「LLM 怎么上 WL170 板」的可读完整实现。** 对我方 LLM 线（`wiki/PL/MOD/llm/`）的价值集中在：prefill/decode 双 Session 的组织方式、KV cache 放在 host 侧的分配与复用、`dynamic_fm` 三元素的逐 step 递增、输入张量不复用图类型（图类型带 `@chunk` 内存型会把普通 Host 张量当用户 chunk）、`forward` 不传 outputs（传了会超时）、`session.apply()` 才是加载权重那一步（也是 1K 档唯一不稳的那一步）。

**（3）它不能当我方"能做 LLM 服务"的证据。** 服务端能力（OpenAI 兼容、SSE、裁剪、容错提取）是真的、可读的；但**模型侧效果很差**（512 上下文 + 7B-AWQ + 贪心，工具调用靠话术挑），**Codex 多轮循环没跑通**，**只有一块板、一次一个请求**。对外表述时按「工程可行性验证」讲，别按「可用的端侧 agent」讲。

---

## 9. 取证命令（可复现）

```bash
cd S:/work/WCIS/repos/official/demo/llm_frontend_cpp

git remote -v; git branch --show-current; git log --format='%h %ad %s' --date=short -3
du -sh .; find src -type f | xargs wc -l | tail -1

# 三档配置差异
diff config/qwen2_5_7b_128.json config/qwen2_5_7b_512.json
diff config/qwen2_5_7b_512.json config/qwen2_5_7b_1k.json

# 第 7 节那三条更正
sed -n '108,131p' src/runner/qwen7b_wl170_runner.cpp   # 设备选择注释 vs AGENTS.md:26
rg -n 'effective_tools|always empty' src/service/model_service.cpp
rg -n 'max_new_tokens < 256' src/server/openai_server.cpp
rg -n 'backend_type|run_backend' config/qwen2_0.5b.json src/model/model_spec.h  # 后者零命中
```

---

## 10. 小结

这个工程的价值不在「效果」，在**结构**：它把「LLM 上 NPU 板」这件事拆成了四层可替换的边界（text / generation / runner / server），每层的契约都用代码写死，所以哪怕模型效果很差、Codex 循环跑不通，每一层的"为什么这样做"仍然读得出来——`dynamic_fm` 三元素、KV 在 host、输入张量另建类型、`forward` 不传 outputs，这些是硬件逼出来的约束，换成任何模型都成立。

它的可信度也来自同一处：README 有一节专门写「局限性（详细现象描述）」，**只记现象不猜根因**，并把 demo 话术按实测分成必成/必败两类。这种"自证边界"的写法，比它宣称做到了什么更有参考价值——**跟我方 `wiki/PL/MOD/官方demo教程与skill审计.md` 那套证据等级纪律是一路货**。
