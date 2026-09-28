id: X.1b.1
title: Why F.14 hurt Ukrainian, and a variant that holds on both languages
parent: X.1b
stage: evidence
kind: task
agent: orchestrator
model: opus
status: done
depends-on: -

# X.1b.1 — Why F.14 hurt Ukrainian, and a variant that holds on both languages

## Instructions

X.1b: F.14 closed the English gap (2.64 = 2.64 %) but Ukrainian stream went to 45.45 % with
hallucinated tokens ("Zum2i", "осьoof1"). Attribute, and find a variant that holds on both.

## What was read / measured

`scripts/X.1b.1/uk_prompt_ab.py` (X.1's uk stream, `small`, run twice per variant; the pre-F.14
code from a scratch worktree at `0dfd92a`) and `scripts/X.1.1/attribute.py` (en). Same 20+20
clips as X.1 — **so this is diagnosis, not evidence: X.1c re-measures on unseen clips too.**

| variant | uk run 1 / run 2 | en edits /417 |
|---|---|---|
| pre-F.14: prompt incl. anchor, ungated time cut | 27.27 / 27.27 % | 32 (21 del) |
| F.14: prompt excl. anchor | 32.87 / 27.97 % (X.1b: 45.45 %) | 11 |
| C: prompt incl. anchor, no time cut | 30.07 / 30.07 % | 32 (18 ins: phrases doubled) |
| E: prompt incl. anchor, time cut gated by resemblance | 25.17 / 25.17 % | 31 (11 ins) |
| **E+H: E + text/n-gram checks against a 5-word committed history** | **25.17 / 25.17 %** | **22** (4 del, 5 ins) |

Batch (X.1): uk 23.78 %, en 2.64 %. E+H: uk +1.39 pts, en +2.64 pts.

## Findings

- [serious] F.14 made Ukrainian decoding non-deterministic: without the anchor words in the prompt
  the model's confidence drops and temperature-fallback sampling produces hallucinations
  (27.97–45.45 % across three runs, vs 27.27 % twice before). English is unaffected.
- [serious] With the anchor in the prompt, Whisper re-emits phrases longer than the surviving
  anchor ("to tell himself" from a one-word anchor "himself"): matching against the anchor alone
  doubled them (variant C, 18 insertions). A 5-word text history fixes it (E+H).
- The ungated time cut is what dropped new words (X.1.1); gating it by resemblance keeps them.

## Could not check

large-v2 and unseen clips — X.1c.

FINDING: findings
