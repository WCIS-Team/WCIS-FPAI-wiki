#!/bin/bash
# SOP 2 hardware & base runtime env collection (read-only, safe)
set +e
OUT=/tmp/sop_hw_$(date +%Y%m%d_%H%M%S)
mkdir -p "$OUT/raw_logs"
cd "$OUT"
echo "$OUT" > .outdir
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "$TS" > collect_time.txt
echo "$(date +%z)" > collect_tz.txt

run(){
  local name="$1"; shift
  { echo "### $name"; echo "cmd: $*"; echo "---"; } > "raw_logs/$name.txt"
  bash -c "$*" >> "raw_logs/$name.txt" 2>&1
}

# ---- 3.1 device identity ----
run hostname "hostname; echo '---'; cat /etc/hostname 2>/dev/null"
run machine_id "cat /etc/machine-id 2>/dev/null; echo '---'; cat /var/lib/dbus/machine-id 2>/dev/null"
run board_release "cat /etc/fmsh* 2>/dev/null; ls /etc/*release* 2>/dev/null"
run uptime "uptime; echo '---'; cat /proc/uptime"

# ---- 3.2 / 3.5 CPU & OS ----
run uname "uname -a"
run os_release "cat /etc/os-release 2>/dev/null"
run lscpu "lscpu 2>/dev/null"
run nproc "nproc"
run cpuinfo "cat /proc/cpuinfo"
run cpu_topology "cat /sys/devices/system/cpu/possible 2>/dev/null; echo '---online:'; cat /sys/devices/system/cpu/online 2>/dev/null; echo '---present:'; cat /sys/devices/system/cpu/present 2>/dev/null"
run cpu_freq "for f in /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor; do echo -n \"\$f: \"; cat \$f 2>/dev/null || echo na; done"
run cpu_temp "for z in /sys/class/thermal/thermal_zone*/temp; do echo -n \"\$z: \"; cat \$z 2>/dev/null | awk '{print \$1/1000\" C\"}'; done"
run numa "numactl --hardware 2>/dev/null || echo 'numactl not installed (not_supported)'"

# ---- 3.3 memory & storage ----
run free "free -h; echo '---bytes---'; free -b"
run meminfo "cat /proc/meminfo"
run swap "swapon --show 2>/dev/null; echo '---'; cat /proc/swaps"
run zram "ls /dev/zram* 2>/dev/null; echo '---'; cat /proc/mounts | grep -i zram"
run cachesize "for c in /sys/devices/system/cpu/cpu0/cache/index*/size /sys/devices/system/cpu/cpu0/cache/index*/level /sys/devices/system/cpu/cpu0/cache/index*/type; do echo -n \"\$c: \"; cat \$c 2>/dev/null || echo na; done"
run df "df -h"
run findmnt "findmnt"
run lsblk "lsblk 2>/dev/null"
run partitions "cat /proc/partitions"
run model_disk "df -h / /root 2>/dev/null; echo '---'; mount | grep -E ' / | /root '"

# ---- 3.4 GPU/NPU/FPGA & other devices ----
run dev_list "ls -l /dev 2>/dev/null"
run lspci "lspci 2>/dev/null || echo 'lspci not installed (not_supported)'"
run lsusb "lsusb 2>/dev/null || echo 'lsusb not installed (not_supported)'"
run dmesg "dmesg 2>/dev/null | head -300"
run lsmod "lsmod 2>/dev/null"
run npu_zg330 "dmesg 2>/dev/null | grep -iE 'zg330|npu|icore' | head -40; echo '---dev---'; ls -l /dev/ | grep -iE 'zg330|npu|icore|axidma|fpga' ; echo '---sysfs---'; ls /sys/class/ 2>/dev/null | grep -iE 'npu|icore|zg'"
run fpga_mgr "ls /sys/class/fpga_manager/ 2>/dev/null; echo '---'; for d in /sys/class/fpga_manager/*; do echo -n \"\$d/state: \"; cat \$d/state 2>/dev/null; echo; done"
run dt_model "cat /proc/device-tree/model 2>/dev/null; echo; cat /proc/device-tree/compatible 2>/dev/null | tr '\\0' '\\n'"

# ---- 3.5 OS detail ----
run kernel "cat /proc/version; echo '---'; uname -r"
run init_container "echo 'cgroup1:'; head -3 /proc/1/cgroup 2>/dev/null; echo '---dockerenv:'; ls -la /.dockerenv 2>/dev/null || echo 'no /.dockerenv'; echo '---1.mountinfo:'; grep -E 'docker|kubepods|containerd' /proc/1/mountinfo 2>/dev/null | head -3 || echo 'no container markers'"

# ---- 3.6 software base ----
run python "for p in python python3 python2; do echo -n \"\$p: \"; \$p --version 2>&1 || echo na; done"
run pip "python3 -m pip --version 2>&1; echo '---list---'; python3 -m pip list 2>/dev/null | head -80"
run gcc "gcc --version 2>&1 | head -1; echo '---g++:'; g++ --version 2>&1 | head -1; echo '---cc:'; cc --version 2>&1 | head -1"
run cmake "cmake --version 2>&1 | head -1 || echo 'cmake na'"
run pkg_mgr "which apt apt-get dpkg yum dnf pip conda 2>/dev/null"
run icraft "which icraft 2>/dev/null && icraft --version 2>&1 | head -5 || echo 'icraft not found (unknown)'"
run inference_fw "ls /usr/lib/ 2>/dev/null | grep -iE 'icraft|npu|zg|fpai|tensor' ; echo '---'; ldconfig -p 2>/dev/null | grep -iE 'icraft|npu|zg|fpai' | head -20"
run env_vars "env | grep -iE 'npu|icore|fpga|zg|device|cuda|opencl|omp|thread|path' | sort"
run dpkg_count "dpkg -l 2>/dev/null | wc -l"

# ---- 3.7 limits & background load ----
run ulimit "ulimit -a"
run fd_limit "cat /proc/sys/fs/file-max; echo '---self:'; cat /proc/self/limits"
run cgroup_self "cat /proc/self/cgroup; echo '---mem limit:'; for f in /sys/fs/cgroup/memory/memory.limit_in_bytes /sys/fs/cgroup/memory.max; do echo -n \"\$f: \"; cat \$f 2>/dev/null || echo na; done"
run ps "ps -eLf 2>/dev/null | head -60"
run loadavg "cat /proc/loadavg; echo '---'; cat /proc/stat | head -1"
run mem_avail_sys "cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|Buffers|Cached'"

# ---- package inventory (raw) ----
run dpkg_list "dpkg -l 2>/dev/null | awk '/^ii/ {print \$2\" \"\$3}' | sort"

echo "COLLECT_DONE"
echo "OUTDIR=$OUT"
echo "FILES=$(ls raw_logs | wc -l)"
