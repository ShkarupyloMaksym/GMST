id: F.2
title: Eval harness: cache key, corpus WER, CIs, mixed clips, metrics
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: in-progress
depends-on: T1

# F.2 — Eval harness: cache key, corpus WER, CIs, mixed clips, metrics

## Instructions

- **FIX-04** key the hypothesis cache by system *and* model (`hyp/<system>__<model>.jsonl`), write the model into every record, refuse to mix (R5 `p3_cache_mixes_models.py`).
- **FIX-05** corpus WER (total errors / total ref words) plus a bootstrap 95 % CI per set.
- **FIX-06** report `switch_detected`/`lid_recall` as n/a for systems that cannot label segments; rename per-language WER to what it measures (LID × ASR).
- **FIX-07** *intra*: cut at word timestamps; *inter*: gaps ≥ `min_silence_ms` + margin.
- **FIX-08** `--systems X` merges into `scores.json` instead of overwriting.
- **FIX-09** split hyphens in `normalize_words`; record the numerals bias in the docstring.
- **FIX-10** the E501 at `eval/run_eval.py:6` (the line is also wrong: it says large-v3).

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

Read `eval/run_eval.py` (all), `eval/build_sets.py` (all), `src/gmst/metrics.py`,
`tests/test_metrics.py`. Tests first, watched fail: `test_metrics.py::test_wer_splits_hyphenated_words_on_both_sides`,
`::test_word_errors_gives_the_counts_corpus_wer_needs`, and a new `tests/test_eval_harness.py`
(loads `eval/run_eval.py` by path; 5 tests: per-model cache path, refusal of another model's
cache, corpus WER + CI, n/a switch metrics for `fw-*`, merged `scores.json`). After: 169 passed,
`ruff check .` clean. `uv run python eval/run_eval.py --score-only` on the existing caches
reproduces R5's corpus figures (tiny-auto uk corpus 62.07 vs macro 68.21; CI [48.89, 90.0] on 4
clips) — and no longer needs `--with jiwer`.

**Stopped before the rebuild:** `eval/build_sets.py` rewrites `eval/results/data/{en,uk}` too, and
X.2 is reading them. Rebuild the mixed set (`uv run python eval/build_sets.py`) once X.2 reports;
same seed, so `en`/`uk` come out byte-identical and only `mixed` changes.

## Findings

- **FIX-04** `hyp_path`: `hyp/fw-<size>-<mode>.jsonl` / `hyp/gmst-<mode>@<model>.jsonl`; every
  record carries `model`; `cached_ids` raises on another model's records. The legacy
  `hyp/gmst-batch.jsonl` (tiny, pre-F.10, no model field) is never resumed; it is still scored as
  `gmst-batch` by `--score-only` and should be read as stale.
- **FIX-05** corpus WER/CER (`metrics.word_errors`/`char_errors`, no jiwer), seeded bootstrap 95 %
  CI (`wer_ci95`), `wer_macro` kept for comparison; `--compare A,B` gives the paired-bootstrap CI
  of the WER difference (X.3's decision number).
- **FIX-06** mixed set: `wer_en_lid`/`wer_uk_lid` (named for LID × ASR); `lid_recall` None and
  `switch_detected` "n/a" for `fw-*`.
- **FIX-07** `build_sets.py`: inter gaps 800/1000/1200 ms; `intra` replaced by `nopause` ([A][B],
  exact reference); `real_cs` removed (DECIDE-06 covers real code-switched audio). Kinds are read
  from the manifest when scoring.
- **FIX-08** `write_scores` merges by system.
- **FIX-09** `normalize_words` splits hyphens (WER only; `normalize_token` unchanged); numerals
  bias documented in `metrics.py`.
- **FIX-10** done in F.10's commit.

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
