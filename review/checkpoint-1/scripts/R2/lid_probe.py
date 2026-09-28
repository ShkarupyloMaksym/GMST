"""R2 probe: what languages does GMST's LID actually pick on Ukrainian speech?

Run from the repo root:
    HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R2/lid_probe.py tiny
    HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R2/lid_probe.py small

Parts
  A  detect_language on each uk clip (full clip, and the first 1.0 s = what run_stream's first
     decode hands the detector at min_chunk_seconds=1.0), then resolve_language with
     prev_lang None / "en" / "uk". Counts labels outside {en, uk}.
  B  batch path: FasterWhisperEngine(per_segment_lid=True).transcribe(language=None) vs raw
     WhisperModel.transcribe(language=None). Is the *text* just the raw autodetect decode,
     with GMST's LID only relabelling it?
  C  stream path: run_stream(language=None) on a "meeting" of N uk clips joined by 1.2 s of
     silence, with detect_language instrumented. Which languages were handed to transcribe()?
"""

from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

from gmst.audio.file_source import decode_file
from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine
from gmst.transcribe.lid import resolve_language

sys.path.insert(0, str(Path("tests").resolve()))
from fakes import ListSource  # noqa: E402

size = sys.argv[1] if len(sys.argv) > 1 else "tiny"
n_stream = int(sys.argv[2]) if len(sys.argv) > 2 else 12
skip_b = len(sys.argv) > 3 and sys.argv[3] == "skipB"  # small under concurrency: time budget
DATA = Path("eval/results/data")
rows = [json.loads(line) for line in (DATA / "uk.jsonl").read_text().splitlines() if line]
clips = [(r["id"], decode_file(DATA / r["wav"])) for r in rows]

cfg = Config(model_size=size, compute_type="int8", word_timestamps=False)
t_load = time.monotonic()
eng = FasterWhisperEngine(cfg, per_segment_lid=True, word_timestamps=False)
print(f"model={size} loaded in {time.monotonic() - t_load:.1f}s; n_clips={len(clips)}")
KW = {"threshold": cfg.lid_threshold, "tiebreak_margin": cfg.lid_tiebreak_margin}

# ---- A ---------------------------------------------------------------------------------------
print("\n== A: detector labels on uk clips ==")
for name, cut in (("full", None), ("first1s", SAMPLE_RATE)):
    raw_c, res = collections.Counter(), {p: collections.Counter() for p in ("None", "en", "uk")}
    examples = []
    for cid, a in clips:
        x = a if cut is None else a[:cut]
        lang, prob, allp = eng._detect_full(x)
        raw_c[lang] += 1
        for p in res:
            r, _ = resolve_language(lang, prob, allp, prev_lang=None if p == "None" else p, **KW)
            res[p][r] += 1
        if lang not in ("uk",) and len(examples) < 6:
            top3 = sorted(allp, key=lambda kv: kv[1], reverse=True)[:3]
            examples.append((cid, [(k, round(v, 3)) for k, v in top3]))
    n = len(clips)
    print(f"[{name}] raw top-1: {dict(raw_c.most_common())}")
    for p, c in res.items():
        off = sum(v for k, v in c.items() if k not in ("en", "uk"))
        print(f"[{name}] resolved prev={p}: {dict(c.most_common())}  -> not en/uk: {off}/{n}")
    for e in examples:
        print(f"[{name}]   e.g. {e[0]} top3={e[1]}")

# ---- B ---------------------------------------------------------------------------------------
print("\n== B: batch per-segment LID relabels, does not re-decode ==")
same = diff_label = 0
shown = 0
for cid, a in ([] if skip_b else clips):
    segs = eng.transcribe(a, language=None)
    raw, info = eng._model.transcribe(a, language=None, multilingual=False, vad_filter=False,
                                      word_timestamps=False,
                                      language_detection_threshold=cfg.lid_threshold)
    raw_text = "".join(s.text for s in raw)
    gm_text = "".join(s.text for s in segs)
    same += raw_text == gm_text
    labels = [s.language for s in segs]
    if any(lab != info.language for lab in labels):
        diff_label += 1
        if shown < 4:
            shown += 1
            print(f"  {cid}: decoded-as={info.language} gmst-labels={labels} text={gm_text[:60]!r}")
print(f"text identical to raw autodetect decode: {same}/{len(clips)}; "
      f"clips where GMST label != language the text was decoded in: {diff_label}/{len(clips)}")

# ---- C ---------------------------------------------------------------------------------------
print(f"\n== C: run_stream(language=None) on a meeting of {n_stream} uk clips ==")
from gmst.pipeline.stream import run_stream  # noqa: E402

gap = np.zeros(int(1.2 * SAMPLE_RATE), dtype=np.float32)
meeting = np.concatenate([np.concatenate([a, gap]) for _, a in clips[:n_stream]])
blk = SAMPLE_RATE // 10
blocks = [meeting[i : i + blk] for i in range(0, len(meeting), blk)]

lid_calls = []
orig_detect = eng.detect_language


def spy_detect(audio, *, prev_lang=None):
    lang, prob, allp = eng._detect_full(audio)
    out = orig_detect(audio, prev_lang=prev_lang)
    top = sorted(allp, key=lambda kv: kv[1], reverse=True)[:2]
    print("  lid", len(audio) / SAMPLE_RATE, prev_lang, lang, round(prob, 3), out[0], flush=True)
    lid_calls.append((round(len(audio) / SAMPLE_RATE, 2), prev_lang, lang, round(prob, 3),
                      [(k, round(v, 2)) for k, v in top], out[0]))
    return out


eng.detect_language = spy_detect


class _Sink:
    def __init__(self):
        self.finals = []

    def emit(self, s):
        if s.is_final:
            self.finals.append(s)

    def close(self):
        pass


sink = _Sink()
scfg = Config(model_size=size, compute_type="int8", word_timestamps=True)
t0 = time.monotonic()
run_stream(scfg, ListSource(blocks), eng, sink, language=None)
print(f"stream wall {time.monotonic() - t0:.1f}s for {len(meeting) / SAMPLE_RATE:.1f}s audio")
for c in lid_calls:
    print(f"  LID on {c[0]:5.2f}s prev={c[1]!s:4} raw={c[2]}@{c[3]} top2={c[4]} -> used {c[5]}")
used = collections.Counter(c[5] for c in lid_calls)
print(f"languages handed to transcribe(): {dict(used)}; "
      f"not en/uk: {sum(v for k, v in used.items() if k not in ('en', 'uk'))}/{len(lid_calls)}")
emitted = collections.Counter(s.language for s in sink.finals)
print(f"final segments by language: {dict(emitted)}")
for s in sink.finals:
    if s.language not in ("uk",):
        print(f"  [{s.language}] {s.start:6.2f}-{s.end:6.2f} {s.text[:70]!r}")
