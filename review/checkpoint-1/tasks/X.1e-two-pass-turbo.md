id: X.1e
title: EVID-01 for the new default model (large-v3-turbo), two-pass, fresh rows
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: F.19

# X.1e — EVID-01 for the new default model (large-v3-turbo), two-pass, fresh rows

## Instructions

DECIDE-10 made `large-v3-turbo` the default; X.1d verified two-pass streaming with `small` and
`large-v2` only. Pre-registered here (2026-09-29, before running): EVID-01's threshold applied to
the default model — stream (final segments only) ≤ batch + 3.0 pts on en and uk — on rows 40–59
of `en.jsonl` / `uk.jsonl` (X.1d's deciding rows), `large-v3-turbo`, each stream run twice. Also
report any repeated 6-gram not present in the reference and any "www" / "End 1"-style boilerplate.
Copy `scripts/X.1d/run_wer.py` to `scripts/X.1e/` (output paths only). Read first: root
`CLAUDE.md`, `tasks/X.1d-*.md`, this file. Offline (turbo is cached), one large model at a time
(`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.1e/`.

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
