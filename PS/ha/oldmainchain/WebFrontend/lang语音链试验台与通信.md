---
tags: [index]
updated: 2026-11-04
---

# lang语音链试验台与通信

本页连接语音源码、网页试验台与服务协议。**代码根目录是 `repos/HA4FPAI/lang/`**，旧的 `repos/lang/` 已整体迁入；ggradio 在 `repos/HA4FPAI/web/ggradio/`。实现细节查 `lang/server/core.py`、`app.py`、`wyoming_gateway.py`、`loop.py` 与控制台 `console.py`；各 README 中的旧档位、旧计数和旧部署路径须与源码及最新状态源核对。

## 一、代码位置与验证窗口

本页基于 **2026-11-04 本地源码及留存证据**，未重新访问板端或联网。下表各行是不同验证窗口，不能相互替代；对应 D 记录见 [[状态源与决策记录#4. 决策日志（追加式，不删除）|状态源与决策记录——4. 决策日志]]。

| 窗口与记录 | 已证明什么 | 尚不能推出什么 |
|---|---|---|
| 11-04 板端 online/edge 部署，D-1793767689 | online ASR＋云 LLM＋Edge TTS 的 HTTP 与 Wyoming 面通过，板上运行时为部署变体 | 该窗口的链路尚无后加的完整十级；不能按早期 HA4FPAI README 宣称本地模型仍现役或全离线成功 |
| 11-04 文件输入 FSM，D-1793768465 | `loop.py --simulate` 跑过 `wake → speech_end → asr_done → llm_done → tts_done`，回复 wav 落盘；无麦重探有记录 | 真麦克风采集、扬声器播放与 barge-in 的完整实机验收 |
| 11-04 板钟 05:15–05:19 UTC（13:15–13:19 +08:00），D-1793769625 | `tts_split` 严格 20 字切块上板；板端自检 **13908 ok / 0 fail**，实际 `/tts` 最长块为 20 字 | 当时特意未同步新版 `core.py` 与 `backends/router.py`；换 tokenizer 不等于十级都上板 |
| 11-04 新十级，D-1793773995 | `core.py:111–145` 登记十级，新增 rms／kws_route／router 等的 PC `smoke.py` **54/54**，FSM 单测 16/16 | 该条仅证明当次 PC 自检；后续板端部署与配置健康回显见 D-1793775864，部署后十级实际推理与路由回归仍缺 |
| 11-04 14:23 +08:00 PC 恢复记录 | 本机 ggradio :7861 与托管 HTTP :18091 的真实 wav ASR 返回中文；证据在 `workenv/lang-deploy/verification-20261104.json` 与同目录 `restore-local-20261104-SOP.md` | 该次本地 sherpa ASR＋echo/sine 配置不是板端 online/edge 档，也不代表全部本地模型可用 |
| 11-04 后续部署，D-1793775864 | 默认全在线、服务 `--no-warm`；`workenv/lang-deploy/final-online-verification.json` 已留十级配置健康回显，含 `rms: energy`／`kws_route: default`／`router: none`，并有模型文件、服务与端口检查 | 文件就绪与健康回显不证明本地模型推理；尚缺部署后十级实际推理与路由功能回归，也不能宣称 `router: klar` 已板端接通 |

## 二、十级编排与两次路由

当前源码顺序为：

```text
sar → rms → kws → kws_route → vad → asr → router → llm → tokenizer → tts
```

- `sar` 前处理与重采样，`rms` 先判整段能量；启用 gate 时静音短路，跳过后续识别。
- `kws` 做唤醒门控；其后 `kws_route` 的规则实现在 `lang/kws/router.py`，server 的 `backends/kws_route.py` 只作薄调用。`continue` 进 VAD／ASR，`stop` 结束，`direct` 用固定回应直达文本输出与 TTS。
- `vad` 切段后交 ASR；ASR 之后的 `router` 再决定 `llm`、`fixed` 或 `verify`。`fixed` 跳过 LLM；**verify 尚未实装，留空跳过**。klar 档通过 HTTP 调上层 NLU，调用失败回落 LLM。
- `tokenizer` 把回复切为短块；`tts_split` 为严格最多 20 字、不丢字的切块档。逐块 TTS 后拼接、重采样为输出 wav。旧 `punct`／`window` 仍是可选档，参数与实现归 `lang/split/`。

上游 klar 是 Rust 确定性 NLU，自研双通道 executor 的固定指令优先；它与本页十级编排不是同一个实现。历史 8/8 仅为文本／API 测试，真麦闭环、PAD 安全标定与真锁验收仍缺；接入背景见 [[Wyoming协议与klar接入#二、klar 在链路里怎么被用|Wyoming协议与klar接入——二、klar 在链路里怎么被用]]，对外限制见 [[风险与完成判据#5. 已知限制与范围外（对外唯一口径）|风险与完成判据——5. 已知限制与范围外]]。

## 三、HTTP、Wyoming 与文件循环

### HTTP 面

入口 `repos/HA4FPAI/lang/server/app.py`，默认 `:18091`，HTTP 服务层为 Python 标准库。后端按档位另有依赖；协议是**完整音频请求与完整结果响应**，不提供逐帧 partial 转写。

| 方法 | 路径 | 输入与返回 |
|---|---|---|
| POST | `/api/v1/chain` | 裸音频、JSON `audio_b64` 或 multipart；默认 JSON，`?format=wav` 返回裸 wav |
| POST | `/api/v1/asr` | funasr 兼容 multipart `audio`；默认只做 ASR，`?llm=1` 才带 LLM |
| POST | `/v1/audio/transcriptions` | OpenAI 兼容 multipart `file`；回 `{"text":…}` |
| POST | `/llm` | JSON `text` 或裸文本；`?tts=1` 可接 TTS |
| POST | `/tts` | JSON `text` 或裸文本；走切块→TTS→拼接→重采样，默认 wav，`?format=json` 回 base64 |
| POST | `/reset` | 上下文重置入口，可带 `session`；具体效果须按后端与回归核验 |
| GET | `/health` · `/stats` · `/components` · `/` | 装配、计数、可选档及用法；健康响应不等于推理或硬件验收 |

公共 query 有 `llm`、`tts`、`out_rate`、`session`、`format`；`tts_tier` 可请求级临时覆盖 TTS 档。检查回包里的 `stages_error` 与实际产物，不能只看 HTTP 200。

### Wyoming 面

入口 `repos/HA4FPAI/lang/server/wyoming_gateway.py`；默认同一进程提供 `wake :10300`、`asr :10301`、`tts :10302`，使用标准 Wyoming 事件：`Detect/Detection`、`Transcribe/Transcript`、`Synthesize/AudioChunk`。

**传输可分块，后端仍按整段处理**：wake／ASR 将音频 chunk 累积到 `AudioStop` 后调用对应 stage，一次回结果；不支持部分转写。TTS 接收整段文本，切块合成后输出音频事件。三口各调所需组件，不代表每个请求都遍历十级或经过 FSM。此面依赖 `wyoming` 包。

### 文件与常驻循环

`loop.py` 自建 `Chain`，由 `DialogueFSM` 驱动。`--simulate` 是文件当麦克风的一轮迁移验收，`--oneshot` 是文件单轮，`--run` 是真实采集／播放循环入口。自动设备匹配、无麦重探与 barge-in 已有实现；真麦真喇叭是否通过，须另有硬件证据。HTTP 与 Wyoming 是请求驱动面，不经过此 FSM。

## 四、进程内共享与服务边界

`core.Chain` 是可实例化对象：各入口持有自己的实例，组件按 `(stage, 档名)` 惰性缓存。**共享范围限定在持有该 Chain 的同一进程内**。

| 入口 | Chain 与运行时归属 |
|---|---|
| ggradio 逐段试验台 | 控制台进程内 `import core`，直接调 `Chain.stage()`；不通过 HTTP 逐级调用 |
| HTTP `app.py` | HTTP 进程持有自己的 Chain，请求线程使用此实例 |
| Wyoming gateway | gateway 进程创建自己的 Chain，wake／ASR／TTS 三口可共享此实例 |
| `loop.py` | 循环进程另建 Chain，供本进程 FSM 使用 |

`SharedEnv.sherpa()` 统一当前 Chain 内 sherpa 后端的导入入口；VAD／KWS／ASR／TTS 各有自己的模型对象或会话，并不合成一个模型。默认 `env.single_runtime` 限制额外加载 pip `onnxruntime`，显式允许后仍是第二套运行时。**HTTP、Wyoming、loop 作为不同服务进程启动时，不能声称跨进程只占一份 sherpa／ORT 或一份模型内存**。外部 HTTP 后端、NPU worker 亦有独立边界。

直接启动服务的预热行为与是否传 `--no-warm` 有关；最新部署模板的三个单元均使用 `/mnt/data/lang/server/`、`LANG_CONFIG_DIR=/mnt/data/lang/config` 与 `--no-warm`。模板正确、文件已部署、推理实测通过仍须分别取证。

## 五、ggradio：保存、重载、重启

控制台由标准库 `ThreadingHTTPServer`＋静态 HTML 实现，默认 `:7861`；名称 ggradio 不表示依赖 Gradio。参数表动态扫描 `lang/config/` 的 YAML，从注册表、人工登记及注释取得选项；**文件数、参数数以当次 `/api/config` 为准**，不固定为旧文中的计数。

| 动作 | 实际效果 |
|---|---|
| 保存参数 | 写回 YAML；正在运行的其他服务不会自动热加载 |
| 保存并重载／`POST /api/reload` | 重建控制台自己的 Config／Chain，使逐段试验台用新值 |
| `--serve` 托管与重启服务 | 控制台另起 HTTP `app.py` 子进程；重启是终止该托管子进程、等待退出后重新启动并探测健康 |
| 端口已有外部服务 | 显示为 external，不接管该进程 |

三个动作的生效范围不同；重启托管 HTTP 不会同时重启 Wyoming 或 loop。配置在入口创建 `Config` 时加载，服务要读到新配置须重新启动对应进程。控制台“恢复默认”的预期是快照恢复；当前源码 `reload_chain()` 也会重拍快照，因此不能把它当永久出厂配置或可靠的首次启动回滚点。

常用端点：`GET/POST /api/config`、`POST /api/config/reset`、`GET /api/stages`、`POST /api/run`、`GET /api/artifact/<name>`、`GET /api/health`、`GET /api/server`、`POST /api/server/{restart,start,stop}` 与 `GET /api/server/log`。密钥掩码 `***` 表示保持原值。产物由 `--artifacts`／`CONSOLE_ARTIFACTS` 指定，WCIS 使用时应落 `workenv/`。

**历史问题已在当前源码修复**：2026-11-04 14:23 +08:00 的 PC 恢复记录曾出现 wildcard bind `0.0.0.0` 被当作健康探测目标，导致 `/api/server` 显示 `health=null`、直接 loopback `/health` 却正常。现读 `console.py:701–705`，`_probe()` 已将空地址／`0.0.0.0` 归一为 `127.0.0.1`，并使用不经代理的 opener。旧 SOP 保留当时现象，不再将其列为当前未修问题；当前实际运行状态仍须单独取证。

## 六、浏览器录音与本机播放

网页普通链路录音现按用户最新要求在浏览器重采样并编码为单声道 16 kHz PCM16 WAV，经 multipart 的 `file` 上传到 `/api/run`；麦克风需 localhost 或受信任 HTTPS。输入端 SAR 仍可选，用于识别前的工作采样率转换。

网页默认传 `audio_output=browser`：TTS 输出按原生率拼接为 WAV，经 `/api/artifact/…` 返回网页播放器，在访问页面的手机或电脑播放；此路径不调用服务端输出 SAR，浏览器／系统可适配声卡。`audio_output=server` 保留原输出采样率导出流程，未提供此字段的旧调用方保持兼容。两者都不自动调用板端扬声器。操作与复核入口见 `repos/HA4FPAI/web/ggradio/README.md` 的「网页录音与浏览器播放」。

16 kHz 更新已用 `workenv/hdmi-kiosk/test-wav-16k.cjs` 验证：16／44.1／48 kHz 各一秒输入均生成 16000 帧、单声道 PCM16 WAV；降采样高频抑制检查通过。以下 48 kHz 联调属于改目标采样率之前的历史证据。

2026-11-04 本机证据：合成 MediaStream 录音／上传得到 48 kHz、1 声道、16 位 WAV；44.1 kHz 与 48 kHz 各一秒输入均编码为 48000 帧；sine 自检返回原生 22050 Hz，网页播放器读到音频元数据。另用离线测试将输出重采样函数替换为抛错函数，浏览器路径仍成功输出 24 kHz。未测试手机真实麦克风／喇叭、板端外设或云端 TTS 本轮表现。

## 相关页面

- [[webapp#现有入口与验证范围|webapp——现有入口与验证范围]]：前端与 HMI 入口。
- [[HDMI直显与网页最小化方案#十、下一步（顺序不可颠倒）|HDMI直显与网页最小化方案——十、下一步]]：显示与鼠标仍需逐步实机验证。
