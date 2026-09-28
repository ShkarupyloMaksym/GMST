"""Voice-activity detection for the streaming endpointer.

Two backends:
- ``silero`` (default) — faster-whisper's bundled Silero model via ``get_speech_timestamps``.
- ``energy`` — a plain RMS gate; no model load, used for tests and low-resource machines.

Both expose ``speech_regions(audio) -> [(t0, t1), …]`` in seconds. The pipeline derives trailing
silence and "has speech" from that.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np

from gmst.audio.types import SAMPLE_RATE, AudioArray
from gmst.config import Config


class Vad(Protocol):
    def speech_regions(self, audio: AudioArray) -> list[tuple[float, float]]: ...


class SileroVad:
    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = threshold

    def speech_regions(self, audio: AudioArray) -> list[tuple[float, float]]:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        opts = VadOptions(
            threshold=self._threshold,
            min_silence_duration_ms=0,
            speech_pad_ms=0,
        )
        ts = get_speech_timestamps(np.ascontiguousarray(audio, dtype=np.float32), opts)
        return [(t["start"] / SAMPLE_RATE, t["end"] / SAMPLE_RATE) for t in ts]


class EnergyVad:
    def __init__(self, threshold: float = 0.02, frame_ms: int = 30) -> None:
        self._threshold = threshold
        self._frame = frame_ms

    def speech_regions(self, audio: AudioArray) -> list[tuple[float, float]]:
        n = max(1, int(SAMPLE_RATE * self._frame / 1000))
        regions: list[tuple[float, float]] = []
        start: int | None = None
        for i in range(0, len(audio), n):
            frame = audio[i : i + n]
            loud = bool(np.sqrt(np.mean(np.square(frame, dtype=np.float64))) >= self._threshold)
            if loud and start is None:
                start = i
            elif not loud and start is not None:
                regions.append((start / SAMPLE_RATE, i / SAMPLE_RATE))
                start = None
        if start is not None:
            regions.append((start / SAMPLE_RATE, len(audio) / SAMPLE_RATE))
        return regions


def make_vad(cfg: Config) -> Vad:
    if cfg.vad_backend == "energy":
        return EnergyVad(threshold=cfg.vad_threshold)
    return SileroVad(threshold=cfg.vad_threshold)


def has_speech(regions: list[tuple[float, float]]) -> bool:
    return bool(regions)


def trailing_silence(regions: list[tuple[float, float]], total_seconds: float) -> float:
    if not regions:
        return total_seconds
    return max(0.0, total_seconds - regions[-1][1])
