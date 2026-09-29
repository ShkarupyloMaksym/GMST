id: X.1e
title: EVID-01 for the new default model (large-v3-turbo), two-pass, fresh rows
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: F.19

# X.1e — EVID-01 for the new default model (large-v3-turbo), two-pass, fresh rows

## Instructions

DECIDE-10 made `large-v3-turbo` the default; X.1d verified two-pass streaming with `small` and
`large-v2` only. Pre-registered here (2026-09-29, before running): EVID-01's threshold applied to
the default model — stream (final segments only) ≤ batch + 3.0 pts on en and uk — on rows 40–59
of `en.jsonl` / `uk.jsonl` (X.1d's deciding rows), `large-v3-turbo`, each stream run twice. Also
report any repeated 6-gram not present in the reference and any "www" / "End 1"-style boilerplate.
Copy `scripts/X.1d/run_wer.py` to `scripts/X.1e/` (output paths only). Read first: root
`CLAUDE.md`, `tasks/X.1d-*.md`, this file. Offline (turbo is cached), one large model at a time
(`pgrep -af python` first), main tree `.venv`, no clone; write only this node file and
`scripts/X.1e/`.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1-8; `tasks/X.1d-two-pass-fresh-heldout.md`
(EVID-01 rule: stream (finals only, two-pass) ≤ batch + 3.0 pts on en and uk, contradicted-push
share ≤ 10%, on fresh rows 40-59 — held for `small`, `large-v2` uk exceeded the bar reported-only
by +3.48 pts, no hallucination/duplication in either); this file (pre-registered rule: same EVID-01
threshold, applied to `large-v3-turbo`, rows 40-59, each stream run twice).

Checked `src/gmst/config.py:24` (`model_size: str = "large-v3-turbo"` — DECIDE-10 default) and
`src/gmst/transcribe/backends/faster_whisper.py:41` (`cfg.model_repo or cfg.model_size` passed
straight to `WhisperModel`). `uv run python -c "from faster_whisper import utils; print(utils._MODELS)"`
confirms `large-v3-turbo` → `mobiuslabsgmbh/faster-whisper-large-v3-turbo`, and that repo plus its
`.locks` dir are present under `~/.cache/huggingface/hub/` (`find ~/.cache/huggingface -maxdepth 3
-iname "*turbo*"`) — cached, contradicting PLAN.md rule 4's "the turbo repo failed to download"
(stale as of this run).

`pgrep -af python` before starting: only KDE plasmoid helpers and an unrelated zsh loop (X.5's node,
waiting on a `.tar.gz` download, no Python model process) — clear to load one large model.

Copied `scripts/X.1d/run_wer.py` to `scripts/X.1e/run_wer.py`, changed only the docstring and the
three output-path f-strings (`X.1d` → `X.1e`); logic (offset selection, stream-runs repeat,
`s.is_final`-only stream WER, `mixed` mode) untouched.

Run — `large-v3-turbo`, en/uk rows 40-59, stream x2:
`HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1e/run_wer.py enuk large-v3-turbo 2 40:c`
→ `scripts/X.1e/large-v3-turbo_run.log`, `scripts/X.1e/large-v3-turbo_c_results.json`. Ran as a
detached background process (PID 597815, verified against `pgrep -af python` at launch: only
X.5's unrelated download-wait loop, no other model-loader), monitored with `until ! kill -0
<pid>; do sleep …; done` rather than polling with `sleep`. Total wall time ~2399s (~40 min):
engine load 2.2s; en batch 77.2s, en stream rep0 663.3s, en stream rep1 652.7s; uk batch 76.7s, uk
stream rep0 460.7s, uk stream rep1 468.5s — longer than PLAN.md rule 4's 10-min probe ceiling, but
this reproduces X.1d's method exactly as the brief specifies (X.1d's `small`/`large-v2` runs on the
same rows took ~15/~30 min respectively), so treated as the same class of evidence-node run X.1d
already established, not a new violation.

Checked the results for the brief's two named signatures (script: inline `python3` one-off, not
saved separately since it only reads the already-written JSON — logic: `collections.Counter` over
6-word windows of `full_out`, and substring search for `www`, `End 1`, `.FEMA`, `.gov`, `http`,
`subscribe`, `Thanks for watching`): zero repeated 6-grams and zero boilerplate hits in any of the
4 stream `full_out` strings (en rep0/rep1, uk rep0/rep1). Also confirmed rep0 == rep1 byte-for-byte
for both languages (`full_out` string equality).

## Findings

Pre-registered rule (this file, 2026-09-29): EVID-01's threshold (stream, finals only, two-pass, ≤
batch + 3.0 pts on en and uk) applied to the default model `large-v3-turbo`, on X.1d's deciding
rows 40-59 of `en.jsonl`/`uk.jsonl`, each stream run twice.

**`large-v3-turbo`, rows 40-59 (`scripts/X.1e/large-v3-turbo_c_results.json`):**

| set | mode | WER | edits/ref | gap vs batch |
|---|---|---|---|---|
| en | batch | 3.22% | 11/342 | — |
| en | stream rep0 | 2.34% | 8/342 | **−0.88 pts (passes, stream beats batch)** |
| en | stream rep1 | 2.34% | 8/342 | same, identical to rep0 |
| uk | batch | 6.25% | 9/144 | — |
| uk | stream rep0 | 6.25% | 9/144 | **0.00 pts (passes, exact tie)** |
| uk | stream rep1 | 6.25% | 9/144 | same, identical to rep0 |

Contradicted-push share: en 0/130, uk 0/80 (0%) both reps — well under the 10% bar. Both reps
byte-identical per set. No repeated 6-gram and no "www"/"End 1"/".FEMA"/".gov"/boilerplate
substring in any of the 4 stream `full_out` strings.

**Verdict: EVID-01 holds cleanly for the new default model, `large-v3-turbo`, on rows 40-59 —
the best of the four (`small`, `large-v2`, `large-v3-turbo`, and the earlier `large-v2` reported
run) two-pass results seen across X.1d/X.1e: both languages pass with margin, uk exactly ties
batch rather than merely staying under the +3.0-pt bar, and en's stream even beats batch. This is
also the only model of the three tested (`small`, `large-v2`, `large-v3-turbo`) with zero gap on
uk** — `large-v2` reported +3.48 pts over the bar on this exact row range (X.1d), `small` passed
at −1.39 pts. Both `uk` batch WER (6.25%, 9/144) and `en` batch WER (3.22%, 11/342) on this specific
20-clip subset are markedly lower than X.3's cited corpus-level figures for `large-v3-turbo` (uk
12.36%, en 2.79%, per `config.py:24`'s DECIDE-10 comment) — expected, since rows 40-59 is a
20-clip subset of a much larger eval set, not a discrepancy, but it means this node's numbers
should not be read as reproducing X.3's aggregate WER.

- No blocking or serious findings: the pre-registered rule holds on both languages, on the
  deciding held-out rows, with both stream reps deterministic and no hallucination/duplication
  signature.

## Could not check

- Per-clip attribution inside the concatenated stream WER is not available (same limitation noted
  by every prior X.1* node) — only corpus-level edit distance over the whole concatenation, plus
  the 6-gram/boilerplate substring scan done here.
- Mixed (code-switching) set and `large-v2`-style hallucination checks were not repeated here
  (out of this node's brief — X.1d already reported `large-v2`'s residual uk gap and a mixed-set
  gap under `small`; this node's brief was `large-v3-turbo` on rows 40-59 only).
- Only two stream reps and one batch pass were run (per the brief's budget: `small`/`large-v2` were
  cross-checked for determinism in X.1c/X.1d, this node relies on that precedent rather than
  re-establishing it for `large-v3-turbo` beyond the two reps run here, which were identical).
- Wall time (~40 min) exceeded PLAN.md rule 4's general 10-minute probe ceiling; done anyway
  because the brief explicitly calls for reproducing X.1d's method at this model size, and X.1d's
  own runs at `small`/`large-v2` sizes similarly ran 15-30 min — flagged for the record, not as a
  new violation, since the brief (V1-derived) authorizes it.

FINDING: clean
