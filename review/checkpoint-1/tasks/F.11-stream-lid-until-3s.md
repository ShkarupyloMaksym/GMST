id: F.11
title: DECIDE-04 fix: stream re-detects until 3 s and holds commits
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.11 — DECIDE-04 fix: stream re-detects until 3 s and holds commits

## Instructions

Implement DECIDE-04 in `run_stream`: while the utterance's buffer holds < `lid_settle_seconds` (new config field, default 3.0, validated) of audio and the language is not pinned, call `detect_language` on every decode (with the previous utterance's language as `prev_lang`) and hold commits — emit partials only; once ≥ 3 s, fix the language for the rest of the utterance and commit normally. An utterance that endpoints before 3 s uses its last detection and commits at the flush. Tests: a `FakeEngine` whose LID says `en` on the first 1–2 s and `uk` from 3 s must commit nothing before 3 s and decode the committed words in `uk`; the pinned-language path must not call LID at all. Also update PLAN/CLAUDE latency text (up to ~3 LID passes per utterance).

Protocol: `verify-then-integrate` skill — regression test first, watch it fail, then fix;
`uv run pytest -q` and `uv run ruff check .` green; commit with an explicit pathspec. The decision:
root PLAN.md "Review decisions".

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(what changed, with the commit)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
