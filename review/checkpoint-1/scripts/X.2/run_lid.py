"""EVID-02 measurement: detect_language accuracy vs prefix length, small vs large-v2.

For each of the 120 fixed clips (scripts/X.2/clips.txt: 60 en, 60 uk), call
faster_whisper.WhisperModel.detect_language on prefixes of 1/2/3/4 s and the full clip.
Record the raw (lang, prob, all_probs) for offline scoring (unrestricted top-1 and the
en/{uk,ru} restricted argmax) in run_lid.py's companion, score_lid.py.

Called directly (not via gmst.transcribe.backends) per the node brief: avoid importing
modules under concurrent edit. Offline only (HF_HUB_OFFLINE=1), one large-* model loaded
at a time. Each detect_language call is independent (no prev_lang / sticky state) -- this
*is* the first-utterance / no-prior case for every row.

Usage: uv run python run_lid.py <model_size> <out.jsonl>
"""
import json
import os
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import soundfile as sf
from faster_whisper import WhisperModel

HERE = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(HERE, "clips.txt")
PREFIXES_S = [1, 2, 3, 4, None]  # None = full clip
SR = 16000


def main():
    model_size = sys.argv[1]
    out_path = sys.argv[2]

    with open(CLIPS) as f:
        clips = [line.strip().split("\t") for line in f if line.strip()]

    t0 = time.time()
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    load_s = time.time() - t0
    print(f"[{model_size}] loaded in {load_s:.2f}s, {len(clips)} clips", flush=True)

    n_calls = 0
    t_start = time.time()
    with open(out_path, "w") as out:
        for i, (truth, path) in enumerate(clips):
            audio, sr = sf.read(path, dtype="float32")
            assert sr == SR, (path, sr)
            dur = len(audio) / SR
            for p in PREFIXES_S:
                requested = p if p is not None else dur
                n = min(len(audio), int((p or dur) * SR)) if p is not None else len(audio)
                a = audio[:n]
                t0 = time.time()
                lang, prob, all_probs = model.detect_language(a)
                dt = time.time() - t0
                n_calls += 1
                row = {
                    "truth": truth,
                    "clip": os.path.basename(path),
                    "clip_dur_s": round(dur, 3),
                    "requested_prefix_s": requested,
                    "actual_prefix_s": round(n / SR, 3),
                    "capped": n >= len(audio) and p is not None and p > dur,
                    "top_lang": lang,
                    "top_prob": float(prob),
                    "all_probs": [[l_, float(pr_)] for l_, pr_ in all_probs],
                    "call_s": round(dt, 3),
                }
                out.write(json.dumps(row) + "\n")
                out.flush()
            if (i + 1) % 10 == 0:
                elapsed = time.time() - t_start
                print(
                    f"[{model_size}] {i + 1}/{len(clips)} clips, "
                    f"{n_calls} calls, {elapsed:.1f}s elapsed",
                    flush=True,
                )
    total_s = time.time() - t_start
    print(f"[{model_size}] done: {n_calls} calls in {total_s:.1f}s (load {load_s:.2f}s)", flush=True)


if __name__ == "__main__":
    main()
