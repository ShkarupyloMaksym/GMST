id: H1
title: Your decisions
parent: -
stage: decision
kind: task
agent: human
model: human
status: in-progress
depends-on: T1

# H1 — Your decisions

## Instructions

The orchestrator lists every `DECIDE-nn` here with the options, the evidence for each, and a recommendation. You choose; the orchestrator records the choice in `PLAN.md` with a dated note.

### Open decisions (from T1, 2026-09-28)

- **DECIDE-01 — how the stream re-anchors after a trim.** (a) Trim at the *start* of the last
  committed word minus the back-off, keeping the whole word as the anchor; exact-prefix `_align`
  unchanged. Cheap, but any re-hearing of that word still contradicts terminally. (b) **Recommended:**
  (a) plus timestamp-based anchoring, as UFAL's `whisper_streaming` does — drop hypothesis words
  ending before the last committed word's end (buffer-relative) and de-duplicate an up-to-5-word
  n-gram overlap, so a contradiction is no longer terminal. Stays LocalAgreement-2 (rule 5); changes
  `_align`'s contract, so its tests change with it. (c) Keep exact alignment, but after N contradicted
  pushes reset the anchor and commit from timestamps.
- **DECIDE-02 — restrict LID.** **Recommended:** a new config field `lid_languages` (default
  `["en", "uk"]`); renormalise the detector's distribution over it, with `ru` folded into `uk` (the
  tie-break becomes a special case), so the first utterance is also safe. Alternative: hard-code
  en/uk. Either way `language = en|uk` pinning is unchanged.
- **DECIDE-03 — what batch "per-segment LID" means.** (a) **Recommended:** VAD-split the file
  (reuse `segment/vad.py`), detect each region with DECIDE-02's restriction, and decode each region in
  its own language — same semantics as the stream. (b) One restricted detection per file, decoded
  in that language (simpler; no code-switching in batch).
- **DECIDE-04 — stream LID timing.** Waits on EVID-02. Options: re-detect on every decode until
  confident; re-decode the utterance if the endpointed segment's language differs; or detect only
  once ≥ N s of buffer exists.
- **DECIDE-05 — where runtime status goes.** **Recommended:** now, `logging` warnings on stderr for
  overflow/lagging/sustained lag, and a console-sink status line (`[lagging]`, idle); later, an
  optional JSONL/SSE `{"status": ...}` event (a schema addition, so it needs your yes).
- **DECIDE-06 — real code-switched eval audio.** **Recommended:** record and hand-transcribe 5–10 min
  of a real mixed meeting (PLAN Phase 1 already asks for it); drop `real_cs` from `build_sets.py`.
- **DECIDE-07 — CI.** Add `.github/workflows/ci.yml` (uv sync, ruff, pytest; useful once you add a
  GitHub remote), or strike the claim from CLAUDE.md/PLAN.md. **Recommended:** add it.


## What was read / measured

2026-09-28, answered in session:
- **DECIDE-01 → (b)** trim before the last committed word + timestamp-based anchoring (UFAL style).
- **DECIDE-02 → `lid_languages`** config field, default `["en", "uk"]`, `ru` folded into `uk`.
- **DECIDE-03 → (a)** batch VAD-splits and decodes each region in its own (restricted) language.
- Still open: DECIDE-04 (waits on EVID-02), DECIDE-05, DECIDE-06, DECIDE-07.

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
