id: F.1
title: Shutdown and CLI errors: SIGTERM, second Ctrl-C, --config traceback
parent: F
stage: fix
kind: task
agent: orchestrator
model: sonnet
status: done
depends-on: T1

# F.1 — Shutdown and CLI errors: SIGTERM, second Ctrl-C, --config traceback

## Instructions

- **FIX-01** install the SIGINT handler for SIGTERM too (`cli.py:169-188`); test: SIGTERM to a child running `run_stream` over a `ListSource` flushes and closes the sink (R3 `sigterm_probe.py`).
- **FIX-02** a second Ctrl-C must abandon the final decode (`stream.py:191-195` finally path) and still close the sink; catch `KeyboardInterrupt` in `_cmd_stream` (R1 `probe_second_ctrl_c.py`).
- **FIX-03** `main()` turns a missing `--config` into a one-line error, exit 1.

Protocol: `verify-then-integrate` skill — re-run the finding's probe first, write the regression
test and watch it fail, then fix; `uv run pytest -q` and `uv run ruff check .` green; one commit per
FIX id with an explicit pathspec. Items and evidence: T1's triage table.

## What was read / measured

Read `cli.py:147-215` (`_cmd_stream`), `cli.py:266-269` (`main`), `stream.py:100-209`, R1
`probe_second_ctrl_c.py`, R3 `sigterm_probe.py`. Tests written first and watched fail:
`test_cli.py::test_sigterm_drains_and_flushes_like_ctrl_c` (no SIGTERM handler),
`test_cli.py::test_a_second_interrupt_exits_130_without_a_traceback` (KeyboardInterrupt escaped
`main` and aborted the pytest run), `test_cli.py::test_missing_config_path_is_a_one_line_error`,
`test_stream_pipeline.py::test_a_second_interrupt_abandons_the_final_decode_but_still_closes_the_sink`
(4th decode started after the interrupt). After the fix: `uv run pytest -q` 140 passed, 4
deselected; `uv run ruff check src tests` clean.

## Findings

- **FIX-01** `_cmd_stream` installs one `_on_stop` handler for SIGINT *and* SIGTERM and restores both
  afterwards (`cli.py`).
- **FIX-02** `run_stream` records a `KeyboardInterrupt` out of the loop and skips the final decode in
  `finally`; `sink.close()` still runs (`stream.py`). `_cmd_stream` catches it and exits 130 with a
  one-line message. A third signal still kills outright (`SIG_DFL`), by design.
- **FIX-03** `main()` turns the missing-`--config` `FileNotFoundError` into a one-line error, exit 1.
- Docs: README exit codes (+130, SIGTERM), CLAUDE.md "Failure modes", PLAN.md Ctrl-C/SIGTERM row, the
  `cli.py` module docstring.
- One commit for the three: FIX-01 and FIX-02 share the same handler hunk in `cli.py`.

## Could not check

A real `kill -TERM` against a running `gmst stream` needs an audio device; the test invokes the installed handler directly instead of signalling the pytest process.

FINDING: recorded
