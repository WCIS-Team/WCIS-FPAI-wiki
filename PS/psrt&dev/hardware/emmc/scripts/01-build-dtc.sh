#!/bin/bash
# 01-build-dtc.sh — 在目标机上编译 dtc 工具
# 目标机: 192.168.1.113  内核源码: /root/home/lili/linux-5.4.52-fmsh
set -e

KSRC=${KSRC:-/root/home/lili/linux-5.4.52-fmsh}
DTC=$KSRC/scripts/dtc/dtc

echo "==> 内核源码: $KSRC"

if [ -x "$DTC" ]; then
    echo "==> dtc 已存在: $DTC"
    $DTC --version
    exit 0
fi

echo "==> 检查工具链"
for t in gcc make flex bison; do
    command -v $t >/dev/null || { echo "缺少 $t，请先安装"; exit 1; }
done

echo "==> 生成 .config（scripts_dtc 需要）"
cd "$KSRC"
[ -f .config ] || make ARCH=arm64 fmsh_fmqlmp_defconfig

echo "==> 编译 dtc"
make scripts_dtc

if [ -x "$DTC" ]; then
    echo "==> 成功: $DTC"
    $DTC --version
else
    echo "==> 失败"
    exit 1
fi
