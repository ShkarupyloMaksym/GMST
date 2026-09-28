"""X.5 (DECIDE-06): build the uk-en terms eval set from taras-sereda/uk-pods.

Source: `taras-sereda/uk-pods` (Hugging Face), CC-BY-NC-4.0, ~51 h of the Ukrainian podcast
"Вертіго" (film/media). Provenance of the reference text is established from the data itself,
not just the card (X.5 node "Findings"): the manifest's `text_no_preprocessing` field keeps
brand/tech terms in correct Latin spelling ("Google", "FilmSpotting", "Dreamcast", "AirPods"),
while the co-shipped `pred_text` field (an ASR model's own transcript of the same clip) garbles
or transliterates the same terms ("голг", "дауонлод", "дрім кастсту") -- the classic OOV-loanword
failure of an ASR model, not something a from-scratch ASR pass would independently reproduce
correctly. That asymmetry is the "human-correction pattern" evidence the X.5 pre-registered rule
asks for. `text` (used for training) is a lowercased AND transliterated version of
`text_no_preprocessing` and has already lost the Latin script, so it is not usable as a terms
reference; this script uses `text_no_preprocessing`.

Inputs (already downloaded to eval/results/raw/ by the X.5 node -- this script does not fetch
anything itself, per the "offline rules otherwise unchanged" instruction):
  eval/results/raw/uk-pods_pods_train.json
  eval/results/raw/uk-pods_pods_test.json
  eval/results/raw/uk-pods_clips.tar.gz   (34231 wav files, already 16 kHz mono PCM16)

Selection rule (mirrors the X.5 pre-registered rule):
  - clip's `text_no_preprocessing` contains >= 1 Latin-script token of >= 2 letters
  - clip has >= 10 Cyrillic letters (so the line is "otherwise Ukrainian", not English)
  - total Latin letters <= total Cyrillic letters (excludes lines that are mostly English)
  - clip duration >= 1.0 s
  - capped at `--per-episode` clips per source episode (the manifest's audio UUID prefix), so one
    heavy episode cannot dominate the set, then capped at `--target` total, sampled with a fixed
    seed for reproducibility.

Output:
  eval/results/data/terms/*.wav   (copied straight from the tar member -- already 16 kHz mono)
  eval/results/data/terms.jsonl   {id, wav, text, terms: [...]}

Run:  uv run python review/checkpoint-1/scripts/X.5/build_terms_set.py
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # repo root (was [3]: pointed at review/ — fixed by the orchestrator 2026-09-28)
RAW = ROOT / "eval" / "results" / "raw"
OUT_DIR = ROOT / "eval" / "results" / "data" / "terms"
OUT_JSONL = ROOT / "eval" / "results" / "data" / "terms.jsonl"

CYR = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
LAT_TOKEN = re.compile(r"[A-Za-z][A-Za-z]+")


def _candidates() -> list[dict]:
    rows: list[dict] = []
    for name in ("uk-pods_pods_train.json", "uk-pods_pods_test.json"):
        fp = RAW / name
        if not fp.is_file():
            raise SystemExit(f"missing {fp} -- fetch pods_train.json/pods_test.json into eval/results/raw/ first")
        with fp.open(encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                raw = (d.get("text_no_preprocessing") or "").strip()
                terms = LAT_TOKEN.findall(raw)
                if not terms:
                    continue
                cyr_chars = len(CYR.findall(raw))
                lat_chars = sum(len(t) for t in terms)
                if cyr_chars < 10 or lat_chars > cyr_chars:
                    continue
                if d.get("duration", 0) < 1.0:
                    continue
                episode = d["audio_filepath"].split("/")[-1].split("_")[0]
                rows.append(
                    {
                        "episode": episode,
                        "path": d["audio_filepath"],  # e.g. clips/<uuid>_0266.wav
                        "text": raw,
                        "terms": terms,
                        "duration": d["duration"],
                    }
                )
    return rows


def _select(rows: list[dict], target: int, per_episode: int, seed: int) -> list[dict]:
    by_ep: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by_ep[r["episode"]].append(r)
    rng = random.Random(seed)
    episodes = list(by_ep)
    rng.shuffle(episodes)
    for ep in episodes:
        rng.shuffle(by_ep[ep])

    selected: list[dict] = []
    # round-robin across episodes so the set stays spread across speakers/episodes even when
    # capped well below the full candidate pool
    idx = 0
    while len(selected) < target and any(by_ep[ep][idx:idx + 1] for ep in episodes):
        for ep in episodes:
            bucket = by_ep[ep]
            if idx < len(bucket) and idx < per_episode:
                selected.append(bucket[idx])
                if len(selected) >= target:
                    break
        idx += 1
    return selected


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=200, help="total clips to select")
    ap.add_argument("--per-episode", type=int, default=6, help="max clips from one episode")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rows = _candidates()
    n_episodes = len({r["episode"] for r in rows})
    print(f"candidate clips (Latin term in otherwise-Ukrainian text): {len(rows)} from {n_episodes} episodes")
    if len(rows) < 150 or n_episodes < 10:
        print("RULE FAILS: fewer than 150 candidate clips or fewer than 10 distinct episodes")
        return

    selected = _select(rows, args.target, args.per_episode, args.seed)
    sel_episodes = len({r["episode"] for r in selected})
    print(f"selected {len(selected)} clips from {sel_episodes} episodes")

    tar_path = RAW / "uk-pods_clips.tar.gz"
    if not tar_path.is_file():
        raise SystemExit(f"missing {tar_path} -- download clips.tar.gz into eval/results/raw/ first")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {r["path"] for r in selected}
    written: dict[str, Path] = {}
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf:
            if member.name not in wanted:
                continue
            f = tf.extractfile(member)
            if f is None:
                continue
            data = f.read()
            out_name = member.name.split("/")[-1]
            out_path = OUT_DIR / out_name
            out_path.write_bytes(data)
            written[member.name] = out_path
            if len(written) == len(wanted):
                break

    missing = wanted - set(written)
    if missing:
        print(f"WARNING: {len(missing)} selected clips not found in the archive: {sorted(missing)[:5]} ...")

    with OUT_JSONL.open("w", encoding="utf-8") as out:
        n = 0
        for r in selected:
            wp = written.get(r["path"])
            if wp is None:
                continue
            rec = {
                "id": wp.stem,
                "wav": f"terms/{wp.name}",
                "text": r["text"],
                "terms": r["terms"],
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} clips to {OUT_DIR} and {OUT_JSONL}")


if __name__ == "__main__":
    main()
