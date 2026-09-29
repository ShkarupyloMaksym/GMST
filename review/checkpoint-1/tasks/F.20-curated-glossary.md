id: F.20
title: Glossary curated-only and experimental; autogrow removed (DECIDE-08, second revision)
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.6b

# F.20 — Glossary curated-only and experimental; autogrow removed (DECIDE-08, second revision)

## Instructions

User, 2026-09-29, after X.6b: "Curated-only, experimental".

## What was read / measured

Tests (`tests/test_glossary.py`): config accepts "Kubernetes", "deploy", "pull request" and
rejects "me", "time", "people" and a list containing "to" at load; `glossary_autogrow` is now an
unknown key; the no-false-positive test extended with X.6b's own failures ("мені тому цим") — the
first two watched fail. `ruff format` wrapped the new word list. Suite 200 passed; ruff clean.

## Findings

- `glossary.py`: `unsafe_term` (< 5 letters, or in `_COMMON`, a fixed list of frequent English
  words of 5+ letters); `Glossary(terms)` only — `observe`, `save`, `autogrow`, `path`,
  `max_terms` removed. `config.py`: `glossary_autogrow` / `glossary_path` / `glossary_max_terms`
  removed; `glossary` validated with `unsafe_term`.
- `stream.py` / `batch.py`: no observe/save.
- Docs: CLAUDE.md, PLAN.md config table, `gmst.example.toml`.

## Could not check

Whether a curated IT-term list helps on real IT-meeting audio: no such data (DECIDE-06).

FINDING: recorded
