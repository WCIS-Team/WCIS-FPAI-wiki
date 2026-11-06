---
tags: [index]
---

# yuanma索引

> 本页是 `repos/yuanma/` 的指路索引，2026-11-04 整理，只读、不修改仓库。
> `yuanma` 是**竞赛提交快照包**（2026-11-03 冻结，4481 文件 / 约 3.1 GB，`filelist.json` 逐文件带 SHA-256），在 repos 库中当前未跟踪（本机目录）。它回答的问题是：**"交给举办方的东西是什么、别人怎么从零复现"**——设计原理不在这里，在 [[FPAI30TAI图像FPGA索引]] 与 `组件设计/` 系列。
> Obsidian 的 vault 根是 `wiki/`，`repos/` 在 vault 之外；要打开原文件按路径去 `S:\work\WCIS\repos\yuanma\` 下取。仓库自带入口是 `README.md`（复现步骤）与 `submission/README.md`（同文）、`submission/filelist.md`（分类索引）。

## 顶层布局

| 路径 | 内容 |
|---|---|
| `README.md` | 复现主线：BOOT → PS 程序 → 上板运行 → 重新生成，四节 |
| `board-run.tar.gz`（64 MB） | 板端一键运行包＝`board/`＋`reference_release/`＋`filelist.json` 的 tar，板上 `tar -xzf` 即用 |
| `submission/` | 全部提交内容（源码、证据、基线、模型、恢复脚本），4481 文件 |

## submission/ 七个分区

| 分区 | 文件数 | 内容 |
|---|---|---|
| `source/` | 1659 | **Vivado 源码工程快照**：`source/fpga_project/` 即 FPAI30TAI图像FPGA 的完整副本（`case/`、`rtl/`、`constraints/`、`npu_photo/`、`ps_app/`、`model_backend/`、`lan_stream/`、`patches/`、`sim/`、`tests/`、`scripts/`、`docs/` 124 篇）。可编辑入口 `case/fpai_demo_vivado.xpr`（顶层 `ai7030_edif_top`，代理器件 `xc7z030ffg676-2`） |
| `evidence/` | 2703 | 原始证据：`stages/`（2453 件，12 个历史阶段的日志/报告，如 `sdi-refclk-fix-20261020`、`pl-jpeg-board-20261016`、`face-cache-resume-20261020`、`pl-command-validation-20261022`）、`workspace/`（构建与 Procise 打包原始日志）、`restore-check/`（本次重开 Vivado 的 104,649 网全布通/0 错误报告）、`reproduction/`（BOOT 重打包逐字节比对 `boot-compare.json`/`portable-boot-compare.json`、RTL 综合/仿真摘要） |
| `implemented_baseline/` | 27 | **冻结的 10-20 实现**：`refclk-final.dcp`（已布线 checkpoint）及父 checkpoint、`boot-candidate/BOOT.bin`（SHA-256 前缀 `f6da96ab`）、原时序报告 `timing.rpt`（setup +0.005 ns / hold +0.004 ns / 周期 −0.409 ns，未完整签核）、`build-and-board-manifest.json`（25 件逐件 SHA-256） |
| `reference_release/` | 67 | 板端运行配套：`boot/`（`BOOT.bin`+`Image`+`fmqlmp-verify.dtb`+`uEnv.txt`）、`app/`（识别程序+网页+三个原生二进制 `wcis_camera_owner`/`wcis_face_cached`/`wcis_face_pl_retained`）、`identity/`+`pad/`（模型 JSON/RAW 与 `wcis_face_pad`/`wcis_face_npu`）、`recorder/`（录像服务八件） |
| `board/` | 7 | 新板安装器：`render_install.py` 按 `board.example.json` 渲染安装树（服务单元+数据目录）、`boot_prepare.py`、`mount_face_store.py`、iCraft 3.39.0 三个 `.deb` |
| `restore/` | 10 | 重新生成脚本：`rebuild_bit.tcl`（从冻结 DCP 直接 write_bitstream，复现 10-20 DRC 策略）、`rebuild_boot.ps1/.tcl`（Procise 打包）、`rebuild_rtl.tcl`（RTL 重综合+布线）、`open_source_project.tcl`/`open_implemented.tcl`（两个只读打开入口）、`compare_boot.py` |
| `model_inputs/` | 6 | 已改写 ONNX：YuNet、MobileFaceNet、MiniFASNetV2/V1SE（`-conv-slope` 为改写版），是模型编译的输入对照 |

## 清单与校验

- `filelist.json`（1.8 MB）：4481 件逐条 `path/category/stage/bytes/sha256`；头部 `checks` 记录两工程已实际打开、重打包 BOOT 逐字节一致、RTL 综合 7 组仿真通过等 10 项复现核验。
- `filelist.txt`（相对路径纯列表）、`filelist.md`（按材料分类的表）。
- 16 个 category：`original_report_or_log` 1931、`source_project` 1601、`build_script` 757、`model_or_release_reference` 67、其余为基线/证据/恢复辅助。

## 复现边界（README 与清单自己声明的）

- 重打包 BOOT 与提交版**逐字节一致**（冻结 DCP → bit → Procise 打包全程可复现）；RTL 重综合可跑通（7 组仿真过），但**未**重新布局布线上板（`rtl_new_route_verified: false`）。
- 原始时序门未完成完整签核（周期 −0.409 ns 的 NPU 告警沿用）；当前 RTL 重新实现不承诺得到同一 bit/BOOT。
- 板端第三节（安装/启动/识别）在新装板离线验证过安装树渲染，运行结果以目标板验收为准（`board_runtime_verified: false`）。

## 相关页面

[[FPAI30TAI图像FPGA索引]] · [[组件总览与阅读地图]] · [[repo项目索引]]
