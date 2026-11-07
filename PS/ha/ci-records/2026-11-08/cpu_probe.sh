#!/bin/sh
echo "== CPU topology"
nproc
grep -E "^processor|^model name|^CPU part" /proc/cpuinfo | head -8
echo "== per-core load (2 samples, 1s apart)"
mpstat 1 2 2>/dev/null | tail -8 || (top -b -n 2 -d 1 | grep -E "^%Cpu" | tail -2)
echo "== process CPU usage (video + control + npuserv)"
top -b -n 2 -d 2 2>/dev/null | tail -25 | awk 'NR>13 && $9>0.5 {printf "%-8s cpu=%-5s mem=%s%% %s\n", $1, $9, $10, substr($0, index($0,$12), 60)}' | head -12
echo "== current affinity of key procs"
for pat in serve_photos camera_owner recording_service vpu_live "m control.service"; do
  for p in $(pgrep -f "$pat" 2>/dev/null | head -1); do
    a=$(grep Cpus_allowed_list /proc/$p/status 2>/dev/null)
    echo "$pat pid=$p $a"
  done
done