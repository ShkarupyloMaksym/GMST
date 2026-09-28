"""`gmst bench` — measure each candidate model on the configured engine.

Reports, per (engine, model):
- **batch RTF**  = transcribe_seconds / audio_seconds, decoding the clip through the **shipped
  batch path** (``pipeline.batch.transcribe_by_region``: per-region restricted LID unless the
  language is pinned) — not the engine's in-pass LID, which ranked models differently (R5).
- **streaming amplification** = *measured* seconds per stream update / ``UPDATE_INTERVAL_S``: the
  median wall time of decoding a ``TYPICAL_BUFFER_S`` buffer, plus the per-utterance LID pass when
  the language is not pinned. Must be < 1 for the model to keep up. Until the 2026-09-28 review
  this was ``RTF x max_buffer_seconds``, which assumes decode cost scales with buffer length;
  Whisper pads every call to a 30 s window, so on the 2-4 s buffers the trim keeps the real cost
  was 4-6x that (R5).
- **WER** (overall) if a reference transcript is supplied — a sanity check on the user's own clip.
  Model selection by UK and EN WER, with confidence intervals, is ``eval/run_eval.py`` (one clip
  cannot separate the candidates: R5 put the needed sample at hundreds to thousands of clips).

Each candidate runs in isolation; a failure (missing CT2 conversion, download error, OOM) is
caught and reported as a row, not raised. Each candidate's model is also **released before the
next one loads** — two large-v3-class models resident at once is an OOM on the Apple Silicon
target, and MLX's global ``ModelHolder`` cache would otherwise keep every candidate alive.
"""

from __future__ import annotations

import dataclasses
import gc
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from gmst.audio.file_source import decode_file
from gmst.audio.types import SAMPLE_RATE, duration_seconds
from gmst.config import Config
from gmst.pipeline.batch import transcribe_by_region

UPDATE_INTERVAL_S = 1.0
TYPICAL_BUFFER_S = 4.0  # one utterance's unconfirmed buffer once the per-commit trim runs
_TIMING_REPEATS = 3

# (label, model_size, model_repo) — see PLAN.md "Model choice is provisional until measured".
FASTER_WHISPER_CANDIDATES = [
    ("large-v2", "large-v2", None),
    ("large-v3", "large-v3", None),
    ("large-v3-turbo", "large-v3-turbo", None),
    ("turbo-quantized-uk", None, "Yehor/whisper-large-v3-turbo-quantized-uk"),
]
MLX_CANDIDATES = [
    ("large-v2", "large-v2", None),
    ("large-v3", "large-v3", None),
    ("large-v3-turbo", "large-v3-turbo", None),
]


@dataclass(slots=True)
class BenchRow:
    label: str
    ok: bool = False
    load_seconds: float = 0.0
    rtf: float = 0.0
    update_seconds: float = 0.0
    amplification: float = 0.0
    wer: float | None = None
    n_segments: int = 0
    error: str = ""


_CANDIDATES = {
    "faster_whisper": FASTER_WHISPER_CANDIDATES,
    "mlx_whisper": MLX_CANDIDATES,
}


def _candidates(engine: str) -> list[tuple[str, str | None, str | None]]:
    """Candidate models for an engine. An engine with no list is an error, not four identical
    ``NotImplementedError`` rows."""
    try:
        return _CANDIDATES[engine]
    except KeyError:
        raise NotImplementedError(
            f"`gmst bench` has no candidate list for engine {engine!r}"
        ) from None


def run_bench(clip: str | Path, cfg: Config, reference: str | None = None) -> list[BenchRow]:
    from gmst.transcribe.backends import load_engine

    audio = decode_file(clip)
    audio_s = duration_seconds(audio)

    rows: list[BenchRow] = []
    engine = None
    for label, model_size, model_repo in _candidates(cfg.engine):
        row = BenchRow(label=label)
        cand = replace(
            cfg,
            model_size=model_size or cfg.model_size,
            model_repo=model_repo,
        )
        try:
            t0 = time.monotonic()
            engine = load_engine(cand, per_segment_lid=False, word_timestamps=False)
            row.load_seconds = time.monotonic() - t0

            t1 = time.monotonic()
            segments = transcribe_by_region(audio, cand, engine)
            row.rtf = (time.monotonic() - t1) / audio_s if audio_s else float("nan")
            row.update_seconds = _per_update_seconds(engine, audio, cand)
            row.amplification = row.update_seconds / UPDATE_INTERVAL_S
            row.n_segments = len(segments)
            if reference is not None:
                from gmst.metrics import word_error_rate

                row.wer = word_error_rate(reference, " ".join(s.text for s in segments))
            row.ok = True
        except Exception as exc:  # noqa: BLE001 - one bad candidate must not abort the run
            row.error = f"{type(exc).__name__}: {exc}"
        finally:
            # release before the next candidate loads — including when this one failed
            engine = None
            _release_model_caches(cfg.engine)
            gc.collect()
        rows.append(row)
    return rows


def _per_update_seconds(engine, audio, cfg: Config) -> float:
    """Median wall time of one stream update: decode a ``TYPICAL_BUFFER_S`` buffer (tiled from
    the clip if it is shorter), plus the per-utterance LID pass unless the language is pinned."""
    n = int(TYPICAL_BUFFER_S * SAMPLE_RATE)
    src = np.asarray(audio, dtype=np.float32)
    buf = np.resize(src, n) if len(src) else np.zeros(n, np.float32)
    lang = cfg.language or "en"
    engine.transcribe(buf, language=lang)  # warm-up: first calls pay one-off init
    times = []
    for _ in range(_TIMING_REPEATS):
        t = time.monotonic()
        if cfg.language is None:
            engine.detect_language(buf[: 3 * SAMPLE_RATE], prev_lang=None)
        engine.transcribe(buf, language=lang)
        times.append(time.monotonic() - t)
    return float(np.median(times))


def _release_model_caches(engine: str) -> None:
    """Drop backend-level caches that outlive the engine object."""
    if engine != "mlx_whisper":
        return
    try:  # pragma: no cover - MLX only exists on Apple Silicon
        import mlx.core as mx
        from mlx_whisper.transcribe import ModelHolder

        ModelHolder.model = None
        ModelHolder.model_path = None
        mx.clear_cache()
    except Exception:  # noqa: BLE001 - a cache we cannot reach is not a bench failure
        pass


def format_table(rows: list[BenchRow]) -> str:
    head = (f"{'model':<20} {'load s':>7} {'RTF':>7} {'s/upd':>6} {'stream×':>8} {'WER':>7} "
            f"{'segs':>5}  note")
    out = [head, "-" * len(head)]
    for r in rows:
        if not r.ok:
            out.append(f"{r.label:<20} {'':>7} {'':>7} {'':>6} {'':>8} {'':>7} {'':>5}  {r.error}")
            continue
        wer = "—" if r.wer is None else f"{r.wer * 100:.1f}%"
        flag = "" if r.amplification < 1.0 else "  (too slow for streaming)"
        out.append(
            f"{r.label:<20} {r.load_seconds:>7.1f} {r.rtf:>7.3f} {r.update_seconds:>6.2f} "
            f"{r.amplification:>8.2f} {wer:>7} {r.n_segments:>5}{flag}"
        )
    return "\n".join(out)


def rows_as_dicts(rows: list[BenchRow]) -> list[dict]:
    return [dataclasses.asdict(r) for r in rows]
