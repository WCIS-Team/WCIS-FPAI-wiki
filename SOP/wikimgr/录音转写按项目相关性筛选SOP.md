---
tags: [SOP]
updated: 2026-11-03
---

# 录音转写按项目相关性筛选SOP

> **这是"把一堆已分类的录音转写，按是否与某个项目相关筛出来、逐段汇成一页"的照抄规程。**
>
> 一句话：**关键词粗筛 ∪ bge 零样本粗筛 → 取并集 → 多段打包交给子 agent（并发上限 3）细筛 → 相关段逐段原文复制进 `wiki/todo/record.md`。**
>
> 本规程的成品示例＝[[record]]（`wiki/todo/record.md`）。脚本正本都在 `workenv\录音筛选_recordmd\`（`workenv/` 属硬规矩排除区，不入库、不清理）。

---

## 一、什么时候用

同一批录音转写已经按 9 类（对话／待办／想法／未分类／疑问_问答集／观点／记录／身体／驳论）分好，但你要从里面**只挑出跟某个具体项目（本例 WCIS-FPAI）有关的段落**，汇成一页可查的东西。人眼看几百段看不完，就按本页跑。

## 二、输入与边界（照抄前先确认）

- **分类目录**（例：`S:\sound_recorder_分类_20261027_195348\`）：每类一个文件。
  - txt 文段结构：`[来源] …` 起头、空行分隔、`title:<录音名>` 行给录音名、其后是正文。
  - 问答集结构：`## n. <主题>` 起头，每段含 `**Q**…` / `**A**…`。
- **只扫清单点名的文件**。带 `.bak-<日期>` 的备份、`疑问.txt`（问答集是它的答案版）、以及名字对不上的目录（如 `S:\asr\txt\sound_recorder_parts\` 里是 `01_问题.md` 等）**一律不扫**——先 `ls` 核一遍名字。
- 编码：本批是 `utf-8-sig`；脚本要带 `utf-8`→`gb18030` 兜底。

## 三、怎么跑（按顺序，脚本都在 `workenv\录音筛选_recordmd\`）

```powershell
cd S:\work\WCIS\workenv\录音筛选_recordmd
```

1. **切分文段**：`python -X utf8 split_segments.py` → 生成 `segments/seg_0001..NNNN.txt` ＋ `manifest.json`（每段→原文件／文段号／录音名／字数）。再 `python -X utf8 renumber.py` 按顺序重编号。
2. **粗筛 A（关键词）**：`python -X utf8 pre_filter.py` → `candidates.json`。关键词取强项目词（`icraft/npu/fpga/vpu/yolo/悟净/fmql/校机/交叉编译/vivado/vitis/petalinux/verilog/设备树/内核/驱动/复旦/开发板/部署/wiki/sdi/摄像头/烧录…`）。关键词只是粗网，**误报留给细筛剔**。
3. **粗筛 B（bge 零样本）**：`python -X utf8 bge_zero_shot.py` → `bge_scores.json`（每段一个 `rel` 分）。**用法与坑见第四节**。
4. **取并集＋打包**：`python -X utf8 union_bundle.py 0.12` → 候选＝关键词 ∪ `bge.rel≥0.12`；按 **≤12 段／≤14K 字／单段正文 ≤3500 字（问答答案 ≤500 字）** 打包成 `bundles/batch_NNN.txt` ＋ `bundles.json`。用 `measure_bundles.py` 复核每批字数与最大段。
5. **细筛（子 agent，并发上限 3）**：用 `workflow` 工具，**每批一个子 agent**，读 `batch_NNN.txt`、逐段判 `related`，返回 `{"verdicts":[{"seg":"seg_XXXX","related":bool,"reason":"一句依据"}]}`。给 agent 的口径要写死（见第五节），并**核对每批返回条数 == 批内段数**。
6. **汇总＋装配**：相关段号写进 `ai_results.json` → `python -X utf8 build_verdicts.py`（扩成全 491 段 `verdicts.json`，非候选＝不相关）→ `python -X utf8 assemble_recordmd.py <verdicts.json>` → 生成 `wiki/todo/record.md`（按来源文件分组；段头＝`### 文段 <号> · <录音名>`；去管线元数据行、保留 `[TLDR]` 摘要）。
7. **校验**：`python -X utf8 wiki/format/check-md.py`（该页无报错）；脚本自检 BOM／CRLF／` [[ ` 出现次数全为 0、H1 = `record`。

## 四、bge 零样本的坑（最容易翻车，必读）

- 模型＝`MoritzLaurer/bge-m3-zeroshot-v2.0`，本地缓存 `S:\asr\model\bge-m3-zeroshot-v2.0\cache`（设 `HF_HOME` 指过去即不重新下载；桌面入口 `笔记分类.bat`→`client.py` 是**固定 9 类的队列服务，不支持自定义标签**，所以另写 `bge_zero_shot.py` 直接调 `transformers.pipeline("zero-shot-classification")`）。
- **必须用英文 NLI 模板 + 英文标签**：`hypothesis_template="This note is a {}."`、标签写成英文整句。用中文标签／中文模板会让**所有分数贴地（0.01~0.06）完全失效**（v2.0 是按英文 NLI 训的）。
- 用 **dGPU（`device=0`，4060 Laptop），不要 iGPU**；长文本按句切 ~700 字块、取 `max`（任一块相关即相关）。
- 它对"陈述式"项目内容能打到 0.2~0.3，对"提问式"（如"Icraft 报错怎么查"）偏弱（<0.1）——**所以 bge 只当补充网、阈值放宽到 0.12，误报交给细筛清**；提问式段靠关键词（icraft/npu…）兜住。

## 五、细筛给子 agent 的口径（写死，别含糊）

- 项目背景（贴进 prompt）：复旦微 FPAI／FMQL30TAI（悟净）开发板边缘 AI 比赛——PS=ARM Linux、PL=FPGA、NPU（iCraft 工具链量化部署，YOLO 等）、VPU；涉及交叉编译、Vivado/Verilog/设备树/内核与驱动、SDI/摄像头/视频链路、板端服务调试、项目 wiki 建设、组队分工、比赛报名/外设采购/报告/答辩。
- `related=true`：任一段话题明确属于上述项目（工作/计划/问题/想法/吐槽/事务都算）；纯技术话题（嵌入式/FPGA/NPU/AI 模型/Linux/硬件/编程）即使泛化也算。
- `related=false`：纯个人生活（游戏电竞、宿舍、饮食、健康、美容、情感、日常闲谈）、与项目无关的科普/医学/影视/政治/求职闲聊、空内容。
- **反例清单要逐类点名**（刘海、多巴胺、香皂、键盘维修、夜神月、路由器借流量、三坑女装、阿根廷化、珍珠港…）——即使文里出现"AI/模型/代码"等词，只要话题本身无关，一律 false。

## 六、判据（怎么算跑过了）

- 切分总数＝各文件文段数之和（本例 491）。
- **细筛每批返回条数 == 批内段数**（覆盖齐、无漏无重）。
- `record.md`：H1＝`record`、CRLF＝0、BOM＝无、`[[`＝0、`check-md.py` 对该页无报错。
- **TLDR-only 段数＝0**：逐段查有无正文行；只有 `[TLDR]` 的按第七节从原件回补后再交付。
- 统计可复现（本例：491 段 → 候选 151 段 → 相关 61 段；按文件 对话 10／待办 6／想法 6／未分类 0／问答集 32／观点 2／记录 5）。
- **质量边界**：关键词粗筛会漏掉 ASR 听错的项目词（如 FPGA→fpg、板子→版子）；要更高召回就降 `union_bundle.py` 的 bge 阈值或补关键词，再重跑第 4~6 步。

## 七、坑与注意

- **每批不仅要看段数，还要看字数**（硬要求）：≤12 段 / ≤14K 字 / 单段正文 ≤3500 字；大问答段单独控，别让单个 batch 撑到几十 KB。
- `.bak-<日期>`、`疑问.txt`、以及清单外目录——不扫。
- **批 A（`A-*`）的块可能只有 `[TLDR]`、没有正文**：2026-11-03 那次重生成时，`S:\asr\cla\batchA_in\` 对 82 件里的 41 件只写了 **16 字节的「交叉引用戳」**（内容甚至是另一个录音名），复核件 `batchA_review_in\` 的 `【录音原文】` 也是空的，最终装配只落了 TLDR。**完整原文在批 A 转写原件 `S:\asr\txt\sound_recorder.txt`**（按 `title:sound_recorder\…wav` 行的录音名切块取；原件是 2026-09-24 的）——装配后必须自检并回补，回补脚本＝`backfill_bodies.py`。本例 61 段里 3 段（`A-040`/`A-041`/`A-008`）属此情况，已回补。
- 分类管线加的 `[评分]/[命中]/[最终]/[来源]/[文段]/title:` 元数据行**不进 record.md**（段头已含文段号＋录音名）；`[TLDR]` 摘要行保留作段首。
- **中间产物与一次性脚本全部留 `workenv\录音筛选_recordmd\`**（段文件、manifest、candidates、bge_scores、bundles、verdicts、各 py）——按硬规矩不删不挪，是下次复跑与调参的入口。

## 相关页面

- 成品示例：[[record]]（`wiki/todo/record.md`）
- bge 分类器的现成入口（固定 9 类，不适用本流程但同一模型）：`S:\asr\model\bge-m3-zeroshot-v2.0\README.md`
