# -*- coding: utf-8 -*-
"""Download wav files listed in a manifest JSON via official huggingface_hub SDK.

Usage: python download_sample.py <manifest.json> [more_manifests.json ...]
"""
import json
import sys

from huggingface_hub import hf_hub_download

REPO = "shenyunhang/AISHELL-1"
LOCAL_DIR = r"D:\yzd\llm\funasr\data\aishell1"


def main():
    for mpath in sys.argv[1:]:
        with open(mpath, "r", encoding="utf-8") as f:
            m = json.load(f)
        ok = fail = 0
        for it in m["items"]:
            rel = "data_aishell/" + it["wav"]
            try:
                p = hf_hub_download(
                    repo_id=REPO,
                    filename=rel,
                    repo_type="dataset",
                    local_dir=LOCAL_DIR,
                )
                ok += 1
                print("OK", rel, "->", p)
            except Exception as e:
                fail += 1
                print("FAIL", rel, repr(e))
        print("SUMMARY", mpath, "ok", ok, "fail", fail)


if __name__ == "__main__":
    main()
