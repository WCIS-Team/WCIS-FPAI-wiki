# -*- coding: utf-8 -*-
"""Aggregate full benchmark run JSONs into a summary JSON + Markdown table.

Usage: python aggregate.py <out_summary.json> <out_table.md> <run1.json> <run2.json> ...
Runs are grouped by --model field; stats are mean/stdev across runs.
"""
import json
import math
import statistics
import sys


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


def stdev(xs):
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def fmt(v, digits=3):
    if isinstance(v, float) and math.isnan(v):
        return "N/A"
    return f"{v:.{digits}f}"


def main():
    out_json, out_md, *runs = sys.argv[1:]
    groups = {}
    order = []
    for p in runs:
        d = json.load(open(p, encoding="utf-8"))
        model = d["meta"]["model"]
        if model not in groups:
            groups[model] = []
            order.append(model)
        groups[model].append(d)

    summary = {}
    lines = []
    lines.append("| 模型 | 轮次 | CER% | WER% | 延迟 P50(s) | P95(s) | P99(s) | RTF | 吞吐(音频秒/墙钟秒) | 稳态RSS(MB) | 峰值RSS(MB) | 稳态CPU% | 峰值CPU% | 加载(s) |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for model in order:
        ds = groups[model]
        summary[model] = []
        for d in ds:
            a = d["accuracy"]
            lat = d["latency"]
            rtf = d["rtf"]
            mc = d["memory_cpu"]
            ph = d["phases"]
            th = d.get("throughput", {})
            row = {
                "run": d["meta"]["run_id"],
                "cer_pct": a["cer"] * 100,
                "wer_pct": a["wer"] * 100,
                "lat_p50": lat["p50_s"],
                "lat_p95": lat["p95_s"],
                "lat_p99": lat["p99_s"],
                "rtf": rtf["mean"],
                "thr_audio_sec_per_sec": th.get("audio_sec_per_wall_sec", float("nan")),
                "rss_steady_mb": mc["steady_avg_rss_mb"],
                "rss_peak_mb": mc["peak_rss_mb"],
                "cpu_steady_pct": mc["steady_avg_cpu_pct"],
                "cpu_peak_pct": mc["steady_peak_cpu_pct"],
                "load_s": ph["model_load_s"],
                "success": a["success"],
                "empty": a["empty"],
                "error": a["error"],
            }
            summary[model].append(row)
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    model,
                    row["run"],
                    fmt(row["cer_pct"]),
                    fmt(row["wer_pct"]),
                    fmt(row["lat_p50"]),
                    fmt(row["lat_p95"]),
                    fmt(row["lat_p99"]),
                    fmt(row["rtf"]),
                    fmt(row["thr_audio_sec_per_sec"]),
                    fmt(row["rss_steady_mb"], 0),
                    fmt(row["rss_peak_mb"], 0),
                    fmt(row["cpu_steady_pct"], 0),
                    fmt(row["cpu_peak_pct"], 0),
                    fmt(row["load_s"]),
                )
            )
        # mean row
        cols = ["cer_pct", "wer_pct", "lat_p50", "lat_p95", "lat_p99", "rtf", "thr_audio_sec_per_sec", "rss_steady_mb", "rss_peak_mb", "cpu_steady_pct", "cpu_peak_pct", "load_s"]
        mvals = []
        for c in cols:
            vs = [r[c] for r in summary[model]]
            if c in ("success", "empty", "error"):
                mvals.append(sum(vs))
                continue
            mvals.append(f"{mean(vs):.3f}±{stdev(vs):.3f}")
        lines.append(
            "| **{} 均值** | 3轮 | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                model,
                mvals[0], mvals[1], mvals[2], mvals[3], mvals[4], mvals[5], mvals[6],
                fmt(mean([r["rss_steady_mb"] for r in summary[model]]), 0),
                fmt(mean([r["rss_peak_mb"] for r in summary[model]]), 0),
                fmt(mean([r["cpu_steady_pct"] for r in summary[model]]), 0),
                fmt(mean([r["cpu_peak_pct"] for r in summary[model]]), 0),
                fmt(mean([r["load_s"] for r in summary[model]]), 0),
            )
        )

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("AGGREGATE_OK", out_json, out_md, "models", len(order))


if __name__ == "__main__":
    main()
