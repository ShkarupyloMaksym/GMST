"""Build the evaluation sets under eval/results/data/ from locally-downloaded corpora.

FLEURS via the HF Hub is unusably rate-limited for unauthenticated use, so:
  uk : egorsmkv "cleaned Common Voice 10" test set  (read speech; the exact set the Ukrainian
       leaderboard at github.com/egorsmkv/speech-recognition-uk scores, so numbers compare directly)
  en : LibriSpeech test-clean                       (read speech)

Derived:
  mixed   : synthetic code-switch clips spliced from the same uk/en clips
            * inter : [A] + 300-600 ms silence + [B]     (per-utterance LID across a pause)
            * intra : [A_head][B][A_tail]  no gaps        (the hard intra-turn switch)
  real_cs : uk clips whose *gold* transcript contains a Latin-script run — real embedded English
            (brand/product/person names), real audio, real reference, nothing hand-made

Run:  uv run --with soundfile --with soxr python eval/build_sets.py [--per-lang N] [--mixed N]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

SR = 16_000
HERE = Path(__file__).parent
RAW = HERE / "results" / "raw"
OUT = HERE / "results" / "data"
LATIN = re.compile(r"[A-Za-z]{2,}")


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
            gap = _silence(rng.choice([300, 400, 600]))
            parts, spans, off = [], [], 0
            for wav, lang, txt in ((a["wav"], la, a["text"]), (gap, None, None),
                                   (b["wav"], lb, b["text"])):
                if lang is not None:
                    spans.append(_span(wav, off, lang, txt))
                parts.append(wav)
                off += len(wav)
            kind = "inter"
        else:
            cut = len(a["wav"]) // 2
            head, tail = a["wav"][:cut], a["wav"][cut:]
            w = a["text"].split()
            h_txt, t_txt = " ".join(w[: len(w) // 2]), " ".join(w[len(w) // 2 :])
            parts, spans, off = [], [], 0
            for wav, lang, txt in ((head, la, h_txt), (b["wav"], lb, b["text"]), (tail, la, t_txt)):
                spans.append(_span(wav, off, lang, txt))
                parts.append(wav)
                off += len(wav)
            kind = "intra"
        clip = np.concatenate(parts)
        cid = f"mix-{kind}-{k:03d}"
        sf.write(d / f"{cid}.wav", clip, SR)
        manifest.append({"id": cid, "wav": f"mixed/{cid}.wav", "kind": kind,
                         "text": " ".join(s["text"] for s in spans), "spans": spans})
    (OUT / "mixed.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n", encoding="utf-8")
    n_inter = sum(1 for m in manifest if m["kind"] == "inter")
    print(f"mixed: {len(manifest)} clips ({n_inter} inter, {len(manifest) - n_inter} intra)")


def _build_real_cs(seed: int, want: int = 40) -> None:
    """uk clips whose gold transcript embeds a Latin-script (English) run."""
    labels = HERE / "results" / "cv10-uk-testset-clean" / "labels_relative.csv"
    rows = [r for r in csv.DictReader(labels.open(encoding="utf-8")) if LATIN.search(r["text"])]
    random.Random(seed).shuffle(rows)
    d = OUT / "real_cs"
    d.mkdir(parents=True, exist_ok=True)
    manifest = []
    for r in rows:
        wp = RAW / r["path"]
        if not wp.is_file():
            continue
        a, sr = sf.read(wp, dtype="float32")
        wav = _to_16k_mono(a, sr)
        cid = f"rcs-{wp.stem}"
        sf.write(d / f"{cid}.wav", wav, SR)
        en_tokens = LATIN.findall(r["text"])
        manifest.append({"id": cid, "wav": f"real_cs/{cid}.wav", "text": r["text"].strip(),
                         "en_tokens": en_tokens})
        if len(manifest) >= want:
            break
    (OUT / "real_cs.jsonl").write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n", encoding="utf-8")
    print(f"real_cs: {len(manifest)} uk clips with embedded English tokens")


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
    _build_real_cs(args.seed)
    print(f"\nwrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
