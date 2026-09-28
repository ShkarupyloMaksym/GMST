id: R6
title: Documents vs code
parent: -
stage: review
kind: task
agent: doc-consistency-auditor
model: sonnet
effort: medium
status: done
depends-on: -

# R6 — Documents vs code

## Instructions

Read `CLAUDE.md`, `PLAN.md`, `README.md` and `gmst.example.toml` as a new session would, and check every factual claim they make about the code: module layout, config fields and defaults (the table in `PLAN.md` "Config" vs `src/gmst/config.py`), env vars, exit codes, phase status, CLI flags (`uv run gmst <cmd> --help`), the test count, and the Commands section. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

Every disagreement is a finding with both locators. Own the onboarding leads on `eval/` being undocumented and the ruff E501. Also list anything a new user would need to run it on Linux (the PulseAudio/PipeWire monitor source) that the README does not say.

## What was read / measured

- Read: root `CLAUDE.md` (full), `PLAN.md` (full), `README.md` (full), `gmst.example.toml` (full),
  `src/gmst/config.py` (full), `src/gmst/cli.py` (full), `src/gmst/bench.py` (full),
  `src/gmst/sink/jsonl.py`, `src/gmst/transcribe/backends/__init__.py`, `src/gmst/reconcile.py:1-5`,
  `eval/build_sets.py:1-30`, `eval/run_eval.py:1-20`, `pyproject.toml`.
- Directory listings: `src/gmst/{audio,transcribe,transcribe/backends,segment,sink,pipeline}/` to
  check every path in `PLAN.md`'s "Module layout" table exists.
- Commands run: `uv run gmst --help`, `uv run gmst stream --help`, `uv run gmst bench --help`,
  `uv run gmst bench --help` , `uv run gmst batch --help`; `uv run pytest -q` (136 passed, 4
  deselected); `uv run pytest -q tests/test_config.py::test_env_beats_toml` (passes, matches
  CLAUDE.md's example); `uv run ruff check src/ eval/ tests/` (1 error: the owned E501 lead);
  `uv run gmst devices` (Linux/ALSA/PipeWire machine); `ldconfig -p | grep portaudio`; checked
  `.venv` for a bundled `libportaudio` and found none; checked for `.github/` (absent).
- Script saved: `review/checkpoint-1/scripts/R6/sse_port_zero.py` — reproduces the `sse_port=0`
  config-load rejection (see finding).
- Stopped: brief items covered (module layout, config table, env vars, exit codes, CLI flags via
  `--help`, test count/example, eval/ onboarding gap, ruff E501, Linux onboarding gaps). Did not
  separately re-derive R1/R3/R4's already-reported items (`trim_to` docstring, PLAN.md failure-mode
  rows, `tests/fixtures/*.wav`) per the orchestrator's note. Bash tool became unavailable
  mid-session (server-side classifier error, persisted across ~6 retries with trivial commands); no
  further shell commands were run after that point — everything below was reached before or without
  it.

## Findings

- [serious] `PLAN.md` and `CLAUDE.md` both assert CI behavior ("CI runs the `faster_whisper` path
  only") but no CI configuration exists anywhere in the repository — `PLAN.md:297` ("CI runs the
  `faster_whisper` path only; MLX cannot run on a Linux runner"), `CLAUDE.md` Commands section
  ("CI runs the `faster_whisper` path only"). Evidence: `.github/` does not exist (`ls -la .github`
  → "No such file or directory"); no `.yml`/`.yaml` workflow file anywhere in the tree outside
  `.venv`. A reader of either doc would reasonably conclude a pipeline exists and is green on every
  push; there is nothing to be green — the claim describes an intent, not an observable fact.

- [serious] `gmst.example.toml:39` documents `sse_port = 0  # ... (0 = any free port)`, but setting
  `sse_port = 0` in `gmst.toml` is rejected at config load, contradicting the doc — only the CLI
  flag `--sse-port 0` (which bypasses `Config._merge`/`_coerce` via a direct `replace`, `cli.py:166`)
  gets the "any free port" behavior the comment describes. Evidence
  (`review/checkpoint-1/scripts/R6/sse_port_zero.py`, run via `uv run python`):
  `_merge(Config(), {"sse_port": 0})` → `FAIL: ValueError sse_port: 0 is out of range (in [1,
  65535])`, because `config.py:85` sets `"sse_port": (int, 1, 65535)` — minimum 1, not 0. A user who
  follows the example file's own comment and puts `sse_port = 0` in `gmst.toml` gets a load-time
  crash instead of "any free port"; the CLAUDE.md/PLAN.md config-validation claim ("a bad enum...
  all fail at load, not mid-meeting") is otherwise true, but here the *documented* value is itself
  invalid.

- [serious] README's Linux row of the audio-routing table ("the PulseAudio/PipeWire sink `.monitor`
  source", Gotchas: "—") implies a Linux user can point `input_device`/`--device` at that source by
  name the same way the macOS row points at "BlackHole", but `gmst devices` does not surface
  per-sink monitor names on a PipeWire/PulseAudio-ALSA machine — it only lists the generic ALSA
  entries `pulse`, `pipewire`, `default`, etc., which route to whichever source is the **system
  default**, not a name a `--device` substring match can pick out. Evidence — actual
  `uv run gmst devices` output on this machine:
  ```
   idx  ch     rate  host / name
  ------------------------------------------------------------
     0   2    44100  ALSA / HDA Intel PCH: ALC257 Analog (hw:0,0)
     9  128    48000  ALSA / sysdefault
    18  128    44100  ALSA / pipewire
    19   32    44100  ALSA / pulse
    24* 128    44100  ALSA / default
  ```
  There is no entry named after any monitor source. Making the Meet-output monitor the thing `gmst`
  actually captures on Linux requires OS-level default-source routing (e.g. `pactl set-default-source
  <sink>.monitor`, or `pactl load-module module-loopback`, or `PULSE_SOURCE=<name>` in the
  environment) — none of which the README or `PLAN.md`'s routing table mentions. `input_device`'s
  doc ("sounddevice id, or name substring", `config.py:36`) is accurate for macOS/BlackHole (a
  uniquely named device) but not operable for the Linux path as documented.

- [minor] README's Setup section (`uv sync` / `uv run gmst devices` / `uv run gmst warmup`) does not
  mention that `sounddevice` on Linux needs the **system** PortAudio library already installed —
  unlike the macOS/Windows PyPI wheels, the Linux wheel does not bundle `libportaudio`. Evidence: no
  `libportaudio*` file anywhere under `.venv/` (`find .venv -iname "*portaudio*"` → empty), while
  `ldconfig -p | grep -i portaudio` resolves it to `/usr/lib/libportaudio.so.2`, a system package on
  this machine (pre-installed, not part of the repo/venv). `cli.py:34-39` does handle the missing
  case cleanly (`except OSError: print("cannot load PortAudio: ...")`, exit 1), so it is not silent
  — but nothing in README/CLAUDE.md tells a fresh Linux user to `apt install libportaudio2` /
  `pacman -S portaudio` / equivalent before `uv sync` will give a working `sounddevice`.

- [minor] Owned lead confirmed: `eval/` is undocumented outside two lines of `CLAUDE.md`.
  `PLAN.md`'s "Module layout" table, "Testing" section and "Phases" table — the three places a
  reader would expect to find every part of the repo — never mention `eval/` at all; `README.md`
  never mentions it either. `CLAUDE.md`'s two lines ("`eval/` (`build_sets.py`, `run_eval.py`) is
  the WER/LID harness against raw faster-whisper; its data and results live in the git-ignored
  `eval/results/`") name the files but not how to run them, or that they need extra dependencies
  beyond `uv sync` — both scripts' own module docstrings specify `uv run --with soundfile --with
  soxr python eval/build_sets.py` and `uv run --with jiwer python eval/run_eval.py`
  (`eval/build_sets.py:15`, `eval/run_eval.py:16-17`), none of which appear in CLAUDE.md's
  "Commands" section alongside `uv sync`/`uv run gmst`/`uv run pytest`/`uv run ruff`. R5/R6 lead;
  see also R5's report for the harness's methodological problems once it *is* found and run.

- [minor] Owned lead confirmed: `uv run ruff check src/ eval/ tests/` reports exactly one error,
  matching the lead — `E501 Line too long (101 > 100)` at `eval/run_eval.py:6:101`
  (`gmst-batch       FasterWhisperEngine(large-v3, per_segment_lid=True) — per-utterance LID +
  tiebreak`). `CLAUDE.md`'s Commands section lists `uv run ruff check .` as clean/expected to pass
  without noting this pre-existing violation; a contributor running the documented command on a
  clean checkout sees one unexplained failure.

- [minor] `PLAN.md`'s "Module layout" table (line ~192) lists
  `transcribe/backends/canary.py        # optional, Phase 4` as if it were a file in the tree
  alongside the other listed backend files, but the file does not exist —
  `src/gmst/transcribe/backends/` contains only `__init__.py`, `faster_whisper.py`,
  `mlx_whisper.py`. The `canary` engine choice is handled entirely inline in
  `backends/__init__.py:30-31` (`elif cfg.engine == "canary": raise NotImplementedError("canary
  backend is Phase 4")`), which is a clean, correct behavior — but unlike the "Phases" table (which
  marks canary with 🔲), the layout table gives no visual cue that this line names a file that was
  never created, so a reader diffing the layout against the tree would flag a phantom discrepancy
  every time.

## Could not check

- Nothing platform-gated came up in this brief's scope (no mlx/BlackHole claims to verify) — the
  Linux-onboarding items above were checked directly on this machine instead.
- The Bash tool returned a persistent server-side classifier error for the remainder of the session
  (six consecutive attempts, including a bare `echo`, all failed identically). No `git`, ruff
  `--fix`, or further shell probes were possible after that point; everything reported above was
  either already captured beforehand or read via the `Read` tool. Nothing in the brief was left
  unaddressed because of this, but a `ruff format --check` pass and a repeat `pytest -q` after this
  point were not taken.

FINDING: findings
