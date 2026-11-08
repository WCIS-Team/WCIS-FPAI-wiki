---
tags: [SOP]
updated: 2026-11-02
---

# 文档库与GitHub同步SOP

> **这是"wiki 库本地攒了一大堆、要把它推上 GitHub 且一个文件都不能少"的照抄规程。**
>
> 一页管一条链路：**体检 → 清障 → FF → 改名 → 逐 blob 核对 → 具名挡凭据 → 分组提交 → 推自己的子库 → 远端复验**。
>
> 一句话：**先数清楚三类差异（D／M／??），再让本地跟上远端，然后把要入库的东西分组成几笔能各自回退的提交——每笔的"没少"都要有 blob 级读数，不靠嘴说。**
>
> 裁定正本在 [[状态源与决策记录|D-1793459164]]（全库 `.md` 一律跟踪、`repo对应WCIS.wiki.repo/`→`repo2WCIS.repos/`、`PL/FPGA/4compile/` 不跟踪、嵌套 clone 删自带 `.git` 保内容）。三库推送与共享工作树的**权限口径**正本在主库 `AGENTS.md` §七，本页只补"怎么做到零丢失"的动作序列。

---

## 一、什么时候跑这一页

任一成立就开跑：

- `git -C wiki status` 里 `??` 上百件，或 `git ls-files --others` 体积 > 10 MiB；
- 本地 `ahead/behind` 有一边非零（分支头分叉，改名／大提交前必须先收）；
- 要做**目录改名**且必须保住 `git log --follow` 的历史；
- 库里出现了**嵌套 clone**（父库把它当 gitlink，`160000` 模式）；
- 同一片工作树里有**另一条会话的未提交改动**，而你这次只推一部分。

## 二、开工前的三条硬门禁

| 门禁 | 怎么查 | 不满足就 |
|---|---|---|
| **只动 wiki 库** | `git -C S:/work/WCIS/wiki rev-parse --show-toplevel` | 主库根五处（`AGENTS.md` 等）默认不动，要她当次明说 |
| **不 bump 主库指针** | `git -C S:/work/WCIS status -s`（应看到 ` M wiki` 挂着但**不 commit**） | 见 §八 |
| **体积闸** | 单笔里最大的文件 `ls -l` | 单文件 > 100 MiB 会被 GitHub 直接拒整笔 push；本仓已知的最大件是 `PL/FPGA/FPGArt/BIT` 一颗 60.4 MiB 级 `.rtd`，所以改名/入库前先量一遍 |

## 三、第 0 步：体检（三类差异 + 三个数）

**用 python 起 git，别在 bash 里拼中文路径**——本机 argv 编码会把 CJK 参数弄成 `fatal: pathspec '...\u5bf9...' did not match any file`。

```
python -X utf8 -c "
import subprocess,collections
W=r'S:/work/WCIS/wiki'
g=lambda *a: subprocess.run(['git']+list(a),capture_output=True,cwd=W).stdout
it=[x.decode('utf-8','replace') for x in g('status','--porcelain','-z').split(b'\0') if x]
print('classes',collections.Counter(x[:2] for x in it))
print('ahead/behind',g('rev-list','--left-right','--count','origin/main...HEAD').decode().strip())
print('HEAD',g('rev-parse','HEAD').decode()[:12])
"
```

读数要落进文档的三个数：**类计数（D／M／??）**、**ahead/behind**、**未跟踪总体积**。体积这样取（含逐目录占比，用来判"大头是不是该跟踪"）：

```
python -X utf8 -c "
import subprocess,collections,os
W=r'S:/work/WCIS/wiki'
u=[x.decode('utf-8','replace') for x in subprocess.run(
   ['git','ls-files','--others','--exclude-standard','-z'],capture_output=True,cwd=W).stdout.split(b'\0') if x]
tot=sum(os.path.getsize(os.path.join(W,p)) for p in u if os.path.isfile(os.path.join(W,p)))
print(len(u),'files |',tot,'B =',round(tot/2**20,3),'MiB | 按顶层目录',
      collections.Counter(p.split('/')[0] for p in u).most_common())
"
```

**这两个键别混**：`ls-files --others` 输出的是**相对仓库根的路径**（所以顶层目录取 `split('/')[0]`）；`status --porcelain` 输出的是 `XY 路径`（要先 `x[3:]` 去掉状态位）。`git ls-tree` 里 CJK 路径**即使加了 `-z` 也会被八进制转义引起来**，取值一律配 `-c core.quotePath=false`。

本轮收工时这一段的实读＝**1 files｜13,797 B｜`[('SOP', 1)]`**（只剩这一页 SOP 没入库）；起点是 **865 件／73,576,684 B＝70.17 MiB**（其中 `PL/FPGA/4compile/` 1,648 件／438.6 MiB 占 86.2 %，被裁定不跟踪）。

**判"要不要跟踪"只问两句**：① 它是我方产物、还是可重下的构建缓存？② 它有没有出厂正本已经在库里（如 `4compile/` 的位流在 `FPGArt/BIT` 与 `BOOT_Gen` 都有）？构建缓存不跟踪，但**要在 `.gitignore` 里具名挡 + 注释写清体积与正本位置**，别让它悄悄消失。

## 四、第 1 步：清障 + FF（改名之前先把头对齐）

**FF 前置 ＝ 0 ahead 且没有挡路改动。** 有挡路件时按这个顺序：

1. **整份存底**：把挡路件复制到 `workenv/tmp/<本轮>/`，记录原大小与 md5；
2. `git checkout HEAD -- <具名路径>` 把工作树退回 HEAD（**不 stash**——共享工作树里 stash 会连对方的一起卷走）；
3. `git merge --ff-only origin/<分支>`（wiki＝`main`，repos＝`master`，主库＝`main`）；
4. **FF 后逐 blob 复验**：对第 1 步存过底的每一件，比 `git ls-tree -r -z HEAD` 里的 sha 与存底副本算出的 sha，一致才继续。

远端拿不到就是网络：`Recv failure: Connection was reset` 是**直连被重置**，一律带代理取，见 §七。

### 4.1 分叉（本地既 ahead 又 behind）时的替代路线：no-checkout 临时 worktree

上面 1–4 步的前提是**能 `--ff-only`**。本地头既 ahead 又 behind 时（实测 2026-11-02：`repos` 的 `rev-list --left-right --count origin/master...HEAD` ＝ `10 2`，本地攒着 10 个没推的提交），FF 必失败、合并又违反 §八「不替另一条会话提交」⇒ **不在共享工作树里动手**，改在 `workenv/tmp/<名>` 起一个**不检出**的临时 worktree，只把要入库的具名文件放进去，从 `origin/<分支>` 起一笔新提交：

```bash
WT=workenv/tmp/<名>
git -C <库> worktree add --detach --no-checkout "$WT" origin/<分支>   # 不物化整棵树
git -C "$WT" read-tree HEAD                                          # 索引必须填满，否则提交会把整棵树删光
mkdir -p "$WT/<目录>" && cp <共享树里的具名文件> "$WT/<目录>/"         # 只放目标文件
git -C "$WT" add -- <具名路径>
git -C "$WT" diff --cached --stat                                    # 只该看到目标件
git -C "$WT" diff --cached --diff-filter=D --name-only | wc -l        # 必须是 0
git -C "$WT" commit -F -                                             # 父提交＝origin/<分支>
git -C "$WT" -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 \
    push origin HEAD:<分支>
git -C <库> worktree remove --force "$WT"                            # --force 必需，见 §十二
```

五条要点：

- **`--no-checkout` 是为了不付检出成本**：本轮 `repos` 的 `origin/master` 是 **1017.6 MB／9016 件**、`wiki` 是 **265.0 MB／1845 件**；`read-tree` 填索引是毫秒级，整棵检出是分钟级＋1 GB 磁盘。
- **`read-tree` 那一步不能省**：`--no-checkout` 留下的索引是空的，直接 `add`＋`commit` 会得到一棵**只含目标文件**的树，等于把其余 9000 多件全删掉。
- **推前两道读数**：`--cached --stat` 只出现目标件、`--diff-filter=D` 计数为 0；再对每件比 `git -C "$WT" cat-file blob <sha> | md5sum` 与共享树里那份的 md5，必须逐字节相等（`wiki` 的 `*.md text eol=lf` 与 `repos` 的 `* -text` 都不改写字节）。
- **子模块不掺和**：`repos` 是含子模块的超级项目（§11.4 说多检出官方不推荐），但 no-checkout 树里**根本没有子模块目录**，`add` 只碰具名路径 ⇒ 这条支路不触发那个坑。
- **本地分支头一个字节不动**：本轮结果 `repos` `f55803f..aa2c60a`（8 件 ＋1021）、`wiki` `3bd1f41..6710fc9`（1 件 ＋2），两个库本地头仍停在 `875dcc8`／`3bd1f41`（各落后远端 1）。⇒ **§八 的验收在这条支路下要改写**：核的是"远端 sha ＝ 临时 worktree 的 `HEAD`"，不是"＝ 本地 HEAD"。

## 五、第 2 步：目录改名，历史不断

改名用**内容不动、路径动**的方式（`git mv` 或 `git add` 新 + `git rm` 旧），让 git 自己识别 rename。验收只看一个数——**提交前先 `--cached`，提交后按区间复算**：

```
git -C S:/work/WCIS/wiki -c core.quotePath=false diff --cached -M -l 0 --find-renames=50% --name-status
git -C S:/work/WCIS/wiki -c core.quotePath=false diff --name-status -M -l 0 --find-renames=50% <旧ish> <新ish>
```

`-l 0` 是不限配对数（默认上限 1000，超限**不报错**、直接把改名拆成 A＋D，见 §11.2）。本轮的实读（第二条命令跑出来的）：

| 区间 | 内容 | 改名识别 |
|---|---|---|
| `3396538^ → 3396538` | `repo对应WCIS.wiki.repo/`→`repo2WCIS.repos/` | **15 对全 `R100`**（＋6 件 `M`） |
| `8529e04^ → 8529e04` | 另一条会话的整理波 | **97 对（96 `R100` ＋ 1 `R099`）**，`A` 163、`D` 5、`M` 1 |
| `a926a83^ → 40784cf`（全程） | 四笔合计 | `A` 752＝589（modrt）＋163，`R` 97，`D` 5，`M` 16＝`.gitignore`＋15 页正文 |

- **`R100`＝逐字节相同**（最干净），`R099`＝差 1 行（一般是顺手改了 H1 或链接），两者都算历史接上。
- 相似度掉到 `R0xx` 很低（<90%）时**别宣称历史保住**：`git log --follow` 只跟"相似度够高的成对增删"，`--follow` 只能一次跟一个路径、跨多次改名会断。
- 改名要**同时改工具链里的目录名**，否则校验器/装配器继续按旧名找。本仓的键位：`format/check-md.py` 的 `RAW_DIRS`（豁免校验的目录名，按**任意层级**目录名匹配）与 `APPENDIX_DIRS`（按顶层目录）、`site/make-content.py` 的 `RAW_DIRS`（决定是否发布）。

**边界要钉死（本轮踩过）**：`RAW_DIRS` 只管**校验与发布**，跟"**跟不跟踪**"无关。别用它当"不入库"的理由——一个目录可以同时"入库但不进站点"。

改名后必查**旧名残留**：

```
rg -l '<旧目录名>' S:/work/WCIS/wiki --glob '*.md'
```

残留逐处读一遍再判：出现在**历史记账/决策正文**里的旧名是对的（那一笔描述的是当时的路径），出现在**活双链**里才是真漏。

## 六、第 3 步：嵌套 clone 入库（先问"它记的是谁的历史"）

目录里有 `.git` ⇒ 父库把它当 **gitlink（模式 `160000`）**，里面的文件一个都不进库。三步：

1. **先判这个 `.git` 记的是谁的历史**：`git -C <内嵌目录> log --oneline -3` ＋ `git remote -v`。是**厂商/别人的上游历史**、且你只要当前版本作参考 ⇒ 删 `.git`，内容退化成普通文件；是**你自己的承重历史** ⇒ 别删，改用真子模块或 `git subtree`。
2. 删 `.git` 后内容才成为可跟踪文件（**这一步不可逆，先按 §九 进回收站**）。
3. **来源要记一份**：URL／分支／commit／体积／"逐字节核对结论"写进 `README.md`。判据：外部来源是**索引到别处的链接**，链接允许重复记录，不受"一个事实只写一处"约束（这条口径她 2026-10-31 定）。

入库前**逐 blob 核对新树是不是旧树的超集**（脚本见 §十配方 3）。

## 七、第 4 步：凭据闸——具名挡，不改别人的内容

**提交前对每个 staged blob 复扫**，不是扫工作树文件（工作树里有历史版本、扫它没意义）。

**别用"裸前缀子串"当判据**——它会把"讲这些前缀的文档自己"判成凭据（本轮就是：这一页 §七 写出来以后自己被自己的闸拦下 7 类命中）。正解是**前缀＋长度**的正则：

```
python -X utf8 -c '
import subprocess,re
W=r"S:/work/WCIS/wiki"
def g(*a): return subprocess.run(["git"]+list(a),capture_output=True,cwd=W).stdout
RX={"gh-pat":rb"github_[p]at_[A-Za-z0-9]{20,}","gh-classic":rb"[g]hp_[A-Za-z0-9]{30,}",
    "gh-oauth":rb"[g]ho_[A-Za-z0-9]{30,}","privkey":rb"BEGIN [A-Z ]*PRIVATE KEY-----",
    "aws":rb"[A]KIA[0-9A-Z]{16}","openai":rb"[s]k-[A-Za-z0-9]{20,}","hf":rb"[h]f_[A-Za-z0-9]{30,}",
    "gitlab":rb"[g]lpat-[A-Za-z0-9]{20,}","basic-url":rb"[a-z]+://[^/@ ]{1,40}:[^/@ ]{1,60}@"}
st=[x.decode() for x in g("diff","--cached","--name-only","-z").split(b"\0") if x]
bad=[(p,[k for k,n in RX.items() if re.search(n,g("show",":"+p))]) for p in st]
print("staged",len(st),"| hits",[x for x in bad if x[1]])
'
```

（前缀里那个 `[p]`／`[g]` 方括号是防自匹配的写法，匹配的还是同一个字符；这段代码本身进库也不会被自己拦下。）

**闸必须带正对照**，否则它只是一枚橡皮章：拿库里那件**已知带现役 token 的未跟踪文件**跑同一套正则，必须命中；再拿本轮的正文页跑，必须 0。本轮实读＝被挡件 **`gh-pat` 命中 1**（值不外显）、这一页 **0 命中**。

命中时的处置**只有一条**：用 `.gitignore` **具名**排除那一件（`/agentpreview/AGENTS.md` 这种写法），注释写清"为什么挡、要入库得先做什么"，**不许为了推上去改别人的内容**。同目录其余文件照常入库。

**闸本身会咬自己**（本轮实测过一次 ABORT）：`.gitignore` 的注释里写了那颗 fine-grained token 的**前缀字面量**，于是 `.gitignore` 自己作为一个 staged blob 被拦下（`staged blobs with PAT/key: 1 ['.gitignore']`）。处置＝注释改成自然语言"GitHub Personal Access Token"，复跑归零——**改的是我自己刚写的那行，不是别人的内容**。

## 八、第 5 步：分组提交（禁 `git add -A`）与推送

**分类原则**：一笔只管一件能独立回退的事。本轮分成三笔＋一笔并入他人改动：

| 笔 | 内容 | 规模 |
|---|---|---|
| `3396538` | 目录改名（15 对 `R100`）＋ 工具链换名 ＋ 决策入册 ＋ `.gitignore` 具名挡 `4compile/` | 21 文件 +221 −16 |
| `a926a83` | 两棵厂商 clone 去 `.git` 后内容入库 | 589 件／67.66 MiB（13 件缓存 49,732 B 被规则挡） |
| `8529e04` | 另一条会话的整理波（旧目录→新目录 97 对改名 + 163 新增 + 5 裸删 + `.gitignore`） | 266 文件 +37,987 −710 |
| `40784cf` | **另一条会话的 15 页正文改动**，本轮只负责推上去 | +419 −79 |

**具名 stage**，永远不用 `git add -A`（共享工作树下会把对方的半截改动一起带走）：

```
git -C S:/work/WCIS/wiki add -- <具名路径…>
```

误 stage 了就摘出来，**不要 reset**：`git restore --staged -- <那几个具名路径>`。

**推送**：内容只进它自己的子库，分支名各库不同（wiki＝`main`）。

```
git -C S:/work/WCIS/wiki -c http.proxy=http://127.0.0.1:7897 -c https.proxy=http://127.0.0.1:7897 \
    -c credential.helper= -c credential.helper=manager push origin main
```

- 代理只给 push／ls-remote 用；**查元数据不带代理**（`api.github.com` 走代理反被 403）。
- 报 `403 Write access not granted` ⇒ 是 `~/.git-credentials` 里那颗 PAT 挡路，加那两条 `credential.helper` 覆写。
- **推前先 `ls-remote` 核远端头**，推后**逐字复验远端 sha ＝ 本地 HEAD**（本轮 `40784cf9055c…` 两边一致）。⚠ 走 §4.1 的临时 worktree 支路时本地头**故意不挪**，这条要改成"远端 sha ＝ 临时 worktree 的 `HEAD`"。
- **push 被拒（non-fast-forward）就是被拒**：不 stash、不替另一条会话提交、不 `reset` 本地分支头——本地分支头常年落后于远端是故意的，挪头会让共享工作树里凭空多出几百个"已删除/已修改"。

**主库指针**：`git add wiki` 是**另一个动作**，默认不做，要她当次明说（理由与历史见 `AGENTS.md` §七）。

## 九、删除一律进回收站

本 SOP 里所有"删"（删 `.git`、删试错副本、删临时产物）都走 send2trash，**不真删**；删后枚举回收站按 `DeletedFrom` 分组验收。配方在 `windows-recycle-bin-api`（用户级记忆），不在本页重复。

## 十、验收：五个零 + 三个可复现配方

跑完这一页，下面五个必须为**零**，且每个都要有读数来源：

1. **未跟踪为零**：`git status --porcelain -z` 里 `??` 计数 ＝ 0（被 `.gitignore` 具名挡的不算）。
2. **分叉为零**：`rev-list --left-right --count origin/main...HEAD` ＝ `0	0`。
3. **丢失为零（blob 超集核对）**：把**旧树每一条 blob 的 sha**拿去新树里找，找不到的**逐件交代**。配方（本轮实跑件在 `workenv/tmp/wikisync/superset_check.py`——**workenv 不入库**，照下面三步重建）：

   ```
   python -X utf8 workenv/tmp/wikisync/superset_check.py "a926a83^" "HEAD"
   ```

   核心三步：`git -c core.quotePath=false ls-tree -r -z --format=%(objectname) %(path) <ish>` 建 `{sha: [路径…]}` 两张表 ⇒ 旧表里 `sha not in 新表` 的就是候选丢失 ⇒ 空文件的 blob 是 `e69de29b…`，**任何空文件都能"假配对"**，必须单独数出来（本轮旧树 1097 条里有 4 条 0 B）。

   本轮实读：旧树 **1097** 条 blob 项 → 新树 **1844** 条，**内容找不到的 22 条**，22 条全部有交代＝**15**（这一轮并入的正文改动）＋**1**（`.gitignore` 本轮改过）＋**4**（她裁定删掉的试错脚本 `fetch_aishell_test2.sh`／`fetch_sample2.sh`／`fetch_seg_dict2.sh`／`fetch_seg_dict_hf.sh`）＋**1**（`man/PS-PL_AXI_HP_…` 改了 H1 故改名不成）＋**1**（`实时伪tts.md` 旧内容是新版的前缀，见下面"改动没丢"）。**对不上号的剩余数＝0。**

   **三个坑**：① CJK 路径必须 `-z` **且** `-c core.quotePath=false`，否则拿到的是 `"...\\347\\256\\227..."` 八进制串，跟工作树路径配不上；② `git show HEAD:<CJK>` 在本机 argv 编码下**静默返回空**，看起来像"零命中"，要取内容用 `ls-tree` 拿 sha ＋ `cat-file blob`；③ `-z` 与 `--name-status` 一起用时记录边界是 `R100\0旧\0新\0`，**不能按行 split tab**。
4. **凭据为零**：§七 的 staged blob 扫描命中 0。
5. **校验问题零新增**：`python -X utf8 wiki/format/check-md.py` 的 problem 数与本轮之前**同数**（本轮 305 problems／197 groups 前后一致）。

另配一条**"改动没丢"**的核对（她问过两次的那条）：对每个"保留版 vs 上游版"的冲突文件，算**最长公共前缀**；若旧行整体是新行的前缀（本轮实测 826 字符全等）⇒ 保留版是**严格超集** ⇒ 零丢失。这不是"两边都读一遍觉得差不多"，是可复算的判据。

## 十一、外部做法对照（他山之石）

本轮做之前/之后查了官方手册与中立工程文，逐条与本页对齐。**能本机复算的都复算过**，其余标来源。

### 11.1 "零丢失"要从一层升到三层

| 层 | 命令 | 判的是 | 本机实读 |
|---|---|---|---|
| 提交级（最强） | `git rev-list --left-right --cherry-pick --right-only --no-merges <旧>..<新>` | 有没有**整笔提交**的改动没上去；手册原文 "Omit any commit that introduces the same change as another commit on the other side"（[git-rev-list](https://git-scm.com/docs/git-rev-list)） | 四笔全在（`>` 侧 3 条＋起点） |
| 改名审计 | `git diff -M100% --name-status --summary` | 只认**逐字节相同**的配对（[git-diff](https://git-scm.com/docs/git-diff)） | 波三 `-M`＝96 `R100`＋1 `R099`；`-M100%` 同一区间变 **A 164／D 6**（那 1 对降级）⇒ 报"历史接上"时**必须写清用的哪个阈值** |
| 树级集合差 | `git ls-tree -r`（默认输出 `mode type sha \t path`）两边排序做差 | 新树 ⊇ 旧树（[git-ls-tree](https://git-scm.com/docs/git-ls-tree)） | §十配方 3，22 条全交代 |

再加两条**备份自洽**判据（本页没做，下次补）：`git bundle create … --all` ＋ `git bundle verify`（前提提交齐不齐，[git-bundle](https://git-scm.com/docs/git-bundle)）；`git fsck --full`——注意 `--connectivity-only` **检不出 blob 内部损坏**（[git-fsck](https://git-scm.com/docs/git-fsck)）。

**并且：`git log --follow` 不能当目录级历史的证据。** 手册原文它 "works only for a single file"，且默认的历史简化会剪掉 merge 侧；非线性历史的 follow 到 2.56 才改进（[git-log](https://git-scm.com/docs/git-log)、[2.56 relnotes](https://gitlab.com/git-scm/git/-/blob/HEAD/Documentation/RelNotes/2.56.0.adoc)）。要证明"整目录搬迁保住了历史"，用上面的集合差，不是 `--follow`。

### 11.2 改名阈值要写死，否则会静默降级

`-M` 默认阈值 **50 %**，配对穷举上限是 `diff.renameLimit`（默认 1000），**超限 git 不报错、直接把改名拆成 A＋D**（[git-diff](https://git-scm.com/docs/git-diff)）。几百件规模的整理波正好在踩线范围。⇒ 命令里固定带 **`-M --find-renames=100% -l 0`**（`-l 0`＝不限，本机已验可接受）。

### 11.3 吸收外部 clone：先问"要不要上游历史"，再选路

| 要不要上游历史 | 正解 | 代价 |
|---|---|---|
| 完全不要（本轮 modrt 两棵厂商 clone） | `git rm --cached` ＋ 删内层 `.git` ＋ 重新 add（摊平） | **不可逆**：上游 commit 全丢，只剩当前快照 ⇒ 必须配 §六 的来源记录 |
| 要、且要能再更新 | `git subtree add --prefix <目录> <URL> <ref>`；不 `--squash` 则上游全历史入本仓，`--squash` 时 commit message 仍留 `git-subtree-dir:`／`git-subtree-split:` 溯源 trailer；man 页另建议"subtree 改动与主项目改动分开提交"（[git-subtree](https://manpages.debian.org/bookworm/git-man/git-subtree.1.en.html)） | 仓库变大 |
| 要重写路径（整树搬进子目录） | `git-filter-repo --to-subdirectory-filter <dir>`（`filter-branch` 已被它取代；手册警告改写后新旧历史不再兼容） | 改写历史，需全员重新 clone |
| 保持独立仓 | 真 submodule | 主库只记 gitlink，`git add -A` 有误 bump 风险 |

**溯源比"README 里写一句"更完整的做法是 manifest 文件**：记 `upstream URL ＋ rev ＋ 本地打了哪些 patch`，OpenTitan 的 `util/vendor.py` / `.vendor.hjson` 就是这种（[opentitan.org](https://opentitan.org/book/util/doc/vendor.html)），同类工具 `git-vendor` 在 subtree 之上做 add/list/update 记账。**本轮只做了 README 一句话记录 ⇒ 这是本页已知的最大欠账。**

### 11.4 `git commit -- <paths>` 与 `git add` 的官方语义差（很容易踩）

`git commit -- <路径>` 提交的是**工作树**内容，**忽略索引里已 staged 的改动**，且列出的路径**必须已被跟踪**；其余 staged 改动"not lost — they are still staged and merely held back"；未跟踪的新页面要么先 `git add <具名>`，要么用 `--include`（[git-commit](https://git-scm.com/docs/git-commit)）。⇒ 本页 §八 用"具名 `git add` ＋不带路径的 commit"是有意的：**新页面走 add，摘出去用 `git restore --staged`，两者别混在一条命令里。**

**并行 agent 的社区共识是物理隔离工作副本**（每人一个 worktree、验证门后再提交），具名 add 只适合短时共存（[Claude Code best practices](https://code.claude.com/docs/en/best-practices)、[parallel AI agents](https://parallelcode.app/blog/parallel-ai-agents/)）。worktree 有四个必须知道的共享项：**除 `refs/bisect`、`refs/worktree`、`refs/rewritten` 外所有 `refs/` 共享**（⇒ `stash` 跨树可见）、同一分支默认不能双检出、`remove` 只清干净树、`gc` 与 hooks 影响全部 worktree；**超级项目（含子模块）的多检出官方不推荐**（[git-worktree](https://git-scm.com/docs/git-worktree)）。⇒ 本仓是三库嵌套，`workenv/tmp/<名>` 那种 detach worktree 只能当**临时装配台**，不能当常驻工作副本。

### 11.5 凭据：`.gitignore` 不是唯一挡口，且它管不到已入库的

- **`gitignore` 只对未跟踪文件生效**；"不入库又不污染共享 `.gitignore`"的正解是本地私有的 **`.git/info/exclude`**（优先级高于 `core.excludesFile`）。另一个坑：**父目录被排除时 `!` 无法反选子文件**（[gitignore](https://git-scm.com/docs/gitignore)）。⇒ 本轮 `agentpreview/AGENTS.md` 那种"我这个人要入库、这个 agent 不要"的判断，按官方口径**更该写 `.git/info/exclude`**；写进 `.gitignore` 的理由是**要让另一个协作者也看得见这条挡口**——这条选择要显式记着，别下次当成疏漏。
- **已提交过的密钥**：官方要求从**所有**含它的提交里删除（最新一笔 `git commit --amend --all`，更早的要改写历史），并强调**撤销／轮换优先于清理**（[push protection on the CLI](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/work-with-leak-prevention/push-protection-on-the-command-line)）。
- 分层扫描（本轮只做了手工 staged 扫，未做这三层）：本地 gitleaks pre-commit ＋ CI trufflehog（`--only-verified --fail`）＋ 平台 push protection；误报用 `.gitleaks.toml` allowlist（commits/paths/regexes/regexTarget/stopwords）与 `.gitleaksignore` 指纹记账（[gitleaks](https://github.com/gitleaks/gitleaks)、[pre-commit.com](http://pre-commit.com/)、[参考综述](https://www.digitalapplied.com/blog/secrets-management-api-key-rotation-2026-engineering-reference)）。

### 11.6 行尾与体积

- `.gitattributes` **优先于** `core.autocrlf`；改过 `text`/`eol`/filter 之后必须 `git add --renormalize .` 并以**单独一笔 renormalize 提交**落地，否则幻影 diff 与跨分支冲突是必然（[gitattributes](https://git-scm.com/docs/gitattributes)，`--renormalize` 本机 dry-run RC＝0 已验）。⇒ 本仓现在是 `core.autocrlf=input` **与** `.gitattributes` **并存**，这就是 numstat 出现"插删相等"抖动的来源；了断办法就是那一笔专笔 renormalize。
- 体积硬数字（官方，本轮二次核）：**>50 MiB 警告、>100 MiB 拒推、网页上传 25 MiB**（[about-large-files-on-github](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)）。LFS 只是"能处理更大文件"，该页**未给**具体上限；按套餐是 2/4/5 GiB 单文件、Free 含 10 GiB 存储＋带宽（[LFS 计费](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)）。⇒ **对 Markdown vault，LFS 不是万能**：Free 配额会先被附件耗尽，且 Quartz 官方也不主张把构建产物入库。

### 11.7 Obsidian / Quartz 侧

Obsidian 官方承认 Git 是有效的版本控制与备份方式（[help.obsidian.md/backup](https://help.obsidian.md/backup)）；实务忽略清单＝`workspace.json`／`workspace-mobile.json`／`cache`／`.trash`／**`plugins/*/data.json`（可能含 API Key）**（[21obsidian](https://21obsidian.com/blog/obsidian-git-sync)；另有一份跨机摘要只取到 abstract，正文 404 ⇒ **未核**）。Quartz 官方口径＝**框架与内容分离**，`npx quartz upgrade`/`sync` 会先把 content 目录 stash 再恢复，框架改动与内容应分开提交（[quartz.jzhao.xyz/upgrading](https://quartz.jzhao.xyz/upgrading)）——这与本页 §八"一笔只管一件能独立回退的事"是同一条原则。

### 11.8 与本页现口径的分歧（不改，但记下来）

1. **"分支头常年故意落后"**（`AGENTS.md` §七）与 `--ff-only` 语义相冲：`git pull --ff-only` 在分叉时按文档必然失败，官方也更推荐 fetch＋merge 两步（[git-pull](https://git-scm.com/docs/git-pull)）。本页保留她的口径（共享工作树下挪头有真风险），但**把风险写成硬门禁**：任何"看起来是清理"的动作（`git add -A`、`git checkout -- .`、`git stash`）在本地落后远端时**一律禁止**。
2. **不跟踪 ≠ 不入库校验**：`RAW_DIRS` 决定校验与发布，跟跟踪无关（§五 的边界），社区没有这条区分，别在文档里混着说。
3. 本页 §十的"最长公共前缀"判据**是我自己造的**，外部没有成文做法 ⇒ 保持"可复算"的定位，别写成通用规程。

## 十二、本轮实测到的坑（都留下了读数）

| 现象 | 真因 | 怎么办 |
|---|---|---|
| `os.walk` 解包 `for _,_,fs in ...` 后 `TypeError` | `_` 最终绑定的是 dirs（list），不是文件 | 写全 `for root, _dirs, fs` |
| `Counter(x for _,x in A)` 报 `too many values to unpack` | `A` 是字符串列表不是元组列表 | 直接 `Counter(A)` |
| `git show HEAD:<CJK>` 返回 `None`，脚本继续跑并给出"零命中"假结论 | Windows argv 编码 | 换 `ls-tree -r -z` ＋ `cat-file blob` |
| 直连 `git ls-remote` `Recv failure: Connection was reset` | `github.com:443` 被重置 | 带 7897 代理重试 |
| 自己的凭据闸 ABORT，命中件＝`.gitignore` | 闸的注释里写了 token 字面量 | 注释改自然语言，复跑归零 |
| `git ls-tree -r -z` 拿到的 CJK 路径是 `"\347\256\227..."` 八进制串，跟工作树配不上 | `-z` **不关掉** `core.quotePath` 的转义 | 一律 `git -c core.quotePath=false ls-tree …` |
| `-z` 配 `--name-status` 按行 split tab 解析出垃圾 | 记录边界是 `R100\0旧\0新\0`，一条状态跨三个 NUL 段 | 要 tab 解析就别加 `-z`，改加 `core.quotePath=false` |
| 体积统计 `IndexError: list out of range` | `os.path.join(W,p).split(os.sep)[1]`：`W` 用正斜杠、`os.sep` 是反斜杠，切不开 | 路径相对仓库根，直接 `p.split('/')[0]` |
| 一次性 `python -c "…"` 里的反引号被 bash 做了命令替换 | 外层用了**双引号**，串内 `` `x` `` 照样展开——本轮 needle 被替换成空串（`b' / '`），还顺手执行了一条不存在的命令 | `python -c` 的包裹引号**一律用单引号**，串内需要单引号时写 `"'"'`；needle 用正则字符类 `[p]` 而不是反引号 |
| `git add -A -- <顶层目录>` 把另一条会话 8 个正文改动一起 stage | `-A` 无视"只推一部分"的意图 | `git restore --staged -- <那 8 个具名路径>` |
| bash 里 `\uXXXX` 传中文路径 → `pathspec did not match` | 转义没被还原 | 中文路径一律在 python 里写真串 |
| `git worktree remove` 报 `Permission denied` 但已注销 | 目录空了才允许 remove，remove 与删目录两回事 | 确认 0 文件后 `rmdir` |
| 说"117 个 D 里 115 件是本次改名"，实测只有 15 件 | 把另一条会话的整理波当成自己的改名波 | **数字必须现算现引**，见 `num-audit` |
| `--no-checkout` 的 worktree 里直接 `add`＋`commit`，提交里 9000 多件全变 D | 索引是空的，`commit` 取的是索引而不是 HEAD | 先 `read-tree HEAD` 填满索引，再 `add -- <具名>`（§4.1） |
| `git worktree remove` 拒删（"contains modified or untracked files"） | no-checkout 树里没有文件、索引却有 9016 条，必然判 dirty | 用 `git worktree remove --force`；它只删这个临时目录，不碰共享树 |
| `git rev-parse --short HEAD origin/master` 报 `fatal: Needed a single revision` | `--short` 只接受一个 revision | 分开两次调，或去掉 `--short` |
| 受限 shell 在 `repos`／`wiki` 下建不了文件：`git worktree add` 报 `could not create leading directories of '.git/worktrees/…'` | 不是 git 的错——这两个目录的 Windows 文件权限只给到别的会话/工具 | 让本会话开**完全权限**后原样重跑；**不要去改系统文件权限**（她 2026-11-02 明说） |

## 相关页面

[[状态源与决策记录]] · [[交付物数字审计num-audit]] · [[Quartz搭建到Pages发布SOP]] · [[板端磁盘清理SOP]] · [[交付件就绪状态盘点SOP]]
