id: F.10
title: DECIDE-03 fix: batch decodes each VAD region in its own language
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.10 — DECIDE-03 fix: batch decodes each VAD region in its own language

## Instructions

Implement PLAN.md "Review decisions" DECIDE-03: with `per_segment_lid` on and no pinned language, batch VAD-splits the file (`segment/vad.py`), detects each region's language via `detect_language` (F.9's restriction, sticky across regions) and decodes each region with that `language`; timestamps offset to file time. Same for `mlx_whisper`. `eval/run_eval.py`'s `gmst-batch` then measures GMST, not raw autodetect. Test: a `FakeEngine` batch run with two regions of different scripted languages decodes each with its own `language`.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; commit with an
explicit pathspec. Items and evidence: T1's triage table; the decision: root PLAN.md "Review
decisions".

## What was read / measured

Read `pipeline/batch.py`, `segment/vad.py`, both backends' `transcribe`, `tests/fakes.py`,
`eval/run_eval.py:80-100`. Test first, watched fail:
`test_batch_pipeline.py::test_batch_decodes_each_speech_region_in_its_own_language` (a fake whose
LID reads amplitude: en region, 1 s silence, uk region). Added
`::test_batch_with_a_pinned_language_decodes_the_file_once`. The existing
`test_run_batch_marks_final_and_reports_rtf` fed zeros with no pinned language; it now pins `en`
(it tests final-marking and RTF, and silence correctly yields no regions). `uv run pytest -q`: 162
passed; `ruff check .` clean.

Real model, `tiny`, auto LID, two `eval/results/data/mixed` inter clips (`uv run gmst batch`):
`mix-inter-000` → `(en) He refused at first to listen to the careful advice…` then
`(uk) Це буде абсолютно гармальний прав, я.`; `mix-inter-002` → `(uk) Навіщий, коли ти назавтра…`
then `(en) But in the rest of the work…`. Both switches found and decoded in the right script (R5
recorded `switch_detected 0/4` for every system before).

## Findings

- `pipeline/batch.py`: `speech_regions` (VAD, merged across gaps < `min_silence_ms`, padded
  0.2 s) and `transcribe_by_region` (pinned → one whole-file call; otherwise per region
  `detect_language` with the previous region's language as `prev_lang`, then `transcribe` in that
  language, times offset to the file). `run_batch` uses it. Backend-agnostic, so `mlx_whisper`
  gets it too.
- `eval/run_eval.py`: `gmst-batch` runs `transcribe_by_region`, so it measures GMST and not raw
  autodetect (R2 F3 / R5); its docstring line was also FIX-10's E501.
- `faster_whisper.py` docstring: the `per_segment_lid` relabel path is label-only and unused by
  both pipelines.
- Docs: CLAUDE.md pipeline line, PLAN.md module layout.

## Could not check

A switch inside one unbroken region (no pause ≥ `min_silence_ms`) is still decoded in the region's first language — LID reads the region's first 30 s. That is the intra-sentence case CLAUDE.md already calls unsolved. The scores in `eval/results/scores.json` predate this and are stale for `gmst-batch`.

FINDING: recorded
