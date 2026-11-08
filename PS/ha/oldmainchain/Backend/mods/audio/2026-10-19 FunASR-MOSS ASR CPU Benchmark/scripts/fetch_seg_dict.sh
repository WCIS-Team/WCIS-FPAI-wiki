#!/bin/bash
set -x
/d/yzd/llm/funasr/venv/Scripts/modelscope.exe download iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch --include seg_dict --local-dir /d/yzd/llm/funasr/models/paraformer-large-vad-punc > /d/yzd/llm/funasr/log_seg_dict.txt 2>&1
echo SEG_DICT_DONE
