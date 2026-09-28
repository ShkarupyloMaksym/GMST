id: F.4
title: Backends: mlx dependency, eager load, warmup hint
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.4 — Backends: mlx dependency, eager load, warmup hint

## Instructions

- **FIX-15** declare `mlx-whisper` as a pinned optional extra with a `sys_platform == 'darwin'` marker; wrap `ImportError` in `load_engine` as `ModelUnavailable` (exit 2) with an install hint.
- **FIX-16** `MlxWhisperEngine.__init__` loads the model (via `_load()`), so a missing repo fails at startup with exit 2 and bench's load time is real. Verification on hardware is MAC-01.
- **FIX-17** attach the "run `gmst warmup`" hint only to not-cached / offline errors.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

Tests (`tests/test_backends.py`, 3) written first; committed with the code in `61faa68` after a
classifier outage delayed the run (176 passed then). The dependency half of FIX-15 needed network:
`uv add --optional mac "mlx-whisper; sys_platform == 'darwin' and platform_machine == 'arm64'"`
resolved `mlx-whisper 0.4.3`, then pinned to `==0.4.3` and `uv lock` re-run. On Linux the marker
keeps it out of the environment; the suite is unchanged.

## Findings

- **FIX-15** `[project.optional-dependencies] mac = ["mlx-whisper==0.4.3 ; darwin arm64"]`
  (`uv sync --extra mac` on the Mac — README and the `ModelUnavailable` message say so); a missing
  install is `ModelUnavailable` / exit 2 (`61faa68`).
- **FIX-16** `MlxWhisperEngine.__init__` calls `_load()` (`61faa68`).
- **FIX-17** warmup hint only on `OSError` (`61faa68`).

## Could not check

Whether 0.4.3's `ModelHolder.get_model(repo, mx.float16)` exists and shares the transcribe cache is MAC-01; the eager load's startup cost on the Mac is MAC-03.

FINDING: recorded
