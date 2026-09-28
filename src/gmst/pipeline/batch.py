"""Batch pipeline: decode a whole file, transcribe once, emit every segment as final.

`faster-whisper` handles VAD and internal 30 s chunking, so this stage is thin. The returned
`BatchResult` carries timing so `gmst batch` can print RTF.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from gmst.audio.file_source import decode_file
from gmst.audio.types import duration_seconds
from gmst.config import Config
from gmst.sink.base import Sink
from gmst.transcribe.engine import Engine


@dataclass(slots=True)
class BatchResult:
    audio_seconds: float
    transcribe_seconds: float
    n_segments: int

    @property
    def rtf(self) -> float:
        return self.transcribe_seconds / self.audio_seconds if self.audio_seconds else float("nan")


def run_batch(path: str | Path, cfg: Config, engine: Engine, sink: Sink) -> BatchResult:
    audio = decode_file(path)
    started = time.monotonic()
    segments = engine.transcribe(audio, language=cfg.language)
    elapsed = time.monotonic() - started

    for seg in segments:
        seg.is_final = True
        sink.emit(seg)
    sink.close()

    return BatchResult(duration_seconds(audio), elapsed, len(segments))
