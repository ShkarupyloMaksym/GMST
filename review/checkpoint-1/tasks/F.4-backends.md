id: F.4
title: Backends: mlx dependency, eager load, warmup hint
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
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

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, per FIX id, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
