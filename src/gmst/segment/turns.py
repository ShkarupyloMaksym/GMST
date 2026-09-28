"""Conversational-turn boundaries from pauses.

Not speaker identification — just "a gap this long means a new turn". The pipeline feeds every
committed span's absolute times in order; ``update`` returns the current turn index, bumping it
when the gap since the previous span exceeds ``gap_seconds`` (``0`` disables bumping).
"""

from __future__ import annotations


class TurnTracker:
    def __init__(self, gap_seconds: float) -> None:
        self._gap = gap_seconds
        self._turn = 1
        self._last_end: float | None = None

    @property
    def turn(self) -> int:
        return self._turn

    def update(self, start: float, end: float) -> int:
        if self._gap > 0 and self._last_end is not None and start - self._last_end > self._gap:
            self._turn += 1
        self._last_end = end if self._last_end is None else max(self._last_end, end)
        return self._turn
