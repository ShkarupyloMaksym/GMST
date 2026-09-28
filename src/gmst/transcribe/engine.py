"""The ASR engine interface.

Backends live in ``transcribe/backends/`` and each implement this Protocol:

- ``faster_whisper`` — portable default; CPU ``int8`` on Apple Silicon, CUDA elsewhere. LID is done
  in-pass (``multilingual=True``), so ``detect_language`` shares the decode work.
- ``mlx_whisper`` — Mac fast path (Apple GPU). ``detect_language`` costs one extra encoder pass.
- ``canary`` — optional (Phase 4); no built-in LID, needs an external one.

``detect_language`` is a method, not a free function, precisely so it can reuse the backend's
already-loaded model instead of loading a second one.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gmst.audio.types import AudioArray
from gmst.transcribe.types import Segment


@runtime_checkable
class Engine(Protocol):
    def transcribe(
        self,
        audio: AudioArray,
        *,
        language: str | None = None,
        prompt: str | None = None,
    ) -> list[Segment]:
        """Transcribe one buffer. ``language=None`` lets the backend detect per segment.

        Streaming callers always pass ``vad_filter=False`` semantics (silence is cut upstream by
        ``segment/vad.py``); batch callers may let the backend filter.
        """
        ...

    def detect_language(
        self, audio: AudioArray, *, prev_lang: str | None = None
    ) -> tuple[str, float]:
        """Return ``(iso_code, probability)`` for the dominant language in ``audio``.

        Applies GMST's LID policy (uk/ru tie-break + sticky threshold vs ``prev_lang``); see
        ``transcribe/lid.py``.
        """
        ...
