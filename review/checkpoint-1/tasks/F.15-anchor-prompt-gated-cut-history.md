id: F.15
title: Keep the anchor in the prompt; gate the time cut by resemblance; check repeats against history
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.1b.1

# F.15 — Keep the anchor in the prompt; gate the time cut by resemblance; check repeats against history

## Instructions

Implement X.1b.1's E+H variant; supersede F.14 (still DECIDE-01: LocalAgreement-2 with UFAL-style
time and n-gram alignment).

## What was read / measured

Tests: `test_reconcile.py::test_a_rehearing_of_words_trimmed_out_of_the_anchor_is_not_committed_twice`
(re-heard phrase timed after the committed end, so only the text history can catch it) and
`::test_the_time_cut_only_drops_words_that_resemble_committed_ones` — both fail on F.14's
`reconcile.py`, pass on F.15's. `test_stream_pipeline.py::test_the_prompt_never_contains_words_still_in_the_buffer`
removed with F.14's prompt rule. The n-gram test's filler "uh" became "aa" (a mis-hearing of "a"):
an unrelated filler is now correctly kept as speech. Suite 198 passed; ruff clean.

## Findings

- `stream.py`: back to the pre-F.14 prompt (anchor included), byte-identical to `0dfd92a`.
- `reconcile.py`: `_history` (last 5 committed words, survives `rebase`, cleared by `reset`) for
  the text and n-gram checks; the time cut requires `_resembles` (SequenceMatcher ≥ 0.5, set once,
  not tuned). Docstring rewritten.
- CLAUDE.md "Streaming reconciliation", PLAN.md edge-case table: F.14's rule struck with a dated
  note.

## Could not check

Real-model evidence is X.1c's.

FINDING: recorded
