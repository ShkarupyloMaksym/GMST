"""X.6: from a results_<model>_<n>.json, pick 10 example terms (a) got wrong and (b)/(c) got
right, and vice versa, for the report. Run after run_glossary_eval.py has produced the results file.

Run: uv run python review/checkpoint-1/scripts/X.6/make_examples.py <results.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)


def edge_strip(tok: str) -> str:
    return _EDGE.sub("", tok)


def term_hit(term: str, hyp_text: str) -> bool:
    key = edge_strip(term).casefold()
    return any(edge_strip(w).casefold() == key for w in hyp_text.split())


def main() -> None:
    fp = Path(sys.argv[1])
    d = json.loads(fp.read_text(encoding="utf-8"))
    ROOT = Path(__file__).resolve().parents[4]
    rows = {r["id"]: r for r in (json.loads(l) for l in (ROOT / "eval/results/data/terms.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

    hyp_a = {h["id"]: h["hyp"] for h in d["a_hyps"]}
    for cond in ("b", "c"):
        key = f"{cond}_hyps"
        if key not in d:
            continue
        hyp_other = {h["id"]: h["hyp"] for h in d[key]}
        a_wrong_other_right = []
        a_right_other_wrong = []
        for cid, hyp_o in hyp_other.items():
            if cid not in hyp_a:
                continue
            r = rows[cid]
            for term in r["terms"]:
                hit_a = term_hit(term, hyp_a[cid])
                hit_o = term_hit(term, hyp_o)
                if not hit_a and hit_o:
                    a_wrong_other_right.append((cid, term, r["text"], hyp_a[cid], hyp_o))
                elif hit_a and not hit_o:
                    a_right_other_wrong.append((cid, term, r["text"], hyp_a[cid], hyp_o))
        print(f"\n=== condition ({cond}) vs (a), model={d['model_size']} ===")
        print(f"(a) wrong, ({cond}) right: {len(a_wrong_other_right)} instances; showing up to 10")
        for cid, term, ref, ha, ho in a_wrong_other_right[:10]:
            print(f"  [{cid}] term={term!r}\n    ref: {ref}\n    (a): {ha[:150]}\n    ({cond}): {ho[:150]}")
        print(f"(a) right, ({cond}) wrong: {len(a_right_other_wrong)} instances; showing up to 10")
        for cid, term, ref, ha, ho in a_right_other_wrong[:10]:
            print(f"  [{cid}] term={term!r}\n    ref: {ref}\n    (a): {ha[:150]}\n    ({cond}): {ho[:150]}")


if __name__ == "__main__":
    main()
