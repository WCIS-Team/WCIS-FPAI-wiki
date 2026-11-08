## funasr
### Python SDK 直接调用

使用 `funasr.AutoModel` 在进程内推理，适合嵌入自研脚本与程序，支持离线文件转写和流式分块输入，是开发调试最常用方式。 可以搭配 PyTorch 在 CPU 或者 GPU 运行，同时支持 VAD 标点说话人分离串联。

### 原生 CLI 命令行

安装包后直接使用 `funasr` 命令，对本地音频批量转写导出 json 字幕等结果，无需额外写代码，适合批量离线处理音频文件。 也支持 hydra 形式的配置式启动。

### OpenAI 兼容 HTTP 服务

通过 `funasr-server` 启动 HTTP 接口，提供 `/v1/audio/transcriptions`，现有 Whisper 调用代码只改地址即可接入，适合后端微服务对接 Agent 工作流。 GPU 场景可搭配 vLLM 后端加速 Fun‑ASR‑Nano，拥有显存调度与更高并发能力，该加速方案不适用于 Paraformer 类非自回归模型。

### WebSocket 流式实时服务

分为 Python WebSocket 服务与 C++ WebSocket 服务，面向麦克风会议字幕通话等低延迟实时场景，支持边上传音频边返回中间识别结果，支持双遍识别模式。 常用模型为 paraformer‑zh‑streaming 搭配 fsmn‑vad。

### ONNX Runtime C++ 原生运行时

模型导出 ONNX，用 C++ 编写推理程序，主打高并发 CPU 部署与嵌入式场景，脱离 Python 依赖，延迟可控，支持离线与流式两路推理。

### GGUF llama.cpp / audio.cpp 轻量化二进制

SenseVoice Paraformer Fun‑ASR‑Nano 均可导出 GGUF 量化模型，提供独立静态二进制程序，无 Python 依赖，适合边缘设备低资源 CPU 环境，自带 VAD 能力。

### Triton + TensorRT 高性能部署

把 SenseVoice 导出 TensorRT engine，接入 Triton Inference Server，面向大规模 GPU 集群高吞吐业务，适合云侧高并发 ASR 服务。

### 容器与编排部署

Docker Compose 用于本地验证小规模服务，Kubernetes 模板用于线上集群托管，支持 GPU 调度持久化模型缓存健康检查等生产能力。

### Transformers 原生加载

直接用 HuggingFace transformers 库加载 Fun‑ASR‑Nano HF 权重，和其它 HF 模型保持一致调用范式，适合已经深度使用 transformers 的项目。

如果你需要，我可以给一份最简 AutoModel 流式示例代码。