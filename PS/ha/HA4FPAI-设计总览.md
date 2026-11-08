---
tags: [index]
updated: 2026-11-08
---

# HA4FPAI-设计总览

综合 wiki 记录与源码实测，对 **HA4FPAI（整机，非单一子项目）** 做一次设计层面的整体梳理。
本页只做**总览与取舍判断**，判据与逐项证据链到各正本页，不复制其表格。

> **口径分层（重要）**：`ARCHITECTURE-OVERVIEW.md`＝**已实现现状**；`REFACTOR-ARCHITECTURE.md`＝**目标架构（未全部署）**；`REFACTOR-CHECKLIST.md`＝**实施状态唯一正本（复选框）**。本页按"现状为主、目标标注"叙述。

## 一、定位与边界

- **目标平台**：FMQL30TAI676H 悟净板——993MB RAM、4×Cortex-A53、256MB CMA、单 NPU、PL 可编程。
- **不是 Home Assistant 的替代**：补上 HA 负责的「**对话代理 + 意图执行器 + 实体表 + 状态查询**」那一层；HA 的长期平台特性（自动化调度、历史库、设备注册、多用户）**故意不做**。见 [ARCHITECTURE-OVERVIEW](../../../repos/HA4FPAI/docs/ARCHITECTURE-OVERVIEW.md)。
- **设计总纲**：**模块化单体**，不为分布式形式给 993MB 板子引入 Redis/Kafka/外置库；**控制面 / 数据面 / 媒体面分离**；业务权威＝SQLite，帧/音频/向量热路径不经业务库与 HTTP 转发。见 [REFACTOR-ARCHITECTURE](../../../repos/HA4FPAI/docs/REFACTOR-ARCHITECTURE.md) §1–§2。

## 二、子系统地图

| 目录 | 层 | 职责（详见） |
|---|---|---|
| `control/` | **控制面/业务权威** | SQLite 业务库：人员/样本/命令/任务/设置/事件/投影/回执，单写协调。见 [control/README](../../../repos/HA4FPAI/control/README.md) |
| `lang/` | **语音面** | 十级语音链 + 三入口（HTTP/Wyoming/麦克风），纯标准库核心。见 [lang/README](../../../repos/HA4FPAI/lang/README.md) |
| `lang/npuserv/` | **推理服务** | 单 device 多 session 的 NPU 管家（Supervisor / ResidentSupervisor）。见 [COEXISTENCE](../../../repos/HA4FPAI/docs/COEXISTENCE.md) |
| `klar/` | **NLU + 执行器** | Rust klar engine（确定性 NLU）+ 双通道 executor + entity/area registry。见 [klar/README](../../../repos/HA4FPAI/klar/README.md) |
| `boards/` | **板端 API/门禁** | console 主页面、door_unlock 四道闸、voiceprint 声纹 |
| 视频域（跨仓） | **数据面/媒体面** | camera_owner / face_cached / vpu_live 三 C++ 进程 + 四模型 NPU 链。见 [VIDEO-NPU-PIPELINE](../../../repos/HA4FPAI/docs/VIDEO-NPU-PIPELINE.md) |
| `web/` | **展示面** | ggradio 语音试验台、offlineHMI（HDMI 原生界面） |
| `ha/` | **子项目** | ha-small：Home Assistant Core 2026.10.4 子集裁剪（见 [[09-裁剪后设计总览]] 系列） |
| `deploy/` `ci/` `archiver/` | **运维/验证** | systemd 单元、多档 CI（quick/full/board/no-npu）、旧实现归档 |

## 三、一条主线的数据流

```
语音入口(HTTP 18091 / Wyoming 10300-2 / mic loop)
  → 十级链 sar→rms→kws→kws_route→vad→asr→router→llm→tokenizer→tts → (SAR 48k 回采)
  → 文本 → klar_executor 双通道(B 直连命令表 ~0ms / A klar NLU ~25ms)
  → 归一为 (动作, slots)
  → [统一路径] control HTTP /v1/commands（幂等/状态机/确认）→ 域适配器
        ├→ 视频域 HTTP（8091 识别 / 8092 状态 / 8093 录制）── 三 C++ 进程 + NPU
        └→ 板内动作（system.time 等）
  → 结果/回执 outbox → inbox → 业务库投影 → TTS 念出
```
开门另走 **door_unlock 四道闸**：口令文本 → NPU 人脸 → PAD 防伪 → 声纹（campplus-zh）。

## 四、逐子系统设计要点

- **control/**：`store/schema`（WAL/FULL/FK/busy_timeout、版本化迁移 checksum、`store_id/generation/restore_epoch/domain_revision`）；`persons/samples`（person_id 稳定、名字不是键、样本带模型指纹、显式 LE FP32）；`settings`（**desired/applied 分离**，(scope,epoch,revision) 防乱序）；`commands`（状态机 + 幂等键 + 危险确认绑定 + unknown）；`events`（producer_id+seq 游标）；`outbox`（不可变快照 + current 原子切换 + 消费游标防倒退）；`tasks`（(task_id,occurrence) 唯一）。**目标**：单写协调器 + 有界队列 + 只读快照；当前"独立 worker 另开 App 写库"是待修缺陷（A02）。
- **lang/**：三入口 + **十级可插拔链**（每级多档）；**单 onnx 运行时**（sherpa 自带 ORT，禁第二份）；核心纯标准库；spk 默认不入链（出 `action=verify` 才装当前段）。
- **npuserv/**：ZG session 绑进程、CMA 只在进程退出全归还 ⇒"放下"=杀 child；**ResidentSupervisor** 单 worker 单 device 多 session；核心规则 **`openDevice()` 每进程一次**；adapter 契约 `load(params, device=None)`；退出回收 worker（watchdog）。
- **klar/**：engine 是**确定性 NLU 解析器**（不执行/不识别语音/不存状态）；`make_registry.py` 出 entity+area 两层 JSON；executor **双通道**。
- **视频域**：三 C++ 进程 = 会话隔离（camera_owner SDI 唯一持有 / face_cached NPU 单持有 / face_pl_retained PL 预处理）；四模型 yunet/mobileface/minifasnet（fp16/SFB/3.39.0）；`models.json` sha256 寻址、`pipeline_id` 即 gallery 目录名前 16 位；与 npuserv 是 HTTP 客户端，不共享 session。

## 五、跨切面设计规则（贯穿全栈）

| 切面 | 规则 |
|---|---|
| **NPU** | `openDevice` 每进程一次；同 device 多 session 可叠可重建；**LLM apply ↔ 相机 CMA 互斥**（apply 把 CmaFree 130→1.6MB → 相机 DMA 死 → quarantine） |
| **内存四条预算线** | ①NPU 会话 ②主存 ΣRSS ③**CMA（真正共存开关）**④CPU 抢核（分核有效）。见 [COEXISTENCE](../../../repos/HA4FPAI/docs/COEXISTENCE.md) |
| **语音** | 单 onnx 运行时；十级可插拔；spk 默认不入链；采样率归 SAR |
| **一致性** | 幂等键 + outbox 至少一次 / inbox 去重 + 世代 epoch 不越代 + 重启先问域结果不盲重放 |
| **发布** | Actions **只手动 workflow_dispatch**；deb 离线安装；systemd **手动 enable** |
| **许可** | ha-small 零补丁 ⇒ 免 Apache-2.0 §4(b)；"Home Assistant" 商标属 Nabu Casa，对外用 ha-small |

## 六、现状实测（板 113，2026-11-08）

- **服务本体 ≈18MB**（control 4.4 / klar 5.3 / lang 8.5）；qwen3 K128 worker +290MB；磁盘 ≈3.5GB（qwen3 两套件 3GB 是大头）。详见 [[HA4FPAI-运行时内存RSS实测]]。
- 视频链 ≈157MB（serve_photos 77 + camera_owner 43 + recording 20 + vpu_live 17）+ ffmpeg 134MB。
- 已验收：C06 klar registry 消费、HiFi-GAN CORR 0.9996、ERNIE 多轮、K128 2.13 tok/s、29 项视觉合同测试、resident worker 退出回收。见 [[HA4FPAI-2026-11-07-08-NPU优化轮]]。

## 七、与 ha-small（[[09-裁剪后设计总览]]）的关系

`09-裁剪后设计总览` 的标题与正文都限定 **"裁剪后的 ha-small"**（Home Assistant 子项目），**不是**整机 HA4FPAI 的总览。作为 ha-small 切片它扎实、边界诚实；但作为"整机设计总览"它未覆盖下列点（本页补齐）：

| 09 未覆盖 | 归属 | 本页对应 |
|---|---|---|
| control 业务权威层（库/人员/样本/命令/设置/事件/outbox/tasks/receipts） | control/ | §二、§四 |
| 语音链 lang 三入口 + 十级链 + 单运行时 | lang/ | §三、§四 |
| npuserv / NPU 推理（resident、openDevice 单次、watchdog、runtime 比对） | lang/npuserv | §四、§五 |
| klar NLU + 双通道 executor + registry | klar/ | §四 |
| 视频域视觉链（三进程 + 四模型 pipeline + sha256/pipeline_id） | 跨仓 | §四 |
| boards 门禁四道闸 + 声纹 | boards/ | §三 |
| 四条预算线 + 共存矩阵（含 CMA 互斥） | COEXISTENCE | §五 |
| 整机内存/磁盘口径（18MB 静置/290MB qwen3/157MB 视频/3GB 盘） | RSS 实测 | §六 |
| 一致性/世代模型（outbox-inbox、epoch、幂等、恢复） | REFACTOR-ARCHITECTURE §2–3 | §五 |
| 部署体系（systemd 单元集、control/lang deb、多档 CI） | deploy/ ci/ | §二 |
| web/ggradio 试验台 + offlineHMI | web/ | §二 |

**反向值得从 09 纳入整机总览的两点**：①**Python ≥3.14.2 / 板端 3.8 跑不了 HA** ⇒ HA 只在本机/容器跑、板端只出流；②**"裁剪省的是攻击面，不是磁盘/RSS"**（加载了什么 vs 盘上有什么）——对整机任何"减负"决策都适用。

## 相关

- 逐子系统细节：`control/README` · `lang/README` · `klar/README` · [COEXISTENCE](../../../repos/HA4FPAI/docs/COEXISTENCE.md) · [VIDEO-NPU-PIPELINE](../../../repos/HA4FPAI/docs/VIDEO-NPU-PIPELINE.md) · [DEPLOY-CONTROL](../../../repos/HA4FPAI/docs/DEPLOY-CONTROL.md)
- 目标架构与状态正本：`REFACTOR-ARCHITECTURE.md` · `REFACTOR-CHECKLIST.md`
- 子项目：[[09-裁剪后设计总览]]（ha-small）· [[00-ha-cut总览]]
- 实测记录：[[HA4FPAI-运行时内存RSS实测]] · [[HA4FPAI-2026-11-07-08-NPU优化轮]] · [[HA4FPAI-CI开发记录]]
