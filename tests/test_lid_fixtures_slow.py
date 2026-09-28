"""Real audio through real LID (review F.5 / FIX-19): the promised fixtures, finally used."""

from pathlib import Path

import pytest
import soundfile as sf

from gmst.config import Config

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.slow
@pytest.mark.parametrize("lang", ["en", "uk"])
def test_detect_language_on_real_speech(lang):
    from gmst.transcribe.backends import load_engine

    audio, sr = sf.read(FIX / f"{lang}.wav", dtype="float32")
    assert sr == 16_000 and audio.ndim == 1
    engine = load_engine(Config(model_size="tiny"), per_segment_lid=False)
    got, _ = engine.detect_language(audio)
    assert got == lang
