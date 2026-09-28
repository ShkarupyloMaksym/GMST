"""EVID-01 (X.1c): stream vs batch corpus WER after F.15, on X.1's clips and on unseen clips.

Copy of scripts/X.1/run_wer.py (itself extending F.8's probe) with two additions only:
  * a row-offset option so the same script can select manifest rows [offset:offset+20) instead of
    always the first 20 (rows 0-19 = X.1's original clips = set "a"; rows 20-39 = unseen = set "b")
  * a --stream-runs N option to repeat the stream decode N times per set (F.14 left uk streaming
    non-deterministic; report every run)
Everything else (batch/stream methodology, corpus WER pooling, CountingLA contradiction counting)
is unchanged from scripts/X.1/run_wer.py. Only en/uk are supported here (no mixed set -- not asked
for by this node's brief).

Run:
  HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1c/run_wer.py <small|large-v2> \
      <stream_runs> <offset:tag> [<offset:tag> ...]

e.g. small run on both sets, stream x2 each:
  run_wer.py small 2 0:a 20:b
large-v2 run on set b only, stream x1:
  run_wer.py large-v2 1 20:b

Writes review/checkpoint-1/scripts/X.1c/<model>_<tag>_results.json per (offset,tag) and a combined
review/checkpoint-1/scripts/X.1c/<model>_all_results.json at the end.
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
from gmst.reconcile import LocalAgreement  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402

SETS = ["en", "uk"]
LANG_OF_SET = {"en": "en", "uk": "uk"}

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


def load_clips(setname: str, offset: int, n: int = 20):
    rows = [
        json.loads(x)
        for x in (ROOT / f"eval/results/data/{setname}.jsonl").read_text().splitlines()
    ]
    rows = rows[offset : offset + n]
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
        "full_out": out,
        "full_ref": ref,
    }


def main():
    size = sys.argv[1] if len(sys.argv) > 1 else "small"
    stream_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    offset_tags = sys.argv[3:] if len(sys.argv) > 3 else ["0:a"]
    offset_tags = [tuple(x.split(":")) for x in offset_tags]
    offset_tags = [(int(o), t) for o, t in offset_tags]
    print(f"=== model={size} stream_runs={stream_runs} offset_tags={offset_tags} ===", flush=True)

    cfg = Config(model_size=size, compute_device="cpu", compute_type="int8")
    t0 = time.monotonic()
    engine = load_engine(cfg)  # shipped default: per_segment_lid=True
    print(f"engine loaded in {time.monotonic() - t0:.1f}s", flush=True)

    combined = {"model": size, "stream_runs": stream_runs, "tags": {}}

    for offset, tag in offset_tags:
        results = {"model": size, "offset": offset, "tag": tag, "sets": {}}
        for setname in SETS:
            clips = load_clips(setname, offset)
            print(f"--- tag={tag} offset={offset} {setname}: {len(clips)} clips, "
                  f"{sum(len(c) for _, c, _ in clips) / SAMPLE_RATE:.1f}s audio ---", flush=True)

            b = run_batch(setname, clips, cfg, engine)
            print(f"[{size}/{tag}/{setname}] batch  WER={b['wer']:.4f} "
                  f"(edits={b['edits']} ref_words={b['ref_words']}) {b['elapsed_s']:.1f}s", flush=True)

            stream_reps = []
            for rep in range(stream_runs):
                s = run_stream_set(setname, clips, cfg, engine)
                print(f"[{size}/{tag}/{setname}] stream rep={rep} WER={s['wer']:.4f} "
                      f"(edits={s['edits']} ref_words={s['ref_words']}) {s['elapsed_s']:.1f}s "
                      f"decodes={s['decodes']} "
                      f"contradicted={s['counts']['contradicted']}/{s['counts']['pushes']}",
                      flush=True)
                stream_reps.append(s)

            results["sets"][setname] = {"batch": b, "stream_reps": stream_reps}
            out_path = ROOT / f"review/checkpoint-1/scripts/X.1c/{size}_{tag}_results.json"
            out_path.write_text(json.dumps(results, indent=2, default=str))
            print(f"  (partial results written to {out_path})", flush=True)

        combined["tags"][tag] = results
        combined_path = ROOT / f"review/checkpoint-1/scripts/X.1c/{size}_all_results.json"
        combined_path.write_text(json.dumps(combined, indent=2, default=str))

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
