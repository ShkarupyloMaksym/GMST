id: X.1
title: EVID-01: stream vs batch WER after the re-anchoring fix
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: in-progress
depends-on: F.8

# X.1 — EVID-01: stream vs batch WER after the re-anchoring fix

## Instructions

Extend R1's `scripts/R1/probe_real_model_contradictions.py` into `scripts/X.1/`: for the first 20 clips of `eval/results/data/en` and of `uk` (language pinned) and the first 20 `mixed` inter clips (auto LID), run batch and `run_stream` with shipped defaults, `small` then `large-v2`. Report corpus WER per set and mode, contradicted-push share, and 5 sample stream outputs.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.1/`. Write the clip list to `scripts/X.1/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1-8; `tasks/V1-evidence-plan.md`
(pre-registered rule for EVID-01: **holds** if corpus stream WER ≤ batch WER + 3.0 pts on en and uk
with `small`, and contradicted-push share ≤ 10%; otherwise DECIDE-01 reopens); `tasks/F.8-*.md`
(the fix under test: end-time anchoring + up-to-5-word n-gram de-dup, tiny-only numbers: stream
0.091 vs batch 0.061 on 81s EN, 0/78 contradicted).

Read source: `gmst/reconcile.py` (LocalAgreement.push/flush/_align/rebase), `gmst/pipeline/stream.py`
(`run_stream`, `decode()` — language pinned via `call_lang`, LID only fires when `language is None
and utt_lang is None`), `gmst/pipeline/batch.py` (`transcribe_by_region` — language pinned = one
whole-file call; not pinned = per-VAD-region LID, sticky), `gmst/transcribe/backends/faster_whisper.py`
(shipped default `per_segment_lid=True`, but irrelevant here since every `engine.transcribe` call in
this probe passes an explicit `language`), `gmst/metrics.py` (`word_errors` returns `(edits,
ref_words)` for corpus pooling), `gmst/config.py` (`lid_languages` default `("en","uk")`),
`tests/fakes.py::ListSource`, `gmst/transcribe/types.py` (`Segment.start/end`, not `t0/t1`).

Data: `eval/results/data/{en,uk,mixed}.jsonl`. First 20 rows of `en`/`uk`; first 20 rows of `mixed`
with `kind=="inter"` (per V1/task brief). Durations (`soundfile.info`): en 20 clips = 162.6s
(mean 8.13s), uk 20 clips = 103.0s (mean 5.15s), mixed-inter 20 clips = 298.8s (mean 14.94s).
Clip list written to `scripts/X.1/clips.txt` (60 lines: set-tag, id, wav path) before any run.

Script: `scripts/X.1/run_wer.py`, extending F.8's `probe_real_model_contradictions.py` (itself R1's
probe) to 3 sets and pooled corpus WER. Batch: en/uk = `engine.transcribe(clip, language=pinned)`
per clip, edits/ref_words summed over the 20 clips (`gmst.metrics.word_errors`, corpus pooling, not
per-clip mean); mixed = `gmst.pipeline.batch.transcribe_by_region(clip, cfg, engine)` with
`cfg.language=None` (the real not-pinned batch path: per-VAD-region auto LID), same pooling. Stream:
the set's 20 clips concatenated with 1.5s silence gaps (R1/F.8 methodology), fed as 100ms blocks to
`run_stream`, language pinned for en/uk, `language=None` (auto per-utterance LID) for mixed;
`word_errors` on the whole concatenated ref vs whole concatenated final output (one corpus-level
edit distance — there is no clip-boundary attribution once LocalAgreement commits across a gap).
`CountingLA` (F.8's wrapper) counts contradicted pushes and flush-dropped words. Engine: shipped
default `load_engine(cfg)` (`per_segment_lid=True`), `compute_device=cpu`, `compute_type=int8`.

Smoke test (`tiny`, 2 clips/set, foreground, not part of the reported numbers): all 3 sets batch +
stream ran without error; en stream 0/19 contradicted, uk 0/12, mixed 0/25 — sane before spending
budget on `small`/`large-v2`.

Checked `pgrep -af python` before starting: no other Python process running (only KDE plasmoid
helpers). Started `small` run (en, uk, mixed; batch+stream) in background
(`scripts/X.1/small_run.log`), offline (`HF_HUB_OFFLINE=1`), no large-* model loaded yet.

`small` run finished (`DONE` in `small_run.log`; `scripts/X.1/small_results.json` written). Wall
time: engine load 0.7s; batch en/uk/mixed 21.8s/19.9s/79.0s; stream en/uk/mixed 406.9s/136.5s/567.8s
(~18.5 min of stream decode alone, ~20.6 min total run). Confirmed no other Python process was
running throughout (checked again after completion via `pgrep -af python`).

Given `small`'s stream cost (en+uk stream alone = 543.4s ≈ 9 min) and X.2's measured large-v2
`detect_language` cost (~3.6s/call, constant regardless of prefix length — encoder pass is always
padded to a fixed 30s window), a full large-v2 run across all three sets was judged likely to exceed
the ~60 min budget in this node's brief. Started `large-v2` on **en and uk only**
(`scripts/X.1/run_wer.py large-v2 en uk`, `scripts/X.1/large-v2_run.log`), skipping mixed per the
node's pre-authorized fallback ("if large-v2 on all three sets would exceed [budget], run large-v2
on en and uk only and record what was skipped").

## Findings

**`small` run complete** (`scripts/X.1/run_wer.py small en uk mixed`, `scripts/X.1/small_run.log`,
`scripts/X.1/small_results.json`; shipped-default engine `faster_whisper`, `per_segment_lid=True`,
`compute_device=cpu`, `compute_type=int8`; no other Python process running before/during, offline).
Corpus WER (`gmst.metrics.word_errors`, pooled edits/ref_words, not per-clip mean):

| set | mode | WER | edits/ref | elapsed | decodes | contradicted/pushes |
|---|---|---|---|---|---|---|
| en | batch | 2.64% | 11/417 | 21.8s | — | — |
| en | stream | 6.95% | 29/417 | 406.9s | 179 | 0/179 |
| uk | batch | 23.78% | 34/143 | 19.9s | — | — |
| uk | stream | 27.27% | 39/143 | 136.5s | 98 | 0/98 |
| mixed-inter | batch | 11.02% | 65/590 | 79.0s | — | — |
| mixed-inter | stream | 33.39% | 197/590 | 567.8s | 293 | 0/293 |

Pre-registered rule (V1, EVID-01): **holds** if stream ≤ batch + 3.0 pts on en and uk with `small`,
and contradicted-push share ≤ 10%.

- en: stream − batch = 6.95 − 2.64 = **4.32 pts** > 3.0 pt threshold.
- uk: stream − batch = 27.27 − 23.78 = **3.50 pts** > 3.0 pt threshold.
- contradicted-push share: 0/179 (en), 0/98 (uk), 0/293 (mixed) = **0%** on all three sets, well
  under the 10% cap — F.8's timestamp-anchoring fix does what it was built for: not one push in
  570 total hit the terminal contradiction path.

**[serious] `fails` — the rule's WER margin is not met on either en or uk with `small`, despite zero
contradictions.** The stream vs batch gap is real amplification, not the contradiction bug F.8 was
built to close. Sample evidence (`small_results.json`, `sample_segments`, `ref_preview`/`out_preview`):
  - en: ref `...AND I DECLARE IT'S TOO BAD THAT...` → stream out `...And I declare it's too bad it is.
    An...` — casing/punctuation aside, extra/garbled words appear at utterance joins, unlike the
    F.8 tiny/81s-EN probe (0.091 stream vs 0.061 batch, +3.0 pts, under this same 3.0-pt bar) — a
    larger/more diverse en set with `small` crosses the line F.8's smaller probe did not.
  - uk: ref `...карі сірі блакитні...` → stream out `...карі, серій, блоквідні.` (batch, by contrast,
    got closer per the lower batch WER) — recognition noise compounded by streaming's shorter,
    re-decoded buffers rather than one full-clip context.
  - mixed-inter (not part of the pre-registered rule, but instructed to report): batch 11.02% →
    stream 33.39%, a **22.37-pt** gap, by far the largest of the three. Sample: ref `...ADVICE IT WAS
    REPUGNANT TO HIS LIBERAL NATURE це буде...` → stream out `...careful advice. was repugnant to his
    liberal nature. It will be absolutely normal...` — "IT" is dropped at the exact point the
    language should switch en→uk (the utterance-final "IT" is swallowed, then the uk clause is
    itself transcribed into English "It will be..." before flipping to Ukrainian). This is
    consistent with a documented, not re-argued, limitation (CLAUDE.md "Language mixture": sentence-
    level LID, sticky, sub-utterance switches un-caught) but the size of the effect — 3x the WER of
    batch on the same clips — is new evidence of how costly that limitation is for streaming
    specifically, since batch's per-VAD-region LID (`transcribe_by_region`) does not pay the same
    penalty (batch mixed WER 11.02% is close to en/uk-pinned batch quality, not degraded).

**[minor]** All three sets show 0 `flushes_dropping` / `flush_dropped_words` — the flush-drops-an-
unplaceable-tail path (`reconcile.py:130-140`) was never exercised in ~570 pushes across ~565s of
audio; it remains untested against a real model at this sample size (a note for future evidence, not
a defect).

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
