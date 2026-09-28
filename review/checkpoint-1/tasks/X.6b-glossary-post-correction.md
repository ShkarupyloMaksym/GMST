id: X.6b
title: DECIDE-08 revised: glossary as post-decode correction, scored on X.6's no-glossary outputs
parent: X
stage: evidence
kind: task
agent: orchestrator
model: opus
status: todo
depends-on: F.18

# X.6b — DECIDE-08 revised: glossary as post-decode correction, scored on X.6's no-glossary outputs

## Instructions

User, 2026-09-29, after X.6: "Correct after decoding" — the glossary no longer goes into Whisper;
it corrects Cyrillic transliterations of English terms in the decoded text. Pre-registered here,
**before the corrector exists** (F.18), so nothing is tuned on these clips:

- **Inputs:** X.6's condition (a) hypotheses — `scripts/X.6/results_small_200.json` `a_hyps`
  (200 clips) and `results_large-v2_100.json` `a_hyps` (100) — no decoding.
- **Glossaries:** (b') the 100 most frequent Latin terms in `uk-pods_pods_train.json`
  `text_no_preprocessing` **excluding every clip id in `terms.jsonl`** (X.6's static list leaked
  179/200); (c') autogrow only — correction plus `observe` over the clips in manifest order,
  starting empty.
- **Metric and rule:** X.6's, unchanged — recommend (b') or (c') only if term recall ≥ (a) + 10.0
  pts and WER ≤ (a) + 1.0 pt, for both models. Also report every replacement the corrector made
  that is *not* a reference term (false positives), with the text.
- **Corrector design fixed in F.18 before scoring:** transliterate Cyrillic runs of 1–3 tokens,
  compare to each term on a crude sound-alike key (SequenceMatcher ≥ 0.75, first letter equal,
  length within ±35 %, ≥ 4 letters, up to 2 trailing letters tolerated for Ukrainian case
  endings). No threshold may be changed after the first score. *(Amended before any score, from
  the unit tests' own examples: a run may not have more words than the term — the ending
  tolerance was swallowing the next short word, "деплой на" → "deploy".)*

## What was read / measured

_(write as you go)_

## Findings

_(numbers against the rule)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
