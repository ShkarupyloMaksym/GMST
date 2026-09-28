"""Transcription result types and their timestamp contract.

Timestamp contract:
- ``start`` / ``end`` (and each ``Word``'s) are **buffer-relative seconds (float)** as returned by
  the engine for the audio it was handed.
- The pipeline owns the monotonic ``samples_consumed`` counter and converts to absolute session
  time (``samples / SAMPLE_RATE``); backends never see absolute time. Segments the pipeline emits
  to a sink carry **absolute** times.
- ``is_final`` is set **only** by ``reconcile``, never by a backend.
- ``turn`` is set **only** by the pipeline's ``TurnTracker``; backends leave it 1.
- Once a span is emitted as final its times never move; committed spans are strictly monotonic.
- Naming rule elsewhere: integer millisecond fields end ``_ms``, float second fields end
  ``_seconds``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(slots=True)
class Segment:
    start: float          # buffer-relative seconds (absolute once emitted by the pipeline)
    end: float
    text: str
    language: str         # ISO code the engine transcribed this span as
    is_final: bool = False
    lid_prob: float = 1.0
    turn: int = 1         # conversational turn index; bumped by the pipeline on long pauses
    words: list[Word] = field(default_factory=list)
