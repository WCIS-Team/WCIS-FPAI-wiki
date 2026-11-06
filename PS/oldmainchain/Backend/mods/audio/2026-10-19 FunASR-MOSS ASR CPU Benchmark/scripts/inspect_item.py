# -*- coding: utf-8 -*-
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
print("ACC", d["accuracy"])
print("NORM", d["meta"]["normalization"])
for p in d["per_item"][:6]:
    print("IDX", p["idx"], p["wav"])
    print("  ref :", p["ref"])
    print("  hyp :", p["hyp"])
    print("  s/d/i:", p.get("S"), p.get("D"), p.get("I"), "cer", p.get("cer"), "wer", p.get("wer"))
