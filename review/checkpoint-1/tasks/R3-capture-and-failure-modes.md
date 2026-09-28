id: R3
title: Capture, failure modes and shutdown
parent: -
stage: review
kind: task
agent: code-reviewer
model: sonnet
effort: medium
status: done
depends-on: -

# R3 — Capture, failure modes and shutdown

## Instructions

Walk every row of `PLAN.md` "Failure modes & degradation" and confirm the code implements its policy, citing the `file:line` that does. Files: `src/gmst/audio/{device_source,resample,file_source,types}.py`, `src/gmst/cli.py` (exit codes 0/1/2/3), `src/gmst/sink/{base,console,jsonl,srt,sse}.py`, and the shutdown path in `pipeline/stream.py`. Read first: root `CLAUDE.md`, `PLAN.md`, `review/checkpoint-1/PLAN.md` (rules 1–8), this file. Set `status: in-progress` before starting.

A row with no implementation, or an implementation that differs from the policy, is a finding. Specific checks: the capture callback does only downmix → persistent `soxr.ResampleStream` → enqueue; drop-oldest and the `[lagging]` flag reach the sink; PortAudio status flags are counted, not swallowed; `DeviceLost` after the drain → exit 3; `sink.close()` runs even when the final decode raises; the SSE per-client queue is bounded at 512 with drop-oldest and a heartbeat; the JSONL/SSE event schema matches the pinned one. You may run `gmst devices` / `gmst listen` briefly on this Linux machine; BlackHole is rule 6.

## What was read / measured

- Read in full: `src/gmst/audio/device_source.py`, `src/gmst/audio/resample.py`,
  `src/gmst/audio/types.py`, `src/gmst/audio/file_source.py`, `src/gmst/cli.py`,
  `src/gmst/sink/base.py`, `src/gmst/sink/console.py`, `src/gmst/sink/jsonl.py`,
  `src/gmst/sink/srt.py`, `src/gmst/sink/sse.py`, `src/gmst/pipeline/stream.py`,
  `src/gmst/segment/vad.py` (for VAD backends used by probes).
- Read `PLAN.md` "Failure modes & degradation" table (lines 144–169) row by row against the code
  above, plus the module-layout and JSONL/SSE schema sections, and `CLAUDE.md`'s own copy of the
  failure-mode summary and exit-code table.
- Read `tests/fakes.py`, `tests/test_device_source.py`, `tests/test_cli.py`, `tests/test_sinks.py`,
  `tests/test_sink_base.py`, `tests/test_sse_sink.py` to see which rows are exercised by the suite.
- Ran `pgrep -af python` before every probe; only R1/R2's tiny/small faster-whisper probes were
  running (no `large-*` model). None of R3's probes load any model (pure Python / `FakeEngine`-style
  doubles), so no interference either way.
- Ran `uv run gmst devices` (real ALSA devices present on this Linux box) and
  `uv run gmst stream -d "definitely-not-a-real-device-xyz"` (exit code check, real CLI).
- Wrote and ran 4 probes, all in `review/checkpoint-1/scripts/R3/`:
  - `lagging_probe.py` — static + dynamic check of whether `[lagging]` / `CaptureStats` ever reach
    `run_stream`/a sink.
  - `sink_close_on_raise_probe.py` — engine raises on its first `transcribe()` call mid-loop;
    checks the original exception still propagates *and* `sink.close()` still ran.
  - `devicelost_probe.py` — source drains then raises `DeviceLost`; checks the shutdown flush
    still commits the tail before the exception propagates.
  - `sigterm_probe.py` — reproduces `_cmd_stream`'s exact signal-registration idiom in a child
    process and compares SIGINT vs SIGTERM.
- Positive confirmations (rows implemented as documented, no finding): sink.close() unconditional
  on a mid-loop engine exception, with the original exception still propagating
  (`sink_close_on_raise_probe.py` output below); `DeviceLost` propagates only after the shutdown
  flush commits the tail, `gmst stream` catches it for exit 3 (`devicelost_probe.py`,
  `cli.py:198-200`); JSONL/SSE payload schema (`jsonl.py:26-37`, `sse.py:40-52`) matches
  `PLAN.md:234-237` field for field; SSE per-client queue bounded at 512 with drop-oldest and a
  15 s heartbeat + `retry:` hint (`sse.py:25,82,90-93,116-127`); long-meeting memory bounds
  (`_MAX_COMMITTED = 4000`, `_PROMPT_CHARS = 600`, `stream.py:41-43,109-110`); bounded audio queue
  sized by `max_buffer_seconds / (block_ms/1000)` with drop-oldest (`device_source.py:70-73,150-158`,
  `test_device_source.py::test_bounded_queue_drops_oldest`); resample callback structure (downmix →
  persistent `soxr.ResampleStream` → enqueue, `device_source.py:121-158`).
- Stopped after the module list in the brief; did not additionally audit `bench.py` or `config.py`
  (out of this node's file list).

## Findings

- [blocking] `gmst stream`'s SIGINT handling (`cli.py:169-188`) is the *only* signal trap installed.
  `grep -rn "SIGTERM" src/gmst/` returns nothing. PLAN.md's row is titled **"Ctrl-C / SIGTERM"**
  with policy "stop stream → drain queue → transcribe & flush the uncommitted tail as final → close
  sink" (`PLAN.md:164`), and CLAUDE.md repeats "without it every session loses its last utterance".
  `sigterm_probe.py` reproduces `_cmd_stream`'s exact idiom (register a SIGINT handler that runs
  cleanup; nothing for any other signal) in a child process:
  ```
  signal=SIGINT exit_code=0 stdout_after_signal='CLEANUP-RAN\n'
  signal=SIGTERM exit_code=-15 stdout_after_signal=''
  ```
  SIGTERM kills the process via Python's default disposition — no drain, no flush, no
  `sink.close()`. Any supervisor that stops the process with SIGTERM first (`systemd stop`,
  `docker stop`, plain `kill <pid>` with no `-INT`) loses the uncommitted tail — the exact loss the
  whole flush mechanism exists to prevent, on a signal the row's own title names.

- [serious] The `[lagging]` flag PLAN.md's "Bounded queues" row promises ("on full, drop oldest
  audio and set a `[lagging]` flag **the sink renders**", `PLAN.md:150`) never reaches any sink used
  by `gmst stream`. `DeviceSource.lagging`/`.stats.blocks_dropped` (`device_source.py:150-158,186-187`)
  is read in exactly one place in the whole codebase: `cli.py:118-119`, inside `_cmd_listen` — a
  different subcommand from `stream` that has no sink at all, just a level meter. `run_stream`
  (`pipeline/stream.py`) never reads `source.lagging` or `source.stats`, and `Segment`
  (`transcribe/types.py:29-37`) has no field for it, so no sink (`console.py`, `jsonl.py`, `srt.py`,
  `sse.py`) could render it even if asked. `lagging_probe.py`:
  ```
  run_stream source mentions 'lagging': False
  run_stream source mentions '.stats': False
  source.lagging = True, blocks_dropped = 7
  ...
  'lagging' appears in sink output: False
  ```
  `tests/fakes.py:70`'s `ListSource.lagging = False` is dead scaffolding — nothing in
  `test_stream_pipeline.py` ever asserts on it (`grep -n lagging tests/*.py` finds only the fakes.py
  attribute and `test_device_source.py`'s own unit test of `DeviceSource`, never a stream/CLI test).
  During a real meeting on this Linux path, a user whose queue is dropping audio gets no signal at
  all in `stream`'s console/jsonl/srt/sse output.

- [serious] PLAN.md's "PortAudio `input_overflow` / `underflow`" row says these are "counted,
  logged, never swallowed" (`PLAN.md:151`). They are counted (`device_source.py:125-128`,
  `CaptureStats.status_flags` / `.overflows`) but never logged: `grep -n "log\|Logger" src/gmst/audio/device_source.py` matches nothing, and
  `grep -rn "logging.getLogger" src/gmst/pipeline/stream.py` finds only the one call at
  `stream.py:205`, for the final-flush exception — unrelated. The counters are read in exactly the
  same one place as `lagging` above: `_cmd_listen` (`cli.py:116-117`), never in `_cmd_stream` or
  `run_stream`. A real overflow during `gmst stream` is silently invisible to the operator, contrary
  to "never swallowed".

- [serious] PLAN.md's "BlackHole / loopback not installed" row: "`gmst devices` and `gmst stream`
  print the routing setup doc and exit 2" (`PLAN.md:156`) is entirely unimplemented. `grep -rn
  "BlackHole\|routing" src/gmst/` returns nothing — the string "BlackHole" only exists in
  `README.md`. Live check on this machine:
  ```
  $ uv run gmst stream -d "definitely-not-a-real-device-xyz"
  cannot open input: no input device matching 'definitely-not-a-real-device-xyz'
  exit=1
  ```
  Every device-open failure in `_cmd_stream`/`_cmd_devices` returns exit **1** with a generic
  message (`cli.py:101-105,155-159`), matching CLAUDE.md's own exit-code table ("1: bad input — no
  such file / device") and the existing test `test_cli.py::test_stream_bad_device_returns_1` — but
  contradicting `PLAN.md`'s row, which is a distinct, never-built code path (no routing doc text
  anywhere, no special-case detection of "device exists but is not a loopback").

- [serious] PLAN.md's "Engine falls behind real time" row has two parts: drop-oldest (implemented,
  confirmed above) **and** "if sustained > 10 s, log a warning suggesting a smaller model"
  (`PLAN.md:153`). The second half does not exist: `grep -rn "smaller model\|sustained" src/gmst/`
  matches nothing, and there is no timer anywhere comparing capture rate to decode rate. A model too
  slow for the input will silently keep dropping audio (per the finding above, invisibly) with no
  diagnostic hint at all about *why*.

- [minor] PLAN.md's "All-silence input" row: "VAD emits nothing; sink shows an idle indicator, no
  hallucinated text" (`PLAN.md:158`). The "no hallucinated text" half holds (VAD emitting nothing
  means `run_stream` never calls `decode()`), but no sink has any idle-indicator concept —
  `grep -rn "idle" src/gmst/` matches nothing; `ConsoleSink`/`JsonlSink`/`SrtSink`/`SseSink` only
  ever act on `emit()`, which is never called for silence. A user watching `gmst stream --sink
  console` during a long silent stretch sees nothing at all, with no way to distinguish "working,
  no one is talking" from "hung".

## Could not check

- Nothing in this node's scope requires Apple hardware; audio capture, sinks, exit codes and the
  stream shutdown path are all cross-platform and were exercised directly on this Linux machine
  (real ALSA devices via `gmst devices`, real `gmst stream` invocation for the exit-code check).

FINDING: findings
