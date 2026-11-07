---
tags: [SOP]
updated: 2026-11-08
---

# 07-运行时内存（RSS）实测

## 实测数据（2026-11-08，x86 容器内 /venv/bin/hass -c /runtime）

| 进程 | RSS | 说明 |
|---|---|---|
| **HA 主进程** | **253.3 MB** | `/proc/<pid>/status` 的 VmRSS，单进程 |
| ffmpeg 子进程 ×2 | 60.0 MB | 22 MB（mediamtx RTSP 测试流）+ 38 MB（板端摄像头桥） |
| **合计** | **~313 MB** | 实验室全功能配置（摄像头流 + mqtt + rest + tts + recorder） |

## 内存构成拆解（估算，非逐项实测）

| 构成 | 估计 | 依据 |
|---|---|---|
| Python 解释器 | ~50 MB | CPython 基础开销 |
| HA 核心框架 | ~80 MB | 事件循环/HTTP/WebSocket/实体注册表 |
| 已加载集成 | ~60 MB | generic/stream/mqtt/rest/wyoming/recorder 等**实际启用**的 |
| 前端服务 | ~40 MB | hass_frontend 静态资源缓存 |
| recorder/numpy | ~20 MB | SQLAlchemy 连接池 + 统计计算 |

## 关键事实：裁剪为什么几乎不省运行时内存

**删掉的 11 个集成对运行时 RSS 的贡献 ≈ 0**，原因：

1. 它们不在 `configuration.yaml` → HA 启动时**从不 import** → 进程里没有它们
2. 运行时内存由「**加载了什么**」（配置决定）决定，与「**盘上有什么**」（代码树）无关
3. 裁剪省的是**磁盘**（几 MB）与**攻击面**（少 11 个入口），不是内存

## 内存大头与可动杠杆

| 大头 | 量级 | 能否减 | 代价 |
|---|---|---|---|
| ffmpeg 子进程（每流 20–40 MB） | 60 MB（2 流） | ✅ 关流即省 | 无视频功能 |
| hass_frontend | 磁盘 269 MB / 内存 ~40 MB | ⚠ 需换轻量前端 | UX 大幅下降 |
| recorder + numpy | ~20 MB | ✅ 禁用 recorder | 失去历史/统计 |
| botocore（盘 31 MB） | 内存中小 | ⚠ 深度定制 wheel | 逐包验证 |

## 未完成的实验（如实记录）

曾设计三阶段实验（A 全功能 → B 纯核心 → C 最简 http+api，同代码树只换 configuration.yaml，
用 `/proc/<pid>/status` VmRSS 统一测），**Phase B 启动失败未得出数据**：实验室只读传感器
`sensor.board_frame_age` 在流不新鲜时状态为空字符串，触发 HA 传感器数值校验
`ValueError: ... indicating it has a numeric value; however, it has the non-numeric value: ''`，
进程起不来。脚本留存 `workenv/ha-small/memory_experiment.py`、`memory_clean_experiment.py`，
复跑前需先修传感器模板（`value_template` 加 `| int(0)` 之类的容错）或把 board-readonly 移出最小配置。

## 对照：磁盘体积的真相

| 项 | 大小 | 与裁剪的关系 |
|---|---|---|
| hass_frontend | 269 MB | 独立 wheel，集成裁剪动不了 |
| av + av.libs（FFmpeg 二进制） | 127 MB | 原生依赖，动不了 |
| homeassistant（Python 源） | 73 MB | 裁 11 个集成只减其中几 MB |
| numpy + libs | 60 MB | recorder 链路依赖 |
| **venv 合计** | **759 MB** | 与 128 集成时基本相同 |

**一句话**：裁剪的收益是**攻击面、维护面、启动加载面**，不是磁盘也不是 RSS；要省 RSS 得关功能（config 层），要省磁盘得动 wheel（依赖层），两者都不在「删集成」这个杠杆上。

## 测量方法（可复现）

```bash
podman exec ha-small-dev /venv/bin/python - <<'PY'
from pathlib import Path
for e in Path('/proc').iterdir():
    if not e.name.isdigit(): continue
    try: cmd=(e/'cmdline').read_bytes().decode('utf-8','replace').replace('\0',' ')
    except OSError: continue
    if '/venv/bin/hass' not in cmd: continue
    rss=[l for l in (e/'status').read_text().splitlines() if l.startswith('VmRSS')][0]
    print(e.name, int(rss.split()[1])//1024, 'MB')
PY
```

判据：HA 主进程单行 VmRSS；ffmpeg 子进程单独计（它们是 stream/generic 拉起的真子进程，属功能成本）。
