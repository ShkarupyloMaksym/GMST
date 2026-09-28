id: R4
title: Test-suite adequacy
parent: -
stage: review
kind: task
agent: code-reviewer
model: sonnet
effort: medium
status: todo
depends-on: -

# R4 — Test-suite adequacy

## Instructions

Audit `tests/` (136 fast tests + 4 slow) against what `PLAN.md` "Testing" and "`reconcile.py` edge cases (each has a test)" promise. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

For each promised test, name the test that covers it or record that none does. Own the onboarding lead: `tests/fixtures/en.wav` / `uk.wav`. Then check that the tests would actually fail if the code were wrong: for the five riskiest guards (your pick, justified — start with `_align`'s −1 on contradiction, the overlap anchor, `trim_to`/`rebase`, the unconditional `sink.close()`, and the drop-oldest queue), apply a one-line mutation in a **scratch copy** of the tree (never the working tree), run the suite there, and record whether it goes red. Save the mutations and outputs in `scripts/R4/`. Run `uv run pytest -m slow` once (offline) and record the result.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
