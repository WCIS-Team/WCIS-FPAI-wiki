---
tags: [SOP]
updated: 2026-11-03
---

# Wyoming协议与klar接入

> 讲清三件事：**板上三条语音服务用的标准协议是什么、怎么调**；**klar 在链路里怎么被用**；
> **语言包为什么生硬、怎么改**。
>
> 全部读数来自 2026-11-03 板端实测（`192.168.1.113`）。

## 一、Wyoming 协议：不是自造的，是标准 PyPI 包

| 项 | 实测值 |
|---|---|
| 包名 | `wyoming` |
| 版本 | **1.10.2** |
| 板上路径 | `/root/.local/lib/python3.8/site-packages/wyoming` |
| 模块数 | 24 个 |

提供的协议模块（`pkgutil.iter_modules` 实测）：

```
asr  audio  client  error  event  handle  http  info  intent  mic
ping  pipeline  pyaudioop  satellite  server  snd  timer  tts
user_event  util  vad  version  wake  zeroconf
```

**我们只用其中三个域**：`asr`（语音转文字）、`tts`（文字转语音）、`wake`（唤醒词）。
其余 `intent` / `satellite` / `pipeline` / `mic` / `snd` / `timer` 是 HA Assist 生态里的其它角色，本板没启用。

### 1.1 三个端口怎么起的

`boards/voice_gateway.py` —— **一个进程、一个事件循环、三个 `AsyncServer`**：

```python
from wyoming.server import AsyncEventHandler, AsyncServer

server = AsyncServer.from_uri("tcp://0.0.0.0:10301")   # 三端口同一进程
await server.start(lambda r, w: AsrHandler(r, w, cfg))
```

| 端口 | 域 | Handler 类 | 背后模型 |
|---|---|---|---|
| 10300 | wake | `WakeHandler` | `sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20` |
| 10301 | asr | `AsrHandler` | `streaming-zipformer-small-bilingual-zh-en-2023-02-16` int8 |
| 10302 | tts | `TtsHandler` | `matcha-icefall-zh-baker` + `vocos-22khz-univ` |

> 合并成单进程是 P0 优化：383.1 MB → **318 MB**，省 65 MB。端口不变，对客户端透明。

### 1.2 每个端口的事件流（从 handler 代码读出来的）

```
10301 ASR
  客户端 → Describe           服务端 → Info（自描述）
  客户端 → Transcribe         服务端 → （建 session）
  客户端 → AudioChunk * N     服务端 → TranscriptChunk（边识别边吐部分结果）
  客户端 → AudioStop          服务端 → Transcript（最终整句）

10302 TTS
  客户端 → Describe           服务端 → Info
  客户端 → Synthesize         服务端 → SynthesizeStart
                              服务端 → AudioStart
                              服务端 → AudioChunk * N
                              服务端 → AudioStop
                              服务端 → SynthesizeStop

10300 wake
  客户端 → Describe           服务端 → Info
  客户端 → Detect             服务端 → （建 session）
  客户端 → AudioChunk * N     服务端 → Detection(name=…)  命中即返回
                              或    → NotDetected         整段无命中
```

**音频格式约定**：`int16le`、单声道、**16000 Hz**。
客户端若送 48 kHz（常见麦克风），服务端内部用 `decimate3-mavg3` 降到 16 kHz（实测 −12.3 dB @20 kHz 抗混叠）。

### 1.3 怎么调（三种方式，都**不需要 token**）

**方式一：官方 wyoming 客户端（Python）**

```python
import asyncio
from wyoming.client import AsyncTcpClient
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStart, AudioStop

async def recognize(pcm16k_bytes):
    async with AsyncTcpClient("192.168.1.113", 10301) as c:
        await c.write_event(Transcribe().event())
        await c.write_event(AudioStart(rate=16000, width=2, channels=1).event())
        for i in range(0, len(pcm16k_bytes), 3200):          # 100 ms 一块
            await c.write_event(AudioChunk(
                rate=16000, width=2, channels=1,
                audio=pcm16k_bytes[i:i+3200]).event())
        await c.write_event(AudioStop().event())
        while True:
            ev = await c.read_event()
            if Transcript.is_type(ev.type):
                return ev.data["text"]

asyncio.run(recognize(pcm))
```

**方式二：仓里的验收客户端**

```bash
python3 wyoming_probe.py asr  --wav x.wav  --uri tcp://192.168.1.113:10301
python3 wyoming_probe.py tts  --text "你好" --out x.wav --uri tcp://192.168.1.113:10302
python3 wyoming_probe.py wake --wav y.wav  --uri tcp://192.168.1.113:10300
python3 wyoming_probe.py describe --uri tcp://192.168.1.113:10301
```

**方式三：裸 TCP 发一行 JSON**（协议就是 JSONL，人可读可手测）

```
发： {"type":"describe"}
收： {"type":"info","data":{"asr":[{...}],"tts":[],...}}
```

### 1.4 实测证据：协议自描述是真的

三个端口 `describe` 返回（2026-11-03 板端）：

```
10300 → wake: [{"name":"sherpa-onnx-kws", "version":"2.0.1",
                "models":[{"languages":["zh","en"],
                           "phrase":"LIGHT_UP, LOVELY_CHILD, 文森特卡索, 周望军,
                                     朱丽楠, 蒋友伯, 女儿, 法国, 见面会, 落实,
                                     小克, 小克小克, 你好小克"}]}]

10301 → asr:  [{"name":"sherpa-onnx", "models":[2 个]}]

10302 → tts:  [{"name":"sherpa-onnx-matcha",
                "voices":[{"name":"model-steps-3","languages":["zh-CN"],
                           "description":"matcha icefall, 22050 Hz"}],
                "supports_synthesize_streaming":false}]
```

**型号、唤醒词、音色都写在协议里**，客户端不需要预先知道板上配置。
这也是「将来接 HA 主机不用改一行代码」的技术基础。

> **注意 `supports_synthesize_streaming: false`**：当前是整段合成完再吐，不是流式。
> 短句无感，长句会有明显等待（matcha RTF 1.16–1.82）。

## 二、klar 在链路里怎么被用

### 2.1 它是官方预编译的静态二进制

| 项 | 实测 |
|---|---|
| 路径 | `/mnt/data/klar/engine/klar` |
| 大小 | **7,164,816 B（6.8 MB）** |
| 类型 | `ELF 64-bit LSB executable, ARM aarch64, **statically linked**` |
| 来源 | GitHub Release `klar-linux-aarch64.tar.gz`，tag `2026.10.10` |

**静态链接**意味着板上不需要任何 Rust 运行时/动态库——这是它能塞进 993 MB 板子的前提。

### 2.2 服务启动参数（systemd `klar-nlu-engine`）

```ini
Environment=KLAR_UI_DIR=/mnt/data/klar/engine/ui
ExecStart=/mnt/data/klar/engine/klar \
    --http 0.0.0.0:10520 \
    --wyoming 0.0.0.0:10500 \
    --config-dir /mnt/data/klar/ha-config \
    --data-dir /mnt/data/klar/ha-data \
    --token-file /mnt/data/klar/.klar-token
```

| 参数 | 作用 |
|---|---|
| `--http 10520` | HTTP UI + Parse API（**主要用这个**）|
| `--wyoming 10500` | Wyoming **intent** 服务端（留给 HA 接入）|
| `--config-dir` | 只读，读 HA 的 `core.entity_registry` 等 |
| `--data-dir` | 可写，校准/overlay/会话落这里 |
| `--token-file` | 写操作凭据（详见仓库内文档 `klar/docs/KLAR-401-BYPASS.md`，讲 token 与 401 那套）|

其它能力：`klar lang {validate,preview,import-hassil}`、`klar eval`、`klar migrate`。
**没有 export 子命令** —— 内置语言包拿不出来（见第三节）。

### 2.3 两个对外面，我们用哪个

| 面 | 端口 | 谁在用 | 调用形态 |
|---|---|---|---|
| **HTTP Parse API** | 10520 | **`klar_executor.py` 通道 A** | `POST /api/v2/parse` |
| Wyoming intent | 10500 | 预留（HA 接入时）| executor 里 `handle_wyoming_intent()` 已备好同形 JSON |

**executor 的实际调用**（`klar/klar_executor.py`）：

```python
KLAR_PARSE = "http://127.0.0.1:10520/api/v2/parse"

def klar_parse(text, language="zh-CN"):
    status, data = http(KLAR_PARSE, "POST", {"text": text, "language": language})
    return data          # {decision, intent, slots, speech, ...}
```

**请求体只认这几个字段**：`text` / `conversation_id` / `language` / `personality` / `preferred_area` / `nlu_*`。
多传 `schema_version` 会 **422**（踩过）。

### 2.4 klar 在链路里的确切位置

```
ASR 出文本
   ↓
executor 通道 A ──POST /api/v2/parse──▶ klar (10520)
   ↓                                   返回 {decision, intent, slots}
把 intent+slots 映射到板上动作（8091/8092/8093 或 door_unlock）
```

**它只管「听懂」，不管执行、不管语音、不存状态。**
只跑 klar = 能听懂但什么都不发生；只跑 executor = 能开关但听不懂人话。

## 三、语言包：为什么生硬、怎么改

### 3.1 机翻的根源（源码级证据）

`src/lang/packs/zh_cn/speech.rs` 第一行：

```rust
// @generated by scripts/lang_packs. DO NOT EDIT.
```

对比手写参考包：`src/lang/packs/de/speech.rs` 是 17,827 B、`zh_cn` 只有 3,098 B；
`en`（手写）与 `zh_cn`（生成）**键完全相同**，但中文是从英文机械转换来的。

`packs/registry.yaml` 也印证了：

```yaml
packs:
  de: {builtin: true}      # 手写参考
  en: {builtin: true}      # 手写参考
  de-AT: {path: de-AT/overrides.yaml, extends: de}
  en-GB: {path: en-GB/overrides.yaml, extends: en}
  fr:    {path: fr/pack.yaml, extends: en}
```

**只有 de / en 是 `builtin` 手写**，其余 65 种语言（含 zh-CN/zh-TW/zh-HK）都是构建时生成。

### 3.2 典型机翻错误（实测对照 en/speech.rs）

| 键 | 英文原文 | 生成的中文 | 问题类型 |
|---|---|---|---|
| `need_which` | Tell me which device you mean. | 打开什么？ | **错译**（抄了 need_on）|
| `media_search` | Starting music. | 播放什么？ | **语义反转**（陈述→问句）|
| `group_on` | {names} are on. | {names}. | **谓语全丢** |
| `cover_open` / `lock` / `unlock` / `turn_on_scene` | Opened / Locked / Unlocked / Started {target}. | {target}. | **动词全丢** |
| `get_temp` | The temperature {loc}. | 温度{loc}。 | **语序错**（→「温度客厅」）|
| `climate_set` | {noun} {target} is at {n} degrees. | {noun} {target} {n} | 语序照搬 + 无单位 |
| `clarify` | Do you mean {names}? | {names}? | **疑问句式丢失** |
| `done` | Done: {name}. | {name} | 「完成」丢失 |
| `pirat` 性格档 | Aye. / Captain. | **Aye.** / 船长。 | **英文未译** |
| `hippie` 性格档 | All good. / Easy. | 放松。 / 慢慢来。 | **两句错位** |

### 3.3 重译版在哪

`repos/HA4FPAI/klar/langpacks/zh_cn_speech.rs` —— 手工重译的**当前生效版**（原机翻版留档在同目录 `zh_cn_speech.generated.rs`），逐条带注释说明改动理由。

**结构校验（机械验证，非目测）**：

```
原文件键数: 67
新文件键数: 67
键名与顺序完全一致: True
占位符不一致的键: 0        ← {target} {n} {names} {loc} {room} {color} {noun} {summary} {when} {items} {name} 全部保留
话术条目改动数: 40 / 64
```

### 3.4 ⚠️ 改它需要重编 Rust（这是硬门槛）

`src/lang/external.rs` 的 `ExternalPack` 结构：

```rust
pub struct ExternalPack {
    klar_lang_pack, id, bcp47, extends,
    verbs, sets, maps, morphology, intents, source
}
```

**没有 `speech` 字段。** 所以能力边界是：

| 想改什么 | 不重编能否生效 | 机制 |
|---|---|---|
| 词表 / 颜色 / 数字映射 / 自定义短语 | ✅ 能 | 外置包 `--lang-dir`、`/api/lang/overlay` |
| **回复话术**（speech.rs） | ❌ **不能** | **必须改源码 + 重编 Rust** |
| 识别句子模式（pack.rs） | ❌ 不能 | 同上 |
| 界面文字（UI） | ✅ 能 | 改 `web/src/` 重构建前端（见 [[校机构建Klar前端并部署上板SOP]]）|

**⇒ 现状**：重译版是「备好的补丁」，等 Rust 构建链通了才能上板。
校机目前只有 Node（v24.22.2），**没有 Rust 工具链**。

## 四、怎么加「新情况 → 新回应」

**结论：新回应加在 `klar_executor.py`，不要碰 klar 的话术包。** 三层能力边界：

| 想加什么 | 在哪加 | 要不要重编 Rust |
|---|---|---|
| **新情况的新回应**（板子做出新反应）| `klar_executor.py`：`act_xxx()` + `DIRECT_COMMANDS` 一行 | ❌ 不用 |
| klar 多认几种说法 | 外置包 `intents`（`phrase→intent→slots`）| ❌ 不用 |
| 新词表／颜色／数字映射 | 外置包 `sets` / `maps` | ❌ 不用 |
| 往 klar 话术包加新 key | `speech.rs` + `Speech` 结构体 + 消费代码 | ✅ **要** |

**为什么回应不归 klar 管**：klar 只做 `文本 → {intent, slots}`，**它本身不产出回复文字**。
回复是 executor 里每条 `act_*()` 自己写的：

```python
def act_unlock(slots):
    ...
    return True, "已开门。", {...}      # 这段中文是我们写的
```

### 4.1 加一条新命令的三步（2026-11-03 实测样例）

**① 写动作函数**（返回 `(ok, 人话, 细节)`）：

```python
def act_time(slots):
    """现在几点：板上本地时间 HH:MM（纯本地，无服务依赖）。"""
    now = time.strftime("%H:%M")
    return True, "现在 %s" % now, {"time": time.strftime("%H:%M:%S")}
```

**② 进 `DIRECT_COMMANDS`**（`(短语列表, 函数, 默认 slots)`）：

```python
DIRECT_COMMANDS = [
    ...
    (["现在几点", "几点了", "现在时间", "看下时间"],  act_time, {}),
    (["拍照存档", "拍一张照片", "拍张照片", "存一张照片"], act_snapshot, {}),
]
```

**③ 传板上重启 gateway**：

```bash
pscp klar/klar_executor.py root@192.168.1.113:/mnt/data/klar/
plink ... "systemctl restart klar-voice-gateway"
python3 klar_executor.py --do "现在几点"     # 板上自测
```

> `_build_index()` 按**短语长度倒序**排，所以「关闭录制」不会被「录制」抢走；加新短语不用管顺序。

### 4.2 拍照存档用哪个接口（源码级依据）

`8091` = `wcis-face-photo.service`（`serve_photos.py --port 8091`）。拍照用：

```
GET /api/camera/preview.jpg
  200 -> Content-Type: image/jpeg，裸 JPEG 字节，带 X-Frame-Id / X-Capture-Session
  503 -> {"error":"暂无新鲜摄像头画面"}（无新鲜帧 / 相机被推理占用）
```

executor 收到 200 就把字节写到 `/mnt/data/klar/snapshots/snap-<时间戳>.jpg`，
回「已存一张：<文件名>」。服务没起时回「拍照服务没在跑」——**不会假装成功**。

> ⚠️ 两个已知前提：
> ① `wcis-face-photo` 平时 `enabled` 但 `inactive`，要拍照得先起它（耗内存）；
> ② **板子时区是 `Etc/UTC`**，`act_time` 报的是 UTC，比她本地（UTC+8）**慢 8 小时**——待定。

## 五、相关事实速查

| 问题 | 答案 |
|---|---|
| 语音服务要 token 吗 | **不要**。Wyoming 三端口完全开放 |
| klar 的 UI/写操作要 token 吗 | 要（无 token 时仅 localhost 可写）|
| 仓库里有 klar 的 Rust 源码吗 | **没有**（无 `.rs`/`Cargo.toml`）|
| 仓库里有 HACS 集成代码吗 | 没有，`ha/` 只有 1 个 3 KB 说明页 |
| 前端源码在哪 | 校机 `D:\yzd\WCIS\klar-ha-nlu`（可构建，产物与板上字节级一致）|
| 板上 UI 路径 | `/mnt/data/klar/engine/ui`，靠 `KLAR_UI_DIR` 指定 |

## 六、`async` 在这里意味着什么

Wyoming 服务端是 **asyncio** 写的：一个事件循环、三个端口、多连接并发。

```python
class AsrHandler(AsyncEventHandler):
    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(...)
```

- **同步**写法要「每连接一个线程」，993 MB 板上吃不消
- **异步**写法一个循环搞定，连接只是协程对象
- `asyncio` 是 Python **标准库**，任何 Python 3.x 自带，不用装；`async`/`await` 是 3.5+ 关键字

## 相关页面

- [[校机构建Klar前端并部署上板SOP]] — 前端构建与上板（Node 那条链）
- 仓内 `docs/ARCHITECTURE-OVERVIEW.md` — 整体链路与 HA 逻辑对照
- 仓内 `klar/docs/KLAR-401-BYPASS.md` — token 与 401
</content>
