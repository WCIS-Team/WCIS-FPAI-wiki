---
tags: [SOP]
---

# VPU串流直播SOP

> **本页回答什么问题**：这颗板子的 VPU 硬编直播，从"改代码"一路走到"板上有能解的码流"该怎么走——在哪个根目录、哪台机、哪些命令、静态门禁看什么、产物怎么上板、怎么验收、以及 HLS 那个"每段零参数集"要按哪条路补。
> **前置阅读**：[[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]]（板端口令的唯一出处）、[[交叉编译主机路由SOP]]（哪台机干什么）、[[我方在板外设#7.8 10-15 单独立项复跑：把 PS 侧那半截抠出来、喂仿真 PL 帧（A）|我方在板外设 §7.8]]（这颗 IP 的能力面登记）。
> **本页是操作页**，性质读数与取证过程在 [[板端我方代码与产物台账#二十、VPU 单独跑通验证（2026-10-15，把 A 改完之后只留 PS 侧那半截，喂仿真 PL 帧）|台账 §二十]]；结论标记 A／B／C／D 的口径同 [[状态源与决策记录]]。

---

## 〇、五条先给结论

1. **现役出流仍是 CPU JPEG 预览**（`live_start.sh` 默认 `LIVE_MODE=jpeg`，10-14 下午定的）。硬编那条按她的 `hls 先不修` 挂着，但**件已经齐了**（源码＋aarch64 二进制＋可重放的构建 payload，见第三节），要接就是第七节那几处。
2. **VPU 硬编 H.264 与 JPEG 都在板上真跑通过**（A，10-15）：H.264 是 Main/yuv420p/level 3.1，300 帧进＝300 张图出、内容逐特征对得上；JPEG 是真 JFIF、`ffprobe` 认 `mjpeg`。
3. **码率与 fixed-QP 控不了**（A）：`video_bitrate`/`bitrate_control_mode` 一类不设，`VIDIOC_S_MVX_RATE_CONTROL(OFF)`＋`VIDIOC_S_MVX_QP_EPR` 两条 ioctl **rc=0 但不生效** ⇒ 直播档只能"默认码控＋内容自然出流"，**不要对外承诺固定码率**。JPEG 侧相反，`Compression Quality` 真生效（A）。
4. **HLS 现在不可播**（A）：泵写出的段除首段外**零 SPS/PPS**，任何非首段起播点都是零帧；`-c copy` 打出的 `.ts` 一律 `width=0 height=0 pix_fmt=unknown`。
5. **补头的路线她已经定了：前端播放器自动补**（10-16 提出，登记为 **D-50 决定 2**，**未实施、未实测**）——落地要点、失效条件和三条硬限制写在第八节，做前端时照那一节执行。

---

## 一、什么时候需要走这条 SOP

| 情况 | 要不要走 |
|---|---|
| 要把直播从 JPEG 预览换成硬编 H.264／HLS | 走全文 |
| 只是要给网页出一个"快照／最新帧" | 只走第四～六节的 `vpu_jpg` 那半：JPEG 硬编可用、`buffers=2`、`quality` 可控（第八节那条 HLS 问题与你无关） |
| 只想知道这颗 VPU 能不能用、有什么限制 | 不用上板，读 [[我方在板外设#七、板载 VPU 的参数与编解码清单（2026-10-05 取全，A 级）|§七]]＋§7.8 就够 |
| 相机侧还是 `data_in_num=0`（没帧） | **别在这上面接硬编**——编码链的正控用 `vtc-test.yaml` 或本页第六节的裸帧输入，与相机无关 |

---

## 二、参数与契约（动手前必须照这个来，全是实测）

| 项 | 契约 | 判级 |
|---|---|---|
| 节点／驱动 | `/dev/video0`＝字符设备 81:0，v4l2 driver `mvx`，**只在 MPLANE 上接线**（板上 `v4l2-ctl` 1.18 跑 M2M 走不通，抓出 0 字节） | A |
| 构造参数 | `Encoder(dev, h, w, in_type=VIDEO_OUTPUT_MPLANE(10), in_fmt, out_type=VIDEO_CAPTURE(1), out_fmt, buffer_num)`；厂商默认 `/dev/video0`、1920×1080、60 fps、`buffer_count=6` | A |
| **喂帧门槛** | 攒够 `buffer_num_` 次入队才 `streamon` ⇒ `buffers=6` 时**喂 6 帧以内是零输出且不报错**，要看到东西必须 **≥7 帧** | A |
| `buffer_count` | **H.264 侧只能用 6**（更大触发内核 `MMU ABORT`，内存侧约束）；**JPEG 侧 `buffers=2` 可用**（3 帧出 3 张，streamon 46 ms） | A |
| 一个输出块 | **＝一张图**（150 帧→151 块）。会话首块是**独立的参数集块**，**长度随码率配置变**：30 fps＝33 B、120 fps＝32 B | A |
| 段头取法 | 只能"攒到 IDR 为止"，**禁止硬编码 32 B**（厂商 `hdmi_display_actor.hpp` 那个 4+20+4+8 的硬切就是这么把段写空的） | A |
| 默认 GOP | **恰好 30 帧**，与 `restart_interval` 无关；不带 B 帧（`-c copy` 需要输入带 DTS 这条反证） | A |
| 色域 | H.264 出 `yuv420p`；**JPEG 出有限范围 16–235**（平坦条 RGB 比值恒 0.929＝235/253，白会被压） | A |
| 输出缓冲硬顶 | capture `sizeimage` 恒 **5,242,880 B**（与分辨率无关）；最大实测 1080p q=100 噪声＝1.6 MB/帧仍在内，更高未测 | A／撞顶行为 C |
| 裸帧格式 | RGB565 **不在**编码入口清单里 ⇒ PL 交付的 RGB565 不能直灌，要 PL 出 `UYVY`/`YUYV` 或 CPU 转 `NV12` | A |
| 拷贝语义 | `enqueueDataPtr` 内部按 `sizeimage` 从调用方指针 memcpy ⇒ 喂堆内存与喂 dmabuf 等价，**指针长度算少一个字节就是越界**（10-15 板上就是这里 SIGSEGV） | A |

---

## 三、交付物位置（本次整理结果）

**根目录＝`repos\vpu-live\`**（10-17 按盘上实况改正：`S:\work\WCIS\vpu-live\` 这个位置不存在，见 D-54），32 个文件、3.7 MB，带 `MANIFEST.md5`（相对路径，可直接 `md5sum -c` 复验）：

```
vpu-live/
  payload/live-payload.tar.xz     构建单元（155 条：build-live.sh + proj-live/CMakeLists.txt
                                    + src-live/{src,include/pipeline/**,3p/spdlog}）
  build/   build-live.sh  run-live.sh  run-lastlog.sh
  src/     live_sim.cpp  vpu_jpg.cpp                      ← 两件探针正本
           stream2segfile.hpp  vpu_live_core.hpp          ← H.264 出流那半截（分段＋固定 QP）
           hdmi_display_actor.hpp                        ← 现役 demo 泵（HLS 缺头的那行在这里，未修）
  bin/     live_sim  vpu_jpg                             ← aarch64 产物（与板上件 md5 全等）
  evidence/ full300.h264 seg0.h264 segQ30_0.h264 jpg_q80.jpg f0.png f0.rgb
            raw/uyvy960x540.raw simR/seg0..9.h264 state.example
  logs/    b2.log b3.log build-live-ok.log               ← 校机构建日志（含门禁逐项 PASS）
```

关键件的 md5（A，构建↔本机↔板三侧比过）：

| 件 | 大小 B | md5 |
|---|---|---|
| `bin/live_sim` | 406,888 | `90af179a7cae716c198635d81c890be4`（＝板上 `/root/live_sim`） |
| `bin/vpu_jpg` | 357,952 | `79b0ca82716a95956c88f0da3e53dd30`（＝板上 `/root/vpu_jpg`） |
| `payload/live-payload.tar.xz` | 217,556 | `02f5fcbcee31218a4985eaf0e49de16a` |
| `evidence/raw/uyvy960x540.raw` | 1,036,800 | `53936215f34dc8695044395c8048d685`（＝板上 `/root/vpu/uyvy960x540.raw`） |
| `evidence/jpg_q80.jpg` | 11,333 | `1a8c41e8807590a751b2dc7af82d1920`（板上 `/dev/shm/jq80/img000.jpg` 取回，两侧同） |

复验一条命令：`cd "S:\work\WCIS\repos\vpu-live" && md5sum -c MANIFEST.md5`。

**正本关系要说清**（别把这里当构建目录）：源码与构建脚本的**写作正本仍在** `S:\apps\llm\agentwork\build\fpai_demo_app\...`（台账 #199/#200 的"本地源文件"那一列指向它），`vpu-live/` 是**这一轮的交付快照**；两边同名文件 md5 相同，改代码改正本、改完再重做快照。

---

## 四、编译：只能在校机（本机与板子都不编）

前置门禁两条，缺一条就别起跑：

1. **主机路由**按 [[交叉编译主机路由SOP]]：校机＝编译＋静态门禁；本机＝只有 iCraft CLI／Vivado 的活；**跑＝只能板子**。
2. **空闲检查**（她的批次在跑就别起）：`ssh school-guest` 后看 `tasklist` 里的 `python.exe` 命令行与 asr／xhs 的 `ScheduledTask` State；`Running` 就别起编译。**不杀她的进程、不关她的控制台窗口。**

```bash
# 本机 → 校机：打包（payload 里已经含 build-live.sh 与全部头/源）
cd "S:/apps/llm/agentwork/crosswin"
/d/yzd/MSYS2/usr/bin/bsdtar.exe -cJf live-payload.tar.xz -C . build-live.sh proj-live src-live   # 参数照现役脚本，别自己发明
# 上传后在校机解压到现役根 D:\yzd\WCIS\crosswin\，再跑：
#   ssh school-guest  "D:\\yzd\\MSYS2\\usr\\bin\\bash.exe -lc /d/yzd/WCIS/crosswin/run-live.sh"
```

**四个已经踩过的坑，照抄就能避开**：

| 坑 | 表现 | 规矩 |
|---|---|---|
| ssh 直接起的 `bash.exe` **没有 coreutils** | `dirname/mkdir/date/tee: command not found` | 必须走 `run-live.sh` 那层包装——它先 `export PATH=/d/yzd/MSYS2/usr/bin:...` 再 `exec bash.exe build-live.sh`，ssh 命令行因此不需要任何引号 |
| 嵌套 PowerShell `-Command` 引号 | `UnexpectedToken` | 复杂命令一律**写成脚本文件再调用**，不要内联 |
| **payload 每次重解会覆盖改过的脚本** | 你在 `D:\yzd\WCIS\crosswin\build-live.sh` 上手改的东西被下一次解包抹掉 | 改动回写正本（`S:\work\WCIS\workenv\crosswin\build-live.sh`）再重做 payload |
| **换根要改七处** | 三段入口脚本把现役根写死，照抄到新根（如 `D:\yzd\tmp\sop1016`）会抹掉它的 kit | 换根先读 [[校机交叉编译环境搭建SOP]]；`build-live.sh` 的默认参数是 `TC=/d/yzd/tools/cross/gcc-arm-10.3-2021.07-mingw-w64-i686-aarch64-none-linux-gnu`、`KIT=$HERE/kit`、`UAPI=$HERE/uapi`、`MINGW=/d/yzd/MSYS2/mingw64` 固定，另需 `$HERE/cmake/crosswin-toolchain.cmake`、`$HERE/ref/board-libs.txt` |

**静态门禁（脚本自己跑，exit 0 才算绿）**：ELF64＋AArch64；`DT_NEEDED` 逐个能在 `ref/board-libs.txt` ∪ kit 里找到；`GLIBC ≤ 2.31`、`GLIBCXX ≤ 3.4.28`、`CXXABI ≤ 1.3.11`；`readelf -W`（不带 `-W` 长条目会被截断，门禁会红在不存在的东西上）。脚本自己会打 `md5sum` 供台账登记。

取日志：`run-lastlog.sh` 把最新的 `logs/build-live-*.log` 复制成 `logs/last.log`，再 base64 取回本机（`vpu-test/../logs` 那三份就是这么来的）。

---

## 五、上板

1. **先查占用登记**：`ssh deb-h61 'cat /home/user/Desktop/113.txt'`，不是 `off` 就不动板子；起手改成 `test==on`，收尾（包括被卡住要问她时）改回 `off`。
2. **点火门禁**：VPU 走 `/dev/video0`，与 NPU 无关，**不需要**核 `BOOT.bin` 的 md5；但只要同轮还要碰 `openDevice`／`sdi_probe`，就按 [[BOOTbin位流替换手术]] 那条——现装位流没 NPU 时一点火整机楔死、零 printk。
3. 传文件用 `S:\work\WCIS\workenv\board-push.py`（SFTP put＋`chmod 0755`＋两侧 md5 打 `MATCH`；口令从 `board-ssh.py` 里正则读，脚本本身不含凭据）。**取文件不要用 `board-get.py`**——它的 SFTP get 落 0 字节＋ENOENT，改用 `board-ssh.py ... "base64 <远端路径>"` 再本地 `base64.b64decode`。
4. **上板前逐件 `md5sum` 核**（路由 SOP 第 8 步），核对值就是第三节那张表。
5. **当场登记台账**：[[板端我方代码与产物台账]] 按"本地源＋板上路径＋大小＋md5＋用途＋启动方式"逐件写行；行号是全文件连续的，**先 `grep -oE '^\| *[0-9]+ *\|'` 取现值再 ＋1**（本页写的时候最大是 **202**，下一行＝**203**）。
6. 测试输出**一律写 `/dev/shm`**（tmpfs＝RAM，497 MB）：写 rootfs 会被 eMMC 的 23 MB/s 压死，且留垃圾。**跑完自己清**（`df -h /dev/shm` 回到 0 是验收动作）。⚠ **板子重启会抹掉 `/dev/shm` 的全部内容**（10-15 就有一次重启把测试输入和一轮输出一起带走，中途看到的"零输出"有一部分只是文件没了）——长一点的结论要在重启后复跑一遍再写。

---

## 六、跑与验收

### 6.1 H.264（`live_sim`＝把 PS 侧那半截单独跑起来，喂仿真 PL 帧）

```bash
cd /root && ./live_sim --w 960 --h 540 --fmt uyvy --fps 30 --frames 300 \
     --buffers 6 --seg 30 --seg-ms 1000 --out /dev/shm/h264sim --reuse
```

`RESULT` 一行 16 个字段（照代码顺序）：`fed in chunks segs pic bytes head_bytes wait_streamon_ms span_ms gen_ms push_ms push_avg_ms push_max_ms fps_eff fps_push kbps alive why`。

**验收判据（六零一全，缺一个就不算通）**：

| 判据 | 10-15 实测值 |
|---|---|
| `in == fed`、`pic == fed` | 300 帧 → `in=300`、`pic=300` |
| `chunks == fed + 1`（多的是首块参数集） | 150 帧 → 151 块 |
| `segs` 真的按 `--seg` 切 | 150 帧／`--seg 30` → **10 段** |
| 段内容：`seg0`＝SPS+PPS+IDR+29P，`seg1..`＝IDR+29P | `simR/seg0..9` 就是这个分布 |
| 整份拼接能被解出 | `full300.h264` → `ffprobe -count_frames` 读 `nb_read_frames=300`，`Main/yuv420p/level 3.1` |
| 内容真的对得上（不是"吐出一堆字节"） | 解出的第 0 帧与生成侧的纯色条／每帧位移黑块／帧号刻度带三处特征逐一对上 |
| `why=''` 且 `alive=0` | 死因字段必须为空 |

**量这颗 IP 一定要加 `--reuse`**（第 0 帧之后复用同一块内存）。不加的时候 `fps_eff` 只有 6.8～7.4，根因是**我方彩条生成器单帧 240 ms**，不是 VPU 慢；加了之后 `push_avg_ms=1.9`、`fps_push=539`。`gen_ms`／`push_ms` 两列就是用来把这两笔开销分开的。

`--src <raw>` 可以喂真裸帧（一帧＝`w*h*2` 的 UYVY 或 `w*h*3/2` 的 NV12）；板上现拼多帧：`for i in $(seq 1 12); do cat /root/vpu/uyvy960x540.raw; done > /dev/shm/u12.raw`。

### 6.2 JPEG（`vpu_jpg`＝快照／预览那条路的可行性件）

```bash
cd /root && ./vpu_jpg /dev/shm/u12.raw 960 540 8 uyvy /dev/shm/jq80 80      # <in.raw> <w> <h> <frames> <nv12|uyvy> <outdir> [q] [buffers] [fps] [ri] [mjpeg]
./vpu_jpg /dev/shm/u12.raw 960 540 3 uyvy /dev/shm/b2 80 2                  # buffers=2：3 帧就出图（快照形态）
```

判据：`RESULT ... chunks==fed && images==fed`，块头两字节 `ffd8 ffe0`，取回本机 `ffprobe` 读 `mjpeg,<w>,<h>,yuvj422p`。控制（`q`／`ri`）必须在喂第一帧之前设完——流起来之后再设 codec 类控制会 `EINVAL`→两侧队列 `EIO` 打死会话。

`state.example` 是运行时的 `state` 文件样子，字段：`seq bytes_total frames frames_in_seg head_bytes fps seg_frames seg_ms keep dir pid unix`（直播链的判活就吃这里的 `unix`＋`seq`）。

---

## 七、要把硬编接进现役直播链，改这几处

| 处 | 现状 | 换成 |
|---|---|---|
| `live_start.sh` 的模式 | 默认 `LIVE_MODE=jpeg`（10-14 下午定的默认） | `LIVE_MODE=hls`，或把默认翻过来（**翻默认值要她判**，D-41 那次就是这么定的） |
| 泵 | `hdmi_display_actor.hpp` 里的 H.264 泵（`hdr.assign` 那行会把攒到的头冲掉＝#195 根因） | 换成 `StreamToSegFileSink`（`stream2segfile.hpp`）的"攒到 IDR"契约，或先把那行改成累加 |
| 帧率口径 | `LIVE_FPS` 默认 30 | 相机 1080P25 时要 `LIVE_FPS=25`，否则 25 帧被按 30 fps 打时间戳、播放快约 20 %（**这一条还没定，等真相机帧**） |
| 喂进去的像素 | 显示缓冲是 RGB565 | 硬编不接 RGB565 ⇒ PL 出 `UYVY`/`YUYV`，或 CPU 转 `NV12`（多一次全帧转换，1080p 那档约 3.1 MB 拷贝） |
| 判活 | `hls` 模式＝`/dev/shm/h264/state` 的 `unix` 在走＋`dead=0`＋`.ts` 不为 0 个 | 别再用 `live.stat`／`/stat age_s` 判硬编链（那两个只对 `jpeg` 模式成立） |
| 打包 | `h264d.py` 用 ffmpeg `-c copy` 出 `.ts`＋`index.m3u8` | 输入必须**段段自带参数集**，否则第八节那个零帧问题原样存在（`-c copy` 还要求输入带 DTS＝VPU 不带 B 帧才走得通） |

长跑一律 `setsid` 包一层，否则 SSH 通道超时会把刚起的链一起带走（10-14 丢过一次运行）。

---

## 八、HLS 每段零参数集：**路线已定＝前端播放器自动补**

### 8.1 现象与根因（A）

- **现象**：除 `seg0` 外每一段都是 `IDR + 29×SLICE`、**零 SPS/PPS/SEI/AUD**；单独喂任何一段 → ffmpeg `non-existing PPS 1 referenced` → `no frame!`；打包出的 `.ts` `ffprobe` 读 `width=0 height=0 pix_fmt=unknown`。传输层是好的（拉 10 s＝432,588 B／300 帧），解不出帧。
- **为什么 IDR 不够**：slice 头只写 `pic_parameter_set_id` 指向 PPS，PPS 再指向 SPS；解码器手里没有这两个就**只能丢 slice**。IDR 只保证"不参考前帧"，不保证"自带怎么解我自己"。HLS 的分段语义要求每段能被独立解码。
- **代码位置（两处，都还没改）**：① 现役 demo 泵 `hdmi_display_actor.hpp:289` 的 `hdr.assign(b, b + (io<0 ? s : io))`——首块把 `hdr` 收好后，下一块 IDR 在偏移 0 时 `io=0` 又把 `hdr` **覆盖成空**；② 我方新 sink `stream2segfile.hpp:95` 把攒到的头写进首段之后 `:96` 的 `head_.clear()` 就清了，而 `openSeg()`（`:168`）开新段时什么都不写 ⇒ 段段自足没做到。
- **硬件侧救不了**：`header_mode` 这个控制 ID 在本驱动 `QUERYCTRL` 就 EINVAL（不存在），`restart_interval` 不改 IDR 间隔 ⇒ 没有"设一下就让 VPU 每段重复参数集"的路。

### 8.2 三条补法对照

| 路线 | 改哪 | 代价 | 段的契约 |
|---|---|---|---|
| 泵侧（C++） | `stream2segfile.hpp:96` 不清 `head_`、`openSeg()` 每段开头写一次 | **一次校机交叉编译＋上板**（几十分钟级） | 段自己就能解，任何播放器通 |
| 打包侧（Python） | `h264d.py` remux 前把头拼到段前 | 零编译；但 `seg0` 会被 `pruneOld()` 删，得先把头缓存成静态件 | 出的 `.ts` 能解，`.h264` 原始段仍缺头 |
| **前端侧（她 10-16 提的路线）** | **播放器 fetch 到段之后，把头拼在字节前面再喂 demuxer** | 零板侧改动；但**仍要板侧先给一次头**（`head.bin`，几十字节），且只对自家网页成立 | 段本身**不**自足，可播性绑在这个页面上 |

### 8.3 前端自动补头：落地要点（照这个做，别再重新发现一遍）

1. **头的来源必须是一个固定的静态件**：`seg0` 开头那 32/33 B 就是完整参数集，可以让板侧一个只读小脚本把它抠成 `head.bin`（纯 Python、零编译、不动现役默认值）。**不能靠"前端去拉 seg0"**——`pruneOld()` 会把 `seg0` 删掉，跑久了前端就没处拿了。
2. **缓存必须会失效，按"会话代次"重取**：参数集**长度随 fps 变**（30 fps＝33 B、120 fps＝32 B），换分辨率整块变 ⇒ 用 `state` 里的 `pid`／`seq` 归零当新会话标记，标记一变就重取 `head.bin`。写错的表现是"播着播着黑屏"，很难查。
3. **拼接的位置在 demux 之前，不在 MSE 之后**：浏览器 MSE **只吃 fMP4／WebM，不吃 Annex-B 也不吃 TS**，所以"前端补"实际是"前端拿到 TS／Annex-B → demux → 用缓存的参数集生成 `avcC`/init segment"。用现成 HLS 库（hls.js 这类）就得让头进到它的 demuxer/remuxer 里。**"后续段没有 SPS/PPS 时它是缓存上一段的还是直接报错"各家实现不一样，这条我没实测过，判 C**——真要走这条，先装一个 hls.js 拉几轮真段把它的第一条报错抓下来，再决定拼在字节层还是拼在 `avcC` 层。
4. **重复参数集本身是合法的**：段前已经带 SPS/PPS 再拼一份，解码器接受，不会因为"重复"出错。
5. **范围限制要说全**：前端补只对**你自己的页面**成立。直接吃 `.ts` 的播放器（Safari 原生 HLS、VLC、OBS、硬解码盒子）**不执行你的 JS**，照样零帧。如果这个流还要给别人/别的工具看，泵侧或打包侧那层就省不掉。
6. **验收判据**（做前端时按这四条打勾）：① 从**第 30 秒**（即非首段）起播能看到图；② 播到中途**拖进度条**到任意段能立刻出画面；③ **直播模式**（跳到最后一段起播）出图；④ 人为丢一段、下一段仍能接着解，不需要 reload。这四条任一条挂＝头没补对或缓存没跟着会话失效。

> **状态**：本节路线是 2026-10-16 她提出的（"我前端这边播放器自动补上"），已登记为 **D-50 决定 2**（见 [[状态源与决策记录]]），**记录在案、尚未实施、板上与浏览器侧都没实测**。当前仍然按她的 `hls 先不修` 执行——直播链原样待用，没人动默认值。

---

## 九、坑与禁手（这条链上踩过的，别再踩）

| 条 | 内容 |
|---|---|
| 1 | **禁止在开发板上编译**：993 MB RAM 里 256 MB 是 CMA 池，匿名页额度只有 700～825 MB，编译必挤死现役链。碰要编译的东西就停下来问，并按第四节走校机。 |
| 2 | **别信 `ps -C`**：comm 截 15 字符，全名一律恒空；判进程存在用 `pgrep -f` 或直接看 `/proc/<pid>/cmdline`。板上裸 `ps` 看不到 `setsid`／`nohup` 起的进程。 |
| 3 | **`killself`／`pkill -f` 两个连坐坑**：① pattern 里的 `+` 被 ERE 当量词（要 `[+]` 或写成 `.`）；② pattern 串出现在**调用者自己的命令行**里会连 SSH shell 一起杀，表现为输出截在一行之后什么都没有。 |
| 4 | **`/dev/shm` 是 RAM**：写完就清；重启清空（第五节第 6 条）。 |
| 5 | **算帧字节数别偷懒**：UYVY＝`w*h*2`、NV12＝`w*h*3/2`。写成 `w*h*2/2` 会让驱动按 `sizeimage` memcpy 时越界读，SIGSEGV／退出码 139，strace 里是 `SEGV_ACCERR` 撞线程栈护栏页（10-15 真实发生过，`live_sim.cpp:175`／`vpu_jpg.cpp:142` 两处已修）。 |
| 6 | **`dmesg` 是环形缓冲**，不是日志：10-15 14:41 UTC 我执行过 `dmesg -C` 清过它，"开机以来没有 X"这种话在这台板上不成立；要判"有没有"就起跑前／后各数一次行数。 |
| 7 | **另一条会话也在动这块板和这个仓库**：直播链可能被对方 kill/换档（`sent` 归零≠崩），wiki 文件会在你读完之后被提交。所以：定点最小子串编辑、`git add` **只加具名文件**（绝不 `-A`）、不动对方进程。 |
| 8 | 板上没有 `curl`（`/usr/bin/time` 有）；`STRICT_DEVMEM` 挡 `/dev/mem`；SSH 走 paramiko，plink 会挂死；板钟是 UTC。 |

---

## 相关页面

[[我方在板外设]]（§七 参数与格式清单、§7.8 10-15 复跑）· [[板端我方代码与产物台账]]（§二十 #199–202 两件探针；#195 HLS 缺头根因）· [[板卡镜像实测取证]]（§十五 VPU 硬编取证）· [[交叉编译主机路由SOP]] · [[校机交叉编译环境搭建SOP]] · [[win无wsl交叉编译]] · [[位流构建与SDI信号检测]] · [[状态源与决策记录]]（D-50 两条出流换 VPU＋前端补头路线、D-41 硬编顶掉 JPEG、D-31 队列）· [[BOOTbin位流替换手术]]
