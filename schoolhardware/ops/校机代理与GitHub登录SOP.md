---
tags: [SOP]
---

# 校机代理与GitHub登录SOP

本页是**可直接照抄的流程**：把校机（`Win11-HV1`）的默认代理指向它本机的 mihomo，并让校机上的 git 能访问三个私有库。

本页只写**校机**这一台；另外两台机器只列身份（第一节），免得再搞混。

---

## 一、三台机器先分清

| 机器 | 地址 / 别名 | 系统 | 用途 | 备注 |
| --- | --- | --- | --- | --- |
| 本机（DSH 宿主） | `192.168.1.107`，主机名 `TKMNOPC`，用户 `takomi` | Windows | 我干活的地方 | 沙箱是 Low IL，TLS/凭据管理器都要走提权通道 |
| PC2 | `192.168.1.102`，ssh 别名 `deb-h61`，用户 `user` | Debian 13 | 跳板 / 中转 | **与校机无关**，别再往它上面装东西 |
| 校机 | `192.168.212.111`，主机名 `Win11-HV1`，用户 `YiZhidi` | Windows 11 | 真正要配的机器 | **没有 UAC、没有管理员权限** |

校机的两个 ssh 别名（`C:\Users\takomi\.ssh\config`）：

- `school-guest` —— 走 `revjump@10.101.54.192:18022`（公网侧）
- `school-guest-lan` —— 走 `revjump@192.168.1.102`（内网侧，**优先用这个**）

身份文件：`C:/Users/Public/app/ssh-school/shell_key`。

> 校机的权威定义是 `C:\Users\takomi\Desktop\school-ssh.bat` 里的 `set "HOST=school-guest"`，改机器前先看它。

---

## 二、校机的网络规矩

### 2.1 mihomo 现状

| 项 | 值 |
| --- | --- |
| 监听 | `127.0.0.1:7890`（`mixed-port`，http 与 socks 同端口） |
| 进程 | `mihomo-windows-amd64-v3-go125.exe`，pid 2268 |
| 配置 | `D:\yzd\proxy\agy\config.yaml` |
| 启动方式 | `%USERPROFILE%\proxy-start.ps1` **脱离式**启动 |

**不要重启 mihomo**：`proxy-start.ps1` 每次跑都会先杀后起，会打断别人正在用的隧道。配置文件里有节点 UUID，**不要贴进任何文档**。

### 2.2 哪个域名走代理、哪个直连

实测（校机上）：

| 目标 | 走代理 7890 | 直连 |
| --- | --- | --- |
| `github.com` | 200（2.1 s） | 超时 |
| `api.github.com` | **403 rate limit**（共享出口 IP 被限） | 200 |

⇒ **`github.com` 走代理，`api.github.com` 直连**。这与本机（DSH 宿主）的规矩同构，只是端口不同（本机是 `127.0.0.1:7897`，校机是 `127.0.0.1:7890`）。

命令行上就体现为两个环境变量：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=api.github.com
```

### 2.3 Edge 的默认代理

Edge 装在 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，**默认跟随系统代理**（WinINET）。所以只要系统代理指向 mihomo，Edge 就走 mihomo。

设置项（全部在 `HKCU`，不需要管理员）：

| 名称 | 值 |
| --- | --- |
| `ProxyEnable` | `1`（DWORD） |
| `ProxyServer` | `127.0.0.1:7890` |
| `ProxyOverride` | `<local>;localhost;127.*;api.github.com;192.168.*;10.*;172.16.*` … `172.31.*` |

绕过表里加 `api.github.com` 是为了绕开限流，加内网段是为了内网设备不经代理。

写入方式（`reg.exe` 建中间键，`New-ItemProperty` 在这台机器上会报 PathNotFound）：

```powershell
$inet = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$edge = 'HKCU:\Software\Policies\Microsoft\Edge'
$px = '127.0.0.1:7890'
$bypass = '<local>;localhost;127.*;api.github.com;192.168.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;172.26.*;172.27.*;172.28.*;172.29.*;172.30.*;172.31.*'

New-ItemProperty -Path $inet -Name ProxyServer -Value $px -PropertyType String -Force | Out-Null
New-ItemProperty -Path $inet -Name ProxyEnable -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $inet -Name ProxyOverride -Value $bypass -PropertyType String -Force | Out-Null
```

### 2.4 Edge 独立策略写不进去（已知限制，别再试）

本想在 `HKCU\Software\Policies\Microsoft\Edge` 写 `ProxyMode=fixed_servers` 把 Edge 钉死在代理上，**被 ACL 拒绝**：

```
HKCU\Software\Policies
  NT AUTHORITY\SYSTEM             FullControl
  BUILTIN\Administrators         FullControl
  WIN11-HV1\YiZhidi               ReadKey      ← 只有读
```

建子键直接「拒绝访问」，要管理员，而校机没有 UAC 权限。**功能上不需要它**（Edge 默认跟随系统代理）。要独立钉死，只能在校机上手动改 `edge://settings` → 系统 → 关掉「使用系统代理设置」→ 手动代理 `127.0.0.1:7890`。

---

## 三、让校机上的 git 访问三个私有库

目标仓库：`takomitkm/WCIS-FPAI`（主库）、`takomitkm/WCIS-FPAI-wiki`、`takomitkm/WCIS-FPAI-repos`。

### 3.1 校机上装了什么

| 件 | 位置 | 说明 |
| --- | --- | --- |
| Git | `C:\Users\YiZhidi\AppData\Local\Programs\Git\cmd\git.exe` | 2.55.0.windows.5 |
| gh | `C:\Users\YiZhidi\gh-dl\gh\bin\gh.exe` | 2.102.0，**绿色 zip 版，不需要安装**（没管理员权限） |

gh 的绿色包：解 `windows_amd64.zip` 到 `gh-dl\`，`gh-dl\gh\bin\gh.exe` 就是可执行文件。

### 3.2 为什么不用 Git Credential Manager

**GCM 在校机上完全不可用**：设备流跑到 `[CreateClient] Git's SSL/TLS backend is: OpenSsl` 之后就没有下文了，没有报错、没有输出，永久挂起。改 `http.sslBackend=openssl` 也没用——**GCM 自带的 .NET HttpClient 不读 git 的这个配置**，它走 .NET Framework 的 TLS 栈，而那台机器的证书吊销检查（CRL）又出不去。

所以校机上一律用 **gh 当凭据助手**，不指望 GCM。

### 3.3 登录：必须用 curl 驱动设备流

gh 自己的设备流在**换 token 那一步反复 EOF**（`Post "https://github.com/login/oauth/access_token": EOF`），代码申请、页面打开都正常，只有换令牌断链。改用 curl 走同一套流程，两个端点都稳定。

**client id 必须用 gh 自己那一枚**：

| client id | 是什么 | 拿到的令牌 | 能不能看私有库 |
| --- | --- | --- | --- |
| **`178c6fc778ccc68e1d6a`** | **GitHub CLI 的经典 OAuth app（gh 自己用的就是这枚）** | `gho_`，scopes `gist, read:org, repo` | **能**（全部私有库） |
| `Iv1.e7b89e013f801f03` | **别的 App**（在 gh 2.102 二进制里，但不是 github.com 用的那枚） | `ghu_`，scopes 空 | 不能 |
| `Iv1.b231c327f1eaa229` | 同上 | `ghu_` | 不能 |
| `Iv1.b507a08c87ecfe98` | 同上 | `ghu_` | 不能 |

**踩过三次的坑**：那几枚 `Iv1.*` 是**别的应用**的 id（授权页上显示的是 tunnel cli、copilot 之类的名字），用它们申请设备码，授权页上同意的是**别人家的应用**，拿回来的令牌对私有库零权限，而 `gh auth status` 还照样显示 "Logged in"、公开库照样能读——**只有私有库 404 才暴露问题**。

**所以规矩是：给用户码之前，先把授权页上的应用名核对出来。** 拿到 client id 的可靠办法是让 gh 自己说：

```bash
GH_DEBUG=api gh auth login --web
```

调试日志里有它发出的请求体：

```
POST https://github.com/login/device/code
client_id=178c6fc778ccc68e1d6a&scope=repo+read%3Aorg+gist
```

凭记忆写 client id 是**行不通**的——本机就因此白费三轮授权。

**完整流程（在校机上跑）**：

```powershell
$px = 'http://127.0.0.1:7890'
$client = '178c6fc778ccc68e1d6a'
$env:HTTP_PROXY = $px
$env:HTTPS_PROXY = $px
$env:NO_PROXY = 'api.github.com'

# 1. apply for a device code
$r = & curl.exe -sS --ssl-no-revoke --http1.1 --proxy $px `
    -X POST -H 'Accept: application/json' -H 'User-Agent: gh/2.102.0' `
    -d "client_id=$client&scope=repo%20read:org%20gist" `
    https://github.com/login/device/code
$txt = ($r -join '')
$dev = [regex]::Match($txt, '"device_code"\s*:\s*"([^"]+)"').Groups[1].Value
$usr = [regex]::Match($txt, '"user_code"\s*:\s*"([^"]+)"').Groups[1].Value
```

把 `$usr` 填进 <https://github.com/login/device>，Authorize。

```powershell
# 2. poll for the token
for ($i = 1; $i -le 200; $i++) {
    $txt = (& curl.exe -sS --ssl-no-revoke --http1.1 --proxy $px `
        -X POST -H 'Accept: application/json' -H 'User-Agent: gh/2.102.0' `
        -d "client_id=$client&device_code=$dev&grant_type=urn:ietf:params:oauth:grant-type:device_code" `
        https://github.com/login/oauth/access_token) -join ''
    if ($txt -match '"access_token"\s*:\s*"([^"]+)"') { $token = $Matches[1]; break }
    Start-Sleep -Seconds 5
}
```

```powershell
# 3. hand the token to gh, then point git at the gh helper
$token | & "$env:USERPROFILE\gh-dl\gh\bin\gh.exe" auth login --hostname github.com --with-token
& "$env:USERPROFILE\gh-dl\gh\bin\gh.exe" auth setup-git
```

验：

```powershell
& "$env:USERPROFILE\gh-dl\gh\bin\gh.exe" auth status
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" ls-remote https://github.com/takomitkm/WCIS-FPAI HEAD
```

### 3.4 备选：把本机的凭据复制过去

本机凭据存在 Windows 凭据管理器里，能正常 push 三个库。把它读出来喂给校机的 git 也可以，代价是同一个 token 落在两台机器上，且**本机读取凭据要提权**（沙箱读不了凭据助手）。

---

## 四、踩过的坑

| 现象 | 根因 | 处置 |
| --- | --- | --- |
| GCM 设备流零输出、永久挂起 | .NET Framework TLS 栈 + CRL 走不出去；`http.sslBackend` 管不到 GCM 自己的 HttpClient | 校机改用 gh 当助手，绕开 GCM |
| gh 设备流换 token 时 EOF | 代理节点在 POST 上断链（code 申请正常） | 改用 curl 走同一套流程 |
| 登录成功但私有库 404 | client id 用错了（`Iv1.*` 那些是别的应用的），同意的是别人家的应用 | 用 gh 自己的 `178c6fc778ccc68e1d6a`；发码前先核对授权页应用名 |
| `gh auth status` 显示 Logged in，公开库能读，私有库 404 | 同上：令牌有效但没有私有库权限 | 看 `Token scopes` 那一行，空的或没有 `repo` 就是错的那枚 |
| `.cmd` 上传后静默无输出 | **纯 LF 批处理在 cmd.exe 上不稳**，必须 CRLF | 上传前统一转 CRLF |
| 起的子进程随 ssh 会话一起死 | `start "" /b` 起的子进程挂在会话上 | 长任务**前台跑**，另开一条 ssh 读日志 |
| 杀掉本地 ssh 后远端进程还在跑 | 远端 PowerShell 不读 stdin，客户端断开它照跑 | 按命令行特征挑进程杀，别按「会话已断」判断 |
| **被脚本拉起的进程会随会话一起被杀** | sshd 的 job object 会清理孙进程 | 长驻进程必须**直接作为 ssh 的远端命令**，不能由另一个脚本 `Start-Process` 拉起 |
| `$Matches` 拿到的是另一个值 | 第二次 `-match` 会覆盖 `$Matches` | 两个字段分别用 `[regex]::Match(...).Groups[1]` 取 |
| 代理下 `api.github.com` 403 | 共享出口 IP 被 GitHub 限流，不是权限问题 | `api.github.com` 直连，`NO_PROXY` 里加上 |
| 策略键写不进去（PathNotFound / 拒绝访问） | `HKCU\Software\Policies` 的 ACL 只给当前用户 ReadKey | 用 `reg.exe` 也一样被拒；改成系统代理路线 |
| cmd 里写 `<local>` 怕转义出问题 | `<` 是 cmd 的重定向字符 | 用 PowerShell 写注册表，`<` 原样传 |

---

## 五、验收

```powershell
# on the guest
$gh = "$env:USERPROFILE\gh-dl\gh\bin\gh.exe"
$git = "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"
& $gh auth status
foreach ($r in @('WCIS-FPAI', 'WCIS-FPAI-wiki', 'WCIS-FPAI-repos')) {
    & $git ls-remote "https://github.com/takomitkm/$r" HEAD
}
```

期望：`gh auth status` 显示已登录且令牌是 `gho_`；三个 `ls-remote` 各自 exit=0 并打出一行 commit 哈希。

代理侧单独验：

```powershell
& curl.exe -sS --ssl-no-revoke --proxy http://127.0.0.1:7890 -o NUL -w "github http=%{http_code}`n" https://github.com
& curl.exe -sS --ssl-no-revoke -o NUL -w "api http=%{http_code}`n" https://api.github.com
```

期望：`github http=200`、`api http=200`。

---

## 相关页面

- [[Windows免提权弹通知与SSH登录告警]] —— 本机的 SSH 登录通知与免 UAC 提权通道
- [[Windows提权与通知失败记录]] —— 上面那套的失败史
