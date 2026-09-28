import numpy as np

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.segment.vad import EnergyVad, has_speech, make_vad, trailing_silence


def test_energy_vad_finds_the_loud_region():
    sr = SAMPLE_RATE
    audio = np.concatenate([
        np.zeros(sr, dtype=np.float32),                       # 1 s silence
        (0.3 * np.ones(sr, dtype=np.float32)),                # 1 s "speech"
        np.zeros(sr, dtype=np.float32),                       # 1 s silence
    ])
    regions = EnergyVad(threshold=0.05).speech_regions(audio)
    assert len(regions) == 1
    t0, t1 = regions[0]
    assert 0.9 < t0 < 1.1
    assert 1.9 < t1 < 2.1


def test_trailing_silence_and_has_speech():
    assert has_speech([]) is False
    assert has_speech([(0.0, 1.0)]) is True
    assert trailing_silence([], 3.0) == 3.0
    assert trailing_silence([(0.0, 2.0)], 3.0) == 1.0


def test_make_vad_selects_backend():
    assert isinstance(make_vad(Config(vad_backend="energy")), EnergyVad)
