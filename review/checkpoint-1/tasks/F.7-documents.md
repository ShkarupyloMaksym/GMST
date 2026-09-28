id: F.7
title: Documents: Linux routing, eval, LID cost, stale claims
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.7 — Documents: Linux routing, eval, LID cost, stale claims

## Instructions

- **FIX-24** README Linux: `pactl set-default-source <sink>.monitor` or `PULSE_SOURCE`, and the system PortAudio package.
- **FIX-25a** amend PLAN.md's loopback row to exit 1 plus a routing hint (and print that hint).
- **FIX-25b** document `eval/` (run commands, extra deps) in CLAUDE.md Commands and PLAN.md layout; mark `backends/canary.py` as not created.
- **FIX-26** correct the LID-cost claims (`engine.py:5-6`, PLAN.md:77-79, :98, :128).
- **FIX-27** after DECIDE-01's fix and EVID-01, replace "verified end-to-end … clean ordered transcript" with what EVID-01 measured.
- DECIDE-07's outcome (CI claim) lands here too.

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
