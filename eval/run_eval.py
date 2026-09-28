"""Evaluate GMST against raw faster-whisper baselines on eval/results/data/.

Systems:
  fw-<size>-auto   raw faster-whisper, language=None (autodetect) — the "just Whisper" baseline
  fw-<size>-forced raw faster-whisper, language pinned to the clip's language (pure sets only)
  gmst-batch       gmst.pipeline.batch.transcribe_by_region(--gmst-model): each VAD region decoded
                   in its own restricted LID language (DECIDE-03)
  gmst-stream      pipeline.run_stream over the clip fed in 0.25 s blocks — the streaming path

Metrics (review F.2, 2026-09-28):
- **corpus** WER / CER (total edits / total reference length, ``gmst.metrics``'s normalization),
  which is what the Ukrainian leaderboard reports, with a bootstrap 95 % CI over clips; the old
  mean-of-per-clip figure is kept as ``wer_macro`` for comparison only.
- mixed set: ``wer_en_lid`` / ``wer_uk_lid`` — that language's reference words against the
  hypothesis text the system *labelled* that language, so they measure LID x ASR jointly;
  ``lid_recall`` and ``switch_detected`` — reported as n/a for ``fw-*``, which label a whole file
  with one language and can never register a switch.
- ``--compare A,B``: paired bootstrap CI of the WER difference on the clips both systems decoded.

Hypotheses are cached per system **and model** — ``hyp/fw-<size>-<mode>.jsonl`` (the model is in
the name) and ``hyp/gmst-<mode>@<model>.jsonl`` — every record names its model, and a cache holding
another model's records is refused rather than resumed (R5: a large-v3 run silently continued a
tiny one). Scoring one system merges into ``scores.json`` instead of overwriting it.

Run:  uv run python eval/run_eval.py --systems fw-large-v3-auto,gmst-batch --gmst-model large-v2
      uv run python eval/run_eval.py --score-only
      uv run python eval/run_eval.py --compare gmst-batch@large-v2,gmst-batch@large-v3
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from gmst.config import Config
from gmst.metrics import char_errors, word_errors
from gmst.pipeline.batch import transcribe_by_region

DATA = Path(__file__).parent / "results" / "data"
HYP = Path(__file__).parent / "results" / "hyp"
SCORES = Path(__file__).parent / "results" / "scores.json"
SR = 16_000
BOOTSTRAP = 2000


# ---------------------------------------------------------------- data

def _load_manifest(name: str) -> list[dict]:
    p = DATA / f"{name}.jsonl"
    if not p.exists():  # a set that was not built scores as empty
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _wav(rel: str) -> np.ndarray:
    a, sr = sf.read(DATA / rel, dtype="float32")
    assert sr == SR, sr
    return a


# ---------------------------------------------------------------- systems

_FW_CACHE: dict[str, object] = {}


def _fw_model(size: str):
    if size not in _FW_CACHE:
        from faster_whisper import WhisperModel

        _FW_CACHE[size] = WhisperModel(size, device="cpu", compute_type="int8")
    return _FW_CACHE[size]


def run_fw(size: str, mode: str, wav: np.ndarray, clip_lang: str | None) -> dict:
    lang = None if mode == "auto" else clip_lang
    t0 = time.monotonic()
    segs, info = _fw_model(size).transcribe(
        wav, language=lang, multilingual=lang is None, word_timestamps=False
    )
    segs = list(segs)
    dt = time.monotonic() - t0
    parts = [{"text": s.text.strip(), "lang": getattr(s, "language", None) or info.language}
             for s in segs]
    return {
        "text": " ".join(p["text"] for p in parts),
        "segments": parts or [{"text": "", "lang": info.language}],
        "file_lang": info.language,
        "rtf": dt / (len(wav) / SR),
    }


_GMST_ENGINE = None
GMST_MODEL = "large-v3"  # overridden by --gmst-model


def _gmst_engine():
    global _GMST_ENGINE
    if _GMST_ENGINE is None:
        from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

        _GMST_ENGINE = FasterWhisperEngine(
            Config(model_size=GMST_MODEL), per_segment_lid=True, word_timestamps=False
        )
    return _GMST_ENGINE


def run_gmst_batch(wav: np.ndarray, clip_lang: str | None) -> dict:
    eng = _gmst_engine()
    t0 = time.monotonic()
    segs = transcribe_by_region(wav, Config(model_size=GMST_MODEL), eng)  # GMST's batch path
    dt = time.monotonic() - t0
    parts = [{"text": s.text.strip(), "lang": s.language} for s in segs]
    return {
        "text": " ".join(p["text"] for p in parts),
        "segments": parts or [{"text": "", "lang": "?"}],
        "rtf": dt / (len(wav) / SR),
    }


def run_gmst_stream(wav: np.ndarray, clip_lang: str | None) -> dict:
    from gmst.pipeline.stream import run_stream

    class _Src:
        def __init__(self, blocks):
            self._b = blocks
            self._c = False
            self.lagging = False

        def blocks(self):
            for x in self._b:
                if self._c:
                    return
                yield x

        def close(self):
            self._c = True

        @property
        def seconds_captured(self):
            return sum(len(x) for x in self._b) / SR

    class _Sink:
        def __init__(self):
            self.segs = []

        def emit(self, s):
            if s.is_final:
                self.segs.append(s)

        def close(self):
            pass

    blk = int(0.25 * SR)
    blocks = [wav[i : i + blk] for i in range(0, len(wav), blk)]
    sink = _Sink()
    cfg = Config(model_size=GMST_MODEL, vad_backend="silero", min_chunk_seconds=0.8,
                 min_silence_ms=500, max_buffer_seconds=12.0)
    eng = _gmst_engine()  # reuse the loaded model; per_segment_lid unused (stream does its own)
    t0 = time.monotonic()
    run_stream(cfg, _Src(blocks), eng, sink, language=None)
    dt = time.monotonic() - t0
    parts = [{"text": s.text.strip(), "lang": s.language} for s in sink.segs]
    return {
        "text": " ".join(p["text"] for p in parts),
        "segments": parts or [{"text": "", "lang": "?"}],
        "rtf": dt / (len(wav) / SR),
    }


def dispatch(system: str, wav: np.ndarray, clip_lang: str | None) -> dict:
    if system == "gmst-batch":
        return run_gmst_batch(wav, clip_lang)
    if system == "gmst-stream":
        return run_gmst_stream(wav, clip_lang)
    # fw-<size>-<auto|forced>
    _, *rest = system.split("-")
    mode = rest[-1]
    size = "-".join(rest[:-1])
    return run_fw(size, mode, wav, clip_lang)


# ---------------------------------------------------------------- caching

def model_of(system: str) -> str:
    """The model a system's hypotheses come from: in the name for ``fw-*``, ``--gmst-model``
    otherwise."""
    if system.startswith("fw-"):
        return "-".join(system.split("-")[1:-1])
    return GMST_MODEL


def hyp_path(system: str) -> Path:
    if system.startswith("fw-"):
        return HYP / f"{system}.jsonl"
    return HYP / f"{system}@{GMST_MODEL}.jsonl"


def _expected_model(path: Path) -> str:
    stem = path.stem
    return stem.split("@", 1)[1] if "@" in stem else model_of(stem)


def cached_ids(path: Path) -> set[str]:
    """Clip ids already decoded into ``path``; refuses a file holding another model's records."""
    if not path.exists():
        return set()
    want, ids = _expected_model(path), set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("model", want) != want:
            raise ValueError(f"{path} holds {rec['model']} hypotheses, not {want}; move it aside")
        ids.add(rec["id"])
    return ids


# ---------------------------------------------------------------- scoring

def _rate(errs: list[int], ns: list[int]) -> float:
    total = sum(ns)
    return 100 * sum(errs) / total if total else float("nan")


def _ci(errs: list[int], ns: list[int]) -> list[float]:
    """Bootstrap 95 % CI of corpus WER, resampling clips (seeded, so reruns agree)."""
    e, n = np.asarray(errs, float), np.asarray(ns, float)
    idx = np.random.default_rng(0).integers(0, len(e), size=(BOOTSTRAP, len(e)))
    rates = 100 * e[idx].sum(1) / np.maximum(n[idx].sum(1), 1)
    return [round(float(np.percentile(rates, q)), 2) for q in (2.5, 97.5)]


def _macro(errs: list[int], ns: list[int]) -> float:
    per = [e / n if n else float(e > 0) for e, n in zip(errs, ns, strict=True)]
    return 100 * sum(per) / len(per) if per else float("nan")


def _load_hyps(key: str) -> dict[str, dict]:
    hp = HYP / f"{key}.jsonl"
    out = {}
    if hp.exists():
        for line in hp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                out[o["id"]] = o
    return out


def score(key: str) -> dict:
    """Scores for one cache file (``fw-tiny-auto``, ``gmst-batch@large-v2``, …)."""
    hyps = _load_hyps(key)
    out: dict = {"system": key, "n": len(hyps)}
    for name in ("en", "uk"):
        rows = [m for m in _load_manifest(name) if m["id"] in hyps]
        if not rows:
            continue
        w = [word_errors(m["text"], hyps[m["id"]]["text"]) for m in rows]
        c = [char_errors(m["text"], hyps[m["id"]]["text"]) for m in rows]
        we, wn = [x[0] for x in w], [x[1] for x in w]
        out[name] = {
            "n": len(rows),
            "wer": round(_rate(we, wn), 2),
            "wer_ci95": _ci(we, wn),
            "wer_macro": round(_macro(we, wn), 2),
            "cer": round(_rate([x[0] for x in c], [x[1] for x in c]), 2),
            "rtf": round(float(np.mean([hyps[m["id"]].get("rtf", np.nan) for m in rows])), 3),
        }

    raw_baseline = key.startswith("fw-")
    mixed = _load_manifest("mixed") if (DATA / "mixed.jsonl").exists() else []
    kinds = sorted({m.get("kind") for m in mixed if m.get("kind")})
    for kset in ["mixed"] + [f"mixed:{k}" for k in kinds]:
        _, _, kind = kset.partition(":")
        rows = [m for m in mixed if m["id"] in hyps and (not kind or m.get("kind") == kind)]
        if not rows:
            continue
        we, wn = [], []
        per_lang: dict[str, tuple[list[int], list[int]]] = {"en": ([], []), "uk": ([], [])}
        lid_hits = lid_total = sw_seen = sw_total = 0
        for m in rows:
            h = hyps[m["id"]]
            e, n = word_errors(m["text"], h["text"])
            we.append(e)
            wn.append(n)
            segs = h.get("segments", [{"text": h["text"], "lang": "?"}])
            ref_langs = {s["lang"] for s in m["spans"]}
            sys_langs = {s["lang"] for s in segs if s["lang"] in ("en", "uk")}
            for lg in ("en", "uk"):
                ref_l = " ".join(s["text"] for s in m["spans"] if s["lang"] == lg)
                if not ref_l:
                    continue
                e, n = word_errors(ref_l, " ".join(s["text"] for s in segs if s["lang"] == lg))
                per_lang[lg][0].append(e)
                per_lang[lg][1].append(n)
            for lg in ref_langs:
                lid_total += 1
                lid_hits += lg in sys_langs
            if len(ref_langs) > 1:
                sw_total += 1
                sw_seen += len(sys_langs) > 1
        entry: dict = {"n": len(rows), "wer": round(_rate(we, wn), 2), "wer_ci95": _ci(we, wn)}
        for lg, (e, n) in per_lang.items():
            entry[f"wer_{lg}_lid"] = round(_rate(e, n), 2) if n else None
        if raw_baseline:  # one file-level label: a switch can never register
            entry["lid_recall"], entry["switch_detected"] = None, "n/a"
        else:
            entry["lid_recall"] = round(100 * lid_hits / lid_total, 1) if lid_total else None
            entry["switch_detected"] = f"{sw_seen}/{sw_total}" if sw_total else "n/a"
        out[kset] = entry
    return out


def compare(key_a: str, key_b: str) -> dict:
    """Paired bootstrap 95 % CI of WER(a) - WER(b), per pure set, on clips both decoded."""
    ha, hb = _load_hyps(key_a), _load_hyps(key_b)
    out: dict = {"a": key_a, "b": key_b}
    for name in ("en", "uk"):
        rows = [m for m in _load_manifest(name) if m["id"] in ha and m["id"] in hb]
        if not rows:
            continue
        ea, na = zip(*(word_errors(m["text"], ha[m["id"]]["text"]) for m in rows), strict=True)
        eb, _ = zip(*(word_errors(m["text"], hb[m["id"]]["text"]) for m in rows), strict=True)
        ea, eb, n = (np.asarray(x, float) for x in (ea, eb, na))
        idx = np.random.default_rng(0).integers(0, len(n), size=(BOOTSTRAP, len(n)))
        d = 100 * (ea[idx].sum(1) - eb[idx].sum(1)) / np.maximum(n[idx].sum(1), 1)
        out[name] = {
            "n": len(rows),
            "diff": round(float(100 * (ea.sum() - eb.sum()) / n.sum()), 2),
            "ci95": [round(float(np.percentile(d, q)), 2) for q in (2.5, 97.5)],
        }
    return out


def write_scores(new: list[dict]) -> None:
    """Merge into ``scores.json`` by system: scoring one system never discards the others."""
    old = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.exists() else []
    by = {s["system"]: s for s in old}
    by.update({s["system"]: s for s in new})
    SCORES.write_text(json.dumps(sorted(by.values(), key=lambda s: s["system"]),
                                 ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="")
    ap.add_argument("--limit", type=int, default=0, help="cap clips per set (0 = all)")
    ap.add_argument("--gmst-model", default="large-v3")
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--compare", default="", help="KEY_A,KEY_B: paired WER difference with CI")
    args = ap.parse_args()

    global GMST_MODEL
    GMST_MODEL = args.gmst_model

    if args.compare:
        a, b = args.compare.split(",")
        print(json.dumps(compare(a, b), ensure_ascii=False))
        return

    systems = [s for s in args.systems.split(",") if s]

    if not args.score_only:
        HYP.mkdir(parents=True, exist_ok=True)
        sets = {"en": "en", "uk": "uk", "mixed": None}
        for system in systems:
            hp = hyp_path(system)
            done = cached_ids(hp)
            with hp.open("a", encoding="utf-8") as fh:
                for name, clip_lang in sets.items():
                    rows = _load_manifest(name)
                    if args.limit:
                        rows = rows[: args.limit]
                    for i, m in enumerate(rows):
                        if m["id"] in done:
                            continue
                        r = dispatch(system, _wav(m["wav"]), clip_lang)
                        r.update(id=m["id"], set=name, model=model_of(system))
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                        fh.flush()
                        if i % 10 == 0:
                            print(f"  {system} {name} {i}/{len(rows)}", flush=True)
            print(f"done {system}", flush=True)

    print("\n# scores\n")
    keys = [hyp_path(s).stem for s in systems] if systems else _known_systems()
    all_scores = [score(k) for k in keys]
    write_scores(all_scores)
    for s in all_scores:
        print(json.dumps(s, ensure_ascii=False))


def _known_systems() -> list[str]:
    return sorted(p.stem for p in HYP.glob("*.jsonl")) if HYP.exists() else []


if __name__ == "__main__":
    main()
