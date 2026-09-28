id: F.11
title: DECIDE-04 fix: stream re-detects until 3 s and holds commits
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.11 — DECIDE-04 fix: stream re-detects until 3 s and holds commits

## Instructions

Implement DECIDE-04 in `run_stream`: while the utterance's buffer holds < `lid_settle_seconds` (new config field, default 3.0, validated) of audio and the language is not pinned, call `detect_language` on every decode (with the previous utterance's language as `prev_lang`) and hold commits — emit partials only; once ≥ 3 s, fix the language for the rest of the utterance and commit normally. An utterance that endpoints before 3 s uses its last detection and commits at the flush. Tests: a `FakeEngine` whose LID says `en` on the first 1–2 s and `uk` from 3 s must commit nothing before 3 s and decode the committed words in `uk`; the pinned-language path must not call LID at all. Also update PLAN/CLAUDE latency text (up to ~3 LID passes per utterance).

Protocol: `verify-then-integrate` skill — regression test first, watch it fail, then fix;
`uv run pytest -q` and `uv run ruff check .` green; commit with an explicit pathspec. The decision:
root PLAN.md "Review decisions".

## What was read / measured

Tests first (`test_stream_pipeline.py`): `test_stream_settles_the_language_at_3s_and_commits_nothing_before`
(LID says `en` < 2.5 s, `uk` after: every final is `uk`, all 10 words once, LID stops after
settling) and `test_a_short_utterance_still_commits_with_its_last_detection` watched fail;
`test_a_pinned_language_never_runs_lid` passed before and after. The first two initially failed
after the fix too, on the fake reading silence as "w0" — the tests now ignore that token. `uv run
pytest -q` 179 passed; ruff clean. The tiny 81 s English probe (language pinned) is unchanged:
stream WER 0.091 (`scripts/F.8/tiny6_after_F11.out`).

## Findings

- `Config.lid_settle_seconds = 3.0` (validated ≥ 0; `0` restores detect-once).
- `run_stream`: `settled` flag; while unsettled every decode re-runs `detect_language` and the
  hypothesis is emitted as a partial only (no `push`); at an endpoint / forced cut before settling
  the hypothesis is committed whole via `absorb`. A forced cut / stall no longer resets the
  utterance's language (it splits one utterance); only a real endpoint does.
- Docs: `gmst.example.toml`, PLAN.md config table and latency row, CLAUDE.md "Language mixture".

## Could not check

Latency cost not measured: up to ~3 LID passes per utterance (≈ 3.6 s each for large-v2 on this CPU, X.2) — X.4 measures it; on the Mac it is MAC-03.

FINDING: recorded
