# -*- coding: utf-8 -*-
"""Compare two manifest JSON files (items only)."""
import json
import sys

a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
ia = [(i["wav"], i["text"], i.get("sha256")) for i in a["items"]]
ib = [(i["wav"], i["text"], i.get("sha256")) for i in b["items"]]
print("A audio_root", a.get("audio_root"), "items", len(ia), "sha", a.get("sha256"))
print("B audio_root", b.get("audio_root"), "items", len(ib), "sha", b.get("sha256"))
print("ITEMS_EQUAL", ia == ib)
if ia != ib:
    sa = set(ia)
    sb = set(ib)
    print("ONLY_A", len(sa - sb), "ONLY_B", len(sb - sa))
