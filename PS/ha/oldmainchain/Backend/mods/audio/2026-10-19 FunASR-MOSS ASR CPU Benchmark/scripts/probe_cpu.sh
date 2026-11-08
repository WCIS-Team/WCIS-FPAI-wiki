#!/bin/bash
echo "=== CPU model ==="
grep -m1 "model name" /proc/cpuinfo
echo "=== CPU MHz (current) ==="
grep -m1 "cpu MHz" /proc/cpuinfo
echo "=== logical processors ==="
grep -c processor /proc/cpuinfo
echo "=== power scheme ==="
powercfg /getactivescheme
echo "=== core count (physical) ==="
grep -m1 "cpu cores" /proc/cpuinfo
echo "=== hypervisor ==="
grep -m1 "hypervisor" /proc/cpuinfo
