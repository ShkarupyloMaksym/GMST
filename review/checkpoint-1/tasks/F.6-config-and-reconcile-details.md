id: F.6
title: Config and reconcile details: sse_port 0, empty tokens, prompt cap
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.6 — Config and reconcile details: sse_port 0, empty tokens, prompt cap

## Instructions

- **FIX-21** allow `sse_port = 0` (range 0–65535) and test it.
- **FIX-22** a token that normalises to empty is skipped in agreement rather than blocking it (R1 `probe_punct_token.py`).
- **FIX-23** cap the prompt by Whisper tokens (the engine's tokenizer) or restate the cap honestly in CLAUDE.md/PLAN.md/`stream.py:41` (R1 `probe_prompt_tokens.py`).

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

Tests first, 3 watched fail: `test_config.py::test_sse_port_zero_means_any_free_port` (R6's
`ValueError`), `test_reconcile.py::test_a_punctuation_only_token_does_not_block_agreement` (R1's
`-` case), `test_stream_pipeline.py::test_the_prompt_fits_whispers_prompt_window_in_ukrainian`
(R1's 235 tokens per 600 Ukrainian characters vs faster-whisper's 223). After: 190 passed, ruff
clean.

## Findings

- **FIX-21** `sse_port` range 0–65535.
- **FIX-22** agreement compares normalized tokens directly, so two punctuation-only tokens agree
  instead of blocking the rest of the hypothesis. A lone `-` against a word still breaks the run.
- **FIX-23** `_PROMPT_CHARS` 600 → 560 (≈ 219 tokens in Ukrainian at R1's measured rate), shared
  by batch's glossary prompt; CLAUDE.md, PLAN.md, `stream.py` and `reconcile.py` docstrings say
  560 and why.

## Could not check

The 0.39 tokens/char rate is R1's single measurement on one Ukrainian sample; a very term-dense prompt could exceed it. faster-whisper then trims from the front, which drops the oldest committed text first — the glossary sits at the front, so an over-long prompt would lose terms first. Not measured.

FINDING: recorded
