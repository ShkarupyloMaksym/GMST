# GMST — pipeline plan

Real-time speech-to-text for Google Meet. Primary use: meetings that mix **English and Ukrainian**,
sometimes within one speaker's turn. Primary dev machine: Apple Silicon MacBook. Build **batch
first**, then streaming — they share the core (audio→float32, engine wrapper, sinks, config);
streaming adds live capture, endpointing, and result reconciliation.

> Reviewed 2026-08-28 (Opus 5). This revision folds in all 15 findings; see git history for the
> annotated version.

## Consensus streaming architecture

Every serious real-time Whisper pipeline is the same shape:

```
audio -> VAD -> rolling buffer -> commit policy -> ASR engine -> reconcile -> sink
```

They differ only in the **commit policy**:

| Policy | Origin | Idea | Cost |
|---|---|---|---|
| **LocalAgreement-2** | UFAL `whisper_streaming` (2023) | Commit the longest common prefix of two successive hypotheses | Trivial; works with any backend incl. faster-whisper |
| **AlignAtt / SimulStreaming** | UFAL `SimulStreaming` (2025) | Use decoder cross-attention; stop decoding when attention nears the buffer edge | Lower latency + better quality, but needs attention weights → **not** faster-whisper / CTranslate2; works with openai-whisper, MLX (`Lightning-SimulWhisper`) |

GMST uses **LocalAgreement-2** for the portable path (Phase 3). AlignAtt via `Lightning-SimulWhisper`
is a Phase 4 latency upgrade on Mac — note it is **PolyForm Noncommercial** dual-licensed upstream
(free for personal use, forecloses commercial use), so decide before building on it.

Turnkey reference to benchmark against: **`QuentinFuxa/WhisperLiveKit`** (maintained successor to
`whisper_streaming`) — both policies, VAD gating, diarization, server + web UI, backends for
faster-whisper / mlx-whisper / Voxtral / Qwen3-ASR / Canary.

## Models & languages — the hard part

Whisper emits **one language token per 30 s window** and does not label language per word.
`language=None` autodetects but biases to English and won't switch cleanly mid-stream. Approach,
cheapest first:

1. **Per-utterance language detection** (GMST's default): detect language on each endpointed
   segment, pass the result as `language` to that transcription call. This gives *sentence-level*
   code-switching — good enough for meeting notes; word-level EN↔UK within a sentence is unsolved
   off-the-shelf. Implementation and cost: see "Language ID" below.
2. **Better multilingual acoustic model** (does **not** remove the LID step):
   - **NVIDIA Canary-1b-v2** — 25 European langs incl. `uk` / `en` / `ru`. Has **no built-in
     language-ID**; `transcribe()` takes an explicit `source_lang`, so you still need an external
     LID (e.g. NeMo AmberNet). Long-form path is 40 s dynamic chunking with 1 s overlap — a batch
     design, not streaming. NeMo is CUDA/Linux-oriented (`triton` is Linux-only). Phase 4, optional.
   - **Voxtral Mini** (Mistral) — multilingual, does per-chunk LID across 100+ languages, has a
     realtime variant. Middle ground; vLLM / transformers.
3. **Ukrainian-only SOTA** (`egorsmkv/speech-recognition-uk` leaderboard, Common Voice 10 `uk`
   test): FastConformer-P&C 4.0 / 4.52, Citrinet-1024 4.32, wav2vec2-bert 6.6 WER. Monolingual
   only — useful solely as a per-language route, which defeats the point for a mixed call.

### Model choice is provisional until measured

The same leaderboard puts **Whisper `large-v2` at 13.72 % WER, `large-v3` at 20.53 %,
`large-v3-turbo` at 22.83 %** on Ukrainian read speech — i.e. `v3` and `turbo` regress badly on
`uk`, and a community fine-tune (`Yehor/whisper-large-v3-turbo-quantized-uk`) hits 12.75 %. So the
scaffold default (`large-v3`) and the obvious Mac fast path (`turbo`) are the *worst* large-family
choices for the primary target language.

`config.py` therefore ships `model_repo` unset and treats `model_size` as **provisional**. Phase 1
picks the default from data (see benchmark below). Caveat: CV10 is read speech, so treat these
numbers as a strong prior, not a verdict — but a prior pointing opposite to the default is reason
enough not to ship it.

Candidate set for the Phase 1 benchmark: `large-v2`, `large-v3`, `large-v3-turbo`,
`Yehor/whisper-large-v3-turbo-quantized-uk`.

## Language ID

`detect_language` is an **`Engine` protocol method**, not a free function — a standalone
`detect_language(np.ndarray)` would either load a second large model (double unified memory on the
Mac) or have no MLX implementation (mlx-whisper exposes LID only as
`mlx_whisper.decoding.detect_language(model, mel)`, which needs an already-loaded model).

- `faster_whisper` backend: ~~use the in-pass detector — `transcribe(..., multilingual=True,
  language_detection_threshold=cfg.lid_threshold, language_detection_segments=1)` does per-segment
  LID inside the single decode pass. Cheaper than a separate encoder pass.~~ *(Corrected
  2026-09-28, review R2 F8: the code never did this. `detect_language` runs `WhisperModel.
  detect_language` — one **separate** encoder pass per utterance (stream) or per VAD region
  (batch) — because faster-whisper 1.2.1's in-pass LID has no uk/ru handling and exposes no
  per-segment language to read back. It is in the latency budget below for both backends.)*
- `mlx_whisper` backend: `decoding.detect_language` on the loaded model + mel; counts as one extra
  encoder pass — include it in the latency budget.
- **Restricted to `lid_languages`** (default `["en", "uk"]`, DECIDE-02, 2026-09-28): probabilities
  are summed per allowed language, `ru` folded into `uk` unless `ru` is itself listed; the best
  allowed language wins, the first utterance included. (Before: any label passed through — R2.)
- **Below `lid_threshold`** (on that folded mass): keep the previous utterance's language (sticky),
  do not flip.
- **`uk` vs `ru` tie-break**: when both are allowed, the top-2 are `{uk, ru}` and within
  `lid_tiebreak_margin`, prefer `uk` (a `ru` mislabel on Ukrainian speech is the failure the user
  will actually see). With the default `lid_languages` the fold replaces it.
- `stream --language en|uk` bypasses LID entirely for known-monolingual meetings.

## ASR engine

`faster-whisper` is **CPU `int8` only** on Apple Silicon (CTranslate2 has no Metal/MPS backend;
faster-whisper #515). On Mac the fast path is **MLX Whisper** (Apple GPU) — *unverified* that plain
`large-v3` runs real-time on an M2 (published ~1× figures are `turbo`, batch decode of a whole
file), so Phase 1 must measure it on the target machine before the streaming phase depends on it.

`transcribe/engine.py` is a `Protocol`:

```python
class Engine(Protocol):
    def transcribe(self, audio: AudioArray, *, language: str | None = None,
                   prompt: str | None = None) -> list[Segment]: ...
    def detect_language(self, audio: AudioArray, *,
                        prev_lang: str | None = None) -> tuple[str, float]: ...
```

| Backend | Use | Notes |
|---|---|---|
| `faster_whisper` | portable default (Linux/Windows), CPU `int8` or CUDA | LID = one separate `detect_language` encoder pass per utterance / region; `vad_filter` available but pipeline-owned (see VAD) |
| `mlx_whisper` | Mac fast path | Apple GPU; `path_or_hf_repo` e.g. `mlx-community/whisper-large-v3-turbo`; no `vad_filter` param; last release 2025-08-29 and pulls `torch` — pin it, fall back to `whisper.cpp` + Core ML if it goes stale |
| `canary` (NeMo) | optional, Phase 4 | Linux/GPU only; needs external LID; batch/40 s-chunk |

### VAD is pipeline-owned

- **Batch**: `file_source` may pass `vad_filter=True` to faster-whisper for convenience.
- **Streaming**: every engine call passes `vad_filter=False`; silence is cut by `segment/vad.py`
  (Silero via `faster-whisper`'s bundled model, or `webrtcvad`). This keeps silence handling and
  timestamp semantics identical across backends (mlx-whisper has no `vad_filter` at all).
- Keep Whisper's own `no_speech_threshold` and temperature fallback **on** — they are the
  documented mitigation for silence hallucination and decode loops.

## Latency budget (Phase 3 target: end-to-end ≲ 3 s)

3 s is the *achieved* number for a tuned Whisper-Streaming system (arXiv:2307.14743), not slack.
Decomposition, worst-case per committed word:

| Stage | Budget |
|---|---|
| capture block | `block_ms` = 100 ms |
| endpoint trailing silence | `min_silence_ms` = 600 ms |
| VAD over the buffer, once per decode (`endpointer.assess`) | Silero: ~10 ms/s of buffer |
| LID pass, on every decode until the utterance has `lid_settle_seconds` = 3 s (≈ 1–3 passes; both backends; R2 F8, DECIDE-04) | mlx ~150 ms (unmeasured); faster-whisper CPU: R5 measured 0.42 s median for `tiny` on 3 s — large models are X.4 |
| decode of the unconfirmed buffer | RTF × `buffer_seconds` |
| agreement lag (≥ 1 extra update by construction) | `update_interval` |
| **sum** | **≤ 3000 ms** |

LocalAgreement-2 re-decodes the whole unconfirmed buffer every update, so required throughput is
`RTF × (buffer_seconds / update_interval)`, **not** RTF. *(2026-09-28, review R5: measured, that
formula undercounts short buffers 4–6× — Whisper pads every call to a 30 s window, so each update
has a large fixed cost — and omits the per-utterance LID pass. `gmst bench` now reports the
measured seconds per update instead (F.3); this section is rewritten with X.4's large-model
numbers.)* For a 15 s buffer at 1 update/s that is
15 × RTF, so the real target is **RTF ≤ ~0.15**, not 0.5. `max_buffer_seconds` (default 15) caps
the buffer; it is trimmed on every commit to just before the last committed **word**
(`Endpointer.trim_to` gets its start, minus a 0.2 s back-off, so that word survives whole as the
anchor — DECIDE-01). The trim is what
keeps `buffer_seconds` near one utterance instead of the 15 s cap — without it every 1 s update
re-decodes the full cap and the budget above cannot close. Trimming committed audio out of the
buffer also means the reconciler's anchor has to move with it: `LocalAgreement.rebase` keeps
exactly the committed words whose audio survived the cut.

## Failure modes & degradation

Every row has a defined policy; none of this is optional.

| Condition | Policy |
|---|---|
| Bounded queues | `audio_queue` sized in blocks (`max_buffer_seconds / (block_ms/1000)`); on full, **drop oldest audio** and set a `[lagging]` flag the sink renders |
| PortAudio `input_overflow` / `underflow` | every status flag is counted (`CaptureStats.status_flags`, `overflows`); `gmst stream` reports new overflows as an `overflow` status event + log warning (≤ 1 per 5 s; until F.13 only `gmst listen` showed them — R3). The counters are read-modify-written from the PortAudio thread: they are diagnostics, so a lost count is accepted rather than paying for a lock in a realtime callback |
| Resampling in the capture callback | the callback downmixes and feeds one persistent `soxr.ResampleStream` (filter state carries across blocks — a one-shot `soxr.resample` per 100 ms block restarts the polyphase filter, ~−57 dB), then enqueues. Measured at ~0.1 % of the callback budget; everything else stays off this thread |
| Engine falls behind real time | drop-oldest (above) keeps latency bounded; a `lagging` status event (≤ 1 per 5 s of audio) and, if dropping lasts > 10 s, one `slow` event suggesting a smaller model — both also logged. Until F.13 (2026-09-28) neither reached `gmst stream` (R3) |
| Input device disconnects mid-call | `finished_callback` → `DeviceSource.blocks()` drains what was captured, then raises `DeviceLost`; the shutdown flush still runs, `gmst stream` logs and **exits 3** (auto-reconnect is a later feature) |
| Device refuses 16 kHz | open at the device's native rate, resample in `resample.py` (never rely on PortAudio silent conversion) |
| BlackHole / loopback not installed | ~~`gmst devices` and `gmst stream` print the routing setup doc and exit 2~~ *(amended 2026-09-28, review R3/FIX-25a: never built, and a missing loopback cannot be told from any other missing device.)* A device that does not open exits **1** (bad input, as CLAUDE.md, README and `test_stream_bad_device_returns_1` say) with a one-line pointer to README "Audio routing" |
| Model not cached | `load_engine` wraps the load; `ModelUnavailable` carries "run `gmst warmup`" and every CLI handler **exits 2** (an unimplemented backend the same way) |
| All-silence input | VAD emits nothing, so no hallucinated text; after 10 s of no speech one `idle` status event ("still listening") — DECIDE-05, implemented 2026-09-28 (F.13) |
| Never-agreeing tail (stutter/disfluency) | force a commit after `max_unconfirmed_seconds` (default 8) **of audio** or `_MAX_STALLED_PUSHES` = 3 updates without progress — both conditions only while something is actually pending |
| Model revises text it already committed | With word times (the stream always has them) the revised words lie over committed audio and are dropped by time (DECIDE-01). Text-only: `LocalAgreement._align` returns −1 (contradiction) instead of falling back to index 0; `push` commits nothing and flags `contradicted`. **Mid-stream**, `flush` drops the unplaceable tail — duplicating a final utterance is worse than losing one the next decode will recover. **On shutdown** there is no next decode, so `absorb` commits the whole tail anyway (a small seam artifact beats losing the last words of the meeting) |
| Engine raises mid-meeting | `run_stream`'s shutdown flush is nested so `sink.close()` is unconditional — `SrtSink` only writes its file there, and one engine failure must not cost the whole transcript. The original exception still propagates |
| SSE viewer stops reading | per-client queue bounded at 512 events, **drop oldest** (`SseSink.dropped` counts); a `retry:` hint and a 15 s heartbeat comment keep proxies from dropping idle connections |
| Long meeting (2 h+) | memory bound = bounded queues + buffer trim + bounded SSE client queues + the committed word list capped at 4000 + `initial_prompt` capped at 560 characters (≤ 223 Whisper tokens in Ukrainian at ~0.39 tokens/char; 600 was 235 — R1, F.6) |
| Ctrl-C / SIGTERM | stop stream → drain queue → transcribe & **flush the uncommitted tail as final** → close sink. A second Ctrl-C/SIGTERM skips the final decode, still closes the sink, exit 130 (both signals handled since the 2026-09-28 review, FIX-01/02) |

Clock: all timestamps derive from a monotonic `samples_consumed` counter (`samples / SAMPLE_RATE`),
never `time.time()` — **including the forced-commit stall timer**, which compares
`ep.t0_seconds + ep.buffer_seconds` against the last commit, so a source that does not run at 1×
real time behaves identically.

## Module layout

```
src/gmst/
  cli.py              # subcommands: devices | warmup | bench | batch | listen | stream
  config.py           # loaded in main(); see Config below

  audio/
    types.py          # SAMPLE_RATE=16000, mono, npt.NDArray[float32] — the contract every stage speaks
    file_source.py    # decode via PyAV -> 16k mono f32 (soundfile fallback for wav/flac)   [batch]
    device_source.py  # sounddevice InputStream (native rate) -> bounded queue of blocks    [stream]
    resample.py       # soxr: native rate -> 16k, downmix to mono                           [shared]

  transcribe/
    engine.py         # Engine Protocol: transcribe(...) -> [Segment]; detect_language(...) -> (lang, prob)
    types.py          # Segment(start, end, text, language, is_final) + timestamp contract
    lid.py            # resolve_language(): uk/ru tie-break + sticky-threshold, shared by backends & stream
    backends/
      __init__.py      # load_engine(cfg) factory — lazy import of the chosen backend only
      faster_whisper.py
      mlx_whisper.py
      (canary.py)      # optional, Phase 4 — not created; load_engine raises NotImplementedError

  segment/
    vad.py            # speech_regions(): Silero (faster-whisper bundle) or energy RMS gate  [stream]
    endpointer.py     # growing buffer; assess() -> endpoint / forced cut; reset() w/ overlap [stream]
    turns.py          # TurnTracker: bump Segment.turn on a pause > turn_gap_seconds          [stream]

  reconcile.py        # LocalAgreement-2 (prefix realignment) + flush(); see edge cases below [stream]

  sink/
    base.py           # Sink protocol + make_sink(cfg, out_path, override=)
    console.py        # committed lines + one rewritable partial line + turn breaks
    jsonl.py          # append-only; schema pinned below
    srt.py            # SRT / VTT                                    [batch mostly]
    sse.py            # Server-Sent Events over stdlib http.server; /events + viewer page

  pipeline/
    batch.py          # file_source -> [VAD regions -> detect_language] -> engine -> sink (DECIDE-03)
    stream.py         # device_source -> endpointer -> engine.detect_language -> engine -> reconcile -> sink

  bench.py            # `gmst bench`: throughput + measured per-update cost per candidate
  metrics.py          # the shared normalizer; word/char error counts (corpus WER)

eval/                 # not part of the package; data + results in git-ignored eval/results/
  build_sets.py       # uk (cleaned CV10), en (LibriSpeech test-clean), mixed (inter / nopause)
  run_eval.py         # GMST vs raw faster-whisper: corpus WER + CIs, LID / switch metrics, --compare
```

### `Segment` timestamp contract (`transcribe/types.py`)

- `start` / `end` are **buffer-relative seconds (float)** as returned by the engine.
- The pipeline owns the monotonic `samples_consumed` counter and converts to absolute session time.
- `is_final` is set **only** by `reconcile`, never by a backend.
- Once a span is emitted as final its times never move; committed spans are strictly monotonic.
- Naming rule: integer millisecond fields end `_ms`, float second fields end `_seconds`.

### `reconcile.py` edge cases (each has a test)

| Case | Policy |
|---|---|
| Longest common prefix | compare **normalized** word tokens (casefold, strip trailing punctuation); emit original text |
| Tail never agrees | forced commit after `max_unconfirmed_seconds` or N stalled updates |
| `initial_prompt` overlap with the buffer | ~~prompt only with committed words whose audio was trimmed out (F.14)~~ — superseded 2026-09-28 (F.15): excluding the anchor made Ukrainian decodes unstable (X.1b.1). The prompt keeps the anchor; Whisper then skips it and may stretch the next new word over its audio, so the time cut drops only words that resemble a recent committed word |
| Re-emitted phrase longer than the surviving anchor | text and n-gram checks compare against the last 5 committed words (a text-only history that survives `rebase`), not just the anchor (X.1b.1: "to tell himself" committed twice) |
| `initial_prompt` growth | cap to the last 560 characters (glossary terms first, then committed text) — inside faster-whisper's 223-token prompt window for Ukrainian |
| Buffer trim mid-word | trim just before the last committed word (its start minus `_TRIM_BACKOFF_S` = 0.2 s), so it survives whole; `rebase` keeps the words whose audio survived, with their times, so they are not committed twice |
| Re-heard anchor spelled differently / dropped | align by text, then by time: drop hypothesis words ending within the committed audio (`_TIME_TOLERANCE_S` = 0.02 s), then de-duplicate a ≤ 5-word repeat of the committed tail (DECIDE-01; R1 showed text-only alignment losing ~85 % of a real stream) |
| Forced cut with `overlap_seconds` retained | the retained audio is decoded again — keep the committed words inside the overlap as the anchor, or those words commit a second time with timestamps that run backwards |
| partial→final race | single-writer sink — only the reconcile thread writes; the sink is not thread-safe and does not pretend to be |

### JSONL / SSE event schema (pinned)

One object per line (JSONL) or per `data:` event (SSE): `{"t0": float, "t1": float, "text": str,
"lang": str, "final": bool, "turn": int, "lid_prob": float}`, plus `"words": [[str, float, float],
…]` when the engine produced per-word timings. Partials carry `"final": false`; a later line/event
for an overlapping span supersedes them.

Runtime status objects share the stream (DECIDE-05, 2026-09-28) and are told apart by their
`"status"` key: `{"status": "lagging" | "overflow" | "slow" | "idle", "t": float, "message": str}`
plus `"dropped"` / `"overflows"` counts where relevant. `t` is audio seconds on the sample clock.
A consumer that only wants transcript lines skips objects with a `status` key.

## Config (`src/gmst/config.py`)

Loaded in `main()` and passed to every subcommand. Precedence: defaults < `gmst.toml` (flat table)
< `GMST_*` env vars. `_merge` validates **key names, enum values, and scalar types** for *every*
field — enums, numbers with ranges, booleans, strings, `language` (`en`/`uk`/`auto`), and
`input_device` — so a bad enum, `"5"` where a float is expected, `word_timestamps = "yes"`, or
`language = "ukranian"` all fail at load rather than on the first decode of the meeting. A
`--config` path that does not exist raises; only the *default* `gmst.toml` may be absent.

| Field | Default | Notes |
|---|---|---|
| `engine` | `faster_whisper` | enum: `faster_whisper` \| `mlx_whisper` \| `canary` |
| `model_size` | `large-v3` | **provisional** — Phase 1 sets the real default |
| `model_repo` | `None` | explicit HF repo / mlx path; overrides `model_size` when set |
| `compute_device` | `cpu` | renamed from `device` (collided with the audio `--device`); `cpu` \| `cuda` \| `auto` |
| `compute_type` | `int8` | enum |
| `word_timestamps` | `true` | per-word timing; accurate spans + turn detection (`bench` forces off) |
| `language` | `None` | `None` / `"auto"` ⇒ per-utterance LID; `"en"` / `"uk"` pins it |
| `lid_threshold` | `0.7` | below this, keep previous language |
| `lid_tiebreak_margin` | `0.15` | `uk`/`ru` tie-break window |
| `lid_languages` | `["en", "uk"]` | LID picks only among these; `ru` folds into `uk` unless listed (DECIDE-02) |
| `glossary` | `[]` | terms fed to every decode as prompt head + faster-whisper `hotwords` (DECIDE-08) |
| `glossary_autogrow` | `false` | add Latin-script terms committed inside Ukrainian text |
| `glossary_path` | `None` | file the grown list is loaded from and saved to |
| `glossary_max_terms` | `100` | most recent kept |
| `lid_settle_seconds` | `3.0` | stream re-detects until the utterance has this much audio and commits nothing before (DECIDE-04; `0` = detect once) |
| `input_device` | `None` | sounddevice id or name substring |
| `block_ms` | `100` | capture block |
| `min_silence_ms` | `600` | endpointer trailing-silence cut |
| `min_chunk_seconds` | `1.0` | min audio before a decode (was `chunk_seconds`) |
| `max_buffer_seconds` | `15.0` | unconfirmed-buffer cap + trim target (replaces `overlap_seconds`) |
| `max_unconfirmed_seconds` | `8.0` | forced-commit timeout |
| `vad_backend` | `silero` | enum: `silero` \| `energy` (no model load) |
| `vad_threshold` | `0.5` | silero speech probability; energy: fraction of full scale |
| `overlap_seconds` | `0.5` | audio kept after a forced cut, to bridge the seam |
| `sink` | `console` | enum: `console` \| `jsonl` \| `srt` \| `sse` |
| `out_path` | `None` | — |
| `sse_port` | `8765` | `sink = "sse"` → `http://127.0.0.1:<port>/` |
| `turn_gap_seconds` | `1.5` | pause longer than this bumps `Segment.turn` (`0` = off) |

Env: `GMST_ENGINE`, `GMST_MODEL`, `GMST_MODEL_REPO`, `GMST_COMPUTE_DEVICE`, `GMST_COMPUTE_TYPE`,
`GMST_LANGUAGE` (`auto` ⇒ `None`), `GMST_LID_LANGUAGES` (comma-separated).

## Review decisions (checkpoint-1 review, 2026-09-28)

Recorded from `review/checkpoint-1/tasks/H1-decisions.md`; the findings behind them are in
`review/checkpoint-1/tasks/T1-triage.md`.

- **DECIDE-01 — re-anchoring after a trim.** The per-commit trim cuts *before* the last committed
  word (its start minus the back-off), not 0.2 s before its end; and reconciliation anchors by word
  timestamps as UFAL's `whisper_streaming` does — hypothesis words that end before the last
  committed word's end are dropped, and an up-to-5-word n-gram overlap with the committed tail is
  de-duplicated — so a re-heard or revised word is no longer a terminal contradiction for the
  utterance. Still LocalAgreement-2.
- **DECIDE-02 — `lid_languages`.** New config field, default `["en", "uk"]`. The detector's
  distribution is renormalised over it, with `ru` folded into `uk`; this applies to the first
  utterance too. `language = en|uk` pinning is unchanged.
- **DECIDE-03 — batch per-segment LID.** Batch VAD-splits the file, detects each region's language
  (restricted as above) and decodes each region in that language — the same semantics as streaming.
- **DECIDE-04 — stream LID timing.** Re-detect on each decode while the utterance holds < 3 s of
  audio; fix its language at 3 s and hold commits until then (X.2: restricted LID ≥ 95 % at 3 s on
  small and large-v2, 88–90 % on Ukrainian at 2 s). The meetings are *Ukrainian with English
  terms* (user, 2026-09-28), so the point is that an utterance opening with an English term is not
  committed as English.
- **DECIDE-06 — evaluation audio.** No private recording for now; find public Ukrainian speech with
  English terms / uk–en code-switching whose transcripts keep the terms in Latin script (X.5).
- **DECIDE-05 — runtime status.** `lagging`, `overflow`, `slow` (> 10 s of dropping: try a smaller
  model) and `idle` (10 s without speech) go to stderr as log warnings, to the console as a status
  line, and into the JSONL/SSE stream as `{"status": ...}` objects (schema addition approved).
- **DECIDE-07 — CI.** There is none and no remote; the claims are struck.
- **DECIDE-08 — auto-growing glossary.** A config-enabled term list passed to Whisper (prompt and
  faster-whisper `hotwords`) on every decode, growing with English terms seen in the session; off
  for speed. Targets term fidelity inside Ukrainian decoding, which per-utterance LID cannot fix.

## Phases

| Phase | Build | Milestone / exit criterion |
|---|---|---|
| **0. Scaffold** ✅ | `pyproject.toml`/uv/ruff/pytest, `config.py`, `audio/types.py`, `transcribe/{engine,types}.py`, `cli.py`, `gmst devices` | `uv run gmst devices` lists the BlackHole device |
| **1. Batch + benchmark** 🟡 | ✅ `file_source` (PyAV), `faster_whisper` backend + per-segment LID (`resolve_language`), `sink/{console,jsonl,srt}`, `pipeline/batch.py`, `gmst batch` / `warmup` / `bench`, `metrics.word_error_rate`. 🔲 `mlx_whisper` backend (written, untested — needs a Mac). 🔲 run `gmst bench` on a real 5–10 min hand-transcribed bilingual clip on the target Mac. | `gmst bench` emits a table: (backend × model) → batch RTF, **streaming amplification**, **UK WER**, **EN WER**. That table sets `model_size` / `engine` / `model_repo` defaults. *(Amended 2026-09-28, review F.3: one clip cannot separate the candidates — R5 puts it at hundreds to thousands of clips — so UK / EN corpus WER with CIs come from `eval/run_eval.py` on the full cleaned-CV10 set (X.3); `gmst bench` supplies throughput and the measured per-update cost on the target Mac, and a sanity WER on the user's own clip.)* |
| **2. Live capture** ✅ | `device_source.py` (native rate, bounded drop-oldest queue, overflow counter, monotonic sample clock, drain-on-close), `resample.py` (soxr), `gmst listen` level meter. Mechanism verified on the default input; BlackHole + 10-min overflow check is a Mac task. | Meter moves via BlackHole; overflow count stays 0 over 10 min |
| **3. Streaming** ✅ | `segment/vad.py` (Silero + energy), `segment/endpointer.py` (growing buffer, endpoint on trailing silence, forced cut, overlap on reset), `reconcile.py` (LocalAgreement-2 with prefix realignment + `flush()`), per-utterance sticky LID, `pipeline/stream.py`, `gmst stream --language`, **graceful-shutdown flush** (SIGINT → `source.close()` → drain → final decode). Verified end-to-end with real Silero + `tiny` Whisper (clean ordered transcript, RTF ~0.43). Latency ≲ 3 s measurement + BlackHole soak are Mac tasks. | Live bilingual transcript, measured end-to-end latency ≲ 3 s; Ctrl-C loses no committed or final-flushable text |
| **4. Upgrades** 🟡 | ✅ word-level timestamps (`Segment.words`, faster-whisper/mlx, `word_timestamps` config; streaming spans + SRT/jsonl use them). ✅ turn segmentation on pauses (`segment/turns.py`, `turn_gap_seconds`, `Segment.turn`; console break + jsonl/SSE field). ✅ SSE sink (`sink/sse.py`, stdlib http.server, `--sink sse`, `/events` + viewer page). 🔲 AlignAtt via `Lightning-SimulWhisper` (Mac/MLX, PolyForm Noncommercial). 🔲 `canary` backend + external AmberNet LID (Linux/GPU). 🔲 LLM cleanup pass (deferred — adds `anthropic` dep + key). | lower latency / better mixed-language accuracy |

## Testing

- **`FakeEngine`** (`tests/fakes.py`) implements the `Engine` protocol and returns a scripted list
  of hypotheses per call → the whole stream pipeline (endpointer → LID → reconcile → sink) is
  testable deterministically with no model and no audio device.
- `reconcile.py` — every edge-case row above is a test.
- `endpointer.py` — synthetic VAD sequences → expected utterance cuts.
- `config.py` — enum/type validation, env precedence, `language=auto` sentinel, `--config` plumbing
  through `main()`.
- Fixtures: two ~5 s clips (`tests/fixtures/en.wav`, `uk.wav`) committed for LID tests.
- Tests that download a model are marked `@pytest.mark.slow` and **deselected by default**
  (`addopts = "-m 'not slow'"`). ~~CI runs the `faster_whisper` path only; MLX cannot run on a
  Linux runner.~~ *(Struck 2026-09-28, DECIDE-07: there is no CI and no remote — R6. Run the suite
  locally; MLX tests skip off Apple Silicon.)*

## Audio routing (user setup, not automatable)

| OS | Device | Gotchas |
|----|--------|---------|
| macOS | [BlackHole](https://github.com/ExistentialAudio/BlackHole) + a Multi-Output Device | BlackHole is 48 kHz/2 ch. In the Multi-Output Device, the **built-in output must be the top / clock device**, and **enable Drift Correction for every other device** — otherwise samples are dropped (this *is* the capture-vs-transcription clock-drift failure). `gmst` opens at native rate and resamples. |
| Windows | VB-Audio Virtual Cable, or WASAPI loopback | — |
| Linux | the PulseAudio/PipeWire sink `.monitor` source | — |

## Platform support

**Supported**: macOS (Apple Silicon) — the only config where both the latency and Ukrainian-accuracy
stories close. **Expected to run, not validated**: Linux / Windows via the `faster_whisper` backend
(the portable fallback; there is no CI — DECIDE-07).
