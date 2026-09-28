"""The ASR engine interface.

Backends live in ``transcribe/backends/`` and each implement this Protocol:

- ``faster_whisper`` — portable default; CPU ``int8`` on Apple Silicon, CUDA elsewhere.
  ``detect_language`` is one separate encoder pass (``WhisperModel.detect_language``), not the
  decode's in-pass LID, which has no uk/ru handling and no per-segment result to read back.
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
        hotwords: str | None = None,
    ) -> list[Segment]:
        """Transcribe one buffer. ``language=None`` lets the backend detect per segment.
        ``hotwords`` carries the term glossary (DECIDE-08); callers pass it only when there are
        terms, and a backend without such a parameter may ignore it (the prompt carries them too).

        Streaming callers always pass ``vad_filter=False`` semantics (silence is cut upstream by
        ``segment/vad.py``); batch callers may let the backend filter.
        """
        ...

    def detect_language(
        self, audio: AudioArray, *, prev_lang: str | None = None
    ) -> tuple[str, float]:
        """Return ``(iso_code, probability)`` for the dominant language in ``audio``.

        Applies GMST's LID policy (restricted to ``cfg.lid_languages``, ``ru`` folded into ``uk``,
        sticky threshold vs ``prev_lang``); see ``transcribe/lid.py``.
        """
        ...
