#!/bin/bash
set -x
cd /d/yzd/llm/funasr
PY=/d/yzd/llm/funasr/venv/Scripts/python.exe
OUT=/d/yzd/llm/funasr/results
mkdir -p "$OUT"
$PY make_manifest.py --csv /d/yzd/llm/funasr/data/aishell1_test/aishell1_test.csv --audio-root /d/yzd/llm/funasr/data/aishell1/data_aishell --out "$OUT/manifest20.json" --limit 20 --seed 42
$PY /d/yzd/llm/funasr/extract_wavs.py "$OUT/manifest20.json" /d/yzd/llm/funasr/wav_list20.txt
args=$(cat /d/yzd/llm/funasr/wav_list20.txt | tr '\n' ' ')
/d/yzd/llm/funasr/venv/Scripts/hf.exe download shenyunhang/AISHELL-1 --repo-type dataset --max-workers 16 $args --local-dir /d/yzd/llm/funasr/data/aishell1 > /d/yzd/llm/funasr/log_sample_dl.txt 2>&1
echo SAMPLE_DL_DONE
