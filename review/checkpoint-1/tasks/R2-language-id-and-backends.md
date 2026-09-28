id: R2
title: Language ID and engine backends
parent: -
stage: review
kind: task
agent: code-reviewer
model: opus
effort: high
status: todo
depends-on: -

# R2 — Language ID and engine backends

## Instructions

Review `src/gmst/transcribe/lid.py`, `engine.py`, `types.py`, and every backend under `transcribe/backends/` (`faster_whisper.py`, `mlx_whisper.py`, the `load_engine` factory) against `CLAUDE.md` "Language mixture" and `PLAN.md` "Language ID" / "ASR engine". Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Own the onboarding lead in `review/checkpoint-1/PLAN.md`: does `resolve_language` ever restrict the detector to the meeting's languages, and what does GMST do when the top label is `bg`, `ja`, `be`, `pl`…? Confirm with a probe on the local clips (`eval/results/data/uk/`, offline, `tiny` and `small` only — rule 4), saved in `scripts/R2/`. Also check: the sticky threshold and uk/ru tie-break compose as the module docstring says; the ≥ 0.5 s LID window around a segment; `multilingual=True` is only requested when `per_segment_lid` is off; `vad_filter=False` on every streaming call; `no_speech_threshold` and temperature fallback left on; `ModelUnavailable` carries "run `gmst warmup`". For `mlx_whisper.py`, read for bugs visible without running it (the `ModelHolder.get_model` reuse and the release in `gmst bench` are open Mac items — record, don't run).

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
