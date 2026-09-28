id: R3
title: Capture, failure modes and shutdown
parent: -
stage: review
kind: task
agent: code-reviewer
model: sonnet
effort: medium
status: todo
depends-on: -

# R3 — Capture, failure modes and shutdown

## Instructions

Walk every row of `PLAN.md` "Failure modes & degradation" and confirm the code implements its policy, citing the `file:line` that does. Files: `src/gmst/audio/{device_source,resample,file_source,types}.py`, `src/gmst/cli.py` (exit codes 0/1/2/3), `src/gmst/sink/{base,console,jsonl,srt,sse}.py`, and the shutdown path in `pipeline/stream.py`. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

A row with no implementation, or an implementation that differs from the policy, is a finding. Specific checks: the capture callback does only downmix → persistent `soxr.ResampleStream` → enqueue; drop-oldest and the `[lagging]` flag reach the sink; PortAudio status flags are counted, not swallowed; `DeviceLost` after the drain → exit 3; `sink.close()` runs even when the final decode raises; the SSE per-client queue is bounded at 512 with drop-oldest and a heartbeat; the JSONL/SSE event schema matches the pinned one. You may run `gmst devices` / `gmst listen` briefly on this Linux machine; BlackHole is rule 6.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
