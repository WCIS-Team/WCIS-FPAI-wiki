---
tags: [SOP]
updated: 2026-11-08
---

# 06-ARM64与qemu验证

## 环境层事实

- **本机 x86_64**（podman 容器）：`uname -m = x86_64`
- **aarch64 模拟**：`echo ':qemu-aarch64:...|...> /proc/sys/fs/binfmt_misc/register` 后，`podman run --arch arm64 ...` 能跑原生 aarch64 镜像
- **板端真实 aarch64**：FMQL30TAI676H（993 MB RAM，Python 3.8），装不了 HA 3.14 基线

## ARM64轮子构建

### x86 交叉编译的坑

`export _PYTHON_HOST_PLATFORM=linux_aarch64` 只改**文件名**，不改`.so` 实际架构；
在 `arm64` wheel 里解压出 `.so` → ELF `machine=62 (x86_64)` → 导入即报错。

### 正确方式

在 **aarch64 容器内原生编译**：
```bash
podman run --rm --platform linux/arm64 python:3.14-slim \
  bash -c "apt-get update && apt-get install -y g++ make cmake libspeexdsp-dev" && \
  pip wheel pymicro_vad==1.0.1 pyspeex_noise==1.0.2 --no-deps --no-build-isolation -w /out
```
输出：`pymicro_vad-1.0.1-cp314-cp314-linux_aarch64.whl`、`pyspeex_noise-1.0.2-cp314-cp314-linux_aarch64.whl`
（ELF machine=183 EM_AARCH64）。

### 完整 wheelhouse

- 50+ 运行时依赖纯 Python 轮（pip download）
- 2 个带 C++ 扩展的原生 aarch64 轮（上面步骤）
- 总计 **118 集成对应全部依赖**可离线安装

## deb安装+启动验证

### 步骤

1. podman 容器装 Debian 13 + docker.io/dpkg
2. `dpkg -i ha-small_0.1.0_all.deb`（`--force-depends` 绕过 python3.14 依赖检查）
3. `/opt/ha-small/bin/hass-setup`（选 python3.14 venv）
4. `systemctl enable --now ha-small` 或 `ha-small` 直接启动

### 结果

```bash
/homeassistant # /opt/ha-small/bin/python -c "print(platform.machine())"
aarch64
/opt/ha-small/bin/hass --script check_config -c /cfg
exit code 0; grep -icE "Integration error/not found" -> 0
# frontend 200, /api/ 401
```

**结论**：ARM64 原生环境下完整安装 + 校验通过，HA 前端可访问。

## 相关

- 证据：`cut/results/arm64-runtime.json`, `cut/results/arm64-native-wheels.json`
- 脚本：`workenv/ha-small/arm64_*.py`
