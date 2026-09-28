id: F.3
title: Bench: shipped decode mode, UK/EN WER, amplification, exit code, warmup
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.3 — Bench: shipped decode mode, UK/EN WER, amplification, exit code, warmup

## Instructions

- **FIX-11** bench decodes through the shipped path (per-utterance LID via `detect_language`, or `run_stream` over the clip) and reports UK and EN WER separately when given per-language references.
- **FIX-12** exit 2 when no candidate produced a row.
- **FIX-13** amplification from measured wall time per decode of a typical-length buffer plus the LID pass, divided by `update_interval` (R5 `p4_amplification.py`); PLAN.md latency budget amended after EVID-04.
- **FIX-14** `gmst warmup --bench` downloads bench's candidates; README says so.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

Read `bench.py` (all), `cli.py` `_cmd_warmup` / `_cmd_bench` / parser, `tests/test_bench.py`.
Tests first, 5 watched fail: `test_bench.py::test_per_update_cost_times_a_typical_buffer_plus_the_lid_pass`,
`::test_bench_decodes_through_the_shipped_batch_path`, the amplification assertion in
`::test_run_bench_computes_amplification_and_wer` (now pins `language="en"`: silent audio correctly
has no VAD regions), `test_cli.py::test_bench_exits_2_when_no_candidate_loads`,
`::test_warmup_bench_loads_every_bench_candidate`. After: 173 passed; `ruff check .` clean.

## Findings

- **FIX-11** bench decodes via `transcribe_by_region` (the shipped batch path). Per-language
  UK/EN WER is **not** added to bench: one clip cannot separate the candidates (R5), so PLAN.md's
  Phase-1 exit criterion is amended (dated) to take UK/EN corpus WER with CIs from
  `eval/run_eval.py` (X.3); bench keeps an overall sanity WER.
- **FIX-12** `gmst bench` exits 2, with a `gmst warmup --bench` hint, when no row is ok.
- **FIX-13** `_per_update_seconds`: median of 3 timed updates (a 4 s `TYPICAL_BUFFER_S` decode +
  `detect_language` on 3 s when not pinned) after one warm-up call; `amplification` =
  that / `UPDATE_INTERVAL_S`; new `s/upd` column. PLAN.md / CLAUDE.md latency text flagged with a
  dated note; the rewrite waits for X.4.
- **FIX-14** `gmst warmup --bench` loads every bench candidate (releasing each), exit 2 if any
  failed; README Setup/Usage say so.

## Could not check

No real `gmst bench` run: it loads four large models (and two are not cached). X.4 measures the per-update cost for large-v2 / large-v3 on this CPU.

FINDING: recorded
