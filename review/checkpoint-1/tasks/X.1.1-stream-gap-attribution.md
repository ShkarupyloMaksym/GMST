id: X.1.1
title: Where the residual stream-vs-batch gap comes from (after X.1 failed)
parent: X.1
stage: evidence
kind: task
agent: orchestrator
model: opus
status: done
depends-on: -

# X.1.1 — Where the residual stream-vs-batch gap comes from (after X.1 failed)

## Instructions

X.1 failed its rule (+4.3 / +3.5 pts en / uk with small) with 0 contradicted pushes. Attribute the
gap before touching DECIDE-01: re-run X.1's en stream with small, keep the full output, log every
word the aligner skips when the text prefix match fails, align output vs reference.

## What was read / measured

`scripts/X.1.1/attribute.py` (X.1's en set and stream construction, `small`, shipped defaults,
language pinned; no other process running).

- Before (`attribute_small.out`): 417 ref words, 396 out, **32 edits = 21 del, 11 sub**; the
  time/n-gram path fired on 43 pushes; **20 of 21 deletions are words that path skipped**. Every
  case: Whisper did not re-emit the anchor word and timed the next new word from 0.00 with an end
  before the committed end (`skipped=['to'] spans=[[0.0, 0.4]] end=0.54 tail=['towards','them,']`).
- Cause: the prompt held the committed text *including the anchor words still in the buffer*, so
  Whisper skipped them in the audio. UFAL prompts only with text whose audio has left the buffer.
- After prompting only with pre-buffer text (`attribute_small_promptfix.out`): **12 edits = 1 del,
  11 sub** (2.88 % vs X.1's batch 2.64 %, 11 edits); 0 deletions from skipped words.

## Findings

- [blocking] The stream prompt overlapped the buffer's audio, turning the time cut into a
  word-dropper: 20 of 21 stream deletions (small, en). Fixed in F.14; X.1b re-measures.

## Could not check

Only en with small was attributed; uk and large-v2 are left to X.1b's re-measurement.

FINDING: findings
