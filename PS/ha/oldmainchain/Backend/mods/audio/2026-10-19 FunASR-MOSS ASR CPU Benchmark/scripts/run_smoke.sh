#!/bin/bash
set -x
cd /d/yzd/llm/funasr
PY=/d/yzd/llm/funasr/venv/Scripts/python.exe
OUT=/d/yzd/llm/funasr/results
mkdir -p "$OUT"

$PY make_manifest.py --csv /d/yzd/llm/funasr/data/aishell1_test/aishell1_test.csv --audio-root /d/yzd/llm/funasr/data/aishell1/data_aishell --out "$OUT/manifest_smoke.json" --limit 2 --seed 42

$PY bench.py --model paraformer --model-dir /d/yzd/llm/funasr/models/paraformer-large-vad-punc --manifest "$OUT/manifest_smoke.json" --out "$OUT/smoke_paraformer.json" --threads 4 --run-id 0
echo SMOKE_PARA_DONE
$PY bench.py --model sensevoice --model-dir /d/yzd/llm/funasr/models/SenseVoiceSmall --manifest "$OUT/manifest_smoke.json" --out "$OUT/smoke_sensevoice.json" --threads 4 --run-id 0
echo SMOKE_SENSE_DONE
$PY bench.py --model moss --model-dir /d/yzd/llm/funasr/models/MOSS-Transcribe-Diarize --manifest "$OUT/manifest_smoke.json" --out "$OUT/smoke_moss.json" --threads 4 --run-id 0
echo SMOKE_MOSS_DONE
echo SMOKE_ALL_DONE
