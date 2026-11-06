---
tags: [index]
---

# FPAI30TAI图像FPGA索引

> 本页是 `repos/FPAI30TAI图像FPGA/` 的指路索引，2026-11-03 整理，只读、不修改仓库。
> **本页与同目录 `llms.txt` 是同一份东西（llms = 本索引）**，内容必须保持一致。
> 仓库自身**没有** `llms.txt`；自带入口是 `README.md` 与 `docs/api-index.md`（接口速查）。
> Obsidian 的 vault 根是 `wiki/`，`repos/` 在 vault 之外，所以本页把仓库内相对路径列出来；
> 要打开原文件，按路径去 `S:\work\WCIS\repos\FPAI30TAI图像FPGA\` 下取。

## 仓库自带的入口

- `README.md` — 主入口（约 33KB）：阶段记录、数据流、构建与验证入口。
- `docs/api-index.md` — 接口速查：HTTP 路由（8091/8092/8093）＋ PL/PS 接口，是仓库里最接近索引的一页。
- `docs/interface.md` — PL/硬件接口：AXI 寄存器、跨时钟握手、valid/ready、尺寸与超时。
- `docs/release-runbook.md` — 发布与回退统一入口。
- `docs/release-source-map.md` — 发布文件对应表。

## 组件设计解读

按组件的设计与实现解读在同目录 `组件设计/`（只讲怎么做与特色设计，不记踩坑），入口 [[组件总览与阅读地图]]；llms.txt 里的「组件设计解读」节与之一一对应：

- [[平台与数据流]] — SoC/内存/启动链/SDI 采集链/整体数据流
- [[视觉前端RTL]] — 整帧选择、VTC 重写、补边、SDI 被动诊断、预览 CSR、CDC 标准件
- [[人脸与防伪预处理RTL]] — 仿射采样、五点对齐、FAC1 CustomOp、PAD 预处理、读写提交
- [[JPEG与MJPEG核]] — mjpegzero 编码流水、JPEG CustomOp、SDI→JPEG 流、PL JPEG 预览
- [[PL网口核]] — UDP 打包发送、RGMII、MDIO、verilog_ethernet 复用、时钟与 CDC
- [[eMMC与存储]] — eMMC 经 EMIO 接 PS SDIO1、分区挂载、人员库布局
- [[单所有者摄像头与H264直播]] — 单 owner、帧租约、请求合并、H.264 硬编与 HLS
- [[模型推理与防伪]] — 模型加载调用、运行时桥接、对齐、同帧绑定、Gallery
- [[录像与页面]] — 分段/配额/回收站、remux MP4、8093 页面与回放
- [[构建打包与部署]] — Vivado+JFM、OOC、Procise BOOT、发布基线与 systemd 前置

## Vivado 工程

- `case/fpai_demo_vivado.xpr` — 完整案例工程，顶层 `ai7030_edif_top`。
- `case/constrs_1/impl_constraints.xdc`、`case/constrs_1/ai7030.xdc` — 约束。
- `case/ip_patch/` — JFM 补丁工具链（`top.tcl`、`run.tcl`、`tools/bitfile_replace.tcl` 等）。
- `case/PS_AI IP/` — PS7 IP 源。
- `scripts/prepare_case.tcl` — 准备工程副本。
- `scripts/synth_blocks.tcl`、`scripts/elaborate_case.tcl` — 独立模块综合与整案 RTL 展开。
- `scripts/repair_mig_ooc.tcl` — MIG OOC 修复。
- `scripts/build_case.tcl`、`scripts/package_boot.tcl` — 整案构建与 BOOT 打包。
- `outputs/` — 综合/实现/位流/BOOT 产物（非源码）。

## JPEG 与 MJPEG 核

- `rtl/vendor/mjpegzero/` — 厂商 MJPEG 编码器：`rtl/mjpegzero_enc_top.v`、`huffman_encoder.v`、`quantizer.v`、`dct_1d.v`、`dct_2d.v`、`rgb_to_ycbcr.v`、`zigzag_reorder.v`、`jfif_writer.v`、`bitstream_packer.v`、`input_buffer.v`、`bram_sdp.v`、`axi4_lite_regs.v`；另有 `sources.json`、`README.md`、`LICENSE`。
- `rtl/wcis_jpeg_compressor.v` — PL JPEG 压缩原型：RGB 流接口、帧号、输出缓冲、溢出/中断恢复。
- `rtl/wcis_jpeg_customop.v` — JPEG CustomOp 接入。
- `rtl/wcis_sdi_jpeg_stream.v` — SDI→JPEG 流。
- `rtl/wcis_pl_jpeg_preview.v` — PL JPEG 预览。
- `rtl/wcis_recording_customop.v` — 录像 CustomOp。
- `rtl/wcis_jpeg_network.v`、`rtl/wcis_jpeg_udp_packetizer.v`、`rtl/wcis_jpeg_network_tx.v`、`rtl/wcis_udp_payload_pipe.v` — JPEG over PL 网络。
- 仿真：`sim/tb_jpeg_compressor.sv`、`tb_jpeg_customop.sv`、`tb_jpeg_network.sv`、`tb_jpeg_network_tx.sv`、`tb_jpeg_udp_packetizer.sv`、`tb_sdi_jpeg_stream.sv`。
- 脚本：`scripts/build_jpeg_board.tcl`、`synth_jpeg_compressor.tcl`、`benchmark_jpeg_core.py`、`verify_jpeg_compressor.py`、`verify_jpeg_customop.py`、`verify_pl_jpeg_transport.py`、`verify_pl_jpeg_tx.py`、`verify_pl_jpeg_network.py`。
- 记录：`docs/pl-jpeg-compressor-20261016.md`、`pl-jpeg-board-20261016.md`、`pl-jpeg-board-acceptance-20261017.md`、`pl-jpeg-ethernet-1080p-20261023.md`、`pl-jpeg-ethernet-validation-20261024.md`、`pl-jpeg-tx-integration-20261025.md`、`pl-jpeg-bram-chunk-20261025.md`。

## PL 网口核

- `rtl/vendor/verilog_ethernet/` — verilog_ethernet：`rtl/eth_mac_1g_rgmii.v`、`rgmii_phy_if.v`、`udp_complete.v`、`ip_complete.v`、`arp.v`、`axis_gmii_rx.v`、`axis_gmii_tx.v`、`axis/rtl/axis_async_fifo.v` 等。
- `rtl/wcis_rgmii_tx_serdes.v`、`rtl/wcis_mdio_clause22.v` — RGMII 收发与 MDIO。
- `rtl/wcis_jpeg_network.v`、`wcis_jpeg_udp_packetizer.v`、`wcis_jpeg_network_tx.v`、`wcis_udp_payload_pipe.v` — UDP 打包与发送。
- `constraints/fmql30tai_pl_ethernet.xdc`、`constraints/fmql30tai_pl_ethernet_tx.xdc` — 引脚/时序约束。
- `npu_photo/src/pl_net_config.cpp` — PL 网口配置。
- `scripts/build_pl_net_config_school.py`、`scripts/assert_pl_udp_payload_cut.tcl`。
- 记录：`docs/pl-ethernet-reference-review-20261024.md`、`pl-ethernet-shared-clock-validation-20261024.md`、`pl-jpeg-ethernet-1080p-20261023.md`、`pl-jpeg-ethernet-validation-20261024.md`、`ps-ethernet-negotiation-20261024.md`、`yt8521-tx-delay-candidate-20261024.md`、`sdi-pl-network-check-20261020.md`。

## eMMC 到 PS 的 SDIO1

- `patches/emmc-sdio1-20261015.patch` — 在 PS7 BD 中添加 `SDIO_1_0` 接口（EMIO）。
- `patches/emmc-interface-budget-20261015.xdc` — eMMC SDR25 接口预算约束（`emmc_sdr25`，20ns max / 5ns setup-hold）。
- `docs/emmc-source-manifest.json` — eMMC 源清单。
- `docs/face-emmc-store-20261015.md` — eMMC 上板记录（`/dev/mmcblk1`，UUID `67104a06-74a6-4268-a124-269d1b232a28`，挂 `/mnt/wcis-emmc`）。
- `scripts/mount_face_store.py` — 挂载人员库。
- 说明：这是接在 PL 引脚上的 eMMC，经 EMIO 连接 PS 原生 MMC 控制器，文件系统由 Linux 管理；没有 PL 自主读取文件或 PL 内向量比对。

## 直播网页服务

- `lan_stream/vpu_live_server.py` — 8092 H.264/MJPEG 预览服务（只读共享内存）。
- `lan_stream/server.py` — MJPEG/HTTP 服务。
- `lan_stream/h264_player.js`、`h264_media.py`、`h264_fragments.py`、`h264_packager.py` — H.264 播放/分片/打包。
- `lan_stream/dist/index.html`、`lan_stream/dist/jpeg-preview.html` — 前端页面。
- `lan_stream/VPU_LIVE.md`、`lan_stream/README.md`、`lan_stream/PROTOCOL.md` — 说明。
- `npu_photo/serve_photos.py` — 8091 照片/人脸/摄像头服务（也提供 H.264 直播路由）。
- `npu_photo/camera_panel.html`、`camera_panel.js`、`camera_requests.py`、`camera_interlock.py`、`camera_owner_runtime.py` — 页面与摄像头 owner 接入。
- `npu_photo/recording_service.py`、`recording_library.py`、`recording_panel.html`、`recording_panel.js`、`recording_compression.py` — 8093 录像与页面。
- `release/540p-r2/site-template.html`、`scripts/assemble_camera_site.py` — 正式首页模板与装配。
- 记录：`docs/h264-ffmpeg-20261030.md`、`docs/preview-low-latency-sop.md`、`docs/preview-maintenance-deploy-20261031.md`、`docs/recording-storage-20261027.md`、`docs/recording-management-20261027.md`、`docs/face-recording-20261026.md`。

## 多个模型部署

- `model_backend/` — `face_geometry.py`、`face_pad.py`、`face_pad_inference.py`、`enrollment_compare.py`、`face_history/`、`README.md`。
- `npu_photo/model_backend_runtime.py`、`native_forward.py`、`owner_pad.py`、`pl_preprocess.py` — 模型运行时/桥接。
- `npu_photo/recognize_photo.py`、`recognize_frame.py`、`run_photos.py`、`serve_photos.py` — 识别入口。
- `ps_app/src/`、`ps_app/vendor/include/` — C++ 板端应用与 icraft/NPU actor。
- 记录：`docs/face-pl-modelbackend-20261015.md`、`face-redeploy-20261015.md`、`face-multi4-20261018.md`、`face-pad-minifas-20261018.md`、`face-pad-owner-20261026.md`、`npu-clock-*.md`。

## 其它 RTL

- `rtl/wcis_face_preprocess.v`、`wcis_face_customop.v`、`wcis_affine_sampler.v`、`wcis_pad_preprocess.v` — 人脸/防伪预处理与 CustomOp。
- `rtl/wcis_frame_rate_gate.v`、`wcis_stream_letterbox.v`、`wcis_vtc.v` — 选帧、补边、VTC。
- `rtl/wcis_sdi_monitor.v`、`wcis_pixel_read_axi.v`、`wcis_native_write_commit.v`、`wcis_status_sync.v`、`wcis_cdc_mailbox.v`、`wcis_preview_csr_router.v`、`wcis_preview_registers.v`。

## 其它目录

- `sim/` — 仿真 testbench；`tests/` — 服务/接口回归；`scripts/` — 构建、部署、验证脚本（186 个）。
- `docs/` — 118 篇按日期记录；`outputs/` — 产物；`release/` — 发布基线；`photo_reference/` — 照片参考路径。

## 维护约定

**本页与同目录 `llms.txt` 是同一份索引（llms = 本索引），内容必须一致。** 以后仓库或本目录有更新（新增/删除 RTL、Vivado 工程、JPEG/MJPEG 核、PL 网口核、eMMC 接口、直播网页服务、模型部署、脚本或文档），**索引要一起更新**：先改一处，再同步另一处，不要只改一边。

## 相关页面

[[板端直播链路与硬件仲裁]] · [[VPU串流直播SOP]] · [[板端FunASR链路操作与可调参数]] · [[repo项目索引]]
