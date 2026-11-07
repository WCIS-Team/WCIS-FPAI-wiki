#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3/compile
IC="C:/Icraft/CLI v3.39.0/bin/icraft.exe"
echo "--- artifacts after parse"
ls jr_path/Q3K128/ | head
echo "--- optimize"
"$IC" optimize Q3K128.toml > ../logs_k128_opt.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_opt.log && echo OPT_FATAL || echo opt_ok
echo "--- quantize"
"$IC" quantize Q3K128.toml > ../logs_k128_q.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_q.log && echo Q_FATAL || echo quant_ok
echo "--- adapt"
"$IC" adapt Q3K128.toml > ../logs_k128_adapt.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_adapt.log && echo ADAPT_FATAL || echo adapt_ok
ls -la jr_path/Q3K128/*adapted* 2>/dev/null