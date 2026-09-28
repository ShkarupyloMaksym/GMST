"""Build the evaluation sets under eval/results/data/ from locally-downloaded corpora.

FLEURS via the HF Hub is unusably rate-limited for unauthenticated use, so:
  uk : egorsmkv "cleaned Common Voice 10" test set  (read speech; the exact set the Ukrainian
       leaderboard at github.com/egorsmkv/speech-recognition-uk scores, so numbers compare directly)
  en : LibriSpeech test-clean                       (read speech)

Derived:
  mixed   : synthetic code-switch clips spliced from the same uk/en clips
            * inter   : [A] + 800-1200 ms silence + [B]   (a switch across a pause the endpointer
                        sees: longer than min_silence_ms = 600 and the eval stream's 500)
            * nopause : [A][B], no gap                    (a sentence-level switch with no pause:
                        one endpointed utterance, one LID decision — the hard realistic case)
            The old "intra" kind (B spliced into the middle of A) cut A mid-word in 18/20 clips and
            split its reference by word count, so the reference was misaligned (R5); the
            intra-sentence switch it was named for is unsolved and is not measured here.
  real_cs : dropped — the cleaned CV10 labels contain no Latin script at all (0 of 3204, R5), so
            it could never be non-empty; real code-switched audio is DECIDE-06.

Run:  uv run python eval/build_sets.py [--per-lang N] [--mixed N]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

SR = 16_000
HERE = Path(__file__).parent
RAW = HERE / "results" / "raw"
OUT = HERE / "results" / "data"


def _to_16k_mono(audio: np.ndarray, rate: int) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    if rate != SR:
        x = soxr.resample(x, rate, SR, quality="HQ").astype(np.float32)
    peak = float(np.max(np.abs(x))) or 1.0
    return (x / peak * 0.95).astype(np.float32)


def _load_uk(n: int, seed: int) -> list[dict]:
    labels = HERE / "results" / "cv10-uk-testset-clean" / "labels_relative.csv"
    base = RAW  # relative paths look like filtered-cv10-test/100.wav
    rows = list(csv.DictReader(labels.open(encoding="utf-8")))
    random.Random(seed).shuffle(rows)
    out = []
    for r in rows:
        wp = base / r["path"]
        if not wp.is_file():
            continue
        a, sr = sf.read(wp, dtype="float32")
        wav = _to_16k_mono(a, sr)
        if len(wav) < SR:
            continue
        out.append({"id": f"uk-{wp.stem}", "text": r["text"].strip(), "wav": wav})
        if len(out) >= n:
            break
    return out


def _load_en(n: int, seed: int) -> list[dict]:
    root = RAW / "LibriSpeech" / "test-clean"
    trans = {}
    for tf in root.rglob("*.trans.txt"):
        for line in tf.read_text(encoding="utf-8").splitlines():
            uid, _, text = line.partition(" ")
            trans[uid] = text.strip()
    flacs = sorted(root.rglob("*.flac"))
    random.Random(seed).shuffle(flacs)
    out = []
    for fp in flacs:
        if fp.stem not in trans:
            continue
        a, sr = sf.read(fp, dtype="float32")
        wav = _to_16k_mono(a, sr)
        if len(wav) < SR:
            continue
        out.append({"id": f"en-{fp.stem}", "text": trans[fp.stem], "wav": wav})
        if len(out) >= n:
            break
    return out


def _write_pure(rows: list[dict], sub: str) -> None:
    d = OUT / sub
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in rows:
        sf.write(d / f"{r['id']}.wav", r["wav"], SR)
        lines.append(json.dumps({"id": r["id"], "wav": f"{sub}/{r['id']}.wav", "text": r["text"]},
                                ensure_ascii=False))
    (OUT / f"{sub}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{sub}: {len(lines)} clips")


def _silence(ms: int) -> np.ndarray:
    return np.zeros(int(SR * ms / 1000), dtype=np.float32)


def _span(wav: np.ndarray, off: int, lang: str, text: str) -> dict:
    return {"lang": lang, "text": text,
            "t0": round(off / SR, 3), "t1": round((off + len(wav)) / SR, 3)}


def _build_mixed(en: list[dict], uk: list[dict], n: int, seed: int) -> None:
    d = OUT / "mixed"
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    manifest = []
    for k in range(n):
        inter = k % 2 == 0
        a, b = (rng.choice(en), rng.choice(uk)) if k % 4 < 2 else (rng.choice(uk), rng.choice(en))
        la = "en" if a in en else "uk"
        lb = "en" if b in en else "uk"
        if inter:
            gap = _silence(rng.choice([800, 1000, 1200]))
            parts, spans, off = [], [], 0
            for wav, lang, txt in ((a["wav"], la, a["text"]), (gap, None, None),
                                   (b["wav"], lb, b["text"])):
                if lang is not None:
                    spans.append(_span(wav, off, lang, txt))
                parts.append(wav)
                off += len(wav)
            kind = "inter"
        else:
            parts, spans, off = [], [], 0
            for wav, lang, txt in ((a["wav"], la, a["text"]), (b["wav"], lb, b["text"])):
                spans.append(_span(wav, off, lang, txt))
                parts.append(wav)
                off += len(wav)
            kind = "nopause"
        clip = np.concatenate(parts)
        cid = f"mix-{kind}-{k:03d}"
        sf.write(d / f"{cid}.wav", clip, SR)
        manifest.append({"id": cid, "wav": f"mixed/{cid}.wav", "kind": kind,
                         "text": " ".join(s["text"] for s in spans), "spans": spans})
    (OUT / "mixed.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n", encoding="utf-8")
    n_inter = sum(1 for m in manifest if m["kind"] == "inter")
    print(f"mixed: {len(manifest)} clips ({n_inter} inter, {len(manifest) - n_inter} nopause)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-lang", type=int, default=60)
    ap.add_argument("--mixed", type=int, default=40)
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading uk (cleaned CV10) …", flush=True)
    uk = _load_uk(args.per_lang, args.seed)
    print("loading en (LibriSpeech test-clean) …", flush=True)
    en = _load_en(args.per_lang, args.seed)
    _write_pure(uk, "uk")
    _write_pure(en, "en")
    _build_mixed(en, uk, args.mixed, args.seed)
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
