#!/bin/sh
set -e
cd /s/apps/llm/agentwork/qwen3
REPO=/s/work/WCIS/repos/HA4FPAI/lang/llm/models/Qwen3-0.6B/compile
echo "--- mask patch (zg variant, n auto=128)"
python $REPO/patch_mask0.py compile/jr_path/Q3V1/Q3K128-decoder_adapted.json \
  compile/jr_path/Q3V1/Q3K128-decoder_adapted_mask0zg.json "@zhuget(330)" 2>&1 | tail -3
echo "--- gen toml for mask0zg"
sed "s|Q3V1-decoder_adapted.json|Q3V1/Q3K128-decoder_adapted_mask0zg.json|; s|Q3V1-decoder_adapted.raw|Q3V1/Q3K128-decoder_adapted_mask0zg.raw|; s/net_name = 'Q3V1'/net_name = 'Q3K128'/" compile/Q3V1_gen_mask0zg.toml > compile/Q3K128_gen_mask0zg.toml 2>/dev/null || true
cat compile/Q3V1_gen_mask0zg.toml
echo "--- generate (mask0zg)"
cd compile
"C:/Icraft/CLI v3.39.0/bin/icraft.exe" generate Q3K128_gen_mask0zg.toml --log_path Q3K128_gen_log > ../logs_k128_gen.log 2>&1 || true
grep -cE "stepTo faild|fatal" ../logs_k128_gen.log && echo GEN_FATAL || echo gen_ok
ls -la jr_path/Q3V1/Q3K128-decoder_ZG.* 2>/dev/null