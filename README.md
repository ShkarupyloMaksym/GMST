# GMST

Real-time speech-to-text for Google Meet via [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper)
(portable) or [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) (Apple
Silicon fast path). Captures the meeting's audio from the local machine, streams it through Whisper,
and prints a live transcript. Target use: meetings that mix **English and Ukrainian**.

See [PLAN.md](PLAN.md) for the pipeline design, phases, latency budget, and failure-mode table.

## Platform support

- **Supported:** macOS (Apple Silicon) — the only config where both latency and Ukrainian accuracy
  close.
- **Expected to run, not validated:** Linux / Windows via the `faster_whisper` backend (the
  portable fallback).

## Setup

```sh
uv sync                 # on Apple Silicon: uv sync --extra mac  (adds the mlx_whisper backend)
uv run gmst devices     # list audio input devices
uv run gmst warmup      # pre-download the configured model (--bench: all of bench's candidates)
```

On Linux, `sounddevice` uses the system PortAudio library, which `uv sync` does not install:
`sudo apt install libportaudio2` (Debian/Ubuntu), `sudo pacman -S portaudio` (Arch),
`sudo dnf install portaudio` (Fedora). Without it `gmst devices` exits 1 with
`cannot load PortAudio`.

## Audio routing

Meet plays to an *output* device, which can't be recorded directly. Route it through a virtual
loopback device and point `gmst` at that (`input_device` in `gmst.toml`, or `--device`):

| OS | Device | Gotchas |
|----|--------|---------|
| macOS | [BlackHole](https://github.com/ExistentialAudio/BlackHole) + a Multi-Output Device | BlackHole is 48 kHz / 2 ch. In the Multi-Output Device the **built-in output must be the top (clock) device**, and **enable Drift Correction on every other device** — otherwise samples are dropped and capture drifts out of sync. `gmst` opens at the native rate and resamples to 16 kHz. |
| Windows | [VB-Audio Virtual Cable](https://vb-audio.com/Cable/), or WASAPI loopback | — |
| Linux | the PulseAudio/PipeWire sink's `.monitor` source | `gmst devices` does **not** list monitor sources by name — through ALSA it only sees `pulse` / `pipewire` / `default`, which record from the *default source*. Point that one process at the monitor instead: `pactl list short sources \| grep monitor`, then `PULSE_SOURCE=<sink>.monitor uv run gmst stream --device pulse`; or start `gmst stream --device pulse` and pick "Monitor of …" for it in `pavucontrol` → Recording. Do **not** `pactl set-default-source` to the monitor: Meet would then use it as its microphone. (Not yet validated end-to-end.) |

## Usage

```sh
uv run gmst batch meeting.m4a -o meeting.srt          # transcribe a recording
uv run gmst stream --language uk                      # live transcript from the input device
uv run gmst stream --sink sse                         # + browse http://127.0.0.1:8765/
uv run gmst bench clip.wav --ref clip.txt             # throughput + streaming cost per model
                                                      # (needs `gmst warmup --bench` first)
```

Exit codes: `0` ok, `1` bad input (no such file/device), `2` the model or backend could not be
loaded (the message names `gmst warmup`), `3` the input device disappeared mid-session, `130` a
second Ctrl-C gave up on `stream`'s final decode. Ctrl-C or SIGTERM (`kill`, `systemctl stop`)
drains, transcribes the tail and closes the sink; a second one gives up on that final decode, and
the sink is still closed with what was committed.

## Status

Phases 1–3 done; Phase 4 partial (word-level timestamps, turn segmentation on pauses, SSE sink).
The 2026-09-28 review (`review/checkpoint-1/`) found and fixed a streaming bug that lost most of
each utterance after its first commit, and restricted language detection to the meeting's
languages (`lid_languages`, default `en`, `uk`); batch now decodes each speech region in its own
language. `model_size` defaults to `large-v3` but this is **provisional** — the Ukrainian/English
WER comparison runs in `eval/run_eval.py` (see CLAUDE.md), and `gmst bench <clip>` measures
throughput and the per-update streaming cost on the target machine. `mlx_whisper` backend is
written but untested (needs Apple hardware); AlignAtt / Canary backends and an LLM cleanup pass
are not implemented.
