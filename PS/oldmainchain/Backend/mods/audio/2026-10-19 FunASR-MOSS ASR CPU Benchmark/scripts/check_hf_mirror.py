# -*- coding: utf-8 -*-
"""List files of the alextomcat paraformer mirror on HF."""
from huggingface_hub import HfApi

api = HfApi()
repo = "alextomcat/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
try:
    items = list(api.list_repo_tree(repo, repo_type="model", recursive=True))
    print("MIRROR_EXISTS", len(items))
    for i in items:
        print("FILE", i.path, getattr(i, "size", ""))
except Exception as e:
    print("MIRROR_FAIL", repr(e))
