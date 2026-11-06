#!/bin/bash
# 03-test-overlay.sh — 运行时用 device tree overlay 临时改 mmc1 配置并测速
#
# 用法:
#   ./03-test-overlay.sh /root/emmc-overlays/mmc1-clock.dtbo   # 测时钟
#   ./03-test-overlay.sh /root/emmc-overlays/mmc1-dma.dtbo     # 测 DMA
#   ./03-test-overlay.sh /root/emmc-overlays/mmc1-both.dtbo    # 两者一起
#   ./03-test-overlay.sh --rollback                            # 回滚
#
# 原理: configfs 的 device-tree/overlays 接口可运行时注入 overlay，
#       再 unbind/rebind dw_mmc 让驱动重新 probe 读取新属性。
#       不重启、不改 DTB，rmdir 即回滚。
#
# 挂载管理: /mnt/wcis-emmc 由 wcis-face-storage.service 管（不是 fstab），
#           必须用 systemctl stop/start 它，不能直接 umount，
#           否则 unit 的 RemainAfterExit=yes 状态会和实际挂载不一致。
set -u

DRV=/sys/bus/platform/drivers/dw_mmc
DEV=e0044000.dwmmc
MNT=/mnt/wcis-emmc
OVBASE=/sys/kernel/config/device-tree/overlays
DTNODE=/proc/device-tree/amba-apu@0/dwmmc@e0044000
SVC_REC=wcis-face-recording.service
SVC_STORE=wcis-face-storage.service

die() { echo "ERROR: $*" >&2; exit 1; }

remount_emmc() {
    if systemctl start "$SVC_STORE" 2>/dev/null; then
        sleep 2
    fi
    if mount | grep -q " $MNT "; then
        echo "    $MNT 已挂载"
    else
        echo "    ⚠️  $MNT 未挂载，尝试直接 mount"
        mount "$MNT" 2>/dev/null && echo "    直接挂载成功" || echo "    ❌ 挂载失败"
    fi
}

do_rollback() {
    echo "==> 回滚：移除 overlay 并重新 probe"
    for d in "$OVBASE"/*; do
        [ -d "$d" ] || continue
        echo "    移除 $(basename "$d")"
        rmdir "$d" 2>/dev/null || echo "    (移除失败)"
    done
    echo $DEV > "$DRV/unbind" 2>/dev/null
    sleep 1
    echo $DEV > "$DRV/bind" 2>/dev/null
    sleep 3
    remount_emmc
    systemctl start "$SVC_REC" 2>/dev/null
    echo "==> 回滚完成，当前状态："
    dmesg | grep -E "dw_mmc.*e0044000|Using (PIO|external)" | tail -3
    grep -E 'clock:' /sys/kernel/debug/mmc1/ios 2>/dev/null
    exit 0
}

[ "${1:-}" = "--rollback" ] && do_rollback

DTBO=${1:-}
[ -n "$DTBO" ] || die "用法: $0 <overlay.dtbo> | --rollback"
[ -f "$DTBO" ] || die "找不到 $DTBO"
NAME=$(basename "$DTBO" .dtbo)

BOOTID=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)
echo "=================================================="
echo " overlay : $DTBO  ($(stat -c%s "$DTBO") bytes)"
echo " 目标节点: $DTNODE"
echo " boot ID : $BOOTID"
echo " 起始时间: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=================================================="
echo ""

echo "==> [0/7] 前置检查"
[ -d "$OVBASE" ] || die "configfs overlay 不可用（检查 CONFIG_OF_CONFIGFS）"
echo "    configfs overlay 可用"

echo "==> [1/7] 停止录像服务"
systemctl stop "$SVC_REC" 2>/dev/null && echo "    已停 $SVC_REC" || echo "    $SVC_REC 未运行"

echo "==> [2/7] 卸载 eMMC（通过 storage service）"
if mount | grep -q " $MNT "; then
    if systemctl is-active --quiet "$SVC_STORE" 2>/dev/null; then
        systemctl stop "$SVC_STORE" || die "停止 $SVC_STORE 失败"
        sleep 1
        echo "    已通过 $SVC_STORE 卸载"
    fi
    if mount | grep -q " $MNT "; then
        echo "    service 停后仍未卸载，回退到直接 umount"
        umount "$MNT" || die "umount 失败，检查占用进程"
    fi
    mount | grep -q " $MNT " && die "仍处于挂载状态，中止"
    echo "    确认已卸载"
else
    echo "    未挂载，跳过"
fi

echo "==> [3/7] 注入 overlay"
OVDIR="$OVBASE/$NAME"
rmdir "$OVDIR" 2>/dev/null
mkdir -p "$OVDIR" || die "创建 $OVDIR 失败"
cat "$DTBO" > "$OVDIR/dtbo" || die "写入 dtbo 失败（内核拒绝了该 overlay）"
echo "    已注入"
echo "    节点当前属性:"
for p in dmas dma-names max-frequency; do
    if [ -e "$DTNODE/$p" ]; then
        printf "      %-14s = " "$p"
        if [ "$p" = "dma-names" ]; then cat "$DTNODE/$p"; echo
        else xxd -p "$DTNODE/$p" | tr -d '\n'; echo; fi
    fi
done

echo "==> [4/7] unbind / bind 驱动"
echo $DEV > "$DRV/unbind" || die "unbind 失败"
sleep 1
echo $DEV > "$DRV/bind" || die "bind 失败"
sleep 3
echo "    已重新 probe"

echo "==> [5/7] 驱动实际选择"
if dmesg | tail -50 | grep -q "Using external DMA controller"; then
    echo "    [OK] 外部 DMA"
elif dmesg | tail -50 | grep -q "Using PIO mode"; then
    echo "    [!] PIO（DMA 请求线可能没接，或属性未生效）"
fi
dmesg | grep -E "dw_mmc.*e0044000|mmc1:|mmcblk1" | tail -6

echo "==> [6/7] 重新挂载"
if [ ! -b /dev/mmcblk1p1 ]; then
    echo "    [FAIL] /dev/mmcblk1p1 未出现，mmc1 probe 失败"
    echo "    立即回滚: $0 --rollback"
    exit 1
fi
remount_emmc

echo "==> [7/7] 总线配置 + 测速"
grep -E 'clock:|bus width:|timing spec:' /sys/kernel/debug/mmc1/ios 2>/dev/null
if mount | grep -q " $MNT "; then
    echo ""
    echo "    --- 32MB 读写 ---"
    dd if=/dev/zero of=$MNT/ddtest.bin bs=1M count=32 oflag=direct 2>&1 | tail -1
    dd if=$MNT/ddtest.bin of=/dev/null bs=1M count=32 iflag=direct 2>&1 | tail -1
    rm -f $MNT/ddtest.bin
    echo ""
    echo "    --- 错误检查 ---"
    dmesg | grep -iE 'crc|timeout|I/O error|mmc1.*error' | tail -5 || echo "    无错误"
fi

echo ""
echo "=================================================="
echo " 完成 (boot $BOOTID)"
echo "   固化   -> 04-apply-dtb-permanent.sh"
echo "   回滚   -> $0 --rollback"
echo "=================================================="
