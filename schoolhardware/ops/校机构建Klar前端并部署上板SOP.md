---
tags: [SOP]
updated: 2026-11-02
---

# 校机构建Klar前端并部署上板SOP

> **这是「改 klar-ha-nlu 的前端 UI，然后让它跑在开发板上」的照抄规程。**
> 一页管三段：**校机装 Node 并构建** → **跨网段把产物搬到板子** → **本机 token 代理让浏览器免 401**。
>
> 上游：`FABBricate-IT-Solutions/klar-ha-nlu`（MIT，前端 `web/` 目录是 React 19 + TS 7 + Vite 8）。
> 板端目标：`/mnt/data/klar/engine/ui`（klar 的 `tower-http serve_dir` 从这里读前端）。
>
> 一句话：**板子不编译，构建在校机；校机与板子跨网段不通，产物经本机中转；token 只留本机，代理只监听 127.0.0.1。**

## 一、为什么必须这么绕（三条硬约束）

| 约束 | 实测证据 | 后果 |
|---|---|---|
| **板子不能编译** | 993 MB 内存、Ubuntu 20.04 focal 只有 Python 3.8.10、无 Node、无 docker/podman | 构建只能在别的机器 |
| **校机与板子跨网段不通** | 校机 `192.168.212.111`，板子 `192.168.1.113`；本机代理 `192.168.1.107:7897` 从校机 TCP 不通 | 产物**必须经本机中转**，校机不能直连板子 |
| **klar 写操作要 token** | 无 token 时只允许 localhost 写入，远程浏览器写操作一律 401 | 需要一个持有 token 的进程 |

## 二、第一步：校机装 Node 并构建前端

### 2.1 环境事实（2026-11-02 实测）

校机是 **Windows 11 Pro for Workstations 虚拟机**（build 26200，`whoami`＝`win11-hv1\yizhidi`），
硬件 EPYC 9654 / 24 核 / 125 GB。**没有 WSL、没有容器**，且装不了：
`SecondLevelAddressTranslationExtensions`=False（宿主未透传嵌套虚拟化），
`whoami /groups` 是 Medium Mandatory Level（非管理员）。

⇒ **一切用便携版，不碰系统目录、不改系统 PATH、不改注册表。**

### 2.2 装 Node（便携 zip）

版本是实读 `https://nodejs.org/dist/index.json` 定的：当时最新 LTS 是 v26.13.0（转 LTS 才 4 天），
选了更成熟的 **v24.22.2**。

```powershell
# 探测最新 LTS（别猜版本号）
curl.exe -s https://nodejs.org/dist/index.json

# 下载官方 zip（带超时保护，别无超时死等）
curl.exe -L -o D:\yzd\tools\node\node.zip --max-time 600 `
  https://nodejs.org/dist/v24.22.2/node-v24.22.2-win-x64.zip

# 解压
Expand-Archive D:\yzd\tools\node\node.zip -DestinationPath D:\yzd\tools\node\
```

**nodejs.org 直连可用**（实测 37.7 MB / 86 s），不必换镜像。若失败再试
`https://npmmirror.com/mirrors/node/`。

### 2.3 npm 配置（C 盘只剩 19.5 GB，缓存必须挪到 D 盘）

```powershell
D:\yzd\tools\node\node-v24.22.2-win-x64\npm.cmd config set cache D:\yzd\tools\node\npm-cache
D:\yzd\tools\node\node-v24.22.2-win-x64\npm.cmd config set registry https://registry.npmmirror.com
```

### 2.4 取源码

```powershell
# 直连 github.com / codeload 从校机会超时；走 gh-proxy.com（实测 200）
git clone https://gh-proxy.com/https://github.com/FABBricate-IT-Solutions/klar-ha-nlu.git `
  D:\yzd\WCIS\klar-ha-nlu
cd D:\yzd\WCIS\klar-ha-nlu
git fetch --unshallow --tags
```

**克隆路线实测表**（校机视角）：

| 路线 | 结果 |
|---|---|
| `github.com` / `codeload.github.com` 直连 | **超时** |
| 本机代理 `192.168.1.107:7897` | **不可达**（跨网段） |
| `ghfast.top` | 403 |
| `ghproxy.net` / `hub.fastgit.xyz` | 超时 |
| **`gh-proxy.com`** | **200，可用**（clone 65 s） |
| `gitee.com` | 200 但无该仓库镜像 |

### 2.5 构建

```powershell
cd D:\yzd\WCIS\klar-ha-nlu\web
D:\yzd\tools\node\node-v24.22.2-win-x64\npm.cmd ci
D:\yzd\tools\node\node-v24.22.2-win-x64\npm.cmd run build
```

`npm run build` ＝ `tsc --noEmit && vite build`（Vite 8 走 rolldown，695 ms）。

**产物**（`web\dist\`，共 2,996,141 B ≈ 2.86 MiB）：

| 文件 | 字节 |
|---|---|
| `dist\index.html` | 433 |
| `dist\assets\index-Bg17n22J.js` | 2,809,902 |
| `dist\assets\index-K2aBKsED.css` | 124,379 |
| `dist\assets\klar-mark-CxFncPff.png` | 61,427 |

`index.html` 用 `base:"./"` 相对路径引资源 ⇒ 产物可放任意子目录由后端托管。

### 2.6 ⚠️ 最大的坑：Windows OpenSSH 会话断开会杀掉远端子进程

Windows OpenSSH 把会话放进一个 **job object**，`Start-Process -WindowStyle Hidden`
起的子进程照样被带走。后果：

- 第一次 `npm install` 在 ~90 秒处被砍，留下**截断的** `node_modules\fdir\dist\index.mjs`
  （2351 B，末尾半句函数）
- 于是 `tsc` 报 `SyntaxError: Unexpected end of input` —— **看着像代码坏了，其实是安装被打断**

**规矩：**

1. 长任务**让 ssh 一直挂着跑完**，不要 detached、不要后台化后立刻断连
2. 已经坏了：`Remove-Item node_modules -Recurse -Force` + `npm ci` 重来
   —— **别指望增量修复**（第二次 `npm install` 只报 "changed 229 packages"，
   根本不校验已有文件）

### 2.7 其他坑

| 现象 | 原因 | 解法 |
|---|---|---|
| `ssh host 'powershell ... -File X.ps1; 别的'` 报「没有 .ps1 扩展名」 | `;` 被 PowerShell 当成 `-File` 参数的一部分 | 带 `;` 的一律包进 `cmd /c "..."` |
| vite 输出全是 ANSI 转义码 | — | PowerShell 读日志先 `-replace "\x1b\[[0-9;]*m"` |
| 远程控制台中文报错乱码 | 控制台是 GBK | 不影响判据，**别把「乱码」当「失败」** |
| `ConvertFrom-Json` 读 `package-lock.json` 报 name 字段无效 | UTF-8 无 BOM 被按 GBK 读 | 编码问题，不是文件坏 |

### 2.8 smoke test 判据（**别用加注释测**）

改 `src/main.tsx` 里一个**字符串字面量**（如 `klar_theme` → `klar_theme_probe`）→
重建 → 产物 hash 变化（`index-Bg17n22J.js` → `index-CsiEjWsM.js`）
且新 bundle 里能搜到该字符串 → `git checkout` 还原 → 重建回原 hash → `git status` clean。

> **加注释测不出 hash 变化**——注释被 minify 掉了。第一次 smoke test 就栽在这。

## 三、第二步：产物搬到板子（跨网段）

校机（`192.168.212.x`）**不能**直连板子（`192.168.1.x`），必须经本机 `192.168.1.107` 中转。

**用现成脚本**（在 `repos/HA4FPAI/klar/deploy/deploy-klar-ui.sh`）：

```bash
bash repos/HA4FPAI/klar/deploy/deploy-klar-ui.sh              # 校机构建 + 部署
bash repos/HA4FPAI/klar/deploy/deploy-klar-ui.sh --no-build   # 只部署已有 dist
bash repos/HA4FPAI/klar/deploy/deploy-klar-ui.sh --rollback    # 回滚到最近备份
```

脚本流程与判据：

1. 校机 `npm run build`（ssh 挂着跑，不 detach）
2. `tar -cf - .` 从校机取回 `dist`
3. 板上备份旧 UI 到 `/mnt/data/klar/ui-backups/<时间戳>/`
4. 传到 `/tmp/klar-ui-new`，**解包校验后再替换**（避免半新半旧）
5. **逐文件 md5 比对**（本机 vs 板子），不一致则提示回滚
6. 探活：`systemctl is-active klar-nlu-engine` + `curl http://192.168.1.113:10520/` 应 200

**回滚**：`--rollback` 把最近备份拷回，旧的那份留在 `$BOARD_UI.broken`。

> **浏览器要强刷（Ctrl+F5）**，否则可能继续用缓存的旧 JS。

### 3.1 可复现性验证（关键证据）

校机构建产物与板上原有 UI **字节级一致**：

| 文件 | MD5（两边相同） |
|---|---|
| `index-Bg17n22J.js` | `ba3d53327346f3636d2aaf603d8be0a1` |
| `index-K2aBKsED.css` | `90fb11071c9f6524316d66ff44b5aee3` |
| `klar-mark-CxFncPff.png` | `aab55c9f5506ae86229fa3d2b7d11576` |

⇒ 板上 UI 确认来自 commit `ab8d036`（release 2026.10.10），
且**构建完全可复现** ⇒ 改完源码可以放心替换。

## 四、第三步：本机 token 代理（免 401）

### 4.1 401 根因

klar 无 token 时**只允许 localhost 写入**（日志：`Kein Token: Schreiben nur von localhost`），
远程浏览器的写操作一律 401。前端从 `localStorage.getItem('klar_token')` 读值，
塞进 `x-klar-token` 头（源码 `web/src/api.ts`）。服务端接受两种头：

| 请求头 | 结果 |
|---|---|
| 无 | **401** |
| `x-klar-token: <token>` | **200** |
| `Authorization: Bearer <token>` | **200** |

### 4.2 ⚠️ 已废弃的错误做法（在板子上跑代理）

第一版在**板子**上跑 10521 代理，把 token **明文注入 HTML**：

```html
<script>localStorage.setItem('klar_token', "336b...")</script>
```

**这是漏洞**——任何能访问板子 10521 的人 `curl` 一下就拿到 token。已彻底删除。

### 4.3 正确做法：token 只留本机

```
浏览器 → http://127.0.0.1:10521/  ← 本机代理（只监听 127.0.0.1）
              ↓ 无条件补 x-klar-token
          http://192.168.1.113:10520  ← 板子
```

**一次性配置**（把板子的 token 抄到本机）：

```powershell
plink -ssh -batch -pw fmsh root@192.168.1.113 "cat /mnt/data/klar/.klar-token" > "$env:USERPROFILE\.klar-token"
```

**每次使用**：双击 `workenv/klar-local-proxy/klar-local-proxy.cmd`，窗口别关，
浏览器开 **http://127.0.0.1:10521/**。

> 代理脚本**不入仓库**（按 AGENTS 硬规矩，个人一次性工具落 `workenv/`），所以 `repos/` 里找不到它，去 `workenv/klar-local-proxy/` 拿。

代理**不再往页面注入任何东西**——前端读不到 localStorage 就不发头，
代理无条件补上。所以**页面 HTML 里明文 token 出现 0 次**。

### 4.4 判据

```powershell
# 通过代理：写操作应 200
curl -X POST -H "Content-Type: application/json" -d '{"personality":"default",...}' `
     http://127.0.0.1:10521/api/settings
# 对照：直连板子仍 401（证明是代理的功劳）
curl -X POST -H "Content-Type: application/json" -d '{...}' http://192.168.1.113:10520/api/settings
# 页面里不该有明文 token
curl -s http://127.0.0.1:10521/ | Select-String "localStorage.setItem"
```

浏览器实测：`hasTokenPrompt=false`、SPA 正常渲染（`root` 有子节点）、控制台仅 `favicon.ico` 404。

### 4.5 安全对比

| | 旧（板子代理） | 新（本机代理） |
|---|---|---|
| token 存哪 | 板子，且注入 HTML | **只在本机文件** |
| 谁能拿到 | **任何能访问 10521 的人** | 只有能登本机的人 |
| 监听范围 | `0.0.0.0:10521` | **`127.0.0.1:10521`** |
| 明文出现在页面 | **是** | **否** |

## 五、当前状态（2026-11-02 实测）

| 项 | 值 |
|---|---|
| Node / npm | v24.22.2 / 11.19.1（`D:\yzd\tools\node\`）|
| 源码 | `D:\yzd\WCIS\klar-ha-nlu\`，commit `ab8d036`（release 2026.10.10），已 unshallow 657 commit |
| 构建 | `npm ci` 21.3 s（热缓存）→ `npm run build` 695 ms |
| 板端 UI | `/mnt/data/klar/engine/ui`，`KLAR_UI_DIR` 必须显式指向它（否则显示德语占位页 "Klar UI nicht gebaut"）|
| 板端备份 | `/mnt/data/klar/ui-backups/<时间戳>/` |
| 本机代理 | `127.0.0.1:10521`，token 在 `%USERPROFILE%\.klar-token`（**已 gitignore**）|

### 相关仓库地址（2026-11-02 改名后）

| 仓库 | 地址 | 说明 |
|---|---|---|
| **本项目（板载语音栈）** | `https://github.com/takomitkm/HA4FPAI.git` | 2026-11-02 由 `HA4FPAI-AIGC` 改名而来（GitHub API `PATCH /repos/{owner}/{repo}`，保留全部历史与私有性）。**旧 clone URL 仍可拉**（GitHub 自动重定向）|
| klar 上游 | `https://github.com/FABBricate-IT-Solutions/klar-ha-nlu` | MIT；板端用其 Release 二进制，前端源码在校机 |
| 父库 `repos/` | `repos/.gitmodules` 里 `submodule.HA4FPAI.url` | 改名后已跟上新地址 |

> **子模块指针 bump 是另一个动作**（AGENTS.md 规矩，默认不做，要她当次明说）。
> 本次改名只提交了 `.gitmodules` 的 URL 一行；指针仍指向改名时远端 master 所在的 commit，
> 该 commit 在新仓库里可正常拉到。

## 六、遗留边界

- **`npm run dev` 不能端到端**：它的 `/api` 代理指向 `127.0.0.1:10520` 的 Rust 引擎，
  我们**没有构建 Rust**，所以本地只能看 UI 骨架、接口 404。
  但这不影响实际工作流——我们走「构建静态 dist → 部署到板子 → 板子上真引擎跑」，比 dev server 更真实。
- **产物 js 2.68 MiB 单 chunk**（recharts + base-ui 全进主包，没做 code split），vite 不报警但值得留意。
- **板子 UI 由 `KLAR_UI_DIR` 指定**，不是默认的 `/usr/share/klar/ui`。

## 相关页面

- [[校机交叉编译环境搭建SOP]] — 校机与交叉编译链路的正本
- [[校机无容器交叉编译]] — 校机没有容器的应对
- [[交叉编译主机路由SOP]] — 三台机路由口径
- [[板端磁盘清理SOP]] — 板端产物与清理纪律
- [[PS/psrt&dev/os]] — 我方对板端 OS 的全部改动（journald 上限、swap 等）
