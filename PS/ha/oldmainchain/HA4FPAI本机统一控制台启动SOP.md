---
tags: [SOP]
updated: 2026-11-04
---
# HA4FPAI本机统一控制台启动SOP

本页记录在 Windows 电脑上启动现有 HA4FPAI 服务的入口和判据。统一控制台是日常入口；Klar 引擎、ggradio、语音服务是其背后的不同进程。板端语音与设备服务继续使用 192.168.1.113 上已有的实例。

## 启动

前提：工作区在 `S:\work\WCIS`，本机 Python、Podman 及已有镜像可用，`zgbuild` 内已有 Klar 源码，电脑可免密 SSH 到 `root@192.168.1.113`。本轮复用了已有环境，没有安装新软件或在板上编译。

首次准备已经完成：在本机 `zgbuild` 容器内以 `cargo build --release --locked -j 8` 生成 x86_64 原生 Klar，将二进制复制到 `workenv/ha4fpai-local/klar`，使用现存编译前端作为该目录的 `ui/`，生成实体注册表与独立本机 token。镜像标签中的 arm64 不能作架构依据；本次所用镜像实测为 amd64。token 只在本机文件及容器中读取，不写进页面、日志或本页。

日常在 PowerShell 执行：

```powershell
& 'S:\work\WCIS\workenv\ha4fpai-local\start.ps1'
```

出现 `READY http://127.0.0.1:10900/` 后，用 Firefox 打开该地址。脚本复用正在运行的进程；缺少时才启动。若现有 ggradio 不支持主题适配器路由，先停止其托管的语音子进程，再重启本项目 ggradio，使新路由和当前服务代码生效；其他程序占用端口时停止启动并报告，不抢占端口。

## 入口与进程归属

| 地址或组件 | 用途与归属 |
|---|---|
| `http://127.0.0.1:10900/` | 电脑上的统一控制台，日常入口；设备指令通过 SSH 调用板端既有执行器 |
| `http://127.0.0.1:7861/` | ggradio 参数配置、录音与逐段试验台；托管本机语音 HTTP 服务 |
| `http://127.0.0.1:18091/health` | 本机 lang-server 健康接口，无独立网页首页 |
| `http://127.0.0.1:10521/` | 电脑上的 Klar UI 代理，自动补鉴权头；从统一控制台内嵌进入亦可 |
| 本机 `10520`、`10500` | 容器 `ha4fpai-klar-local` 的 HTTP 与 Wyoming 引擎端口；浏览器使用 10521 代理，直接访问 API 可能返回 401 |
| 板端 `10300/10301/10302`、`8091/8092/8093` | 已有语音与人脸／直播／录像服务；本轮未改板端服务或部署文件 |

本机控制台使用 `workenv/ha4fpai-local/desktop_console.py` 加载原有控制台和执行器，通过包装动作函数把设备操作发往板端。包括重启与取消重启，均不调用 Windows 本地设备动作。Klar 解析走本机鉴权代理，设备执行走板端。历史保存在本机运行目录；勾选播报后，答复请求本机语音 HTTP 服务并在电脑播放。

本机新引擎的界面语言初始化为简体中文，实体表已加载，首启向导已标记完成；没有更换语音链的选档或密钥。Klar 的独立语音／LLM 设置与 ggradio 的 lang-server 配置不是同一份，不要把前者当成后者的启动开关。语音链仍按当前配置运行，本轮没有启用新的 ASR 后路由或自动麦克风循环。

## 验收

```powershell
Invoke-RestMethod 'http://127.0.0.1:10900/api/health'
Invoke-RestMethod 'http://127.0.0.1:7861/api/server'
Invoke-RestMethod 'http://127.0.0.1:18091/health'
Invoke-RestMethod 'http://127.0.0.1:10521/api/ui'
podman ps --filter name=ha4fpai-klar-local
```

2026-11-04 本机实跑结果：统一控制台健康接口返回语音网关与 Klar active；板端人脸、直播、录像接口均 HTTP 200，直播 ready，录像 auto／armed。ggradio 托管本机 lang-server，健康接口正常。控制台输入「现在几点」通过板端执行器返回当时的时间。另以替身动作检查已配置的重启／取消短语和所有设备目标均通过远程包装，不实际重启设备。

浏览器实跑确认：统一控制台可加载 Klar 与 ggradio；ggradio 内嵌主题按钮隐藏，父页切换明暗可同步。内嵌主题协议正本见代码库 `web/shared/README.md`。Firefox 已打开统一控制台。上述是启动与只读查询验证，不代表实际麦克风、播报、开门或重启动作均已验收。

2026-11-04 导航分类调整后，只重启本机 10900 统一控制台，保留 ggradio、语音 HTTP 和 Klar 进程。界面分类与各内嵌入口的正本见代码库 `docs/CONSOLE-AND-TOKEN.md`；打开着的旧网页需刷新。隔离预览与本机入口已验证分类切换、历史直接链接与刷新、旧书签兼容、子标签键盘操作、iframe 状态保留和主题广播；320／390／768／1080／1440 px 无页面横向溢出，后端 AST 与修改前一致。预览使用占位视频页，不以此冒充实物视频验收。取证文件留在 `workenv/console-navigation/`。

## 日志与排查

- 本机进程日志：`workenv/ha4fpai-local/logs/`，每次新启动使用带时间戳的文件，保留旧日志。
- ggradio 托管语音服务日志：`workenv/ha4fpai-local/artifacts/lang-server.log`。
- Klar 日志：`podman logs --tail 40 ha4fpai-klar-local`。
- 控制台历史：`workenv/ha4fpai-local/state/console-history.jsonl`。
- 本机启动适配脚本：同一运行目录的 `desktop_console.py`、`local_proxy_entry.py`、`start.ps1`。

Klar 原始 API 返回 401 时，先检查 10521 代理及其本机 token 文件，不关闭鉴权。`start.ps1` 的引擎就绪检查访问公开首页；鉴权 API 经代理检查。关闭网页不会停止后台服务，本轮未配置 Windows 登录自动启动。

文档校验按 `python -X utf8 wiki/format/check-md.py` 运行；全库仍有既有的页名／链接等问题，报告保存在运行目录 `logs/markdown-check.log`，本页未被报错。本轮不顺带修复其他文档。
