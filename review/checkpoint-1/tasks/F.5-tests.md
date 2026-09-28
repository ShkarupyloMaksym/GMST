id: F.5
title: Tests: queue content, real-audio fixtures, env isolation
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.5 — Tests: queue content, real-audio fixtures, env isolation

## Instructions

- **FIX-18** `test_bounded_queue_drops_oldest` asserts on block *content* after overflow (R4 `queue_content_probe.py`; mutation 5 must go red).
- **FIX-19** commit short `tests/fixtures/en.wav` (LibriSpeech, CC BY 4.0, credit in the fixtures README) and `uk.wav` (Common Voice, CC0) and a slow test that `detect_language` returns `en`/`uk` on them.
- **FIX-20** an autouse fixture in `tests/conftest.py` clears every `GMST_*` variable.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, per FIX id, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
