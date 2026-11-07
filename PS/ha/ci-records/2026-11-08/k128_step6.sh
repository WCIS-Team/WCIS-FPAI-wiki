#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
# K128 全链 toml：全部产物隔离在 jr_path/Q3K128/，不碰 Q3V1
cat > Q3K128_full.toml <<'EOF'
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

[optimize]
target = 'zhuge'
json = './jr_path/Q3K128/Q3K128-decoder_parsed.json'
raw = './jr_path/Q3K128/Q3K128-decoder_parsed.raw'
jr_path = './jr_path/Q3K128/'

[quantize]
json = './jr_path/Q3K128/Q3K128-decoder_optimized.json'
raw = './jr_path/Q3K128/Q3K128-decoder_optimized.raw'
jr_path = './jr_path/Q3K128/'
qdtype = "fp16"
target = "zhuge"

[adapt]
target = 'zhuge'
json = './jr_path/Q3K128/Q3K128-decoder_quantized.json'
raw = './jr_path/Q3K128/Q3K128-decoder_quantized.raw'
jr_path = './jr_path/Q3K128/'
pass_off = "icraft.MergeTransDataOpSeqPass"

[generate]
json = './jr_path/Q3K128/Q3K128-decoder_adapted.json'
raw = './jr_path/Q3K128/Q3K128-decoder_adapted.raw'
jr_path = './jr_path/Q3K128/'
EOF
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
for st in parse optimize quantize adapt; do
  echo "--- $st"
  "$IC" $st Q3K128_full.toml > ../logs_k128full_$st.log 2>&1 || true
  grep -cE "stepTo faild|fatal" ../logs_k128full_$st.log >/dev/null && grep -aE "stepTo faild|fatal" ../logs_k128full_$st.log | head -2 || echo ${st}_ok
done
ls -la jr_path/Q3K128/*adapted* 2>/dev/null | head -3