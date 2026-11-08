**eKho 与 SummerTTS** 两个都编译失败，已如实记录、未用替代品冒充。eKho 是 Linux autotools 工程，Windows 下需要 NSIS+VS 工程且运行依赖 festival/portaudio/espeak-ng，mingw 环境 configure 不出二进制。SummerTTS 源码和模型 .bin 齐全，但内置旧版 glog/gflags 在 Windows 下依赖 Linux 专用头文件，项目自述仅 Ubuntu 测试过。两者均无二进制，故无实测数值、无音频，失败原因链已写入 ekho.json/summertts.json 和报告失败记录段。若校机后续装完整 WSL 类 Linux 环境可再试。

| 模型             | 样本             | 采样率    | 语言范围 |
| -------------- | -------------- | ------ | ---- |
| melo（ONNX）     | zh×2 en×1 mx×2 | 44.1k  | 中英混语 |
| melotts（torch） | zh×2 en×1 mx×2 | 44.1k  | 中英混语 |
| chattts        | zh×2 en×1 mx×2 | 24k    | 中英混语 |
| piper_zh       | zh×3           | 22.05k | 纯中文  |
| aishell3       | zh×3           | 8k     | 纯中文  |
| kokoro         | zh×3           | 24k    | 纯中文  |
| piper en       | en×3           | 22.05k | 纯英文  |
| vctk           | en×3           | 22.05k | 纯英文  |

