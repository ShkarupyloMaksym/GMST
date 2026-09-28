"""X.6 condition (b): build the static glossary = 100 most frequent Latin terms in
eval/results/raw/uk-pods_pods_train.json's `text_no_preprocessing` field (same tokenizer as X.5:
`[A-Za-z][A-Za-z]+`, i.e. Latin runs of >=2 letters), and report the overlap of clip ids between
that file and the 200 terms.jsonl test clips (X.5 built terms.jsonl from train+test manifests).

Writes review/checkpoint-1/scripts/X.6/static_glossary.json: {"terms": [...100...], "overlap_ids": N,
"overlap_total_train_rows": N, "overlap_example_ids": [...]}

Run: uv run python review/checkpoint-1/scripts/X.6/build_static_glossary.py
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / "eval" / "results" / "raw"
DATA = ROOT / "eval" / "results" / "data"

LAT_TOKEN = re.compile(r"[A-Za-z][A-Za-z]+")


def clip_id(audio_filepath: str) -> str:
    return Path(audio_filepath).stem


def main() -> None:
    train_fp = RAW / "uk-pods_pods_train.json"
    counts: collections.Counter[str] = collections.Counter()
    surface: dict[str, str] = {}  # casefold -> most frequent surface form
    train_ids: set[str] = set()
    with train_fp.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            train_ids.add(clip_id(d["audio_filepath"]))
            raw = (d.get("text_no_preprocessing") or "").strip()
            for tok in LAT_TOKEN.findall(raw):
                key = tok.casefold()
                counts[key] += 1
                # keep the first-seen surface form as representative casing (stable, reproducible)
                surface.setdefault(key, tok)

    top100 = [surface[k] for k, _ in counts.most_common(100)]

    terms_fp = DATA / "terms.jsonl"
    terms_rows = [json.loads(line) for line in terms_fp.read_text(encoding="utf-8").splitlines() if line.strip()]
    terms_ids = {r["id"] for r in terms_rows}
    overlap = terms_ids & train_ids

    out = {
        "n_train_rows": len(train_ids),
        "n_terms_clips": len(terms_ids),
        "overlap_ids_count": len(overlap),
        "overlap_ids_example": sorted(overlap)[:10],
        "top100_terms": top100,
        "top100_counts": [counts[t.casefold()] for t in top100],
    }
    out_fp = Path(__file__).resolve().parent / "static_glossary.json"
    out_fp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"train rows: {len(train_ids)}  terms clips: {len(terms_ids)}  overlap: {len(overlap)}")
    print(f"top 10 terms: {top100[:10]}")
    print(f"wrote {out_fp}")


if __name__ == "__main__":
    main()
