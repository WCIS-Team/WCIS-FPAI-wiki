---
tags: [SOP]
updated: 2026-11-08
---

# HA4FPAI-运行时内存RSS实测

**实测对象**：HA4FPAI 控制/推理栈（control + klar + lang-server + npuserv）在开发板 `192.168.1.113`
（FMQL30TAI676H，994 MB 内存 / 256 MB CMA）上的常驻占用。**这是整机 HA4FPAI 部分**，与
[[07-运行时内存RSS实测|ha-cut 07]]（那是 Home Assistant 主进程，另一套系统）互补，互不重叠。

## 实测数据（2026-11-08，板上现役服务，未装模型）

| 组件 | RSS | 进程数 | 说明 |
|---|---|---|---|
| control | 4.4 MB | 1 | `control.service`（127.0.0.1:18100，业务库/投影） |
| klar-nlu-engine | 5.3 MB | 1 | Rust 引擎（`MemoryMax=256M` 是上限，实测只 5.3M） |
| lang-server | 8.5 MB | 3 | loop 4.4 + wyoming_gateway 2.8 + app 1.3 |
| npuserv worker | 0 MB | 0 | 未 `/load` 时无 worker |
| **服务本体合计** | **18.1 MB** | | 这才是 HA4FPAI “静置”占的内存 |

同期整机读数：`MemTotal 994M / MemFree 409M / MemAvailable 614M / CmaFree 84M / SwapUsed 132M`。

## 装模型时的增量（真正吃内存的部分）

| 件 | 增量 | 备注 |
|---|---|---|
| Qwen3-0.6B K128 常驻 worker | **+290 MB** | `resident_worker.py` 装上后实测 290 MB |
| ERNIE-4.5-0.3B | ≈300 MB | 与 qwen3 不能同时装（993MB 内存装不下两个 LLM） |
| HiFi-GAN | 小 | 图小，可叠在任一 LLM 旁 |

⇒ **HA4FPAI 的内存在“装了什么模型”上，不在“代码树有多大”上**（与 ha-cut 07 的机制结论一致：
RSS 由加载了什么决定，裁剪代码几乎不省运行时内存）。不装模型时整套服务只 18 MB。

## 磁盘构成

| 路径 | 大小 | 内容 |
|---|---|---|
| `/root/qwen3` | **3.0 GB** | K128 + 512 两套件（各约 1.5 GB，json+raw） |
| `/var/lib/lang-server` | 444 MB | venv + 下载的 ASR/TTS/VAD/KWS 模型 |
| `/usr/lib/lang-server` | 35 MB | lang 代码 |
| `/mnt/data/klar` | 8.2 MB | klar engine(8.5MB ELF) + registry |
| `/var/lib/ha4fpai-control` | 1.3 MB | control 业务库 |
| `/usr/lib/ha4fpai-control` | 440 KB | control 代码 |
| `/root/npuserv` | 1.8 MB | npuserv 代码 + state |
| **合计** | **≈3.5 GB** | 整机盘 26G，已用 18G，剩 7G |
| 磁盘大头 | qwen3 两套件 | 若只留 K128 一套可省 ~1.5 GB |

## 事故记录：npuserv 孤儿 worker 泄漏（2026-11-08 发现并清理）

**现象**：核占用时发现板上挂着 **5 个 `resident_worker.py` 进程**，全部 `ppid=1`、
启动于 4–5 小时前、**没有对应的 `server.py` 在跑**（`ss -ltn` 无 18080 监听）。

**根因**：此前多轮测试用 `setsid python3 server.py --resident &` 起服务，再用
`pkill -f "port 18080"` 杀服务；`setsid` 让 worker 脱离会话（`ppid→1`），服务被 SIGKILL 时
来不及回收 worker，于是 worker 成孤儿继续存活、且**仍占着 NPU 设备内存**。

**清理前后对比（同一次测量，`SIGTERM`→`SIGKILL` 5 个孤儿）**：

| 指标 | 清前 | 清后 |
|---|---|---|
| MemFree | 115 MB | **409 MB** |
| MemAvailable | 299 MB | **614 MB** |
| SwapUsed | 869 MB | **132 MB** |
| CmaFree | 75 MB | 84 MB |
| npuserv worker | 5 个 / 311 MB | **0 个 / 0 MB** |

（swap 掉 737 MB 是孤儿进程自己的换出页随进程退出被释放——不是 swapoff 的效果。）

**修复（2026-11-08 已落地并板端验证）**：

1. `server.py`：装 `SIGTERM`/`SIGINT` 处理 → 在独立线程 `httpd.shutdown()`，`finally` 调
   `ResidentSupervisor.shutdown()`（真 `_reap` worker 进程）。**根因**：旧 `unload()` 只卸模型
   会话、**不杀 worker 进程**，所以即便优雅退出也留孤儿。
2. `resident_worker.py`：加父进程看护守护线程——`getppid()` 变化（父死→重挂 PID 1）即
   `os._exit(0)`，覆盖服务被 `SIGKILL`（信号处理跑不到）的路径。

**验证（板 113，`tts-hifigan-v2` 0.4s 快装）**：`--resident` 起服 → `/load` 后 1 个 worker →
① `kill -TERM` 服务，6s 后 worker=0；② `kill -KILL` 服务，6s 后 worker=0（看护自退）。
两条路径都不再留孤儿。

**清理手法**（修好前遗留或任何时侯手工清）：`pkill -f resident_worker.py`（先 TERM、复核残留
再 KILL），清完 `free -m` 复核。

## 可动杠杆（省内存/磁盘往哪使劲）

| 目标 | 杠杆 | 代价 |
|---|---|---|
| 省内存（最大项） | `/unload` 掉 Qwen3 worker（省 290 MB） | 失去 LLM 推理，要用再 `/load` |
| 省磁盘（最大项） | 只留 Qwen3 K128 一套，删 512 旧套件 | 省 ~1.5 GB |
| 少 swap | 不装大模型时常驻即 18 MB，swap 自然回落 | 无 |
| 降 CMA 占用 | 相机/视频链在用 CMA（DMA 池），非 HA4 本体 | 无（本体不吃 CMA） |

## 测量方法（可复现）

板上直接跑（把下面存成 `usage.py`，`python3 usage.py`）：

```python
import os, subprocess
def rss(pid):
    for l in open('/proc/%s/status' % pid, encoding='ascii', errors='ignore'):
        if l.startswith('VmRSS:'): return int(l.split()[1]) / 1024.0
G = {'control': [], 'klar': [], 'lang': [], 'npuserv': []}
for pid in os.listdir('/proc'):
    if not pid.isdigit(): continue
    try: cmd = open('/proc/%s/cmdline' % pid,'rb').read().decode('utf-8','ignore').replace('\0',' ')
    except OSError: continue
    r = rss(pid)
    if r is None: continue
    if 'ha4fpai-control' in cmd: G['control'].append(r)
    elif '/mnt/data/klar/engine' in cmd: G['klar'].append(r)
    elif '/lang-server' in cmd: G['lang'].append(r)
    elif '/root/npuserv' in cmd: G['npuserv'].append(r)
for g, v in G.items(): print('%-9s %6.1f MB' % (g, sum(v)))
```

判据：按 `cmdline` 归组件、取 `/proc/<pid>/status` 的 `VmRSS`；npuserv 在 `--resident`
模式下应对应**一个** worker（多于一个且 `ppid=1` 即孤儿，见上节事故）。

## 一句话

**HA4FPAI 服务本体只占 ≈18 MB 内存 + ≈3.5 GB 磁盘（qwen3 两套件就 3 GB）；真正吃内存的是
装模型时的 worker（qwen3 K128 = 290 MB）——省内存要 `/unload`，不在裁代码。**
