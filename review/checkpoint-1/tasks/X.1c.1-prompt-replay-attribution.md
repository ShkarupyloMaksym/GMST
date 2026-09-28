id: X.1c.1
title: Unseen Ukrainian at 79 % stream WER — attribution and the utterance-local prompt
parent: X.1c
stage: evidence
kind: task
agent: orchestrator
model: opus
status: done
depends-on: -

# X.1c.1 — Unseen Ukrainian at 79 % stream WER — attribution and the utterance-local prompt

## Instructions

X.1c (interim, small): unseen uk (rows 20–39) stream 79.37 % vs batch 14.29 %, identical on both
runs. Attribute before X.1c finishes.

## What was read / measured

X.1c's `small_b_results.json` uk `out_preview`: after "Інших пояснень немає" the stream re-emits
"Розпочали рити котлован Цей сервіс дозволить тепер Плотити через смартфон…" — text committed
utterances earlier. Whisper regurgitates its prompt on short buffers; the prompt was the whole
session's committed text. Variant P — prompt from the current utterance only (cleared at each
endpoint) — measured with `scripts/X.1c.1/uk_stream.py` (X.1's uk stream with a row offset) and
`scripts/X.1.1/attribute.py`, `small`, one run each (X.1c's large-v2 was loading concurrently; no
timings used):

| clips | batch | F.15 stream | P stream |
|---|---|---|---|
| uk unseen (20–39) | 14.29 % | 79.37 % | **21.43 %** (+7.1) |
| uk original (0–19) | 23.78 % | 25.17 % | 26.57 % (+2.8) |
| en original (0–19) | 2.64 % | 5.28 % (22/417) | 4.80 % (20/417) |

`scripts/X.1c.1/align_errors.py` on P's unseen-uk output: the remaining 27 edits are acoustic
substitutions spread across utterances ("червоноармійців" → "червону армійцю", "каси" → "касом"),
no replays or duplicates.

## Findings

- [blocking] The session-long prompt made the stream replay earlier utterances on unseen
  Ukrainian (79 % WER). Fixed by F.16 (utterance-local prompt).
- [serious] After F.16, unseen Ukrainian with `small` is still +7.1 pts over batch, from
  misrecognitions of words committed from partial audio — not a reconciliation defect. Whether
  large-v2 narrows it is X.1c's large-v2 run (on F.15 code — its process started before F.16).

## Could not check

P on unseen English (F.15 already passed there: +1.6 / +1.9 pts).

FINDING: findings
