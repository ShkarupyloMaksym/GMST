id: F.6
title: Config and reconcile details: sse_port 0, empty tokens, prompt cap
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.6 — Config and reconcile details: sse_port 0, empty tokens, prompt cap

## Instructions

- **FIX-21** allow `sse_port = 0` (range 0–65535) and test it.
- **FIX-22** a token that normalises to empty is skipped in agreement rather than blocking it (R1 `probe_punct_token.py`).
- **FIX-23** cap the prompt by Whisper tokens (the engine's tokenizer) or restate the cap honestly in CLAUDE.md/PLAN.md/`stream.py:41` (R1 `probe_prompt_tokens.py`).

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
