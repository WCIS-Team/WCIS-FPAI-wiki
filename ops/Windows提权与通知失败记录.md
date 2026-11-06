# Windows提权与通知失败记录

本页只记**失败**：在这台 Windows（TKMNOPC）上做 SSH 登录通知与免 UAC 提权时，撞到过的坑、报过的错、以及各自怎么绕过去的。

**只看成功步骤的**，去 [[Windows免提权弹通知与SSH登录告警]]——那里是可直接照抄的最小可复现流程，本页是它背后的失败史。

记法：一条一个坑，**先记原始报错原文**，再记根因，最后记绕法。报错原文照抄不改字，因为下次搜就是拿它搜。

---

## 一、WinRT toast 弹不出来

### 1.1 `CreateToastNotifier()` 无参重载报 `0x80070490`

```
Exception calling "Show" ... HRESULT 0x80070490 Element not found
```

**根因**：无参重载靠进程自己的 AppUserModelID 解析出要通知哪个应用。非打包进程没有 package identity，解析不出来。

**迷惑之处**：豆包、PowerToys、MAA、Firefox 这些**开机前就注册好 AUMID** 的应用用无参重载**也一样报这个错**。所以看到这个错**不要去查注册表有没有注册**，注册是好的。

**绕法**：改用字符串重载，把 AUMID 显式传进去：

```powershell
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($Aumid)
```

### 1.2 字符串重载在 Low 完整性下报 `0x80073D54`

```
The process has no package identity. (0x80073D54)
```

**根因**：还是完整性级别。Low 完整性进程调用 WinRT 会走到 package identity 检查。

**绕法**：让脚本跑在**交互会话**里（计划任务，`takomi` / `InteractiveToken`），那里是 Medium 完整性。同一个 AUMID、同一份代码，Medium 下成功。

### 1.3 AUMID 注册成嵌套键 / 带斜杠

**根因**：`HKCU\Software\Classes\AppUserModelId` 下面的 AUMID 必须是**一个键名**。

- 写成 `{GUID}\SSHLoginAlert` ⇒ 多出一层嵌套键，注册等于没注册
- 名字里带 `\` 或 `/` ⇒ `New-Item` 直接失败

**绕法**：键名就用 `{9B2A1C4D-3E5F-4A6B-8C7D-1E2F3A4B5C6D}` 这种形态，一个都不多。

### 1.4 AUMID 只注册了一半

字符串重载要成功，**两处**都得有，缺一不可：

1. `HKCU\Software\Classes\AppUserModelId\<AUMID>`，含 `DisplayName` + `IconUri`
2. 开始菜单里一个 `.lnk`，其 `System.AppUserModel.ID` 等于同一个 AUMID

**根因**：只做第 1 处，第 2 处缺失时字符串重载仍然失败。症状与 1.1 一模一样，极易误判。

### 1.5 提权进程写的 `HKCU` 不是前台用户的

**根因**：用 `Start-Process -Verb RunAs` 提权后，进程跑在管理员账号 `TKMNOPC\tkmta` 下，它的 `HKCU` **不是** `takomi` 的。往 `HKCU:` 写等于写到管理员账号去了。

**绕法**：显式写 `Registry::HKEY_USERS\S-1-5-21-3721062100-2258089301-1718852391-1002\Software\Classes\AppUserModelId\...`（那个 SID 是 takomi 的）。

### 1.6 `[Registry]::Users.CreateSubKey()` 报参数不正确

```
The parameter is incorrect.
```

**根因**：`Microsoft.Win32.Registry` 的那个 API 对这种路径处理不对。

**绕法**：用注册表 provider，即 `Registry::HKEY_USERS\...` 前缀的路径。

### 1.7 写 `.lnk` 时 COM CLSID 用错

```
80040154 Class not registered
```

**根因**：用了 `000214F9`。那是 `IShellLinkW` 的 **IID**，不是 coclass。

**绕法**：coclass 是 `{00021401-0000-0000-C000-000000000046}`。

### 1.8 PROPVARIANT 结构体布局

**根因**：64 位下指针在偏移 8，不显式指定布局会拿到错误偏移。

**绕法**：

```csharp
[StructLayout(LayoutKind.Explicit)]
public struct PROPVARIANT
{
    [FieldOffset(0)] public ushort vt;
    [FieldOffset(8)] public IntPtr pointer;
}
```

### 1.9 从 `.lnk` 读回 `System.AppUserModel.ID` 得到空字符串

**根因**：读回 API 在某些情况下返回空，尽管二进制里明明有那串 UTF-16。

**绕法**：**校验要靠二进制扫描**（在 `.lnk` 文件里找 AUMID 的 UTF-16 字节），不要信读回 API 的返回值。

---

## 二、中文变成乱码

### 2.1 脚本里的中文变成 `??` / 乱码

**根因**：系统 ANSI 代码页是 **936（GBK）**，Windows PowerShell 5.1 按 ACP 解码脚本源码。

**绕法**：脚本与配置文件**一律 ASCII**，中文只放在 `toast-config.json`（UTF-8 无 BOM）里，读的时候 `Get-Content -Raw -Encoding UTF8`。

### 2.2 日志里的中文变成 `??`

**根因**：`Add-Content` 默认按 ANSI 写。

**绕法**：`Add-Content ... -Encoding UTF8`。

---

## 三、事件触发器与去重

### 3.1 事件查询报 "The specified query is invalid"

```
The specified query is invalid.
```

以及 `wevtutil qe` 报：

```
Failed to open event query.
```

**根因**：任务计划程序的事件触发器**不支持 XPath 的 `contains()`**。写成 `*[System[(EventID=4)]][EventData[Data[@Name='payload'][contains(., 'Accepted')]]]` 必然失败。

**绕法**：触发器**只按 EventID 过滤**，`Accepted` 的判断和去重都放到脚本里。

### 3.2 隧道账号把真正的登录记录顶掉

**根因**：这台机器上的 `tunnel` 是反向隧道账号，**每 5 秒重连一次**。如果先做 RecordId 去重、再过滤跳过账号，隧道账号的新记录会把真正的登录记录顶掉（因为它 RecordId 更大）。

**绕法**：**先按 `skipUsers` 过滤，再做去重**。顺序反了就会漏报。

### 3.3 注册计划任务报 "No mapping between account names and security IDs"

**根因**：`<UserId>` 里写错了账号名。这个报错完全不提"用户名拼错了"。

**绕法**：写**裸用户名** `takomi` 或全名 `TKMNOPC\takomi`；`akomi`（少一个字母）和 `TKMNOPC\akomi`（把 takomi 写成 akomi）都会失败。

---

## 四、判据不可信

### 4.1 `Show()` 没抛异常 ≠ 通知弹出来了

**根因**：`Show()` 成功只证明 API 调用没报错，通知面板可能在错误的会话里，或根本没显示。

**绕法**：**在同一个交互会话里截图做像素比对**。本机实测几何：面板 362×108，右缘离屏幕右 18 px、下缘离底 62 px，框内变化密度 67.7%。

### 4.2 截图时机晚了判据失效

**根因**：面板约 4 秒后收缩淡出，密度掉到 8% 以下。

**绕法**：**1.5 秒内截**，晚了就判不出来。

### 4.3 `wpdatABASE.db` 不存在

**根因**：这台机器上那个通知存储文件压根没有。

**绕法**：**别拿它当判据**。

---

## 五、DSH 沙箱的边界

### 5.1 gsudo 在 Low 完整性下完全不可用

```
Error: Sorry, gsudo doesn't allow to elevate from low integrity level.
```

**根因**：DSH 沙箱把子进程压到 **Low**（4096）。gsudo 的这条检查在**查 cache 之前**。

**关键实测**：cache 会话明明活着（`Total active cache sessions: 1`），Low 调用方照样报这个错，`Available for this process: False`。

**绕法**：**不要试图从 DSH 直接调 gsudo**。改走"DSH → Medium 进程 → gsudo"的两跳。

### 5.2 `gsudo cache on` 从 Low 侧看不到任何东西

**根因**：Low 侧连 `gsudo status`、`gsudo service status` 都直接被上面那条挡掉。

**绕法**：这类探测必须放到 Medium 上下文里跑。

### 5.3 计划任务接口被封

```
Schedule.Service COM → 0x80070003 The system cannot find the path specified.
schtasks → Invalid argument/option - 'C:/Users/.../create'
```

**根因**：`schtasks` 那条是 MSYS 的路径转换（`/create` 被当成路径）＋沙箱拦截；`Schedule.Service` 是沙箱直接封了。

**绕法**：MSYS 里跑 `schtasks` 要先 `export MSYS2_ARG_CONV_EXCL='*'`；但沙箱拦截绕不过，只能提权后跑。

### 5.4 `Start-ScheduledTask` 报 Access denied

**根因**：Low 进程没有启动他人任务的权限。

**绕法**：由一个已经提权的进程去 `Start-ScheduledTask`。

### 5.5 Explorer 借道启动被拦

**根因**：`explorer.exe <script>` 无产出。

**绕法**：别用这条路。

### 5.6 沙箱内写不动这些位置

- `C:\ProgramData\...` ⇒ Access denied
- `HKCU` ⇒ Access denied
- `C:\Users\takomi\AppData\Local\...` ⇒ Access denied

**绕法**：提权进程写；但提权进程是 `tkmta`，所以**每用户目标要按 `HKEY_USERS\<takomi-SID>` 或 `C:\Users\takomi\...` 寻址**。

### 5.7 `sshd.exe -t` 报 "no hostkeys available"

```
sshd: no hostkeys available -- exiting.
```

**根因**：Low 完整性读不到 host key 目录，**不是配置错**。

**绕法**：用提权进程跑 `sshd -t`。配置是否正确，用"真登录成功"来判更直接。

### 5.8 TLS 读不到证书存储

```
The underlying connection is closed: An unexpected error occurred on a receive.
  inner: No credentials are available in the security package
```

curl 版是 `SEC_E_NO_CREDENTIALS (0x8009030e)`。

**根因**：Low 完整性读不到用户证书存储，TLS 握手直接失败。

**绕法**：走 Medium 上下文的计划任务。同一个 `Invoke-WebRequest`，Medium 下 http=200。

---

## 六、gsudo cache 的生命周期

### 6.1 cache 会话跟着创建它的进程一起消失

**实测**：`cache on -d 2:00:00` 之后让那个进程退出，20 秒后再查 `Total active cache sessions: 0`——**2 小时的期限根本没用上**。

**根因**：cache 会话挂在调用它的进程树上。

**绕法**：要么让持有者常驻，要么把"起 cache → 干活 → 关 cache"放进同一个进程生命周期里。

### 6.2 `cache on` 会弹 UAC，而且 Medium 侧的监视器看不见

**根因**：`ConsentPromptBehaviorAdmin = 5` ＋ `PromptOnSecureDesktop = 1` ⇒ consent UI 跑在**安全桌面**上。

**实测**：Medium 权限的进程 `Get-Process consent` **一次都看不到**；换成**提权**的监视器才抓到：

```
01:01:29.368 consent pid=6304
...
01:02:32.134 consent pid=6304
```

**绕法**：判"有没有弹 UAC"要用**提权进程**监视 `consent.exe` / `credui.exe`，不能靠 Medium 侧的 `Get-Process`。

### 6.3 cache 存续期间的提权不再弹窗

**实测**：cache 起好后连跑三条提权命令，`consent.exe` 一次都没再出现。

**绕法**：这就是"一次授权、多次使用"的实现方式——起 cache 那一次弹窗，之后安静。

### 6.4 `gsudo cache on` 在 Low 侧连参数都不认

**实测**：Low 侧 `gsudo cache on` 打印"成功"但**没有真起会话**（`CacheSessionsCount` 仍是 0）。

**根因**：同上，Low 下 gsudo 不可用。

**绕法**：在 Medium 上下文里起。

---

## 七、零散

### 7.1 `HttpWebRequest` 的 Content-Type 是受限头

```
The 'Content-Type' header must be modified using the appropriate property or method.
Parameter name: name
```

**根因**：`Content-Type` 不能走 `Headers[]`，那是普通自定义头才用的。

**绕法**：`$req.ContentType = 'text/plain; charset=utf-8'`。

### 7.2 MSYS 把 `/create` 当路径转换

```
Invalid argument/option - 'C:/Users/.../create'
```

**绕法**：`export MSYS2_ARG_CONV_EXCL='*'`。

### 7.3 PowerShell 单元素管道会吞掉输出

**根因**：`$x = & cmd | Out-String` 这类写法，命令恰好只输出一行时，变量可能拿到数组而非字符串，后续拼接会出问题。

**绕法**：统一用 `*>&1` 抓全流。

### 7.4 PowerShell 里带 `&` 的参数会被拆

**根因**：`& $gsudo cmd /c "echo A & echo B"` 这种，PowerShell 与 cmd 两层引号解析打架，实测报 `TerminatorExpectedAtEndOfString`。

**绕法**：把要执行的逻辑**写进 `.cmd` 文件**，再用 `Start-Process -ArgumentList @('cmd','/c', $file)` 调，不要在命令行里拼复合命令。

### 7.5 job 文件里带中文路径 ⇒ job 永久挂起

**现象**：job 一直不结束，`.out` 是空文件，cache 也一直挂着（`Total active cache sessions: 1` 不降）。

**根因**：job 文件是 `.cmd`，cmd.exe 按系统 ANSI 代码页（这台机器 936）解码它，文件里的中文路径被解成乱码，于是 `cmd /c` 在等一个**不存在的文件**——不报错，就是干等。路径传进 `dsh-elevate.ps1` 的 `-Script` 参数时是对的（`Test-Path` 过），坏的只发生在 job 文件正文里。

**绕法**：**job 正文只放 base64**（UTF-8 字节的 base64），中文路径不出现；由 `dsh-job-run.ps1` 解码后在子进程里执行。job 名也做 ASCII 化（`[^A-Za-z0-9._-]` 换成 `_`）。

### 7.6 `Get-Content` 不带 `-Encoding` 读出乱码

**现象**：job 实际跑对了、输出也对，但 DSH 侧读出来是 `涓枃璺娴嬭瘯.ps1`。

**根因**：输出文件是 UTF-8，`Get-Content` 不带 `-Encoding` 时按系统 ANSI（936）读。同一个坑，日志那次是写、这次是读。

**绕法**：`Get-Content $file -Encoding UTF8`。

### 7.7 stderr 里一大坨 CLIXML

**现象**：stderr 出现 `#< CLIXML` 加一大段 `<Objs Version="1.1.0.1" ...>`。

**根因**：脚本里的 `Write-Host` 写的是 Information 流，stdout 被重定向时 PowerShell 会把这些记录**序列化到 stderr**。

**绕法**：执行时把 Information 流并进 stdout——`& 'script.ps1' 6>&1`。

### 7.8 `& $script` 捕获不到 `Write-Host` 的输出

**现象**：在同一个 PowerShell 里用 `& $scriptPath` 调脚本，变量里什么都没有。

**根因**：`Write-Host` 走 Host，不走成功流，`$x = & $script` 捕获不到。

**绕法**：**用子进程 + 重定向**跑脚本（`ProcessStartInfo` + `RedirectStandardOutput`），别在进程内调用。

### 7.9 提权通道跑出来的中文变乱码（误判成通道坏了）

**现象**：中文脚本直接跑正常，走提权通道就乱码。

**根因**：**不是通道的问题**。是 7.6 那个坑——输出文件本身是好的，是读取端没指定编码。

**教训**：先分层验证再下结论。用 `Get-Content -Encoding UTF8` 读一次就知道是哪一边的问题；直接改通道会改错地方。

### 7.10 `Start-Job` 里的监视器看不到 UAC 弹窗

**现象**：Medium 权限的 PowerShell 里 `Get-Process consent` 一次都抓不到，误判成"没弹 UAC"。

**根因**：UAC 同意框跑在**安全桌面**上（`PromptOnSecureDesktop = 1`），普通会话的进程枚举看不到那边的进程。

**绕法**：判"有没有弹 UAC"要用**提权进程**监视。实测换成提权监视器后立刻抓到：

```
01:01:29.368 consent pid=6304
01:01:29.489 consent pid=6304
...
01:02:32.134 consent pid=6304
```

（这一条是 6.2 的成因，此处只强调：**监视器本身也要提权**。）

### 7.11 `Start-Process -PassThru` 的 `ExitCode` 是空的

**现象**：job 明明跑完了、`.out` 也有内容，但 `.done` 里写的是空，`exit code =` 后面什么都没有。

**根因**：`Start-Process -PassThru` 返回的 Process 对象，在 `WaitForExit(ms)` 返回 true 之后 **`ExitCode` 仍可能是 null**。补一次无参 `WaitForExit()` 也不保证。

**绕法**：改用 `System.Diagnostics.ProcessStartInfo` + `Process.Start()`，这样拿到的 `ExitCode` 是可靠的。holder 里的 job 执行已经改成这个写法。

### 7.12 两个 holder 同时在跑

**现象**：日志里同一个 job 被两个 pid 各执行一次；cache 起了又关、关了又起。

**根因**：重装 holder 时只 `Unregister-ScheduledTask` 再 `Start-ScheduledTask`，**旧的那个 holder 进程还活着**（任务注销不等于进程立刻退出）。两个 holder 抢同一个 job 目录。

**绕法**：两处都补上——

- 装之前先 `Stop-ScheduledTask` 并等几秒
- holder 启动时抢一个**命名互斥量**（`Global\DSHElevationHolder`），抢不到就退出

### 7.13 已经有 `.done` 的残留 job 会白起一次 cache

**现象**：日志里出现 `cache on` 紧接着 `cache off`，中间没有 `running job`。

**根因**：holder 先判断"目录里有 job"，再逐个跳过已有 `.done` 的。结果是**为一个不用跑的 job 起了 cache**，而 `cache on` 会弹 UAC——等于白让用户点一次。

**绕法**：判断"有没有活要干"时**先过滤掉已有 `.done` 的 job**，再决定起不起 cache。

### 7.14 一口气弹了 14 次 UAC 全是自己造的

**现象**：一轮排查里用户被反复要求输管理员密码。

**根因**：排查过程中用了 14 次 `Start-Process powershell -Verb RunAs`。`takomi` **不是管理员**（管理员是 `TKMNOPC\tkmta`），所以每次 `-Verb RunAs` 都要走凭据输入框。**明明提权通道已经建好了，却还在用一次性的 `-Verb RunAs`。**

**绕法**：**通道建好之后，任何需要提权的操作一律走通道**（`dsh-elevate.ps1`），一次性的 `-Verb RunAs` 只留给"安装通道本身"。

**要连一次同意框都不要**：用 `install-holder-as-admin.ps1` 把 holder 注册成 tkmta / Highest / Password 模式，holder 自己是管理员，就完全不需要 gsudo 和 cache。

### 7.15 从 DSH 沙箱里跑 git 访问私有库必失败

**现象**：

```
error: cannot create standard input pipe for remote-https: Permission denied
```

**根因**：**不是凭据问题**。DSH 沙箱禁止子进程开命名管道，而 git 的凭据助手正是靠命名管道跟 git 通信。两个 git（MSYS2 版和 Git for Windows 版）都一样失败。

**绕法**：**git 操作走提权通道**。实测在提权上下文里：

```
credential.helper = manager
git ls-remote https://github.com/takomitkm/WCIS-FPAI-wiki HEAD
  b031a2b88d39f63e5e771d1cdcd275d85c3bed09	HEAD
  exit=0
```

`manager` 直接读 Windows 凭据管理器里已存的 `git:https://github.com`，**不弹窗、不要密码**。

### 7.16 `credential.helper = helper-selector` 会弹选择框

**现象**：一个标题类似 "Git Credential Manager" 的小窗口跳出来，要你选用哪个凭据助手。

**根因**：**DSH 自带的那个 git**（`/ucrt64/bin/git`，MSYS2 版）自带一份 gitconfig，里面是 `credential.helper = helper-selector`；而系统 Git（`AppData\Local\Programs\Git\cmd\git.exe`）用的是 `credential.helper = manager`。两套配置不一致，DSH 里跑 git 用的是前者。

**绕法**：**用系统 Git**（`C:\Users\takomi\AppData\Local\Programs\Git\cmd\git.exe`）。它的凭据已经在 Windows 凭据管理器里，什么都不用填。

**注意**：往全局 `~/.gitconfig` 加 `helper = manager` **对 DSH 那个 git 没用**——`credential.helper` 是多值键，两边会叠加，`helper-selector` 仍然排在前面。

---

## 相关页面

- [[Windows免提权弹通知与SSH登录告警]]：对应的成功步骤（最小可复现流程）
- [[状态源与决策记录]]：涉及长期决定时的登记处（凭据单点记账见该页 D-27）
