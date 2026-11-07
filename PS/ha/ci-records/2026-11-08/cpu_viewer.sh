#!/bin/sh
# 视觉链 CPU：0 观众 vs 1 观众（拉 live.mp4 10s）
SNAP() {
  for p in $(pgrep -f "serve_photos|wcis_camera_own|h264|vpu_live|recording_service"); do
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
echo "== A) 0 观众（空闲持续流，现状）"
SNAP > /tmp/p1
sleep 10
SNAP > /tmp/p2
DIFF /tmp/p1 /tmp/p2
echo "== B) 1 观众（拉 live.mp4 流 10s，浏览器等效）"
curl -s --max-time 12 "http://127.0.0.1:8091/api/camera/h264/live.mp4?session=$(curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;print(json.load(sys.stdin).get('session'))")" -o /dev/null &
CURL=$!
sleep 1
SNAP > /tmp/p3
sleep 10
SNAP > /tmp/p4
DIFF /tmp/p3 /tmp/p4
wait $CURL 2>/dev/null
echo "== fps check"
curl -s --max-time 3 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('fps_ctx',d.get('fps_limit'),'frame',d.get('frame_id'))"
echo done