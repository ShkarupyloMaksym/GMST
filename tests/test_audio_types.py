import numpy as np

from gmst.audio.types import SAMPLE_RATE, duration_seconds, rms_dbfs


def test_duration_seconds():
    assert duration_seconds(np.zeros(SAMPLE_RATE, dtype=np.float32)) == 1.0


def test_rms_dbfs_silence_is_neg_inf():
    assert rms_dbfs(np.zeros(1024, dtype=np.float32)) == float("-inf")


def test_rms_dbfs_full_scale_is_zero():
    assert rms_dbfs(np.ones(1024, dtype=np.float32)) == 0.0
