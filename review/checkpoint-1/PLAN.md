# Checkpoint-1 review — plan

basis: checkpoint-1 (8beade7)
branch: review-checkpoint-1
previous: none — first review of GMST

**Question.** Is the state tagged `checkpoint-1` sound enough to (a) use in a real English/Ukrainian
meeting on Linux with `faster_whisper`, and (b) build the remaining work on — the model-selection
eval, the Mac tasks, and Phase 4? **Scope:** everything in the tag: `src/gmst/`, `tests/`, `eval/`,
`PLAN.md`, `CLAUDE.md`, `README.md`, `gmst.example.toml`. `eval/results/` is git-ignored but present
locally; it is in scope as evidence, read-only.

The pattern is copied from the master-thesis repository (`review/checkpoint-1/` there): a graph of
node files, one agent and one model per node, a generated status table and dashboard.

## How this review is organised: a graph

Every unit of work is a **node**: one file, `tasks/<ID>-<slug>.md`. It has one agent, one model
(opus / sonnet / haiku, or human), its own instructions, and its own findings. `graph.py` derives
`STATUS.md`, `graph.json` and the dashboard from those files.

```
review ──► triage ──► evidence plan ──► evidence ──► decisions ──► fixes ──► close-out
(R1–R7)     (T1)         (V1)          (X.n, made    (H1, you)    (F.n, made   (Z1)
                                        by V1)                     by T1)
```

**Deepening a part = adding a child node.** Copy `templates/node.md` to `tasks/<parent>.<n>-<slug>.md`,
set `parent:` and a dotted id, and run `python3 graph.py`. A task that gains children becomes a group
automatically; its own file keeps its instructions and becomes the place where it synthesises its
children's findings. A group is done only when every child is done **and** its own synthesis is done.

**Choosing the model for a node**
- **opus:** judgment, attribution, synthesis, anything whose output becomes a DECIDE item; the
  streaming seams and the language-ID logic.
- **sonnet:** reading code and documents closely against a stated standard, and running scripts.
- **haiku:** mechanical sweeps with a precise rule.
- **human:** decisions. The model named in the node is passed to the Agent tool's `model` parameter
  when the node is spawned; it overrides the agent definition's default.

## Rules (pre-committed; amend only with a dated note)

1. **Reviews are read-only.** A review node writes only its own node file and `scripts/<ID>/`. It never
   edits code, documents, tests or config, and never runs git.
2. **Severity, one scale for every node.** `[blocking]` would lose or duplicate transcript text, emit
   wrong text or timestamps, crash or hang a session, or lead to a wrong model/engine/latency decision.
   `[serious]` would cost real time or trust (a misleading doc, an untested risky path, a silent
   degradation). `[minor]` is worth fixing but not urgent. Each finding is one bullet under
   `## Findings`, starting with its tag, and cites `file:line` or the command that showed it.
3. **Evidence is verbatim.** Quote with locators. Every number comes with the script that produced it,
   saved in `scripts/<ID>/`. Prefer a short probe that demonstrates a defect over an argument that one
   might exist.
4. **Measurements are cheap.** A review node may run the suite, existing scripts and small read-only
   probes (≤ 10 min wall). Anything bigger goes to V1's plan. Offline only: `HF_HUB_OFFLINE=1`, and use
   models already in the Hugging Face cache (`tiny`, `small`, `large-v2`, `large-v3`; the turbo repo
   failed to download). At most one `large-*` model loaded at a time across all running agents (15 GiB
   RAM); check `pgrep -af python` first and note when timings were measured under concurrency.
5. **Settled is settled.** The design choices in `PLAN.md` are inputs: LocalAgreement-2 as the commit
   policy, per-utterance LID via `Engine.detect_language`, pipeline-owned VAD, the `Engine` Protocol,
   macOS as the supported target, batch-before-streaming. A node may report that a choice has a
   *consequence nobody implemented*, or that evidence contradicts an assumption the plan states. It may
   not re-argue the choice.
6. **Mac-only is not a finding.** Anything that needs Apple hardware (the `mlx_whisper` backend,
   BlackHole, Metal timings) goes under `## Could not check` and becomes a `MAC-nn` item at triage.
   Reading the mlx code for bugs visible without running it *is* in scope.
7. **Triage numbering:** `FIX-01`, `DECIDE-01`, `EVID-01`, `MAC-01` are the first free IDs.
8. **Orchestrator:** one session integrates (`verify-then-integrate` skill), runs `graph.py`,
   republishes the dashboard, and commits after every node report with an explicit pathspec. At most
   three agents run at once.

## Leads from onboarding (2026-09-28) — verify, do not assume

Seen while onboarding, not yet checked. The node named owns each; confirming or refuting it is part of
its brief.

- **R2:** `resolve_language` (`src/gmst/transcribe/lid.py:24`) never restricts the detector to the
  meeting's languages. In `eval/results/hyp/gmst-batch.jsonl` Ukrainian clips are labelled `bg`, `ja`,
  `ru`; `gmst-batch` UK WER equals raw autodetect (68.21 %) while pinned language gets 41.54 % (tiny,
  n = 4 — too small to quote).
- **R4:** `PLAN.md` "Testing" says `tests/fixtures/en.wav` and `uk.wav` are committed for LID tests;
  `tests/fixtures/` holds only `README.md`.
- **R5 / R6:** `eval/` is not mentioned in `CLAUDE.md` or `PLAN.md`; `eval/run_eval.py:6` says
  `gmst-batch` is `large-v3`, while `scores.json` holds only `tiny` runs.
- **R6:** `uv run ruff check .` reports one E501 at `eval/run_eval.py:6`.

## Nodes at creation (2026-09-28)

| Stage | Node | Agent | Model |
|---|---|---|---|
| review | R1 Streaming seams (reconcile, endpointer, stream, turns) | code-reviewer | opus |
| review | R2 Language ID and engine backends | code-reviewer | opus |
| review | R3 Capture, failure modes and shutdown | code-reviewer | sonnet |
| review | R4 Test-suite adequacy | code-reviewer | sonnet |
| review | R5 Eval and bench methodology | code-reviewer | opus |
| review | R6 Documents vs code | doc-consistency-auditor | sonnet |
| review | R7 Clean-clone reproduction | repro-runner | sonnet |
| triage | T1 Triage | orchestrator | opus |
| plan | V1 Evidence plan | orchestrator | opus |
| evidence | X Evidence runs (group; V1 creates X.1 …) | repro-runner | sonnet |
| decision | H1 Your decisions | human | human |
| fix | F Fixes (group; T1 creates F.1 …) | orchestrator | sonnet |
| close | Z1 Close-out and checkpoint-2 | orchestrator | opus |

## Results ledger

_(the orchestrator appends: date — node — what changed in which file, and the commit)_
