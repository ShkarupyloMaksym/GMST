id: X.4
title: EVID-04: per-update decode cost and LID cost, large models on CPU
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: -

# X.4 — EVID-04: per-update decode cost and LID cost, large models on CPU

## Instructions

Extend R5's `scripts/R5/p4_amplification.py` into `scripts/X.4/`: `large-v2` then `large-v3`, CPU int8, buffers 2/4/8/15 s cut from `eval/results/data/en` speech, 10 repetitions each after 2 warm-up calls, median and p90 wall time; `detect_language` on 3 s. Record `nproc`, threads used, and anything else running.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.4/`. Write the clip list to `scripts/X.4/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
