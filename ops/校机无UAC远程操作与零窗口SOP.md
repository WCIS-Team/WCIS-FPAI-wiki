---
tags: [SOP]
---

# 校机无UAC远程操作与零窗口SOP

本页是**可直接照抄的规程**：在一台没有管理员权限、只能经反向 SSH 隧道进去的 Windows（校机 `WIN11-HV1`，用户 `YiZhidi`）上，怎么把命令送进去、怎么让守护程序**一个窗口都不弹**、以及怎么证明"真的没弹"。

触发这次整理的事故：2026-10-23 她报"校机一直在弹 cmd"。根因是 `\RAG-watchdog` 计划任务，**与 SSH 隧道无关**——但顺着查隧道时查出一条重启即断的隐患，一起记在第二节；那条隐患已于 2026-10-25 补脚本闭合，第二节的"现状"段是补完之后的机上读数。

进入校机本身（`school-guest` / `school-guest-lan` 两个别名、身份文件、`school-ssh.bat` 的权威定义）在 [[校机代理与GitHub登录SOP#一、三台机器先分清|校机代理与GitHub登录SOP——一、三台机器先分清]]，本页不重复；本页只管**进去以后**的形态。

---

## 一、先分清归属：弹窗是 RAG，隧道是 SSH

| 面 | 归属 | 判据 |
| --- | --- | --- |
| 每分钟 :01 闪一扇黑窗 | `\RAG-watchdog` 计划任务 | 触发器 `interval=PT1M`、`startBoundary=2026-10-21T16:45:00`；观察器抓到的三扇窗出现在 10:10:01.164 / 10:11:01.125 / 10:12:01.179，逐分钟对齐 |
| 桌面上常驻的一扇 cmd 窗 | v1 看门狗用 WMI 起的服务 | 那扇窗是**真交互控制台**，按键的痕迹就落在服务日志里：`^C` 与 `'6' is not recognized as an internal or external command`（写入 10-23 00:18:07） |
| SSH 隧道 | 与弹窗无关 | 守护 `powershell`（pid 13516）自 10-14 04:47:35、它的 `ssh.exe` 子进程（pid 16120）自 04:47:38 在跑，那之后没有新建过任何窗口；10-25 复核仍是同一对 pid |

隧道那条链是**一次登录起一次、之后常驻**，不会每分钟动；会每分钟动的只有计划任务。这就是"是 RAG 不是 SSH"的依据。

---

## 二、隧道的实际做法：脚本丢过、补回来了、补成了二代

校机侧（实测 2026-10-24 15:45，这条链的形态到 10-25 未变）：

```
Startup\ssh-tunnel-YiZhidi.lnk
  -> C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
     -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden
     -File "C:\Users\YiZhidi\start-ssh-tunnel.ps1"
  -> (pid 13516, 自 10-14 04:47:35)
     "C:\WINDOWS\System32\OpenSSH\ssh.exe" -N -R 13401:127.0.0.1:19022
        -p 18022 -i C:\Users\YiZhidi\.ssh\id_ed25519_tunnel
        -o BatchMode=yes -o ExitOnForwardFailure=yes
        -o ServerAliveInterval=30 -o ServerAliveCountMax=3
        -o StrictHostKeyChecking=yes tunnel@10.101.54.192
```

同一台机上的 sshd 是便携版、只听本机回环：`C:\Users\YiZhidi\sshserver\OpenSSH-Win64\sshd.exe -f …\sshd_config -E …\sshd.log`，`sshd_config` 里 `Port 19022`；它的自启件是 `Startup\sshserver-YiZhidi.lnk` → 同形态的隐藏 powershell → `C:\Users\YiZhidi\sshserver\start-sshd.ps1`（**这个文件存在**）。

于是全链是：

```
校机 sshd  127.0.0.1:19022
  ↑ 校机出向 ssh -R 13401:127.0.0.1:19022 → 10.101.54.192:18022（= PC2）
PC2 本地 127.0.0.1:13401
  ↑ 本机 ProxyCommand：ssh -p 18022 revjump@10.101.54.192 -W 127.0.0.1:13401
本机 ssh school-guest
```

**当时的隐患（10-24 读数，10-25 已闭）**：`C:\Users\YiZhidi\start-ssh-tunnel.ps1` 那时**已不存在**（`Test-Path` 返回 `False`），而进程还活着——所以隧道是"靠上一次登录的那个进程在续命"。同时 `Get-ScheduledTask | Where TaskName -match 'ssh|tunnel|rev'` 返回**空**，没有任何计划任务兜底。**⇒ 校机一重启，反向隧道就回不来**，`ssh school-guest` 会变 `Connection refused`（2026-10-20 已经发生过一次，那天的记录在 [[实时伪tts]] 末尾）。缺失的原因与取证过程（家目录 `*.ps1` 被一次通配清扫带走、窗口 10-14 04:47:38→10-23 08:24:46、PowerShell 日志起点晚于该窗口因此无从指认操作者）不落在这里，那是另一件事的账。

**10-25 补完的现状（A，机上逐件读回）**：`start-ssh-tunnel.ps1` 3,093 B、sha256 `C0876C299D8403500974FDE97CCB47E11DDDCE74BB06A14E6A74F252E6CFCFE4`，同目录新增它的共用库 `tunnel-common.ps1` 3,000 B、sha256 `E509E64FA29345B8B8BE54C466DDDB4976FD4B38EF92BE389F42D4059FDC3162`，两件都 UTF-8 BOM＋全 CRLF（61／62 行）。替换之前先落了 `start-ssh-tunnel.ps1.pre-gen2-20261025-010011.bak`（999 B，sha `C9EB6C1B4F6488AA9D897DBD4C1DB0F04F0FF9CD75B2E8F561CE465F5166FB84`＝10-25 早先按 `.lnk` 命令行逐字节还原的一代），旧件一件没删。`Startup\ssh-tunnel-YiZhidi.lnk` 的目标与参数未动。

补的是**二代**，不是一代的复原：13516 那个进程内存里跑的还是补回的一代，盘上文件已经是二代，所以**下次登录起来的才是二代**。

另外三个自启项同一形态：`embed-llama-autostart.cmd` 内部也是 `powershell -WindowStyle Hidden -File start-llama.ps1`，`mihomo-autostart.cmd` / `mihomo-proxy.cmd` 用 `start "" /min`（那是**最小化**、不是无窗）。按第四节的机制，登录那次各会闪一扇窗——**未实测**，登录瞬间没采样。mihomo 的重启纪律仍在 [[校机代理与GitHub登录SOP#二、校机的网络规矩|校机代理与GitHub登录SOP——二、校机的网络规矩]]，别在这里改。

### 2.1 一代 / 二代 / RDP 孪生件

一代（999 B）的正文是按 `.lnk` 命令行加它还活着的日志反出来的：固定 20 s 重播、`2>>` 整段追加。二代不是一代的复原，它按**同批重写的 RDP 孪生件** `start-tunnel.ps1.disabled`（2,358 B，C=10-03 20:45:40、M=10-06 13:14:04）的骨架重建——那是 10-06 那次重写唯一还留在盘上的产物，函数名、调用点、日志模板都以它为准。

| 维度 | 一代 | 二代 | 依据 |
| --- | --- | --- | --- |
| 退避 | 恒定 20 s | 连续失败 0/1/2/3/4/≥5 ⇒ 20/20/40/80/160/300 s | A，`ssh-tunnel.err` 里实测的阶梯 |
| ssh 的 stderr | 整段 `2>>` 追加 | 只取非空首行，落成 `[WARN] <程序> : <首行>`，临时文件读完即删 | A，孪生件正文 |
| 每次退出 | 无汇总行 | `[WARN] SSH 转发退出 code=255 持续 21s \| 连续失败 1 \| 20s 后重试` | A，逐字命中她日志里的 528 组 |
| 恢复 | 无 | `[INFO] 隧道恢复(持续 5120s)后断开, code=255`，同时清零失败计数 | A，孪生件＋她日志 17 条 INFO |
| 日志体量 | 只增不减（559,108 B／4,396 行） | 超上限重写成末 `KeepErrLines` 行 | 机制 A，阈值见 2.2 |
| 建档编码 | `2>>` 天然是 UTF-16LE | `Initialize-TunnelLog` 显式 `-Encoding unicode`，与现有文件同格式 | A，本机实测 BOM `ff fe` |
| 缺共用库 | 不存在该情况 | 当场 `exit 1` 并写 `[FATAL]` | 我加的闸，见 2.3 |

拨号参数与 pidfile 互斥守卫**两代逐字相同**：`-N -R 13401:127.0.0.1:19022 -p 18022 -i %USERPROFILE%\.ssh\id_ed25519_tunnel -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o UserKnownHostsFile=%USERPROFILE%\.ssh\known_hosts tunnel@10.101.54.192`；pidfile 里的 pid 若仍是活的 `powershell`/`pwsh` 就直接 `exit 0`。

RDP 孪生件与 SSH 版只差四项：`-R 13390:127.0.0.1:3389`、`tunnel.err`/`tunnel.pid`、日志标签写 `RDP`、临时文件前缀 `tun-`；中转机、密钥、退避与日志逻辑同一份。它改名 `.disabled` 之后没再跑，家目录里 `tunnel.err`/`tunnel.pid` 也已不在，`Get-ScheduledTask` 侧 0 命中说明没有任务在拉它。要恢复启用得改名回 `start-tunnel.ps1` 并自配一条 `.lnk`——**没实跑过**。

### 2.2 两个参数只有区间，值是定下来的（C 级，别当实测引用）

- `HealthyAfterSec`（"这次算真连上了、把失败计数清零"的最短存活秒数）：她日志里 `code=255 持续 21s` 后面接的是 `连续失败 1` ⇒ 阈值 > 21；17 条恢复行里最短的持续是 718 s ⇒ 阈值 ≤ 718。**区间 (21, 718]，我取 120**。
- 截断上限：那份 559,108 B 的日志到被删都没触发截断 ⇒ 原阈值只知道 **> 559,108 B**，是下界不是测量。**我取 1 MB／留末 200 行**。

这两个数都不影响协议，只影响掉线风暴时的日志体量和"多少秒算恢复"的判定。

### 2.3 两处没验的，别把整节当已验

1. **二代的循环本体在校机没跑过**。13516 跑的是一代，我不杀它，也不允许第二个守护同时拨号（`ExitOnForwardFailure=yes` 会让第二个直接 255）。机上只验到"两文件解析 0 错＋拿部署后的真文件跑守卫空转 ⇒ exit 0／0 秒／`ssh-tunnel.err` 前后 559,108 B 同一 mtime／临时文件 0 个"这一层。循环、退避、首行提取、截断、恢复分支是在本机沙盒测的（假拨号程序直接 `exit /b 255` 并往 stderr 写一行；**不联网、不碰密钥、不提交任何凭据**）。首次真跑要等下次登录由 `.lnk` 拉起，届时日志首行是一个空行——`Initialize-TunnelLog` 用 `Set-Content ''` 建档，孪生件原样行为。
2. **缺库硬闸是我加的**，一代和孪生件里都没有：`tunnel-common.ps1` 与主脚本同在家目录根，会被同一次 `*.ps1` 通配清扫一起带走；没有它 `Get-NextDelay` 取不到值，`Start-Sleep` 报错后立刻重拨＝零间隔死循环打中转机。所以缺库必须当场停。

---

## 三、把命令送进去

1. **远端默认 shell 是 cmd.exe**。要 sh 只走 `D:/yzd/MSYS2/usr/bin/bash --login`（不带 `--login` 连 `uname` 都找不到），细节在 [[交叉编译主机路由SOP]]。
2. **PowerShell 一律走 `-EncodedCommand`**，脚本本地写成文件再编码，别在 ssh 命令行里嵌套引号：嵌套引号经 cmd.exe 会把路径拆坏，报出来的却是"找不到文件/目录名称无效"——**这个文本和"文件真的不存在"长得一模一样**，只有换 `-EncodedCommand` 复核才能把两者分开（本页第二节那条隐患就是靠这一步才确认的，不是靠猜）。

   ```bash
   # 本地（Git Bash），check.ps1 必须 ASCII
   python -c "
   import base64,subprocess
   raw=open('check.ps1','rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
   b64=base64.b64encode(raw.decode('utf-8').encode('utf-16-le')).decode()
   print(subprocess.run(['ssh','school-guest',
     'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand '+b64],
     capture_output=True,text=True,errors='replace').stdout)"
   ```

3. **多文件部署走 scp，不走 EncodedCommand**：整段脚本编码后会撞 cmd.exe 的 8191 字符上限。 scp 的**本地源路径**不能带盘符，**远端目标带盘符可行**（`scp a.ps1 school-guest:D:/yzd/models/`）。
4. **落盘后逐文件双向核 sha256**，八件全对才算部署完成（这条与 [[校机代理与GitHub登录SOP#四、踩过的坑|校机代理与GitHub登录SOP——四、踩过的坑]] 里的 `.cmd` 必须 CRLF 是同一条纪律的两半）。
5. **含中文的 `.ps1` 必须 UTF-8 BOM＋CRLF 原样逐字节送**，别让它过任何"断言纯 ASCII"或做编码归一的送件器：`rs.py` 那类会直接拒收，而 PS 5.1 无 BOM 时按 GBK 解源码、中文日志串当场烂掉；`Set-Content` 新建文件也是 ANSI。落地用 `certutil -hashfile <文件> SHA256` 回读比对，比 `Get-Content` 转一圈再算可靠得多（第二节那两件就是这么验的）。
6. **备份计划任务别用 `schtasks /query /tn X /xml 1`**——它报 `ERROR: Improper display format type specified`，会把备份写成 3 字节空文件。用：

   ```powershell
   $x = Get-ScheduledTask -TaskName 'RAG-watchdog' | Export-ScheduledTask
   [IO.File]::WriteAllText('D:\yzd\models\rag-watchdog-task.bak-20261023.xml', $x, (New-Object Text.UTF8Encoding $false))
   ```

7. **改自己账号的任务不需要提权**（A，实测）：任务主体是 `YiZhidi`/`Interactive`，`Set-ScheduledTask` 在普通 ssh 会话里直接成功。校机没有 gsudo、也没有本机那套 DSH 提权通道——见 [[Windows免提权弹通知与SSH登录告警]]，那套是 `192.168.1.107` 的，不通用。

---

## 四、为什么必弹：默认终端是 Windows Terminal，且 ssh 落在 session 2

两条实测前提，缺一条结论就不成立：

- **从 ssh 起的进程在 session 2，不是 session 0**：`[Diagnostics.Process]::GetCurrentProcess().SessionId` = `2`，观察器日志首行也写着 `session=2`。⇒ 我（或任何脚本）从 ssh 启动的可见控制台**直接落在她桌面上**。
  > 更正：我一度断言"我的 ssh 通道在 session 0，所以看不见窗"。实测是 2，那句作废。
- **这台机的默认终端是 Windows Terminal**（窗口类 `CASCADIA_HOSTING_WINDOW_CLASS`，标题 `[Windows Terminal]`，子窗 `PseudoConsoleWindow`）。⇒ 任何**被分配了控制台**的程序都会变成 WT 的一扇真窗；而 `powershell -WindowStyle Hidden` 是"窗口已经建好之后才 ShowWindow(SW_HIDE)"，对 WT 的伪控制台不生效。

四种起法的窗口归宿（前两行是病灶，后两行是修法；读数出自第八节那两段 180 s 观察）：

| 起法 | 落到哪种窗 | 可见采样 | 附带后果 |
| --- | --- | --- | --- |
| 计划任务 → `powershell -WindowStyle Hidden -File …` | WT 真窗 | 每分钟一扇，各约 2.7 s | 她看到的"一直弹" |
| `Invoke-CimMethod Win32_Process Create 'cmd /c …'` | 经典可见控制台，**常驻** | 服务跑多久在多久（实测 7.5 h） | 是活的交互控制台：有人按键就打断了服务 |
| `wscript` + `WshShell.Run(cmdline, 0, False)` | 子进程拿到经典 `ConsoleWindowClass`（不再是 WT） | **0**（三个整分钟点各一扇 powershell 控制台窗，6／261／6 个采样点全部不可见） | 无 |
| 脚本内 `Start-Process -WindowStyle Hidden` | `ConsoleWindowClass`（属主是 conhost） | **0**（1222 个采样点里 0 次） | 无 |

---

## 五、零窗口的两条跑法

### 5.1 任务动作套 VBS

`wscript.exe` 不是控制台程序，任务不会为它分配控制台；`WshShell.Run` 的第二个参数 `0` = SW_HIDE 写进 `STARTUPINFO`，子进程**出生即无窗**。`D:\yzd\models\rag_watchdog.vbs` 全文：

```vbs
' rag_watchdog.vbs - zero-window launcher for the every-minute RAG watchdog.
' Task Scheduler starts console programs by allocating a visible console, and
' powershell -WindowStyle Hidden only hides the window AFTER it exists, which is
' the black flash once per minute. wscript.exe is not a console program, and
' WshShell.Run with window style 0 creates the child hidden from the start.
Option Explicit
Dim sh, cmdline
Set sh = CreateObject("Wscript.Shell")
cmdline = """C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe"" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""D:\yzd\models\rag_watchdog.ps1"""
sh.Run cmdline, 0, False
Set sh = Nothing
```

通用件同形态：`D:\yzd\models\run-hidden-ps.vbs`（arg0 = ps1 全路径，后续参数逐个加引号转发），拿来给任意脚本或观察器用。

换任务动作（一条命令，不需要提权）：

```powershell
$a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"D:\yzd\models\rag_watchdog.vbs"'
Set-ScheduledTask -TaskName 'RAG-watchdog' -Action $a | Out-Null
```

### 5.2 脚本内部起子进程

看门狗自己无窗了还不够——它拉起的服务也得无窗。v2 里只此一处：

```powershell
function LaunchHidden($scriptPath) {
    Start-Process -FilePath $env:ComSpec -ArgumentList @('/c', $scriptPath) -WindowStyle Hidden
}
```

`Start-Process -WindowStyle Hidden` 与 5.1 走的是同一个 `STARTF_USESHOWWINDOW`＋SW_HIDE，所以够用；而 `powershell -WindowStyle Hidden` 不够用，因为窗是 WT 替控制台先建好的。

### 5.3 临时任务（观察器、探针）的注册形态

```powershell
$a  = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '"D:\yzd\models\run-hidden-ps.vbs" "D:\yzd\models\rag_obs.ps1" 180 "D:\yzd\models\rag-obs.log" after_v2_action'
$tr = New-ScheduledTaskTrigger -Once -At (Get-Date).AddYears(5)      # 远未来，只靠手动 run
$p  = New-ScheduledTaskPrincipal -UserId 'YiZhidi' -LogonType Interactive
$s  = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::FromHours(2))
Register-ScheduledTask -TaskName 'RAG-obs-1023' -Action $a -Trigger $tr -Principal $p -Settings $s | Out-Null
schtasks /run /tn 'RAG-obs-1023'
```

---

## 六、看门狗 v2：自愈留着、连发掐掉

v1 的两条病在文件头注释里逐字写着（WMI 起可见控制台 + 无冷却导致 1 小时内 7 次重启 rerank）。v2 的改动只有三处，其余逻辑（`/health` 探活、`TcpClient` 判端口、20 s 慢启动宽限、`taskkill /F /T` 按 `*--port $p*` 匹配、12 s 后复述 healthy）原样保留：

```powershell
$CooldownMinutes = 15
$MutexName       = 'Global\RagWatchdogLock'

# 冷却门必须放在 kill 之前：冷却期内既不 kill 也不 launch
$last = LastLaunch $svc.tag
if ($last) {
    $mins = [math]::Round(((Get-Date) - $last).TotalMinutes, 1)
    if ($mins -lt $CooldownMinutes) {
        Say "$($svc.tag) :$p DOWN but in cooldown ($mins of $CooldownMinutes min since last launch) - no kill, no launch"
        continue
    }
}
Say "$($svc.tag) :$p DOWN - starting (hidden) $($svc.script)"
LaunchHidden $svc.script
MarkLaunch $svc.tag
```

命名互斥量拿不到就 `exit 0`——每分钟一次的调度必然重叠，不锁住会两个看门狗抢同一次重启。上次启动时刻记在 `D:\yzd\models\rag-watchdog-state\last-<tag>.txt`（ISO 8601，`Set-Content -Encoding ascii`）。

件清单（2026-10-24 重取，尺寸＋sha256 前 16 位，全在 `D:\yzd\models\`）：

| 件 | B | sha256 前缀 |
| --- | --- | --- |
| `rag_watchdog.ps1`（v2） | 4135 | `E6C3145F4CA94C71` |
| `rag_watchdog.vbs` | 679 | `3A47DC22BC25718E` |
| `run-hidden-ps.vbs`（通用零窗口启动器） | 628 | `7079589E80889BCF` |
| `rag_obs.ps1`（全窗差集观察器） | 3983 | `86D2AD133F7921C0` |
| `rag_watchdog.ps1.bak-20261023`（v1 原件） | 2122 | `92771B9879A9F8FD` |
| `rag-watchdog-task.bak-20261023.xml`（改前任务定义） | 2033 | `4E7735ACC1E8DEA3` |

现役状态读数（2026-10-24 15:44:44）：`state=Ready`、`last run=15:44:01`、`last result=0`、动作 `wscript.exe "D:\yzd\models\rag_watchdog.vbs"`；`:8080 http=200`、`:8081 http=200`；日志里最后一次 DOWN 是 10-23 10:16:06，之后约 29 h 无重启。

回退两条（**未实跑**，第 1 条的两段字符串是备份 XML 里逐字抄出来的改前原值；整份任务定义另有 `rag-watchdog-task.bak-20261023.xml` 可整体重注册）：

```powershell
# 1. 任务动作换回改前那一行 —— 会重新每分钟闪一扇 WT 窗
$a = New-ScheduledTaskAction -Execute 'powershell' `
      -Argument '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File D:\yzd\models\rag_watchdog.ps1'
Set-ScheduledTask -TaskName 'RAG-watchdog' -Action $a | Out-Null
# 2. 脚本本体换回 v1（连带把 WMI 重启和"无冷却"一起换回来）
Copy-Item D:\yzd\models\rag_watchdog.ps1.bak-20261023 D:\yzd\models\rag_watchdog.ps1 -Force
```

---

## 七、长任务与观察器的起法

**任何要活过一条 ssh 通道的东西，都不能由 ssh 命令树直接起**。sshd 的 job object 会连坐清理子进程与孙进程，识别特征是"0 字节日志 + 进程仍在列表里"或"日志停在 STOP 之后"。既有实测口径在 [[校机代理与GitHub登录SOP#四、踩过的坑|校机代理与GitHub登录SOP——四、踩过的坑]]，本页只加一条：**观察器必须在 session 2 里跑**。`EnumWindows` 只看得到调用方所在 session 的 window station（这句是 Win32 语义，本机没做"从 session 0 跑一遍"的对照，实测过的只有"ssh 起的进程在 session 2"）——所以观察器一旦没落在她的会话里，看到的窗会恒为 0，那就是假绿，不是修好了。

所以 5.3 那套"远未来触发器 + `schtasks /run`"是标配：任务把自己注册成 `YiZhidi`/`Interactive`，跑起来就在她的会话里，与 ssh 通道无关。

---

## 八、验收：全窗差集，不是按 pid 过滤

### 8.1 为什么不能按 pid

第一版探针按 pid 过滤，报 `windows=0`——**假阴性**。控制台窗的属主 pid 常常是共享的 conhost：改后那一扇 `[C:\WINDOWS\system32\cmd.exe]` 的 `ConsoleWindowClass`，属主是 `pid=40224(conhost)`，而不是那个 cmd。按 cmd 的 pid 去找它，永远找不到。

正确形态：**先取会话基线（实测 165 扇顶层窗），60 ms 采样 `EnumWindows`，只报"新出现的窗"，再按时间分箱归因**。API 五件套：`EnumWindows` / `IsWindowVisible` / `GetWindowThreadProcessId` / `GetWindowTextW` / `GetClassNameW`。现成件 `D:\yzd\models\rag_obs.ps1`，用法＝`wscript.exe "D:\yzd\models\run-hidden-ps.vbs" "D:\yzd\models\rag_obs.ps1" <时长秒> <日志路径> <标签>`（见 5.3）。

### 8.2 实测数

判据形式：日志尾行 `visible_window_count=<新窗里可见采样大于 0 的扇数>`。

| 段 | 时长 | 采样 | 新窗 | 可见窗 | 细节 |
| --- | --- | --- | --- | --- | --- |
| 改前基线（v1 动作） | 180 s | 2848 | 6 | **6** | 三扇 `[Windows Terminal]`（`CASCADIA_HOSTING_WINDOW_CLASS`）＋三扇 `PseudoConsoleWindow`，逐分钟出现在 :01，各可见约 2.7 s |
| 改后（VBS 动作） | 180 s | 2833 | 13 | **0** | 新窗是 `WSH-Timer`（wscript 自己的计时窗，0/1）、`ConsoleWindowClass` powershell（0/6、0/261、0/6，三个整分钟点各一扇）、`ConsoleWindowClass` cmd（0/1222）、若干 `Default IME` |

改后那三段"整分钟点照常拉起 powershell"是关键：**零窗口没有把自愈一起关掉**。

同一轮里做的端到端：10:16:06 手动 `taskkill /F /T` 掉旧 rerank 树 → 日志 `rerank-Q8_0 :8081 DOWN - starting (hidden) D:\yzd\models\run-rerank-llama.cmd` → 10:16:18 `healthy after restart = True`；被拉起的那个 cmd 控制台在 1222 个采样点里 0 次可见。8080/8081 各自 `/health` 200。

### 8.3 负断言的规矩

报"0 扇可见"之前，必须先确认**同一套采样在改前抓到过 6 扇**（8.2 那行就是这份正对照）。没有正对照的 0，可能是观察器自己没跑起来。

---

## 九、边界、坑表与未决

**权限边界**：`YiZhidi` 不在 `Administrators`（10-24 `net localgroup Administrators` 重取，成员仍是 `Administrator`、`SuRongbin`），校机上没有 UAC 也没有 sudo 通道。⇒ 需要 SYSTEM 的起法（`RunAs=System`、S4U）在这里**不可行**，别照搬本机 DSH 那一套。

**读数的边界**：安全日志里 4624 登录事件在本页场景下**读不到**（返回 0 条）。0 条是权限，不是"没人登录过"——这类"取不到"在任何负断言里都要单独标出来。

| 坑 | 根因 | 处置 |
| --- | --- | --- |
| `powershell -WindowStyle Hidden` 在计划任务里照样闪窗 | 默认终端是 WT，窗由控制台宿主先建好 | 任务动作套 `wscript`（5.1） |
| WMI `Win32_Process Create` 起的服务留一扇常驻黑窗、按键能打断 | 那样起的进程没有控制台，系统给它新建一个可见的 | 换 `Start-Process -WindowStyle Hidden`（5.2） |
| 看门狗 1 小时重启同一服务 7 次 | v1 没有冷却 | 冷却门放在 kill 之前（第六节） |
| 按 pid 过滤窗 → 报 0 扇 | 控制台窗属主是共享 conhost | 全窗差集＋时间分箱（8.1） |
| `schtasks /query /xml 1` 备份写成 3 字节 | 该参数组合在这台机上直接报错 | `Export-ScheduledTask`＋UTF8 无 BOM 写文件 |
| 部署 8 个文件时 EncodedCommand 失败 | cmd.exe 命令行 8191 字符上限 | 多文件走 scp，落盘逐件核 sha |
| 含中文的 ps1 送不进去／进去后日志串变乱码 | 送件器断言纯 ASCII；PS 5.1 无 BOM 按 GBK 解源码 | UTF-8 BOM＋CRLF 逐字节 scp，`certutil -hashfile` 回读（三.5） |
| 共用库被同一次清扫带走后零间隔重拨 | `Get-NextDelay` 取不到值，`Start-Sleep` 报错即返 | 缺库当场 `exit 1` 写 `[FATAL]`（2.3） |
| 从 ssh 起的"临时"进程留在她桌面 | 进程在 session 2 | 长驻/长跑一律挂计划任务（5.3、第七节） |

**未决（等她定）**：① 冷却 15 min 要不要缩短；② 四个开机自启项要不要也换成 `run-hidden-ps.vbs` 包装（现成件已在机上）；③ 夜间 00:02–01:02 那 7 次 rerank 死亡的成因——应用日志 14 h 内 0 条崩溃事件，无法归因，且 4624 读不到，只有"00:18 前后有没有人在那扇窗里按键"这一条她能答；④ 要不要让二代**立刻**接手：那必须停掉 pid 13516 连带它的 ssh 子进程 16120，断的几秒 `ssh school-guest` 连不上；不停就等下次登录自然换。脚本缺失本身已在 10-25 补掉，与上面②那条"自启项要不要套 VBS 包装"是两件事——补脚本治的是重启即断，套包装治的是登录那一扇窗。

**已闭**：`start-ssh-tunnel.ps1` 缺失（10-24 发现，10-25 补）——先按 `.lnk` 命令行逐字节还原一代、落 `.bak`，再按 RDP 孪生件重建二代并部署，读数见第二节。

---

## 相关页面

- [[校机代理与GitHub登录SOP]] —— 怎么进校机、代理与 git；它的第四节是本页第七节连坐杀的既有实测出处
- [[Windows免提权弹通知与SSH登录告警]] —— 本机（`192.168.1.107`）的免 UAC 提权通道，与校机的边界对照
- [[Windows提权与通知失败记录]] —— 提权与"判据不可信"那一类失败史
- [[交叉编译主机路由SOP]] —— 校机上 bash/MSYS2 侧的取数与送件口径
