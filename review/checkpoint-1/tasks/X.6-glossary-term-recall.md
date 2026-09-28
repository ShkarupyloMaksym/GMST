id: X.6
title: DECIDE-08: does the glossary keep English terms in Latin script? (terms set)
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: todo
depends-on: X.4

# X.6 — DECIDE-08: does the glossary keep English terms in Latin script? (terms set)

## Instructions

Data: `eval/results/data/terms.jsonl` (200 uk-pods clips from 187 episodes, each reference holding
≥ 1 Latin-script term inside Ukrainian text; built by X.5). Pre-registered here (2026-09-28,
before any run):

- **Metric:** term recall = share of the reference's Latin terms (the `terms` field) that appear in
  the hypothesis as the same Latin token, case-insensitive, edge punctuation stripped; plus corpus
  WER (`gmst.metrics.word_errors`) on the same clips.
- **Path:** batch per clip, language pinned `uk` (`gmst.pipeline.batch.transcribe_by_region` with
  `Config(language="uk", ...)`), `small` and `large-v2`.
- **Conditions:** (a) no glossary; (b) static glossary = the 100 most frequent Latin terms (same
  tokenizer as X.5) in `eval/results/raw/uk-pods_pods_train.json` `text_no_preprocessing`, which
  does not include the 200 test clips — check and report the overlap of clip ids; (c) autogrow
  only — `glossary_autogrow = true`, starting empty, one `Glossary` object carried across the 200
  clips in manifest order (the `Glossary` API in `src/gmst/glossary.py`: decode each clip with its
  prompt/hotwords, then `observe` the output).
- **Rule:** recommend enabling a glossary (b or c) only if its term recall is ≥ 10.0 pts above (a)
  **and** its WER is ≤ (a)'s + 1.0 pt, for both models. Otherwise record that it does not earn its
  latency and leave it off by default.

Also report decode time per clip for each condition (the latency cost the user accepted), and 10
example terms that (a) got wrong and (b)/(c) got right, and vice versa. Read first: root
`CLAUDE.md`, `src/gmst/glossary.py`, `tasks/X.5-*.md`, this file. Offline, one large model at a
time (`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.6/`.

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
