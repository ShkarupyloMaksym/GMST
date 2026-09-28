# review/checkpoint-1 — the review graph

Review of the state tagged `checkpoint-1`, on branch `review-checkpoint-1`. The plan and rules are in
`PLAN.md`.

- **Status:** `python3 graph.py`, then `STATUS.md` → "Can start now".
- **Dashboard:** generated from `dashboard.template.html` into `dashboard.html` by `graph.py`, and
  republished (same URL, see the root `CLAUDE.md`) after every change. Never hand-edit it.
- **Nodes:** `tasks/<ID>-<slug>.md`, one writer each. Each names its agent (`.claude/agents/`) and
  model (opus / sonnet / haiku / human).
- **Go deeper on a part:** copy `templates/node.md` to `tasks/<parent>.<n>-<slug>.md`, set `parent:`,
  and rerun `graph.py`.
- **Run a node:** spawn its agent with the node's model, and give it the node file's path. When it
  reports, run `graph.py`, republish, and commit with an explicit pathspec.
