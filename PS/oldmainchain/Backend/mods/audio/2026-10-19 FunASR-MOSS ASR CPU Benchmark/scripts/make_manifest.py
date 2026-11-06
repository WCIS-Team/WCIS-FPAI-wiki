# -*- coding: utf-8 -*-
"""
从 modelscope aishell1_test.csv 生成 benchmark manifest。
wav 路径映射到 hf 下载的 shenyunhang/AISHELL-1 本地目录。
用法: python make_manifest.py --csv <csv> --audio-root <dir> --out <json> --limit N --seed 42
"""
import argparse
import csv
import hashlib
import json
import os
import random

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--audio-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = []
    with open(args.csv, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        header = next(r, None)
        for row in r:
            if len(row) >= 2:
                wav_rel = row[0].strip()
                text = row[1].strip()
                # 去掉 "speech_asr_aishell1_testsets/" 前缀，得到 data 内相对路径
                if wav_rel.startswith("speech_asr_aishell1_testsets/"):
                    wav_rel = wav_rel[len("speech_asr_aishell1_testsets/"):]
                rows.append({"wav": wav_rel, "text": text})

    # 确定性抽样
    rng = random.Random(args.seed)
    idx = list(range(len(rows)))
    rng.shuffle(idx)
    if args.limit and args.limit < len(idx):
        idx = idx[:args.limit]

    items = [{"wav": rows[i]["wav"], "text": rows[i]["text"]} for i in sorted(idx)]

    manifest = {
        "dataset": "AISHELL-1 official test set (via shenyunhang/AISHELL-1 audio + modelscope speech_asr_aishell1_testsets csv)",
        "source_csv": os.path.basename(args.csv),
        "total_rows": len(rows),
        "sampled": len(items),
        "seed": args.seed,
        "audio_root": args.audio_root,
        "items": items,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("manifest", args.out, "rows", len(rows), "sampled", len(items))
    print("sha256", sha256_file(args.out))

if __name__ == "__main__":
    main()
