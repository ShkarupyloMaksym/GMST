id: R6
title: Documents vs code
parent: -
stage: review
kind: task
agent: doc-consistency-auditor
model: sonnet
effort: medium
status: todo
depends-on: -

# R6 — Documents vs code

## Instructions

Read `CLAUDE.md`, `PLAN.md`, `README.md` and `gmst.example.toml` as a new session would, and check every factual claim they make about the code: module layout, config fields and defaults (the table in `PLAN.md` "Config" vs `src/gmst/config.py`), env vars, exit codes, phase status, CLI flags (`uv run gmst <cmd> --help`), the test count, and the Commands section. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Every disagreement is a finding with both locators. Own the onboarding leads on `eval/` being undocumented and the ruff E501. Also list anything a new user would need to run it on Linux (the PulseAudio/PipeWire monitor source) that the README does not say.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
