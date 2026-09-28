---
name: verify-then-integrate
description: The single-writer protocol for applying review agents' proposals to shared GMST files (src/, tests/, PLAN.md, CLAUDE.md, README.md) — reproduce the defect first, fix with a test that fails before and passes after, propagate every copy of a changed claim, gate the commit on pytest + ruff. Use as the orchestrator of any review/*/ investigation.
---

# Verify, then integrate

You are the only writer of shared files. Agents propose; you decide what survives.

## Before applying a proposal

1. **Read the finding's exact text and its probe**, not a summary.
2. **Re-run the probe yourself** (`review/checkpoint-1/scripts/<ID>/`). A finding whose probe you
   cannot reproduce is recorded as such, not fixed.
3. **Check proposals that touch the same file** and merge them into one edit.
4. **Check whether the fix changes a documented contract** — the `Engine` Protocol, the `Segment`
   timestamp contract, the pinned JSONL/SSE schema, exit codes, a config field. If it does, it is a
   `DECIDE` item for the user, not a fix.

## Applying

- Write the regression test first and watch it fail. For streaming seams, the test's engine must
  react to the audio it is handed (`_marked_engine`), or it cannot catch the bug.
- When a claim changes, **grep every copy** across `CLAUDE.md`, `PLAN.md`, `README.md`,
  `gmst.example.toml`, docstrings and test docstrings — including paraphrases.
- Supersede in place in PLAN.md: strike or annotate with a dated note; don't silently rewrite history.

## Before committing

- `uv run pytest -q` and `uv run ruff check .` — gate on their exit status, not on printed output.
  Check `pgrep -af pytest` first; never stack runs.
- `git add` with an **explicit pathspec**; message via `git commit -F - <<'EOF'` (backticks in `-m "..."`
  are shell-substituted). End with the attribution lines the session specifies.
- Append to the investigation's Results ledger in its PLAN.md.
