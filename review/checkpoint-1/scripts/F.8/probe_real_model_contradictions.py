# Copy of scripts/R1/probe_real_model_contradictions.py adapted to the F.8 push(hypothesis, spans) signature; logic unchanged.
"""R1 probe: does a real Whisper model trip the contradiction path after a trim, and how much
text does the stream pipeline lose because of it?

Run: HF_HUB_OFFLINE=1 timeout 580 uv run python review/checkpoint-1/scripts/R1/probe_real_model_contradictions.py [tiny|small] [n_clips] [noprompt] [backoff=S]

Builds one stream from N LibriSpeech clips in eval/results/data/en (read-only), 1.5 s of silence
between clips, fed as 100 ms blocks through the real `run_stream` with the shipped defaults
(silero VAD, min_chunk 1.0, overlap 0.5, ...), language pinned to en. LocalAgreement is wrapped to
count contradicted pushes and words dropped by `flush()` on a contradiction. Output is scored
against the references with gmst.metrics.word_error_rate, next to a per-clip batch decode of the
same engine as the control.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import gmst.pipeline.stream as stream_mod  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.metrics import word_error_rate  # noqa: E402
from gmst.reconcile import LocalAgreement  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402

EXAMPLES: list = []
COUNTS = {"pushes": 0, "contradicted": 0, "flush_dropped_words": 0, "flushes_dropping": 0}


class CountingLA(LocalAgreement):
    def push(self, hypothesis, spans=None):
        out = super().push(hypothesis, spans)
        COUNTS["pushes"] += 1
        if self.contradicted:
            COUNTS["contradicted"] += 1
            if len(EXAMPLES) < 6:
                EXAMPLES.append((self._committed[-3:], hypothesis[:5]))
        return out

    def flush(self):
        a = self._align(self._prev, self._prev_spans)
        if a < 0 and self._prev:
            COUNTS["flushes_dropping"] += 1
            COUNTS["flush_dropped_words"] += len(self._prev)
        return super().flush()


class RecSink:
    def __init__(self):
        self.segs = []

    def emit(self, seg):
        self.segs.append(seg)

    def close(self):
        pass


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "small"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    opts = sys.argv[3:]  # attribution knobs: "noprompt", "backoff=<seconds>"
    for o in opts:
        if o.startswith("backoff="):
            import gmst.segment.endpointer as ep_mod
            ep_mod._TRIM_BACKOFF_S = float(o.split("=")[1])
    print("opts:", opts)
    rows = [json.loads(x) for x in (ROOT / "eval/results/data/en.jsonl").read_text().splitlines()]
    rows = [r for r in rows if len(r["text"].split()) >= 15][:n]
    clips = []
    for r in rows:
        a, sr = sf.read(ROOT / "eval/results/data" / r["wav"], dtype="float32")
        assert sr == SAMPLE_RATE and a.ndim == 1, (sr, a.shape)
        clips.append(a)
    gap = np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([x for c in clips for x in (c, gap)])
    ref = " ".join(r["text"] for r in rows)
    print(f"model={size} clips={len(rows)} audio={len(audio) / SAMPLE_RATE:.1f}s "
          f"ref_words={len(ref.split())}")

    cfg = Config(model_size=size, compute_device="cpu", compute_type="int8")
    print("cfg:", {k: getattr(cfg, k) for k in (
        "vad_backend", "min_chunk_seconds", "min_silence_ms", "max_buffer_seconds",
        "max_unconfirmed_seconds", "overlap_seconds", "word_timestamps")})
    engine = load_engine(cfg, per_segment_lid=False)

    t = time.monotonic()
    batch = " ".join(
        " ".join(s.text for s in engine.transcribe(c, language="en")) for c in clips
    )
    print(f"batch per-clip WER = {word_error_rate(ref, batch):.3f}  ({time.monotonic() - t:.0f}s)")

    stream_mod.LocalAgreement = CountingLA
    if "noprompt" in opts:
        real = engine.transcribe
        engine.transcribe = lambda audio, *, language=None, prompt=None: real(
            audio, language=language, prompt=None)
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    sink = RecSink()
    t = time.monotonic()
    stats = stream_mod.run_stream(cfg, ListSource(blocks), engine, sink, language="en")
    out = " ".join(s.text for s in sink.segs if s.is_final)
    print(f"stream WER = {word_error_rate(ref, out):.3f}  ({time.monotonic() - t:.0f}s) "
          f"decodes={stats.decodes} committed_words={stats.committed_words} "
          f"out_words={len(out.split())}")
    print("counts:", COUNTS)
    for anchor, head in EXAMPLES:
        print("  contradicted: committed tail", anchor, "| hyp head", head)
    print("\nREF:   ", ref.lower())
    print("\nSTREAM:", out)


if __name__ == "__main__":
    main()
