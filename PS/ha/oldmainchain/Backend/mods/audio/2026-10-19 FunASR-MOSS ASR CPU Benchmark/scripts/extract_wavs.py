# -*- coding: utf-8 -*-
"""Extract wav relative paths from a manifest JSON into a plain-text list (one per line)."""
import json
import sys

if len(sys.argv) != 3:
    print("usage: extract_wavs.py <manifest.json> <out.txt>")
    sys.exit(2)
with open(sys.argv[1], "r", encoding="utf-8") as f:
    m = json.load(f)
paths = ["data_aishell/" + it["wav"] for it in m["items"]]
with open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write("\n".join(paths) + "\n")
print("WAVS", len(paths))
