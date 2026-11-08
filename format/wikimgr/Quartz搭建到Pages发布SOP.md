---
tags: [SOP]
---

# Quartz搭建到Pages发布SOP

> 定稿 2026-10-18（2026-10-20 按 D-65 整体改判：站点搬进文档库自己构建）。这页只管一件事：**wiki 里的 Markdown 和图片怎么变成线上站点，以及坏了查哪里**。一次性设置装在哪、日常一步触发什么、内容集从哪里改、缓存为什么有时慢十分钟、失败看哪一行。为什么这么定的判据与全部验收读数的正本不在这页，在 [[状态源与决策记录#D-58 · 站点与 vault：private＋Free 开不了 Pages 只能出制品、图片要在生成副本里写全路径、OFM 的标签解析关掉|状态源与决策记录——D-58]]（方案与图片那条）与 [[状态源与决策记录#D-65 · 站点搬进文档库：push 即重建、私有库 Pages 靠 Pro 档、主库不再有 site/|状态源与决策记录——D-65]]（搬迁与发布面这条）。
>
> 线上地址：**https://takomitkm.github.io/WCIS-FPAI-wiki/**。站点就建在文档库里，**改完笔记推上 `wiki` 库的 `main` 就重出站点**，没有中间环节。这台机器没有 Node，构建全在 Actions 里跑——库里既没有 Quartz 本体，也没有 `site/content/` 和构建产物，本机不要试图起本地构建。

## 一、正本只有四处（全在文档库 `WCIS-FPAI-wiki`，主库 `WCIS-FPAI` 已不再放站点）

| 文件 | 管什么 | 动手前先想 |
|---|---|---|
| `site/quartz.config.yaml` | Quartz 配置与启用的 35 件插件；**剔一页不发也在这里**（`configuration.ignorePatterns`）；`baseUrl` 决定站点前缀，现为 `takomitkm.github.io/WCIS-FPAI-wiki` | 插件来源要写成 v5.0.0 那笔 tag 认的 `github:quartz-community/…` 形式，v5 分支的 npm 包名它不认 |
| `site/quartz.lock.json` | 配置启用的那 34 件插件各自的 commit | 加/删插件要同时改这份，`plugin install` 只按 lockfile 装，配置里多出来的一件靠 `plugin resolve` 补。**它的 hash 在插件缓存 key 里**，动它就等于冷构建一轮 |
| `site/make-content.py` | 内容装配：挑页、复制媒体、注入日期、改写图片路径 | **以库根为内容树**（`TREES = ("",)`），页面在站点上的路径就是它在库里的路径、不再套一层 `wiki/`；`site/`、`qbuild/`、`public/` 在 `SKIP_DIRS` 里，所以它不会把自己的产物当原料吃进去。**剔一页不发有两条路**：整目录/按文件名走 `RAW_DIRS`／`RAW_FILES`（`--all` 会放行），或按文件名进 `NEVER_PUBLISH`（**`--all` 也不放行**，现值只有 `agent.md`，理由见 [[状态源与决策记录#D-70 · 站点只发标题检索、agent.md 剔出内容集，顺带把客户端里那批根绝对路径改挂到站点根\|状态源与决策记录——D-70]] 决定 1） |
| `.github/workflows/deploy.yml` | 拉 Quartz、装依赖、跑装配、构建、**加固防爬＋剪掉索引正文＋把客户端改挂站点根＋把每页重复的样式表外置**、上传制品、发布 Pages | 发布那一步有**仓库变量开关**：`Upload Pages artifact` 与 `deploy` 作业都挂 `if: vars.PUBLISH != 'false'`。极性是"不等于 false"，所以**不建变量＝照常发布**；把 `PUBLISH` 建成 `false` 只是不部署（站点冻结在最后一次部署、现有 URL 全 200），要停构建与分钟得禁用工作流。判据与三档口径见 [[状态源与决策记录#D-68 · 发布开关：仓库变量 PUBLISH 只掐部署那一步，站点冻结在最后一次部署\|状态源与决策记录——D-68]] |
| `site/robots.txt` | 交给爬虫的那张"不许来"的告示：`User-agent: *` ＋ `Disallow: /`，再按名字点名 40 个搜索引擎与 AI 抓取器 | **它不在库根也不由 Pages 读**，是 `harden-site.py` 在构建后复制进产物根的。改它不用改工作流 |
| `site/harden-site.py` | 构建后、上传前那一步（工作流里叫 `Harden and trim output`）：写 robots.txt、往每个 HTML 注入 `noindex` 那条 meta、删掉 `sitemap.xml` **与 RSS `index.xml`** 这些爬虫索引、**把 `static/contentIndex.json` 里每条正文删掉**、**把 `postscript.js` 里那批域名根路径改挂到站点根**、**把检索的字段列表从只查标题改成标题＋标签**（`index:["title","content","tags"]`，1 处）、**把每页逐字重复的那块内联样式表抽成一个外链**（`assets/site-<12 位摘要>.css`） | **全是硬门禁**：产物里没 HTML、某个文件找不到 `<head>`、`contentIndex.json` 不在或不是按 slug 索引的对象、一条正文都没删掉、四组字面量的出现次数不是 3／1／3 与 1、**最大那块 `<style>` 在页间不一致或树处于半改状态**——任何一条对不上就 `exit 1`，宁可不出站点。防爬那两样是请求不是强制，边界见 [[状态源与决策记录#D-67 · 全站禁止爬虫：deny-all robots.txt ＋ 每页 noindex ＋ 删掉 sitemap，Pages 这一层发不出 X-Robots-Tag\|状态源与决策记录——D-67]] 决定 3；检索与改根两样见 [[状态源与决策记录#D-70 · 站点只发标题检索、agent.md 剔出内容集，顺带把客户端里那批根绝对路径改挂到站点根\|状态源与决策记录——D-70]] 决定 2 与决定 3，字段列表那一改和"全库标签为空"的读数见 [[状态源与决策记录#D-71 · 检索字段加进标签，同日记下"全库标签为空"这个事实；过程记录成页\|状态源与决策记录——D-71]]，样式表外置与 RSS 那一漏见 [[状态源与决策记录#D-73 · 每页重复的 41.8 万 B 内联样式表抽成一个可缓存外链，顺带补上删爬虫索引时漏掉的 RSS\|状态源与决策记录——D-73]] |

Obsidian 的入口是仓库根（本库自己就是 vault，配置在 `.obsidian\`，决策 D-59）。装配器和 `check-md.py` 本来就直接读目录树，不经 Obsidian。

## 二、一次性设置（1、2 已做完并有认证读数，3 **现在建成了 `false`＝构建照跑、不部署**，4 是她手动）

| 项 | 在哪做 | 要达到的状态 |
|---|---|---|
| 1 库可见性与套餐 | 仓库 Settings → Details；账户套餐 | 库保持 `private`。**私有库能不能发 Pages 由套餐决定，不由可见性决定**：官方原文是"GitHub Pages is available in public repositories with GitHub Free … and in public and **private** repositories with GitHub Pro, GitHub Team, GitHub Enterprise Cloud"（2026-10-20 逐字取原文 HTML，非摘要）。学生认证给的就是 Pro 档，所以 D-58 那句"private＋Free 开不了 Pages"现在只描述 Free 时期；个人套餐在 REST 里没有读数（`/user` 与 `/users/{login}` 的 `plan` 恒为 `null`），**唯一的判据是一次真实部署成功** |
| 2 Pages 来源 | 仓库 Settings → Pages → Build and deployment → Source | **GitHub Actions**。API 复核口径：`build_type = workflow`、`source = {branch: main, path: /}`。本次是 `POST /repos/takomitkm/WCIS-FPAI-wiki/pages {"build_type":"workflow"}` 建起来的（201），响应里 `public: true` |
| 3 发布开关 | 仓库 Settings → Actions → General → Variables（`Create variable`） | **10-20 起是活的**：变量名 `PUBLISH`，值写 `false` 就"构建照跑、不部署"，删掉变量（或改成别的值）就恢复发布。**这笔开关不存在＝发布**，所以不建也能正常用。它**不会**让任何现有 URL 变 404，只是内容冻住；要停构建与分钟用 Disable workflow，要摘 URL 用 Settings → Pages → Unpublish。三档分界与读数见 [[状态源与决策记录#D-68 · 发布开关：仓库变量 PUBLISH 只掐部署那一步，站点冻结在最后一次部署\|状态源与决策记录——D-68]]。主库那个旧变量 `PUBLISH_PAGES` 还读着 `false`，对这条链路没有任何作用力。**`2026-10-25T01:31:52Z` 起这道闸是真拉下的**：`POST /repos/takomitkm/WCIS-FPAI-wiki/actions/variables {"name":"PUBLISH","value":"false"}` 回 201，`GET` 读到 `total_count: 1`（`created_at` 与 `updated_at` 同一秒）。她的口径是**不发**，所以"作业全绿而 `deploy` skipped"从故障改成预期。同一时刻 Pages 那侧也不是"Source 调成 None"而是**整站已不存在**（`GET /repos/…` 的 `has_pages: false`、`/pages` 与 `/pages/health` 双双 404、根路径 404），所以将来要恢复发布是**两步**：删 `PUBLISH` ＋ 把来源重新设回 GitHub Actions；只删变量会撞上第六节那行 `Failed to create deployment (status: 404)`。**站点被谁、什么时候下的我没核到**（有 admin 的只有她一个，`anxianji11-pixel` 是 `push=True, admin=False`；API 不记 Pages 删除与可见性变更），这条挂 B |
| 4 vault 入口 | Obsidian「打开文件夹作为仓库」 | 选 `wiki\`（决策 D-59），配置 `.obsidian\app.json`，`attachmentFolderPath: images` |

复核 1、2 两项的只读脚本（用 Windows 凭据管理器里那条 git 凭据做认证 GET，不写任何东西），**第一个参数现在要指文档库**：

```
python -X utf8 S:\apps\llm\agentwork\pagescheck\site_state.py takomitkm/WCIS-FPAI-wiki
```

一条坑仍然成立：**不带 token 的 `GET /repos/{owner}/{repo}/pages` 一律回 404**——别用它判定"Pages 没配"，要么用上面的认证读数（好：`build_type=workflow`），要么直接 curl 站点 URL。

## 三、日常触发：改完笔记推上去就重新出站点

工作流 `Build and publish wiki site` 吃两种触发：

- **push 到本库 `main`**——命中整个库，没有 `paths` 过滤。改一页、改 `site/` 配置、改工作流自己，都会重出站点。
- **Actions 页面里 Run workflow**（`workflow_dispatch`）——内容一个字没改、只想重出一次时用这条。

**主库那边不再有触发**：`wiki/` 在主库只是一个指针，动指针不再建站（那条老工作流已随 D-65 删除）。所以"文档改了但站点没更新"这件事，现在有三种因：本库的 push 没成功、作业红了、或仓库变量 `PUBLISH` 被建成 `false`（第七节末段那两处读数专门用来分这三档）。不会再是忘了 bump 指针。

耗时只有一个变量：插件缓存命中与否。

| 情形 | 读数 | 什么时候会遇到 |
|---|---|---|
| 热（缓存命中） | 本库第二笔实测：整笔 `build` 作业 **3 分 21 秒**（恢复插件 45 s、`Build site` 57 s、存缓存 45 s），`deploy` 11 秒，push 到线上约 **3 分半** | 常态 |
| 冷（缓存空） | 独占 `Build site` 那一步，本库第一笔实测 **18 分 09 秒**（整笔作业 19 分 48 秒，站点本体只占 26 s 处理＋16 s emit，余下全是插件） | 首次、或 `site/quartz.lock.json` 改了 |

本库的第一笔作业就是冷构建（缓存按库分账，主库那份带不过来），`deploy` 作业实测 12 秒，全部读数与归因在 D-65 决定 5。**所以 `watch_ci.py` 的超时对冷构建要给到 25 分钟以上**，给 20 会在 `Build site` 还没跑完时就自己退出。

推送按 [[清单]] 那套走代理，然后看作业：

```
git status
git add <明确路径>            # 别用 git add -A：本库里常有正在写的未跟踪页（2026-10-20 就有 PL/plvid.md），一条 -A 就把别人的半成品带上去
git commit -m "docs: ..."
git -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 push
python -X utf8 S:\apps\llm\agentwork\pagescheck\watch_ci.py $(git rev-parse --short HEAD) 25
```

`watch_ci.py` 第一个参数是必填的短 sha（它按 sha 找那一笔作业），第二个是轮询超时分钟数，不给就 45。**它和 `ci_log.py`、`check_artifact.py`、`site_probe.py` 现在都写死了 `WCIS-FPAI-wiki`**（2026-10-20 随 D-65 一起改指），要回看主库那些旧作业得手动改回 `REPO`。

## 四、内容集：加页、剔页、换范围都在装配器

命令都在文档库根目录跑（`S:\work\WCIS\wiki`）：

```
python -X utf8 site/make-content.py                        # 策展集 -> site/content
python -X utf8 site/make-content.py --audit-only           # 只报数不写盘，改内容集先跑这条
python -X utf8 site/make-content.py --audit-only --strict  # 未解析嵌入或重名页就当失败
python -X utf8 site/make-content.py --all                  # 连原料目录一起发
python -X utf8 site/make-content.py --dest site/content-test   # 写到另一处试，不碰 site/content
```

装配器的四条规矩，改之前必须知道：

1. **内容树＝库根本身**，整个库当同一个 vault，双链照常解析。`SKIP_DIRS` 里除了 `.obsidian`、`.git`、`node_modules` 这类，现在还有 `site`、`qbuild`、`public`——少了这三条，它会把上一次生成的副本当原料再吃一遍（2026-10-20 实测到过一次：主库那版脚本扫已经存在 `wiki/site/content-test/` 的库时，一次报出满屏 `DUP`）。
2. **目标目录必须叫 `content` 或 `content-test`**，且只有里面躺着 `.generated-by-make-content` 哨兵时才允许清空——防止把它指到人写的目录上抹掉别人的东西。
3. **原料默认不进内容集，但按"文件名"挡、不按"目录"挡**（脚本里 `RAW_DIRS`＝厂商转档、抓来的博客、板卡取证提取件，加 `FAQ共建_images`；`RAW_FILES`＝`*.docx.md` 那一件 word 转档），但被已发布页面嵌入的媒体照样复制——否则那几页出来是破图。`check-md.py` 那份同名的 `RAW_DIRS` 只管"要不要按自著页形状校验"，装配器这份管"要不要发"，两棵的用途不同、内容也不同（D-61 解耦）。现值读数在 D-65。**还有一条只在这里说清**：装配器的审计**只覆盖媒体嵌入与重名页，不校验页面链接目标**——所以把某个目录塞进这份 `RAW_DIRS` 之前先确认别处没有策展页链着它里面的页，否则站点上留下的是静默死链，两个校验脚本都不会报（`NPU调用链` 那件被 26 处／13 页链着，就是这条撞上的样子）。
4. **剔一页不发，两条路**：① 写进 `site/quartz.config.yaml` 的 `configuration.ignorePatterns`（现值 `private`、`templates`、`.obsidian`），不用改装配器；② 写进 `site/make-content.py` 的 `NEVER_PUBLISH`（按文件名，**`--all` 也放不进来**），文件根本不复制进内容文件夹。**要连着索引一起摘就走 ②**：`ignorePatterns` 按上游实现是"构建期不处理那些文件"，但它与 `static/contentIndex.json` 的条目之间的实际关系**没测过**，别拿它当"从索引里消失"的依据。走 ② 的实测结果是干净的：`/agent` 与 `/agent.html` 都 404，索引里 `agent` 这个 slug 也没了（D-70 决定 1）。现值 ②＝`agent.md`，因为它带着一行我方内网主机的口令，而站点是全网可读。**这一条现在是要害而不是"暂时不咬人"**：站点走的是"全网可看"这一档，而凭据单点那一页 [[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]] 就在策展集里，2026-10-20 她的口径是**这次先不摘、照发**；要收公开面就把那一页（或整个目录名）加进 `ignorePatterns` 再推一次。

## 五、装配器对生成的副本做两处改写，笔记里不要照着写

| 改写 | 为什么 | 别在笔记里做什么 |
|---|---|---|
| 注入 `created`／`modified`（取该文件在本库 git 里的首末提交日；**日期那一趟 walk 不带 pathspec**，由 `rename_lookup()` 把旧路径折回现名，否则页面一旦被纯移动过，`created` 就刷成移动日——2026-10-18 `archive/` 折进来时实测复现并修好，21 页回到 `2026-09-19`） | 内容文件夹不属任何库，不注入的话每页都显示构建日 | 不用手写这两个键；真写了注入会尊重已有键不覆盖 |
| 把媒体嵌入的目标改成内容根全路径，例如 `![[foo.png]]` 在生成副本里变成 `![[man/fpai-blog/assert/foo.png]]` | Obsidian 按文件名在全库找图，Quartz 只会把链接和**页面自己那层目录**拼，按文件名的最短匹配只对页面生效、对资源不生效——`![[foo.png]]` 在站点里必然取不到图 | **笔记里照旧写最短链接**，别手写全路径；改写只发生在生成副本，本体不动 |

日期只走**这一个库**：`wiki/` 出库时是带全历史切出去的（`git subtree split`，D-63 那 20 笔），所以改造前的每一天都还在本库的 log 里，不需要再回主库合并取数。D-63 那段"两库合并"只在站点住主库时才是必需的，随站点搬进本库一起作废。

所以：图片在 Obsidian 里能看、在站点上却破图，先查装配器有没有改写成功（它打印改了几处），不要去改笔记。

## 六、失败了查这张表

| 现象 | 判读 | 动作 |
|---|---|---|
| `Unknown arguments: from-config` | v5.0.0 的 `npx quartz plugin install` 没有这个参数，网上指南是别的版本写的 | 参数删掉；它按 `quartz.lock.json` 装 |
| `Invalid code point -4` | `remark-obsidian` 0.1.0 把 micromark 的合成 `lineFeed`（−4）喂给 `String.fromCodePoint`，触发形如正文开头的 `#apps` 这类 `#` token | 已由 `parseTags: false` 挡掉。要恢复标签解析必须先升 OFM 到解析已修的版本，别在 0.1.0 上打开 |
| 构建挂在某一页、看不出哪页 | 一页失败会让整批失败，其余页是连坐不是原因 | 看 `Diagnostic - locate the failing page` 那一步：它逐页删掉重构建，**反复出现在 `DIAG attempt N failing pages` 里的那页才是真因**，还会把那页前 900 字符的 `repr` 打出来 |
| `Build site` 挂、报 `Failed to emit from plugin \`CustomOgImages\`: fetch failed`，而 DIAG 是 `no page failed` | **不是内容问题**：OG 图那件插件在构建期要联网取一次东西，CI 那次请求没成，页面全清白 | 直接重跑失败作业（10-18 实测 attempt 2 内容一字未改即全绿） |
| `Restore built plugins` 显示 miss、又是十几分钟 | 缓存 key 含 `hashFiles('site/quartz.lock.json')`，改 lockfile 就换 key | 正常，这一轮会重新保存 |
| 缓存明明存过却没命中 | 失败的作业不跑 `actions/cache` 的 post 步 | 工作流已拆成 `restore` ＋ `save`（`if: always()`），别把它改回单个 `actions/cache@v4` |
| **缓存换库后要重新冷构建** | Actions 缓存按库分账，主库那份命中不到本库 | 一次性代价，别试图跨库共享 |
| `Input required and not supplied: token`（红在 checkout） | 那是**主库旧版**工作流的死法：`secrets.SUBMODULE_TOKEN` 没建时该输入展开成空串，checkout 连访问都不发起就失败 | 本库这版不跨库取内容，默认 `GITHUB_TOKEN` 够用；看到这行说明你还在跑主库那条旧作业 |
| `deploy` 失败：`Failed to create deployment (status: 404)` ＋ `Ensure GitHub Pages has been enabled` | **两种因**：① 套餐不含私有库 Pages（Free 档就是这样，10-18 主库实测）；② Settings → Pages → Source 不是 GitHub Actions | ① 确认学生认证的 Pro 已生效（或把库转公开——公开库 Free 也能发）；② 用 `POST /repos/…/pages {"build_type":"workflow"}` 或去设置里点。两种都不用动工作流 |
| 构建成功、站点却少图 | 盘上本来就没那个文件 | 现存唯一一处是 `PS/psdev.md` 引的 `/1787890661831885.png`，属既有缺图，她的口径是不管 |
| 页面日期显示成构建日 | 该页从没进过 git（新页没提交） | 提交后再构建；装配器只认 `git log` 里的日期。**本地跑装配器时磁盘上的未跟踪文件会被选进内容集并显示 undated**，CI 里不会 |
| 站点上一片 404、路径都对 | 页面路径少了一层或多一层 `wiki/` | D-65 之后站点路径＝库内路径，`README.md` 落根 `index.md`。旧收藏里的 `/WCIS-FPAI/wiki/…` 全部作废 |
| `/robots.txt` 404，或页上读不到 `name="robots"` | 构建没跑到 `Harden output against crawlers` 那一步（那步被删了、或它前面一步失败就没往下走） | 看那一笔作业里这一步在不在、红没红；`harden-site.py` 是硬门禁，它 `exit 1` 会让整笔作业红，**不会**悄悄发一个没加固的站点 |
| `--img-audit` 报 `ERR` 而不是 404 | 不是缺图，是那张太大、脚本 40 秒超时 | 直接 `curl` 那一条 URL 复跑一次；字节数与制品里同名文件一致就是好的 |
| `--img-audit` 说 `artifact … is not a directory` | 页表现在取自构建制品，而那一笔作业的 zip 还没解 | 先 `check_artifact.py <run_id>`，再 `site_probe.py … --img-audit <run_id>` |
| **作业全绿、线上内容却不动**（四页 200、字节数不变，`deploy` 作业显示 skipped） | 十有八九是仓库变量 `PUBLISH` 被建成了 `false`——这道闸的设计就是"跳过部署但不算失败"（D-68）。**10-25 起这是故意状态，不是故障**（见第二节那行），别再按这一行去删变量 | 去 Settings → Actions → Variables 把 `PUBLISH` 删掉或改成别的值，再手动跑一次 `workflow_dispatch`。要判别很快：那一笔作业里 `Upload Pages artifact` 是 `skipped` 而不是 `success` |
| **侧栏文件树是空的、搜索一搜就没结果、关系图不动**，而页面正文与图片全照常 | 客户端 `postscript.js` 硬写域名根路径（`fetch("/static/contentIndex.json")`、`href="/"+slug`），站点挂在 `/WCIS-FPAI-wiki` 子路径下时这些请求全落到域名根、回 GitHub 的 404 HTML，浏览器控制台的表现是 `Error building file trie: SyntaxError: Unexpected token '<'`。**这类故障 HTTP 侧一律看不出来**，只有开浏览器控制台才知道（D-70 决定 3） | 先确认那一笔作业里 `Harden and trim output` 绿、且它打印了 `re-rooted the bundle on /WCIS-FPAI-wiki`；再确认 `site/quartz.config.yaml` 的 `baseUrl` 还写着 `takomitkm.github.io/WCIS-FPAI-wiki`（改 `baseUrl` 就是改这个前缀，装配与改根两处一起跟着走） |
| 红在 `Harden and trim output`、消息里有 `the bundle changed` 或 `the index shape changed` | 上游（Quartz 那笔 tag 或某件插件）改了捆包字面量或 `contentIndex.json` 的形状，而这几处的出现次数是写死的（改根三组 3／1／3、检索字段 1、正文一条都不能少、最大那块样式表必须在每一页逐字一样） | **别把门禁改成警告**。拿新 tag 的产物比一遍锚点，确认语义没变后把 `ROOT_PATCHES`、`SEARCH_PATCHES` 的次数与 `trim_index()` 的判据一起对上；门禁宁可让作业红，也不发一个点不动或带满正文的站 |
| 红在 `Harden and trim output`、消息里有 `refusing to share one stylesheet` 或 `mixed state` | 前者＝各页最大的 `<style>` 不再是同一份字节（Quartz 改成按页出样式了），后者＝产物里一部分页已经换成外链、一部分还是内联。**"已换成外链"自 `16be89d` 起按整条标签判**，页面正文里引用这条路径不再算半改——在此之前，一笔只改了本页第七节那组 curl 的提交就被判成 `1 of 126 pages … mixed state`（作业 `39540461698`，红即不发，旧版照常服务） | 外置这一步**不做将就地合并**：样式按页不同时必须停下来看上游怎么变的。`mixed state` 一般是拿半改的树重跑——换一棵干净的产物副本再跑（判据与六态实测见 [[状态源与决策记录#D-73 · 每页重复的 41.8 万 B 内联样式表抽成一个可缓存外链，顺带补上删爬虫索引时漏掉的 RSS\|状态源与决策记录——D-73]] 决定 2） |
| 站点整站 404，但作业一直绿 | Pages 那侧被 Unpublish 或 Source 改了 —— **下一次成功部署会自己把站点放回来**（官方原文：A successful workflow run in the repository for your site will create a new deployment） | 想让站点保持不在线，光 Unpublish 顶不住下一次 push，要连工作流一起禁用；只想恢复就 `workflow_dispatch` 跑一次 |
| **中转机 `10.101.54.192:18080` 还 200 出整页，而 `takomitkm.github.io/WCIS-FPAI-wiki/` 根路径已经 404** | 那是 102 上 `wcis-relay` 在**吐自己磁盘里那份最后一次部署的副本**，不能当作线上有站点。三条读数一眼定性：响应头 `server: GitHub.com`（它确实回过源）、`x-relay-cache: stale`、`last-modified` 正好等于最后一次成功部署那一秒（10-25 实测 `Thu, 22 Oct 2026 12:38:29 GMT`，与作业 `39779356214` 的完成时刻对得上）。**定性只认两条**：`GET /repos/takomitkm/WCIS-FPAI-wiki` 的 `has_pages`，和 origin 自己的状态码 | 已改（10-25）：`relay.js` 现在回源拿到 **401／403／404／410 就把那条缓存整个丢掉**（`dropCache()` 删 body、删 meta、清索引槽、退字节记账），下一次请求直接透传上游的 404；**5xx 与超时故意不丢**——那说的是链路不是页面，抖动时照吐旧体才是缓存该干的事。A/B 实测（假上游 `max-age=1`，先 200 后翻成 404）：原版第四次仍 `200 stale`，日志两条 `refreshed / -> http 404` 状态一点不动；补丁版第四次 `404 miss`，日志 `dropped / (upstream 404)`。改动在 `192.168.1.102:/home/user/wcis-relay/relay.js`，原版与旧缓存都留着没删（`relay.js.bak-20261025-093610`、`cache-disabled-20261025-093610`，后者 8.9 MB＝Pages 最后那版的完整副本）。重启走 `./relay-stop.sh` ＋ `./relay-start.sh`——这套没有 systemd unit、也没有开机自启，机器重启它就自己没了 |
| `watch_ci.py <短 sha>` 报 `JOB build completed failure`，而步骤名是 `Pull ghcr.io/actions/jekyll-build-pages` ＋ `Upload artifact` skipped | **那一笔不是本站点的工作流**。本库里有两笔作业同时监听 push：我们的 `.github/workflows/deploy.yml`（`Build and publish wiki site`，build 19 步）与 GitHub 自建的 `dynamic/pages/pages-build-deployment`（`pages build and deployment`，她那句"我不想生成 pages 我才这么调成 branch 的"留下的那条），**后者每次 push 都跑且恒红**。`watch_ci.py` 只按 `head_sha` 在 `per_page=10` 里取第一条命中，**抢到哪条算哪条**——10-21 实测同一颗 sha `9bf80d5` 两笔并列：`39579649455` 红（jekyll），`39579649099` build 19/19 ＋ deploy 3/3 全绿 | 验收只认 `path == .github/workflows/deploy.yml` 那一笔：`GET /repos/takomitkm/WCIS-FPAI-wiki/actions/runs?per_page=10` 逐条打印 `id / head_sha / name / conclusion / path` 再挑（10-21 用的就是这段现查，脚本没改）。**红叉本身不用管**，但要在表里写明"jekyll 那一笔不是站点坏了的证据" |
| 连推几笔时，中间那一笔 `deploy.yml` 判 `cancelled`（10-21 实测 `ca731a7`＝39579554002 被取消，前后两笔都绿） | 工作流写着 `concurrency: {group: pages, cancel-in-progress: false}` ⇒ **正在跑的不杀**，但**排队等的那一笔在新 push 到达时被取消**（机制按官方 concurrency 语义说的＝B；现象与三个作业号＝A） | 只看**最后一笔** sha 的作业绿不绿——线上内容＝最后一笔的产物，中间那笔取消不影响站点；要每一笔都上线就别连着推（`workflow_dispatch` 补跑那一笔也行） |

## 七、验收要看哪几个读数

改完 `site/make-content.py` 或内容集，跑 `--audit-only` 看打印；跑完整构建后按 D-58／D-65 的口径核这几项（读数的正本在决策记录，别在这页抄第二份）：

```
python -X utf8 site/make-content.py --audit-only
python -X utf8 S:\apps\llm\agentwork\pagescheck\check_artifact.py <run_id>
python -X utf8 S:\apps\llm\agentwork\pagescheck\site_probe.py "SOP/Quartz搭建到Pages发布SOP" --img-audit <run_id>
```

`site_probe.py` 报这几类读数：首页的 HTTP 码与字节数、首页上的 `<time>`、argv 里每个路径对应页的码／标题／`<time>`／该页前几张本地图的码、`sitemap.xml` 的码与大小（**D-67 之后 404 才是对的**——构建把 sitemap 删了），最后再用 7897 代理取一次首页。加 `--img-audit <run_id>` 会逐页取本地图并计数，**页表现在来自那一笔作业的构建制品，不再来自线上 sitemap**（所以要先跑 `check_artifact.py <run_id>` 把制品解出来，脚本会指着缺目录告诉你这一点）。以前那种"抽样看两页"的口径不算验收——**图片到没到位要用全量**，别抽样下结论。**`ERR` 不是缺图**：那个脚本对每张图只给 40 秒，大图会假阳性；`161206601-012.png`（882,220 B）这类要复跑或直接 `curl` 一次再判（实测三张报 ERR 的复跑全 200、字节数与制品一致）。**argv 里给的路径不带 `.md`、也不带 `wiki/` 前缀**（D-65 之后站点路径＝库内路径），照旧写 `wiki/SOP/…` 只会得到一个 404；URL 又没有尾斜杠，手拼时按制品里那个 `a/b.html` 去掉 `.html` 为准。

线上要命中的四件事：首页 200、页面底部时间不是构建日、本地图的 src 200、**`/robots.txt` 200 且随便一页的 `<head>` 里有那条 `noindex`**。

```
curl -s -o NUL -w "%{http_code}\n" https://takomitkm.github.io/WCIS-FPAI-wiki/
curl -s -o NUL -w "%{http_code}\n" -x http://127.0.0.1:7897 https://takomitkm.github.io/WCIS-FPAI-wiki/
curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/robots.txt | grep -c "^User-agent:"
curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/ | grep -o 'name="robots"[^>]*'
```

境内直连与走 7897 代理都要跑——这条不是当然的，家里网络对被污染的域名会给出假读数。第四条那个标签是**给爬虫看的**，Pages 设不了 HTTP 头（`X-Robots-Tag` 这条路在本托管上不存在），所以别拿"响应头里没有"当没生效的证据。

**再加两件（D-70 之后才有）**：

```
curl -s -o NUL -w "%{http_code} %{size_download}\n" https://takomitkm.github.io/WCIS-FPAI-wiki/static/contentIndex.json
curl -s -o NUL -w "%{http_code}\n" https://takomitkm.github.io/WCIS-FPAI-wiki/agent
curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/postscript.js | grep -c 'index:\["title","content","tags"\]'
```

第一条的字节数是检索口径的读数：**满正文是 2,513,798 B，只留标题是 49,521 B／123 条**（条目键应为 `slug`／`filePath`／`title`／`links`／`tags`，出现 `content` 就是剪正文那步没生效）。第二条应当 404——`agent.md` 已按 D-70 决定 1 剔出内容集。第三条应回 **1**，回 0 就是 D-71 那条检索字段没落上去（`grep` 用 Git Bash 自带的 GNU grep，`findstr` 不认这种方括号写法）。想复核"正文里才有的词搜不到"是不是检索口径的正常后果，而不是索引坏了：从制品里挑一个只出现在某页正文、不出现在任何标题或标签里的词，控制台搜它应回 `No results.`。

**上面这四条 curl 够不着客户端 JS**——侧栏树、搜索、关系图、结果链接、悬浮预览全靠 `postscript.js`，判据只有浏览器控制台。跑法：打开首页，控制台里必须见到 `[Explorer] Trie result: success` 与 `[Explorer] Render complete, final list length: N`，**并且一条 `Failed to load resource: … 404` 都没有**；再在搜索框里打一个标题词（如 `交叉编译主机路由`），结果卡的 `href` 要以 `/WCIS-FPAI-wiki/` 开头、点进去要落对页。**浏览器若拿着旧捆包**（脚本 URL 不带版本号，Pages 的缓存会喂旧文件），先 `fetch(bundleURL, {cache:'reload'})` 再刷新，否则读到的是上一笔的故障。

**再加一组（D-73 之后才有，样式表外置与 RSS 那一漏）**：

```
curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/ | grep -o '/assets/site-[0-9a-f]*\.css'
curl -s -o NUL -w "%{http_code} %{size_download} %{content_type}\n" https://takomitkm.github.io/WCIS-FPAI-wiki$(curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/ | grep -o '/assets/site-[0-9a-f]*\.css' | head -1)
curl -s https://takomitkm.github.io/WCIS-FPAI-wiki/ | grep -c '<style'
curl -s -o NUL -w "%{http_code}\n" https://takomitkm.github.io/WCIS-FPAI-wiki/index.xml
```

第一条取到的是**当下那个文件名**，别抄现值：那 12 位是样式表字节的 sha256 前 12 位，Quartz 一升级、主题一改，名字就跟着换。第二条要 **200／`text/css`**，`size_download` 是压缩后的传输字节（解开来的字节数＝那块样式表的现值，记在 D-73，这里不抄第二份）。第三条现在应回 **3**（原来是 4：最大的那块已换成外链，剩下三块小的仍内联，体积见 D-73）——回 4 就是外置没生效，回 0 或 1 说明连小的也被动了，要停下来查。第四条要 **404**：Quartz v5.0.0 把 RSS 写在站点根的 `index.xml`，不在 D-67 那份名单里，所以 10-21 之前它一直在线、里面是最近十篇页面的 URL。**判"这一页外置了没有"要认整条标签**（`<link href="…assets/site-….css" … data-persist="true"/>`），别只 `grep '/assets/site-'`——上面这几条命令本身就是正文里的字面量，命中它证明不了什么。

要在这四条里加体积判据，就在本地对构建制品量 gzip，别抄线上现值——Pages 的 gzip 级别与本地 `-9` 略有差，同一页两个数对不上是正常的。

**改过 `harden-site.py` 想在推之前验一遍产物**：拿那一笔作业的制品解出来的目录做**一次性副本**跑同一条命令即可——

```
python -X utf8 S:\apps\llm\agentwork\pagescheck\check_artifact.py <run_id>
cp -r <解出来的 public 目录> <临时副本>
python -X utf8 site/harden-site.py <临时副本>
```

跑完看它打印的 `trimmed … from … to … bytes`、`re-rooted the bundle on /WCIS-FPAI-wiki`、`made the search query take title+tags` 与 `moved the shared stylesheet (417916 bytes, 124 pages) out of every page's head`。两条注意：① **必须在副本上跑**——剪正文那一关是单程的（正文已剪掉的文件再跑一次会被 `the index shape changed` 判成形状变了而 `exit 1`），而改根、检索字段与样式表外置那三关是幂等的（10-21 拿线上捆包实测：反改回改前形态跑一遍、与直接对改后形态跑一遍，产物逐字节相同；对同一产物连跑两遍字节不变。样式表那关的幂等是 10-21 另测的四态之一：对已外置的树再跑一次报 `already externalised` 且每一页字节不变）；② 剪 JSON 不用验语法，**改捆包字符串一定要过一遍解析**——本机没有 node，用 Deno：`deno eval "await import('file:///<副本>/postscript.js')"`，**能过解析就报运行时 `ReferenceError: document is not defined`，改坏了解析就报语法错**（10-21 我就是用这条抓到 `href="/"+` 被我替换成 `href("/"+` 的漏等号，那一版没进 git 也没上线）。

**"这一笔到底部署了没有"看两处**：作业里 `Upload Pages artifact` 那一步是 `success` 还是 `skipped`、`deploy` 作业是 `success` 还是 `skipped`；线上则看那四页的 **ETag 前缀**——每次成功部署会把所有文件的 Last-Modified 一起刷新，前缀随之整体变化，而字节数不动就说明"没有新部署落上去、也不是内容变了"。10-20 那三笔现跑对照：`6ad733df` →（部署）`6ad740be` →（关闸那笔，四页前缀不变、字节数一字未动）→（恢复部署）`6ad746c7`。

## 八、关掉与回退

| 想撤到哪一步 | 怎么做 |
|---|---|
| 停"内容更新"，构建照跑、URL 全在 | Settings → Actions → Variables → 建 `PUBLISH` ＝ `false`（或 `POST /repos/takomitkm/WCIS-FPAI-wiki/actions/variables {"name":"PUBLISH","value":"false"}`）。效果是 `Upload Pages artifact` 与 `deploy` 一起 skipped、整笔仍 `success`、**线上一个链接都不会变 404**。恢复＝删掉变量再跑一次（`DELETE /actions/variables/PUBLISH` ＋ `workflow_dispatch`），10-20 双向都实测过（D-68） |
| 停构建、连 Actions 分钟一起省 | Settings → Actions → `Build and publish wiki site` → Disable workflow。站点冻在最后那版；代价是 `workflow_dispatch` 同时失效，恢复要先 Enable |
| 站点整个不要了（现有链接变 404） | Settings → Pages → Unpublish（或 `DELETE /repos/takomitkm/WCIS-FPAI-wiki/pages`）。**注意这只顶到下一次成功部署为止**——工作流没停的话，改一页推上去站点自己回来；要真按住得同时 Disable workflow 或把 `PUBLISH` 关成 `false` |
| 站点这套代码撤干净 | 本库 revert D-65 那笔（`site/` 三件＋工作流＋`.gitignore` 一次带的），主库那边把 `site/` 与 `.github/workflows/deploy.yml` 从历史里取回即可——它们在主库历史中完整存在，不需要重写 |
| 站点搬回主库 | 就是恢复 D-63 那套：主库工作流加 `submodules: wiki` 与 `token: secrets.SUBMODULE_TOKEN`，代价是**每次发布要手动 bump 指针、还要一个能读两库的 PAT** |
| 只把防爬这一步撤掉 | 本库 revert `668bf3a`（`site/robots.txt`＋`site/harden-site.py`＋工作流那一步一起消失）。下一次构建 `sitemap.xml` 自己回来、`noindex` 标签消失，内容与链路都不用动。要留 robots.txt 只不注入标签 ⇒ 删 `harden-site.py` 里注入那一段；要留 sitemap 又不给爬虫读 ⇒ 在 `robots.txt` 里写 `Disallow: /sitemap.xml` 并让脚本别删它 |
| 只退 D-70 那三样（正文剪掉／客户端改根／`agent.md` 剔除） | 三样各自独立，就在 `site/harden-site.py` 的 `main()` 里去掉对应那一行、或从 `site/make-content.py` 的 `NEVER_PUBLISH` 里删那个文件名，各自单独可退；整包退 ⇒ revert `b031a2b` ＋ `6d29c29`。**退 `agent.md` 这一项的代价要先讲清**：`/agent` 会重新带出那行内网口令（D-70 决定 1 就是为它加的） |
| 只退 D-71 那一样（检索字段里加 `tags`） | 从 `site/harden-site.py` 的 `patch_bundle()` 那个循环里去掉 `SEARCH_PATCHES`（或删掉那一条元组）即可，索引数据与页面都不动，侧栏和搜索回到只按标题命中。**今天退与不退没有可观测差别**：全库 123 条索引的 `tags` 都是空的（D-71 先纠正的那个前提） |
| 只退 D-73 那两样（样式表外置／RSS `index.xml` 也删掉） | 外置：去掉 `main()` 里 `shared_style()` 那一行，每页重新内联那块 `<style>`，`assets/` 那个文件就不再生成——**页面 URL 一个都不变**，只是首页又涨回 47 万 B。`index.xml`：从 `CRAWLER_INDEXES` 里删掉 `"index.xml"` 这个名字，RSS 重新上线（内容集与正文都没动，摘的只是那份十篇 URL 的清单）。两样各自独立，整包退 ⇒ revert `d9c9a8d` ＋ `5fe9d36` |

## 相关页面

- [[状态源与决策记录]]——D-58 是方案与图片那条的判据正本，D-63 是出库，D-65 是这次搬迁，D-67 是防爬这一层，D-68 是发布开关那一步，D-70 是内容集剔除、标题检索与客户端改根，D-71 是检索字段加进标签，D-73 是每页重复的样式表外置与 RSS 那一漏
- [[pages建设过程]]——这条链按时间顺序的建设过程（哪一步为什么这么改、当时撞见了什么）；这页是操作规程，那页是过程
- [[板卡镜像实测取证#敏感信息|板卡镜像实测取证——敏感信息]]——公开面唯一那处凭据
- [[清单]]——找什么东西去哪
- [[验证与交付#5. 交付包内容清单|验证与交付——5. 交付包内容清单]]——对外分发包的内容口径
