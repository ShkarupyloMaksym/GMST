id: X.3
title: EVID-03: model selection on the full cleaned CV10 uk set
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: in-progress
depends-on: F.2

# X.3 — EVID-03: model selection on the full cleaned CV10 uk set

## Instructions

After F.2's harness fixes: build the full cleaned-CV10 `uk` set (3204) and a 500-clip LibriSpeech test-clean `en` set, language pinned, `gmst-batch` path. Candidates `large-v2`, `large-v3`; ask the user before downloading `large-v3-turbo` / `Yehor/whisper-large-v3-turbo-quantized-uk`. Report corpus WER with bootstrap CIs and pairwise paired-bootstrap CIs. Expect hours per model on CPU: run overnight, one model at a time, resumable.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.3/`. Write the clip list to `scripts/X.3/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

**Amended 2026-09-28 (user, before any X.3 run):** scope is **800** cleaned-CV10 `uk` clips (first
800 in a fixed seed-0 shuffle, written to `scripts/X.3/clips.txt` first) and the same 500 `en`
clips, candidates `large-v2`, `large-v3`, `large-v3-turbo`, `Yehor/whisper-large-v3-turbo-quantized-uk`
— downloads approved for the two turbo models (faster-whisper maps `large-v3-turbo` to
`mobiuslabsgmbh/faster-whisper-large-v3-turbo`, already partly cached; check whether the turbo-uk
repo is CTranslate2-loadable, and convert with `ct2-transformers-converter` into
`eval/results/models/` if it is not). Per R5 this resolves large-v2 vs large-v3 (~73 paired clips)
and large-v3 vs turbo (~761) but **not** turbo-uk vs large-v2 (~2,893): report that pair's CI
as-is, with no ranking claimed unless it excludes 0. The pre-registered rule is otherwise
unchanged. Runs after X.1 and X.4 (one large model at a time); overnight.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
