#!/bin/bash
set -x
/d/yzd/llm/funasr/venv/Scripts/hf.exe download shenyunhang/AISHELL-1 --repo-type dataset --include "data_aishell/wav/test/**" --local-dir /d/yzd/llm/funasr/data/aishell1 > /d/yzd/llm/funasr/log_aishell_dl.txt 2>&1
echo AISHELL_TEST_DONE
