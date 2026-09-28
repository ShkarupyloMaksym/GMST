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

2026-09-28, after X.2 — **DECIDE-04 reframed by the user:** "Main problem of this question is
Ukrainian/English mix is professional language, like we can speak Ukrainian, but with English
terms." So the dominant case is *Ukrainian utterances carrying English technical terms*
(intra-sentence), not whole utterances switching language. Per-utterance LID picks `uk` for those
(correctly); the failure is then inside the Ukrainian decode — English terms transliterated into
Cyrillic or misheard — which no LID timing fixes. Consequences: (1) DECIDE-04's timing question
shrinks to "don't let an utterance that *starts* with an English term flip to `en`" (X.2: 2 s
prefixes are 88–90 % right on Ukrainian); (2) the real open problem is term fidelity in `uk`
decoding — candidates: a glossary of the team's terms in Latin script as `initial_prompt` /
faster-whisper `hotwords`, a Ukrainian fine-tune, a post-pass; (3) none of it can be measured on
the synthetic sets — DECIDE-06 (a recorded, hand-transcribed real meeting) becomes a prerequisite.

2026-09-28, answered in session:
- **DECIDE-04 → detect until 3 s, hold commits.** Re-detect on each decode while the utterance has
  < 3 s of audio (X.2: restricted LID ≥ 95 % on both models at 3 s); fix the language at 3 s and
  hold commits until then, so an utterance opening with an English term cannot be committed as `en`.
- **DECIDE-06 → search the web for datasets** ("I can't give you real audio for now"): public
  Ukrainian speech with English terms / uk–en code-switching, with transcripts that keep the terms
  in Latin script. Node X.5.
- **DECIDE-08 (new) → an auto-growing glossary**, enabled in config and removable for speed ("yes,
  it'd add latency, but if we would want speed — it can be removed"): a configured term list fed to
  Whisper as prompt / `hotwords`, which grows with English terms seen in the session.

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
