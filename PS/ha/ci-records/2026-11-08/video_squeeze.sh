#!/bin/sh
# 视频链压核实验：2核 → 1.5核(cgroup quota) → 1核(taskset)，各档测相机满帧率
set -e
P=$(pgrep -f serve_photos | head -1)
echo "photo_pid=$P (camera_owner 同 pid)"
BASE_FRAMES() {
  curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('frame_id'))"
}
MEASURE() {
  f1=$(BASE_FRAMES); t1=$(date +%s.%N)
  sleep 10
  f2=$(BASE_FRAMES); t2=$(date +%s.%N)
  python3 -c "print('  fps=%.1f' % (($f2-$f1)/($t2-$t1)))"
  curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('  age=%.2f ready=%s'%(d.get('frame_age_s',-1),d.get('ready')))"
}
echo "== 当前配置基线（无绑定，2s 采样）"
MEASURE
echo "== 档1: cgroup cpu quota 1.5 核（cpu.cfs_quota_us=150000/period 100000）"
CG=/sys/fs/cgroup/cpu/ha4fpai_video
mkdir -p $CG 2>/dev/null || true
if [ -d $CG ]; then
  echo 150000 > $CG/cpu.cfs_quota_us
  echo 100000 > $CG/cpu.cfs_period_us
  for pid in $(pgrep -f "serve_photos|camera_owner|recording_service|vpu_live"); do echo $pid > $CG/cgroup.procs 2>/dev/null || true; done
  echo "  cgroup attached"
  MEASURE
else
  echo "  cgroup v1 cpu controller unavailable（回退 taskset 1 核）"
fi
echo "== 档2: taskset 钉 1 核（cpu0）"
taskset -pc 0 $P >/dev/null && echo "  pinned photo($P)->cpu0"
for pid in $(pgrep -f "camera_owner" | head -1); do taskset -pc 0 $pid >/dev/null && echo "  pinned owner($pid)->cpu0"; done
MEASURE
echo "== 档3: 解除绑定恢复"
taskset -pc 0-3 $P >/dev/null
for pid in $(pgrep -f "camera_owner" | head -1); do taskset -pc 0-3 $pid >/dev/null; done
rm -rf $CG 2>/dev/null || true
MEASURE
echo done