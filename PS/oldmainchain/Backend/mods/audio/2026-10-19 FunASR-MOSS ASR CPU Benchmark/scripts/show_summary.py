# -*- coding: utf-8 -*-
import json
import sys

for name in sys.argv[1:]:
    d = json.load(open(name, encoding="utf-8"))
    print("===", name)
    print(" phases", d["phases"])
    mc = d["memory_cpu"]
    print(
        " mem/cpu",
        {
            k: mc.get(k)
            for k in (
                "start_avg_rss_mb",
                "start_peak_rss_mb",
                "steady_avg_rss_mb",
                "peak_rss_mb",
                "steady_avg_cpu_pct",
                "steady_peak_cpu_pct",
                "user_cpu_s",
                "sys_cpu_s",
            )
        },
    )
    print(" latency", d["latency"])
    print(" rtf", d["rtf"])
    print(" acc", d["accuracy"])
    print(
        " per_item",
        [
            (p.get("wav"), p.get("duration_s"), p.get("latency_s"), p.get("cer"))
            for p in d["per_item"]
        ],
    )
