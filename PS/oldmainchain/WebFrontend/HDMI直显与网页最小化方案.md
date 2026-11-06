---
updated: 2026-11-04
---

# HDMI直显与网页最小化方案

> **本页管什么**：把 113 上那几张自建网页**投到这块板的 HDMI 上、并且能用 USB 鼠标点**的方案与判据——显示出口怎么造、浏览器最低要哪一档、哪几页的"重实现"可以砍成轻实现、砍完降到哪一档。
>
> **本页不管什么**：页面业务功能与接口定义（各服务自己的页）；HDMI 那半截的数据流与每段归属正本在 [[魔改厂商视频流程部署记录]]；板端文件登记在 [[板端我方代码与产物台账]]；决策在 [[状态源与决策记录]]——**本页尚未产生决策，全部待她拍板**。

**判级口径**：A＝板上实测原文（2026-11-03 夜，**只读查询**，未装任何包、未写任何寄存器）｜B＝厂商源码或本仓 RTL 直证｜C＝推断／未验证｜D＝外部素材、平台标注不明。

---

## 一、先钉死那条硬约束：这块板没有"显示设备"

| 事实 | 读数 / 出处 | 级 |
|---|---|---|
| 没有 `/dev/fb*`、没有 `/dev/dri`、没有 DRM | `ls` 全无；`/sys/class/graphics` 只有 `version`、`fbcon` | A |
| 内核其实**编了** fbdev／DRM（`CONFIG_FB=y`、`FRAMEBUFFER_CONSOLE=y`、`DRM_FBDEV_EMULATION=y`、`CONFIG_DRM_XLNX=y`）——但没有驱动去注册设备 | `/proc/config.gz` | A |
| HDMI 是 **PL 里的哑帧缓冲读出器**：每个 vsync 从 PS DDR 某地址读一整帧 1920×1080 RGB565，做 TMDS 输出 | `frame_to_ps_largebuf.v` 的 `video_rect_read_data`＋`uihdmitx` | B |
| PS 只写一个寄存器 `0x40080054 = 物理地址>>3`；PL 侧解成 `camera_rd_addr`（27 位，单位 8 B ⇒ 可寻址 ≤ **1 GiB**） | `frame_ctrl.v` 0x54 段；C++ 侧 `hdmi_display.hpp` 同址同写法 | B |
| **0x78 bit0 是 `disable_hdmi`**，`display_en = ~bit`；RGB565 分支写 **0**（显示开），YUV422/VPU 分支写 **1**（显示关） | `frame_ctrl.v` 0x78 段 ＋ `sdicamera.hpp:206/222` | B |
| 当前板况：`0x54 = 0x07E00000`（复位默认）、`0x78 = 0`（**显示是开的**）、`0x50 = 0x0623FA40`（上次 demo 残留） | `busybox devmem` 只读回读 | A |
| `dip_switches` 硬连 `1'b1` ⇒ 一律出 DDR 读出，彩条只在常数改 0 时出现 | `ps_ai_peripheral.sv:670` | B |
| 显示读出的几何是**写死 1080p**（`video_width=1920`、`video_height=1080`、`read_len=518400`） | `frame_to_ps_largebuf.v:303/364-365` | B |
| HDMI 引脚在 PL：`AC17`（CLK）、`AA15/Y16/W16`（TX0-2），`TMDS_33` | `case/constrs_1/impl_constraints.xdc:2-7` | B |
| 显示缓冲就是 PS DDR 里的一块 udmabuf：`0x30100000`，128 MiB；`phys_addr`/`size` 走 sysfs 就能拿到 | `/sys/class/u-dma-buf/udmabuf0/` | A |
| 一帧大小 = 1920×1080×2 = **4,147,200 B** | 算术 | A |
| 像素时钟与 SDI 相机**有耦合**：`cam_clk = rx0_locked ? rx_usrclk : sys_clk_200m`（SDI 锁上走恢复时钟，没锁回退 200 MHz），HDMI 出图用的 `cam_clk_use` 就是这个 `cam_clk`；TMDS 的 148.5/742.5 MHz 由它经 MMCM（×5）再生 ⇒ **没接相机时也有时钟（200 MHz 回退），HDMI 信号按推断仍会产生**——VTC 无相机能出图是实测过的，但"200 MHz 回退下 TMDS 输出正常"这一步没单独实测 | `sdi/rx_sdi.v:373`、`frame_to_ps_largebuf.v:201-214`、MMCM 注释 `clk_out1=148.5 / clk_out2=742.5`（`cmos_clkgen_742_5_clk_wiz.v:59-60`） | B／C |

⇒ **"系统识别到显示器了吗"这个问法在这块板上不成立**，与"系统识别到摄像头了吗"同源（[[魔改厂商视频流程部署记录]] §二）。

---

## 二、小结论：为什么"装个浏览器"不够

`xserver`／`chromium`／`firefox` 这些包在别的板子上之所以"装上就能看"，是因为内核里有 fbdev 或 DRM/KMS 设备可以接管。这块板**一个都没有**，所以浏览器画到哪里、谁来把它变成 HDMI 信号，全靠我们自己补一个**显示出口（sink）**。

缺的那一段是固定的三步：

1. 把渲染好的像素整理成 **RGB565、1920×1080、行紧排**；
2. 拷进 udmabuf 里的一块（4.14 MB）；
3. 写 `0x40080054 = (0x30100000 + 偏移) >> 3`，让 PL 下一帧去读它（`0x78` 保持 0 即显示开）。

这三步与页面复杂度无关——**网页简化只能省掉浏览器这一层的开销，省不掉 sink**。

---

## 三、显示出口的三条候选（未选定）

| 方案 | 组成 | 优点 | 代价 / 风险 |
|---|---|---|---|
| **A. Xorg(dummy) + 自写 sink** | `xserver-xorg-core` + `-video-dummy` + `-input-evdev` + 一个 XDamage 驱动的投帧 daemon | 鼠标键盘**原生**可用（X 自己读 evdev、软光标画进帧缓冲）；现成浏览器全都能跑；daemon 约 300 行 C，板端 gcc 可编 | 每帧一次 XShm 回读＋memcpy；X server 约 40 MB RSS |
| **B. 内核 fbdev 模块** | ~200 行 fbdev 驱动（`dma_alloc_coherent` 4.14 MB、`fb_ops`、`pan_display` 里写寄存器），出 `/dev/fb0` | 零拷贝、标准栈、顺带白送文本控制台（`fbcon`） | **卡在拿不到 FMSH 5.4.52 内核源码/头**（`/lib/modules` 只有 2 个 `.ko`，源码不在板端）；vermagic 必须严格匹配 |
| **C. 完全不要 X** | 无头浏览器 + CDP／自研输入 | 省一个 X | focal 的 `chromium` 是 snap 过渡壳（deb 仅 48 KB、Depends 只有 debconf），板上无 snapd ⇒ **不可用**；只剩 Firefox 无头，鼠标要自己读 evdev 转事件、光标要自己画、坐标要自己映射，体验明显更差 |

**本页推荐 A**（若将来拿到内核源码再升级到 B）；C 仅作为"实在不想要 X"的兜底。

A 的两个设计要点：

- **X 跑 depth 16 / RGB565**（不是 24）：这样 XShm 读出的就是 RGB565，sink 只做 memcpy（4.14 MB/帧，A53 上约 3–5 ms），省掉 24→16 的逐像素转换。
- **双缓冲 + 换址**：写后备用，写完再写 `0x54` 换过去；撕裂只发生在换帧那一瞬（PL 是自由跑 60 Hz 连续读，不会自己等你）。
- 偏移建议取 udmabuf0 尾部（如 `+0x07000000`），与 icraft 的池子不重叠；本方案**不需要 icraft 在跑**。

---

## 四、113 现有网页清点（2026-11-03 读到的原文）

| 端口 | 服务 | 首页大小 | 页面里真正用到的东西 | 性质 |
|---|---|---|---|---|
| **8091** | `serve_photos.py`（wcis-face） | 26,316 B | 2 个 `canvas`（960×540 检测帧＋照片框）、`new Image()`＋`drawImage`、`fetch('results.json')`／`/api/health`／POST `/api/recognize`（传 JPEG） | 拍照识别＋画框叠加 |
| **8092** | `vpu_live_server.py` | 959 B | `video autoplay muted` ＋ `/h264_player.js`（4,220 B，**`MediaSource` ＋ `createObjectURL` ＋ `fetch('/h264/…')` 分片喂流**），内联每 500 ms 拉 `/api/status` | H.264 实时预览（MSE） |
| **8093** | `recording_service.py` | 7,528 B | `video controls` ＋ `<img>` 回退 ＋ `/recording_panel.js`（13,288 B，`createObjectURL`＋`fetch`＋`new Image`） | 录像回放 |
| **10900** | `klar/console.py` | 10,418 B | 纯 DOM ＋ 7 处 `fetch` 轮询（health/commands/voiceprint/history/logs）＋ `setInterval` 8 s | 控制台看板 |
| **10520** | klar Web（Vite 构建） | 433 B | `script type=module` → `./assets/index-Bg17n22J.js` **2,809,902 B**（含 React 特征、canvas、fetch），CSS 124,379 B | React SPA |
| 18090 | `mimo_bridge.py` | text/plain 801 B | API 说明，不是页面 | —— |
| 10300 / 10500 | voice_gateway / klar | 非 HTTP | 10300 直接断连；10500 回 JSON | 不是页面 |

⇒ **五张页面里没有一张是静态 HTML**：最轻的 10900 也要 `fetch`＋`async`，最重的 10520 是 2.8 MB 的 React 包。

---

## 五、浏览器档位判定

| 档位 | 包 | 8091 | 8092 | 8093 | 10900 | 10520 | 备注 |
|---|---|---|---|---|---|---|---|
| netsurf 3.6 | `netsurf-gtk` | ✗ | ✗ | ✗ | ✗ | ✗ | JS 是极小子集，无 `fetch`／ES module／完整 canvas／`video` |
| WebKitGTK 2.38 | `midori` 7.0 / `epiphany-browser` 3.36 | ✓ | △ | ✓ | ✓ | △ | 8092 要额外补 GStreamer；10520 能开但慢 |
| Firefox | `firefox` 136（focal 真 deb，62,136,556 B） | ✓ | ✓ | ✓ | ✓ | ✓ | RSS 450–700 MB，总内存 993 MB，余量最小 |

- **最低可用档 = WebKitGTK**；netsurf 只能当"链路烟测"，不能当交付面。
- **8092 的坑不在浏览器**：板上 `/usr/lib/aarch64-linux-gnu/gstreamer-1.0/` 现在**只有 `libgstcoreelements.so`**（A）⇒ MSE 的 H.264 解不了，页会一直"正在连接…"。补 `gstreamer1.0-libav`＋`plugins-good`＋`plugins-bad` 才有戏。
- 装包规模（`apt-get -s` 的 `newly installed` 计数，A）：`epiphany-browser` 59、`midori` 57、`libwebkit2gtk-4.0-37` 51、`firefox` 25、`gstreamer1.0-plugins-bad` 44、`plugins-good` 14、`plugins-ugly` 9、`1.0-libav` 3。磁盘余量 `/` 26 G 用 18 G，**7.2 G 可用**（A），放得下。
- 硬件底子：4×Cortex‑A53（`CPU part 0xd03`）、993 MB／可用 493 MB、CMA 256 MB（free 130 MB）、swap 1 GB（A）。**无 GPU**：`mali_kbase` 虽加载但没有 `/dev/dri` ⇒ 一律 llvmpipe 软渲染，1080p 滚动就是卡的，换哪档都一样。

---

## 六、核心答案：哪些"重实现"其实可以砍

**真刚需只有三件**：① 把后端状态／帧显示出来；② 让人能点（上传、按钮）；③ 周期刷新。这三件 `img`＋`form`＋`a`＋`meta refresh` 就够，**是 HTML 基本功，netsurf 都支持**。
"厉害的实现"指的是 React、H.264/MSE、canvas 画框、fetch 异步轮询——**全是可选载体，不是功能本身**。

| 页面 | 重在哪 | 能砍成什么 | 砍完落档 | 代价 |
|---|---|---|---|---|
| **8091** | `canvas` 画框 ＋ `fetch`＋`async` | 让 `/api/recognize` 直接回**已画好框的 JPEG**；前端只留一个 `form` 上传 ＋ 一张 `img` 轮询结果图 | netsurf 档 | 少一层"客户端可交互改框"的能力（本来也没有） |
| **8092** | `MediaSource` ＋ H.264 分片 | 直接吃板上**已有的 `mjpeg_server.py`**：`img src=…/snap.jpg` 靠 meta refresh 刷（约 2–5 fps），或多帧 `img` | netsurf 档（多帧形态未验证，C） | 60 fps 实时预览 → 秒级快照；MSE/GStreamer 全不用装 |
| **8093** | `video` 控件 ＋ JS 面板 | 改成"直接打开／下载录像文件"的链接，或 `img` 逐帧 | netsurf 档 | 丢进度条、逐帧控制 |
| **10900** | `fetch` 轮询 ＋ DOM 重排 | 后端 `console.py` 直接吐整页 HTML，`meta refresh` 5–8 s 自动重载 | netsurf 档 | 丢"无刷新自动更新"，改整页重载 |
| **10520** | Vite＋React 2.8 MB 包 | 同 10900：后端渲染 HTML ＋ 极少原生 JS（同一批 `/api/*`） | netsurf 档 | 工作量最大；丢 SPA 的局部刷新与过渡 |

⇒ **"改网页"能换来的最大收益**：不必装 Firefox（省 450–700 MB）、不必装 GStreamer H.264 插件、不必为 SPA 牺牲 A53；最低可以停在 **Xorg ＋ netsurf** 这条最轻的路。

---

## 七、统一的最小页面形态（若走"全砍"路线）

后端渲染 HTML，前端零 JS：

1. 页面由一个 Python 路由直接吐完整 HTML（数据在服务端就拼好）；
2. 会变的东西用 `meta http-equiv=refresh` 整页重载（5–8 s），或用 `img` 指向一个每次都返回新 JPEG 的 URL；
3. 需要人操作的用普通 `form`（含文件上传）＋按钮，POST 回后端；
4. 不引入任何打包器、不引 CDN、不写 `fetch`／`async`。

这样 netsurf 档就够，页面在 1080p 上渲染成本也最低。

---

## 八、边界与风险（别踩）

1. **简化网页 ≠ 省掉显示链路**：sink 仍必须做（第一节那三步）。
2. **netsurf 的具体能力未实测**（按她的要求不动板；校机是 Windows 虚拟机、没有 apt）。`meta refresh`／`form`／`img` 是它支持的老基本功，但 `multipart/x-mixed-replace` 的 MJPEG 在 `img` 里它未必解 ⇒ **C 级**，落档前必须先验一枪。
3. **分辨率写死 1920×1080，刷新率跟着像素时钟**：`video_define.v:1` 选中的是 `VIDEO_1920_1080`（`color_bar.v:118-129`，标准 CEA-861：2200×1125/帧），`video_rect_read_data` 的 `video_width/height` 与 `read_len` 也是常数 ⇒ 换分辨率要改 RTL 重编位流。像素时钟 `cam_clk = rx0_locked ? rx_usrclk : sys_clk_200m`（`sdi/rx_sdi.v:373`）：**接 3G-SDI 1080p60 相机＝148.5 MHz＝真 60 Hz；不接相机＝回退 200 MHz＝同一组消隐常数下约 81 Hz**（与 wiki 记的 VTC 轮 80 fps 吻合，B＋旁证 A；显示器认不认属 C）⇒ 不接相机直上 HMI 前必须先用彩条实测显示器。
4. **无 GPU**：任何档位都是软渲染；A53 上 1080p 网页滚动会掉帧，属预期。
5. **内存**：WebKit 档 200–350 MB、Firefox 档 450–700 MB，贴着 493 MB 可用 + 1 GB swap 的边；netsurf 档最宽裕。
6. **`0x78` 极性别记反**：写 **0** 是开显示（RGB565），写 **1** 是关（YUV422/VPU 档）。当前板况 `0x78=0`，即读出是开着的，只是地址还是复位默认 `0x07E00000`。

---

## 九、原生 HMI：不过编解码、零新装的第四条路线（2026-11-04 她定向：不一定要网页）

**关键事实**：这几张页的"操作逻辑"全在 REST 接口里，界面只是瘦客户端——而录像链天生不过编解码：录像文件是 **`.mjpeg`（逐帧 JPEG）＋ `.frames.jsonl` 索引**，回放按 offset 直接切 JPEG（`recording_library.py:243`，A 级源码），**不解码不转码**。只有 8092 实时预览走 VPU 硬编 H.264，且那是为了局域网远端省带宽；本地看走 `/api/camera/preview.jpg` 单帧 JPEG 即可。编解码只发生在"把视频嵌进页面给远端看"这一步，**显示网页本身从不过编解码**（Electron 的念头由此否掉：它比 WebKitGTK 更重、一样要 X，见 §六 附录表）。

**原生 UI 只调同一批 REST**（接口清单来自源码，A）：

| 界面动作 | 接口 | 出处 |
|---|---|---|
| 实时预览（单帧） | `GET /api/camera/preview.jpg` | serve_photos.py:171 |
| 开始／停止录像 | `POST /api/mode` `{"mode":…}` | recording_service.py:521 |
| 录像列表 | `GET /api/recordings?page&limit&from&to&trash` | recording_service.py:462 |
| 回放某一秒 | `GET /api/recordings/<id>/frame?at=<sec>` → JPEG | recording_service.py:479 |
| 下载整段 | `GET /api/recordings/<id>.<ext>`（`Content-Disposition: attachment`） | recording_service.py:505 |
| 删除／恢复／彻底删 | `POST /api/trash`／`/api/restore`／`/api/purge` `{"id":…}` | recording_service.py:521 |
| 存储／压缩／保留 | `GET /api/storage`、`GET|POST /api/compression`、`/api/retention` | recording_service.py:456-460 |
| 拍照识别／录入 | `POST /api/recognize`、`/api/recognize-camera`（空体＝从相机取帧）、`/api/enroll`（`X-Person-Name` 头，≤8 MB） | serve_photos.py:227-259 |

**四档对比**（都不需要桌面环境）：

| 档 | 技术 | 新装 | RSS 估 | 开发量 |
|---|---|---|---|---|
| **① 原生直画（推荐）** | Python＋Pillow（板上已有 9.3.0，A）直接画进 udmabuf＋`/dev/input/event*` 自读鼠标 | **0**（中文需 `fonts-wqy-microhei` 1 包，最小档，见 repos/README §2.2） | 40–70 MB | 中，~600–800 行 |
| ② 原生直画·极简 | C＋LVGL（板端 gcc 编） | 0（源码编译） | 10–20 MB | 中高 |
| ③ 半原生 | Xorg 最小集＋Tkinter/GTK3 单窗口 | 20–30 包 | 120–180 MB | 低 |
| ④ 网页 | Xorg＋midori（WebKitGTK） | 57 包 | 230–350 MB | 低 |

①的三个坑：`input_event` 在 aarch64 是 24 B（timeval 16＋type/code/value），相对鼠标读 `EV_REL/REL_X|REL_Y`＋`BTN_LEFT`，要处理热插拔重开；光标自己画（每帧从底图重贴 16×16 位图）；板上只有 6 个字体，中文要装 `fonts-wqy-microhei` 或界面用英文。

**代码落点**：`repos/HA4FPAI/web/offlineHMI/`（见 §十），界面复现先在 102／本机验证、不碰板。

**开机门卫（2026-11-04 她要求"打包成一个单元"）**：`deploy/offlinehmi.service` 一个单元——
开机跑 `hdmi_probe.py` 判定"这块 HDMI 屏有没有人在用"（默认 60 s），判"有"→ exec 起 kiosk，
判"没有"→ 退出 0 不再检测。**判定的硬边界**（板上实测 A）：HDMI 是 PL 单向 TMDS 输出，
引脚约束只有 4 个输出（`AC17/AA15/Y16/W16`），**无 HPD/DDC**；`/sys/class/drm` 无 connector、
`/dev/i2c-*` 不存在、`/sys/kernel/debug/gpio` 无 HPD 线 ⇒ **没有"显示器在不在"的回读信号**，
今天唯一可用的是 L3"一分钟人确认"（画倒计时＋鼠标点击）；等带 DRM 的位流或 HPD 接进 PS 才转自动。

## 十、下一步（顺序不可颠倒）

1. 先在本机／校机把 sink 的代码与逻辑自测编过（**不上板**）；
2. 上板第一枪只做"彩条烟测"：填一张彩条进 udmabuf 尾部、写 `0x54`，看显示器出不出图——一次同时验"位流带 HDMI 读出、`0x54` 可写、udmabuf 可用"；脚本正本＝[../../../workenv/hdmi-kiosk/colorbar_fill.py](../../../workenv/hdmi-kiosk/colorbar_fill.py)（`python3 colorbar_fill.py` 预演、加 `--write` 真切、`--restore` 恢复 `0x07E00000`；**2026-11-04 仅编写、未上板运行**）；
3. 烟测过了再装 Xorg 最小集，用 `xeyes`／`xclock` 验"鼠标能移、指针在 HDMI 上"；
4. 最后才接浏览器与页面（先 netsurf 档验"能看能点"，再按第 3 项决议升级）。

## 相关页面

- [[魔改厂商视频流程部署记录]] —— HDMI 那半截的数据流、每段归属、判活口径的正本
- [[VPU串流直播SOP]] —— 板上现有 MJPEG/HLS 服务面（8092 的替代路径要用）
- [[板端我方代码与产物台账]] —— 每个上板文件的登记
- [[webapp]] —— 前端目录入口（index stub）
- [[webapp]] —— 前端目录的入口页
