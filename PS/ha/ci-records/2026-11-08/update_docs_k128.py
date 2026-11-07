from pathlib import Path

repo = Path(r'S:\work\WCIS\repos\HA4FPAI')

# 1) pipeline.md 增补 K128 重编译记录
pm = repo / 'lang/llm/models/Qwen3-0.6B/pipeline.md'
s = pm.read_text(encoding='utf-8')
s += """

## 9. K128：KV 深度 512→128 重编译（2026-11-07，速度 0.93→2.13 tok/s）

动机：45min 长稳定位到每步 ~0.93s 的瓶颈＝56×2MB KV 的每步 DMA（112MB）。
把 `max_tokens_length` 从 512 改 **128**（Q3V1_parse.toml 唯一旋钮），KV 变
[1,8,128,128]，每步 DMA 28MB。

全链（本机 agentwork/qwen3/compile，**全部产物隔离在 jr_path/Q3K128/**，不碰 Q3V1）：

```
Q3K128_full.toml（五段全在 Q3K128/ 目录；net_name=Q3K128）
  icraft parse/optimize/quantize/adapt    # 各 ~1min
python patch_mask0.py adapted.json adapted_mask0zg.json "@zhuget(330)"
                                        # n 自动=128：Slice[0,0,127]、[0,0,1]
Q3K128_gen.toml（[parse] max_tokens_length=128 + [generate] json/raw 相对 cwd 全路径）
  icraft generate                         # 出 Q3K128-decoder_ZG.{json,raw}
```

坑（三个都踩过）：
1. toml 里 [parse] 的 `max_tokens_length` 是唯一深度旋钮；generate 段**也要写**
   （否则 CausalMask 参数回默认）。
2. [generate] 的 json/raw 是 **cwd 相对**路径（不是相对 jr_path）——写 `Q3V1/…` 会
   拼出 `jr_path/Q3V1//Q3V1/…` 不存在；写 `./jr_path/Q3K128/…` 全路径。
3. jr_path 隔离必须做：曾用「只改文件名前缀、共用 Q3V1/ 目录」的方式，adapt 链把
   现役 Q3V1-decoder_{optimized,quantized,adapted} **覆写**了（确定性编译，内容
   未损、_ZG 未动，但属事故）。

验证：
- 图内 KV `[1,8,128,128]`（grep json），`kv_depth_from_graph:128`（板上 load info）。
- 语义：host_gen 25 链（gen_k128）与校机 HF padfix-mask0 参考 **26/26 逐 id 全等**；
  上板 64 token 文本连贯（2.13 tok/s）。
- 上板：`/root/qwen3/jr_path/decode_k128/`（raw md5 3502236b…），registry qwen3
  defaults 加 `json/raw/max_decode_length=128`（回退＝删这三个键）。
- 读数：max_new=32 → **2.01 tok/s**；max_new=64 → **2.13 tok/s**（无 swap）。
  每步 ~0.47s：DMA 28MB≈0.15s + NPU 计算 ~0.3s（计算成为新瓶颈——再提速要
  减层数/换 quant，超出本件范围）。
"""
pm.write_text(s, encoding='utf-8', newline='')

# 2) Qwen3 README 追加一段
rm = repo / 'lang/llm/models/Qwen3-0.6B/README.md'
r = rm.read_text(encoding='utf-8')
r += """

## K128：KV 深度重编译（2026-11-07）——2.13 tok/s（原 0.93）

`max_tokens_length` 512→128 重编译（pipeline.md §9 全流程），KV [1,8,128,128]，
每步 KV DMA 112MB→28MB。语义与校机 HF 参考 26/26 全等；板上 max_new=64 →
**2.13 tok/s**（原 1.04）。上下文窗口同步缩到 128（prompt+生成 ≤128 token，
语音单轮场景够用）。registry defaults 已指 `decode_k128` 件；回退＝删 defaults
的 `json/raw/max_decode_length`。
"""
rm.write_text(r, encoding='utf-8', newline='')
print('pipeline.md and README.md updated')