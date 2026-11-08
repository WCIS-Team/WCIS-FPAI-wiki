# FunASR / MOSS ASR CPU-only Benchmark（2026-10-19）

依据 `S:\work\WCIS\wiki\SOP\MOD\ASR CPU-only Benchmark SOP.md` 在远程校机执行。被测模型 3 个（FunASR paraformer-large-vad-punc、SenseVoiceSmall、MOSS-Transcribe-Diarize），固定测试集 AISHELL-1 test 确定性抽样 20 条，每模型 3 次独立运行，共 9 轮。

## 1. 测试环境

| 项 | 值 |
|---|---|
| 主机 | 校机 Win11-HV1（Windows 11 虚拟机） |
| CPU | AMD EPYC 9654 96-Core（虚拟机，hypervisor 标志），24 逻辑核可见，实测频率约 2400 MHz |
| CPU 限制 | psutil cpu_affinity 限定 4 逻辑核 + torch.set_num_threads(4)；SOP 的"4 核 1GHz"属宿主机 VM 配置，guest 内无法施加，按实测频率记录 |
| Python | 3.12.15（D:\yzd\models\python312） |
| venv | D:\yzd\llm\funasr\venv |
| FunASR | 1.4.16（git clone https://github.com/modelscope/FunASR + pip install -e .） |
| torch | 2.14.1+cpu（MKL/OpenMP 可用） |
| transformers | 5.20.1 |
| 音频加载 | torchaudio（未装 ffmpeg） |

## 2. 被测模型与来源

| 模型 | 官方仓库 | 本地路径 | 下载工具 | 完整性 |
|---|---|---|---|---|
| paraformer-large-vad-punc | ModelScope `iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch` | D:\yzd\test\models\paraformer-large-vad-punc | modelscope CLI（model.pt 901MB）+ hf CLI 补 seg_dict | model.pt 900702648 B 与 HF 镜像逐字节一致；seg_dict 8287834 B |
| SenseVoiceSmall | ModelScope `iic/SenseVoiceSmall` | D:\yzd\test\models\SenseVoiceSmall | modelscope CLI | 20/20 文件完整（model.pt 936MB） |
| MOSS-Transcribe-Diarize | HuggingFace `OpenMOSS-Team/MOSS-Transcribe-Diarize` | D:\yzd\test\models\MOSS-Transcribe-Diarize | hf CLI | 20/20 文件完整 |

下载约束说明：全部使用各模型提供网站的官方工具（modelscope CLI / hf CLI）。paraformer 的 seg_dict（8.29MB，标点恢复词典）在 ModelScope CDN 上于约 3.0MB 与 6.2MB 两个固定断点反复 `Connection broken: IncompleteRead`，官方 CLI 重试耗尽仍失败；按既定策略改用 HF 上同款镜像 `alextomcat/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch`（model.pt 900702648 B 与官方一致，判定同款）以官方 hf CLI 补齐，校验通过。

## 3. 测试集与固定清单

| 数据集 | SOP 要求 | 可用性 | 说明 |
|---|---|---|---|
| AISHELL-1 test | 必测 | 已用 | 官方 test 7176 条（speech_asr_aishell1_testsets CSV 索引，ModelScope 该 repo 仅索引无音频，实测 include wav 返回 No files to download）；音频取自 HF 分发镜像 `shenyunhang/AISHELL-1`（data_aishell/wav/test，7176 wav） |
| AISHELL-ASR0009-OS1 | 附加 | 即 AISHELL-1 本体 | 官网开源编号即 AISHELL-1（178h 中文普通话库），其 test 已由 AISHELL-1 test 覆盖 |
| WenetSpeech | 附加 | 不可用 | 官方需表单申请密码 + AES 解密，无法即时获取，记为 N/A |
| MagicData-RAMC | 附加 | 不可用 | openslr 123 需学术授权审批，无法即时获取，记为 N/A |
| AISHELL-2023A-EVAL（家居） | 附加 | 不可用 | 官网（opendata.aishelltech.com）下载需人工申请/学术注册审批，无法即时获取，记为 N/A |
| 自建家居指令音频集 | 附加 | 无 | 本机不存在该类数据，记为 N/A |
| NLP-CSmHomComC | 附加 | 文本语料 | 纯文本语料，无音频，不能计算 CER，记为 N/A |

固定测试清单：`results/manifest20.json`，seed=42 确定性抽样 20 条（含 20 个 wav 的 sha256 清单校验，manifest 文件 sha256 见下）。全部 20 个音频已下载至校机 `D:\yzd\test\asr\aishell1\data_aishell\wav\test\`，经官方 huggingface_hub SDK 按清单逐个下载并校验成功（22/22 OK，含 smoke 2 条）。

校机资源布局（2026-10-19 移动后）：测试集 CSV 与音频位于 `D:\yzd\test\asr\`（aishell1_test 与 aishell1），3 个模型位于 `D:\yzd\test\models\`，benchmark 脚本与结果位于 `D:\yzd\test\bench\`（含按新路径重新生成的 manifest20.json，其 sha256 与本节下方记录的基准值不同仅因 audio_root 字段变更，items 清单一致）。原环境目录 `D:\yzd\llm\funasr\` 保留 venv 与 FunASR/MOSS 源码。

manifest20.json sha256：`3f90351b7229c9d7cab13f153a0c97e629f5b460019470b24305725238ed3862`

## 4. 评测方法与口径

- 每轮流程：进程冷启动 → 模型加载 → 首次推理 → 预热 2 条 → 稳态推理全部 20 条；稳态段计入延迟/RTF/吞吐/内存/CPU 统计。
- 延迟：逐条推理墙钟（含预处理/后处理），输出 mean/P50/P95/P99。
- RTF：推理墙钟 / 音频时长（soundfile 实测），mean/P50/P95/P99。
- 吞吐：稳态段成功样本音频总秒数 / 稳态墙钟秒数（实时倍数口径）。
- 内存：psutil RSS 0.5s 采样，启动段均值/峰值、稳态均值、全程峰值。
- CPU：psutil Process.cpu_percent，单核满载计 100%，多线程累计可超 100%；稳态均值/峰值。
- CER/WER：字符级编辑距离 / jieba 词级编辑距离；文本先归一化（移除全部标点与空白，保留汉字/字母/数字，不做简繁与数字转换）再计算；MOSS 输出剥离 `[start][Sxx]` 时间戳/说话人标签，SenseVoice 剥离 `<|...|>` 标签。
- 重复运行：每模型 3 次独立进程运行（run1/2/3），报告均值 ± 标准差。

## 5. 结果汇总

| 模型 | 轮次 | CER% | WER% | 延迟 P50(s) | P95(s) | P99(s) | RTF | 吞吐(音频秒/墙钟秒) | 稳态RSS(MB) | 峰值RSS(MB) | 稳态CPU% | 峰值CPU% | 加载(s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| paraformer | 1 | 1.079 | 1.325 | 0.230 | 0.334 | 0.348 | 0.052 | 18.112 | 1483 | 2268 | 381 | 412 | 9.022 |
| paraformer | 2 | 1.079 | 1.325 | 0.227 | 0.338 | 0.349 | 0.053 | 17.783 | 1484 | 2269 | 374 | 400 | 9.004 |
| paraformer | 3 | 1.079 | 1.325 | 0.232 | 0.347 | 0.363 | 0.054 | 17.547 | 1558 | 2266 | 379 | 400 | 9.075 |
| **paraformer 均值** | 3轮 | 1.079±0.000 | 1.325±0.000 | 0.230±0.003 | 0.340±0.007 | 0.353±0.008 | 0.053±0.001 | 17.814±0.284 | 1508 | 2268 | 378 | 404 | 9 |
| sensevoice | 1 | 8.273 | 6.623 | 0.240 | 0.350 | 0.364 | 0.054 | 17.563 | 1482 | 2277 | 384 | 400 | 8.553 |
| sensevoice | 2 | 8.273 | 6.623 | 0.237 | 0.348 | 0.364 | 0.054 | 17.618 | 1482 | 2164 | 381 | 400 | 8.666 |
| sensevoice | 3 | 8.273 | 6.623 | 0.237 | 0.346 | 0.358 | 0.054 | 17.490 | 1479 | 2259 | 382 | 400 | 8.580 |
| **sensevoice 均值** | 3轮 | 8.273±0.000 | 6.623±0.000 | 0.238±0.001 | 0.348±0.002 | 0.362±0.004 | 0.054±0.000 | 17.557±0.064 | 1481 | 2233 | 382 | 400 | 9 |
| moss | 1 | 1.799 | 1.987 | 7.847 | 10.427 | 10.728 | 1.900 | 0.574 | 4180 | 4230 | 397 | 412 | 6.706 |
| moss | 2 | 1.799 | 1.987 | 7.886 | 10.478 | 10.589 | 1.899 | 0.574 | 4180 | 4230 | 397 | 412 | 6.852 |
| moss | 3 | 1.799 | 1.987 | 7.856 | 10.404 | 10.550 | 1.897 | 0.575 | 4179 | 4229 | 396 | 409 | 6.758 |
| **moss 均值** | 3轮 | 1.799±0.000 | 1.987±0.000 | 7.863±0.021 | 10.436±0.038 | 10.622±0.094 | 1.899±0.002 | 0.574±0.000 | 4180 | 4230 | 397 | 411 | 7 |

要点解读：

- 识别精度（AISHELL-1 test 抽样 20 条）上，paraformer（CER 1.08%）与 MOSS（CER 1.80%）接近，SenseVoiceSmall（CER 8.27%）明显偏弱，其逐条差异多为数字/量词类误识。
- 速度上，paraformer 与 SenseVoiceSmall 同属流式前向模型，延迟 P50 约 0.23s、RTF 约 0.05、吞吐约 17.6-17.8 音频秒/墙钟秒，两者几乎无差别。
- MOSS-Transcribe-Diarize（0.9B 生成式，float32，4 核）延迟 P50 7.86s、RTF 1.90、吞吐仅 0.574，比前两者慢约 34 倍，但换来说话人分离与时间戳输出。
- 内存上 MOSS 稳态约 4.18GB，paraformer/sensevoice 约 1.5GB。
- 三轮运行 CER/WER 完全一致（±0.000，推理确定性），延迟/RTF 波动 <1.5%。

## 6. 逐条结果

完整逐条（每条 wav、时长、延迟、RTF、参考文本、识别文本、S/D/I）见 results/full_*.json 的 per_item 字段；smoke_*.json 为冒烟（2 条）结果。

## 7. 异常与说明

- 无错误、无超时、无空输出（全部 60 次样本成功，fail_rate 0）。
- paraformer 的 WER 曾因输出为 token 级空格分隔文本导致 jieba 词切分虚高（329%），修复为分词前先归一化去空白后重跑，见汇总表最终值。
- "4 核 1GHz"频率限制无法在 guest 内施加，已记录实际频率 2400 MHz 与核数限制方式。
- WenetSpeech / MagicData-RAMC / AISHELL-2023A-EVAL 因授权/申请流程无法即时获取，相关行报告 N/A。

## 8. 复现命令

```bash
# 环境（校机，MSYS2 bash；venv 与源码库仍在 D:\yzd\llm\funasr）
git clone --depth 1 https://github.com/modelscope/FunASR.git
python -m venv venv
venv/Scripts/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
venv/Scripts/pip install -e FunASR
venv/Scripts/pip install psutil
git clone --depth 1 https://github.com/OpenMOSS/MOSS-Transcribe-Diarize.git
venv/Scripts/pip install -e MOSS-Transcribe-Diarize

# 模型下载（官方工具；目标 D:\yzd\test\models）
modelscope download iic/SenseVoiceSmall --local-dir models/SenseVoiceSmall
modelscope download iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch --local-dir models/paraformer-large-vad-punc
hf download OpenMOSS-Team/MOSS-Transcribe-Diarize --local-dir models/MOSS-Transcribe-Diarize
# seg_dict 若断流，从 HF 同款镜像用 hf 工具补齐

# 测试集（D:\yzd\test\asr）
modelscope download modelscope/speech_asr_aishell1_testsets --repo-type dataset --local-dir data/aishell1_test
# 音频经 huggingface_hub SDK 按清单下载（scripts/download_sample.py）

# 生成清单 + 运行（脚本位于 D:\yzd\test\bench）
python make_manifest.py --csv ../asr/aishell1_test/aishell1_test.csv --audio-root ../asr/aishell1/data_aishell --out results/manifest20.json --limit 20 --seed 42
python bench.py --model <paraformer|sensevoice|moss> --model-dir ../models/<dir> --manifest results/manifest20.json --out results/full_<model>_run<N>.json --threads 4 --run-id N
python aggregate.py summary.json summary_table.md results/full_*.json
```
