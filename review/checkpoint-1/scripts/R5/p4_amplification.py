"""R5 probe 4: is bench's `amplification = RTF_batch x (max_buffer_seconds / 1 s)` the per-update
cost LocalAgreement-2 actually pays? Whisper pads every call to a 30 s window, so a short buffer is
not proportionally cheaper; stream also pays a detect_language pass per utterance.
Measures tiny (faster_whisper, CPU int8) on a 60 s clip spliced from eval uk clips (language pinned
so LID mode does not enter), then per-call wall time on buffers of 1..15 s.
Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run python review/checkpoint-1/scripts/R5/p4_amplification.py
"""
import json, statistics, time
from dataclasses import replace
from pathlib import Path

import numpy as np
import soundfile as sf
from gmst.bench import UPDATE_INTERVAL_S
from gmst.config import Config
from gmst.transcribe.backends import load_engine

D = Path("eval/results/data")
rows = [json.loads(l) for l in (D / "uk.jsonl").read_text().splitlines() if l.strip()]
audio = np.concatenate([sf.read(D / r["wav"], dtype="float32")[0] for r in rows])[: 60 * 16000]
cfg = replace(Config(), model_size="tiny", compute_device="cpu", compute_type="int8")
eng = load_engine(cfg, per_segment_lid=False, word_timestamps=False)
eng.transcribe(audio[:16000 * 5], language="uk")  # warm-up (bench does not do this)

t = time.monotonic(); eng.transcribe(audio, language="uk"); rtf = (time.monotonic() - t) / 60
print(f"batch RTF on 60 s (bench's quantity): {rtf:.4f}; bench amplification = RTF x "
      f"{cfg.max_buffer_seconds}/{UPDATE_INTERVAL_S} = {rtf * cfg.max_buffer_seconds / UPDATE_INTERVAL_S:.3f}")
print("buffer_s  median_call_s  RTF_batch*buffer_s  ratio  (per-update load = call_s / update_interval)")
for b in (1, 2, 4, 8, 15):
    ts = []
    for k in range(5):
        seg = audio[k * 16000 * 3 : k * 16000 * 3 + b * 16000]
        t = time.monotonic(); eng.transcribe(seg, language="uk"); ts.append(time.monotonic() - t)
    med = statistics.median(ts)
    print(f"{b:>8}  {med:>13.3f}  {rtf * b:>18.3f}  {med / (rtf * b):>5.1f}")
ts = []
for k in range(5):
    seg = audio[k * 16000 * 3 : k * 16000 * 3 + 3 * 16000]
    t = time.monotonic(); eng.detect_language(seg); ts.append(time.monotonic() - t)
print(f"detect_language on 3 s: median {statistics.median(ts):.3f} s (not in bench's amplification)")
