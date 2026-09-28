id: F.9
title: DECIDE-02 fix: `lid_languages`, restricted and renormalised LID
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.9 — DECIDE-02 fix: `lid_languages`, restricted and renormalised LID

## Instructions

Implement PLAN.md "Review decisions" DECIDE-02: config field `lid_languages` (default `["en", "uk"]`, validated in `_merge`, env `GMST_LID_LANGUAGES` comma-separated, documented in `gmst.example.toml` and PLAN.md's config table). `resolve_language` renormalises `all_probs` over the allowed set with `ru` folded into `uk`, so the first utterance is covered; the sticky threshold applies to the renormalised probability. Tests: R2's cases (`bg`, `ja`, `tr`, `ar` top-1 on Ukrainian; first utterance at 0.21) in `test_lid.py`.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; commit with an
explicit pathspec. Items and evidence: T1's triage table; the decision: root PLAN.md "Review
decisions".

## What was read / measured

Read `lid.py`, `config.py`, both backends' `detect_language`, `test_lid.py`,
`test_backend_lid_windows.py`. Tests first, 9 watched fail: seven in `test_lid.py` built from R2's
recorded distributions (`bg` 0.40 top-1 on Ukrainian, first utterance `ar` 0.21, `ru` 0.972 vs `uk`
0.012, the uk/ru 0.11/0.10 noise case, confident English, `ru` explicitly allowed, no
distribution), `test_config.py::test_lid_languages_default_and_sources` (default, TOML list, env
`"uk, en"`), `test_backend_lid_windows.py::test_detect_language_is_restricted_to_lid_languages`.
The four invalid-value cases first passed for the wrong reason (unknown key); their match was
tightened to `"lid_languages: "`. `uv run pytest -q`: 160 passed; ruff clean.

## Findings

- `Config.lid_languages: tuple[str, ...] = ("en", "uk")`, validated in `_coerce` (non-empty list
  of 2–3-letter lowercase codes; a bare string is split on commas, which is how
  `GMST_LID_LANGUAGES` arrives), env `GMST_LID_LANGUAGES`.
- `resolve_language(..., allowed=...)`: sums the distribution per allowed language (`ru` → `uk`
  unless `ru` is listed), best wins, sticky threshold on that mass, `fallback` = previous language
  or the first allowed one when nothing allowed is present. `allowed=None` keeps the old path, so
  the eight earlier tests are untouched.
- Both backends pass `allowed=self._cfg.lid_languages`.
- Docs: `gmst.example.toml`, PLAN.md "Language ID" and config table + env list, CLAUDE.md
  "Language mixture" and "Config".

## Could not check

No real-model run here: X.2 measures the same rule (argmax over {en, uk+ru}) on 60+60 clips with `small` and `large-v2`. The `lid_prob` reported for restricted LID is now the folded mass, not the raw top-1 probability.

FINDING: recorded
