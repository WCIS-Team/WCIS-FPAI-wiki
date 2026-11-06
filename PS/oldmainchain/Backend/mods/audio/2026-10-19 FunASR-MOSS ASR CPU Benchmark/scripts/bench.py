# -*- coding: utf-8 -*-
"""
ASR CPU-only Benchmark runner (per S:\\work\\WCIS\\wiki\\SOP\\MOD\\ASR CPU-only Benchmark SOP.md)

每次调用执行一轮完整流程（冷启动 -> 模型加载 -> 首次推理 -> 预热 -> 稳态推理 -> 全程资源监控），
输出一个 JSON 结果文件。外层脚本循环调用多次以获得独立重复运行。

用法:
  python bench.py --model paraformer --manifest manifest.json --out out.json [--threads 4] [--timeout 600]

依赖: funasr / transformers / psutil / jieba (由 FunASR 环境提供)
"""

import argparse
import ctypes
import json
import math
import os
import re
import sys
import threading
import time

import psutil

# ---------------------------------------------------------------------------
# CPU 亲和性与线程配置
# ---------------------------------------------------------------------------

def apply_cpu_limit(threads, core_ids):
    """将当前进程限制到给定逻辑核，并设置 torch 线程数。"""
    proc = psutil.Process()
    try:
        proc.cpu_affinity(core_ids)
    except Exception as e:
        print("[warn] cpu_affinity failed:", e)
    import torch
    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(1)
    except Exception:
        pass
    return proc.cpu_affinity()

# ---------------------------------------------------------------------------
# 文本归一化与 CER/WER
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[\s\u3000!\x22#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~，。！？；：、（）《》〈〉「」『』【】〔〕“”‘’～·…—–．℃％＊×÷±]")

def normalize(text):
    """移除标点与空白；保留汉字、字母、数字。不做简繁与数字转换（记录于配置）。"""
    t = _PUNCT_RE.sub("", text or "")
    return t

def levenshtein(a, b):
    """字符级编辑距离。"""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def word_seg(text):
    """中文按 jieba 分词；非中文 token 按空白/字母数字切分。"""
    import jieba
    return list(jieba.cut(text))

def char_metrics(ref, hyp):
    ref_n = normalize(ref)
    hyp_n = normalize(hyp)
    d = levenshtein(ref_n, hyp_n)
    s = 0
    i = 0
    # 从编辑距离反推 S/D/I 不直接；此处用对齐近似：
    # 采用最长公共子序列近似分解，简化处理：S+D+I = d，且 D = len(ref_n) - LCS,
    # I = len(hyp_n) - LCS, S = d - D - I
    lcs = lcs_len(ref_n, hyp_n)
    D = len(ref_n) - lcs
    I = len(hyp_n) - lcs
    S = d - D - I
    if S < 0:
        S = 0
    cer = d / len(ref_n) if len(ref_n) else (1.0 if d else 0.0)
    return {"cer": cer, "S": S, "D": D, "I": I, "ref_chars": len(ref_n)}

def lcs_len(a, b):
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]

def word_metrics(ref, hyp):
    import jieba
    jieba.setLogLevel(60)
    rw = word_seg(normalize(ref))
    hw = word_seg(normalize(hyp))
    d = levenshtein(rw, hw)
    wer = d / len(rw) if len(rw) else (1.0 if d else 0.0)
    return {"wer": wer, "S": d, "ref_words": len(rw)}

# ---------------------------------------------------------------------------
# 模型加载与推理
# ---------------------------------------------------------------------------

def load_model(name, model_dir):
    if name in ("paraformer", "sensevoice"):
        from funasr import AutoModel
        kwargs = {
            "model": model_dir,
            "disable_update": True,
            "device": "cpu",
        }
        if name == "sensevoice":
            kwargs["trust_remote_code"] = False
        model = AutoModel(**kwargs)
        return model, None
    elif name == "moss":
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor
        model = AutoModelForCausalLM.from_pretrained(
            model_dir, trust_remote_code=True, dtype="auto"
        ).to(dtype=torch.float32).to("cpu").eval()
        processor = AutoProcessor.from_pretrained(model_dir, trust_remote_code=True)
        return model, processor
    raise ValueError("unknown model " + name)

def _strip_tags(text):
    """剥离 MOSS 的 [start][Sxx]... 时间戳/说话人标签 与 SenseVoice 的 <|...|> 标签。"""
    t = re.sub(r"<\|[^|]*\|>", "", text or "")
    t = re.sub(r"\[\d+(\.\d+)?\]", "", t)
    t = re.sub(r"\[S\d+\]", "", t)
    return t

def transcribe(name, model, processor, wav_path, timeout):
    from funasr import AutoModel as _unused  # noqa
    if name == "paraformer":
        res = model.generate(input=wav_path, batch_size=1, disable_pbar=True)
        text = res[0]["text"] if res else ""
        return text
    if name == "sensevoice":
        res = model.generate(input=wav_path, language="auto", use_itn=True, disable_pbar=True)
        text = res[0]["text"] if res else ""
        return _strip_tags(text)
    if name == "moss":
        import torch
        from moss_transcribe_diarize import parse_transcript  # noqa
        from moss_transcribe_diarize.inference_utils import (
            build_transcription_messages,
            generate_transcription,
            resolve_device,
        )
        device = resolve_device("auto")
        dtype = torch.float32
        messages = build_transcription_messages(wav_path)
        result = generate_transcription(
            model, processor, messages,
            max_new_tokens=2048, do_sample=False,
            device=device, dtype=dtype,
        )
        return _strip_tags(result["text"])
    raise ValueError("unknown model " + name)

# ---------------------------------------------------------------------------
# 资源监控线程
# ---------------------------------------------------------------------------

class Monitor(threading.Thread):
    def __init__(self, interval=0.5):
        super().__init__(daemon=True)
        self.interval = interval
        self.samples = []
        self.stop = threading.Event()
        self.proc = psutil.Process()

    def run(self):
        while not self.stop.is_set():
            try:
                with self.proc.oneshot():
                    rss = self.proc.memory_info().rss
                    cpu = self.proc.cpu_percent(interval=None)
                    ut = self.proc.cpu_times().user
                    st = self.proc.cpu_times().system
                    self.samples.append((time.time(), rss, cpu, ut, st))
            except Exception:
                pass
            time.sleep(self.interval)

    def stop_and_stats(self, t_start, t_steady_start, t_steady_end):
        self.stop.set()
        self.join(timeout=5)
        if not self.samples:
            return {}
        # 启动阶段 = t_start..t_steady_start
        start_s = [s for s in self.samples if s[0] <= t_steady_start + 0.001]
        steady_s = [s for s in self.samples if t_steady_start <= s[0] <= t_steady_end]
        all_rss = [s[1] for s in self.samples]
        stats = {
            "start_avg_rss_mb": mean([s[1] for s in start_s]) / 1048576 if start_s else None,
            "start_peak_rss_mb": max([s[1] for s in start_s]) / 1048576 if start_s else None,
            "steady_avg_rss_mb": mean([s[1] for s in steady_s]) / 1048576 if steady_s else None,
            "peak_rss_mb": max(all_rss) / 1048576 if all_rss else None,
            "steady_avg_cpu_pct": mean([s[2] for s in steady_s]) if steady_s else None,
            "steady_peak_cpu_pct": max([s[2] for s in steady_s]) if steady_s else None,
            "user_cpu_s": steady_s[-1][3] if steady_s else None,
            "sys_cpu_s": steady_s[-1][4] if steady_s else None,
            "sample_count": len(self.samples),
            "sample_interval_s": self.interval,
        }
        return stats

def mean(xs):
    return sum(xs) / len(xs) if xs else None

def percentile(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] * (c - k) + xs[c] * (k - f)

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["paraformer", "sensevoice", "moss"])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--core-mask", type=int, default=0xF)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--timeout", type=float, default=1800)
    ap.add_argument("--run-id", type=int, default=1)
    args = ap.parse_args()

    t_process_start = time.time()
    env_cores = list(range(24))
    mask_cores = [i for i in env_cores if (args.core_mask >> i) & 1]
    actual_affinity = apply_cpu_limit(args.threads, mask_cores)

    mon = Monitor(interval=0.5)
    mon.start()
    t_import_done = time.time()

    manifest = load_manifest(args.manifest)
    items = manifest["items"]
    audio_root = manifest["audio_root"]
    run_label = f"{args.model}-run{args.run_id}"

    # ---- 模型加载 ----
    t_load0 = time.time()
    model, processor = load_model(args.model, args.model_dir)
    t_model_loaded = time.time()

    # ---- 首次推理 ----
    def infer(i):
        wav = os.path.join(audio_root, items[i]["wav"])
        ref = items[i]["text"]
        t0 = time.time()
        hyp = transcribe(args.model, model, processor, wav, args.timeout)
        dt = time.time() - t0
        return hyp, ref, dt, wav

    first_hyp, first_ref, first_infer_s, _ = infer(0)

    # ---- 预热 ----
    for i in range(1, min(args.warmup + 1, len(items))):
        infer(i)

    # ---- 稳态推理（全部样本，含第 0 条重跑以消除首推理影响） ----
    t_steady_start = time.time()
    per_item = []
    n_ok = n_empty = n_err = n_timeout = 0
    audio_sec_total = 0.0
    lat = []
    rtfs = []
    for i, it in enumerate(items):
        try:
            t0 = time.time()
            hyp, ref, dt, wav = infer(i)
            wall = dt
            lat.append(wall)
            # 音频时长
            try:
                import soundfile as sf
                info = sf.info(wav)
                dur = info.frames / info.samplerate
            except Exception:
                dur = None
            if dur:
                audio_sec_total += dur
                rtfs.append(wall / dur)
            if not normalize(hyp):
                n_empty += 1
            cm = char_metrics(ref, hyp)
            wm = word_metrics(ref, hyp)
            per_item.append({
                "idx": i, "wav": os.path.basename(wav),
                "duration_s": dur, "latency_s": round(wall, 4),
                "rtf": round(wall / dur, 4) if dur else None,
                "ref": ref, "hyp": hyp,
                "cer": round(cm["cer"], 6), "S": cm["S"], "D": cm["D"], "I": cm["I"],
                "ref_chars": cm["ref_chars"], "wer": round(wm["wer"], 6),
                "ref_words": wm["ref_words"],
            })
            n_ok += 1
        except Exception as e:
            n_err += 1
            per_item.append({"idx": i, "wav": os.path.basename(it["wav"]), "error": repr(e)})
    t_steady_end = time.time()

    # ---- 汇总 ----
    res = {}
    res["meta"] = {
        "model": args.model,
        "model_dir": args.model_dir,
        "run_id": args.run_id,
        "python": sys.version.split()[0],
        "torch_threads": args.threads,
        "affinity_cores": actual_affinity,
        "cpu_limit_note": "affinity 限制 4 逻辑核；每核 1GHz 属宿主机 VM 配置，guest 内无法施加，按实测频率记录",
        "cpu_percent_definition": "psutil Process.cpu_percent，单核满载计 100%，多线程累计可超 100%",
        "normalization": "移除全部标点与空白；保留汉字/字母/数字；未做简繁与数字转换",
        "warmup": args.warmup,
        "timeout_s": args.timeout,
    }
    import funasr, torch, transformers
    res["versions"] = {
        "funasr": funasr.__version__,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "psutil": psutil.__version__,
    }
    res["phases"] = {
        "cold_start_s": round(t_import_done - t_process_start, 3),
        "model_load_s": round(t_model_loaded - t_load0, 3),
        "first_infer_s": round(first_infer_s, 4),
        "total_wall_s": round(t_steady_end - t_process_start, 3),
    }
    stats = mon.stop_and_stats(t_process_start, t_steady_start, t_steady_end)
    res["memory_cpu"] = stats
    total_audio = audio_sec_total
    total_wall_steady = t_steady_end - t_steady_start
    res["latency"] = {
        "n": len(lat), "mean_s": round(mean(lat), 4) if lat else None,
        "p50_s": round(percentile(lat, 50), 4) if lat else None,
        "p95_s": round(percentile(lat, 95), 4) if lat else None,
        "p99_s": round(percentile(lat, 99), 4) if lat else None,
    }
    res["rtf"] = {
        "mean": round(mean(rtfs), 4) if rtfs else None,
        "p50": round(percentile(rtfs, 50), 4) if rtfs else None,
        "p95": round(percentile(rtfs, 95), 4) if rtfs else None,
        "p99": round(percentile(rtfs, 99), 4) if rtfs else None,
        "definition": "RTF = 推理墙钟耗时 / 音频时长",
    }
    res["throughput"] = {
        "audio_sec": round(total_audio, 3),
        "steady_wall_s": round(total_wall_steady, 3),
        "audio_sec_per_wall_sec": round(total_audio / total_wall_steady, 4) if total_wall_steady else None,
        "definition": "吞吐量 = 成功样本音频总时长 / 稳态墙钟总时长（含预处理与后处理）",
    }
    ok_items = [p for p in per_item if "cer" in p]
    if ok_items:
        ref_chars = sum(p["ref_chars"] for p in ok_items)
        ref_words = sum(p["ref_words"] for p in ok_items)
        S = sum(p["S"] for p in ok_items)
        D = sum(p["D"] for p in ok_items)
        I = sum(p["I"] for p in ok_items)
        res["accuracy"] = {
            "cer": round((S + D + I) / ref_chars, 6) if ref_chars else None,
            "wer": round(sum(p["wer"] * p["ref_words"] for p in ok_items) / ref_words, 6) if ref_words else None,
            "S": S, "D": D, "I": I,
            "ref_chars": ref_chars, "ref_words": ref_words,
            "success": len(ok_items), "empty": n_empty, "error": n_err, "timeout": n_timeout,
            "fail_rate": round((len(items) - len(ok_items)) / len(items), 4) if items else None,
        }
    else:
        res["accuracy"] = {"success": 0, "empty": n_empty, "error": n_err, "timeout": n_timeout, "fail_rate": 1.0}
    res["per_item"] = per_item

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("DONE", args.model, args.run_id, "->", args.out)
    print("CER", res.get("accuracy", {}).get("cer"), "RTF", res.get("rtf", {}).get("mean"))

if __name__ == "__main__":
    main()
