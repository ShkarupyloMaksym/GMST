import numpy as np

import gmst.pipeline.batch as batch_mod
from gmst.config import Config
from gmst.pipeline.batch import run_batch
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine


class _RecordingSink:
    def __init__(self):
        self.emitted: list[Segment] = []
        self.closed = False

    def emit(self, seg):
        self.emitted.append(seg)

    def close(self):
        self.closed = True


def test_run_batch_marks_final_and_reports_rtf(monkeypatch):
    monkeypatch.setattr(batch_mod, "decode_file", lambda _p: np.zeros(32_000, dtype=np.float32))
    engine = FakeEngine([[Segment(0.0, 1.0, "hi", "en"), Segment(1.0, 2.0, "there", "en")]])
    sink = _RecordingSink()

    result = run_batch("ignored.wav", Config(language="en"), engine, sink)  # one whole-file call

    assert [s.text for s in sink.emitted] == ["hi", "there"]
    assert all(s.is_final for s in sink.emitted)
    assert sink.closed
    assert result.n_segments == 2
    assert result.audio_seconds == 2.0  # 32000 / 16000
    assert result.rtf >= 0.0


class _TwoLanguageEngine(FakeEngine):
    """Detects "en" on amplitude-0.3 audio and "uk" on amplitude-0.5 audio, and says which audio
    it was asked to decode — so a test can see each region decoded in its own language."""

    def __init__(self):
        super().__init__(self._script)
        self.lid_calls: list[str] = []

    @staticmethod
    def _script(audio, _i):
        loud = audio[np.abs(audio) > 0.05]
        word = "hello" if np.isclose(loud.mean(), 0.3) else "привіт"
        return [Segment(0.1, len(audio) / 16_000 - 0.1, word, "xx")]

    def detect_language(self, audio, *, prev_lang=None):
        loud = audio[np.abs(audio) > 0.05]
        lang = "en" if np.isclose(loud.mean(), 0.3) else "uk"
        self.lid_calls.append(lang)
        return lang, 0.9


def test_batch_decodes_each_speech_region_in_its_own_language(monkeypatch):
    """DECIDE-03: with no pinned language, batch VAD-splits the file and decodes each region with
    the language detected on it — not faster-whisper's one autodetect for the whole file (R2 F3)."""
    sr = 16_000
    audio = np.concatenate([
        np.full(sr, 0.3, dtype=np.float32), np.zeros(sr, dtype=np.float32),
        np.full(sr, 0.5, dtype=np.float32), np.zeros(sr // 2, dtype=np.float32),
    ])
    monkeypatch.setattr(batch_mod, "decode_file", lambda _p: audio)
    engine = _TwoLanguageEngine()
    sink = _RecordingSink()

    run_batch("ignored.wav", Config(vad_backend="energy", vad_threshold=0.05), engine, sink)

    assert [c["language"] for c in engine.calls] == ["en", "uk"]
    assert [(s.text, s.language) for s in sink.emitted] == [("hello", "en"), ("привіт", "uk")]
    assert sink.emitted[1].start > 1.5, "region times were not offset to file time"


def test_batch_with_a_pinned_language_decodes_the_file_once(monkeypatch):
    monkeypatch.setattr(batch_mod, "decode_file", lambda _p: np.full(32_000, 0.3, np.float32))
    engine = _TwoLanguageEngine()
    run_batch("x.wav", Config(language="uk", vad_backend="energy"), engine, _RecordingSink())
    assert [c["language"] for c in engine.calls] == ["uk"] and engine.lid_calls == []
