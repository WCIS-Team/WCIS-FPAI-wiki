#!/bin/sh
SNAP() {
  for p in $(pgrep -f "serve_photos|wcis_camera_own|h264|vpu_live|recording_service|ffmpeg"); do
    echo "$p $(awk '{print $14+$15}' /proc/$p/stat 2>/dev/null) $(cat /proc/$p/comm 2>/dev/null)"
  done
}
DIFF() {
  python3 - "$1" "$2" <<'PY'
import sys
d1, d2 = {}, {}
for line in open(sys.argv[1]):
    f = line.split()
    if len(f) >= 3: d1[f[0]] = (int(f[1]), f[2])
for line in open(sys.argv[2]):
    f = line.split()
    if len(f) >= 3 and f[0] in d1:
        d = int(f[1]) - d1[f[0]][0]
        if d > 2:
            print('  %-18s cpu=%d%%' % (d1[f[0]][1][:18], d / 10))
PY
}
echo "== A) 全开基线 10s"
SNAP > /tmp/p1; sleep 10; SNAP > /tmp/p2
DIFF /tmp/p1 /tmp/p2
echo "== stop recording + vpu_live（保留 photo/owner 采集）"
systemctl stop wcis-face-recording wcis-sdi-vpu-view
sleep 2
SNAP > /tmp/p3; sleep 10; SNAP > /tmp/p4
echo "== B) 停两服务后 10s"
DIFF /tmp/p3 /tmp/p4
echo "== 相机还活着吗（photo/owner 保留）"
curl -s --max-time 3 localhost:8092/api/status 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('ready',d.get('ready'),'age',round(d.get('frame_age_s',-1),2))" 2>/dev/null || echo panel_down_but_owner_alive
curl -s --max-time 3 localhost:8091/api/health | python3 -c "import sys,json;d=json.load(sys.stdin);print('health',d.get('status'))"
echo "== 恢复两服务"
systemctl start wcis-face-recording wcis-sdi-vpu-view
sleep 3
systemctl is-active wcis-face-recording wcis-sdi-vpu-view
echo done