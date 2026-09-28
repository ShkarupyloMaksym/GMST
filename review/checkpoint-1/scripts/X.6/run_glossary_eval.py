"""X.6 (DECIDE-08): term recall + WER on eval/results/data/terms.jsonl (200 uk-pods clips),
batch, language pinned uk, three glossary conditions, per the pre-registered rule in
review/checkpoint-1/tasks/X.6-glossary-term-recall.md.

Conditions:
  (a) no glossary
  (b) static glossary = 100 most frequent Latin terms in uk-pods_pods_train.json
      text_no_preprocessing (built by build_static_glossary.py) -- via
      gmst.pipeline.batch.transcribe_by_region, one call per clip.
  (c) autogrow only -- glossary_autogrow=True, one Glossary object carried across the 200 clips
      in manifest order, decoded manually with the Glossary API (not transcribe_by_region, which
      would build a fresh Glossary every call and lose the carried state).

Metric: term recall = share of the reference's Latin terms (the `terms` field) that appear in the
hypothesis as the same Latin token, case-insensitive, edge punctuation stripped. Plus corpus WER
(gmst.metrics.word_errors) on the same clips, and decode time per clip.

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.6/run_glossary_eval.py <model_size> [n_clips]
e.g. HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.6/run_glossary_eval.py small 200
"""
from __future__ import annotations

import json
import re
import signal
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from gmst.config import Config
from gmst.glossary import Glossary
from gmst.metrics import word_errors
from gmst.pipeline.batch import transcribe_by_region
from gmst.transcribe.backends import load_engine

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "eval" / "results" / "data"
SCRIPT_DIR = Path(__file__).resolve().parent
_PROMPT_CHARS = 560  # same cap as pipeline/batch.py
CLIP_TIMEOUT_S = 45  # per-clip decode budget; a runaway (hallucinating) decode is recorded as a
                      # timeout, not allowed to stall the whole run -- itself evidence of the
                      # glossary path's cost, per X.6's "report decode time per clip" instruction.


class ClipTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise ClipTimeout


def with_timeout(fn, *args, **kwargs):
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(CLIP_TIMEOUT_S)
    try:
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)


def edge_strip(tok: str) -> str:
    return _EDGE.sub("", tok)


def term_hit(term: str, hyp_text: str) -> bool:
    key = edge_strip(term).casefold()
    for w in hyp_text.split():
        if edge_strip(w).casefold() == key:
            return True
    return False


def load_rows() -> list[dict]:
    rows = [json.loads(line) for line in (DATA / "terms.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows


def load_audio(wav_rel: str) -> np.ndarray:
    a, sr = sf.read(DATA / wav_rel, dtype="float32")
    assert sr == 16000, sr
    if a.ndim > 1:
        a = a.mean(axis=1).astype(np.float32)
    return a


def hyp_text_of(segs) -> str:
    return " ".join(s.text.strip() for s in segs).strip()


def run_condition_ab(model_size: str, rows: list[dict], engine, glossary_terms: tuple[str, ...]) -> list[dict]:
    cfg = Config(language="uk", model_size=model_size, compute_device="cpu", compute_type="int8",
                 glossary=glossary_terms, glossary_autogrow=False)
    out = []
    for i, r in enumerate(rows):
        audio = load_audio(r["wav"])
        t0 = time.monotonic()
        try:
            segs = with_timeout(transcribe_by_region, audio, cfg, engine)
            hyp = hyp_text_of(segs)
            timed_out = False
        except ClipTimeout:
            hyp = ""
            timed_out = True
        dt = time.monotonic() - t0
        out.append({"id": r["id"], "hyp": hyp, "decode_s": dt, "timed_out": timed_out})
        if timed_out:
            print(f"  [{i+1}/{len(rows)}] id={r['id']} TIMED OUT after {dt:.1f}s", flush=True)
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(rows)}] last decode {dt:.2f}s", flush=True)
    return out


def run_condition_c(model_size: str, rows: list[dict], engine) -> list[dict]:
    cfg = Config(language="uk", model_size=model_size, compute_device="cpu", compute_type="int8")
    glossary = Glossary((), autogrow=True)  # one object, carried across all clips, manifest order
    out = []
    for i, r in enumerate(rows):
        audio = load_audio(r["wav"])
        prompt = glossary.prompt(None, max_chars=_PROMPT_CHARS)
        hotwords = glossary.hotwords()
        t0 = time.monotonic()
        try:
            segs = with_timeout(engine.transcribe, audio, language="uk", prompt=prompt, hotwords=hotwords)
            hyp = hyp_text_of(segs)
            timed_out = False
            for s in segs:
                glossary.observe(s.text, lang="uk")
        except ClipTimeout:
            hyp = ""
            timed_out = True
        dt = time.monotonic() - t0
        out.append({"id": r["id"], "hyp": hyp, "decode_s": dt, "timed_out": timed_out,
                    "glossary_size_after": len(glossary.terms)})
        if timed_out:
            print(f"  [{i+1}/{len(rows)}] id={r['id']} TIMED OUT after {dt:.1f}s", flush=True)
        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(rows)}] last decode {dt:.2f}s  glossary_size={len(glossary.terms)}", flush=True)
    return out


def score(rows: list[dict], hyps: list[dict]) -> dict:
    hyp_by_id = {h["id"]: h["hyp"] for h in hyps}
    total_terms = 0
    hit_terms = 0
    total_edits = 0
    total_ref_len = 0
    per_clip_hits = {}
    for r in rows:
        hyp = hyp_by_id[r["id"]]
        terms = r["terms"]
        hits = [term_hit(t, hyp) for t in terms]
        total_terms += len(terms)
        hit_terms += sum(hits)
        per_clip_hits[r["id"]] = hits
        e, n = word_errors(r["text"], hyp)
        total_edits += e
        total_ref_len += n
    return {
        "term_recall": hit_terms / total_terms if total_terms else float("nan"),
        "total_terms": total_terms,
        "hit_terms": hit_terms,
        "wer": total_edits / total_ref_len if total_ref_len else float("nan"),
        "total_ref_words": total_ref_len,
        "per_clip_hits": per_clip_hits,
    }


def main() -> None:
    model_size = sys.argv[1] if len(sys.argv) > 1 else "small"
    n_clips = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    rows = load_rows()[:n_clips]
    print(f"model={model_size} n_clips={len(rows)}")

    static = json.loads((SCRIPT_DIR / "static_glossary.json").read_text(encoding="utf-8"))
    static_terms = tuple(static["top100_terms"])
    assert len(static_terms) == 100, len(static_terms)

    t_load = time.monotonic()
    cfg0 = Config(language="uk", model_size=model_size, compute_device="cpu", compute_type="int8")
    engine = load_engine(cfg0, per_segment_lid=False, word_timestamps=False)
    print(f"load time: {time.monotonic() - t_load:.2f}s")

    results = {"model_size": model_size, "n_clips": len(rows)}
    out_fp = SCRIPT_DIR / f"results_{model_size}_{len(rows)}.json"

    def checkpoint():
        out_fp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  checkpoint written to {out_fp}", flush=True)

    print("=== condition (a): no glossary ===")
    t0 = time.monotonic()
    hyps_a = run_condition_ab(model_size, rows, engine, ())
    results["a_wall_s"] = time.monotonic() - t0
    results["a"] = score(rows, hyps_a)
    results["a"]["decode_times"] = [h["decode_s"] for h in hyps_a]
    results["a"]["n_timed_out"] = sum(h["timed_out"] for h in hyps_a)
    results["a_hyps"] = hyps_a
    print(f"  wall {results['a_wall_s']:.1f}s  term_recall={results['a']['term_recall']:.3f}  wer={results['a']['wer']:.3f}  timed_out={results['a']['n_timed_out']}")
    checkpoint()

    print("=== condition (b): static glossary (100 terms) ===")
    t0 = time.monotonic()
    hyps_b = run_condition_ab(model_size, rows, engine, static_terms)
    results["b_wall_s"] = time.monotonic() - t0
    results["b"] = score(rows, hyps_b)
    results["b"]["decode_times"] = [h["decode_s"] for h in hyps_b]
    results["b"]["n_timed_out"] = sum(h["timed_out"] for h in hyps_b)
    results["b_hyps"] = hyps_b
    print(f"  wall {results['b_wall_s']:.1f}s  term_recall={results['b']['term_recall']:.3f}  wer={results['b']['wer']:.3f}  timed_out={results['b']['n_timed_out']}")
    checkpoint()

    print("=== condition (c): autogrow only ===")
    t0 = time.monotonic()
    hyps_c = run_condition_c(model_size, rows, engine)
    results["c_wall_s"] = time.monotonic() - t0
    results["c"] = score(rows, hyps_c)
    results["c"]["decode_times"] = [h["decode_s"] for h in hyps_c]
    results["c"]["n_timed_out"] = sum(h["timed_out"] for h in hyps_c)
    results["c_hyps"] = hyps_c
    print(f"  wall {results['c_wall_s']:.1f}s  term_recall={results['c']['term_recall']:.3f}  wer={results['c']['wer']:.3f}  timed_out={results['c']['n_timed_out']}")
    checkpoint()
    print(f"wrote {out_fp}")


if __name__ == "__main__":
    main()
