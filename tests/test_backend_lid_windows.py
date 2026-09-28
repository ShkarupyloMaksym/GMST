"""Per-segment LID windowing, with the model stubbed out (no download, no MLX)."""

import numpy as np
import pytest

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config


class _RecordingModel:
    """Stands in for a WhisperModel: records the length/content of every LID clip."""

    def __init__(self):
        self.clips = []

    def detect_language(self, audio):
        self.clips.append(np.asarray(audio))
        return "uk", 0.95, [("uk", 0.95), ("en", 0.02)]


def _engine(monkeypatch):
    from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

    monkeypatch.setattr(FasterWhisperEngine, "__init__", lambda self, cfg: None)
    eng = FasterWhisperEngine(Config())
    eng._cfg = Config()
    eng._per_segment_lid = True
    eng._model = _RecordingModel()
    return eng


def test_short_segment_widens_its_window_instead_of_taking_the_whole_file(monkeypatch):
    eng = _engine(monkeypatch)
    # 10 minutes of audio, each second marked with its own value so we can tell where a clip came
    # from; a 0.2 s interjection sits at minute 5.
    audio = np.repeat(np.arange(600, dtype=np.float32), SAMPLE_RATE)

    lang, _ = eng._detect_slice(audio, 300.0, 300.2, prev_lang="en")

    assert lang == "uk"
    clip = eng._model.clips[0]
    assert len(clip) >= SAMPLE_RATE // 2, "window was not widened to the detector's minimum"
    assert len(clip) < len(audio), "LID fell back to the entire recording"
    # everything in the clip comes from around minute 5, not from the file's opening
    assert clip.min() >= 299.0 and clip.max() <= 301.0


def test_long_enough_segment_is_sliced_exactly(monkeypatch):
    eng = _engine(monkeypatch)
    audio = np.repeat(np.arange(60, dtype=np.float32), SAMPLE_RATE)

    eng._detect_slice(audio, 10.0, 12.0, prev_lang=None)

    clip = eng._model.clips[0]
    assert len(clip) == 2 * SAMPLE_RATE
    assert clip.min() == 10.0 and clip.max() == 11.0


def test_window_is_clamped_at_the_start_of_the_buffer(monkeypatch):
    eng = _engine(monkeypatch)
    audio = np.zeros(SAMPLE_RATE, dtype=np.float32)

    eng._detect_slice(audio, 0.0, 0.1, prev_lang=None)

    assert len(eng._model.clips[0]) >= SAMPLE_RATE // 2


def test_per_segment_lid_does_not_also_ask_for_in_pass_multilingual(monkeypatch):
    """Paying for faster-whisper's own per-segment LID *and* ours is paying twice for one answer."""
    from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

    seen = {}

    class _Model(_RecordingModel):
        def transcribe(self, audio, **kw):
            seen.update(kw)
            return iter(()), type("Info", (), {"language": "uk", "language_probability": 0.9})()

    monkeypatch.setattr(FasterWhisperEngine, "__init__", lambda self, cfg: None)
    eng = FasterWhisperEngine(Config())
    eng._cfg, eng._vad_filter, eng._word_ts = Config(), False, True
    eng._model = _Model()

    eng._per_segment_lid = True
    eng.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language=None)
    assert seen["multilingual"] is False

    eng._per_segment_lid = False
    eng.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language=None)
    assert seen["multilingual"] is True


@pytest.mark.slow
def test_mlx_lid_model_is_the_cached_transcribe_model():
    """Mac-only: `_load()` must hand back the instance `mlx_whisper.transcribe` already caches.

    Loading separately keeps two copies of a large-v3-class model in unified memory.
    """
    mx = pytest.importorskip("mlx.core")
    pytest.importorskip("mlx_whisper")
    from mlx_whisper.transcribe import ModelHolder

    from gmst.transcribe.backends.mlx_whisper import MlxWhisperEngine

    cfg = Config(engine="mlx_whisper", model_repo="mlx-community/whisper-tiny")
    eng = MlxWhisperEngine(cfg, per_segment_lid=False)
    assert eng._load() is ModelHolder.get_model(cfg.model_repo, mx.float16)


def test_detect_language_is_restricted_to_lid_languages(monkeypatch):
    """The backend passes cfg.lid_languages through: a Ukrainian clip the model calls "bg" comes
    back as "uk" (R2)."""
    eng = _engine(monkeypatch)

    class _BgModel:
        def detect_language(self, audio):
            return "bg", 0.4, [("bg", 0.4), ("uk", 0.3), ("ru", 0.2), ("en", 0.05)]

    eng._model = _BgModel()
    assert eng.detect_language(np.zeros(SAMPLE_RATE, dtype=np.float32))[0] == "uk"
