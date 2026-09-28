"""R1 probe: what the prompt the stream pipeline builds looks like, in Whisper tokens.

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R1/probe_prompt_tokens.py

Rebuilds the prompt exactly as `src/gmst/pipeline/stream.py:118` does
(`" ".join(committed[-_PROMPT_WORDS:])[-_PROMPT_CHARS:]`) from reference text in
eval/results/data/{en,uk}.jsonl (read-only), and counts tokens with the cached `tiny` tokenizer
(multilingual Whisper vocabulary, shared with large-v2/v3). faster-whisper keeps only the last
`max_length // 2 - 1` = 223 prompt tokens.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from tokenizers import Tokenizer

from gmst.pipeline.stream import _PROMPT_CHARS, _PROMPT_WORDS

ROOT = Path(__file__).resolve().parents[4]
tok_path = glob.glob(os.path.expanduser(
    "~/.cache/huggingface/hub/models--Systran--faster-whisper-tiny/snapshots/*/tokenizer.json"))[0]
tok = Tokenizer.from_file(tok_path)

for lang in ("en", "uk"):
    rows = [json.loads(x) for x in (ROOT / f"eval/results/data/{lang}.jsonl").read_text().splitlines()]
    committed = " ".join(r["text"].lower() for r in rows).split()[:2000]
    prompt = " ".join(committed[-_PROMPT_WORDS:])[-_PROMPT_CHARS:]
    n = len(tok.encode(" " + prompt, add_special_tokens=False).ids)
    first = prompt.split()[0]
    whole = committed[-len(prompt.split())]
    print(f"{lang}: prompt chars={len(prompt)} words={len(prompt.split())} tokens={n} "
          f"first prompt word={first!r} vs source word={whole!r} (cut mid-word: {first != whole})")
