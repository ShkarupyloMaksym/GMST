"""X.6b: score the post-decode glossary correction (F.18) on X.6's no-glossary hypotheses.

No decoding: the corrector only rewrites text. term_hit / score are copied verbatim from
scripts/X.6/run_glossary_eval.py so the metric is identical. Glossary (b') = the 100 most frequent
Latin terms of uk-pods train, **excluding every clip id in terms.jsonl** (X.6's list leaked
179/200); (c') = autogrow only, correct-then-observe over the clips in manifest order.

Run: uv run python review/checkpoint-1/scripts/X.6b/score_correction.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from gmst.glossary import Glossary  # noqa: E402
from gmst.metrics import word_errors  # noqa: E402

DATA = ROOT / "eval/results/data"
RAW = ROOT / "eval/results/raw"
X6 = ROOT / "review/checkpoint-1/scripts/X.6"
_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)
LAT_TOKEN = re.compile(r"[A-Za-z][A-Za-z]+")


def edge_strip(tok):
    return _EDGE.sub("", tok)


def term_hit(term, hyp_text):
    key = edge_strip(term).casefold()
    return any(edge_strip(w).casefold() == key for w in hyp_text.split())


def score(rows, hyp_by_id):
    tt = ht = te = tn = 0
    for r in rows:
        hyp = hyp_by_id[r["id"]]
        hits = [term_hit(t, hyp) for t in r["terms"]]
        tt += len(hits)
        ht += sum(hits)
        e, n = word_errors(r["text"], hyp)
        te += e
        tn += n
    return {"term_recall": ht / tt, "hit_terms": ht, "total_terms": tt, "wer": te / tn}


def static_terms(exclude: set[str]) -> tuple[list[str], int]:
    counts: collections.Counter = collections.Counter()
    surface: dict[str, str] = {}
    n = 0
    for line in (RAW / "uk-pods_pods_train.json").open(encoding="utf-8"):
        d = json.loads(line)
        if Path(d["audio_filepath"]).stem in exclude:
            continue
        n += 1
        for tok in LAT_TOKEN.findall((d.get("text_no_preprocessing") or "").strip()):
            counts[tok.casefold()] += 1
            surface.setdefault(tok.casefold(), tok)
    return [surface[k] for k, _ in counts.most_common(100)], n


def false_positives(rows, before, after):
    """Latin words the corrector inserted that are not reference terms of that clip."""
    out = []
    for r in rows:
        ref = {t.casefold() for t in r["terms"]}
        b = {edge_strip(w).casefold() for w in before[r["id"]].split()}
        for w in after[r["id"]].split():
            k = edge_strip(w).casefold()
            if LAT_TOKEN.fullmatch(edge_strip(w).split()[0] if edge_strip(w) else "") and \
                    k not in b and k not in ref:
                out.append((r["id"], w, before[r["id"]], after[r["id"]]))
    return out


def main():
    rows = [json.loads(x) for x in (DATA / "terms.jsonl").read_text().splitlines() if x.strip()]
    ids = {r["id"] for r in rows}
    terms, n_train = static_terms(ids)
    print(f"static list: {len(terms)} terms from {n_train} train clips (test ids excluded)")
    report = {"static_terms": terms}
    for model, fn in (("small", "results_small_200.json"), ("large-v2", "results_large-v2_100.json")):
        d = json.loads((X6 / fn).read_text())
        a = {h["id"]: h["hyp"] for h in d["a_hyps"]}
        rs = [r for r in rows if r["id"] in a]
        base = score(rs, a)
        g = Glossary(terms, max_terms=100)
        b = {i: g.correct(h) for i, h in a.items()}
        ga = Glossary(autogrow=True, max_terms=100)
        c = {}
        for r in rs:
            c[r["id"]] = ga.correct(a[r["id"]])
            ga.observe(c[r["id"]], lang="uk")
        sb, sc = score(rs, b), score(rs, c)
        fpb, fpc = false_positives(rs, a, b), false_positives(rs, a, c)
        print(f"\n== {model} (n={len(rs)})")
        for name, s in (("(a) none", base), ("(b') static", sb), ("(c') autogrow", sc)):
            print(f"  {name:14s} recall={100 * s['term_recall']:.1f} ({s['hit_terms']}/"
                  f"{s['total_terms']})  WER={100 * s['wer']:.2f}")
        for name, s, fp in (("b'", sb, fpb), ("c'", sc, fpc)):
            dr, dw = 100 * (s["term_recall"] - base["term_recall"]), 100 * (s["wer"] - base["wer"])
            verdict = "HOLDS" if dr >= 10.0 and dw <= 1.0 else "fails"
            print(f"  ({name}) d_recall={dr:+.1f} d_WER={dw:+.2f} -> {verdict}; "
                  f"false positives: {len(fp)}")
            for cid, w, before, after in fp[:8]:
                print(f"     FP {w!r}: {before!r} -> {after!r}")
        changed = [(i, a[i], b[i]) for i in a if a[i] != b[i]]
        print(f"  (b') changed {len(changed)} clips, e.g.:")
        for i, x, y in changed[:6]:
            print(f"     {x!r}\n  -> {y!r}")
        report[model] = {"a": base, "b": sb, "c": sc, "fp_b": len(fpb), "fp_c": len(fpc)}
    (Path(__file__).with_name("scores.json")).write_text(json.dumps(report, ensure_ascii=False,
                                                                    indent=1))


if __name__ == "__main__":
    main()
