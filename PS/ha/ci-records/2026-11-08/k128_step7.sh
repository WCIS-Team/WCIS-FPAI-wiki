#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3
REPO=/s/work/WCIS/repos/HA4FPAI/lang/llm/models/Qwen3-0.6B/compile
python $REPO/patch_mask0.py compile/jr_path/Q3K128/Q3K128-decoder_adapted.json \
  compile/jr_path/Q3K128/Q3K128-decoder_adapted_mask0zg.json "@zhuget(330)" 2>&1 | tail -2
cd compile
cat > Q3K128_gen.toml <<'EOF'
[parse]
net_name = 'Q3K128'
framework = 'onnx'
network = './fmodel/q3_v1/model.onnx'
network_exdata  = './fmodel/q3_v1/model.onnx.data'
jr_path = './jr_path/Q3K128/'
max_prompt_length = 32
max_tokens_length = 128
target = 'zhuge'
llm_mode = true
quantized = true

[generate]
json = './jr_path/Q3K128/Q3K128-decoder_adapted_mask0zg.json'
raw = './jr_path/Q3K128/Q3K128-decoder_adapted.raw'
jr_path = './jr_path/Q3K128/'
EOF
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
"$IC" generate Q3K128_gen.toml --log_path Q3K128_genlog > ../logs_k128full_gen.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128full_gen.log >/dev/null && grep -aE "stepTo faild|fatal|Exception" ../logs_k128full_gen.log | head -3 || echo gen_ok
ls -la jr_path/Q3K128/Q3K128-decoder_ZG.* 2>/dev/null