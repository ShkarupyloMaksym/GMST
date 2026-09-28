"""The audio contract shared by every pipeline stage.

All audio moving between stages is float32 mono PCM at ``SAMPLE_RATE``, shape ``(n_samples,)``,
amplitude in ``[-1.0, 1.0]``. Sources open at the device's native rate and resample/downmix to
this form (see ``audio/resample.py``). Timestamps are always derived from a monotonic sample
counter, never wall-clock time.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

SAMPLE_RATE = 16_000          # Hz — Whisper's native input rate
CHANNELS = 1

AudioArray = npt.NDArray[np.float32]   # mono, shape (n_samples,)


def duration_seconds(samples: AudioArray) -> float:
    return len(samples) / SAMPLE_RATE


def rms_dbfs(samples: AudioArray) -> float:
    """Level of a block in dBFS; -inf for pure silence."""
    if samples.size == 0:
        return float("-inf")
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    return 20.0 * np.log10(rms) if rms > 0 else float("-inf")
