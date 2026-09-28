id: X.1c
title: EVID-01 after F.15, on the original clips and on unseen clips
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.15

# X.1c — EVID-01 after F.15, on the original clips and on unseen clips

## Instructions

X.1b.1 iterated on X.1's 20+20 clips, so they are no longer a clean test. Pre-registered here
(2026-09-28, before running): EVID-01's rule, unchanged — stream ≤ batch + 3.0 pts on en and uk
with `small`, contradicted pushes ≤ 10 % — evaluated on **(a)** X.1's clips (manifest rows 0–19)
and **(b)** unseen clips (manifest rows 20–39 of `en.jsonl` / `uk.jsonl`); the verdict is (b)'s.
Run each stream **twice** and report both (Ukrainian decoding was non-deterministic under F.14).
Then `large-v2` on (b) en and uk, once, within ~60 min. Copy `scripts/X.1/run_wer.py` to
`scripts/X.1c/` adding only a row-offset option and output paths; save full outputs. Read first:
root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`, `tasks/V1-*.md`, `tasks/X.1*.md`, this file.
Offline, one large model at a time (`pgrep -af python` first), main tree `.venv`, no clone; write
only this node file and `scripts/X.1c/`.

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
