# -*- coding: utf-8 -*-
"""List file tree of shenyunhang/AISHELL-1 dataset to find wav path prefix."""
from collections import Counter
from huggingface_hub import HfApi

api = HfApi()
repo = "shenyunhang/AISHELL-1"
items = list(api.list_repo_tree(repo, repo_type="dataset", recursive=True))
print("TOTAL_ITEMS", len(items))
wavs = [i.path for i in items if i.path.endswith(".wav")]
print("WAV_COUNT", len(wavs))
for p in wavs[:20]:
    print("SAMPLE", p)
pref3 = Counter("/".join(p.split("/")[:3]) for p in wavs)
print("--- PREFIX3 TOP20 ---")
for k, v in pref3.most_common(20):
    print("PREF3", k, v)
pref2 = Counter("/".join(p.split("/")[:2]) for p in wavs)
print("--- PREFIX2 TOP20 ---")
for k, v in pref2.most_common(20):
    print("PREF2", k, v)
# 非 wav 顶层条目
tops = Counter(i.path.split("/")[0] for i in items)
print("--- TOPLEVEL ---")
for k, v in tops.most_common(30):
    print("TOP", k, v)
