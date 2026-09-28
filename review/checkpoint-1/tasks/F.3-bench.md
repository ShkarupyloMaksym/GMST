id: F.3
title: Bench: shipped decode mode, UK/EN WER, amplification, exit code, warmup
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.3 — Bench: shipped decode mode, UK/EN WER, amplification, exit code, warmup

## Instructions

- **FIX-11** bench decodes through the shipped path (per-utterance LID via `detect_language`, or `run_stream` over the clip) and reports UK and EN WER separately when given per-language references.
- **FIX-12** exit 2 when no candidate produced a row.
- **FIX-13** amplification from measured wall time per decode of a typical-length buffer plus the LID pass, divided by `update_interval` (R5 `p4_amplification.py`); PLAN.md latency budget amended after EVID-04.
- **FIX-14** `gmst warmup --bench` downloads bench's candidates; README says so.

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
