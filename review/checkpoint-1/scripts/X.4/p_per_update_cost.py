"""X.4 (EVID-04): per-update decode cost and LID cost, large-v2 / large-v3, CPU int8.

Extends R5's scripts/R5/p4_amplification.py: two large models instead of tiny, buffers
2/4/8/15 s (not 1), 10 repetitions each after 2 warm-up calls (not 5), median AND p90,
detect_language on 3 s (10 reps, median+p90). Uses eval/results/data/en speech (not uk).

Amended 2026-09-28 (F.17 two-pass): also times the final pass — one whole-utterance
`transcribe` + one `detect_language` on it — for utterances of 2/5/10/15 s, median of 5
after a warm-up, per model. This is the "final text" latency after an utterance ends,
reported next to the per-update cost.

Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.4/p_per_update_cost.py
"""
import json
import os
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf

from gmst.bench import UPDATE_INTERVAL_S
from gmst.config import Config
from gmst.transcribe.backends import load_engine

D = Path("eval/results/data")
rows = [json.loads(l) for l in (D / "en.jsonl").read_text().splitlines() if l.strip()]

# Build >=60 s of concatenated en speech, manifest order (first N clips), and record which.
used = []
chunks = []
total = 0
for r in rows:
    a, sr = sf.read(D / r["wav"], dtype="float32")
    assert sr == 16000, sr
    chunks.append(a)
    used.append(r["wav"])
    total += len(a)
    if total >= 60 * 16000:
        break
audio = np.concatenate(chunks)[: 60 * 16000]

Path("review/checkpoint-1/scripts/X.4/clips.txt").write_text(
    "\n".join(used) + "\n" + f"# concatenated en clips, first {len(used)} of manifest order, "
    f"total {len(audio) / 16000:.1f}s (>=60s target), from eval/results/data/en.jsonl\n"
)

print(f"nproc={os.cpu_count()}  OMP_NUM_THREADS={os.environ.get('OMP_NUM_THREADS')}  "
      f"cpu_threads param passed to WhisperModel: none (default/auto)")

def median_p90(ts):
    ts = sorted(ts)
    med = statistics.median(ts)
    # p90 via nearest-rank on sorted list
    idx = min(len(ts) - 1, int(round(0.9 * (len(ts) - 1))))
    return med, ts[idx]

models = sys.argv[1:] or ["large-v2", "large-v3"]
for model_size in models:
    print(f"\n=== model_size={model_size}  compute_device=cpu  compute_type=int8 ===")
    cfg = replace(Config(), model_size=model_size, compute_device="cpu", compute_type="int8")
    t0 = time.monotonic()
    eng = load_engine(cfg, per_segment_lid=False, word_timestamps=False)
    print(f"load time: {time.monotonic() - t0:.2f} s")

    # 2 warm-up calls (per instructions), using a representative buffer.
    for _ in range(2):
        eng.transcribe(audio[: 4 * 16000], language="en")

    print("buffer_s  median_s  p90_s  (n=10, after 2 warm-ups)")
    per_update = {}
    for b in (2, 4, 8, 15):
        ts = []
        for k in range(10):
            start = (k * 3 * 16000) % (len(audio) - b * 16000)
            seg = audio[start : start + b * 16000]
            t = time.monotonic()
            eng.transcribe(seg, language="en")
            ts.append(time.monotonic() - t)
        med, p90 = median_p90(ts)
        per_update[b] = (med, p90)
        print(f"{b:>8}  {med:>8.3f}  {p90:>6.3f}")

    # detect_language on 3 s, 10 reps after 2 warm-ups
    for _ in range(2):
        eng.detect_language(audio[: 3 * 16000])
    ts = []
    for k in range(10):
        start = (k * 3 * 16000) % (len(audio) - 3 * 16000)
        seg = audio[start : start + 3 * 16000]
        t = time.monotonic()
        eng.detect_language(seg)
        ts.append(time.monotonic() - t)
    lid_med, lid_p90 = median_p90(ts)
    print(f"detect_language(3s): median {lid_med:.3f} s  p90 {lid_p90:.3f} s")

    print(f"\nEVID-04 rule check: (wall at 4s update + LID(3s)) <= 1.0 s -> "
          f"{per_update[4][0]:.3f} + {lid_med:.3f} = {per_update[4][0] + lid_med:.3f} s "
          f"-> {'HOLDS' if per_update[4][0] + lid_med <= 1.0 else 'FAILS'}")

    # Amended: final-pass latency (one whole-utterance transcribe + one detect_language),
    # utterances of 2/5/10/15 s, median of 5 after a warm-up.
    print("\nfinal-pass (transcribe + detect_language), median of 5 after 1 warm-up:")
    warm_len = 5
    eng.transcribe(audio[: warm_len * 16000], language="en")
    eng.detect_language(audio[: warm_len * 16000])
    print("utt_s  median_transcribe_s  median_lid_s  median_total_s")
    for u in (2, 5, 10, 15):
        tts, lts = [], []
        for k in range(5):
            start = (k * 3 * 16000) % (len(audio) - u * 16000)
            seg = audio[start : start + u * 16000]
            t = time.monotonic(); eng.transcribe(seg, language="en"); tts.append(time.monotonic() - t)
            t = time.monotonic(); eng.detect_language(seg); lts.append(time.monotonic() - t)
        mt, ml = statistics.median(tts), statistics.median(lts)
        print(f"{u:>5}  {mt:>18.3f}  {ml:>12.3f}  {mt + ml:>14.3f}")

    del eng
