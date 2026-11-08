## llama.cpp / GGUF 运行时（官方主推轻量零Python路线）

SenseVoice / Paraformer / Fun‑ASR‑Nano 都有预转 GGUF 权重，走 ggml 推理栈，脱离 PyTorch 和 FunASR Python 框架依赖

- 量化档位 f16 / q8_0 / q5_K_M / q4_K_M。SenseVoiceSmall q8 仅 254MB，Paraformer q8 237MB，精度几乎不变
- 单静态二进制，内置 FSMN‑VAD，直接读 wav mp3 flac，CPU / Vulkan / CUDA 都支持
- 适合边缘盒子、低内存笔记本、不想维护 Python 环境；不支持复杂后处理、自定义热词能力弱于原生 SDK
- 内存收益巨大，去掉 torch 解释器开销 + 权重量化双重节省

## ONNX Runtime C++ / funasr-onnx 导出路线

Paraformer / SenseVoice / FSMN‑VAD / CT‑PUNC 都可以导出 ONNX，支持 QDQ INT8 量化模型 `model_quant.onnx`

- 可以用 C++ 服务或者轻量 Python 封装 funasr-onnx，不再加载完整 funasr+torch 依赖链
- 可控 intra_op / inter_op 线程、内存复用、动态 shape，长音频配合 VAD 分段，避免一次性超大 tensor
- 适合 CPU 高并发服务；算子支持需要校验，流式 Paraformer 有专门的在线 ONNX 版本
- 社区还有 sherpa-onnx 封装好 Fun‑ASR‑Nano ONNX 包，开箱即用 INT8 / FP16 版本

## TensorRT / TensorRT‑LLM 路线（GPU 专用）

SenseVoiceSmall 可以导出 ONNX 再编译 TensorRT plan，FP16 / INT8，搭配 Triton 服务化

- 权重和激活显存都压缩，kernel 融合，显存碎片远少于原生 PyTorch
- 局限：plan 和 GPU 架构绑定，Paraformer 这类非自回归模型适合 TRT，**Paraformer 不能走 vLLM**
- Fun‑ASR‑Nano 属于 LLM‑ASR，走 TensorRT‑LLM 而不是普通 TRT 编码器路径

## vLLM 原生推理（仅限 Fun‑ASR‑Nano / Fun‑ASR‑MLT‑Nano）

这是专门给 LLM 结构的 ASR 设计，**Paraformer、SenseVoice 不支持 vLLM**

- 把编码器和 Qwen3 decoder 拆成 split‑engine，编码器批量前向，decoder 交给 vLLM PagedAttention KV cache 管理，大幅降低并发显存开销
- 权重用 safetensors 单独导出，不走 funasr toolkit 的 generate 链路；支持 OpenAI 兼容接口、热词
- 适合 GPU 批量长音频转写；纯 CPU 不可用，版本锁定 vLLM 0.27.1 附近固定快照

## HuggingFace Transformers 原生加载（绕开 FunASR 框架）

Fun‑ASR‑Nano‑2512‑hf 提供原生 HF checkpoint，直接用 `AutoModelForSpeechSeq2Seq + AutoProcessor`，不需要 import funasr 包

- 只加载模型和 feature extractor，去掉 FunASR 内置 pipeline、VAD、标点、spk 整套重组件，你自己按需拼接 VAD
- 可以配合 `torch_dtype=bfloat16/float16`、`device_map`、bitsandbytes INT4 进一步压内存
- 好处是生态打通，缺点是没有内置流式 chunk cache、没有官方时间戳输出

## 流式 chunk + VAD 分段（属于推理策略，配合任意后端）

不是 runtime，但对内存 OOM 最关键，很多人忽略

- 离线长音频：FSMN‑VAD / Silero VAD 先切语音片段，只送语音段进模型，静音丢弃，`max_single_segment_time` 限制单段上限，避免超长 mel tensor
- 流式 Paraformer：`chunk_size` + 滑动窗口 cache，只保留 encoder/decoder 有限回看历史，不维护整段全局状态；每个流独立 cache，用完释放
- 流式本身不减少权重内存，但控制激活和序列长度，是长音频防 OOM 的标配
