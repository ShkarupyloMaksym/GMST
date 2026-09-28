id: F.1
title: Shutdown and CLI errors: SIGTERM, second Ctrl-C, --config traceback
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.1 — Shutdown and CLI errors: SIGTERM, second Ctrl-C, --config traceback

## Instructions

- **FIX-01** install the SIGINT handler for SIGTERM too (`cli.py:169-188`); test: SIGTERM to a child running `run_stream` over a `ListSource` flushes and closes the sink (R3 `sigterm_probe.py`).
- **FIX-02** a second Ctrl-C must abandon the final decode (`stream.py:191-195` finally path) and still close the sink; catch `KeyboardInterrupt` in `_cmd_stream` (R1 `probe_second_ctrl_c.py`).
- **FIX-03** `main()` turns a missing `--config` into a one-line error, exit 1.

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
