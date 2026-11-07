#!/bin/sh
# 视频链 1 核持久化：systemd drop-in（ExecStartPost taskset）
V=/etc/systemd/system/wcis-face-photo.service.d
mkdir -p $V
cat > $V/10-cpu-affinity.conf <<'EOF'
[Service]
# 视频链 1 核满帧（2026-11-07 实测：COEXISTENCE.md §六）；cpu1-3 让给 CPU 密集件
ExecStartPost=/usr/bin/taskset -pc 0 $MAINPID
CPUAffinity=0
EOF
systemctl daemon-reload
systemctl restart wcis-face-photo
sleep 8
P=$(pgrep -f serve_photos | head -1)
echo "photo_pid=$P affinity=$(grep Cpus_allowed_list /proc/$P/status)"
OP=$(pgrep -f camera_owner | head -1)
[ -n "$OP" ] && { taskset -pc 0 $OP >/dev/null; echo "owner($OP)=$(grep Cpus_allowed_list /proc/$OP/status)"; }
curl -s --max-time 4 localhost:8092/api/status | python3 -c "import sys,json;d=json.load(sys.stdin);print('ready',d.get('ready'))"
echo persisted