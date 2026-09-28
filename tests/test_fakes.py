import numpy as np

from gmst.transcribe.engine import Engine
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine


def _audio(seconds: float = 1.0) -> np.ndarray:
    return np.zeros(int(seconds * 16_000), dtype=np.float32)


def test_fakeengine_satisfies_protocol():
    eng: Engine = FakeEngine([[]])
    assert isinstance(eng, Engine)  # runtime_checkable structural check


def test_scripts_advance_then_repeat_last():
    scripts = [
        [Segment(0.0, 1.0, "hello", "en")],
        [Segment(0.0, 2.0, "hello world", "en")],
    ]
    eng = FakeEngine(scripts)
    assert [s.text for s in eng.transcribe(_audio())] == ["hello"]
    assert [s.text for s in eng.transcribe(_audio())] == ["hello world"]
    assert [s.text for s in eng.transcribe(_audio())] == ["hello world"]  # repeats
    assert len(eng.calls) == 3
    assert eng.calls[0]["samples"] == 16_000


def test_detect_language_is_scripted():
    eng = FakeEngine([[]], lang="uk", lang_prob=0.8)
    assert eng.detect_language(_audio()) == ("uk", 0.8)
