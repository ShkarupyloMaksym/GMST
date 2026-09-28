"""Resample / downmix arbitrary PCM to the pipeline contract (16 kHz mono float32).

``to_contract`` is the whole-signal (one-shot) path: the batch/file side, and any caller handed a
complete buffer. ``soxr.resample`` is a one-shot API — calling it per 100 ms capture block would
restart the polyphase filter at every block boundary — so the live device source instead keeps a
persistent ``make_stream_resampler`` between blocks and feeds it chunk by chunk.

The batch file source relies on PyAV's own resampler (it is already decoding through ffmpeg).
"""

from __future__ import annotations

import numpy as np
import soxr

from gmst.audio.types import SAMPLE_RATE, AudioArray


def to_mono_float32(pcm: np.ndarray) -> AudioArray:
    """Downmix and rescale, without touching the sample rate.

    ``pcm`` may be ``(n,)`` mono or ``(n, channels)``; any dtype. Returns ``(n,)`` float32.
    """
    x = np.asarray(pcm)
    if x.ndim == 2:
        x = x.mean(axis=1)
    elif x.ndim != 1:
        raise ValueError(f"expected 1-D or 2-D PCM, got shape {x.shape}")

    if np.issubdtype(x.dtype, np.integer):
        scale = float(np.iinfo(x.dtype).max)
        return x.astype(np.float32) / scale
    return x.astype(np.float32, copy=False)


def make_stream_resampler(in_rate: int):
    """A stateful resampler for block-by-block capture, or ``None`` when the rate already matches.

    Feed it with ``rs.resample_chunk(block)``; filter state carries across calls, so the output is
    continuous instead of restarting at every block boundary.
    """
    if in_rate == SAMPLE_RATE:
        return None
    return soxr.ResampleStream(in_rate, SAMPLE_RATE, 1, dtype="float32", quality="HQ")


def to_contract(pcm: np.ndarray, in_rate: int) -> AudioArray:
    """One-shot conversion of a whole signal to ``(n,)`` 16 kHz mono float32."""
    x = to_mono_float32(pcm)
    if in_rate != SAMPLE_RATE:
        x = soxr.resample(x, in_rate, SAMPLE_RATE, quality="HQ").astype(np.float32, copy=False)
    return x
