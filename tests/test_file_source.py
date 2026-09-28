import numpy as np
import pytest
import soundfile as sf

from gmst.audio.file_source import decode_file
from gmst.audio.types import SAMPLE_RATE


def _sine(seconds: float, rate: int, freq: float = 220.0) -> np.ndarray:
    t = np.linspace(0, seconds, int(seconds * rate), endpoint=False)
    return (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def test_decode_wav_resamples_to_contract(tmp_path):
    src = tmp_path / "a.wav"
    sf.write(src, _sine(1.0, 44_100), 44_100)
    out = decode_file(src)
    assert out.dtype == np.float32
    assert out.ndim == 1
    assert abs(len(out) - SAMPLE_RATE) <= SAMPLE_RATE * 0.02


def test_decode_stereo_is_downmixed(tmp_path):
    src = tmp_path / "s.wav"
    stereo = np.stack([_sine(0.5, 16_000), -_sine(0.5, 16_000)], axis=1)
    sf.write(src, stereo, 16_000)
    out = decode_file(src)
    assert out.ndim == 1
    assert np.max(np.abs(out)) < 1e-3  # opposite channels cancel


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        decode_file("nope.wav")
