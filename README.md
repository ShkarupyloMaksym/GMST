# GMST

Real-time speech-to-text for Google Meet via [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper)
(portable) or [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (Apple
Silicon fast path). Captures the meeting's audio from the local machine, streams it through Whisper,
and prints a live transcript. Target use: meetings that mix **English and Ukrainian**.

See [PLAN.md](PLAN.md) for the pipeline design, phases, latency budget, and failure-mode table.

## Platform support

- **Supported:** macOS (Apple Silicon) — the only config where both latency and Ukrainian accuracy
  close.
- **Expected to run, not validated:** Linux / Windows via the `faster_whisper` backend (CI +
  portable fallback).

## Setup

```sh
uv sync
uv run gmst devices     # list audio input devices
uv run gmst warmup      # pre-download the configured model
```

## Audio routing

Meet plays to an *output* device, which can't be recorded directly. Route it through a virtual
loopback device and point `gmst` at that (`input_device` in `gmst.toml`, or `--device`):

| OS | Device | Gotchas |
|----|--------|---------|
| macOS | [BlackHole](https://github.com/ExistentialAudio/BlackHole) + a Multi-Output Device | BlackHole is 48 kHz / 2 ch. In the Multi-Output Device the **built-in output must be the top (clock) device**, and **enable Drift Correction on every other device** — otherwise samples are dropped and capture drifts out of sync. `gmst` opens at the native rate and resamples to 16 kHz. |
| Windows | [VB-Audio Virtual Cable](https://vb-audio.com/Cable/), or WASAPI loopback | — |
| Linux | the PulseAudio/PipeWire sink `.monitor` source | — |

## Usage

```sh
uv run gmst batch meeting.m4a -o meeting.srt          # transcribe a recording
uv run gmst stream --language uk                      # live transcript from the input device
uv run gmst stream --sink sse                         # + browse http://127.0.0.1:8765/
uv run gmst bench clip.wav --ref clip.txt             # pick the model from WER + throughput
```

Exit codes: `0` ok, `1` bad input (no such file/device), `2` the model or backend could not be
loaded (the message names `gmst warmup`), `3` the input device disappeared mid-session. Ctrl-C
drains, transcribes the tail and closes the sink; a second Ctrl-C gives up on that final decode.

## Status

Phases 1–3 done; Phase 4 partial (word-level timestamps, turn segmentation on pauses, SSE sink).
Every subcommand works, including live `stream`. `model_size` defaults to `large-v3` but this is
**provisional** — run `gmst bench <clip> --ref <transcript>` on the target machine to measure
Ukrainian/English WER and streaming throughput per model and set the real default. `mlx_whisper`
backend is written but untested (needs Apple hardware); AlignAtt / Canary backends and an LLM
cleanup pass are not implemented.
