id: F.10
title: DECIDE-03 fix: batch decodes each VAD region in its own language
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.10 — DECIDE-03 fix: batch decodes each VAD region in its own language

## Instructions

Implement PLAN.md "Review decisions" DECIDE-03: with `per_segment_lid` on and no pinned language, batch VAD-splits the file (`segment/vad.py`), detects each region's language via `detect_language` (F.9's restriction, sticky across regions) and decodes each region with that `language`; timestamps offset to file time. Same for `mlx_whisper`. `eval/run_eval.py`'s `gmst-batch` then measures GMST, not raw autodetect. Test: a `FakeEngine` batch run with two regions of different scripted languages decodes each with its own `language`.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; commit with an
explicit pathspec. Items and evidence: T1's triage table; the decision: root PLAN.md "Review
decisions".

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
