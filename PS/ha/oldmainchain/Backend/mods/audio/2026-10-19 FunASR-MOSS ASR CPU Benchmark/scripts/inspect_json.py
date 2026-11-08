# -*- coding: utf-8 -*-
import json
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
print("TOP_KEYS", list(d.keys()))
for k, v in d.items():
    if isinstance(v, dict):
        print("DICT", k, list(v.keys()))
    else:
        print("VAL", k, repr(v)[:120])
