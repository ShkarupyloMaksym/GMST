id: X.1d
title: EVID-01 after F.17 (two-pass), on fresh unseen clips
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.17

# X.1d — EVID-01 after F.17 (two-pass), on fresh unseen clips

## Instructions

Rows 0–39 of `en.jsonl` / `uk.jsonl` have all been used for diagnosis. Pre-registered here
(2026-09-28, before running): EVID-01's rule, unchanged — stream ≤ batch + 3.0 pts on en and uk
with `small` — on **fresh rows 40–59**, which decide the verdict. Stream = the **final** segments
only (two-pass semantics). Run each stream twice with `small`; then `large-v2` once on rows 40–59
en and uk (X.1c saw large-v2 hallucinate on English: report whether the finals still contain
"www", "End 1"-style boilerplate); then `small` on the first 20 mixed `inter` and 20 `nopause`
clips (auto LID), reported, not part of the rule. Copy `scripts/X.1c/run_wer.py` to
`scripts/X.1d/` (output paths only). Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`,
`tasks/V1-*.md`, `tasks/X.1*.md`, `tasks/F.17-*.md`, this file. Offline, one large model at a time
(`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.1d/`. If Bash starts failing with a classifier error, record what completed first.

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
