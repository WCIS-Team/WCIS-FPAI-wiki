# vpu-live

## 定位

板侧 VPU 直播链路源码和证据目录，位置为 `repos/vpu-live/`。

## 目录入口

- `src/`：采集与 VPU 编码程序。
- `bin/`：板端可执行文件。
- `evidence/`、`logs/`：阶段记录和验证结果。
- `payload/`：部署载荷。
- `README.md`、`MANIFEST.md5`：工程说明和文件清单。

README 记载了独立 H.264/JPEG 探针，以及接入 SDI 取图后的 HLS 打包路径。2026-10-20 所述逐段解码验证使用 PL 的 VTC 测试图；相机输入并未在该次记录中验证。检查运行时结论时应回到对应阶段证据。

## 相关页面

[[repo项目索引]]
