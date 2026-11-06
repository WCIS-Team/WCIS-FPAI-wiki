# sdi2hdmi

## 定位

FMQL30TAI 上的纯 PL SDI → HDMI 转换工程，位于 `repos/sdi2hdmi/`。

## 数据路径与入口

README 描述的路径为 SDI 接收、色彩转换、缩放、行缓存跨时钟处理、720p60 光栅和 TMDS HDMI 输出。

- `rtl/`：RTL 模块。
- `constrs/`：引脚及时序约束。
- `sim/`：仿真材料。
- `build.tcl`、`compile.ps1`：构建入口。

目录另含构建日志与输出文件；查阅时应区分源码、仿真结果与生成产物。

## 相关页面

[[SDI转HDMI转换器]] · [[repo项目索引]]
