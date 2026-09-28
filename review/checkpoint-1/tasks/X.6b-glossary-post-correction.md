id: X.6b
title: DECIDE-08 revised: glossary as post-decode correction, scored on X.6's no-glossary outputs
parent: X
stage: evidence
kind: task
agent: orchestrator
model: opus
status: done
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

`scripts/X.6b/score_correction.py` (X.6's `term_hit` / `score` copied verbatim; the static list
rebuilt from 30,629 train clips with every `terms.jsonl` id excluded), run once:
`scripts/X.6b/score_correction.out`, `scores.json`. No decoding.

## Findings

| model | glossary | term recall | WER | Δrecall / ΔWER | false positives | rule |
|---|---|---|---|---|---|---|
| small (200) | (a) none | 43.8 % | 20.79 % | | | |
| small | (b') static, leak-free | 50.3 % | 24.98 % | +6.5 / +4.19 | 188 | fails |
| small | (c') autogrow | 44.6 % | 24.20 % | +0.9 / +3.41 | 128 | fails |
| large-v2 (100) | (a) none | 61.7 % | 11.03 % | | | |
| large-v2 | (b') static, leak-free | 66.0 % | 15.62 % | +4.3 / +4.60 | 89 | fails |
| large-v2 | (c') autogrow | 64.2 % | 13.54 % | +2.5 / +2.51 | 48 | fails |

- [serious] **Post-decode correction fails the rule too.** Recall rises a little, but short common
  English words in the list match ordinary Ukrainian words and WER rises 2.5–4.6 pts: "мені" →
  "Men", "тому" → "To", "цим" → "time", "приводу" → "Prey", "ліси" → "Lies", "Мілані" → "Man".
- [serious] **Autogrow learns the wrong things**: speakers' English phrases ("ring hollow for me",
  "one note") feed it "me", "to", "time", which then overwrite Ukrainian words.
- Per the pre-registration, no threshold is changed after this score. Not tested (would need a
  new pre-registered set): a curated list of long, distinctive technical terms only.

## Could not check

Whether a *curated* list of distinctive technical terms (not frequency-mined from a film podcast) helps — the podcast's terms are film titles and everyday English, not an IT meeting's vocabulary.

FINDING: findings
