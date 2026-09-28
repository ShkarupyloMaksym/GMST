"""`gmst bench` — measure each candidate model on the configured engine.

Reports, per (engine, model):
- **batch RTF**  = transcribe_seconds / audio_seconds
- **streaming amplification** = RTF x (max_buffer_seconds / UPDATE_INTERVAL_S) — the factor
  LocalAgreement-2 adds by re-decoding the growing buffer each update (PLAN.md "Latency budget").
  Must be < 1 for the model to keep up in streaming.
- **WER** (overall) if a reference transcript is supplied.

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

from gmst.audio.file_source import decode_file
from gmst.audio.types import duration_seconds
from gmst.config import Config

UPDATE_INTERVAL_S = 1.0

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
    amp_factor = cfg.max_buffer_seconds / UPDATE_INTERVAL_S

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
            segments = engine.transcribe(audio, language=cfg.language)
            row.rtf = (time.monotonic() - t1) / audio_s if audio_s else float("nan")
            row.amplification = row.rtf * amp_factor
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
    head = f"{'model':<20} {'load s':>7} {'RTF':>7} {'stream×':>8} {'WER':>7} {'segs':>5}  note"
    out = [head, "-" * len(head)]
    for r in rows:
        if not r.ok:
            out.append(f"{r.label:<20} {'':>7} {'':>7} {'':>8} {'':>7} {'':>5}  {r.error}")
            continue
        wer = "—" if r.wer is None else f"{r.wer * 100:.1f}%"
        flag = "" if r.amplification < 1.0 else "  (too slow for streaming)"
        out.append(
            f"{r.label:<20} {r.load_seconds:>7.1f} {r.rtf:>7.3f} "
            f"{r.amplification:>8.2f} {wer:>7} {r.n_segments:>5}{flag}"
        )
    return "\n".join(out)


def rows_as_dicts(rows: list[BenchRow]) -> list[dict]:
    return [dataclasses.asdict(r) for r in rows]
