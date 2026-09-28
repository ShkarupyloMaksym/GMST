id: R1
title: Streaming seams: reconcile, endpointer, stream loop, turns
parent: -
stage: review
kind: task
agent: code-reviewer
model: opus
effort: high
status: todo
depends-on: -

# R1 — Streaming seams: reconcile, endpointer, stream loop, turns

## Instructions

Review line by line `src/gmst/reconcile.py`, `src/gmst/segment/endpointer.py`, `src/gmst/segment/turns.py` and `src/gmst/pipeline/stream.py` against the invariants in `CLAUDE.md` ("Streaming reconciliation") and `PLAN.md` ("`reconcile.py` edge cases", "`Segment` timestamp contract", the Ctrl-C and forced-commit rows of "Failure modes"). Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

What counts as a finding: any input sequence that (a) commits a word twice, (b) makes committed spans non-monotonic, (c) re-commits a revised prefix, (d) loses text that was committed or was flushable at shutdown, (e) lets the real buffer grow past one utterance because the trim/rebase is skipped, or (f) writes to the sink from a thread other than the reconcile thread. Demonstrate each with a probe in `scripts/R1/` built on `tests/fakes.py` and the audio-reactive `_marked` / `_marked_engine` helpers in `tests/test_stream_pipeline.py` — a fixed script that ignores the audio it is handed cannot show a seam bug (CLAUDE.md "Testing"). Also check: the 600-character prompt cap, the 4000-word cap, the stall counter using the sample clock not wall time, and the second-Ctrl-C path.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
