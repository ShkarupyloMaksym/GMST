"""X.1b.1: is the Ukrainian stream regression (X.1b: 45.45 % vs X.1's 27.27 %) caused by F.14's
prompt change, or run-to-run variation? Runs the X.1 uk stream (same 20 clips, 1.5 s gaps, 100 ms
blocks, shipped defaults, language pinned uk, `small`) with whichever `gmst` is first on
PYTHONPATH, N times, and prints corpus WER, committed words and the full output.

Run (repo root):
  PYTHONPATH=<tree>/src HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1b.1/uk_prompt_ab.py LABEL N
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(1, str(ROOT))  # tests.fakes only; gmst comes from PYTHONPATH first
import gmst  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.metrics import word_errors  # noqa: E402
from gmst.pipeline.stream import run_stream  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402

label, n = sys.argv[1], int(sys.argv[2])
print("gmst from", Path(gmst.__file__).parent)
OFF = int(sys.argv[3]) if len(sys.argv) > 3 else 0
rows = [json.loads(x) for x in (ROOT / "eval/results/data/uk.jsonl").read_text().splitlines()][OFF:OFF + 20]
clips = [sf.read(ROOT / "eval/results/data" / r["wav"], dtype="float32")[0] for r in rows]
gap = np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)
audio = np.concatenate([x for c in clips for x in (c, gap)])
ref = " ".join(r["text"] for r in rows)
cfg = Config(model_size="small", compute_device="cpu", compute_type="int8")
eng = load_engine(cfg, per_segment_lid=False)
blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
for k in range(n):
    class Sink:
        segs: list = []

        def emit(self, s):
            if s.is_final:
                self.segs.append(s)

        def close(self):
            pass

    sink = Sink()
    sink.segs = []
    run_stream(cfg, ListSource(blocks), eng, sink, language="uk")
    out = " ".join(s.text for s in sink.segs)
    e, nref = word_errors(ref, out)
    print(f"[{label} run {k}] WER={e / nref:.4f} edits={e} ref={nref} out_words={len(out.split())}")
    print(f"  OUT: {out}")
