id: F.18
title: Glossary as a post-decode corrector; never in the decoder's context
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.6

# F.18 — Glossary as a post-decode corrector; never in the decoder's context

## Instructions

DECIDE-08 revised by the user (2026-09-29, after X.6): "Correct after decoding". Remove the
glossary from every decode; correct Cyrillic transliterations of the terms in the decoded text.

## What was read / measured

Confirmed X.6's root cause in faster-whisper 1.2.1 `WhisperModel.get_prompt`
(`transcribe.py:1542-1550`): `hotwords` and the `initial_prompt` tokens both go into one
`sot_prev` block, so F.12's glossary went in twice. Tests (`tests/test_glossary.py`): the glossary
never reaches the decoder (prompt and `hotwords`), correction of "деплой" / "кубернетіс" / "пул
реквест", a case ending ("кубернетісі"), ordinary words left alone ("депутат замовив реквієм"),
word timings kept across a merged run, stream finals corrected — 6 watched fail. The first
implementation over-matched on the tests' own examples ("деплой на" → "deploy": the case-ending
tolerance swallowed the next word); fixed by never letting a run have more words than the term,
recorded in X.6b's pre-registration before any score. Suite 203 passed; ruff clean.

## Findings

- `glossary.py`: `correct_words` / `correct` (transliteration → sound-alike key, SequenceMatcher
  ≥ 0.75, first letter, ≥ 4 letters, ±35 % length, ≤ 2 trailing letters, run ≤ term words);
  `prompt` / `hotwords` removed.
- `stream.py`: live and final decodes carry no glossary; final words corrected. `batch.py`:
  segments corrected (words or text) and observed.
- Docs: CLAUDE.md, PLAN.md (config table, prompt row, DECIDE-08 struck and revised),
  `gmst.example.toml`, `engine.py` (the `hotwords` parameter stays, unused by GMST).

## Could not check

Whether it helps: X.6b.

FINDING: recorded
