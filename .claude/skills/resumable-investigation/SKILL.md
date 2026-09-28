---
name: resumable-investigation
description: How to run or join a multi-node, multi-agent investigation in GMST that must survive session limits — one writer per file, pre-committed rules, graph.py-derived STATUS/dashboard, write-as-you-go, commit after every report. Use when working in review/*/ or setting up a new investigation of that shape (an eval campaign, a Mac verification pass).
---

# Resumable investigation

GMST runs reviews as directories of small node files that parallel agents can work on and that a
cut-off session can resume without losing anything. The pattern is copied from the user's
master-thesis repository. First instance: `review/checkpoint-1/`.

## Layout

```
<investigation>/
  PLAN.md       question, pre-committed rules, node list, Results ledger; `basis:`/`branch:` header lines
  README.md     how to resume, in five lines
  graph.py      stdlib only; derives STATUS.md, graph.json and dashboard.html from the node files
  STATUS.md, graph.json, dashboard.html   GENERATED — never hand-edited
  dashboard.template.html
  tasks/<ID>-<slug>.md   one per node, ONE WRITER each
  scripts/<ID>/          every script that produces a number — committed, never scratch-only
  templates/node.md      copied by the orchestrator; not scanned
```

## Node file

Header lines: `id`, `title`, `parent`, `stage`, `kind`, `agent`, `model`, `effort` (optional), `status`
(`todo | in-progress | done | blocked`), `depends-on`. Then `## Instructions`, `## What was read /
measured`, `## Findings`, `## Could not check`, and a final `FINDING: clean | findings | recorded |
blocked` line. `graph.py` marks a `done` node INCOMPLETE if the FINDING line or the read/measured
section is missing.

## Rules

1. **Pre-commit the rules before any evidence.** Amend with a dated note — never edit a rule. Never
   retune a threshold to turn a failing measurement into a passing one.
2. **One writer per file.** A node writes only its own file and `scripts/<ID>/`. Shared files (code,
   tests, PLAN.md, CLAUDE.md) are written only by the orchestrator (`verify-then-integrate` skill).
3. **Write as you go.** Set `status: in-progress` first; record commands and numbers the moment you
   have them.
4. **Save scripts in the repository**, never only in a scratchpad.
5. **Evidence is verbatim.** Quotes with locators; numbers with the script that produced them.
6. **The orchestrator commits after every agent report**, with an explicit pathspec.
7. **At most three agents at once; at most one `large-*` Whisper model loaded machine-wide** (15 GiB RAM).

## Resuming

`cd` into the investigation, run `python3 graph.py`, read `STATUS.md` → "Can start now". An
`in-progress` node's "What was read / measured" section says where it stopped — read it before
redoing anything.
