id: F.19
title: Default model large-v3-turbo (DECIDE-10)
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: X.3

# F.19 — Default model large-v3-turbo (DECIDE-10)

## Instructions

Set the default per the user's DECIDE-10 and replace every "provisional large-v3" statement.

## What was read / measured

`config.py` default, `test_config.py::test_defaults_when_no_file`, `gmst.example.toml`, PLAN.md
config table + "Review decisions", CLAUDE.md ("Model default is provisional" rewritten as "Default
model" with X.3's table), README status. Suite 203 passed; ruff clean. faster-whisper maps
`large-v3-turbo` to `mobiuslabsgmbh/faster-whisper-large-v3-turbo` (cached by X.3).

## Findings

- Default `model_size = "large-v3-turbo"`; the leaderboard ranking no longer cited as guidance.

## Could not check

Two-pass streaming with turbo (X.1d used small / large-v2) — follow-up measurement.

FINDING: recorded
