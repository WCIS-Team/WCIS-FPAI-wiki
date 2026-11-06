#!/bin/bash
# 04-apply-dtb-permanent.sh — 永久修改 boot 分区的 DTB（重启后生效）
#
# 用法:
#   ./04-apply-dtb-permanent.sh clock     # 只改时钟 25->50MHz（推荐先做这个）
#   ./04-apply-dtb-permanent.sh dma       # 只加 dmas 属性
#   ./04-apply-dtb-permanent.sh both      # 两者都改
#   ./04-apply-dtb-permanent.sh verify    # 只做校验，不写盘
#
# 安全设计:
#   - 改前自动备份到 fmqlmp-verify.dtb.bak-<时间戳>
#   - dtc 往返编译后强制 diff 校验，只允许出现预期的属性变化
#   - 校验不通过直接中止，不写盘
#   - root 在 SD 卡上，eMMC 配错不会导致系统起不来
set -u

MODE=${1:-}
BOOTDEV=/dev/mmcblk0p1
BOOTMNT=/mnt/bootrw
DTBNAME=fmqlmp-verify.dtb
KSRC=${KSRC:-/root/home/lili/linux-5.4.52-fmsh}
DTC=$KSRC/scripts/dtc/dtc
WORK=/tmp/dtbwork

case "$MODE" in
    clock|dma|both|verify) ;;
    *) echo "用法: $0 clock|dma|both|verify"; exit 1 ;;
esac

[ -x "$DTC" ] || { echo "先跑 01-build-dtc.sh"; exit 1; }

mkdir -p "$BOOTMNT" "$WORK"

echo "==> [1/6] 挂载 boot 分区"
if ! mount | grep -q " $BOOTMNT "; then
    mount -o rw "$BOOTDEV" "$BOOTMNT" || { echo "挂载失败"; exit 1; }
fi
SRC="$BOOTMNT/$DTBNAME"
[ -f "$SRC" ] || { echo "找不到 $SRC"; umount "$BOOTMNT"; exit 1; }
echo "    源文件: $SRC ($(stat -c%s "$SRC") bytes)"

echo "==> [2/6] 反编译"
$DTC -I dtb -O dts "$SRC" > "$WORK/orig.dts" 2>/dev/null || { echo "反编译失败"; umount "$BOOTMNT"; exit 1; }
cp "$WORK/orig.dts" "$WORK/mod.dts"

echo "==> [3/6] 修改节点 (mode=$MODE)"
python3 - "$WORK/mod.dts" "$MODE" <<'PYEOF'
import sys, re
path, mode = sys.argv[1], sys.argv[2]
lines = open(path).read().split('\n')

start = None
for i, l in enumerate(lines):
    if re.match(r'\s*dwmmc@e0044000\s*\{', l):
        start = i
        break
if start is None:
    sys.exit('找不到 dwmmc@e0044000 节点')

depth = 0
end = None
for i in range(start, len(lines)):
    depth += lines[i].count('{') - lines[i].count('}')
    if depth == 0 and i > start:
        end = i
        break
if end is None:
    sys.exit('找不到节点结尾')

add = []
if mode in ('dma', 'both'):
    if not any('dmas' in lines[j] for j in range(start, end)):
        add.append('\t\t\tdmas = <0x0a 0x01 0x00 0x00>;')
        add.append('\t\t\tdma-names = "rx-tx";')
    else:
        print('    注意: 节点已有 dmas，跳过')
if mode in ('clock', 'both'):
    hit = False
    for j in range(start, end):
        if 'max-frequency' in lines[j]:
            lines[j] = '\t\t\tmax-frequency = <0x2faf080>;'
            hit = True
    if not hit:
        add.append('\t\t\tmax-frequency = <0x2faf080>;')

lines[end:end] = add
open(path, 'w').write('\n'.join(lines))
print('    已插入 %d 行: %s' % (len(add), ', '.join(a.strip().split(' ')[0] for a in add) or '(替换已有值)'))
PYEOF

[ $? -eq 0 ] || { echo "修改失败"; umount "$BOOTMNT"; exit 1; }

echo "==> [4/6] 重新编译"
$DTC -I dts -O dtb "$WORK/mod.dts" -o "$WORK/new.dtb" 2>/dev/null || { echo "编译失败"; umount "$BOOTMNT"; exit 1; }
echo "    新 DTB: $(stat -c%s "$WORK/new.dtb") bytes"

echo "==> [5/6] 校验（只允许预期变化）"
$DTC -I dtb -O dts "$WORK/new.dtb" > "$WORK/new.dts" 2>/dev/null
diff -u "$WORK/orig.dts" "$WORK/new.dts" > "$WORK/delta.diff"
CHANGED=$(grep -E '^[+-][^+-]' "$WORK/delta.diff" | sed 's/^[+-]//' | sed 's/^\s*//' | grep -vE '^(dmas|dma-names|max-frequency)' | grep -v '^$' | wc -l)
echo "    非预期变更行数: $CHANGED"
echo "    --- 实际变更 ---"
grep -E '^[+-][^+-]' "$WORK/delta.diff" | sed 's/^/      /'
echo "    ----------------"
if [ "$CHANGED" -ne 0 ]; then
    echo "    ❌ 出现非预期变更，中止写盘。详情: $WORK/delta.diff"
    umount "$BOOTMNT"
    exit 1
fi
echo "    ✅ 校验通过"

if [ "$MODE" = "verify" ]; then
    echo "==> verify 模式，不写盘"
    umount "$BOOTMNT"
    exit 0
fi

echo "==> [6/6] 备份并写盘"
BK="$BOOTMNT/$DTBNAME.bak-$(date +%Y%m%dT%H%M%S)"
cp "$SRC" "$BK" && echo "    备份: $BK"
cp "$WORK/new.dtb" "$SRC" && echo "    已写入 $SRC"
sync
umount "$BOOTMNT"

echo ""
echo "=================================================="
echo " 完成。重启后生效："
echo "   reboot"
echo ""
echo " 重启后验证："
echo "   dmesg | grep -E 'mmc1|dw_mmc.*e0044000'"
echo "   cat /sys/kernel/debug/mmc1/ios | head -3"
echo ""
echo " 回滚："
echo "   99-rollback.sh $BK"
echo "=================================================="
