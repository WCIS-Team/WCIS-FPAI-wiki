

AISHELL-1 test 抽样 20 条，4 逻辑核 CPU 限制

|模型|CER|WER|延迟 P50|RTF|吞吐 (音频秒 / 墙钟秒)|稳态内存|
|---|---|---|---|---|---|---|
|paraformer-large-vad-punc|1.08%|1.33%|0.23s|0.053|17.8|1.5GB|
|SenseVoiceSmall|8.27%|6.62%|0.24s|0.054|17.6|1.5GB|
|MOSS-Transcribe-Diarize|1.80%|1.99%|7.86s|1.90|0.57|4.2GB|
funasr mod zoo
![[Pasted image 20261108105622.png]]

# 模型权重

## 1. ModelScope 模型仓页面（教程 README 就在这里）

- CAMpplus — [https://www.modelscope.cn/models/AIBS/CAMpplus](https://www.modelscope.cn/models/AIBS/CAMpplus)
- EcapaTDNN — [https://www.modelscope.cn/models/AIBS/EcapaTDNN](https://www.modelscope.cn/models/AIBS/EcapaTDNN)
- ERes2Net — [https://www.modelscope.cn/models/AIBS/ERes2Net](https://www.modelscope.cn/models/AIBS/ERes2Net)
- Res2Net — [https://www.modelscope.cn/models/AIBS/Res2Net](https://www.modelscope.cn/models/AIBS/Res2Net)
- SeResNet — [https://www.modelscope.cn/models/AIBS/SeResNet](https://www.modelscope.cn/models/AIBS/SeResNet)
- TDNN — [https://www.modelscope.cn/models/AIBS/TDNN](https://www.modelscope.cn/models/AIBS/TDNN)

## 2. 真正的迁移部署工程（蜂鸟 mdz，GitLink，含 0_源码 到 5_部署 全流程）

这是比 README 更实质的东西，v3.31.0 分支下每个模型一个工程目录，仅 Res2Net/SeResNet/TDNN 的 ModelScope 卡片是空模板，实际教程只能看这里。

- CAM++ — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/CAM++](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/CAM++)
- EcapaTDNN — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/EcapaTDNN](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/EcapaTDNN)
- ERes2Net — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/ERes2Net](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/ERes2Net)
- Res2Net — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/Res2Net](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/Res2Net)
- ResNetSE — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/ResNetSE](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/ResNetSE)
- TDNN — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/TDNN](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/TDNN)
- SeResNet — [https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/SeResNet](https://www.gitlink.org.cn/spider-mxh/mdz/tree/modelzoo_v3.31.0/pytorch/SeResNet) （注意索引里它是 Flower 花卉图像分类，不是音频）

## 3. ERes2Net 教程里引用的原始资源（其他几个模型的迁移流程同构）

- 原始源码 VoiceprintRecognition-Pytorch — [https://gitee.com/yeyupiaoling/VoiceprintRecognition-Pytorch](https://gitee.com/yeyupiaoling/VoiceprintRecognition-Pytorch)
- 原始权重 model.pth — [https://download.fdwxhb.com/data/04_FPAI/04_modelzoo/modelzoo_pub/weights/pytorch/ERes2Net/ERes2Net_TSTP_Fbank/best_model/model.pth](https://download.fdwxhb.com/data/04_FPAI/04_modelzoo/modelzoo_pub/weights/pytorch/ERes2Net/ERes2Net_TSTP_Fbank/best_model/model.pth)
- icraft 编译器介绍 — [https://gitee.com/mxh-spiger/icraft-introduction](https://gitee.com/mxh-spiger/icraft-introduction)
- runtime 部署教程 — [https://gitee.com/mxh-spiger/tutorial-runtime](https://gitee.com/mxh-spiger/tutorial-runtime)
- 官方模型清单（飞书 wiki，可能需登录权限）— [https://ucnb4916m9po.feishu.cn/wiki/UPp5wSnPEijIHskhbA2chb66nu9](https://ucnb4916m9po.feishu.cn/wiki/UPp5wSnPEijIHskhbA2chb66nu9)
- benchmark 数据 — [https://gitee.com/mxh-spiger/benchmark/tree/master/benchmark](https://gitee.com/mxh-spiger/benchmark/tree/master/benchmark)
- conformer 的原始模型仓 — [https://www.modelscope.cn/models/limengying/conformer](https://www.modelscope.cn/models/limengying/conformer)

说明一点，6 个仓里只有 **ERes2Net** 的 README 是完整的"下载权重 → 保存框架模型 → icraft 编译 → 仿真 → 板上部署 → 精度测试"教程，CAMpplus 和 EcapaTDNN 的 README 只是 modelzoo 通用工程说明，Res2Net/SeResNet/TDNN 则是空卡片。这些 README 已随模型下载到校机 `D:\yzd\llm\funasr\aibs\models\<模型名>\README.md`，我也拉了一份到本机项目目录的 `aibs_readmes` 文件夹，可直接离线看。

