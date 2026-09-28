"""Test doubles.

``FakeEngine`` implements the ``Engine`` protocol with scripted output, so the whole streaming
pipeline (endpointer -> LID -> reconcile -> sink) can be tested deterministically with no model
and no audio device.
"""

from __future__ import annotations

from collections.abc import Sequence

from gmst.audio.types import AudioArray
from gmst.transcribe.types import Segment


class FakeEngine:
    """Returns scripted segments on each ``transcribe`` call.

    ``scripts`` is either a sequence of hypotheses (``scripts[i]`` for the i-th call, last entry
    repeating) or a callable ``(audio, call_index) -> list[Segment]``. ``lang`` / ``lang_prob``
    drive ``detect_language``.
    """

    def __init__(
        self,
        scripts,
        *,
        lang: str = "en",
        lang_prob: float = 0.99,
    ) -> None:
        self._callable = scripts if callable(scripts) else None
        self._scripts = None if self._callable else ([list(s) for s in scripts] or [[]])
        self._lang = lang
        self._lang_prob = lang_prob
        self.calls: list[dict[str, object]] = []

    def transcribe(
        self,
        audio: AudioArray,
        *,
        language: str | None = None,
        prompt: str | None = None,
        hotwords: str | None = None,
    ) -> list[Segment]:
        idx = len(self.calls)
        self.calls.append({"samples": len(audio), "language": language, "prompt": prompt,
                           "hotwords": hotwords})
        if self._callable is not None:
            src = self._callable(audio, idx)
        else:
            src = self._scripts[min(idx, len(self._scripts) - 1)]
        return [
            Segment(
                s.start, s.end, s.text, s.language,
                s.is_final, s.lid_prob, s.turn, list(s.words),
            )
            for s in src
        ]

    def detect_language(
        self, audio: AudioArray, *, prev_lang: str | None = None
    ) -> tuple[str, float]:
        return self._lang, self._lang_prob


class ListSource:
    """A pre-recorded block stream, for testing `run_stream` without an audio device."""

    def __init__(self, blocks: Sequence[AudioArray]) -> None:
        self._blocks = list(blocks)
        self._closed = False
        self.lagging = False

    def blocks(self):
        for b in self._blocks:
            if self._closed:
                return
            yield b

    def close(self) -> None:
        self._closed = True

    @property
    def seconds_captured(self) -> float:
        from gmst.audio.types import SAMPLE_RATE

        return sum(len(b) for b in self._blocks) / SAMPLE_RATE
