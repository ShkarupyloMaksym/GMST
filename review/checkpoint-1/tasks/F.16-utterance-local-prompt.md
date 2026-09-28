id: F.16
title: Prompt with the current utterance's committed words only
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.1c.1

# F.16 — Prompt with the current utterance's committed words only

## Instructions

Implement X.1c.1's variant P.

## What was read / measured

Test `test_stream_pipeline.py::test_a_new_utterance_is_not_prompted_with_the_previous_one` (two
utterances told apart by amplitude; no decode of the second may be prompted with the first's word):
fails on F.15's `stream.py`, passes on F.16's. (A first version passed on both — an early,
not-yet-committed decode satisfied it trivially — and was rewritten.) Suite 199 passed; ruff clean.

## Findings

- `run_stream`: `utt_words` (committed words of the current utterance) feeds the prompt; cleared
  at every real endpoint (a forced cut / stall continues the utterance). Glossary terms still lead.
- CLAUDE.md "Streaming reconciliation", PLAN.md edge-case table, `stream.py` docstring.

## Could not check

The pre-registered re-measurement on unseen clips after F.16 is X.1d.

FINDING: recorded
