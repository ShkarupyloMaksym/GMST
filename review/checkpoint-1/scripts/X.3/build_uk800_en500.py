"""X.3 (EVID-03, amended 2026-09-28): build the 800-clip cleaned-CV10 uk set and the 500-clip
LibriSpeech test-clean en set, first N of a fixed seed-0 shuffle.

Reuses eval/build_sets.py's loading helpers (_load_uk / _load_en) verbatim so the clip selection,
resampling and peak-normalisation are identical to the existing en/uk manifests -- only n and seed
differ. Writes new files only: eval/results/data/uk800{,.jsonl} and en500{,.jsonl}. Never touches
the existing en.jsonl / uk.jsonl (seed=13, n=60).

Run:  uv run python review/checkpoint-1/scripts/X.3/build_uk800_en500.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "eval"))
import build_sets as bs  # noqa: E402

SEED = 0
N_UK = 800
N_EN = 500


def main() -> None:
    print("loading uk (cleaned CV10), seed=0, n=800 ...", flush=True)
    uk = bs._load_uk(N_UK, SEED)
    print("loading en (LibriSpeech test-clean), seed=0, n=500 ...", flush=True)
    en = bs._load_en(N_EN, SEED)
    assert len(uk) == N_UK, f"only found {len(uk)} uk clips"
    assert len(en) == N_EN, f"only found {len(en)} en clips"
    bs._write_pure(uk, "uk800")
    bs._write_pure(en, "en500")

    clips_txt = Path(__file__).parent / "clips.txt"
    with clips_txt.open("w", encoding="utf-8") as fh:
        fh.write("# uk800 (cleaned CV10, seed=0, first 800)\n")
        for r in uk:
            fh.write(f"{r['id']}\n")
        fh.write("# en500 (LibriSpeech test-clean, seed=0, first 500)\n")
        for r in en:
            fh.write(f"{r['id']}\n")
    print(f"wrote {clips_txt} ({len(uk)} uk + {len(en)} en ids)")


if __name__ == "__main__":
    main()
