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

    result = run_batch("ignored.wav", Config(), engine, sink)

    assert [s.text for s in sink.emitted] == ["hi", "there"]
    assert all(s.is_final for s in sink.emitted)
    assert sink.closed
    assert result.n_segments == 2
    assert result.audio_seconds == 2.0  # 32000 / 16000
    assert result.rtf >= 0.0
