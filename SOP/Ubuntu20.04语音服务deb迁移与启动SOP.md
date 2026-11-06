---
tags: [SOP]
updated: 2026-11-04
---

# Ubuntu20.04语音服务deb迁移与启动SOP

## 范围与前提

本轮按用户“板子上旧的清理了，把新的放上去，并且启动”执行，目标192.168.1.113。现场为Ubuntu20.04.4/aarch64、Python3.8.10；安装GitHub正式Release的lang-server 0.1.1。不能在113编译，不构造、加载或执行本地模型；默认ASR remote-api、LLM openai、TTS edge，三个服务全部带--no-warm。

该发行包的健康回显是八级；共享源码中的十级编排、声纹等未发布修改不属于本次部署，不把迁移前十级健康回显当成本包的能力。Ekho和三个NPU LLM也未随本包部署。

操作脚本、下载包、日志和JSON证据保留在本机工作目录：

```text
S:/work/WCIS/workenv/lang-board-install/
  board.py                  私有SSH传输，不打印凭据
  probe.py                  只读前提检查
  fetch-release.py          从私有GitHub Release获取deb并核对SHA256
  stage-prepare.py           备份、复制模型/配置、退役旧单元
  run-install.py             apt安装和服务启动
  run-verify.py              验证并归档旧server目录
  before.json / release-package.json / install-plan.json
  prepared.json / installed.json / verification.json / apt-install.log
```

## 迁移步骤

1. 只读检查架构、OS、Python、可用空间、当前服务/监听和其他旧server消费者。确认新包适配，并先复用已有依赖及模型。此次预检发现旧三单元仍运行，位于/etc/systemd/system；新包尚未安装。
2. 从[正式Release](https://github.com/takomitkm/HA4FPAI/releases/tag/lang-v0.1.1)取得arm64 deb和SHA256SUMS，在本机核对后SFTP上传，目标再算一次SHA256。使用已登记SSH主机密钥，不自动接受新指纹，不打印或外传目标凭据。
3. 在板端建立root-only备份目录，保存旧单元、drop-in和完整配置；只退役四个指定lang单元，不移动整个lang树、不删除模型或其他业务。
4. 在线配置原样复制到新配置目录，SHA256证明迁移前后一致。组件配置复制时跳过旧server与zz覆盖；用新包管理选档。Linux Edge解码单独覆盖为mpg123，避免新私有venv依赖旧系统miniaudio。循环输出另设到可写cache，避免旧root所有的固定tmp文件阻碍新服务用户。
5. 按包内五组清单复制已有模型到新模型目录，使用文件集合/非空大小检查，不导入模型。为新服务用户授予模型目录写入权，配置保持root所有、lang-server组只读。
6. 停止并disable旧三服务，移动旧unit/drop-in到备份并daemon-reload，确认四固定端口空闲；不终止未知进程。
7. 仅在缺系统依赖时刷新apt索引；通过apt安装本地deb。Python依赖由包内固定版本、带哈希wheel离线装入独立venv，不使用系统pip，也不编译原生组件。此次缺python3-venv；apt实际新增lang-server、python3-venv、python3.8-venv三包，并按venv的版本依赖同步升级7个既有Python3.8系统包，从3.8.10-0ubuntu1~20.04.7到3.8.10-0ubuntu1~20.04.18（解释器仍为3.8.10）。没有执行全量upgrade，另144包未升级。第三方Python依赖仍只进入私有venv，没有使用系统pip。
8. enable并restart新三单元。确认实际FragmentPath指向/lib/systemd/system下的包单元、进程使用新代码与私有Python、账号为lang-server。仅GET health，不请求转写/合成/LLM推理。
9. 下载单元检查到五组现有文件后成功退出，无须联网重拉。确认其Result=success、ExecMainStatus=0以及状态JSON的model_execution=false。
10. 确认没有旧路径消费者后，旧server代码移动到备份下的retired-server；原模型与lang其他目录保留。再次采样，确认新PID不变、没有自动重启。

## 本次落点与读数

```text
新代码       /usr/lib/lang-server/lang/server/
新配置       /etc/lang-server/config/
私有venv     /var/lib/lang-server/venv/
模型         /var/lib/lang-server/models/
循环输出     /var/lib/lang-server/cache/loop_reply.wav
安装暂存     /var/tmp/lang-server-install-20261104T100925Z/
回滚备份     /var/backups/lang-server/migration-20261104T100925Z/
```

Deb SHA256：`0646a03a321399ffb2020a467ddaf32a2891be6fb6944ab6aa770418083fc868`。

| 服务 | 实测PID | 状态 | RSS KiB |
|---|---:|---|---:|
| lang-server-http | 67429 | active/enabled、--no-warm、0次自动重启 | 16848 |
| lang-server-voice | 67430 | active/enabled、--no-warm、0次自动重启 | 20780 |
| lang-server-loop | 68256 | active/enabled、--no-warm、0次自动重启 | 8404 |

两次采样PID稳定；三进程合计46032 KiB，约45MiB；采样时MemAvailable=483444 KiB，约472MiB。这是启动后快照，不是推理峰值或长时稳定性结论。三进程均未映射sherpa/ORT/torch模型运行库；私有venv隔离，pip check无缺依赖。

监听均为0.0.0.0，端口18091、10300、10301、10302。板内及本机访问[HTTP健康接口](http://192.168.1.113:18091/health)均成功。ASR/LLM认证配置可读，未发起新的人工云推理验收，不能把凭据存在当作云端认证与计费额度通过。

五组文件状态均为files-present；模型下载oneshot显示inactive/dead属于成功结束，不是服务故障。服务仍默认在线，模型文件就绪不代表本地推理通过。

## 复核命令

```bash
systemctl status lang-server-http lang-server-voice lang-server-loop
systemctl show lang-server-http -p FragmentPath -p MainPID -p ActiveState -p UnitFileState
systemctl show lang-server-model-download -p Result -p ExecMainStatus
ss -lnt
python3 -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:18091/health")))'
/var/lib/lang-server/venv/bin/python -m pip check
```

验证只看配置、文件、健康、进程与内存映射，不执行模型构造、预热、推理或板端编译。

## 回滚入口

本次没有执行回滚。需要恢复旧手工部署时，先停新服务，再apt remove；不要purge或删除模型。移回旧server、清除包卸载产生的mask、恢复备份单元后重新enable/start。执行前核对目标路径未被其他部署重新占用；若被占用应先另行备份，不能覆盖。

```bash
B=/var/backups/lang-server/migration-20261104T100925Z
sudo systemctl stop lang-server-http lang-server-voice lang-server-loop lang-server-model-download
sudo apt remove lang-server
sudo systemctl unmask lang-server-http lang-server-voice lang-server-loop lang-server-model-download
# 仅当原路径不存在时恢复，禁止覆盖新出现的文件。
test ! -e /mnt/data/lang/server && sudo mv "$B/retired-server" /mnt/data/lang/server
sudo cp -a "$B/retired-units/." /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lang-server-http lang-server-voice lang-server-loop
```

配置原件和五组旧模型仍保留在旧lang树；备份目录是root-only，不将其中的密钥文件收进Git。系统改动归口见[[os#七、我方对板端 OS 的改动（归口，2026-10-11 起）|os——七、我方对板端OS的改动]]，产物登记见[[板端我方代码与产物台账#卅五、lang-server 0.1.1 deb接管旧手工服务|板端我方代码与产物台账——卅五]]。
