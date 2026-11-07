#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
cat > Q3K128_gen_mask0zg.toml <<'EOF'
[parse]
net_name = 'Q3K128'
framework = 'onnx'
network = './fmodel/q3_v1/model.onnx'
network_exdata  = './fmodel/q3_v1/model.onnx.data'
jr_path = './jr_path/Q3V1/'
max_prompt_length = 32
max_tokens_length = 128
target = 'zhuge'
llm_mode = true
quantized = true

[generate]
json = './jr_path/Q3V1/Q3K128-decoder_adapted_mask0zg.json'
raw = './jr_path/Q3V1/Q3K128-decoder_adapted.raw'
jr_path = './jr_path/Q3V1/'
EOF
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
"$IC" generate Q3K128_gen_mask0zg.toml --log_path Q3K128_gen_log > ../logs_k128_gen3.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_gen3.log && echo GEN_FATAL || echo gen_ok
ls -la jr_path/Q3V1/Q3K128-decoder_ZG.* 2>/dev/null | head -3