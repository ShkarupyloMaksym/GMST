id: F.13
title: DECIDE-05 fix: runtime status to stderr, console and JSONL/SSE; DECIDE-07 CI claim struck
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.13 — DECIDE-05 fix: runtime status to stderr, console and JSONL/SSE; DECIDE-07 CI claim struck

## Instructions

Implement DECIDE-05 (R3's four serious rows + the idle minor) and DECIDE-07 (R6's CI claim).

## What was read / measured

Read `sink/{base,console,jsonl,sse}.py`, `device_source.py` stats API, `stream.py` loop. Tests
first (`tests/test_status.py`, 6): lagging reported and logged, rate-limited; `slow` once after
> 10 s of dropping with the smaller-model hint; `overflow` once; 25 s of silence → exactly one
`idle`; JSONL status line + `TeeSink.status` fan-out; a sink without `status` untouched — 5
watched fail (the last passed before and after). After: 196 passed; `ruff check .` clean.

## Findings

- `stream.py` `_StatusMonitor`: reads `source.stats.blocks_dropped` / `.overflows` every block
  and VAD speech every decode, on the audio clock; events `{"status", "t", "message", ...}` via
  `logging.getLogger("gmst.stream").warning` and the sink's optional `status()`.
- Sinks: `JsonlSink.status` writes the object; `SseSink.status` broadcasts it and the viewer shows
  it in a status bar instead of as a partial; `ConsoleSink.status` prints a line on a TTY only;
  `TeeSink.status` fans out; `SrtSink` has none.
- Docs: PLAN.md failure rows (queues, overflow, falls behind, all-silence), the pinned JSONL/SSE
  schema (status objects), "Review decisions"; CLAUDE.md "Failure modes".
- DECIDE-07: CI sentences struck/removed in CLAUDE.md, PLAN.md, README.

## Could not check

A real overflow / lagging run needs a live device and a slow model; covered by a fake source
whose stats behave like `DeviceSource`'s.

FINDING: recorded
