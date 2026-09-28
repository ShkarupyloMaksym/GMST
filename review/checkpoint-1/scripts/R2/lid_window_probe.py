"""R2 probe: _detect_slice window invariants over random (start, end) incl. timestamps past the
buffer end (Whisper's last segment often reports end > audio length). No model.

    uv run python review/checkpoint-1/scripts/R2/lid_window_probe.py
"""
import random

import numpy as np

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

eng = FasterWhisperEngine.__new__(FasterWhisperEngine)
eng._cfg = Config()


class M:
    def detect_language(self, a):
        M.last = len(a)
        return "uk", 0.9, [("uk", 0.9)]


eng._model = M()
rng = random.Random(0)
bad = []
for _ in range(20000):
    n = rng.randint(1, 40 * SAMPLE_RATE)
    dur = n / SAMPLE_RATE
    s = rng.uniform(-0.1, dur + 1.0)
    e = s + rng.uniform(0, 3.0)
    eng._detect_slice(np.zeros(n, np.float32), s, e, None)
    want = min(n, SAMPLE_RATE // 2)
    if M.last < want:
        bad.append((n, round(s, 3), round(e, 3), M.last))
print(f"cases with window < min(len, 0.5 s): {len(bad)}/20000", bad[:5])
