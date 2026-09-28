id: F.9
title: DECIDE-02 fix: `lid_languages`, restricted and renormalised LID
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.9 — DECIDE-02 fix: `lid_languages`, restricted and renormalised LID

## Instructions

Implement PLAN.md "Review decisions" DECIDE-02: config field `lid_languages` (default `["en", "uk"]`, validated in `_merge`, env `GMST_LID_LANGUAGES` comma-separated, documented in `gmst.example.toml` and PLAN.md's config table). `resolve_language` renormalises `all_probs` over the allowed set with `ru` folded into `uk`, so the first utterance is covered; the sticky threshold applies to the renormalised probability. Tests: R2's cases (`bg`, `ja`, `tr`, `ar` top-1 on Ukrainian; first utterance at 0.21) in `test_lid.py`.

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
