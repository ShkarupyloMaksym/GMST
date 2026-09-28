id: X.5
title: DECIDE-06: find public Ukrainian speech with English terms, and build a terms eval set
parent: X
stage: evidence
kind: task
agent: general-purpose
model: sonnet
effort: high
status: todo
depends-on: -

# X.5 — DECIDE-06: find public Ukrainian speech with English terms, and build a terms eval set

## Instructions

The user's meetings are *Ukrainian with English technical terms* (H1, 2026-09-28) and they cannot
supply recordings; they asked for public datasets. Read first: root `CLAUDE.md`, root `PLAN.md`
"Review decisions" (DECIDE-06, DECIDE-08), `review/checkpoint-1/PLAN.md`, this file. Set
`status: in-progress` before starting. **Rule 4 is amended for this node only (2026-09-28, the
user asked for a web search): network access and dataset downloads are allowed**, up to ~10 GB
total, into `eval/results/raw/` (git-ignored). Write only this node file, `scripts/X.5/` and new
files under `eval/results/`.

Candidates found by the orchestrator (verify each; search for more — IT/tech podcasts, conference
talks, YouTube with manual subtitles, anything with uk–en code-switching):
- `taras-sereda/uk-pods` (HF): 51 h, podcast "Вертіго" (film/media), CC-BY-NC-4.0, manifests
  `pods_train.json` / `pods_test.json` with `text` and `pred_text`; card examples keep "MCU",
  "retouch" in Latin script. **Provenance of `text` unknown.**
- `espnet/yodas2` `uk000` / `uk100` (HF): YouTube, CC BY 3.0; manual vs automatic subtitles per
  subset is unconfirmed.
- `Yehor/broadcast-speech-uk` (~300 h), `speech-uk/voice-of-america` (~390 h).

Pre-registered rule (fixed now, before any download):
- A source is **usable as reference** only if its transcripts are human-made (manual subtitles,
  human transcription, or human-corrected), established from its card, paper, repo, or by
  evidence in the data (e.g. `text` differing from `pred_text` in human-correction patterns).
  Whisper-generated references are rejected: scoring Whisper against Whisper is circular.
- A **terms set** is buildable if the usable sources yield **≥ 150 clips** whose reference contains
  ≥ 1 Latin-script token of ≥ 2 letters inside otherwise Ukrainian text, from **≥ 10 distinct
  speakers or episodes**. Otherwise record what exists and say so.

Deliverables: per candidate — size, licence, domain, provenance of transcripts (with the quote or
evidence), count of Latin-term clips in a sample; if the rule holds, a script
`scripts/X.5/build_terms_set.py` that writes `eval/results/data/terms/*.wav` (16 kHz mono) and
`eval/results/data/terms.jsonl` with `{id, wav, text, terms: [...]}`, and the counts. Do not run
any ASR model beyond `tiny` (for spot checks only). Offline rules otherwise unchanged; X.1 may be
loading models concurrently — keep CPU use modest.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(the measured numbers against the pre-registered rule, then `- [holds|fails] ...`)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
