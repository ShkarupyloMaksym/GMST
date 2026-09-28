id: F.14
title: Prompt only with committed text whose audio has left the buffer
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.1.1

# F.14 — Prompt only with committed text whose audio has left the buffer

## Instructions

Fix X.1.1's finding within DECIDE-01 (it aligns the implementation with UFAL, which the decision
names; not a new decision).

## What was read / measured

Regression test `test_stream_pipeline.py::test_the_prompt_never_contains_words_still_in_the_buffer`
(no decode's prompt contains the first word of the audio it decodes): fails with the old prompt
(`git stash` of `stream.py`: 1 failed), passes with the fix. Suite 197 passed; ruff clean.

## Findings

- `run_stream.decode`: the prompt tail is `committed[:-len(agree.committed)]` — the session's
  committed words minus the anchor words still in the buffer. CLAUDE.md "Streaming
  reconciliation" and PLAN.md's edge-case table say so.

## Could not check

The real-model effect is X.1b's (pre-registered rule unchanged).

FINDING: recorded
