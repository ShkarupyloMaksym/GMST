"""X.3 (EVID-03, amended 2026-09-28): model-selection eval on uk800 / en500, language pinned.

Reuses eval/run_eval.py's word_errors/char_errors, its bootstrap-CI helpers and its raw-faster-
whisper ``run_fw`` (which already pins language: ``fw-<size>-forced``), pointed at the new
uk800.jsonl / en500.jsonl manifests instead of the existing 60-clip en.jsonl / uk.jsonl. Writes its
own hyp cache (``eval/results/hyp/x3-fw-<size>-forced.jsonl``) so it never collides with or
overwrites run_eval.py's own caches; resumable by clip id exactly like run_eval.py's cache.

Candidates (faster-whisper model-size string -> HF repo faster-whisper maps it to):
  large-v2         Systran/faster-whisper-large-v2          (cached)
  large-v3         Systran/faster-whisper-large-v3          (cached)
  large-v3-turbo   mobiuslabsgmbh/faster-whisper-large-v3-turbo  (cached; CTranslate2 native)
  turbo-uk         NOT RUNNABLE via this path -- see scripts/X.3/turbo_uk_conversion.md.
                   Yehor/whisper-large-v3-turbo-quantized-uk is an HF-transformers compressed-
                   tensors (4-bit pack-quantized) checkpoint, not CTranslate2. ct2-transformers-
                   converter needs ``torch`` (wrapped in a bare ``try: import torch`` in
                   ctranslate2 4.8.1 -- absent it fails with ``NameError: name 'torch' is not
                   defined`` deep inside ``_load()``, not an install hint) and transformers needs
                   ``compressed_tensors`` to dequantize on load; neither is a GMST dependency, and
                   installing them is outside this node's network authorization (download the two
                   turbo repos only). Left undone; recorded as blocking in the node file.

Run (one candidate at a time -- one large-* model machine-wide):
  uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --model large-v2
  uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --model large-v3
  uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --model large-v3-turbo
  uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --score-only   # after all runs
  uv run python review/checkpoint-1/scripts/X.3/run_x3_eval.py --compare large-v2,large-v3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "eval"))
import run_eval as re_mod  # noqa: E402

DATA = REPO / "eval" / "results" / "data"
HYP = REPO / "eval" / "results" / "hyp"
OUT = Path(__file__).parent / "x3_scores.json"
SETS = {"uk800": "uk", "en500": "en"}  # manifest name -> language


def hyp_path(model: str) -> Path:
    return HYP / f"x3-fw-{model}-forced.jsonl"


def cached_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("model") and rec["model"] != _model_of(path):
            raise ValueError(f"{path} holds {rec['model']} hypotheses, not {_model_of(path)}")
        ids.add(rec["id"])
    return ids


def _model_of(path: Path) -> str:
    # x3-fw-<model>-forced.jsonl
    stem = path.stem
    return stem[len("x3-fw-") : -len("-forced")]


def run_model(model: str, limit: int = 0) -> None:
    hp = hyp_path(model)
    done = cached_ids(hp)
    HYP.mkdir(parents=True, exist_ok=True)
    t_start = time.monotonic()
    n_done_this_run = 0
    with hp.open("a", encoding="utf-8") as fh:
        for manifest_name, lang in SETS.items():
            rows = re_mod._load_manifest(manifest_name)
            if limit:
                rows = rows[:limit]
            for i, m in enumerate(rows):
                if m["id"] in done:
                    continue
                wav = re_mod._wav(m["wav"])
                r = re_mod.run_fw(model, "forced", wav, lang)
                r.update(id=m["id"], set=manifest_name, model=model)
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                n_done_this_run += 1
                if i % 20 == 0:
                    el = time.monotonic() - t_start
                    print(f"  {model} {manifest_name} {i}/{len(rows)}  "
                          f"({n_done_this_run} decoded this run, {el:.0f}s elapsed)", flush=True)
    print(f"done {model}: {n_done_this_run} new decodes, "
          f"{time.monotonic() - t_start:.0f}s", flush=True)


def _load_hyps(model: str) -> dict[str, dict]:
    hp = hyp_path(model)
    out = {}
    if hp.exists():
        for line in hp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                out[o["id"]] = o
    return out


def score(model: str) -> dict:
    hyps = _load_hyps(model)
    out: dict = {"system": f"x3-fw-{model}-forced", "n": len(hyps)}
    for manifest_name, lang in SETS.items():
        rows = [m for m in re_mod._load_manifest(manifest_name) if m["id"] in hyps]
        if not rows:
            continue
        w = [re_mod.word_errors(m["text"], hyps[m["id"]]["text"]) for m in rows]
        c = [re_mod.char_errors(m["text"], hyps[m["id"]]["text"]) for m in rows]
        we, wn = [x[0] for x in w], [x[1] for x in w]
        out[lang] = {
            "n": len(rows),
            "wer": round(re_mod._rate(we, wn), 2),
            "wer_ci95": re_mod._ci(we, wn),
            "wer_macro": round(re_mod._macro(we, wn), 2),
            "cer": round(re_mod._rate([x[0] for x in c], [x[1] for x in c]), 2),
            "rtf": round(float(np.mean([hyps[m["id"]].get("rtf", np.nan) for m in rows])), 3),
        }
    return out


def compare(model_a: str, model_b: str) -> dict:
    ha, hb = _load_hyps(model_a), _load_hyps(model_b)
    out: dict = {"a": model_a, "b": model_b}
    for manifest_name, lang in SETS.items():
        rows = [m for m in re_mod._load_manifest(manifest_name)
                if m["id"] in ha and m["id"] in hb]
        if not rows:
            continue
        ea, na = zip(*(re_mod.word_errors(m["text"], ha[m["id"]]["text"]) for m in rows),
                      strict=True)
        eb, _ = zip(*(re_mod.word_errors(m["text"], hb[m["id"]]["text"]) for m in rows),
                     strict=True)
        ea, eb, n = (np.asarray(x, float) for x in (ea, eb, na))
        idx = np.random.default_rng(0).integers(0, len(n), size=(re_mod.BOOTSTRAP, len(n)))
        d = 100 * (ea[idx].sum(1) - eb[idx].sum(1)) / np.maximum(n[idx].sum(1), 1)
        out[lang] = {
            "n": len(rows),
            "diff": round(float(100 * (ea.sum() - eb.sum()) / n.sum()), 2),
            "ci95": [round(float(np.percentile(d, q)), 2) for q in (2.5, 97.5)],
        }
    return out


def write_scores(new: list[dict]) -> None:
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    by = {s["system"]: s for s in old}
    by.update({s["system"]: s for s in new})
    OUT.write_text(json.dumps(sorted(by.values(), key=lambda s: s["system"]),
                               ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--compare", default="", help="MODEL_A,MODEL_B")
    args = ap.parse_args()

    if args.compare:
        a, b = args.compare.split(",")
        print(json.dumps(compare(a, b), ensure_ascii=False, indent=2))
        return

    models = [args.model] if args.model else []
    if not args.score_only and models:
        for model in models:
            run_model(model, args.limit)

    known = models or sorted({_model_of(p) for p in HYP.glob("x3-fw-*-forced.jsonl")})
    scores = [score(m) for m in known]
    write_scores(scores)
    for s in scores:
        print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
