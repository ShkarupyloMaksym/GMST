id: T1
title: Triage: merge, dedupe and number the findings
parent: -
stage: triage
kind: task
agent: orchestrator
model: opus
effort: high
status: done
depends-on: R1, R2, R3, R4, R5, R6, R7

# T1 — Triage: merge, dedupe and number the findings

## Instructions

Read every review node's findings. Deduplicate, re-grade on the one scale (PLAN.md rule 2), and give each an ID: `FIX-nn` (clear fix, no decision needed), `DECIDE-nn` (needs the user), `EVID-nn` (needs a measurement first), `MAC-nn` (needs Apple hardware). Write the table here. Create one `F.n` child of `F` per group of related FIX items, and hand EVID items to V1.

## What was read / measured

Read every `## Findings` and `## Could not check` section of R1–R7 in full (2026-09-28), 57 raw
findings. Spot-checked in code before accepting: R1 trim point (`endpointer.py:88`, `stream.py:183`,
`reconcile.py:42-66`); R2 batch relabel (`faster_whisper.py:54-69`); R3 SIGINT-only (`grep -rn SIGTERM
src/` empty); R5 cache key (`run_eval.py:196`, `hyp/<system>.jsonl`); R6 `sse_port` range
(`config.py:85` vs `gmst.example.toml:39`); R7 `_cmd_bench` `return 0` (`cli.py:144`) and
`test_config.py:6` (no `delenv`). Load-bearing numbers (R1 stream WER 0.878, R2 11/12, R5 sample
sizes) are attributed to their node, not re-run here; EVID-01..03 re-measure them after the fixes.

## Findings

### From R1–R7, triaged (not re-counted by graph.py)

Re-grades against rule 2: **R4's drop-oldest test gap** blocking → serious (R4's own probe shows the
code is correct; only the test is blind). **R2 F4** (stream LID on a 1–4 s prefix) serious →
blocking (it emits wrong-language text on 58–60 of 60 EN→UK switches, the case the product exists
for). **R2 F1 + F2** merged (one mechanism). **R4's trim-test finding** merged into R1's trim
finding (it is why that bug stayed green). **R2 F3** and **R5's "gmst-batch measures raw
autodetect"** are one finding.

**Blocking (7)**

| ID | Finding | From | Route |
|---|---|---|---|
| DECIDE-01 | Trim cuts 0.2 s before the *end* of the last committed word; the sliver breaks `_align`, every later push is `contradicted`, `flush` drops the tail and its audio is discarded. Stream WER 0.878 vs batch 0.015 (`small`, 81 s EN). The test harness's 0.5 s marks are coarser than the back-off, so the suite is blind to it. | R1, R4 | the fix touches the reconcile contract → decision, then F; EVID-01 re-measures |
| DECIDE-02 | LID is never restricted to en/uk (Ukrainian decoded as `tr`/`ar`/`ru`/`bg`…; 11/12 utterances in the tiny stream run), and the sticky threshold does not guard the first utterance, which then anchors later low-confidence ones. | R2 F1+F2, R7 | new config field → decision |
| DECIDE-03 | Batch "per-segment LID" only relabels: text is faster-whisper's own first-window autodetect (60/60 identical), so `gmst-batch` in the eval measures raw autodetect under GMST's name. | R2 F3, R5 | how batch should decode per segment → decision |
| DECIDE-04 | Stream fixes each utterance's language from its first 1–4 s; Ukrainian after English stays `en` on 58–60/60. | R2 F4 | EVID-02 first (does the en/uk restriction alone fix it?), then decide |
| FIX-01 | No SIGTERM handler: `kill`/`systemctl stop`/`docker stop` skips drain, final flush and `sink.close()` (SRT file lost). | R3 | F.1 |
| FIX-04 | Eval hypothesis cache keyed by system name only; a `large-v3` run silently resumes a `tiny` run; no record names its model. | R5 | F.2 |
| EVID-03 | 60 clips/language gives ±4.6 pts; separating the candidates needs ~760 (v3/turbo) to ~2900 (turbo-uk/v2) paired clips. No CI is reported anywhere. | R5 | V1 (model-selection run) + FIX-05 (report CIs) |

**Serious (22)**

| ID | Finding | From | Route |
|---|---|---|---|
| FIX-02 | Second Ctrl-C during the drain still runs the final decode (now under `SIG_DFL`); a third kills without `sink.close()`; `KeyboardInterrupt` ends in a traceback. | R1 | F.1 |
| DECIDE-05 | Runtime status never reaches `gmst stream`: `[lagging]` not rendered, overflow counters never logged, no sustained-lag (> 10 s) warning; (minor) no idle indicator. | R3 ×3 + minor | where to surface it (stderr vs sink/schema) → decision |
| FIX-25a | PLAN.md row "loopback not installed → routing doc, exit 2" is unimplemented and contradicts CLAUDE.md/README/test (exit 1). Undetectable in general → amend the row, print a routing hint with the exit-1 message. | R3 | F.7 |
| FIX-05 | Eval reports mean per-clip WER, not corpus WER (tiny uk 68.21 vs 62.07); no CIs. | R5 | F.2 |
| DECIDE-06 | `real_cs` is empty and can never be filled from cleaned CV10 (0 Latin rows of 3204): there is no real code-switched audio in the harness. | R5 | data source → decision |
| FIX-06 | Raw baselines can never register a switch (faster-whisper segments have no `language`), and "per-language WER" scores LID × ASR jointly (`wer_uk` 100 for every system). | R5 | F.2 |
| FIX-07 | Synthetic `mixed`: *intra* cut mid-word (18/20) with a misaligned reference and a whole other sentence inserted; *inter* gaps < `min_silence_ms` in 15/20. | R5 | F.2 |
| FIX-11 | `gmst bench` decodes with faster-whisper's in-pass LID, not the shipped per-utterance path, and reports one WER where PLAN's exit criterion asks for UK and EN. | R5 | F.3 |
| FIX-13 | Bench amplification assumes decode cost ∝ buffer; measured fixed per-call cost makes the real load 4–6× the formula on 2–4 s buffers; LID pass omitted. | R5 | F.3 + EVID-04 (large models) + PLAN latency-budget amendment |
| MAC-05 | `MLX_CANDIDATES` omits `Yehor/whisper-large-v3-turbo-quantized-uk`, the best prior. | R5 | Mac (does an mlx conversion exist?) |
| FIX-15 | `mlx-whisper` is not declared in `pyproject.toml` (CLAUDE.md says "pin it"); its `ModuleNotFoundError` escapes as a traceback, not exit 2. | R2 F5 | F.4 |
| FIX-16 | `MlxWhisperEngine` loads lazily: `ModelUnavailable` can never fire at startup (fails at the first utterance, unwrapped), and bench folds load time into mlx RTF. | R2 F6 | F.4 (+ MAC-01 to verify) |
| DECIDE-07 | CLAUDE.md/PLAN.md say "CI runs the faster_whisper path only"; there is no CI config and no remote. | R6 | add a workflow vs strike the claim → decision |
| FIX-21 | `gmst.example.toml` documents `sse_port = 0` (any free port); `config.py:85` rejects it at load. | R6 | F.6 |
| FIX-24 | README's Linux routing row is not operable: `gmst devices` lists no `.monitor` source; needs `pactl set-default-source` / `PULSE_SOURCE`, undocumented. (+ minor: system `libportaudio` not mentioned.) | R6 | F.7 |
| FIX-14 | `gmst warmup` does not cache bench's four hardcoded candidates; Setup → Usage fails offline. | R7 | F.3 |
| FIX-12 | `gmst bench` exits 0 even when every candidate fails to load. | R7 | F.3 |
| FIX-20 | `test_defaults_when_no_file` fails when `GMST_MODEL` is exported (`assert 'tiny' == 'large-v3'`). | R7 | F.5 |
| FIX-18 | Drop-oldest queue test cannot distinguish drop-oldest from drop-newest (identical zero blocks; mutation passes 9/9). | R4 (re-graded) | F.5 |
| FIX-19 | `tests/fixtures/en.wav` / `uk.wav` promised, absent; no test runs real EN/UK audio through LID. | R4 | F.5 |
| FIX-27 | CLAUDE.md "verified end-to-end with real Silero VAD + tiny Whisper" / PLAN.md "clean ordered transcript" does not hold on real speech (R1: the realvad slow test feeds noise). | R1 | F.7, after DECIDE-01's fix lands |
| FIX-26 | Docs say faster-whisper LID is in-pass and free (`engine.py:5-6`, PLAN.md:77-79, `language_detection_segments=1` never passed); the budget has no LID row for the portable path; PLAN.md:98 signature lacks `prev_lang`. | R2 F8 | F.7 (+ EVID-04 measures the cost) |

**Minor (11)**

| ID | Finding | From | Route |
|---|---|---|---|
| FIX-23 | Prompt cap "~200 tokens" is wrong for both languages (uk 600 chars = 235 tokens > 223 window; en bound by the 100-word pre-cap). | R1 | F.6 |
| FIX-22 | A token that normalizes to empty (`-`, `…`) can never agree; commits stall until the 3-push force. | R1 | F.6 |
| FIX-17 | "run `gmst warmup`" hint attached to errors warmup cannot fix (`float16 on cpu`, `large-v9`). | R2 F7 | F.4 |
| FIX-09 | WER normalization: hyphens (`що-небудь` vs `що небудь` → WER 2.0) and numerals (refs fully verbalised). | R5 | F.2 (hyphen); numerals recorded as a known bias |
| FIX-08 | `run_eval --systems X` overwrites `scores.json` with only X. | R5 | F.2 |
| FIX-25b | `eval/` undocumented (run commands, extra deps `soundfile`/`soxr`/`jiwer`); PLAN layout lists a non-existent `backends/canary.py`. | R6 | F.7 |
| FIX-10 | `ruff` E501 at `eval/run_eval.py:6`. | R6 | F.2 |
| FIX-03 | Missing `--config` path dumps a traceback instead of a one-line error. | R7 | F.1 |
| (in DECIDE-05) | No idle indicator during silence. | R3 | — |
| (in FIX-24) | System `libportaudio` not mentioned in Setup. | R6 | — |
| (R4 minor) | Positive: contradiction guard, overlap anchor and unconditional `sink.close()` are adequately tested (mutations go red). | R4 | none |

**Mac (Could-not-check → MAC items, rule 6)**

| ID | Item | From |
|---|---|---|
| MAC-01 | `ModelHolder.get_model(repo, mx.float16)` helper name/signature and the shared-cache memory saving; bench's `_release_model_caches` actually frees unified memory. | CLAUDE.md, R2 |
| MAC-02 | `mlx_whisper.py:133-134`: float32 mel into a float16 model in `detect_language` — promotes (extra latency) or raises? Layout assumptions of `log_mel_spectrogram`, `mel[None]`, `probs[0]`. | R2 |
| MAC-03 | MLX LID cost per utterance (PLAN's ~150 ms) and streaming amplification on Apple Silicon; end-to-end latency ≲ 3 s. | R2, R5 |
| MAC-04 | BlackHole routing and the 10-min zero-overflow soak. | PLAN Phase 2 |
| MAC-05 | turbo-uk in `MLX_CANDIDATES` (see serious table). | R5 |
| MAC-06 | Stream WER with `mlx_whisper` after DECIDE-01's fix (the mechanism is backend-independent). | R1 |

**Evidence for V1**

| ID | Measurement | From |
|---|---|---|
| EVID-01 | Stream vs batch WER after DECIDE-01's fix, on `eval/results/data/{en,uk,mixed}`, `small` and `large-v2` (R1's probe). | R1 |
| EVID-02 | LID accuracy vs buffer prefix length (1/2/3/4 s/full) on uk and en clips, with and without the en/uk restriction, `small` and `large-v2`. Decides DECIDE-04. | R2 |
| EVID-03 | Model selection: corpus WER + 95 % CI, language pinned, full cleaned-CV10 uk (3204) + LibriSpeech test-clean subset, candidates large-v2 / large-v3 / (turbo, turbo-uk if downloadable), after F.2. Overnight on CPU. | R5 |
| EVID-04 | Per-update wall time vs buffer length (2/4/8/15 s) + `detect_language` cost, large-v2 and large-v3 CPU int8. Feeds FIX-13 and the PLAN latency-budget amendment. | R5, R2 F8 |

**Fix groups created:** F.1 shutdown & CLI errors · F.2 eval harness · F.3 bench · F.4 backends ·
F.5 tests · F.6 config & reconcile details · F.7 documents. Decision-dependent fixes (DECIDE-01..07)
become F.8+ once H1 records the choice. Suggested order: F.1 (FIX-01 is the only blocking fix with no
decision) → DECIDE-01 fix → DECIDE-02/03 fix → F.2 → EVID-03.

**Rule amendment (2026-09-28):** H1's `depends-on` narrowed from `T1, X` to `T1` — only DECIDE-04
needs evidence first (EVID-02); the others can be decided now.

## Could not check

Nothing re-measured here (see above); Mac items listed as MAC-01..06.

FINDING: recorded
