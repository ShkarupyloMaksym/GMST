"""Growing-buffer endpointer for the streaming pipeline.

Accumulates 16 kHz mono blocks. The pipeline decodes the whole buffer each time
``ready_to_decode()`` is true (>= ``min_chunk_seconds`` of new audio), then asks ``assess()``
whether this is an endpoint (>= ``min_silence_ms`` trailing silence after speech) or a forced cut
(buffer >= ``max_buffer_seconds``). ``reset()`` starts the next utterance, optionally keeping
``overlap_seconds`` of audio to bridge the seam. ``trim_to()`` drops audio the pipeline has already
committed, so the re-decoded buffer stays short (PLAN.md's latency budget assumes this).

Absolute time is owned here: ``t0_seconds`` is the session-time offset of the current buffer's
start, advanced on every ``reset``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gmst.audio.types import SAMPLE_RATE, AudioArray
from gmst.config import Config
from gmst.segment.vad import Vad, has_speech, trailing_silence

_TRIM_BACKOFF_S = 0.2  # small back-off so a trim never cuts mid-phoneme


@dataclass(slots=True)
class Assessment:
    regions: list[tuple[float, float]]
    trailing_silence: float
    is_endpoint: bool
    forced: bool


class Endpointer:
    def __init__(self, cfg: Config, vad: Vad) -> None:
        self._cfg = cfg
        self._vad = vad
        self._buf: list[AudioArray] = []
        self._buf_samples = 0
        self._since_decode = 0
        self._t0_samples = 0

    def add(self, block: AudioArray) -> None:
        self._buf.append(np.asarray(block, dtype=np.float32))
        self._buf_samples += len(block)
        self._since_decode += len(block)

    @property
    def buffer(self) -> AudioArray:
        if not self._buf:
            return np.zeros(0, dtype=np.float32)
        if len(self._buf) > 1:
            self._buf = [np.concatenate(self._buf)]
        return self._buf[0]

    @property
    def buffer_seconds(self) -> float:
        return self._buf_samples / SAMPLE_RATE

    @property
    def t0_seconds(self) -> float:
        return self._t0_samples / SAMPLE_RATE

    def ready_to_decode(self) -> bool:
        return self._since_decode / SAMPLE_RATE >= self._cfg.min_chunk_seconds

    def mark_decoded(self) -> None:
        self._since_decode = 0

    def assess(self) -> Assessment:
        audio = self.buffer
        regions = self._vad.speech_regions(audio)
        total = len(audio) / SAMPLE_RATE
        tail = trailing_silence(regions, total)
        is_endpoint = has_speech(regions) and tail * 1000 >= self._cfg.min_silence_ms
        forced = self.buffer_seconds >= self._cfg.max_buffer_seconds
        return Assessment(regions, tail, is_endpoint, forced)

    def trim_to(self, seconds: float) -> float:
        """Drop buffer audio before ``seconds`` (buffer-relative); advances ``t0`` to match.

        Called at a committed word boundary, with ``_TRIM_BACKOFF_S`` of slack so the cut lands
        just before the word rather than inside it. Returns the seconds actually dropped, which
        the caller needs to work out which words are still in the buffer (0.0 when nothing went).
        """
        audio = self.buffer
        n = max(0, min(len(audio), int((seconds - _TRIM_BACKOFF_S) * SAMPLE_RATE)))
        if n <= 0:
            return 0.0
        self._buf = [audio[n:].copy()]  # copy so the pre-trim buffer can be freed
        self._buf_samples = len(audio) - n
        self._t0_samples += n
        return n / SAMPLE_RATE

    def reset(self, *, keep_overlap: bool) -> None:
        audio = self.buffer
        keep = min(int(self._cfg.overlap_seconds * SAMPLE_RATE), len(audio)) if keep_overlap else 0
        self._t0_samples += len(audio) - keep
        tail = audio[len(audio) - keep :] if keep else np.zeros(0, dtype=np.float32)
        self._buf = [tail] if keep else []
        self._buf_samples = keep
        self._since_decode = 0
