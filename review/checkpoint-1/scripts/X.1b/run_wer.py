"""EVID-01 (X.1): stream vs batch corpus WER after the F.8 re-anchoring fix.

Extends F.8's scripts/F.8/probe_real_model_contradictions.py (itself R1's probe, adapted to the
push(hypothesis, spans) signature) to three sets and pooled corpus WER.

For each of {en, uk, mixed-inter} (first 20 clips of eval/results/data/{en,uk,mixed}.jsonl, mixed
restricted to kind=="inter", clips.txt written before running) runs two decode paths with the
shipped-default engine (faster_whisper, per_segment_lid=True, cfg.lid_languages=("en","uk")):

  * batch  -- en/uk: engine.transcribe(clip, language=<pinned>) per clip (language pinned, as the
    node brief specifies). mixed: gmst.pipeline.batch.transcribe_by_region(clip, cfg, engine) with
    cfg.language=None, i.e. auto per-VAD-region LID -- the real "language not pinned" batch path.
  * stream -- gmst.pipeline.stream.run_stream on the set's 20 clips concatenated with 1.5 s silence
    gaps, fed as 100 ms blocks (R1/F.8 methodology), language pinned for en/uk, language=None (auto
    per-utterance LID) for mixed. LocalAgreement is wrapped (F.8's CountingLA) to count contradicted
    pushes and words a flush() drops on a contradiction.

Corpus WER is pooled with gmst.metrics.word_errors, NOT per-clip means: batch sums (edits,
ref_words) over the 20 individual clip decodes; stream computes word_errors once on the whole
concatenated reference vs the whole concatenated final output (a single corpus-level edit distance
over the same audio the ref belongs to -- there is no other way to attribute stream output back to
clip boundaries once LocalAgreement has committed across a silence gap).

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1b/run_wer.py <small|large-v2> [sets...]
Writes review/checkpoint-1/scripts/X.1b/<model>_results.json and prints a log to stdout.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import gmst.pipeline.stream as stream_mod  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.metrics import word_errors  # noqa: E402
from gmst.pipeline.batch import transcribe_by_region  # noqa: E402
from gmst.reconcile import LocalAgreement  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402

SETS = ["en", "uk", "mixed"]
LANG_OF_SET = {"en": "en", "uk": "uk", "mixed": None}  # mixed = auto LID (not pinned)

COUNTS: dict = {}
EXAMPLES: dict = {}


class CountingLA(LocalAgreement):
    def push(self, hypothesis, spans=None):
        out = super().push(hypothesis, spans)
        COUNTS["pushes"] += 1
        if self.contradicted:
            COUNTS["contradicted"] += 1
            if len(EXAMPLES.setdefault("contradictions", [])) < 6:
                EXAMPLES["contradictions"].append(
                    {"committed_tail": self._committed[-3:], "hyp_head": hypothesis[:5]}
                )
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


def load_clips(setname: str):
    rows = [
        json.loads(x)
        for x in (ROOT / f"eval/results/data/{setname}.jsonl").read_text().splitlines()
    ]
    if setname == "mixed":
        rows = [r for r in rows if r["kind"] == "inter"][:20]
    else:
        rows = rows[:20]
    clips = []
    for r in rows:
        a, sr = sf.read(ROOT / "eval/results/data" / r["wav"], dtype="float32")
        assert sr == SAMPLE_RATE and a.ndim == 1, (sr, a.shape)
        clips.append((r["id"], a, r["text"]))
    return clips


def run_batch(setname, clips, cfg, engine):
    edits_total, ref_total = 0, 0
    per_clip = []
    t0 = time.monotonic()
    for cid, audio, ref in clips:
        if setname == "mixed":
            segs = transcribe_by_region(audio, cfg, engine)
            hyp = " ".join(s.text for s in segs)
        else:
            lang = LANG_OF_SET[setname]
            segs = engine.transcribe(audio, language=lang)
            hyp = " ".join(s.text for s in segs)
        e, n = word_errors(ref, hyp)
        edits_total += e
        ref_total += n
        per_clip.append({"id": cid, "edits": e, "ref_words": n, "hyp": hyp})
    elapsed = time.monotonic() - t0
    wer = edits_total / ref_total if ref_total else float("nan")
    return {
        "mode": "batch",
        "edits": edits_total,
        "ref_words": ref_total,
        "wer": wer,
        "elapsed_s": elapsed,
        "per_clip": per_clip,
    }


def run_stream_set(setname, clips, cfg, engine):
    gap = np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([x for _, c, _ in clips for x in (c, gap)])
    ref = " ".join(text for _, _, text in clips)
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]

    COUNTS.clear()
    COUNTS.update({"pushes": 0, "contradicted": 0, "flush_dropped_words": 0, "flushes_dropping": 0})
    EXAMPLES.clear()

    stream_mod.LocalAgreement = CountingLA
    sink = RecSink()
    lang = LANG_OF_SET[setname]
    t0 = time.monotonic()
    stats = stream_mod.run_stream(cfg, ListSource(blocks), engine, sink, language=lang)
    elapsed = time.monotonic() - t0
    out = " ".join(s.text for s in sink.segs if s.is_final)
    e, n = word_errors(ref, out)
    wer = e / n if n else float("nan")
    sample_segs = [
        {"text": s.text, "start": s.start, "end": s.end, "lang": s.language, "is_final": s.is_final}
        for s in sink.segs[:5]
    ]
    return {
        "mode": "stream",
        "edits": e,
        "ref_words": n,
        "wer": wer,
        "elapsed_s": elapsed,
        "audio_s": len(audio) / SAMPLE_RATE,
        "decodes": stats.decodes,
        "committed_words": stats.committed_words,
        "out_words": len(out.split()),
        "counts": dict(COUNTS),
        "examples": dict(EXAMPLES),
        "sample_segments": sample_segs,
        "ref_preview": ref[:300],
        "out_preview": out[:300],
    }


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "small"
    sets = sys.argv[2:] if len(sys.argv) > 2 else SETS
    print(f"=== model={size} sets={sets} ===", flush=True)

    cfg = Config(model_size=size, compute_device="cpu", compute_type="int8")
    t0 = time.monotonic()
    engine = load_engine(cfg)  # shipped default: per_segment_lid=True
    print(f"engine loaded in {time.monotonic() - t0:.1f}s", flush=True)

    results = {"model": size, "sets": {}}
    for setname in sets:
        clips = load_clips(setname)
        print(f"--- {setname}: {len(clips)} clips, "
              f"{sum(len(c) for _, c, _ in clips) / SAMPLE_RATE:.1f}s audio ---", flush=True)

        t0 = time.monotonic()
        b = run_batch(setname, clips, cfg, engine)
        print(f"[{size}/{setname}] batch  WER={b['wer']:.4f} "
              f"(edits={b['edits']} ref_words={b['ref_words']}) {b['elapsed_s']:.1f}s", flush=True)

        t0 = time.monotonic()
        s = run_stream_set(setname, clips, cfg, engine)
        print(f"[{size}/{setname}] stream WER={s['wer']:.4f} "
              f"(edits={s['edits']} ref_words={s['ref_words']}) {s['elapsed_s']:.1f}s "
              f"decodes={s['decodes']} contradicted={s['counts']['contradicted']}/{s['counts']['pushes']}",
              flush=True)

        results["sets"][setname] = {"batch": b, "stream": s}
        out_path = ROOT / f"review/checkpoint-1/scripts/X.1b/{size}_results.json"
        out_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"  (partial results written to {out_path})", flush=True)

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
