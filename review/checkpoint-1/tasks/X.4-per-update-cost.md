id: X.4
title: EVID-04: per-update decode cost and LID cost, large models on CPU
parent: X
stage: evidence
kind: task
agent: repro-runner
model: sonnet
effort: medium
status: done
depends-on: -

# X.4 — EVID-04: per-update decode cost and LID cost, large models on CPU

## Instructions

Extend R5's `scripts/R5/p4_amplification.py` into `scripts/X.4/`: `large-v2` then `large-v3`, CPU int8, buffers 2/4/8/15 s cut from `eval/results/data/en` speech, 10 repetitions each after 2 warm-up calls, median and p90 wall time; `detect_language` on 3 s. Record `nproc`, threads used, and anything else running.

Read first: root `CLAUDE.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), `tasks/V1-evidence-plan.md` (the pre-registered rule for this node — do not change it), this file. Offline (`HF_HUB_OFFLINE=1`), one `large-*` model at a time machine-wide (check `pgrep -af python`), scripts and outputs in `scripts/X.4/`. Write the clip list to `scripts/X.4/clips.txt` before running. Report the numbers against the rule; a `fails` is a result, not something to tune away.

**Amended 2026-09-28 (before any X.4 run), after F.17 made streaming two-pass:** also time the
**final pass** — one `transcribe` of a whole utterance, plus one `detect_language` on it — for
utterances of 2, 5, 10 and 15 s (median of 5 after a warm-up), per model. That is the latency of
the final text after an utterance ends. Report it next to the per-update cost; the pre-registered
rule for the per-update cost is unchanged.

## What was read / measured

Read: root `CLAUDE.md`; `review/checkpoint-1/PLAN.md` rules 1–8; `review/checkpoint-1/tasks/V1-evidence-plan.md`
line 35 (EVID-04 rule, unchanged, not re-argued); this node file including the 2026-09-28 amendment;
`review/checkpoint-1/scripts/R5/p4_amplification.py` (base script, tiny/uk/1..15s/5-rep, extended
here to large-v2+large-v3/en/2,4,8,15s/10-rep+p90, plus the amended final-pass block);
`src/gmst/bench.py:7,38,110` (`UPDATE_INTERVAL_S = 1.0`, amplification definition);
`src/gmst/config.py:24-27,50` (`model_size` default, `compute_device`/`compute_type` fields,
`max_buffer_seconds`); `src/gmst/transcribe/backends/__init__.py:25-34` (`load_engine` signature);
`src/gmst/transcribe/backends/faster_whisper.py:42-43,46,86` (no `cpu_threads` override — CTranslate2
default/auto); `review/checkpoint-1/tasks/F.17-two-pass-streaming.md` (what "final pass" means:
`final_pass(upto)` — one whole-utterance `transcribe` + one `detect_language`, live LocalAgreement-2
buffer separate and kept < 4 s).

Script: `review/checkpoint-1/scripts/X.4/p_per_update_cost.py`. Clip list written first to
`review/checkpoint-1/scripts/X.4/clips.txt` (9 clips from `eval/results/data/en.jsonl`, manifest
order, concatenated to 60.0 s — the LibriSpeech-derived `en` set CLAUDE.md/PLAN.md's eval harness
uses, not uk, per the instruction to use `en` speech). Model cache confirmed present offline:
`~/.cache/huggingface/hub/models--Systran--faster-whisper-large-v2` and `-large-v3` (`ls
~/.cache/huggingface/hub`). Machine check before each run: `pgrep -af python` (only unrelated KDE
plasmoid `python3` processes and my own shell wrappers — no other large model loaded) and `uptime`
(load average ~1.0–1.1 before starting, 16 cores per `nproc`; ~4.2–4.6 during/after the two runs,
i.e. this machine's own baseline plus one `WhisperModel` int8 CPU run using CTranslate2's default
thread count — no `cpu_threads` override in `faster_whisper.py`, no `OMP_NUM_THREADS` set). Ran
`large-v2` then `large-v3` sequentially (never both loaded at once — confirmed via `pgrep` between
runs), each `HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.4/p_per_update_cost.py <model>`,
output tee'd to `scripts/X.4/out_large-v2.txt` and `out_large-v3.txt`. Each run: load engine, 2
warm-up `transcribe` calls, then for buffer ∈ {2,4,8,15} s: 10 reps, median+p90; then
`detect_language` on 3 s: 2 warm-ups + 10 reps, median+p90; then the amended final-pass block:
1 warm-up (`transcribe`+`detect_language` on 5 s), then for utterance ∈ {2,5,10,15} s: 5 reps each
of `transcribe` and `detect_language`, median reported (matches PLAN.md's language-mixture note
that `detect_language` runs per utterance as a separate encoder pass, and F.17's `final_pass`, which
runs both per utterance).

## Findings

**EVID-04 rule:** "(wall at 4 s + LID) ≤ 1.0 s → 1 update/s is feasible on this CPU; otherwise
record the smallest feasible update interval."

Raw numbers (CPU int8, 16 cores, load avg ~4.2–4.6/16 during runs, nothing else large running):

| model | buf 2s med/p90 | buf 4s med/p90 | buf 8s med/p90 | buf 15s med/p90 | LID(3s) med/p90 |
|---|---|---|---|---|---|
| large-v2 | 4.035 / 4.300 | 4.536 / 4.745 | 5.014 / 5.703 | 6.402 / 7.616 | 3.533 / 3.559 |
| large-v3 | 4.377 / 4.498 | 4.818 / 5.141 | 5.448 / 5.755 | 6.534 / 6.748 | 4.030 / 4.044 |

Rule check at buffer=4s: large-v2: 4.536 + 3.533 = **8.069 s** → **FAILS** (script's own printed
verdict: `FAILS`). large-v3: 4.818 + 4.030 = **8.848 s** → **FAILS**.

Smallest feasible update interval on this CPU: none of the tested buffers reach ≤1 s even
excluding LID — even the smallest buffer (2 s, effectively a floor since Whisper pads every call
toward its internal window) costs 4.0–4.4 s of wall time alone; the per-update decode floor by
itself is already 4–4.5× the 1 s target before LID is added. 1 update/s is infeasible for either
large model on this CPU; the smallest observed per-call cost (buffer=2s, large-v2, median 4.035 s,
LID excluded) implies a feasible update interval on the order of ≥5 s if LID is included, ≥4 s if
not — both far outside PLAN.md's implicit 1 Hz cadence.

- [fails] EVID-04's rule fails for both `large-v2` and `large-v3` on this CPU (int8): per-update
  cost at the 4 s reference buffer plus LID is 8.07 s (large-v2) / 8.85 s (large-v3), roughly 8×
  the 1.0 s budget, not a close miss. `PLAN.md`'s latency budget (`RTF ≤ ~0.15` for a 15 s buffer
  at 1 update/s, CLAUDE.md "Latency & throughput") is not met by either large model on x86 CPU
  int8 — consistent with CLAUDE.md's own framing that faster_whisper/CPU is the "portable
  fallback," not the latency-critical path (that's `mlx_whisper` on Apple GPU, MAC-only, not
  measurable here). This is not new information (R5/EVID-04's own premise already expected this),
  but it makes the smallest-feasible-interval number concrete: on this CPU, 1 update/s is not
  reachable by any margin with either large model — a real streaming deployment on the
  faster_whisper/CPU path would need either a much smaller model, a much larger update interval
  (≥5–9 s), or a smaller buffer than 4 s — none of which is currently configured as the default
  (`update_interval`/1.0 s literal in `bench.py:38` is not exposed as a `Config` field at all, so
  there is no way to raise it without a code change).

**Amended final-pass timing** (F.17 two-pass: one whole-utterance `transcribe` + one
`detect_language`, median of 5, after 1 warm-up):

| model | utt 2s | utt 5s | utt 10s | utt 15s |
|---|---|---|---|---|
| large-v2 transcribe | 4.259 | 4.892 | 5.919 | 6.783 |
| large-v2 detect_language | 3.487 | 3.526 | 3.535 | 3.521 |
| large-v2 total | 7.746 | 8.418 | 9.454 | 10.304 |
| large-v3 transcribe | 4.547 | 5.119 | 5.864 | 6.634 |
| large-v3 detect_language | 4.024 | 4.020 | 4.030 | 4.006 |
| large-v3 total | 8.570 | 9.139 | 9.894 | 10.639 |

- [serious] Under F.17's two-pass design, the *final* text for an utterance (the thing CLAUDE.md's
  "Streaming reconciliation" section treats as the reconciled, committed output) is not available
  until 7.7–10.6 s after the utterance ends, on this CPU, for either large model — this is on top
  of whatever live LocalAgreement-2 provisional latency already exists. `detect_language` alone
  costs 3.5–4.0 s regardless of utterance length (it is a fixed per-call cost, not proportional to
  input, matching R5's finding that Whisper pads every call toward its internal window) and is run
  a *second* time per utterance under F.17 (once live during LID pinning/detection, once again in
  `final_pass`) — CLAUDE.md's "End-to-end target is ≲ 3 s (Phase 3)" is already stated as aspirational
  for Phase 3, but F.17's two-pass final-text latency alone (final `transcribe` + final
  `detect_language`) exceeds that 3 s target by itself on CPU int8, before any live-pass time is
  added. F.17's own "Could not check" section flagged this ("Final-text latency ... is X.4 / MAC-03's
  to measure") — this closes that gap for the CPU path; the Mac/MLX path remains open (see below).

## Could not check

- Apple Silicon / `mlx_whisper` timings (MAC-03's territory per F.17's own note) — this machine has
  no Apple GPU; CLAUDE.md states macOS/MLX is the actual target for the latency story, so these CPU
  numbers should not be read as the final verdict on feasibility, only as the portable-fallback
  path's numbers, which is what EVID-04 asked to be measured here.
- Whether GMST's actual live-stream code path (`stream.py`'s LocalAgreement-2 loop, not this
  isolated `engine.transcribe`/`detect_language` probe) exhibits materially different per-call cost
  under real threading/queueing overhead — out of scope for this micro-benchmark, in scope for a
  soak test (already noted elsewhere as a remaining Mac/latency task).

FINDING: recorded
