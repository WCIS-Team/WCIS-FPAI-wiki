#!/bin/sh
# 抢核实测：视频链全开 + control + 并发压力，采样每核/每进程
echo "== start vision chain"
systemctl start wcis-face-photo wcis-face-recording wcis-sdi-vpu-view 2>/dev/null
for i in $(seq 1 12); do
  R=$(curl -s --max-time 3 localhost:8092/api/status 2>/dev/null | python3 -c "import sys,json;print(json.load(sys.stdin).get('ready'))" 2>/dev/null)
  [ "$R" = "True" ] && break
  sleep 3
done
echo "cam_ready=$R"
# 快照1: 每核
read_cputime() {
  grep '^cpu[0-9]' /proc/stat | awk '{print $2+$3+$4+$6+$7+$8, $5, $1}'
}
S1=$(read_cputime)
P1=$(grep -E "^(VmRSS|Name)" /proc/*/status 2>/dev/null | head -1 >/dev/null; for p in $(pgrep -f "serve_photos|camera_owner|recording_service|vpu_live|m control.service|python3"); do
  t=$(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null)
  n=$(cat /proc/$p/comm 2>/dev/null)
  [ -n "$t" ] && echo "$t $p $n"
done)
sleep 10
S2=$(read_cputime)
P2=$(for p in $(pgrep -f "serve_photos|camera_owner|recording_service|vpu_live|m control.service|python3"); do
  t=$(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null)
  n=$(cat /proc/$p/comm 2>/dev/null)
  [ -n "$t" ] && echo "$t $p $n"
done)
echo "== per-core utilization over 10s (jiffies delta / 100Hz * cores)"
python3 - <<PY
import sys
s1 = """$S1""".strip().split('\n')
s2 = """$S2""".strip().split('\n')
for a, b in zip(s1, s2):
    ta = [int(x) for x in a.split()][:2]
    tb = [int(x) for x in b.split()][:2]
    tot = tb[0] - ta[0]; idle = tb[1] - ta[1]
    if tot > 0:
        print('  %s busy=%.0f%%' % (a.split()[2], 100.0 * (tot - idle) / tot))
PY
echo "== per-process CPU% over 10s (utime+stime delta / 1000s_clock)"
python3 - <<PY
p1 = """$P1""".strip().split('\n')
p2 = """$P2""".strip().split('\n')
d1 = {}
for line in p1:
    parts = line.split()
    if len(parts) >= 3:
        d1[parts[1]] = (int(parts[0]), parts[2])
for line in p2:
    parts = line.split()
    if len(parts) >= 3:
        pid = parts[1]
        if pid in d1:
            delta = int(parts[0]) - d1[pid][0]
            print('  %-18s pid=%-6s cpu=%.0f%%' % (d1[pid][1][:18], pid, delta / 10.0))
PY
echo "== nproc & loadavg"
nproc; cat /proc/loadavg
echo done