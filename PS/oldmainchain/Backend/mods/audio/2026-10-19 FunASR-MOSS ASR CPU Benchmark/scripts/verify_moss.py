# -*- coding: utf-8 -*-
"""Verify MOSS package imports and required inference helpers exist."""
import importlib

mod = importlib.import_module("moss_transcribe_diarize")
print("MOSS_PKG", getattr(mod, "__version__", "n/a"))

from moss_transcribe_diarize.inference_utils import (  # noqa
    build_transcription_messages,
    generate_transcription,
    resolve_device,
)
print("MOSS_IMPORT_OK")
