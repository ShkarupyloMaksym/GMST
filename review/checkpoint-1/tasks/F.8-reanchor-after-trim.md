id: F.8
title: DECIDE-01 fix: trim before the last committed word; timestamp-based anchoring
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.8 — DECIDE-01 fix: trim before the last committed word; timestamp-based anchoring

## Instructions

Implement PLAN.md "Review decisions" DECIDE-01. `Endpointer.trim_to` cuts at the last committed word's *start* minus the back-off (fix the docstring). `LocalAgreement` anchors by timestamps: hypothesis words ending at or before the last committed word's end (buffer-relative) are dropped, then an up-to-5-word n-gram overlap with the committed tail is removed; a contradiction is no longer terminal for the utterance. Regression tests first: extend `_marked` to sub-0.2 s marks (or a fake that drops/mis-hears the sliver, as R1's `probe_trim_fragment.py` does) so the current code goes red; R1's fragment/dropped probes must show `lost 0/24`. Keep both CLAUDE.md seam invariants and their existing tests green. Then X.1 measures it with a real model.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; commit with an
explicit pathspec. Items and evidence: T1's triage table; the decision: root PLAN.md "Review
decisions".

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
