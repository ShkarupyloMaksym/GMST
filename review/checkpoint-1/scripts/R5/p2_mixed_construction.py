"""R5 probe 2: do the synthetic `mixed` clips measure what they are named for?
(a) inter: gap lengths vs the endpointer silence the eval's gmst-stream uses (min_silence_ms=500)
    and the Config default.
(b) intra: the audio is cut at len(A)//2 samples but the reference is cut at len(words)//2 words.
    Using tiny word timestamps on A (language pinned), count how many words actually precede the
    audio cut, and whether a word straddles it.
Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run python review/checkpoint-1/scripts/R5/p2_mixed_construction.py
"""
import json
from collections import Counter
from pathlib import Path

import soundfile as sf
from gmst.config import Config

D = Path("eval/results/data")
mix = [json.loads(l) for l in (D / "mixed.jsonl").read_text().splitlines() if l.strip()]
pure = {}
for name in ("en", "uk"):
    for l in (D / f"{name}.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l); pure[(name, r["text"].strip())] = r

inter = [m for m in mix if m["kind"] == "inter"]
gaps = Counter(round((m["spans"][1]["t0"] - m["spans"][0]["t1"]) * 1000) for m in inter)
print("Config().min_silence_ms =", Config().min_silence_ms, "| run_eval gmst-stream uses 500")
print("inter gaps (ms -> clips):", dict(sorted(gaps.items())),
      "| gaps < 500 ms:", sum(v for k, v in gaps.items() if k < 500), "of", len(inter))

from faster_whisper import WhisperModel
model = WhisperModel("tiny", device="cpu", compute_type="int8")
intra = [m for m in mix if m["kind"] == "intra"]
off_by = []
straddle = 0
for m in intra:
    h, b, t = m["spans"]
    lang = h["lang"]
    A = pure[(lang, (h["text"] + " " + t["text"]).strip())]
    a, sr = sf.read(D / A["wav"], dtype="float32")
    cut_s = (len(a) // 2) / sr
    segs, _ = model.transcribe(a, language=lang, word_timestamps=True)
    words = [w for s in segs for w in s.words]
    before = sum(1 for w in words if w.end <= cut_s)
    st = any(w.start < cut_s < w.end for w in words)
    straddle += st
    ref_head = len(h["text"].split())
    off_by.append(before + (1 if st else 0) - ref_head if False else before - ref_head)
    print(f"{m['id']} lang={lang} ref_words={len(A['text'].split())} ref_head={ref_head} "
          f"hyp_words_before_cut={before} straddles={st}")
print("head-word count mismatch (hyp words fully before cut - ref head words):", Counter(off_by))
print(f"clips where a word straddles the cut: {straddle}/{len(intra)}")
print("mean inserted-B duration s:", round(sum(m['spans'][1]['t1']-m['spans'][1]['t0'] for m in intra)/len(intra),2))
