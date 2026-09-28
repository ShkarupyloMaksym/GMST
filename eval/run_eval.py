"""Evaluate GMST against raw faster-whisper baselines on eval/results/data/.

Systems:
  fw-<size>-auto   raw faster-whisper, language=None (autodetect) — the "just Whisper" baseline
  fw-<size>-forced raw faster-whisper, language pinned to the clip's language (pure sets only)
  gmst-batch       gmst.pipeline.batch.transcribe_by_region(--gmst-model): each VAD region decoded
                   in its own restricted LID language (DECIDE-03)
  gmst-stream      pipeline.run_stream over the clip fed in 0.25 s blocks — the streaming path

Metrics: WER / CER (jiwer, shared normalization), and for the mixed set: per-language WER,
utterance-level LID accuracy, and whether the system detected the language switch at all.

Per-clip hypotheses are cached to eval/results/hyp/<system>.jsonl so a re-run resumes.

Run:  uv run --with jiwer python eval/run_eval.py --systems fw-large-v3-auto,gmst-batch [--limit 40]
      uv run --with jiwer python eval/run_eval.py --score-only
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from gmst.config import Config
from gmst.metrics import normalize_words
from gmst.pipeline.batch import transcribe_by_region

DATA = Path(__file__).parent / "results" / "data"
HYP = Path(__file__).parent / "results" / "hyp"
SR = 16_000


# ---------------------------------------------------------------- data

def _load_manifest(name: str) -> list[dict]:
    p = DATA / f"{name}.jsonl"
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


# ---------------------------------------------------------------- scoring

def _wer(ref: str, hyp: str) -> float:
    import jiwer

    r, h = " ".join(normalize_words(ref)), " ".join(normalize_words(hyp))
    if not r:
        return 0.0 if not h else 1.0
    return jiwer.wer(r, h)


def _cer(ref: str, hyp: str) -> float:
    import jiwer

    r, h = " ".join(normalize_words(ref)), " ".join(normalize_words(hyp))
    if not r:
        return 0.0 if not h else 1.0
    return jiwer.cer(r, h)


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def score(system: str) -> dict:
    hyps = {}
    hp = HYP / f"{system}.jsonl"
    if hp.exists():
        for line in hp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                hyps[o["id"]] = o

    out: dict = {"system": system, "n": len(hyps)}
    for name in ("en", "uk"):
        rows = [m for m in _load_manifest(name) if m["id"] in hyps]
        if not rows:
            continue
        out[name] = {
            "n": len(rows),
            "wer": round(100 * _mean([_wer(m["text"], hyps[m["id"]]["text"]) for m in rows]), 2),
            "cer": round(100 * _mean([_cer(m["text"], hyps[m["id"]]["text"]) for m in rows]), 2),
            "rtf": round(_mean([hyps[m["id"]].get("rtf", float("nan")) for m in rows]), 3),
        }

    for kset in ("mixed", "mixed:inter", "mixed:intra"):
        base, _, kind = kset.partition(":")
        rows = [m for m in _load_manifest(base) if m["id"] in hyps
                and (not kind or m.get("kind") == kind)]
        if not rows:
            continue
        overall, wl = [], {"en": [], "uk": []}
        lid_hits = lid_total = sw_seen = sw_total = 0
        for m in rows:
            h = hyps[m["id"]]
            overall.append(_wer(m["text"], h["text"]))
            segs = h.get("segments", [{"text": h["text"], "lang": "?"}])
            ref_langs = {s["lang"] for s in m["spans"]}
            sys_langs = {s["lang"] for s in segs if s["lang"] in ("en", "uk")}
            # per-language WER: this language's ref text vs the hyp segments labelled that language
            for lg in ("en", "uk"):
                ref_l = " ".join(s["text"] for s in m["spans"] if s["lang"] == lg)
                if not ref_l:
                    continue
                hyp_l = " ".join(s["text"] for s in segs if s["lang"] == lg)
                wl[lg].append(_wer(ref_l, hyp_l))
            # LID span recall: did the system emit every language actually present?
            for lg in ref_langs:
                lid_total += 1
                lid_hits += lg in sys_langs
            if len(ref_langs) > 1:
                sw_total += 1
                sw_seen += len(sys_langs) > 1
        out[kset] = {
            "n": len(rows),
            "wer": round(100 * _mean(overall), 2),
            "wer_en": round(100 * _mean(wl["en"]), 2) if wl["en"] else None,
            "wer_uk": round(100 * _mean(wl["uk"]), 2) if wl["uk"] else None,
            "lid_recall": round(100 * lid_hits / lid_total, 1) if lid_total else None,
            "switch_detected": f"{sw_seen}/{sw_total}" if sw_total else "n/a",
        }
    return out


# ---------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="")
    ap.add_argument("--limit", type=int, default=0, help="cap clips per set (0 = all)")
    ap.add_argument("--gmst-model", default="large-v3")
    ap.add_argument("--score-only", action="store_true")
    args = ap.parse_args()

    global GMST_MODEL
    GMST_MODEL = args.gmst_model

    systems = [s for s in args.systems.split(",") if s]

    if not args.score_only:
        HYP.mkdir(parents=True, exist_ok=True)
        sets = {"en": "en", "uk": "uk", "mixed": None}
        for system in systems:
            hp = HYP / f"{system}.jsonl"
            done = set()
            if hp.exists():
                done = {json.loads(x)["id"] for x in hp.read_text().splitlines() if x.strip()}
            with hp.open("a", encoding="utf-8") as fh:
                for name, clip_lang in sets.items():
                    rows = _load_manifest(name)
                    if args.limit:
                        rows = rows[: args.limit]
                    for i, m in enumerate(rows):
                        if m["id"] in done:
                            continue
                        cl = clip_lang
                        r = dispatch(system, _wav(m["wav"]), cl)
                        r["id"] = m["id"]
                        r["set"] = name
                        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                        fh.flush()
                        if i % 10 == 0:
                            print(f"  {system} {name} {i}/{len(rows)}", flush=True)
            print(f"done {system}", flush=True)

    print("\n# scores\n")
    all_scores = [score(s) for s in (systems or _known_systems())]
    (Path(__file__).parent / "results" / "scores.json").write_text(
        json.dumps(all_scores, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for s in all_scores:
        print(json.dumps(s, ensure_ascii=False))


def _known_systems() -> list[str]:
    return sorted(p.stem for p in HYP.glob("*.jsonl")) if HYP.exists() else []


if __name__ == "__main__":
    main()
