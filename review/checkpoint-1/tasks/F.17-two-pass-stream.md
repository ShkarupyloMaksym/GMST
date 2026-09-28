id: F.17
title: Two-pass streaming — provisional live text, the utterance decoded whole as final
parent: F
stage: fix
kind: task
agent: orchestrator
model: opus
status: done
depends-on: X.1c.1

# F.17 — Two-pass streaming — provisional live text, the utterance decoded whole as final

## Instructions

Implement DECIDE-09 (user, 2026-09-28): live LocalAgreement-2 output provisional; at each
utterance end, decode the utterance's audio whole and emit that as final.

## What was read / measured

`run_stream` restructured; the live LocalAgreement-2 block is unchanged except where its output
goes. Seven existing stream tests failed at first: two were real regressions, fixed (engine dies
mid-meeting / second Ctrl-C → empty SRT: `salvage` now emits the live-agreed words as final when
the final pass fails or is abandoned), plus a third found while updating them (a tail shorter than
one decode chunk was never flushed: the shutdown now runs the final pass whenever the utterance
holds audio). The other four encoded the old semantics and were updated without weakening what
they protect (one final per utterance; the final pass re-detects LID on the whole utterance; the
live buffer stays < 4 s while only final passes decode a whole utterance; the whole-utterance
revision wins, nothing lost or doubled); the turn test was rewritten on real audio + energy VAD
(its fake VAD cropped the final pass to silence). New contract test
`test_two_pass_live_text_is_provisional_and_each_utterance_gets_one_final` fails on F.16's code,
passes on F.17's. Suite 200 passed; ruff clean.

Diagnostic (small, `scripts/X.1c.1/`; rows already used, so not evidence): unseen uk (20–39)
**14.29 %** twice = batch 14.29 % (F.16: 21.43, F.15: 79.37); original en **10/417** vs batch 11.

## Findings

- `stream.py`: `utt_audio` since the last final (silence bounded to 1 s when nothing was heard);
  `final_pass(upto)` crops to VAD speech ± 0.2 s, detects LID on it unless pinned, prompts with
  glossary terms only, emits final segments (turns, glossary, stats); `monologue_cut` at
  `max_buffer_seconds` ends a final at the latest pause in the second half; `salvage`;
  `emit_provisional` shows the utterance so far as one partial.
- Docs: `stream.py` docstring, CLAUDE.md "Streaming reconciliation", PLAN.md schema semantics and
  "Review decisions".

## Could not check

Final-text latency (one decode of the utterance after its endpoint) is X.4 / MAC-03's to
measure. Evidence on unseen clips is X.1d.

FINDING: recorded
