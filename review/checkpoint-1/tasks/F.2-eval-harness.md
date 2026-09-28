id: F.2
title: Eval harness: cache key, corpus WER, CIs, mixed clips, metrics
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
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

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, per FIX id, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
