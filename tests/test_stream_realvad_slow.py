"""Streaming pipeline over the real Silero VAD + real `tiny` Whisper. Deselected by default.

Run with: uv run pytest -m slow
"""

import numpy as np
import pytest

from gmst.config import Config
from gmst.pipeline.stream import run_stream
from tests.fakes import ListSource

pytestmark = pytest.mark.slow

SR = 16_000


class _Sink:
    def __init__(self):
        self.segs = []
        self.closed = False

    def emit(self, seg):
        self.segs.append(seg)

    def close(self):
        self.closed = True

    @property
    def finals(self):
        return [s for s in self.segs if s.is_final]


def test_real_vad_and_engine_wire_together_and_shut_down_cleanly():
    from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

    rng = np.random.default_rng(0)
    speechish = (rng.standard_normal(3 * SR) * 0.05).astype(np.float32)
    tail_silence = np.zeros(SR, dtype=np.float32)
    audio = np.concatenate([speechish, tail_silence])
    blocks = [audio[i : i + SR // 4] for i in range(0, len(audio), SR // 4)]

    cfg = Config(model_size="tiny", vad_backend="silero", min_chunk_seconds=0.5)
    engine = FasterWhisperEngine(cfg, per_segment_lid=False)
    sink = _Sink()

    stats = run_stream(cfg, ListSource(blocks), engine, sink, language="en")

    assert sink.closed is True
    # Real Silero may or may not call this noise speech, so the transcript *content* is not
    # assertable — but the pipeline's invariants hold whatever it decides.
    assert stats.committed_words == sum(len(s.text.split()) for s in sink.finals)

    prev_end = -1.0
    for s in sink.finals:  # committed spans are strictly monotonic (types.py)
        assert s.start >= prev_end - 1e-6, f"{s.text!r} starts at {s.start}, before {prev_end}"
        assert s.end >= s.start
        prev_end = s.end

    # the same span must never be committed twice (the forced-cut/overlap seam bug)
    spans = [(round(s.start, 3), s.text) for s in sink.finals]
    assert len(spans) == len(set(spans))

    for s in sink.segs:
        assert s.language == "en"  # pinned by `language="en"`, partials included
        assert s.end >= s.start
        assert s.start >= 0.0
