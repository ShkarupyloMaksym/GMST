id: Z1
title: Close-out and checkpoint-2
parent: -
stage: close
kind: task
agent: orchestrator
model: opus
effort: medium
status: done
depends-on: F

# Z1 — Close-out and checkpoint-2

## Instructions

Confirm every FIX is done or explicitly deferred, every MAC item is listed in `PLAN.md`, `CLAUDE.md` / `PLAN.md` reflect what changed, the suite and ruff are green. Write `changes.md` (what the review changed) and tag `checkpoint-2` on `main` after the user merges.

## What was read / measured

2026-09-29. Gates: `uv run pytest -q` 200 passed; `HF_HUB_OFFLINE=1 uv run pytest -q -m slow` 5
passed, 1 skipped (mlx, Linux); `uv run ruff check .` clean. 56 commits on `review-checkpoint-1`
since `checkpoint-1`; `src/` + `tests/`: 38 files, +2092 / −212. Every FIX is done or superseded;
MAC-01…06 and the deferred items are listed in root PLAN.md "Open after the checkpoint-1 review";
CLAUDE.md / PLAN.md / README describe the code as it is (two-pass, restricted LID, turbo default,
experimental curated glossary). Eleven stale background wait loops left by agents (`pgrep -f`
matching their own shell, so they never ended) were stopped; no process is left running.

## Findings

- `review/checkpoint-1/changes.md` written.
- **Not done here, by rule:** merging to `main` and tagging `checkpoint-2` — the user merges
  `review-checkpoint-1`, then `git tag checkpoint-2` on `main` (the user pushes).

## Could not check

The Mac items (MAC-01…06).

FINDING: recorded
