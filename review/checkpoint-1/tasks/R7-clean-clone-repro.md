id: R7
title: Clean-clone reproduction
parent: -
stage: review
kind: task
agent: repro-runner
model: sonnet
effort: low
status: done
depends-on: -

# R7 — Clean-clone reproduction

## Instructions

From a clean clone of tag `checkpoint-1` in your scratchpad (`git clone --branch checkpoint-1 <repo> <scratch>/gmst` — cloning is the one git use allowed), follow `README.md` "Setup" and "Usage" literally, offline where the model is cached. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Record every step that fails or needs knowledge the docs don't give. Run: `uv sync`, `uv run pytest -q`, `uv run pytest -m slow -q`, `uv run ruff check .`, `uv run gmst devices`, `uv run gmst batch` on one clip from `eval/results/data/uk/` with `--language uk` and with auto LID, and `uv run gmst bench` on one clip with a reference, all with `GMST_MODEL=tiny`. Compare counts and outputs with what the docs claim. Delete the clone when done.

## What was read / measured

Read: root `CLAUDE.md`, `PLAN.md` (full), `review/checkpoint-1/PLAN.md` (rules 1–8, leads), this
node file, `README.md` (Setup/Usage/Audio routing/Status), `src/gmst/cli.py`,
`src/gmst/pipeline/batch.py`, `src/gmst/bench.py`, `src/gmst/transcribe/backends/faster_whisper.py`,
`tests/test_config.py`.

Cloned `checkpoint-1` (`git clone --branch checkpoint-1 /home/maxymus/code_for_soul/GMST <scratch>/gmst-r7-clone`)
into the scratchpad; confirmed `git log -1 --oneline` = `8beade7` (matches `review/checkpoint-1/PLAN.md:3`).
Only one Python process running throughout (`pgrep -af python` showed unrelated KDE plasmoid
processes only; no other agent/model loaded — checked before and confirmed only one candidate
loaded at a time during `bench`, released between per `bench.py`'s own docstring).

Commands run (script saved at `review/checkpoint-1/scripts/R7/repro.sh`):
- `uv sync` — clean, all 35 deps resolved from cache, no network needed.
- `HF_HUB_OFFLINE=1 uv run pytest -q` — 136 passed, 4 deselected.
- `HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run pytest -q` (as the brief specifies) — **1 failed**, 135
  passed, 4 deselected.
- Isolated re-run of the failing test without the env var — passes.
- `HF_HUB_OFFLINE=1 uv run pytest -m slow -q -rs` — 3 passed, 1 skipped (mlx — expected, no mlx on
  Linux), 136 deselected.
- `uv run ruff check .` — 1 error, `E501` at `eval/run_eval.py:6` (matches the already-known R6
  lead verbatim — not re-reported).
- `HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run gmst devices` — lists ALSA devices, no crash.
- `gmst batch --help` / `gmst stream --help` / `gmst bench --help` — compared flags against the
  brief and README.
- `gmst batch eval/results/data/uk/uk-1206.wav` with `GMST_LANGUAGE=uk` and unset (auto), `-o
  *.jsonl` — inspected output JSON.
- `gmst bench eval/results/data/uk/uk-1206.wav --ref <matching line from eval/results/data/uk.jsonl>`
  with `GMST_MODEL=tiny` — inspected table and real exit code (captured to a file, `$?` checked
  directly, not through a pipe).
- `gmst batch` on a missing file, and `gmst -c <missing path> devices` — checked against the
  documented exit-code table.

Deleted the clone (`rm -rf <scratch>/gmst-r7-clone`) after all runs; no code/docs/tests were
modified; no git command other than the one `clone` was run.

## Findings

- [serious] `README.md` "Setup" (`uv sync` / `uv run gmst warmup`) does not prepare the cache that
  "Usage"'s own `gmst bench clip.wav --ref clip.txt` example needs. `warmup` downloads only
  `cfg.model_repo or cfg.model_size` — the one configured model (`cli.py:61-66`) — but `gmst bench`
  always benchmarks a hardcoded 4-candidate list regardless of config (`bench.py:31-35`,
  `FASTER_WHISPER_CANDIDATES = [large-v2, large-v3, large-v3-turbo,
  Yehor/whisper-large-v3-turbo-quantized-uk]`). Following Setup then Usage literally, offline, a
  user hits: `ModelUnavailable: could not load 'Yehor/whisper-large-v3-turbo-quantized-uk': ...
  outgoing traffic has been disabled` for the one candidate `warmup` never touches (verbatim from
  the recorded run). Nothing in README or CLAUDE.md states that `bench` needs 4 separate large-model
  downloads independent of the configured model, or that `warmup` doesn't cover them.
- [serious] `README.md`'s "Exit codes" table (`0 ok, 1 bad input, 2 model/backend could not be
  loaded, 3 device disappeared`) does not hold for `gmst bench`: `cli.py:130-144` (`_cmd_bench`)
  unconditionally `return 0` after printing the table, even when every candidate fails to load.
  Reproduced: with `Yehor/whisper-large-v3-turbo-quantized-uk` uncached and `HF_HUB_OFFLINE=1`, that
  row printed `ModelUnavailable: ...` yet the process's real exit code (checked directly, not via a
  pipe) was `0`. In a from-scratch environment where none of the 4 candidates are cached, `gmst
  bench` would print 4 failure rows and still exit `0` — a caller scripting on `$?` (as the
  documented exit-code table invites) gets a false "ok" for a run that produced zero usable
  numbers. `bench.py`'s own docstring documents catch-and-report-as-a-row for candidate failures,
  but neither it nor the README scopes the Exit-codes promise as bench-exempt.
- [serious] `tests/test_config.py::test_defaults_when_no_file` (line 6) is not isolated from the
  live environment: it asserts `cfg.model_size == "large-v3"` but never calls
  `monkeypatch.delenv("GMST_MODEL", raising=False)`, unlike `test_env_beats_toml` two tests below it
  which explicitly `monkeypatch.setenv("GMST_MODEL", "tiny")`. Reproduced exactly as this node's own
  brief instructs: `HF_HUB_OFFLINE=1 GMST_MODEL=tiny uv run pytest -q` → `FAILED
  tests/test_config.py::test_defaults_when_no_file - AssertionError: assert 'tiny' == 'large-v3'`;
  the same test passes in isolation once `GMST_MODEL` is unset. Any contributor or CI job that
  exports `GMST_MODEL` (e.g. to avoid downloading `large-v3` while iterating, which is exactly what
  this review's own rules ask every agent to do) gets one unrelated red test.
- [minor] A nonexistent `--config` path does not fail cleanly like every other CLI error path.
  `CLAUDE.md`/`PLAN.md` say only "raises", and it does (`config.py`'s `Config.load` raises
  `FileNotFoundError`), but `gmst -c /no/such/path.toml devices` dumps a raw Python traceback to the
  user rather than the one-line messages every other failure path uses (`no such file: ...`,
  `cannot open input: ...`, `ModelUnavailable: ... run \`gmst warmup\``). Exit code happens to be
  `1` (Python's default for an uncaught exception) which matches "bad input" by coincidence, not by
  design — `main()` has no `try/except` around `Config.load`.
- No new findings from `gmst batch --language uk` vs auto-LID beyond what R2 already recorded:
  pinned `uk` gives a plausible-looking (still garbled at `tiny`) transcript with `lang: "uk",
  lid_prob: 1.0`; auto on the same clip mislabels it `lang: "cs", lid_prob: 0.3452` (below
  `lid_threshold` 0.7, and there is no previous utterance to stick to on segment 1 of a batch file)
  — consistent with, not additional to, R2's finding that `resolve_language` never restricts the
  detector to `en`/`uk`.
- `uv sync`, `gmst devices`, `gmst batch` (both language modes), plain `uv run pytest -q`, `uv run
  pytest -m slow -q`, `uv run ruff check .`, and the two CLI exit-code sanity checks (missing input
  file, missing `--config` file) all reproduced clean / as documented — recorded above, not listed
  again as findings.

## Could not check

- Everything Mac-only per rule 6: `mlx_whisper` backend execution, BlackHole routing, Metal timings.
  The one `mlx`-marked slow test skipped for lack of the `mlx` package on Linux, as expected.
- `Yehor/whisper-large-v3-turbo-quantized-uk` could not be loaded (not in the local HF cache,
  offline-only per rule 4) — this absence is itself evidence for the first finding above, not a gap
  in coverage.

FINDING: findings
