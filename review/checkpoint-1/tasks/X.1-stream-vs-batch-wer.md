id: X.1
title: EVID-01: stream vs batch WER after the re-anchoring fix
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.8

# X.1 — EVID-01: stream vs batch WER after the re-anchoring fix

## Instructions

Extend R1's `scripts/R1/probe_real_model_contradictions.py` into `scripts/X.1/`: for the first 20 clips of `eval/results/data/en` and of `uk` (language pinned) and the first 20 `mixed` inter clips (auto LID), run batch and `run_stream` with shipped defaults, `small` then `large-v2`. Report corpus WER per set and mode, contradicted-push share, and 5 sample stream outputs.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.1/`. Write the clip list to `scripts/X.1/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
