# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`GMST` — real-time speech-to-text for Google Meet. Target use is meetings that **mix English and
Ukrainian**, sometimes within one speaker's turn. Captures the meeting's audio from the local
machine, streams it through an ASR engine, emits a live transcript.

**Supported platform: macOS (Apple Silicon)** — the only config where both the latency and the
Ukrainian-accuracy stories close. Linux/Windows are expected to run via the `faster_whisper`
backend (CI + portable fallback) but are not validated.

Build order is **batch first, then streaming** — see `PLAN.md` for the full phase plan, model
survey, latency budget, failure-mode table, and config reference. Current state: **Phases 1–3 done,
Phase 4 partial.** Every subcommand works. `stream` runs device → endpointer → per-utterance sticky
LID → engine → LocalAgreement-2 → sink, SIGINT-driven drain-and-flush shutdown, verified end-to-end
with real Silero VAD + `tiny` Whisper. Phase 4 shipped: word-level timestamps (`Segment.words`),
turn segmentation on pauses (`segment/turns.py`, `Segment.turn`), and an SSE sink (`sink/sse.py`,
`--sink sse`). Not done: AlignAtt/`Lightning-SimulWhisper` and the `canary` backend (Mac/GPU only),
LLM cleanup pass (deferred). `mlx_whisper` backend is written but untested (needs a Mac); `gmst
bench` model selection and the latency/BlackHole soak are the remaining Mac tasks. **Open Mac
verification item:** `MlxWhisperEngine._load()` now reuses `mlx_whisper`'s own
`ModelHolder.get_model(repo, mx.float16)` cache instead of loading a second float32 copy, and
`gmst bench` releases each candidate (plus `ModelHolder.model` / `mx.clear_cache()`) before loading
the next — neither the helper name nor the memory saving has been confirmed against a pinned
`mlx-whisper` on real hardware.

## Commands

- `uv sync` — create `.venv` and install deps (runtime + dev group)
- `uv run gmst <subcommand>` — CLI (`devices` | `warmup` | `bench` | `batch` | `listen` | `stream`)
- `uv run pytest -q` — test suite (model-downloading tests are `@pytest.mark.slow`, deselected by
  default via `addopts = "-m 'not slow'"`; `uv run pytest -m slow` to include them)
- `uv run pytest tests/test_config.py::test_env_beats_toml` — single test
- `uv run ruff check .` / `uv run ruff format .` — lint / format

Python pin: `.python-version` is 3.12; `requires-python` is `>=3.11,<3.15`.

## Architecture

**The hard parts are audio capture, the English/Ukrainian language mixture, streaming
reconciliation, and failure handling — not raw transcription.** Meet plays to an *output* device
that can't be read directly, so the user routes it through a virtual loopback device (BlackHole on
macOS) and points `gmst` at that input.

Every audio stage speaks one contract, defined in `src/gmst/audio/types.py`:
`AudioArray = npt.NDArray[np.float32]`, mono, `SAMPLE_RATE` (16 kHz), shape `(n_samples,)`,
amplitude `[-1, 1]`. Sources open at the device's native rate and resample/downmix to this
(`audio/resample.py`, `soxr`). **All timestamps derive from a monotonic `samples_consumed` counter
(`samples / SAMPLE_RATE`), never `time.time()`.**

Pipeline: `device_source -> endpointer -> engine.detect_language -> engine -> reconcile -> sink`
(streaming); `file_source -> engine -> sink` (batch). Both pipelines are implemented; every module
in the layout table in `PLAN.md` exists.

### ASR engine is a Protocol

`transcribe/engine.py` defines `Engine`:

```python
def transcribe(self, audio, *, language=None, prompt=None) -> list[Segment]: ...
def detect_language(self, audio) -> tuple[str, float]: ...
```

Backends under `transcribe/backends/`:

- `faster_whisper` — **portable default** (Linux/Windows/CI). CPU `int8` only on Apple Silicon
  (CTranslate2 has no Metal/MPS backend), CUDA where available. Per-segment LID runs GMST's own
  detector pass on a **window around the segment** (widened to ≥ 0.5 s, never the whole file) and
  routes it through `resolve_language`. faster-whisper's in-pass `multilingual=True` is asked for
  **only when `per_segment_lid` is off** — 1.2.1 exposes no per-segment `language` to read back and
  has no uk/ru tie-break, so doing both would pay twice for one answer.
- `mlx_whisper` — **Mac fast path**. Apple GPU. `model_repo` must be an mlx path (e.g.
  `mlx-community/whisper-large-v3-turbo`). No `vad_filter` param. LID via
  `mlx_whisper.decoding.detect_language` (one extra encoder pass — counted in the latency budget).
  Pin the dep; it pulls `torch` and is slow-moving.
- `canary` (NeMo) — optional, Phase 4. Linux/GPU only. **Has no built-in language-ID** (`transcribe()`
  takes an explicit `source_lang`), so it does not remove the LID step; batch/40 s-chunk oriented.

### Model default is provisional

`config.py` ships `model_size="large-v3"` but this is **not** validated — the Ukrainian leaderboard
GMST cites (`egorsmkv/speech-recognition-uk`, CV10 `uk`) puts `large-v2` at 13.72 % WER, `large-v3`
at 20.53 %, `large-v3-turbo` at 22.83 %, and `Yehor/whisper-large-v3-turbo-quantized-uk` at
12.75 %. Phase 1's `gmst bench` measures UK WER + EN WER + streaming throughput over
`{large-v2, large-v3, large-v3-turbo, the quantized fine-tune}` on the target Mac and sets the real
default. Do not treat `large-v3` as decided.

### Language mixture

Whisper emits one language token per 30 s window and does not label language per word. GMST does
**per-utterance language detection** via `Engine.detect_language` on each endpointed segment,
passing the result as `language` to the engine. This yields sentence-level code-switching;
word-level EN↔UK within a sentence is not solved.

- `detect_language` is a **Protocol method**, never a free function (a standalone one would load a
  second model or have no MLX path).
- Below `cfg.lid_threshold` (0.7): keep the previous utterance's language, don't flip.
- `uk`/`ru` within `cfg.lid_tiebreak_margin`: prefer `uk` (a `ru` mislabel on Ukrainian is the
  visible failure).
- `gmst stream --language en|uk` bypasses LID for known-monolingual meetings.
- Never rely on global `language=None` autodetect — it biases to English.

### VAD is pipeline-owned

Batch may pass `vad_filter=True` to faster-whisper for convenience. **Streaming always passes
`vad_filter=False`** and cuts silence in `segment/vad.py`, so silence handling and timestamps are
identical across backends (mlx-whisper has no `vad_filter`). Keep Whisper's `no_speech_threshold`
and temperature fallback on.

### Streaming reconciliation

`reconcile.py` uses **LocalAgreement-2** (`whisper_streaming`, UFAL): commit the longest common
prefix of two consecutive hypotheses, comparing **normalized** word tokens (casefold, strip
trailing punctuation) but emitting original text. Plus: forced commit after
`max_unconfirmed_seconds` **of audio** (or 3 updates without progress) when the tail never agrees;
`initial_prompt` capped at 600 characters (~200 Whisper tokens — 200 *words* of Ukrainian is ~400);
buffer trimmed at committed **word** boundaries on every commit (`Endpointer.trim_to`, 0.2 s
back-off) with `LocalAgreement.rebase` moving the anchor to match. `is_final` is set only here,
never by a backend. The sink is **single-writer** — only the reconcile thread emits — and is not
thread-safe.

Two invariants the seams have to preserve, both easy to break:

- **committed spans are strictly monotonic** (`types.py`). Audio retained across a forced cut
  (`overlap_seconds`) or left by the trim back-off gets transcribed *again*, so the committed words
  inside it must stay as the anchor — otherwise they commit twice with times running backwards.
- **a revised prefix is never re-committed.** When the model changes a word it already emitted as
  final, `_align` returns −1 (`contradicted`) rather than falling back to index 0; `push` emits
  nothing. Mid-stream, `flush` drops the unplaceable tail (the next decode recovers it); on
  shutdown, `absorb` commits the whole tail regardless — there is no next decode, and losing the
  last utterance of a meeting is the failure the shutdown flush exists to prevent.

AlignAtt/SimulStreaming (lower latency) needs decoder attention weights, only works via MLX
(`Lightning-SimulWhisper`), and is **PolyForm Noncommercial** licensed. Phase 4, not the default.

### Latency & throughput

End-to-end target is ≲ 3 s (Phase 3). LocalAgreement-2 re-decodes the whole unconfirmed buffer
every update, so required throughput is `RTF × (buffer_seconds / update_interval)`, **not** RTF —
for a 15 s buffer at 1 update/s the real target is **RTF ≤ ~0.15**. `max_buffer_seconds` caps the
buffer, and the per-commit trim is what keeps the real `buffer_seconds` near one utterance rather
than at that cap — without it the budget cannot close. `PLAN.md` has the full budget decomposition; `gmst bench` reports streaming amplification,
not just batch RTF.

### Failure modes

`PLAN.md` has the full table — every row has a defined policy, none optional. Load-bearing ones:
bounded `audio_queue` (drop-oldest + `[lagging]` flag when the engine falls behind); PortAudio
status flags surfaced not swallowed; device disconnect → `DeviceLost` after the drain → exit 3;
missing/unloadable model → `ModelUnavailable` carrying "run `gmst warmup`" → exit 2; a stalled SSE
viewer → bounded per-client queue, drop-oldest; **Ctrl-C → drain → transcribe & flush the
uncommitted tail as final → close sink** (without it every session loses its last utterance) — and
`sink.close()` is unconditional even when that final decode raises, because `SrtSink` writes its
file only there. A second Ctrl-C abandons the final decode instead of being ignored.

### Threading (Phase 3)

The sounddevice callback downmixes, feeds the session's persistent `soxr.ResampleStream` (filter
state must carry across blocks) and enqueues (bounded queue, drop-oldest on full) — nothing else;
transcription runs on its own thread. Only the reconcile thread writes to the sink.

## Config

`Config` dataclass in `src/gmst/config.py`, **loaded in `main()`** and passed to every subcommand.
Precedence: defaults < `gmst.toml` (flat table) < `GMST_*` env vars (`GMST_ENGINE`, `GMST_MODEL`,
`GMST_MODEL_REPO`, `GMST_COMPUTE_DEVICE`, `GMST_COMPUTE_TYPE`, `GMST_LANGUAGE` where `auto` ⇒
`None`). `_merge` validates key names, enum values, and scalar types for **every** field — enums,
ranged numbers, booleans, strings, `language` (`en`/`uk`/`auto`) and `input_device` — so a bad enum,
a string where a float is expected, `word_timestamps = "yes"` or `language = "ukranian"` all fail at
load, not mid-meeting. A `--config` path that does not exist raises; only the default `gmst.toml`
may be absent. `compute_device` (cpu/cuda) is distinct from the audio `--device`. Full field table in `PLAN.md`; `gmst.example.toml` documents every field; `gmst.toml`
is git-ignored.

## Testing

`tests/fakes.py::FakeEngine` implements the `Engine` protocol with scripted hypotheses, so the
whole stream pipeline is testable with no model and no audio device. Model-downloading tests are
`@pytest.mark.slow` and deselected by default. CI runs the `faster_whisper` path only.

A fixed script is not enough for the seams. Anything about the overlap, the buffer trim, or
timestamp monotonicity needs an engine that reacts to the audio it is *actually* handed —
`test_stream_pipeline.py::_marked` builds audio whose every chunk carries its own amplitude and
`_marked_engine` reads the word back out of it, so re-decoded audio yields the same word the way a
real model would. A script that answers the same thing regardless of the buffer will happily pass
while the seam duplicates text. For the same reason, don't leave `max_unconfirmed_seconds` and
`overlap_seconds` at values that disable the paths under test.
