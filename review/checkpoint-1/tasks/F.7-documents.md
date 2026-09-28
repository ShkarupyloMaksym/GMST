id: F.7
title: Documents: Linux routing, eval, LID cost, stale claims
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
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

FIX-24, -25a, -25b, -26 landed in `8ea0f79` (after a classifier outage); DECIDE-07's CI claim in
`fed803c` (F.13). FIX-27 waited for X.1d, done here.

## Findings

- **FIX-24** README: system PortAudio; the Meet monitor on Linux via `PULSE_SOURCE` / pavucontrol.
- **FIX-25a** PLAN loopback row amended (exit 1 + routing pointer, printed by `stream`).
- **FIX-25b** `eval/` in PLAN's layout and CLAUDE.md's commands; `canary.py` marked not created.
- **FIX-26** LID is a separate encoder pass on both backends (PLAN, `engine.py`, latency table).
- **FIX-27** the "verified end-to-end … clean ordered transcript" claims in CLAUDE.md and PLAN.md
  struck and replaced with X.1d's measured numbers.

## Could not check

The Linux monitor-routing steps are documented as not yet validated end-to-end.

FINDING: recorded
