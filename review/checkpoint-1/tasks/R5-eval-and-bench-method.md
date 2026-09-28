id: R5
title: Eval and bench methodology
parent: -
stage: review
kind: task
agent: code-reviewer
model: opus
effort: high
status: todo
depends-on: -

# R5 — Eval and bench methodology

## Instructions

Review `eval/build_sets.py`, `eval/run_eval.py`, `src/gmst/bench.py` and `src/gmst/metrics.py` as the instruments that will pick the default model (`CLAUDE.md` "Model default is provisional"). Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Questions: (1) Are the WER numbers comparable to the `egorsmkv/speech-recognition-uk` leaderboard they are meant to reproduce (same test set, same normalization — casing, punctuation, apostrophes ʼ/'/’, numerals)? (2) Do the synthetic `mixed` inter/intra clips and `real_cs` measure what they are named for, and are per-language WER and `switch_detected` computed correctly? (3) Is `gmst bench`'s "streaming amplification" the quantity `PLAN.md` "Latency budget" defines? (4) What sample size per set is needed to separate the four candidates at the leaderboard's gaps (13.7 / 20.5 / 22.8 / 12.8 % WER) — compute it, don't guess. (5) Is `eval/results/` reproducible from the scripts (the onboarding lead on `tiny` vs `large-v3`)? You may re-score from cached hypotheses (`--score-only`) and run ≤ 10 min with `tiny`; propose anything bigger as child nodes for V1.

## What was read / measured

_(write as you go: files and line ranges read, commands run, where you stopped)_

## Findings

_(one bullet per finding: `- [blocking|serious|minor] <claim> — <file:line or command>`, then the evidence)_

## Could not check

_(and why)_

FINDING: _(clean | findings | recorded | blocked)_
