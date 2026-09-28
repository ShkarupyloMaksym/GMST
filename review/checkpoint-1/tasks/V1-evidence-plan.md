id: V1
title: Evidence plan: design the measurements
parent: -
stage: plan
kind: task
agent: orchestrator
model: opus
effort: medium
status: done
depends-on: T1

# V1 — Evidence plan: design the measurements

## Instructions

For each `EVID-nn`, pre-register the measurement: data, model, command, the number that decides it and the threshold, **before** running anything. Create one `X.n` child of `X` per measurement with its own node file. The model-selection eval (four candidates, sample size from R5) is expected to be one of them.

## What was read / measured

Read T1's EVID table, R1's `probe_real_model_contradictions.py`, R2's `lid_probe.py`, R5's
`p4_amplification.py` / `p5_sample_size.py`, and the local data (`eval/results/data/{en,uk,mixed}`,
60/60/40 clips; `eval/results/cv10-uk-testset-clean`, 3204 clips). HF cache holds `tiny`, `small`,
`large-v2`, `large-v3`; turbo and turbo-uk are not cached. Rules pre-committed below on
2026-09-28, before any X node ran.

## Findings

### Pre-registered measurements (2026-09-28)

| Node | EVID | Needs | Deciding number | Rule |
|---|---|---|---|---|
| X.1 | EVID-01 | F.8 (DECIDE-01 fix) | corpus WER stream − batch, language pinned; share of contradicted pushes | **holds** if stream ≤ batch + 3.0 pts on en and uk with `small`, and contradicted pushes ≤ 10 %; otherwise DECIDE-01 reopens |
| X.2 | EVID-02 | nothing | restricted-LID accuracy by prefix length (1/2/3/4 s/full), per language | ≥ 95 % on both at 2 s → DECIDE-04 = detect once at ≥ 2 s of buffer; ≥ 95 % only at full → re-detect on every decode until the endpoint; < 95 % even at full → record, DECIDE-04 needs a design |
| X.3 | EVID-03 | F.2 (eval fixes) | UK corpus WER + paired-bootstrap 95 % CI of each pairwise difference; EN corpus WER | default = lowest UK WER whose CI vs the runner-up excludes 0, provided its EN WER is within 2.0 pts of the best; if not separable, the cheaper one per X.4 |
| X.4 | EVID-04 | nothing | median wall time per decode at 2/4/8/15 s + `detect_language` at 3 s, large-v2 and large-v3 CPU int8 | (wall at 4 s + LID) ≤ 1.0 s → 1 update/s is feasible on this CPU; otherwise record the smallest feasible update interval. Either way PLAN.md's latency budget is amended with the measured fixed cost (FIX-13) |

*Amendment 2026-09-28 (user): X.3 runs on 800 uk clips, not the full 3,204 — see X.3's node; the
turbo-uk vs large-v2 pair is then expected to stay unresolved.*

Common: offline, one `large-*` model at a time machine-wide, results and scripts in
`scripts/X.n/`, a wall-clock note if anything else was running. Clip lists are fixed by manifest
order (first N) and written to `scripts/X.n/clips.txt` before the run.

## Could not check

X.3's turbo and turbo-uk candidates need a download (rule 4 is offline): X.3 asks the user before fetching them, or runs on large-v2 / large-v3 only.

FINDING: recorded
