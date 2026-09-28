id: X.1d
title: EVID-01 after F.17 (two-pass), on fresh unseen clips
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: F.17

# X.1d — EVID-01 after F.17 (two-pass), on fresh unseen clips

## Instructions

Rows 0–39 of `en.jsonl` / `uk.jsonl` have all been used for diagnosis. Pre-registered here
(2026-09-28, before running): EVID-01's rule, unchanged — stream ≤ batch + 3.0 pts on en and uk
with `small` — on **fresh rows 40–59**, which decide the verdict. Stream = the **final** segments
only (two-pass semantics). Run each stream twice with `small`; then `large-v2` once on rows 40–59
en and uk (X.1c saw large-v2 hallucinate on English: report whether the finals still contain
"www", "End 1"-style boilerplate); then `small` on the first 20 mixed `inter` and 20 `nopause`
clips (auto LID), reported, not part of the rule. Copy `scripts/X.1c/run_wer.py` to
`scripts/X.1d/` (output paths only). Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md`,
`tasks/V1-*.md`, `tasks/X.1*.md`, `tasks/F.17-*.md`, this file. Offline, one large model at a time
(`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.1d/`. If Bash starts failing with a classifier error, record what completed first.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1-8; `tasks/V1-evidence-plan.md`
(EVID-01 rule unchanged: holds if corpus stream WER ≤ batch WER + 3.0 pts on en and uk with
`small`, contradicted-push share ≤ 10%); `tasks/X.1c-*.md` (post-F.15, unseen rows 20-39: uk/small
failed +65.08 pts — verbatim clause duplication past the 5-word `_history` window; en/large-v2
failed +30.03 pts — Whisper "www.FEMA.gov" / "End 1" boilerplate hallucination; both
`contradicted=0`); `tasks/F.17-*.md` (DECIDE-09 two-pass: live LocalAgreement-2 output is
provisional (`is_final=False`); at each utterance end the utterance's own audio is decoded whole
as final (`is_final=True`) and supersedes the provisional text — F.17's own diagnostic on rows
20-39 uk (already used, not evidence): 14.29% both reps = batch 14.29%). Confirmed F.17 is present
at 9d6b3ed: `sink/stream.py` docstring "Streaming pipeline, two passes ... DECIDE-09", `grep -n
"is_final" src/gmst/pipeline/stream.py` shows the live pass emits `is_final=False`
(`emit_provisional`) and the final pass emits `is_final=True` segments.

`pgrep -af python` before starting: no Python process loading a model (KDE plasmoid helpers and an
unrelated zsh loop waiting on a tar.gz download for a different node, same as X.1c/X.1b's notes).

Wrote `scripts/X.1d/run_wer.py`: copy of `scripts/X.1c/run_wer.py` (offset/tag selection,
stream-runs repeat, `s.is_final` filter on stream output — unchanged, already two-pass-correct)
plus the `mixed` mode ported back from `scripts/X.1/run_wer.py` (auto LID: batch via
`transcribe_by_region`, stream `language=None`) for the brief's reported-only mixed run. Output
paths only differ from X.1c as instructed. Wrote `scripts/X.1d/clips.txt` (80 lines: en rows
40-59, uk rows 40-59, all 40 `mixed.jsonl` rows = first 20 `inter` + first 20 `nopause`, since the
set holds exactly 20 of each) before any run.

Run 1 — `small`, en/uk rows 40-59, stream x2:
`HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1d/run_wer.py enuk small 2 40:c`
→ `scripts/X.1d/small_run.log`, `scripts/X.1d/small_c_results.json`. `pgrep -af python` checked
immediately before start (only this run's own process afterward, no other model-loader). Completed
~15 min wall. Checked both reps' `full_out` for repeated 6-grams (the duplication signature X.1c
found post-F.15) with a small script (`Counter` over 6-word windows) — zero repeats in en or uk,
either rep.

Run 2 — `large-v2`, en/uk rows 40-59, stream x1: `pgrep -af python` checked immediately before
start (only the X.5 node's unrelated shell loop waiting on a download, no model-loader) —
`HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1d/run_wer.py enuk large-v2 1 40:c`
→ `scripts/X.1d/large-v2_run.log`, `scripts/X.1d/large-v2_c_results.json`. Ran ~30 min wall
(batch 119.1+103.2s, stream 991.8+623.9s ≈ 1838s total), no other model-loading process observed
during the run. Checked `full_out` for the "www .FEMA .gov" / "End 1" boilerplate X.1c found on
`large-v2`/en post-F.15, and for repeated 6-grams — neither present in en or uk this time; spot-read
of the uk `full_out` vs `full_ref` head shows ordinary transcription variance (e.g.
"заострений"/"Скуморох" vs ref "загострений"/"скоморох"), not hallucination or duplication.

Run 3 — `small`, mixed set (first 20 `inter` + first 20 `nopause`, auto LID, reported not part of
the rule): `pgrep -af python` checked immediately before start (only the unrelated zsh loop, no
model-loader) — `HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1d/run_wer.py mixed
small 1` → `scripts/X.1d/mixed_run.log`, `scripts/X.1d/small_mixed_results.json`. Ran ~20 min wall
(batch 167.6s, stream 1039.5s). Initial 6-gram repeat scan flagged 45-49 repeated windows in the
stream output; cross-checked each against the *reference*'s own repeat count (the corpus itself
repeats two whole sentences across different clips, e.g. "навіщо відкладати..." appears in both
`mix-inter-002`'s reference and a later clip) — `ref.count("навіщо")==2`, `out.count("навіщо")==2`,
same for `"rest of the work"` (2/2) — so the repeated n-grams are corpus-inherent duplicate
sentences reproduced once each, not the reconciliation double-commit X.1c found; no repeat count in
`full_out` exceeded the same phrase's count in `full_ref` for these two spot-checked phrases.

## Findings

Pre-registered rule (unchanged from V1/X.1c): EVID-01 **holds** if corpus stream WER (finals only,
two-pass) ≤ batch WER + 3.0 pts on en **and** uk with `small`, and contradicted-push share ≤ 10%;
decided on fresh rows 40-59 (never used for diagnosis before this node).

**`small`, rows 40-59 (`scripts/X.1d/small_c_results.json`) — the deciding run:**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 3.22% | 11/342 | — |
| en | stream rep0 | 3.51% | 12/342 | +0.29 pts (passes) |
| en | stream rep1 | 3.51% | 12/342 | +0.29 pts (passes), identical to rep0 |
| uk | batch | 33.33% | 48/144 | — |
| uk | stream rep0 | 31.94% | 46/144 | **−1.39 pts (passes, stream beats batch)** |
| uk | stream rep1 | 31.94% | 46/144 | same, identical to rep0 |

Contradicted-push share: en 0/130, uk 0/80 (0%), both reps — well under the 10% bar. Both reps
byte-identical per set (F.14's uk non-determinism, still visible in X.1c, is not present here).
No repeated 6-gram found in any `full_out` (the X.1c duplication signature is gone on this set).

**Verdict: EVID-01 holds on fresh, never-before-used clips, under F.17's two-pass streaming.**
This directly reverses X.1c's post-F.15 result on the equivalent held-out check (uk +65.08 pts
fail, en/large-v2 +30.03 pts fail) — the two-pass design (provisional LocalAgreement-2 output,
whole-utterance final decode) removes both failure modes X.1c found on unseen audio: the
long-range clause duplication (previously past the 5-word `_history` window) and, on `small`, any
gap beyond the margin at all. `uk` batch itself is markedly harder on this row range (33.33% vs
14.29% on X.1c's set (b)) — this fresh set is not an easier test, which strengthens the pass.

**`large-v2`, rows 40-59, reported (rule is `small`-only) (`scripts/X.1d/large-v2_c_results.json`):**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 2.92% | 10/342 | — |
| en | stream | 3.80% | 13/342 | +0.88 pts (would pass) |
| uk | batch | 8.33% | 12/144 | — |
| uk | stream | 11.81% | 17/144 | **+3.48 pts (would fail the 3.0-pt bar, if it applied)** |

No "www"/"End 1"/".FEMA"/".gov" boilerplate and no repeated 6-gram in either language's
`full_out` — the specific `large-v2` hallucination X.1c documented on English did not reproduce
here. The uk stream/batch diff read as ordinary ASR variance (e.g. "заострений" vs ref
"загострений"), not hallucination or duplication.

- **[serious] Two-pass does not fully close the stream/batch gap on `large-v2`.** uk exceeds the
  3.0-pt margin by +3.48 pts on this fresh set (reported only — the pre-registered rule is
  `small`-only, so this does not reopen DECIDE-01/EVID-01's verdict) — but it is evidence that if
  `large-v2` (or a comparably-sized model) is later chosen as the default (X.3/X.4's job), the
  two-pass fix would need re-verification against the 3.0-pt bar at that model size before the
  same "holds" verdict could be claimed for it. The failure mode this time is ordinary
  transcription drift, not the earlier hallucination/duplication classes — a materially milder,
  non-catastrophic gap (+3.48 pts vs X.1c's +30.03/+65.08 pts, roughly an order of magnitude
  smaller).

**`small`, mixed set (`inter`+`nopause`, auto LID), reported, not part of the rule
(`scripts/X.1d/small_mixed_results.json`):**

| mode | WER | edits/ref | gap vs batch |
|---|---|---|---|
| batch | 10.96% | 111/1013 | — |
| stream | 14.12% | 143/1013 | +3.16 pts (would fail the 3.0-pt bar, if it applied to mixed) |

No genuine duplication (see the corpus-repeat cross-check above); `contradicted=0/289`. This is
the code-switching set the rule was never written to cover (EVID-01 is en/uk-pinned only), so it
is reported per the brief, not a rule failure — but the gap direction is consistent with the
`large-v2` en/uk finding: two-pass narrows but does not eliminate a stream-vs-batch gap outside the
`small`/en/uk case the rule actually decides.

## Could not check

- Per-clip attribution inside the concatenated stream WER is not available (same limitation noted
  by every prior X.1* node) — only a corpus-level edit distance over the whole concatenation, plus
  the spot n-gram/repeat-count cross-checks done here.
- Could not attribute the residual `large-v2`/uk and mixed-set gaps (+3.48, +3.16 pts) to a
  specific mechanism (e.g. final-pass prompt content, VAD cropping, LID re-detection cost) — out
  of budget for an evidence node; material for a fix/diagnosis node if `large-v2` or a mixed
  workload becomes load-bearing.
- Only one `large-v2` stream rep was run (per the brief's budget), so uk's `large-v2`
  non-determinism (if any, as seen for `small`/en pre-F.17 in X.1c) could not be checked here.
- `mixed` was run once (stream x1) per the brief; determinism across reps not checked for this set.

FINDING: findings
