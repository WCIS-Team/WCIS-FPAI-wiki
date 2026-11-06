#!/bin/bash
# 02-bench-mmc.sh — eMMC / SD 吞吐与 CPU 开销测量
# 在目标机上直接运行。会在 /mnt/wcis-emmc 和 /root 下建临时文件，跑完删除。
# 不触碰 /mnt/wcis-emmc/wcis-face/ 目录。
set -u

HZ=$(getconf CLK_TCK)
NP=$(nproc)
echo "HZ=$HZ  nproc=$NP"
echo "提示: 机上有相机服务常驻，基线会波动，绝对值有 ±50% 噪声，看趋势"

snap() { awk '/^cpu /{tot=0; for(i=2;i<=NF;i++) tot+=$i; print tot-$5-$6, $7+$8}' /proc/stat; }

busy_ms_per_s() {
  local secs=$1
  read b i <<< "$(snap)"
  sleep $secs
  read a j <<< "$(snap)"
  awk "BEGIN{printf \"%.0f\", ($a-$b)/$HZ/$secs*1000}"
}

run() {
  local L="$1" C="$2" SZ="$3"
  local base bt at bi ai s e w db tms mbps permb
  base=$(busy_ms_per_s 3)
  read bt bi <<< "$(snap)"
  s=$(date +%s%N)
  eval "$C" >/dev/null 2>&1
  e=$(date +%s%N)
  read at ai <<< "$(snap)"
  w=$(awk "BEGIN{printf \"%.3f\", ($e-$s)/1e9}")
  db=$((at-bt))
  tms=$(awk "BEGIN{printf \"%.0f\", $db/$HZ/$w*1000}")
  mbps=$(awk "BEGIN{printf \"%.2f\", $SZ/1e6/$w}")
  permb=$(awk "BEGIN{printf \"%.1f\", ($tms-$base)*$w/($SZ/1e6)}")
  printf "%-14s | %7s MB/s | wall=%6ss | base=%4s test=%4s net=%4s ms-CPU/s | %6s ms-CPU/MB\n" \
         "$L" "$mbps" "$w" "$base" "$tms" "$((tms-base))" "$permb"
}

E=/mnt/wcis-emmc/ddtest.bin
S=/root/ddtest_sd.bin
SZ=67108864

echo ""
echo "=== eMMC (PIO) 64MB ==="
run "eMMC W 1M" "dd if=/dev/zero of=$E bs=1M count=64 oflag=direct" $SZ
run "eMMC W 64K" "dd if=/dev/zero of=$E bs=64K count=1024 oflag=direct" $SZ
run "eMMC W 4K"  "dd if=/dev/zero of=$E bs=4K count=16384 oflag=direct" $SZ
run "eMMC R 1M"  "dd if=$E of=/dev/null bs=1M count=64 iflag=direct" $SZ
run "eMMC R 64K" "dd if=$E of=/dev/null bs=64K count=1024 iflag=direct" $SZ
run "eMMC R 4K"  "dd if=$E of=/dev/null bs=4K count=16384 iflag=direct" $SZ
rm -f $E

echo ""
echo "=== SD (DMA) 64MB 对照 ==="
run "SD W 1M"  "dd if=/dev/zero of=$S bs=1M count=64 oflag=direct" $SZ
run "SD R 1M"  "dd if=$S of=/dev/null bs=1M count=64 iflag=direct" $SZ
rm -f $S

echo ""
echo "=== 当前总线配置 ==="
for h in mmc0 mmc1; do
    echo "--- $h ---"
    grep -E 'clock:|bus width:|timing spec:' /sys/kernel/debug/$h/ios 2>/dev/null
done
echo "DONE"
