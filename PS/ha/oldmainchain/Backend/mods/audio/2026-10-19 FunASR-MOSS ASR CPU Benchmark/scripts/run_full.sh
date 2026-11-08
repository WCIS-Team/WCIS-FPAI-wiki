#!/bin/bash
set -x
cd /d/yzd/llm/funasr
PY=/d/yzd/llm/funasr/venv/Scripts/python.exe
OUT=/d/yzd/llm/funasr/results
for m in paraformer sensevoice moss; do
  case $m in
    paraformer) DIR=models/paraformer-large-vad-punc ;;
    sensevoice) DIR=models/SenseVoiceSmall ;;
    moss) DIR=models/MOSS-Transcribe-Diarize ;;
  esac
  for r in 1 2 3; do
    $PY bench.py --model $m --model-dir /d/yzd/llm/funasr/$DIR --manifest $OUT/manifest20.json --out $OUT/full_${m}_run${r}.json --threads 4 --run-id $r
  done
done
echo FULL_ALL_DONE
