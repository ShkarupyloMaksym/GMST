"""Real faster-whisper backend — downloads the `tiny` model. Deselected by default.

Run with: uv run pytest -m slow
"""

import numpy as np
import pytest

from gmst.config import Config
from gmst.transcribe.engine import Engine

pytestmark = pytest.mark.slow


def _engine() -> Engine:
    from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

    return FasterWhisperEngine(Config(model_size="tiny", compute_type="int8"))


def test_transcribe_returns_segments_on_speech_like_audio():
    eng = _engine()
    rng = np.random.default_rng(0)
    # 3 s of low-level noise — we only assert the call path works and shapes are sane.
    audio = (rng.standard_normal(48_000) * 0.01).astype(np.float32)
    segments = eng.transcribe(audio, language="en")
    assert isinstance(segments, list)
    for s in segments:
        assert s.end >= s.start
        assert s.language == "en"


def test_detect_language_returns_code_and_prob():
    eng = _engine()
    lang, prob = eng.detect_language(np.zeros(16_000, dtype=np.float32))
    assert isinstance(lang, str) and len(lang) <= 3
    assert 0.0 <= prob <= 1.0
