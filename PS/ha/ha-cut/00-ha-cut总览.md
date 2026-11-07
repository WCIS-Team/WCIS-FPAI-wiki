---
tags: [SOP]
updated: 2026-11-08
---

# 00-ha-cut总览

ha-small 分支（从 Home Assistant Core 2026.10.4 删除式裁剪）的工作页面索引。**每页一个步骤**，按序号阅读；正本清单在仓库内 `ha-cut.md`（ha-small 分支根）。

## 页面索引

| 页 | 内容 | 状态 |
|---|---|---|
| [[01-来源与基线]] | 官方 sdist 下载、SHA256 核对、为什么从官方源而不是 archive 复制 | ✅ |
| [[02-依赖闭包与三轮试删教训]] | 三条裁剪规则（manifest 硬依赖/跨行导入/bootstrap 预导入）与 128→118 的收敛过程 | ✅ |
| [[03-功能验收与回归]] | 30 项功能套件、mTLS/弱网/转接设备/摄像头/只读接入的证据链 | ✅ |
| [[04-打包与交付]] | 源码包/wheel/deb 三产物、校验和方法、安装方式 | ✅ |
| [[05-录像控制与磁盘守护]] | 只读接入板端 recorder、10GB 守护阈值、短录验证结果 | ✅ |
| [[06-ARM64与qemu验证]] | binfmt 注册、原生轮子构建、check_config 与完整启动 | ✅ |
| [[07-运行时内存RSS实测]] | HA 主进程 253.3 MB + ffmpeg 60 MB；裁剪为何不省 RSS 的机制说明 | ✅ |

## 与仓库的关系

- **分支**：`WCIS-Team/HA4FPAI` 的 `ha-small`（orphan，与 master 无共同历史）
- **正本清单**：分支根的 `ha-cut.md`（52+ 已勾项，直接在 GitHub 可见）
- **本地暂存**：`S:/work/WCIS/repos/ha-small`（被 `repos/.gitignore` 忽略）
- **一次性脚本**：`S:/work/WCIS/workenv/ha-small/`（不入库）

## 边界

- HA 上游基线 **2026.10.4**，Python **≥3.14.2**——板端 Python 3.8 装不了，HA 跑本机、板端只出流
- 本目录页面只记录**做了什么+怎么验的**；功能正确性的逐项判据在 `ha-cut.md`，不复制表格
