id: X.2
title: EVID-02: LID accuracy vs prefix length, with and without the en/uk restriction
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: -

# X.2 — EVID-02: LID accuracy vs prefix length, with and without the en/uk restriction

## Instructions

For all 60 `uk` and 60 `en` clips, call the model's `detect_language` on prefixes of 1, 2, 3, 4 s and the full clip, `small` then `large-v2`. From each raw distribution compute (a) unrestricted top-1 and (b) restricted = argmax over {en, uk + ru}. Report accuracy per language × prefix × model for both, and the first-utterance case (no prior).

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.2/`. Write the clip list to `scripts/X.2/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1-8), `tasks/V1-evidence-plan.md`
(pre-registered rule for X.2: "restricted-LID accuracy by prefix length (1/2/3/4 s/full), per
language | ≥ 95 % on both at 2 s → DECIDE-04 = detect once at ≥ 2 s of buffer; ≥ 95 % only at full
→ re-detect on every decode until the endpoint; < 95 % even at full → record, DECIDE-04 needs a
design"), this node file.

Read code to match the real call path: `src/gmst/transcribe/backends/faster_whisper.py:84-100`
(`detect_language` = model's own `detect_language`, one encoder pass, then `resolve_language`),
`src/gmst/transcribe/lid.py` (uk/ru tie-break: combined uk+ru mass vs `threshold`, prefer `uk`
inside `tiebreak_margin`) — used to define the "restricted" scoring rule below. Per the invoking
prompt, called `faster_whisper.WhisperModel.detect_language` directly rather than importing
`gmst.transcribe.backends` (orchestrator editing `src/` concurrently).

Data: `eval/results/data/en/*.wav` (60 clips), `eval/results/data/uk/*.wav` (60 clips), confirmed
16 kHz mono PCM16 (`sf.info`), durations en 2.05-22.5 s, uk 2.856-10.332 s (uk n<4s = 19, en n<4s =
24 — prefixes longer than a clip's own duration are capped to the full clip; recorded per-row in
`capped`).

Environment checks: `pgrep -af python` before each model load showed no other python process
(besides an unrelated KDE plasma applet) both before `small` and before `large-v2` loads. HF cache
confirmed to hold `Systran/faster-whisper-small` and `Systran/faster-whisper-large-v2`
(`~/.cache/huggingface/hub`). Ran `HF_HUB_OFFLINE=1` throughout.

Scripts (`scripts/X.2/`):
- `write_clips.py` — writes the fixed 60 en + 60 uk clip list (sorted glob order) to `clips.txt`.
- `run_lid.py <model_size> <out.jsonl>` — for each clip, prefixes `[1, 2, 3, 4, full]` s (capped to
  clip duration), calls `WhisperModel(model_size, device="cpu", compute_type="int8").detect_language`
  directly (matches `Config`'s defaults, `src/gmst/config.py:26-27`). No `prev_lang`/sticky state is
  modeled — every row is the first-utterance/no-prior case, satisfying that part of the brief by
  construction. Records raw `(top_lang, top_prob, all_probs)` + wall time per call.
- `score_lid.py` — scores unrestricted top-1 (`top_lang == truth`) and restricted argmax
  (`P(en)` vs `P(uk)+P(ru)`, winner-takes-language; a `ru` label counts as the "uk-ish" bucket,
  matching `resolve_language`'s combined-mass tie-break). Labels each of the 5 rows/clip by file
  position (1,2,3,4,full in fixed order) rather than by matching floats — an early version compared
  `requested_prefix_s` (full precision) to `clip_dur_s` (rounded to 3 dp) and silently mis-bucketed
  1/60 "full" rows per model; caught by a bucket-count check (299 vs 300) and fixed before scoring
  the real numbers below (self-caught tooling bug, not a GMST defect).

Runs: `small` — 600 calls in 673.0 s wall (~1.12 s/call, load 0.76 s), sequential foreground.
`large-v2` — 600 calls in 2170.3 s wall (~3.6 s/call, load 3.58 s), backgrounded, polled to
completion; per-call wall time was ~constant across prefix lengths (1 s and 4 s prefixes took the
same ~3.6-3.9 s), consistent with Whisper's mel front-end padding every input to a fixed 30 s/3000-
frame window before the encoder pass — i.e. the *cost* of `detect_language` does not scale with
how much real audio the prefix carries, only the *accuracy* does. No other python process observed
running concurrently during either run (checked via `pgrep -af python` at the start of each and
periodically during large-v2; one Bash-tool outage mid-run was worked around by polling the output
files with `Read` instead of `pgrep`/`tail`, no process interaction involved).

Raw output: `scripts/X.2/small_raw.jsonl`, `scripts/X.2/large-v2_raw.jsonl` (600 rows each: 120
clips x 5 prefixes, in fixed clip/prefix order). Scored with `score_lid.py`; full table in
`scripts/X.2/score_output.txt`.



## Findings

**Restricted accuracy** = argmax(P(en), P(uk)+P(ru)) vs truth (the en/uk-ish bucket a mixed
EN/UK meeting actually needs, matching `resolve_language`'s combined-mass uk/ru tie-break).
**Unrestricted** = raw top-1 label over all ~99 Whisper language codes, exact match only. All
rows are first-utterance/no-prior (no `prev_lang` threaded across calls — every call is
independent, so this *is* the no-prior case the brief asks for, by construction of calling
`detect_language` directly rather than `resolve_language`'s sticky path).

| model | lang | 1 s | 2 s | 3 s | 4 s | full |
|---|---|---|---|---|---|---|
| small | en restricted | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| small | uk restricted | 0.183 | 0.883 | 0.950 | 0.983 | 0.983 |
| small | en unrestricted | 1.000 | 0.983 | 0.983 | 0.983 | 0.983 |
| small | uk unrestricted | 0.000 | 0.133 | 0.400 | 0.533 | 0.600 |
| large-v2 | en restricted | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| large-v2 | uk restricted | 0.233 | 0.900 | 0.983 | 1.000 | 1.000 |
| large-v2 | en unrestricted | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| large-v2 | uk unrestricted | 0.017 | 0.217 | 0.550 | 0.700 | 0.733 |

n = 60 per (lang, prefix, model) cell. Full numbers incl. capped-row detail:
`scripts/X.2/score_output.txt`, raw rows: `scripts/X.2/{small,large-v2}_raw.jsonl`.

**Against the pre-registered rule** (`tasks/V1-evidence-plan.md`, X.2 row): "≥ 95 % on both at 2 s
→ DECIDE-04 = detect once at ≥ 2 s of buffer; ≥ 95 % only at full → re-detect on every decode until
the endpoint; < 95 % even at full → record, DECIDE-04 needs a design."

- At 2 s, restricted uk accuracy is 0.883 (small) and 0.900 (large-v2) — **below the 95 % bar**;
  en is 1.000 at 2 s for both. **The "≥ 95 % on both at 2 s" branch fails for both models.**
- At full clip, restricted accuracy is ≥ 95 % on both languages for both models (small: en 0.983 /
  uk 0.983; large-v2: en 1.000 / uk 1.000). **The "≥ 95 % only at full" branch holds** →
  per the pre-registered rule, DECIDE-04 = re-detect on every decode until the endpoint (not
  detect-once-at-2s).
- Refinement within that branch (not a fourth rule branch, additional evidence for DECIDE-04's
  design): restricted uk accuracy already reaches the 95 % bar at **3 s**, not only at full, for
  both models (small 0.950, large-v2 0.983; en is 1.000 at every prefix ≥ 1 s for both models). If
  DECIDE-04 is designed against this data rather than just the three coarse buckets, "re-detect
  until ≥ 3 s of buffer, then stop" is a cheaper policy than "re-detect on every decode until the
  endpoint" and the data supports it about as well as "until full clip" does — worth flagging to
  whoever writes DECIDE-04's design.
- **Caveat on the 3 s/4 s cells' cleanliness**: prefixes longer than a clip's own duration are
  capped to the full clip (`capped` field in the raw rows), so the 3 s and 4 s buckets are partly
  populated by short clips whose "3 s"/"4 s" row is actually their full-clip audio. Measured:
  3 s bucket — en 12/60 (20 %) capped, uk 3/60 (5 %) capped; 4 s bucket — en 24/60 (40 %) capped,
  uk 19/60 (32 %) capped; 1 s and 2 s buckets have 0 capped rows (no clip is shorter than 2 s: en
  min 2.05 s, uk min 2.856 s). The 3 s cell is largely clean (95 % uk / 100 % en of it real);
  the 4 s cell is not — a third to two-fifths of it is really "full clip" relabeled "4 s". This
  does not change the deciding comparison above (2 s fails, full holds — both clean cells) but it
  means the 4 s row should not be read as "true 4 s prefix accuracy" without that caveat, and the
  3 s vs 4 s numbers in the table are not independent confirmation of a smooth accuracy-vs-duration
  curve (the corpus itself has few 3-4 s clips to give one, given LibriSpeech/CV10-derived clip
  lengths).
- **`ru` is the dominant unrestricted failure mode on uk, confirming the tie-break's premise**: at
  the full clip, small's unrestricted uk errors are 24/60, of which 21 are labeled `ru` (the rest
  `pl`×1, `de`×1, `hr`×1); large-v2's unrestricted uk errors are 16/60, of which 15 are `ru` (`pl`
  ×1). Across all prefixes pooled, `ru` accounts for 125/200 (62.5 %) of small's uk mislabels and
  100/167 (59.9 %) of large-v2's. `en` is the next most common uk mislabel (48/200 small, 50/167
  large-v2) — expected on short/noisy Ukrainian clips given `resolve_language`'s sticky-threshold
  design exists for exactly that case, though that path isn't exercised here (no prior). This is
  direct, quantified confirmation of the premise stated in `src/gmst/transcribe/lid.py:7` ("a `ru`
  label on Ukrainian speech is the visible failure") and of R2's onboarding lead (`PLAN.md:76-79`).
- [holds] `resolve_language`'s uk/ru combined-mass restriction (`src/gmst/transcribe/lid.py:37-41`)
  is doing real, measurable work: it recovers restricted accuracy to ≥ 95 % on uk by 3 s of audio
  for both models, where unrestricted top-1 alone is still 40-55 % wrong on uk at 3 s and 27-40 %
  wrong even at the full clip. Per PLAN.md rule 5 this is a design choice already settled, not
  re-argued here — the number just confirms it is load-bearing, not decorative.
- [holds] Larger model (large-v2) is uniformly at or above small's restricted accuracy at every
  prefix x language cell measured (see table); no prefix length where small beats large-v2 on
  restricted accuracy. Consistent with using large-v2 (or the eventual X.3 default) for
  `detect_language`, not a smaller model, once DECIDE-04 is written.

## Could not check

- No Mac/MLX comparison: `mlx_whisper`'s LID path (`mlx_whisper.decoding.detect_language`) needs
  Apple hardware; this node measured `faster_whisper` only, on the CPU int8 config `Config` ships
  as default. Per PLAN.md rule 6, an Apple-hardware gap, not a finding.
- `small`/`large-v2` only, per rule 4 (offline, cached models only) — `large-v3`, `turbo`, and the
  uk fine-tune are cached for `large-v3`/turbo-mlx but not asked to run `detect_language` here
  since X.2's brief names `small`/`large-v2` specifically; X.3 covers the wider model comparison.
- No test of the sticky/prior path (`resolve_language`'s `prev_lang` threshold): the brief's
  "first-utterance (no prior)" case is exactly what was measured (see Findings); the *sequential*
  case (LID on utterance 2+ of a meeting, with a prior language) is a different measurement this
  node's rule does not ask for.

FINDING: recorded
