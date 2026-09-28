"""Score EVID-02 raw detect_language output: unrestricted top-1 vs restricted en/{uk,ru} argmax.

Restricted argmax follows resolve_language's tie-break design (src/gmst/transcribe/lid.py):
the only two languages a mixed EN/UK meeting can be is en or uk, and a ru label on Ukrainian
speech is the visible failure the tie-break exists to fix. So the restricted bucket sums
P(uk)+P(ru) into one "uk-ish" mass and compares it against P(en); whichever mass is larger
wins. Ground truth "uk" clips are scored correct if the uk-ish bucket wins (i.e. the tie-break,
if applied downstream, would recover uk from a ru mislabel); "en" clips are correct iff the en
bucket wins.

Unrestricted top-1 is the raw argmax over all ~100 Whisper language codes (the "top_lang" field
faster-whisper returns), scored correct only if it exactly equals the ground-truth label -- a
"ru" call on a uk clip counts as wrong here, by design (that's the failure mode X.2 is measuring
the size of).

Every row here has no prev_lang / sticky state -- every measurement is the first-utterance
(no-prior) case per the node brief.

Usage: uv run python score_lid.py small_raw.jsonl large-v2_raw.jsonl
"""
import json
import sys
from collections import defaultdict

PREFIX_LABELS = [1, 2, 3, 4, "full"]  # matches run_lid.py's PREFIXES_S order, 5 rows/clip


def load(path):
    with open(path) as f:
        rows = [json.loads(line) for line in f]
    # run_lid.py writes exactly 5 rows per clip in PREFIXES_S order (1,2,3,4,full); label by
    # position, not by matching requested_prefix_s to clip_dur_s (that float comparison is
    # unreliable: requested_prefix_s for the full row is unrounded len(audio)/SR, clip_dur_s is
    # round(dur, 3) -- they differ in the last digits for most clips).
    assert len(rows) % 5 == 0, len(rows)
    for i, r in enumerate(rows):
        r["prefix_label"] = PREFIX_LABELS[i % 5]
    return rows


def restricted_pred(all_probs):
    d = dict(all_probs)
    p_en = d.get("en", 0.0)
    p_uk = d.get("uk", 0.0)
    p_ru = d.get("ru", 0.0)
    return "en" if p_en >= (p_uk + p_ru) else "uk"


def score(rows, model_name):
    # bucket by (truth, requested_prefix_s) -- requested_prefix_s is 1,2,3,4 or the clip's own
    # duration for the "full" row (None -> dur in run_lid.py, stored as requested_prefix_s==dur)
    buckets = defaultdict(lambda: {"n": 0, "unrestricted_correct": 0, "restricted_correct": 0})
    for r in rows:
        key = r["prefix_label"]
        truth = r["truth"]
        b = buckets[(truth, key)]
        b["n"] += 1
        b["unrestricted_correct"] += int(r["top_lang"] == truth)
        b["restricted_correct"] += int(restricted_pred(r["all_probs"]) == truth)

    print(f"\n=== {model_name} ===")
    print(f"{'lang':4} {'prefix':6} {'n':>4} {'unrestr_acc':>12} {'restr_acc':>10}")
    summary = {}
    for truth in ("en", "uk"):
        for key in (1, 2, 3, 4, "full"):
            b = buckets.get((truth, key))
            if b is None:
                continue
            ua = b["unrestricted_correct"] / b["n"]
            ra = b["restricted_correct"] / b["n"]
            print(f"{truth:4} {str(key):6} {b['n']:4} {ua:12.3f} {ra:10.3f}")
            summary[(model_name, truth, key)] = (b["n"], ua, ra)
    return summary


def main():
    all_summary = {}
    for path in sys.argv[1:]:
        model_name = path.split("/")[-1].replace("_raw.jsonl", "")
        rows = load(path)
        all_summary.update(score(rows, model_name))

    print("\n=== capped rows (prefix > clip duration, i.e. prefix == full audio already) ===")
    for path in sys.argv[1:]:
        rows = load(path)
        capped = [r for r in rows if r["capped"]]
        print(path, "capped rows:", len(capped), "/", len(rows))


if __name__ == "__main__":
    main()
