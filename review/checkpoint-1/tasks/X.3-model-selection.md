id: X.3
title: EVID-03: model selection on the full cleaned CV10 uk set
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.2

# X.3 — EVID-03: model selection on the full cleaned CV10 uk set

## Instructions

After F.2's harness fixes: build the full cleaned-CV10 `uk` set (3204) and a 500-clip LibriSpeech test-clean `en` set, language pinned, `gmst-batch` path. Candidates `large-v2`, `large-v3`; ask the user before downloading `large-v3-turbo` / `Yehor/whisper-large-v3-turbo-quantized-uk`. Report corpus WER with bootstrap CIs and pairwise paired-bootstrap CIs. Expect hours per model on CPU: run overnight, one model at a time, resumable.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.3/`. Write the clip list to `scripts/X.3/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
