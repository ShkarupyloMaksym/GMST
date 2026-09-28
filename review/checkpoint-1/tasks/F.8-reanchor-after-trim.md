id: F.8
title: DECIDE-01 fix: trim before the last committed word; timestamp-based anchoring
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.8 — DECIDE-01 fix: trim before the last committed word; timestamp-based anchoring

## Instructions

Implement PLAN.md "Review decisions" DECIDE-01. `Endpointer.trim_to` cuts at the last committed word's *start* minus the back-off (fix the docstring). `LocalAgreement` anchors by timestamps: hypothesis words ending at or before the last committed word's end (buffer-relative) are dropped, then an up-to-5-word n-gram overlap with the committed tail is removed; a contradiction is no longer terminal for the utterance. Regression tests first: extend `_marked` to sub-0.2 s marks (or a fake that drops/mis-hears the sliver, as R1's `probe_trim_fragment.py` does) so the current code goes red; R1's fragment/dropped probes must show `lost 0/24`. Keep both CLAUDE.md seam invariants and their existing tests green. Then X.1 measures it with a real model.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; commit with an
explicit pathspec. Items and evidence: T1's triage table; the decision: root PLAN.md "Review
decisions".

## What was read / measured

Read `reconcile.py` (all), `stream.py:100-215`, `endpointer.py:80-92`, R1's
`probe_trim_fragment.py` and `probe_real_model_contradictions.py`. Tests first, watched fail (5):
`test_reconcile.py::test_a_misheard_anchor_word_does_not_block_the_utterance`,
`::test_a_dropped_anchor_word_does_not_block_the_utterance`,
`::test_a_repeated_committed_ngram_timed_past_the_boundary_is_not_committed_again`,
`test_stream_pipeline.py::test_a_misheard_or_dropped_trim_sliver_loses_and_duplicates_nothing[fragment|dropped]`
(R1's fake engines at shipped defaults). Added after the trace below:
`::test_a_new_word_stretched_back_to_the_buffer_head_is_kept`, and
`::test_absorb_commits_a_contradicting_tail_rather_than_dropping_it` (absorb had no unit test).

Iterations, each measured (`scripts/F.8/`, tiny, R1's 6 LibriSpeech clips, 81 s, shipped defaults;
X.2 was running `small`/`large-v2` LID concurrently, so no timings are quoted):
1. start-based time cut, tolerance 0.1 (UFAL's rule): stream WER 0.183 vs batch 0.061, 0/78
   contradicted (`tiny6.out`). Trace (`debug_push_trace.out`): after the trim Whisper skips the
   anchor and stretches the first *new* word to 0.00 ("for@0.00-0.56", committed end 0.42), so
   start-based cutting drops it — and PLAN.md's DECIDE-01 text says *end*, so the code had
   deviated from the decision.
2. end-based cut, tolerance 0.1: "would@0.00-0.44" vs committed end 0.38 still dropped
   (`debug_push_trace_endrule.out`); a 0.1 s word right after a commit likewise (stream test).
3. end-based cut, tolerance 0.02 (timestamp resolution): traced clip word-perfect
   (`debug_push_trace_tol002.out`); stream WER **0.091** vs batch 0.061, 0/78 contradicted, 0
   flush-dropped (`tiny6_tol002.out`). Before the fix, R1 measured 0.873 on the same set.
R1's `probe_trim_fragment.py` (unchanged): `lost 0/24`, no duplicates, in all three variants
(was 21/24). `uv run pytest -q`: 147 passed; `ruff check src tests` clean.

## Findings

- `Endpointer.trim_to` is called with the last committed word's **start** (docstring corrected).
- `LocalAgreement.push/absorb/rebase` take optional word `spans`; `_align` falls back from text to
  time (drop words ending ≤ committed end + 0.02 s) and then a ≤ 5-word n-gram de-dup. Text-only
  callers keep the old contradiction semantics, so every earlier reconcile test is unchanged.
- `run_stream` passes spans everywhere and shifts them by the cut on both rebase paths.
- `test_shutdown_flush_keeps_a_contradicting_tail_instead_of_dropping_it` was rewritten as
  `..._keeps_a_revised_tail_...`: its fake timed the new words over committed audio, which the
  time rule rightly treats as re-heard. The no-drop guarantee is now also a unit test on `absorb`.
- Docs: CLAUDE.md "Streaming reconciliation", PLAN.md latency paragraph, failure-mode and edge-case
  rows. FIX-27 (the "verified end-to-end" claim) waits for X.1.

## Could not check

Real-model numbers above are `tiny` on 81 s of English only — X.1 is the pre-registered measurement (`small`, `large-v2`; en, uk, mixed).

FINDING: recorded
