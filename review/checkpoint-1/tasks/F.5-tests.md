id: F.5
title: Tests: queue content, real-audio fixtures, env isolation
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
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

- **FIX-18** `test_bounded_queue_drops_oldest` now feeds blocks at levels 0.0…0.4 and asserts the
  three survivors are the most recent. Checked against R4's mutation 5 (drop-newest) applied by
  text replacement in a scratch copy: `1 failed, 8 passed` (R4 measured `9 passed` before).
  (The diff in `scripts/R4/` uses absolute scratch paths and does not `patch` cleanly.)
- **FIX-19** fixtures chosen by running tiny `detect_language` over 3–5.5 s clips of the eval sets:
  `en-260-123440-0014` (3.8 s, `en` 0.99) and `uk-2023` (4.8 s, `uk` 0.86 restricted — R2 recorded
  Whisper decoding it as Russian, so it pins the ru→uk fold). `tests/test_lid_fixtures_slow.py`:
  `HF_HUB_OFFLINE=1 uv run pytest -m slow tests/test_lid_fixtures_slow.py` → 2 passed.
  `tests/fixtures/README.md` records source, licence (LibriSpeech CC BY 4.0, Common Voice CC0).
- **FIX-20** `tests/conftest.py` autouse fixture removes every `GMST_*` variable;
  `GMST_MODEL=tiny uv run pytest -q tests/test_config.py` → 23 passed (R7: 1 failed).
Full suite: 187 passed, 6 deselected; ruff clean.

## Findings

See above; one commit for the three.

## Could not check

Nothing.

FINDING: recorded
