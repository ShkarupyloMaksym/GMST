"""F.8 debug: trace every push on one LibriSpeech clip with tiny — which words the aligner skips
(text match, time cut, n-gram) and what commits. Finds where the stream loses single words."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import gmst.pipeline.stream as stream_mod  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.reconcile import LocalAgreement  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402


class TraceLA(LocalAgreement):
    def push(self, hypothesis, spans=None):
        anchor, cend = self._committed[-3:], self._committed_end
        h0 = self._align(hypothesis, spans)
        out = super().push(hypothesis, spans)
        sp = [f"{w}@{s:.2f}-{e:.2f}" for w, (s, e) in zip(hypothesis[:6], spans[:6])] if spans else hypothesis[:6]
        print(f"anchor={anchor} end={cend}  skip={h0}  head={sp}\n   -> commit={out[0]} pend={out[1][:4]}")
        return out

    def rebase(self, committed, pending, spans=None):
        print(f"   rebase committed={committed} pending={pending[:3]} spans={[(round(a,2),round(b,2)) for a,b in (spans or [])][:4]}")
        return super().rebase(committed, pending, spans)


rows = [json.loads(x) for x in (ROOT / "eval/results/data/en.jsonl").read_text().splitlines()]
r = [r for r in rows if len(r["text"].split()) >= 15][0]
a, _ = sf.read(ROOT / "eval/results/data" / r["wav"], dtype="float32")
audio = np.concatenate([a, np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)])
print("REF:", r["text"])
cfg = Config(model_size="tiny", compute_device="cpu", compute_type="int8")
eng = load_engine(cfg, per_segment_lid=False)
stream_mod.LocalAgreement = TraceLA
blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]


class S:
    segs: list = []

    def emit(self, s):
        self.segs.append(s)

    def close(self):
        pass


s = S()
stream_mod.run_stream(cfg, ListSource(blocks), eng, s, language="en")
print("OUT:", " ".join(x.text for x in s.segs if x.is_final))
