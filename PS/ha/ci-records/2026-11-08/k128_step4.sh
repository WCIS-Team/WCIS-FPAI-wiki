#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
# 生成 K128 的 generate toml：max_tokens_length=128，json/raw 相对 jr_path（不带 Q3V1/ 前缀）
cat > Q3K128_gen_mask0zg.toml <<'EOF'
[generate]
json = './jr_path/Q3V1//Q3K128-decoder_adapted_mask0zg.json'
raw = './jr_path/Q3V1//Q3K128-decoder_adapted.raw'
jr_path = './jr_path/Q3V1/'
max_prompt_length = 32
max_tokens_length = 128
target = 'zhuge'
llm_mode = true
quantized = true
EOF
echo "--- toml written"
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
"$IC" generate Q3K128_gen_mask0zg.toml --log_path Q3K128_gen_log > ../logs_k128_gen2.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_gen2.log && echo GEN_FATAL || echo gen_ok
ls -la jr_path/Q3V1/Q3K128-decoder_ZG.* 2>/dev/null