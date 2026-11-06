#!/bin/bash
# SOP 2 follow-up collection: fills gaps found in the first pass.
# Read-only: no config change, no reboot, no process kill, no benchmark.

OUTDIR="${1:-/tmp/sop_hw_followup}"
mkdir -p "$OUTDIR/raw_logs"
RAW="$OUTDIR/raw_logs"

run() {
  name="$1"; shift
  {
    echo "### $name"
    echo "cmd: $*"
    echo "---"
  } > "$RAW/$name.txt"
  "$@" >> "$RAW/$name.txt" 2>&1
}

run_sh() {
  name="$1"; shift
  {
    echo "### $name"
    echo "cmd: $*"
    echo "---"
  } > "$RAW/$name.txt"
  sh -c "$*" >> "$RAW/$name.txt" 2>&1
}

date -u +%Y-%m-%dT%H:%M:%SZ > "$OUTDIR/collect_time.txt"
date +%z > "$OUTDIR/collect_tz.txt"

# 1. Full dmesg (first pass was truncated to 300 lines)
run_sh dmesg_full "dmesg 2>/dev/null | cat"
run_sh dmesg_tail "dmesg 2>/dev/null | tail -120"
run_sh dmesg_accel "dmesg 2>/dev/null | grep -iE 'mve|linlon|arm china|china|mali|bifrost|amvx|zg330|icore|npu|fpga|axi|dma'"

# 2. Cache sizes (first pass glob did not expand)
run_sh cache_sizes "for i in 0 1 2 3; do for a in level type size ways_of_associativity coherency_line_size; do p=/sys/devices/system/cpu/cpu0/cache/index\$i/\$a; echo -n \"\$p: \"; cat \$p 2>/dev/null || echo na; done; done"
run_sh cache_shared "for i in 0 1 2 3; do p=/sys/devices/system/cpu/cpu0/cache/index\$i/shared_cpu_map; echo -n \"\$p: \"; cat \$p 2>/dev/null || echo na; done"

# 3. CPU frequency alternatives (no cpufreq driver present)
run_sh cpu_clock "ls /sys/devices/system/cpu/cpu0/ 2>/dev/null; echo '---clocksource:'; cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null; echo '---opp:'; ls /proc/device-tree/cpu@0/ 2>/dev/null"

# 4. Network
run_sh net_addr "ip -o addr show 2>/dev/null || ifconfig -a 2>/dev/null"
run_sh net_link "ip -o link show 2>/dev/null || ifconfig -a 2>/dev/null"
run_sh net_route "ip route show 2>/dev/null; echo '---resolv:'; cat /etc/resolv.conf 2>/dev/null"
run_sh net_sysfs "for n in /sys/class/net/*; do echo \"== \$n\"; for a in address speed duplex mtu operstate carrier type; do echo -n \"  \$a: \"; cat \$n/\$a 2>/dev/null || echo na; done; done"
run_sh net_ethtool "which ethtool >/dev/null 2>&1 && ethtool eth0 2>/dev/null || echo 'ethtool not installed'"

# 5. VPU (video codec: mve / Linlon V5276 / amvx) presence and driver state.
#    NOT the NPU: the ZG330 iCore lives in the PL and has no device-tree node at all
#    (grep the flattened dtb for npu|aiu|zhuge|icore -> 0 hits), no kernel module and
#    no /dev node; the only "vpu" node in the tree is this codec. Fixed up 2026-10-23,
#    D-79. The run_sh names below still say "npu_*" on purpose: they are the raw log
#    file names the 2026-10-18 archive was built with, and renaming them would orphan
#    every evidence path that cites npu_platform.txt / npu_dev.txt / npu_module.txt.
run_sh npu_mve "ls -d /proc/device-tree/mve* 2>/dev/null; for d in /proc/device-tree/mve*; do echo \"== \$d\"; ls \$d 2>/dev/null; echo -n 'status: '; cat \$d/status 2>/dev/null; echo; done"
run_sh npu_platform "ls /sys/bus/platform/devices/ 2>/dev/null | grep -iE 'mve|china|npu|zg|icore|amvx|axidma|dma'"
run_sh npu_dev "ls -l /dev/ 2>/dev/null | grep -iE 'mve|npu|zg|icore|amvx'"
run_sh npu_module "lsmod 2>/dev/null | grep -iE 'mve|china|npu|zg|icore|amvx|axidma|u_dma'; echo '---modules.dep grep:'; grep -iE 'mve|china|npu|zg330' /lib/modules/$(uname -r)/modules.dep 2>/dev/null | head -20 || echo 'no match in modules.dep'"

# 6. FPGA manager detail
run_sh fpga_detail "for a in state name firmware status; do echo -n \"\$a: \"; cat /sys/class/fpga_manager/fpga0/\$a 2>/dev/null || echo na; done; echo '---firmware dir:'; ls -R /sys/firmware 2>/dev/null | head -30"
run_sh fpga_bridge "ls /sys/class/fpga_region/ 2>/dev/null; for r in /sys/class/fpga_region/*; do echo \"== \$r\"; cat \$r/ compat 2>/dev/null; done"

# 7. GPU (Mali) detail
run_sh mali_gpu "ls -l /dev/mali* 2>/dev/null; echo '---sysfs misc:'; ls /sys/class/misc/ 2>/dev/null | grep -i mali; echo '---drm:'; ls /sys/class/drm/ 2>/dev/null; echo '---gpu props:'; for p in /sys/kernel/debug/gpu/*/; do echo \"== \$p\"; cat \$p/gpuinfo 2>/dev/null; done"

# 8. QSPI / NOR flash
run_sh mtd_flash "cat /proc/mtd 2>/dev/null; echo '---dmesg spi:'; dmesg 2>/dev/null | grep -iE 'spi|qspi|nor|flash' | head -20"

# 9. cgroup v2 limits (first pass only tried v1 paths)
run_sh cgroup_v2 "for f in /sys/fs/cgroup/unified/memory.max /sys/fs/cgroup/unified/memory.high /sys/fs/cgroup/unified/cpu.max /sys/fs/cgroup/unified/pids.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.high /sys/fs/cgroup/cpu.max /sys/fs/cgroup/pids.max; do echo -n \"\$f: \"; cat \$f 2>/dev/null || echo na; done; echo '---self cgroup v2:'; cat /proc/self/cgroup"

# 10. PCI / PCIe
run_sh pci_sysfs "ls /sys/bus/pci/devices/ 2>/dev/null; echo '---proc bus pci:'; ls /proc/bus/pci/ 2>/dev/null; echo '---pci resources:'; for d in /sys/bus/pci/devices/*; do echo \"== \$d\"; cat \$d/vendor 2>/dev/null; cat \$d/device 2>/dev/null; cat \$d/class 2>/dev/null; done"

# 11. Hugepages and shm limits
run_sh hugepages "ls /sys/kernel/mm/hugepages/ 2>/dev/null; for d in /sys/kernel/mm/hugepages/*; do echo -n \"\$d free: \"; cat \$d/free_hugepages 2>/dev/null; echo -n ' size: '; cat \$d/hugepagesize 2>/dev/null; done; echo '---shm:'; df -h /dev/shm 2>/dev/null"

# 12. Full platform device inventory (SoC peripherals)
run_sh platform_devices "ls /sys/bus/platform/devices/ 2>/dev/null"

# 13. Vendor package inventory
run_sh dpkg_vendor "dpkg -l 2>/dev/null | grep -iE 'fmsh|icraft|zg330|mali|amvx|npu|fpga|fpa' | head -40"

# 14. Device-tree model and serial number nodes
run_sh dt_serial "for p in serial-number model board-name; do echo -n \"\$p: \"; cat /proc/device-tree/\$p 2>/dev/null | tr '\0' ' '; echo; done; echo '---dt root:'; ls /proc/device-tree/ 2>/dev/null | head -40"

# 15. Clocksource and timer
run_sh clocksource "cat /sys/devices/system/clocksource/clocksource0/available_clocksource 2>/dev/null; echo '---current:'; cat /sys/devices/system/clocksource/clocksource0/current_clocksource 2>/dev/null"

# 16. Running process snapshot for background load assessment
run_sh ps_snapshot "ps -eo pid,ppid,user,pcpu,pmem,rss,etime,comm --sort=-pcpu 2>/dev/null | head -30; echo '---thread count:'; ps -eLf 2>/dev/null | wc -l"

echo "COLLECT_DONE"
echo "OUTDIR=$OUTDIR"
find "$RAW" -type f | wc -l
