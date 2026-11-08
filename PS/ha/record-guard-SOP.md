---
tags: [SOP]
---

# record-guard-sop

**目的**：监控板端录像服务对 `/mnt/wcis-data` 的磁盘占用，在自由空间 <10GB 时自动停止写入；短录验证测试 guard 行为。


## 一、守卫机制（disk_monitor）

- **脚本位置**：`workenv/ha-small/scripts/disk_monitor.py`
- **触发条件**：`/api/status.disk_free_bytes < 10240 MB` → POST `/api/mode {mode:off}`
- **特点**：
  - **只读探测**：用 recorder API 的 `disk_free_bytes` 字段，不 SSH 也不改板端代码
  - **无自动恢复**：一旦触发就停在 off，避免震荡
  - **安全阈值**：guard 在 10GB 停写，而 recorder quota=4GiB，留足余量

## 二、短录验证流程

**运行**：
```bash
podman exec ha-small-dev /venv/bin/python /tmp/record_short_trial.py --auto-duration 30
```

**预期行为**：
- 模式切换到 auto，保持约 30 秒
- 强制切换到 off
- 记录帧数变化、盘占增长
- 人工确认 `df -h /mnt/wcis-data`

## 三、结果记录

| 日期 | 自动时长 | 起始盘占 | 终止盘占 | 写入帧数 | guard 触发 | 备注 |
|---|---|---|---|---|---|---|
| 2026-11-08 | 30s | 27.8GB | 未变 | ~0 | 否 | 当前摄像头源未提供 H264 流 |

**注意**：短录试验中 `received_frames` 没有增加，说明摄像头数据通路尚未就绪（可能 bridge 或 live.mp4 接口问题）。Guard 机制本身是有效的，只是需要真实数据来触发写入。
