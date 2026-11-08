---
tags: [SOP]
updated: 2026-10-31
---

# 板端磁盘清理SOP

> **这是"板子快满、要怎么安全清"的照抄规程。** 一页管两件事：**怎么判"这堆东西真能删"**，以及**怎么删才不把在跑的别人删掉**。
>
> 判定口径与现读账正在 [[06-磁盘清理清单]]；删了什么、凭什么（逐件墓碑）在 [[板端我方代码与产物台账#廿四、板端磁盘清理（2026-10-31，两轮＝缓存/产物一轮＋她点名删档一轮）|板端我方代码与产物台账——廿四]]。**本页只讲动作顺序与陷阱**。
>
> 一句话：**先量、再查有没有人在用、再核本机有没有副本、才删；每删一批当场 `df` 复读并复查服务。**

---

## 一、什么时候该跑这个

任一条件成立就开跑：`df -h /` 的 Use% **≥ 80%**；或剩余 **< 5G**；或有人报 "No space left on device"。

```bash
ssh root@192.168.1.113 'df -h / | tail -1; df -h /mnt/data /mnt/wcis-emmc | tail -2'
```

**这块板的分区关系先记住（`lsblk` 实测，别搞混）**：

```
mmcblk0   58.4G   ← 一张 SD 卡
 ├─ p1      1G    ← FAT，/mnt/boot（位流；本次开机常不自动挂）
 ├─ p2   26.1G    ← /            ← 满的是它
 └─ p3     30G    ← /mnt/data    ← 同卡第三分区，还有 26G 空
mmcblk1   29.1G   ← eMMC 芯片（独立器件）
 └─ p1   29.1G    ← /mnt/wcis-emmc（挂载带 nosuid,nodev,noexec）
```

⇒ **要腾 `/`，能挪的落点是 `/mnt/data`（没有 `noexec`）；eMMC 是独立介质但 `noexec`，只适合放纯数据/模型。**

---

## 二、第 0 步：查有没有人正在用（**这一步跳过就会删到别人的东西**）

板子是**共享的**。10-31 当天就撞过一次：另一条会话在我删完 2 分钟后，往同一个 `/root/vocos_run` 写回了同族产物（详见台账 §24.3）。

```bash
# 2.1 现役进程（看有没有人正在跑大任务）
ssh root@192.168.1.113 'ps -eo pid,etime,rss,cmd --sort=-rss | head -12'

# 2.2 最近 15 分钟谁在写大文件（最关键的一条）
ssh root@192.168.1.113 'find / -xdev -newermt "-15 minutes" -type f -size +1M 2>/dev/null \
  | grep -v -E "^/(proc|sys|run|dev)|journal" | head -20'

# 2.3 目标目录的 mtime（若 15 分钟内动过 ⇒ 有人在用）
ssh root@192.168.1.113 'stat -c "%y  %n" /root/<目标目录>'
```

**判据**：2.2 有任何命中指向你要删的目录 ⇒ **停手**，先问那条会话；2.1 里有陌生进程占着目标目录 ⇒ 同上。
**注意坑**：`df` 静止 **不等于**没人要用——对方可能刚跑完一轮正在准备下一轮。**只看 `df` 不够，必须看 `find -newermt`。**

---

## 三、第 1 步：量（哪些大、哪些是缓存）

```bash
ssh root@192.168.1.113 '
  du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -12
  echo "--- /root ---"
  du -sh /root/*/ 2>/dev/null | sort -rh
  echo "--- caches ---"
  du -sh /root/.cache /home/*/.cache /var/cache /var/log /tmp 2>/dev/null
  journalctl --disk-usage
'
```

**别只看 `du -sh /root` 的总数**：`/root` 里的大头经常分散在 `wcis-face/candidates`、`funasr/models`、`vocos_run` 这三个"看起来像一个目录"的地方，必须下钻一层。

---

## 四、第 2 步：分级 —— 哪些能直接删

按**风险从低到高**分四级。**只做到第 ① 级也可以，收益通常是几百 M 到 1G。**

### ① 缓存类（零风险，直接删）

```bash
ssh root@192.168.1.113 '
  journalctl --vacuum-size=200M       # 只砍归档、保留最近
  rm -rf /root/.cache/pip /home/*/.cache/pip   # 两个位置都要，装包主要走 fmsh 用户
  apt clean                            # 已下载的 .deb
  rm -rf /var/lib/apt/lists/*          # 187M 级别；下次 apt update 会自己重下
  df -h /
'
```

**判据**：这些删了不影响任何已装的东西。**唯一的代价**是下次 `pip install`／`apt update` 要重下。

> **量级参考（2026-10-31 实测）**：journal 224M（vacuum 后 137M）／`/home/fmsh/.cache/pip` 300M／apt 缓存 86M／`apt/lists` 187M ⇒ 一轮约 **800M–1G**。

### ② 已装包的残留（低风险）

`*.whl` / `*.tar.gz` / `*.tgz` / `*.tar` —— **前提是"已经装进 `site-packages`／解压目录还在"**。

```bash
# 先列，别直接删
ssh root@192.168.1.113 'find /root -maxdepth 1 -type f \( -name "*.whl" -o -name "*.tar.gz" -o -name "*.tgz" -o -name "*.tar" \) -printf "%10s %p\n" | sort -rn'
# 确认每个都有"解压目录在"或"已装"的依据后，再逐个 rm -f
```

**判据**：能 `python3 -c "import <包>"` 通过 ⇒ 这个 wheel 就是残留。有**本机原件**的更好，删了随时重推。

### ③ 测试期产物（中风险 —— 必须先确认"读数正本已入库"）

`out/`、`segments/`、`logs/`、`*.bin` 中间产物、`fix/` 夹具、`results2/`、`logs2/`。

**判据三条，至少满足一条才删**：
1. 该轮的读数**已写进 wiki**（台账／SOP／实测页）；
2. 本机有**逐件副本**（`du -sb` 两遍 + 抽样 `md5sum` 对得上）；
3. 有**确定性重生成脚本**（同种子、同输入）。

```bash
# 本机副本可信度核查（示例：coco）
ssh root@192.168.1.113 'cd <板上目录>; ls | wc -l; du -sb .; md5sum <抽样3件>'
cd <本机对应目录>; ls | wc -l; du -sb .; md5sum <同样3件>   # 件数、字节量级、md5 三项对得上才算有副本
```

> ⚠ **最容易踩的坑**：删了一个"上游数据"，把下游脚本的重生成路径打断了。
> 实例（10-31 真踩过）：删 `v8eval/coco` 后，`compbench/fixtures.py:33` 里写死的 `COCO=/root/v8eval/coco/val2017` 就找不到了 ⇒ `compbench/fix/` **再也重生成不出来**。
> **所以删任何"输入类"目录前，先 `rg -n "<该路径>" /root --glob '*.py' --glob '*.sh'`**，看有没有别的脚本指着它。

### ④ 项目目录 / 模型权重（高风险 —— **必须她点头**）

模型、`candidates/`、代码树、厂商件。**这一级不许自己决定**，按第五节的"提清单"流程走。

---

## 五、第 3 步：要她点头的，怎么提清单

**不要问"要不要清 xxx"，要给一张能决策的表**，每行三条：**现值 + 一句话它是什么 + 凭什么说可清（带证据）**。

模板：

| 项 | 现值 | 是什么 | 凭什么可清（证据） |
|---|---|---|---|
| `<路径>` | `<大小>` | `<一句话>` | `<实测证据／文档原文／本机副本科核结果>` |

**提清单时必带的三类证据**（缺一个就会被追问）：
- **零引用**：`grep -rl "<路径>" /etc/systemd/system /etc/rc.local /root/.bashrc /root/*.json` 无命中 + `ps` 无进程
- **本机有副本／可重建**：`du -sb` 对比 + 抽样 md5 + 重生成命令
- **文档原文**：wiki 里那句"可复原／属残留／已换回"的原话（带 `文件:行号`）

**一条硬规矩**：清单里凡是她之前明说过"删要她明说"的（模型权重、`aec1029` 五颗仅板端 wav、`hb/q3_s*.log` 正本等），**必须单独一行标出来**，不能混在"建议可清"里。

---

## 六、第 4 步：删

```bash
# 模板（每删一批就复读一次 df）
ssh root@192.168.1.113 '
  set -e
  echo "===== 前 ====="; df -h / | tail -1
  <du 一遍确认大小>
  <rm 动作>
  echo "===== 后 ====="; df -h / | tail -1
'
```

**六条纪律**（10-31 实战总结）：

1. **一批一复读** `df`，别删到最后才看。中途有人写回你就得知道是哪一步变的。
2. **用 `rm -rf <具体路径>`，禁止 `find ... -delete` 扫全盘**——扫全盘的删除条件写错一次就是灾难。
3. **白名单式写脚本**比黑名单安全：先列 KEEP，循环里 `case " $KEEP " in *" $n "*) continue;; esac`，白名单之外才删。
4. **删完立刻复查服务**（见第八节）。
5. **`.bin` 类批量删时保留输入件**：`find ... -name "*.bin" ! -name "<已知输入件>" -delete`。
6. **不许顺手重启板子**。重启会带走别人的现场（10-31 就发现板子在 10:20 被重启过，不是我干的，正好撞上）。

---

## 七、第 5 步：从根源止住回涨（journald 上限）

**这一条 10-31 已落，是本 SOP 里唯一改 OS 层的动作。** 出厂 `journald.conf` 的 `SystemMaxUse` 是**注释**状态，默认＝`min(盘 10%, 留 SystemKeepFree)` ⇒ 26G 的 SD 卡上**允许 journal 吃 2.6G**，这就是它反复回涨的根因。

**实测增速**（10-31 板上量的，`journalctl --since "-60min" | wc -c`）：**3.0 MiB/h 原始文本 ≈ 72 MiB/天**（journal 二进制再乘 1.3–1.6）⇒ 225M 存量 ≈ **2.5 天**。

**落点：用 drop-in，不改出厂主文件**（出厂文件保持 1042 B 原样，回滚只需删 drop-in）：

```bash
ssh root@192.168.1.113 '
  mkdir -p /etc/systemd/journald.conf.d
  cat > /etc/systemd/journald.conf.d/99-wcis-size.conf <<"EOF"
[Journal]
SystemMaxUse=256M
SystemMaxFileSize=32M
SystemMaxFiles=20
RuntimeMaxUse=32M
MaxRetentionSec=1month
EOF
  systemctl restart systemd-journald
'
```

**取值理由**：256M ≈ **3.5 天**（够对上"昨天/前天发生了什么"）；想更省改 **128M ≈ 1.8 天**。`RuntimeMaxUse=32M` 是因为 `/run` 是 **100M tmpfs（内存盘）**，运行期 journal 不该在那儿攒。

**怎么判它真生效了**（**唯一可靠的证据是 journald 自己打印的那行**，`systemctl show` 在 systemd 245 不暴露这些属性）：

```bash
ssh root@192.168.1.113 'systemctl restart systemd-journald; sleep 3; \
  journalctl --no-pager -q | grep "is .*max" | tail -2'
```

期望输出（10-31 实测原文）：

```
System Journal (/var/log/journal/…) is 48.0M, max 256.0M, 207.9M free.
```

**没看到 `max 256.0M` 就是没生效**，查：drop-in 文件名是否是 `*.conf`、是否在 `/etc/systemd/journald.conf.d/`、`systemd-analyze cat-config systemd/journald.conf | tail` 能不能看到它。

> ⚠ `systemd-analyze verify <某.conf>` **不支持 .conf 文件**（它只验 unit），报 `Failed to prepare filename … Invalid argument` 是**用法错不是语法错**，别被吓到。

**回滚**：`rm /etc/systemd/journald.conf.d/99-wcis-size.conf && systemctl restart systemd-journald`。

---

## 八、第 6 步：验收（删完必跑）

```bash
ssh root@192.168.1.113 '
  echo "=== 磁盘 ==="; df -h / | tail -1
  echo "=== journal ==="; journalctl --disk-usage
  echo "=== 服务 8 项 ==="
  for s in klar-voice-gateway klar-nlu-engine klar-console klar-autotoken \
           wcis-sdi-vpu-view wcis-face-recording wcis-face-photo wcis-heartbeat; do
    printf "%-24s %s\n" "$s" "$(systemctl is-active $s)"
  done
  echo "=== 端口 ==="; ss -lntp 2>/dev/null | grep -E "8091|8092|10300|10301|10302|10500|10520" | awk "{print \$4}"
'
```

**判据**：
- **8/8 `active`**，端口 7 个全在（8091／8092／10300-10302／10500／10520）。
- ⚠ **`wcis-face-photo` 要看 `Active:` 那行**：它 10-30 曾因 `camera_interlock.py:33`（`RuntimeError: Hardware review required; no automatic SDK reuse`）失败过，**10-31 10:20 重启后自愈**。它现在的 `active` **不能当"清理没事"的证据**——要看 `Active: active (running) since …` 的时刻是否晚于你的删除动作。
- **`df` 的回收量要与"你删的东西"对得上**。对不上就先查有没有别人写回（`find -newermt`），**别当成自己删失败了**。

---

## 九、踩过的坑（照抄时逐条看）

| # | 坑 | 10-31 的现场 | 怎么避 |
|---|---|---|---|
| 1 | **只删了 `/root/.cache/pip`，漏了 `/home/fmsh/.cache/pip`** | 后者 300M，比前者还大 | 两个路径一起写，或 `rm -rf /root/.cache/pip /home/*/.cache/pip` |
| 2 | **`df` 静止就当没人用** | 删完 2 分钟，另一会话往同目录写回 456M | **必跑 `find -newermt "-15 minutes"`** |
| 3 | **删上游输入，打断下游重生成** | `v8eval/coco` 删了 ⇒ `compbench/fixtures.py` 断链 | 删前 `rg -n "<路径>" /root --glob '*.py'` |
| 4 | **flood 测上限把 journal 卡在 cap 下沿来回甩** | 我灌了 22 万行测试噪声，还让 journal 反复 rotate（208M→48M→…） | **别用灌日志的办法验上限**；只认 journald 自己启动那行 `max xxx`。真要造压力，用 `/tmp` 上的临时文件，别往 journal 里灌 |
| 5 | **`systemd-analyze verify *.conf` 报错当成语法错** | `Failed to prepare filename … Invalid argument` | 它是**只验 unit** 的工具；验 conf 用 `systemd-analyze cat-config` |
| 6 | **看 `du -sh /root/*` 以为看全了** | 大头藏在 `wcis-face/candidates`（3.5G）里 | 下钻一层：`du -sh <大头者>/*` |
| 7 | **把 `/mnt/data` 当成独立盘** | 它和 `/` 是**同一张 SD 卡** | `lsblk` 先看一眼再谈"换介质" |
| 8 | **顺手重启板子** | 10-31 10:20 那次重启把别人现场带走 | 清理不用重启；要重启先问 |

---

## 十、清理后必须回写的两处（别攒）

1. **[[板端我方代码与产物台账]]**：每个删掉的件，**当天**把那一行就地改成 `🗑 已删 + 日期`（原 md5/大小划掉、写清凭什么删、本机还有没有副本）。**不删行、不重排号。** 成批删除的全貌记在 §廿四。
   ⇒ 判据：以后照台账去板上找的人，**不能扑空**。
2. **[[06-磁盘清理清单]]**：如果现值已经偏离超过 20%，**当场重刷那一节**（账面数不刷＝埋假事实）。

**为什么这么在意**：台账是"照着它去板上找东西"的唯一依据，留一个已经不存在的路径比留空更有害；这一条 10-31 已写进台账第 9 行的"删除规则"。

## 相关页面

[[06-磁盘清理清单]] · [[板端我方代码与产物台账]] · [[PS/psrt&dev/os]] · [[板卡镜像实测取证]] · [[板端内存上限与心跳日志]] · [[05-DMA启用方案]]
