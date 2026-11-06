---
tags: [SOP]
updated: 2026-11-04
---

# 原生HMI深浅主题切换SOP

本页复现原生 kiosk 与四个功能页的深浅配色。代码位于 `repos/HA4FPAI/web/offlineHMI/`，字体与颜色由共享 `Theme` 管理；主机预演不依赖网络或实物显示器。

## 启动与切换

在代码目录运行，输出指定到主库 `workenv/`。使用已有带 Pillow、numpy 的 Python，不安装新依赖：

```powershell
python -B -X utf8 kiosk.py --theme light --backend png:S:/work/WCIS/workenv/hdmi-kiosk/light --mouse 'mock:[]' --mock --frames 1 --no-single-instance
python -B -X utf8 kiosk.py --theme dark --backend png:S:/work/WCIS/workenv/hdmi-kiosk/dark --mouse 'mock:[]' --mock --frames 1 --no-single-instance
```

`app_preview.py`、`app_recording.py`、`app_photos.py`、`app_voice.py` 同样接受 `--theme dark|light`；省略参数为原深色。用鼠标操作时可点顶部“浅色模式／深色模式”切换，标签表示目标模式；当前页状态、回首页和随后打开的页面沿用同一主题。仅在本进程保留，重启按启动参数恢复。

真机显示/输入验证就绪后，启动命令可使用 `--backend udmabuf --mouse evdev --host 127.0.0.1 --theme light`。若使用门卫单元，把参数加在 `--then-exec` 内的 kiosk 命令。本 SOP 未部署或修改任何板端单元，也未验证真实 HDMI/鼠标。

## 检查与通过判据

```powershell
python -B -X utf8 S:/work/WCIS/workenv/hdmi-kiosk/test_themes.py
```

脚本要求退出码 0、六项测试无失败：深浅往返/独立实例、四页共用主题及状态保留、鼠标实际点击与首页导航、媒体像素不变、五入口默认深色/显式浅色及非法参数、Python 3.8 语法。所有输入均为 mock，测试禁止外部请求。

图片与 `result.json` 位于 `workenv/hdmi-kiosk/theme-validation/`。检查首页、语音文本区、录像选中行和按钮在浅色时可读；照片与视频本身的颜色保持不变。2026-11-04 本机六项通过，实物显示和长时运行另行验收。主题不改变在线语音的网络依赖。

## 相关页面

[[webapp#两种前端的边界|webapp——两种前端的边界]] 说明原生 kiosk 与网页试验台的边界。
