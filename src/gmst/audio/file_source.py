"""Decode an audio file to the pipeline contract (16 kHz mono float32), whole-file, for batch.

PyAV (ffmpeg) is the primary path — it reads m4a/aac/mp3/opus/wav/flac/…. ``soundfile`` is a
fallback for the plain PCM formats libsndfile supports, in case PyAV is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from gmst.audio.types import SAMPLE_RATE, AudioArray


def decode_file(path: str | Path) -> AudioArray:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        return _decode_pyav(path)
    except _PyAVUnavailable:
        return _decode_soundfile(path)


class _PyAVUnavailable(Exception):
    pass


def _decode_pyav(path: Path) -> AudioArray:
    try:
        import av
    except ImportError as exc:  # pragma: no cover - PyAV is a declared dep
        raise _PyAVUnavailable(str(exc)) from exc

    chunks: list[np.ndarray] = []
    with av.open(str(path)) as container:
        if not container.streams.audio:
            raise ValueError(f"no audio stream in {path}")
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray().reshape(-1))

    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32, copy=False)


def _decode_soundfile(path: Path) -> AudioArray:
    import soundfile as sf

    from gmst.audio.resample import to_contract

    pcm, rate = sf.read(str(path), dtype="float32", always_2d=False)
    return to_contract(pcm, rate)
