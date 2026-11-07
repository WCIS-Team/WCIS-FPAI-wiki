#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
sed "s/max_tokens_length = 512/max_tokens_length = 128/; s/net_name = 'Q3V1'/net_name = 'Q3K128'/" Q3V1_parse.toml > Q3K128.toml
grep -E "net_name|max_tokens" Q3K128.toml
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
echo "--- parse"
"$IC" parse Q3K128.toml > ../logs_k128_parse.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_parse.log && echo PARSE_FATAL || echo parse_ok
ls -la jr_path/Q3K128/*parsed* 2>/dev/null | head -3