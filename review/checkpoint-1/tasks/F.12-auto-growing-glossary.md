id: F.12
title: DECIDE-08 fix: config-enabled, auto-growing term glossary
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.12 — DECIDE-08 fix: config-enabled, auto-growing term glossary

## Instructions

Implement DECIDE-08. Config: `glossary` (list of terms, default empty), `glossary_autogrow` (bool, default false), `glossary_path` (optional file the grown list persists to, one term per line), `glossary_max_terms` (cap, default 100). Every decode (batch and stream) passes the glossary to the engine: as a leading part of `initial_prompt` (before the committed-text tail, within the existing 600-character cap — terms first) and, for faster-whisper, as `hotwords`. Autogrow adds Latin-script tokens of ≥ 2 letters that appear in *committed* text (they are what the model already got right, so later occurrences stay consistent), de-duplicated case-insensitively, most-recent kept under the cap, written to `glossary_path` on sink close. Off by default and fully removable for speed (the user's words). Extend the `Engine` protocol only if needed (a `hotwords` keyword with a default keeps `FakeEngine` and mlx compatible). Tests: prompt contains the terms; autogrow picks up `deploy` from a committed Ukrainian sentence and not Cyrillic words; the cap holds; disabled → prompt unchanged. X.5's terms set, when built, measures term recall with and without it.

Protocol: `verify-then-integrate` skill — regression test first, watch it fail, then fix;
`uv run pytest -q` and `uv run ruff check .` green; commit with an explicit pathspec. The decision:
root PLAN.md "Review decisions".

## What was read / measured

Tests first (`tests/test_glossary.py`, 8 tests; collection failed before the module existed):
autogrow from Ukrainian text only, case-insensitive de-dup + cap keeping the most recent,
disabled autogrow, persistence round-trip, prompt with terms first inside the cap, config
validation, stream passes prompt + `hotwords`, no glossary → `hotwords=None`. `uv run pytest -q`
187 passed; ruff clean. `faster_whisper` 1.2.1 `WhisperModel.transcribe` has `hotwords` (checked
by `inspect.signature`). `gmst batch` with `glossary = ["Kubernetes", "deploy"]`, tiny, on
`mix-inter-000.wav` runs end to end (term fidelity itself is unmeasured until X.5's set exists).

## Findings

- `gmst/glossary.py`: `Glossary` (`observe`, `prompt`, `hotwords`, `save`) and `make_glossary`.
- Config: `glossary`, `glossary_autogrow`, `glossary_path`, `glossary_max_terms`, all validated.
- `Engine.transcribe` gains `hotwords=None`; faster-whisper passes it through, mlx ignores it,
  `FakeEngine` records it. Callers pass it only with a non-empty glossary, so every existing
  engine and test double stays compatible.
- Stream: prompt = terms + committed tail inside 600 chars; finals feed `observe`; saved before
  `sink.close()` (a failed save is logged, never costs the transcript). Batch: the same per call,
  saved at the end.
- Docs: `gmst.example.toml`, PLAN.md config table, CLAUDE.md "Language mixture".

## Could not check

Whether the glossary actually keeps English terms in Latin script (and its latency cost) needs X.5's terms set: term recall with vs without, measured when it exists.

FINDING: recorded
