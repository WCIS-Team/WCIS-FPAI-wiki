---
tags: [index]
---

# RELEASE-0.1.0

## 构建产物

| 文件 | 大小 | SHA256 | 备注 |
|---|---|---|---|
| `ha-small-0.1.0-source.tar.gz` | 6,850,596 B | `04f014cccc00635bb3d29e5cb24afb0ecf6b482716c99401784381ae1f12826e` | 源码包（含 cut/示例配置） |
| `homeassistant-2026.10.4-py3-none-any.whl` | 8,280,826 B | `6bd60dc72c88312185fd5563c1d6f30ddd968b9aa0d4c1c57d4c638f1b0f5c2b` | x86_64 wheel（128→117 集成） |
| `ha-small_0.1.0_all.deb` | 7,366,076 B | `c56af67a74a4507f26daa04659009993bf901e3aac31fbec4da802d809c841a8` | deb 包（含 HA 安装脚本 + 录像守护） |

## 裁剪详情

- **集成数**：从 Home Assistant Core 2026.10.4 的 **128 → 117**（移除 11 个叶子集成）
- **保留核心**：`generic/mqtt/rest/rest_command/counter/wyoming` 等已验收功能支柱
- **验证**：干净 venv 安装 + check_config(零错) + pip check(干净) + 30/30 功能回归

## 新增功能

- **录像控制守护**：在盘占 <10GB 时自动切换 recorder 为 off（只读 API + 安全 POST）
- **mTLS 支持**：客户端证书认证 + broker 强制验证
- **转接设备**：MQTT 自动发现 + LWT 遗嘱 + 事件实体
- **弱网测试**：netem 模拟丢包延迟，HA 重连成功

## 使用方式

### 安装（本地容器）
```bash
podman run -d --name ha-small python:3.14-slim sleep infinity
podman cp homeassistant-2026.10.4-py3-none-any.whl ha-small:/tmp/
podman exec ha-small /venv/bin/pip install /tmp/homeassistant-2026.10.4-py3-none-any.whl
```

### 安装（板端/Debian）
```bash
sudo dpkg -i ha-small_0.1.0_all.deb
sudo /opt/ha-small/bin/hass-setup
```

### 运行（守护模式）
```bash
python -B /scripts/disk_monitor.py --host 192.168.1.113 --port 8093
```

## Actions 流程

- **手动触发**：Go to GitHub → WCIS-Team/HA4FPAI → Actions → Run workflow
- **无 CI 自动化**：按项目规定，Actions 仅由人触发（非 CI/CD）
- **Release 标记**：推送到远端后由人工打 tag

## 边界与注意

- **Python 版本**：要求 >=3.14.2（板端只有 3.8，不可装）
- **mTLS 证书**：实验室 CA 有效期 30 天，生产需替换
- **guard 阈值**：默认 10GB，可根据实际需求调整脚本参数
- **摄像头源**：当前 bridge 依赖 live.mp4 接口，需确保板端服务就绪

## 证据材料

- 功能探针：`cut/results/{functional,board-*,mqtt-*.json}`
- 文档：[[record-guard-sop]], `cut/BUILD.md`
- 审计：`cut/source-audit.json`, `cut/cut-report.json`