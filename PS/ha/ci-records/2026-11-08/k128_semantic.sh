#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
REPO=/s/work/WCIS/repos/HA4FPAI/lang/llm/models/Qwen3-0.6B/compile
python $REPO/host_gen.py --json jr_path/Q3K128/Q3K128-decoder_adapted_mask0zg.json \
  --raw jr_path/Q3K128/Q3K128-decoder_adapted.raw --work probe_k128 \
  --prompt 151644 --max-new 0 --pos-offset 1 2>&1 | tail -6