id: X.2
title: EVID-02: LID accuracy vs prefix length, with and without the en/uk restriction
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: -

# X.2 — EVID-02: LID accuracy vs prefix length, with and without the en/uk restriction

## Instructions

For all 60 `uk` and 60 `en` clips, call the model's `detect_language` on prefixes of 1, 2, 3, 4 s and the full clip, `small` then `large-v2`. From each raw distribution compute (a) unrestricted top-1 and (b) restricted = argmax over {en, uk + ru}. Report accuracy per language × prefix × model for both, and the first-utterance case (no prior).

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.2/`. Write the clip list to `scripts/X.2/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
