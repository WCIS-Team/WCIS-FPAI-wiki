---
tags: [SOP]
updated: 2026-11-07
---

# WCIS递归许可证扫描SOP

## 用途与范围

在最外层 [WCIS-FPAI](https://github.com/WCIS-Team/WCIS-FPAI) 运行一个手动 CI，递归检出子模块后统一生成许可证、版权和软件包清单。工作流正本为主库 `.github/workflows/scancode.yml`，名称为 `ScanCode recursive report`。

扫描的是所选主库提交及其逐层记录的子模块提交，不追踪所有仓库的最新分支；没有 `push`、PR 或定时触发。子仓库已有的工作流不会因递归检出而被启动。

扫描包括检出树中的文件与 Git LFS 对象，只排除 Git 元数据。没有进入远端版本控制的本机文件、依赖安装后才产生的内容、构建产物与压缩包内部未展开内容，不属于完整覆盖承诺。ScanCode 的软件包识别也不等于所有运行时依赖已被解析。

## 手动执行

1. 先将工作流提交并推送至主库默认分支 `main`；仅本地新增文件不会让 GitHub 出现运行按钮。遵守主库推送规范，不夹带共享工作区其他会话的改动。
2. 打开主库 **Actions → ScanCode recursive report → Run workflow**，选择要检查的分支并执行。所选分支须包含工作流。
3. 等待 `scan` 作业结束。作业在 GitHub 托管的 Ubuntu 24.04 上安装固定版本 ScanCode Toolkit 32.5.0，使用 Python 3.12；本机无需安装 ScanCode。
4. 在运行详情查看摘要，并下载 `wcis-scancode-<运行ID>-<重跑序号>` 制品，解压后打开 `scancode.html`。

工作流总时限 180 分钟，检出最多 30 分钟、工具安装最多 20 分钟、扫描步骤最多 110 分钟，为摘要与上传预留时间；扫描使用两个进程，单文件扫描器超时为 120 秒。制品保留 30 天，需要长期留证时在到期前下载。

## 报告内容与通过判据

| 制品内文件 | 用途 |
|---|---|
| `scancode.html` | 供人阅读的统一扫描结果 |
| `scancode.json` | 完整结构化扫描结果，保留许可证匹配文本 |
| `root-commit.txt`、`submodules.txt` | 实际主库提交与所有递归子模块提交 |
| `context.txt` | 仓库、分支引用、运行链接、工具版本与扫描范围 |
| `scancode-version.txt`、`python-packages.txt` | 工具版本与本次实际 Python 依赖版本 |
| `install.log`、`scancode.log`、`scan-exit-code.txt` | 安装日志、扫描日志与原始退出码 |
| `summary.md` | 与 Actions 页面一致的摘要 |

检查作业成功、JSON 与 HTML 均已生成、所有子模块状态行均没有 `-`／`+`／`U` 前缀，并确认 JSON 的文件级 `scan_errors` 与报告头 `headers[].errors` 为空。摘要同时展示检出、提交校验、Python 设置、安装和扫描步骤的状态，并链接完整运行日志。发现许可证属于正常清单结果；本工作流没有设置许可证允许／禁止名单，作业成功不代表已完成法律审查。

扫描步骤失败时仍会尝试上传已有结果与诊断，原始非零退出码会使作业失败。检出、安装失败或运行被取消／总超时，可能只能取得部分诊断，不能把它当完整报告。

## 故障处理

- 子模块无法拉取：检查主库记录的提交是否已推到对应远端。子模块若是私有仓库，默认 `GITHUB_TOKEN` 无法跨库读取，需要具备全部相关仓库只读权限的凭证后再调整检出配置。
- LFS 下载失败：检查对象是否已上传、远端访问和配额。不得把仅含指针的文件当成实际大文件已扫描。
- 单文件超时或扫描错误：先在 JSON 中定位 `scan_errors`，结合日志判断是否需要调整单文件时限后重新手动执行。
- 没有运行按钮：确认工作流已进入主库默认分支，且仓库 Actions 与该工作流处于启用状态。

## 实施与验证边界

2026-11-07 按用户“最外层 WCIS 放一个 CI，手动触发，递归检出，统一出报告”的指令新增配置。实施阶段只进行本地结构、脚本语法与摘要逻辑校验；GitHub 上的递归检出、Linux 安装和整树扫描须以首次手动运行记录为准。此页不宣称工作流已经推送或运行成功。

参考：[ScanCode Toolkit](https://github.com/aboutcode-org/scancode-toolkit)、[checkout 子模块配置](https://github.com/actions/checkout#usage)。
