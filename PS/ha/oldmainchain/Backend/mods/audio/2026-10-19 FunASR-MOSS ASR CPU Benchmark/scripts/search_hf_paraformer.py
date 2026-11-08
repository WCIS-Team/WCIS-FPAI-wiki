# -*- coding: utf-8 -*-
"""Search HF for paraformer-large-vad-punc mirror repos."""
from huggingface_hub import HfApi

api = HfApi()
for q in ["paraformer-large-vad-punc", "speech_paraformer-large-vad-punc"]:
    try:
        res = api.list_models(search=q, limit=20)
        print("QUERY", q)
        for m in res:
            print("MODEL", m.id, m.downloads, m.lastModified)
    except Exception as e:
        print("QUERY_FAIL", q, repr(e))
