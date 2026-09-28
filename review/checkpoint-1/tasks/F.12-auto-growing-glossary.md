id: F.12
title: DECIDE-08 fix: config-enabled, auto-growing term glossary
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: todo
depends-on: T1

# F.12 — DECIDE-08 fix: config-enabled, auto-growing term glossary

## Instructions

Implement DECIDE-08. Config: `glossary` (list of terms, default empty), `glossary_autogrow` (bool, default false), `glossary_path` (optional file the grown list persists to, one term per line), `glossary_max_terms` (cap, default 100). Every decode (batch and stream) passes the glossary to the engine: as a leading part of `initial_prompt` (before the committed-text tail, within the existing 600-character cap — terms first) and, for faster-whisper, as `hotwords`. Autogrow adds Latin-script tokens of ≥ 2 letters that appear in *committed* text (they are what the model already got right, so later occurrences stay consistent), de-duplicated case-insensitively, most-recent kept under the cap, written to `glossary_path` on sink close. Off by default and fully removable for speed (the user's words). Extend the `Engine` protocol only if needed (a `hotwords` keyword with a default keeps `FakeEngine` and mlx compatible). Tests: prompt contains the terms; autogrow picks up `deploy` from a committed Ukrainian sentence and not Cyrillic words; the cap holds; disabled → prompt unchanged. X.5's terms set, when built, measures term recall with and without it.

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
