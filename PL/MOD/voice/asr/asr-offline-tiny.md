| 模型                | 参数    | 中文精度                         | 端侧部署路径                                           |
| ----------------- | ----- | ---------------------------- | ------------------------------------------------ |
| FireRedASR-AED-XS | ~140M | 3.79%（v1 缩放实验，4 个普通话公开集平均）   | 官方无端侧方案，需自己导出                                    |
| SenseVoice-Small  | 234M  | AISHELL-1 约 3.0%（仓库柱状图近似值）   | SenseVoice.cpp（GGML 3/4/5/8-bit 量化）+ sherpa-onnx |
| Paraformer-zh     | 220M  | AISHELL-1 1.95%（FunASR 论文口径） | sherpa-onnx，平台覆盖最广                               |
| Dolphin small.cn  | 0.4B  | 21 个方言/口音集平均 5.74%           | 支持流式、词级时间戳、热词                                    |
| Dolphin base      | 0.1B  | 难方言明显退化（上海话测试 14.25%）        | 同上                                               |
| Whisper-tiny      | 39M   | 中文非主场，明显偏弱                   | whisper.cpp，生态最成熟                                |
| Moonshine Tiny    | 27M   | CER 36.1%，中文不可用              | 自带端侧运行时                                          |
- **要中文精度、能接受 200M 级** → SenseVoice-Small（顺带白拿情感识别和音频事件检测）
- **要平台覆盖最广、最省事** → Paraformer-zh + sherpa-onnx
- **要方言、还要小** → Dolphin small.cn（0.4B）或 base（0.1B）
- **要 40M 以内的极端端侧** → Whisper-tiny 能跑但中文偏弱；Moonshine Tiny 中文直接排除

## 实测对比（AISHELL-1 test 前 500 条，0.816 小时音频，4 线程）
| 模型                               | 参数量  | CER   | 句准率   | 峰值 RSS  | CPU 占用 | RTF   | 加载耗时   |
| -------------------------------- | ---- | ----- | ----- | ------- | ------ | ----- | ------ |
| Paraformer-zh                    | 220M | 2.36% | 76.8% | 2230 MB | 164.7% | 0.115 | 56.5 s |
| Dolphin base.cn                  | 0.1B | 2.31% | 75.6% | 1816 MB | 163.9% | 0.138 | 47.3 s |
| SenseVoice-Small                 | 234M | 2.84% | 72.8% | 2280 MB | 167.2% | 0.144 | 30.1 s |
| streaming-zipformer-small-mobile | 35M  | 5.44% | 57.8% | 141 MB  | 188.0% | 0.192 | 1.41 s |
## streaming-zipformer-small-mobile同量级

| 模型                                | 语言  | CER   | 句准率   | 峰值 RSS | RTF   | 加载     | 推理总耗时  |
| --------------------------------- | --- | ----- | ----- | ------ | ----- | ------ | ------ |
| zf-zh-int8-2025-06-30             | 中   | 2.20% | 77.8% | 286 MB | 0.566 | 3.77 s | 1665 s |
| zf-bilingual-zh-en-2023-02-20     | 中英  | 5.10% | 62.6% | 304 MB | 0.419 | 2.68 s | 1231 s |
| zipformer-small-mobile（你原来的）      | 中英  | 5.44% | 57.8% | 141 MB | 0.192 | 1.41 s | 563 s  |
| x-asr-480ms-zh-en-int8-2026-06-05 | 中英  | 7.16% | 31.6% | 294 MB | 0.456 | 3.71 s | 1339 s |
（作为对照，非流式的三个：Paraformer-zh 2.36%/2230MB、Dolphin base.cn 2.31%/1816MB、SenseVoice-Small 2.84%/2280MB）

## 关键结论：这个量级存在明确的"精度—内存"拐点

把内存往上加，收益非常不均匀：

- 103 MB → 141 MB（+38MB）：CER 14.44% → 5.44%，**收益巨大**
- 141 MB → 286 MB（+145MB）：CER 5.44% → **2.20%**，**这是最划算的一段**
- 286 MB → 1816/2230 MB（+1.5～2GB）：CER 2.20% → 2.31%/2.36%，**几乎没收益，反而略差**

也就是说 **286MB 是这条曲线的拐点**：再往下的省内存模型精度都掉到 4% 以上，再往上加内存换不来精度。`zipformer-zh-int8-2025-06-30` 卡在这个位置上，它同时是这次全部 10 个模型里 CER 最低的——比 2.2GB 的 Paraformer 和 SenseVoice 都低。

**所以推荐就是它**，没有找到同量级更优的。它的实际代价只有两个：RTF 0.566（比 mobile 版慢 3 倍，但仍远快于实时）、加载 3.8s。下载入口：`sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30.tar.bz2`（126MB，int8 ONNX）。


**`zipformer-zh-xlarge-int8-2025-06-30` 没测** 没必要了，太大