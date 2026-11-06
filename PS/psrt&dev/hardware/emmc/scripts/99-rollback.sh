#!/bin/bash
# 99-rollback.sh — 回滚
#
# 用法:
#   ./99-rollback.sh                 # 只清运行时 overlay + 恢复挂载和服务
#   ./99-rollback.sh <backup.dtb>    # 恢复 boot 分区 DTB（需重启生效）
set -u

DRV=/sys/bus/platform/drivers/dw_mmc
DEV=e0044000.dwmmc
MNT=/mnt/wcis-emmc
OVBASE=/sys/kernel/config/device-tree/overlays
SVC=wcis-face-recording.service
BOOTDEV=/dev/mmcblk0p1
BOOTMNT=/mnt/bootrw
DTBNAME=fmqlmp-verify.dtb

echo "==> 1. 清理运行时 overlay"
for d in "$OVBASE"/*; do
    [ -d "$d" ] || continue
    echo "    移除 $(basename "$d")"
    rmdir "$d" 2>/dev/null || echo "    (失败，可能被占用)"
done

echo "==> 2. 重新 probe mmc1"
echo $DEV > "$DRV/unbind" 2>/dev/null
sleep 1
echo $DEV > "$DRV/bind" 2>/dev/null
sleep 3
dmesg | grep -E "dw_mmc.*e0044000|Using (PIO|external)" | tail -3

echo "==> 3. 重新挂载 $MNT（通过 storage service）"
if ! mount | grep -q " $MNT "; then
    systemctl start wcis-face-storage.service 2>/dev/null
    sleep 2
    if mount | grep -q " $MNT "; then
        echo "    已通过 wcis-face-storage.service 挂载"
    else
        echo "    service 未挂上，尝试直接 mount"
        mount "$MNT" && echo "    已挂载"
    fi
fi

echo "==> 4. 重启服务"
systemctl start "$SVC" 2>/dev/null && echo "    已启动 $SVC"

if [ -n "${1:-}" ]; then
    echo "==> 5. 恢复 boot 分区 DTB: $1"
    [ -f "$1" ] || { echo "找不到 $1"; exit 1; }
    mkdir -p "$BOOTMNT"
    mount | grep -q " $BOOTMNT " || mount -o rw "$BOOTDEV" "$BOOTMNT" || exit 1
    cp "$BOOTMNT/$DTBNAME" "$BOOTMNT/$DTBNAME.before-rollback-$(date +%Y%m%dT%H%M%S)"
    cp "$1" "$BOOTMNT/$DTBNAME" && echo "    已恢复，需 reboot 生效"
    sync
    umount "$BOOTMNT"
fi

echo ""
echo "==> 完成"
