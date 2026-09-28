id: X.1b
title: EVID-01 re-measured after F.14 (same pre-registered rule)
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.14

# X.1b — EVID-01 re-measured after F.14 (same pre-registered rule)

## Instructions

Re-run `scripts/X.1/run_wer.py` unchanged (copy it to `scripts/X.1b/` first, adding only output
paths) on the same clips with `small` then `large-v2`, en and uk (language pinned); mixed with
`small` only (auto LID, now after F.11 and F.14). Report against V1's EVID-01 rule, unchanged:
holds if stream ≤ batch + 3.0 pts on en and uk with small and contradicted pushes ≤ 10 %. Also save
the full stream output text per set. Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`,
`tasks/V1-evidence-plan.md`, `tasks/X.1-*.md`, `tasks/X.1.1-*.md`, this file. Offline; you are the
only process loading models; work from the main tree's `.venv` (no clone); write only this node
file and `scripts/X.1b/`.

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
