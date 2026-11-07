from pathlib import Path

p = Path(r'S:\work\WCIS\repos\HA4FPAI\docs\COEXISTENCE.md')
s = p.read_text(encoding='utf-8')

# §一① 改写
old1 = """① NPU 会话（决定"常驻"可能性）
   ZG330 session 是设备级独占：第二会话 apply 成功也会破坏第一会话的 DMA 通道
   （实验：Qwen3 常驻后 HiFi-GAN 第二 worker apply→Qwen3 forward "DMA Write failed"；
    同进程双 session 同样崩）。⇒ NPU 上**任意时刻只有一个会话**，多模型只能"时间分片"，
    切换代价 = 杀 worker + 重新 apply（件大小决定：HiFi-GAN 0.4s，ERNIE ~40s，Qwen3 ~170s）。"""
new1 = """① NPU 会话（决定"常驻"可能性）——**2026-11-08 结论修正**
   原判"session 设备级独占"是**误诊**：真规则 = **`openDevice()` 每进程只能调一次**。
   第二把 device 句柄（同进程再开、或另一进程各开各的）会打坏第一把的 DMA 通道——
   这就是当年多 worker 实验与 11-07 晚双 worker 实验里 "DMA Write failed" 的真因。
   **同一把 device 上 session 可以任意叠加、任意卸载重建**（实测：hf session 重建 3 轮
   逐位相同；qwen3-K128 + hifigan 同进程同 device 交替 forward/apply 全绿）。
   ⇒ **多模型常驻可行**：npuserv `--resident`（单 worker 单 device 多 session），
   qwen3+hifigan 并存交替 generate 实测通过（README "Resident mode" 节）。
   约束仍在：每个 adapter 必须接受 device 注入（不再自己 openDevice）——qwen3/hifigan
   已转，ERNIE 已转（e41_chatd.E41(device=)）；worker 崩 = 全部 resident 丢。
   切换代价：同 device 叠 session 时 **apply 就是切换代价**（HiFi-GAN 0.4s / ERNIE ~40s
   / Qwen3 ~170s），但 apply 之后各 session 并存，不再互踢。"""
assert old1 in s, 'section 1 anchor missing'
s = s.replace(old1, new1)

# §三 结论表改写
old2 = """| **Qwen3 + HiFi-GAN 同时常驻** | ❌ | NPU session 设备独占（§一①），实验实证 |"""
new2 = """| **Qwen3 + HiFi-GAN 同时常驻** | ✅ **2026-11-08 实测通过** | npuserv `--resident` 单 device 多 session：q3 2.06→2.54 tok/s、hf peak 1.0、交替全绿（原判 ❌ 系误诊，见 §一①） |"""
assert old2 in s, 'conclusion row anchor missing'
s = s.replace(old2, new2)

old3 = """**架构结论**：语音/LLM 线与视觉线在**NPU 时间轴上互斥**，共享靠"分时+小件热切换"
（vocoder apply 0.4s 可随句切换；LLM apply 170s 只能整段让出视觉）。若日后要真并存，
解法在**驱动/图层面**（NPU 多会话或 CMA 预算重划），不是 npuserv 能解决的。"""
new3 = """**架构结论（2026-11-08 修订）**：模型间互斥**已被 resident 模式解除**（单 device 多
session 叠加）；**仍然互斥的是 LLM apply ↔ 相机**——那是 CMA 预算问题（apply 吃光
CmaFree），与会话数无关。即：多模型并存 ✅，多模型+相机（含 LLM apply 阶段）仍要
分时（apply 期间视觉让位；apply 完成后 LLM 推理不吃 CMA，推理阶段与相机并存待验
——推理本身若不碰 CMA 则窗口期后可共存，未单独实测）。"""
assert old3 in s, 'arch conclusion anchor missing'
s = s.replace(old3, new3)
p.write_text(s, encoding='utf-8', newline='')
print('COEXISTENCE rewritten for 2026-11-08 findings')