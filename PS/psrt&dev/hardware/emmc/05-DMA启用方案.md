# 05 · eMMC 提速操作手册（部分执行：50MHz ✅，DMA ✅，8bit ✅不可用，仅剩永久固化 DTB）

> 脚本已写好、overlay 机制已预检通过、50MHz 时钟与 DMA 均已**运行时实测验证**（见 [04-性能实测.md](04-性能实测.md)）。
> 8-bit 实测不可用。执行前请通读 [07-踩坑与注意事项.md](07-踩坑与注意事项.md)。

---

## 0. 预检已完成（2026-10-29，boot `72a8f941`）

**overlay 机制本身已经实测通过，不用再怀疑它能不能用。** 做的全是"只改实时 DT 属性、不 rebind"的空转测试，
驱动不会重新探测，等于零影响：

| 测试 | 结果 |
|---|---|
| `mmc1-clock.dtbo` 注入 | ✅ `status=applied`，`max-frequency` 25000000 → **50000000** |
| `mmc1-dma.dtbo` 注入 | ✅ `status=applied`，`dmas = <0x0a 0x01 0x00 0x00>`、`dma-names = "rx-tx"` 出现 |
| 卸载 overlay 回滚 | ✅ `rmdir` 后属性消失，`max-frequency` 回到 25000000 |
| 驱动是否被影响 | ✅ 无影响，`CTRL=0x10`（仍 PIO）、`CLKDIV=2`（仍 25MHz），符合预期 |
| eMMC 数据完整性 | ✅ 写读 8MB md5 一致 |

**两个必须知道的坑：**

1. **`path` 属性只能写相对 `/lib/firmware` 的文件名。**
   写绝对路径 `/root/emmc-overlays/mmc1-clock.dtbo` 会失败：
   ```
   Direct firmware load for /root/emmc-overlays/mmc1-clock.dtbo failed with error -2
   ```
   而且 **`echo` 的返回码是 0**，看起来像成功，实际没加载（`max-frequency` 没变）。容易误判。
   → **脚本统一用 `dtbo` 二进制接口（`cat xxx.dtbo > overlays/xxx/dtbo`），不走 `path`，绕开这个坑。**

2. **会出现一条 `memory leak will occur if overlay removed` 警告。**
   ```
   OF: overlay: WARNING: memory leak will occur if overlay removed, property: .../max-frequency
   ```
   这是正常的：overlay 替换已有属性时，旧值的字符串没被释放，泄漏几十字节。**无害，忽略。**

### 0.1 50MHz 时钟已运行时实测 ✅（2026-10-30 boot `db887f8e`）

按本手册步骤 1→5 在真机上跑通：

- 停录播（当时 `--mode off`，无写入）→ 停存储卸挂载 → 注入 `mmc1-clock.dtbo` → `unbind/bind` → 重挂载
- 结果：CLKDIV `0x2 → 0x1`，**50MHz 生效**，写 22.9 / 读 23.7 MB/s（×2），16MB 随机写读回 md5 一致，dmesg 无错误
- 直播 `wcis-sdi-vpu-view` 全程未停、未受影响；测试后录播服务已 `systemctl start` 恢复
- 当前是 configfs 临时态，重启即回 25MHz

**下一步只剩把 50MHz 固化进 DTB（见下方"永久改 DTB"），以及可选的 DMA 实测。**

### 0.2 8-bit 总线已实测：不可用 ✅（2026-10-30 boot `db887f8e`）

同样 overlay + rebind，把 `bus-width` 改 8，驱动报 `switch to bus width 8 failed`，**自动回退 4-bit**，
无损坏。原因：PCB 大概率只布线 DAT0~3，或颗粒仅 4-bit。硬件限制，软件无解，这条路封死。
详见 [04-性能实测.md](../emmc/04-性能实测.md) 与 `../hardware/emmc_evidence/8bit-test-20261030-bootdb887f8e.txt`。

---

## 前提：先搞清楚该做什么

根据 [04-性能实测.md](04-性能实测.md) 的结论：

| 措施 | 吞吐收益 | CPU 收益 | 风险 | 优先级 |
|---|---|---|---|---|
| 时钟 25→50MHz | **×2（→约 23 MB/s）** | 无 | 低 | **高** |
| 总线 4→8bit | ×2（若走线支持） | 无 | 中（走线未知） | 中 |
| PIO→DMA | ≈0（瓶颈是总线不是 CPU） | 省 0.6% 总 CPU | 中（请求线未知） | 低 |

**建议顺序：先做时钟（收益最大、风险最低），再决定要不要折腾 DMA。**

**补充（2026-10-29 实测）**：EXT_CSD 已确认卡支持 52MHz / HS200 / HS400，
所以时钟这一步**不存在"卡不支持"的失败可能**，只剩控制器侧能不能稳住 50MHz 的问题。
HS200/HS400 需要 1.8V 信号，DT 里没有 `vqmmc-supply`，**不要试**。

---

## 影响面评估

**root 文件系统在 SD 卡（mmc0）上，eMMC 只是 `/mnt/wcis-emmc` 数据盘。**
所以 eMMC 配置改错**不会导致系统起不来**，最坏情况是 `/mnt/wcis-emmc` 挂载失败。这是很重要的安全垫。

会受影响的服务：

| 服务 | 是否用 eMMC | 处理 |
|---|---|---|
| `wcis-face-recording.service` | **是**（`--storage /mnt/wcis-emmc/wcis-face/recordings`） | **必须先停** |
| `wcis-face-storage.service` | **是**（它就是挂载管理者） | **停它 = 卸载 eMMC** |
| `wcis-face-photo.service` | 否（在 `/root/wcis-face`） | 可不停 |
| `wcis-heartbeat.service` | 否 | 可不停 |
| `wcis-sdi-vpu-view.service` | 否 | 可不停 |

### 卸载 eMMC 的正确方式（重要）

`/mnt/wcis-emmc` **不是 fstab 管的**，是 systemd 单元 `wcis-face-storage.service` 管的：

```ini
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/python3 .../mount_face_store.py --device /dev/mmcblk1p1 --mount /mnt/wcis-emmc --uuid 67104a06-...
ExecStop =/usr/bin/python3 .../mount_face_store.py ... --unmount
```

所以**正确顺序是**：

```bash
systemctl stop wcis-face-recording.service   # 先停使用者
systemctl stop wcis-face-storage.service     # 它自己会跑 --unmount，并校验 UUID
# 测完
systemctl start wcis-face-storage.service    # 重新挂载（自带 UUID 校验）
systemctl start wcis-face-recording.service
```

**不要**直接 `umount /mnt/wcis-emmc`——绕过 systemd 会让 unit 状态和实际挂载不一致，之后 `start` 可能因为 `RemainAfterExit=yes` 而认为"已经挂好了"，导致实际没挂上。

---

## 阶段一：时钟 25 → 50MHz（推荐先做）

### 方式 A：运行时 overlay 试（不重启，可秒回滚）

> 前提：dtbo 已固化在目标机 `/root/emmc-overlays/`（重启不丢）。
> 如果丢了，用 `overlay/*.dts` 重新编译，见文末"重新编译 overlay"。

```bash
# 1. 准备工具（首次执行，重启后不会丢）
scp scripts/01-build-dtc.sh root@192.168.1.113:/tmp/
ssh root@192.168.1.113 "sed -i 's/\r$//' /tmp/01-build-dtc.sh && bash /tmp/01-build-dtc.sh"

# 2. 执行（脚本会自动停服务、卸载、注入、rebind、挂载、测速）
scp scripts/03-test-overlay.sh root@192.168.1.113:/tmp/
ssh root@192.168.1.113 "sed -i 's/\r$//' /tmp/03-test-overlay.sh && bash /tmp/03-test-overlay.sh /root/emmc-overlays/mmc1-clock.dtbo"
```

脚本内部做的 7 步：

0. 检查 configfs overlay 可用、记录 boot ID
1. `systemctl stop wcis-face-recording.service`
2. `systemctl stop wcis-face-storage.service`（= 卸载 eMMC，走官方 --unmount）
3. `mkdir /sys/kernel/config/device-tree/overlays/<name>` + 写入 dtbo
4. `echo e0044000.dwmmc > /sys/bus/platform/drivers/dw_mmc/unbind` 然后 `bind`
5. 重新挂载并跑 32MB 读写测速
6. 记录 `/sys/kernel/debug/mmc1/ios` 的实际时钟

**判断成功**：

```bash
grep -E 'clock:|bus width:' /sys/kernel/debug/mmc1/ios
# 期望 clock: 50000000 Hz
```

**判断失败**（信号完整性问题，会看到 CRC 错误）：

```bash
dmesg | grep -iE 'crc|error|timeout' | tail
```

失败就回滚：

```bash
bash /tmp/03-test-overlay.sh --rollback
```

### 方式 B：永久改 DTB（重启生效）

运行时验证没问题后，把改动固化到 DTB：

```bash
scp scripts/04-apply-dtb-permanent.sh root@192.168.1.113:/tmp/
ssh root@192.168.1.113 "sed -i 's/\r$//' /tmp/04-apply-dtb-permanent.sh"

# 先空跑校验，不写盘
ssh root@192.168.1.113 "bash /tmp/04-apply-dtb-permanent.sh verify"

# 确认无误后写入
ssh root@192.168.1.113 "bash /tmp/04-apply-dtb-permanent.sh clock"

# 重启生效
ssh root@192.168.1.113 reboot
```

脚本的安全设计：

- 改前备份到 `fmqlmp-verify.dtb.bak-<时间戳>`
- dtc 往返编译后强制 `diff`，**只允许 `dmas` / `dma-names` / `max-frequency` 三种行变化**，出现其他变更立即中止不写盘
- 自动 `sync` 后 umount

> **已验证**：在 `/tmp/cur.dtb` 副本上跑 `both` 模式，diff 只出现 3 处预期变化，编译后 16079 → 16127 字节，phandle `0x0a` 保持不变。

---

## 阶段二：DMA（已实测 ✅，验证厂商那句注释）

> **2026-10-30 实测结论**：在 eMMC 节点补 `dmas = <0x0a 0x01 0x00 0x00>`（req=1）后，
> 驱动打印 `Using external DMA controller.`，CTRL `0x10 → 0x30`（bit5=1），读写正常、数据完整。
> **本板 req=1 请求线接好了，厂商注释 `/* mmc1 not support dma */` 是错的。**
> 但 DMA 不改吞吐（总线已饱和），只省 CPU；提总线下仍需照常做。

如果阶段一成功、且你确实想搞清楚"mmc1 到底支不支持 DMA"，再做这一步。

```bash
# dtbo 已就绪: /root/emmc-overlays/mmc1-dma.dtbo
ssh root@192.168.1.113 "bash /tmp/03-test-overlay.sh /root/emmc-overlays/mmc1-dma.dtbo"
```

**判断成功**：

```bash
dmesg | grep -E 'dw_mmc.*e0044000|Using (PIO|external)'
# 成功: "Using external DMA controller."
# 失败: "Using PIO mode."
```

同时看：

```bash
cat /sys/class/dma/dma0chan1/in_use    # 期望变成 1
```

**如果请求线没接会怎样**：probe 阶段只申请 channel 不传输，所以仍会打印 "Using external DMA controller."，但**第一次真正读写会卡住直到超时**，表现为 `I/O error`、`mmc1: Timeout waiting for hardware interrupt`。

所以测试时脚本会立刻做一次 32MB 读写——卡住就是失败信号。**看到卡住直接 Ctrl-C 然后回滚。**

> 历史记录：本板实测时 req=1 **没有卡住**，读写正常，证明线接好了。如果换板子/换批次，仍需按上面流程验证。

### 请求线号说明

`dmas = <0x0a REQ 0 0>` 里的 `REQ` 当前填的是 `1`。

- `0x0a` 是 `dmahost0` 的 phandle（运行中的 DTB 没有 `__symbols__`，无法用 `&dmahost0`，只能硬编码）
- `REQ=0` 已被 SD 卡（mmc0）占用，所以 eMMC 必须用别的
- `of.c:28-29` 里 `args[0]` 同时赋给 `src_id` 和 `dst_id`，收发共用一条请求线
- 如果 `1` 不行，依次试 `2`、`3`…`15`（`dma-requests = 16`）

改请求线的方法：编辑 `overlay/mmc1-dma-overlay.dts` 里的 `<0x0a 0x01 0x00 0x00>`，把 `0x01` 换成目标值，重新编译。

---

## 阶段三：8-bit 总线（最后考虑）

`bus-width = <0x04>` 改成 `<0x08>`，`CTYPE` 会自动变 `0x3`。

**风险最高**：eMMC 芯片本身几乎肯定支持 8-bit，但板子上 D0-D7 八根数据线是否全部走通是未知数。如果只走了 4 根，切到 8-bit 会直接数据错误、文件系统损坏。

**判断依据**：如果板子是 4-bit 走线，切换后第一次读就会 CRC 错误或读出一堆乱码。所以：

1. 必须先在**空的 eMMC** 或已备份的前提下测
2. 或者用 `mmc-utils` 先读 EXT_CSD 的 `BUS_WIDTH` 支持位（目标机没有 mmc-utils，需要先交叉编译）

不建议在现在这个有数据的 eMMC 上直接试。

---

## 完整回滚

```bash
# 只回滚运行时 overlay（不重启）
bash /tmp/03-test-overlay.sh --rollback

# 回滚 boot 分区的 DTB（需重启）
scp scripts/99-rollback.sh root@192.168.1.113:/tmp/
ssh root@192.168.1.113 "sed -i 's/\r$//' /tmp/99-rollback.sh && bash /tmp/99-rollback.sh /mnt/bootrw/fmqlmp-verify.dtb.bak-<时间戳>"
ssh root@192.168.1.113 reboot
```

备份文件都在 boot 分区上，命名 `fmqlmp-verify.dtb.bak-YYYYMMDDTHHMMSS`。

---

## 重新编译 overlay（如果 /root/emmc-overlays/ 丢了）

```bash
# 上传源码
scp overlay/*.dts root@192.168.1.113:/root/emmc-overlays/

# 编译
ssh root@192.168.1.113 'DTC=/root/home/lili/linux-5.4.52-fmsh/scripts/dtc/dtc
  cd /root/emmc-overlays
  for f in *.dts; do sed -i "s/\r$//" $f; done
  for n in clock dma both; do
    $DTC -@ -I dts -O dtb -o mmc1-$n.dtbo mmc1-$n-overlay.dts
  done
  ls -la *.dtbo'
```

期望产物：`mmc1-clock.dtbo` 194B / `mmc1-dma.dtbo` 227B / `mmc1-both.dtbo` 257B。

编译时会警告 `cell 0 is not a phandle reference`，**这是预期的**——我们故意硬编码 phandle `0x0a`（运行中 DTB 没有 `__symbols__`，无法用 `&dmahost0`）。

---

## 执行检查清单

执行前逐项打勾：

- [ ] 已读 [07-踩坑与注意事项.md](07-踩坑与注意事项.md)
- [ ] 确认当前没有正在进行的录像任务（`systemctl status wcis-face-recording`）
- [ ] 确认 `/mnt/wcis-emmc` 上没有别的重要写入
- [ ] 已备份 `/mnt/wcis-emmc/wcis-face/` 下的数据（如果在意）
- [ ] dtc 已编译好（`01-build-dtc.sh`）
- [ ] overlay 已编译好
- [ ] 知道怎么回滚（本文"完整回滚"一节）
- [ ] 有人能在设备旁边物理断电重启（万一彻底卡死）

执行后记录：

- [ ] **boot ID**：`cat /proc/sys/kernel/random/boot_id`（这块板子频繁重启，不记 boot ID 的数据不可比）
- [ ] SDIO 时钟实际值：`cat /sys/kernel/debug/mmc1/ios | grep clock`
- [ ] 驱动模式：`dmesg | grep 'Using'`
- [ ] 实测吞吐：`02-bench-mmc.sh` 输出
- [ ] 有无 CRC/超时错误：`dmesg | grep -iE 'crc|timeout'`
- [ ] **CPU 主频未变**（本来也改不了，但确认一下）：`ls /sys/devices/system/cpu/cpu0/cpufreq` 仍不存在
