#!/bin/bash
# 05-preflight-overlay.sh — overlay 机制预检（零风险）
#
# 目的：在动 eMMC 之前，先确认 overlay 能注入、能回滚、不影响驱动。
#       全程只改实时 DT 属性，不做 unbind/bind，驱动不会重新探测，等于空转。
#
# 用法：
#   ./05-preflight-overlay.sh                # 跑全部检查
#   ./05-preflight-overlay.sh --clock        # 只测时钟 overlay
#   ./05-preflight-overlay.sh --dma          # 只测 DMA overlay
#
# 安全性：eMMC 保持挂载、服务不动、数据不写（除了最后的 8MB 校验文件，写完即删）
#
# 2026-10-29 首次执行结果：全部通过（boot 72a8f941）

set -u

NODE=/sys/firmware/devicetree/base/amba-apu@0/dwmmc@e0044000
OVBASE=/sys/kernel/config/device-tree/overlays
DTBO_DIR=/root/emmc-overlays
MNT=/mnt/wcis-emmc

RED='\033[31m'; GRN='\033[32m'; YEL='\033[33m'; NC='\033[0m'
ok()   { echo -e "  ${GRN}✅ $*${NC}"; }
bad()  { echo -e "  ${RED}❌ $*${NC}"; }
warn() { echo -e "  ${YEL}⚠️  $*${NC}"; }
hr()   { echo "------------------------------------------------------------"; }

readfreq() { od -An -tu4 --endian=big "$NODE/max-frequency" 2>/dev/null | tr -d ' \n'; }
readreg()  { busybox devmem "$1" 32 2>/dev/null; }

MODE="${1:---all}"

hr
echo "overlay 预检 @ $(date -u '+%F %T UTC')"
echo "  boot_id      : $(cat /proc/sys/kernel/random/boot_id)"
echo "  kernel       : $(uname -r)"
echo "  max-frequency: $(readfreq)   (基线应为 25000000)"
echo "  CLKDIV       : $(readreg 0xe0044008)   (基线应为 0x2)"
echo "  CTRL         : $(readreg 0xe0044000)   (基线应为 0x10，PIO)"
hr

# ---- 前置检查 ----
echo "[0] 前置"
[ -d "$OVBASE" ] || { bad "configfs overlay 目录不存在"; exit 1; }
ok "configfs overlay 目录存在"
for f in mmc1-clock.dtbo mmc1-dma.dtbo; do
    [ -f "$DTBO_DIR/$f" ] && ok "$f 存在（$(stat -c%s "$DTBO_DIR/$f") B）" || { bad "$f 缺失"; exit 1; }
done
BASE_FREQ=$(readfreq)
BASE_CLKDIV=$(readreg 0xe0044008)
[ "$BASE_FREQ" = "25000000" ] || warn "基线 max-frequency 不是 25000000，而是 $BASE_FREQ（可能已改过）"
echo

# ---- 通用：注入一个 dtbo，检查，回滚 ----
inject_and_check() {
    local dtbo="$1" label="$2" checker="$3"
    local name="pf-$$-$RANDOM"
    local dir="$OVBASE/$name"

    echo "[$label] 注入 $(basename "$dtbo")"
    dmesg -C >/dev/null 2>&1 || true
    mkdir -p "$dir" || { bad "mkdir 失败"; return 1; }

    # 用 dtbo 二进制接口，不走 path（path 不吃绝对路径，见 07 踩坑 C7）
    if ! cat "$dtbo" > "$dir/dtbo" 2>/dev/null; then
        bad "写入 dtbo 失败"
        rmdir "$dir" 2>/dev/null
        return 1
    fi

    local st
    st=$(cat "$dir/status" 2>/dev/null)
    [ "$st" = "applied" ] && ok "status = applied" || { bad "status = $st"; }

    $checker

    echo "  dmesg:"
    dmesg | grep -i overlay | sed 's/^/    /' || echo "    (无)"

    rmdir "$dir" 2>/dev/null
    [ -d "$dir" ] && bad "卸载失败，目录还在" || ok "已卸载"
    return 0
}

check_clock() {
    local f; f=$(readfreq)
    [ "$f" = "50000000" ] && ok "max-frequency = $f（期望 50000000）" \
                           || bad "max-frequency = $f（期望 50000000）"
    local c; c=$(readreg 0xe0044008)
    [ "$c" = "0x00000002" ] && ok "CLKDIV 仍为 0x2 —— 驱动没被触发，符合预期" \
                             || warn "CLKDIV 变成 $c，驱动被触发了？"
}

check_dma() {
    [ -e "$NODE/dmas" ] && ok "dmas 属性已注入" || { bad "dmas 属性不存在"; return; }
    local raw; raw=$(od -An -tx1 "$NODE/dmas" 2>/dev/null | tr -s ' ')
    echo "    dmas 原始字节:$raw"
    echo "    dma-names    : [$(tr -d '\0' < "$NODE/dma-names" 2>/dev/null)]"
    echo "    期望解析为 phandle=0x0a, req=0x01, m_master=0, p_master=0"
    local c; c=$(readreg 0xe0044000)
    [ "$c" = "0x00000010" ] && ok "CTRL 仍为 0x10 —— 仍在 PIO，符合预期" \
                             || warn "CTRL 变成 $c"
}

case "$MODE" in
    --clock) inject_and_check "$DTBO_DIR/mmc1-clock.dtbo" "1" check_clock ;;
    --dma)   inject_and_check "$DTBO_DIR/mmc1-dma.dtbo"   "1" check_dma ;;
    *)
        inject_and_check "$DTBO_DIR/mmc1-clock.dtbo" "1" check_clock
        echo
        inject_and_check "$DTBO_DIR/mmc1-dma.dtbo"   "2" check_dma
        ;;
esac

echo
hr
echo "[3] 回滚确认"
F=$(readfreq)
[ "$F" = "$BASE_FREQ" ] && ok "max-frequency 已恢复 $F" || bad "max-frequency = $F，基线是 $BASE_FREQ"
[ -e "$NODE/dmas" ] && bad "dmas 属性残留！" || ok "dmas 属性已清除"
echo "  overlays 目录: [$(ls "$OVBASE" 2>/dev/null | tr '\n' ' ')]"
echo "  CLKDIV: $(readreg 0xe0044008)   CTRL: $(readreg 0xe0044000)"
echo

hr
echo "[4] eMMC 数据完整性自检（写读 8MB md5）"
if [ -d "$MNT" ] && mountpoint -q "$MNT"; then
    TMPF="$MNT/.preflight-$$.bin"
    dd if=/dev/urandom of="$TMPF" bs=1M count=8 2>/dev/null
    sync
    A=$(md5sum "$TMPF" | cut -d' ' -f1)
    echo 3 > /proc/sys/vm/drop_caches
    B=$(md5sum "$TMPF" | cut -d' ' -f1)
    rm -f "$TMPF"; sync
    echo "  写入 md5: $A"
    echo "  读回 md5: $B"
    [ "$A" = "$B" ] && ok "一致，eMMC 数据通路正常" || bad "不一致！立刻检查"
else
    warn "$MNT 未挂载，跳过"
fi

hr
echo "预检结束。若全部 ✅，说明 overlay 机制可用，可以进入 03-test-overlay.sh 做真 rebind。"
