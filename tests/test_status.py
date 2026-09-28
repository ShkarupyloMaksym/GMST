"""DECIDE-05: runtime status reaches the user during `gmst stream` (review F.13, R3)."""

import io
import json
import logging
from types import SimpleNamespace

import numpy as np

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.pipeline.stream import run_stream
from gmst.sink.base import TeeSink
from gmst.sink.jsonl import JsonlSink
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine


class _StatusSink:
    def __init__(self):
        self.events = []

    def emit(self, seg):
        pass

    def status(self, event):
        self.events.append(event)

    def close(self):
        pass


class _DroppingSource:
    """Replays blocks while its capture stats report drops/overflows, like a DeviceSource whose
    queue overflowed because the engine fell behind."""

    def __init__(self, blocks, drops_per_block=0, overflow_at=None):
        self._blocks = blocks
        self._closed = False
        self.stats = SimpleNamespace(blocks_dropped=0, overflows=0)
        self._drops = drops_per_block
        self._overflow_at = overflow_at

    @property
    def lagging(self):
        return self.stats.blocks_dropped > 0

    def blocks(self):
        for i, b in enumerate(self._blocks):
            if self._closed:
                return
            self.stats.blocks_dropped += self._drops
            if self._overflow_at is not None and i == self._overflow_at:
                self.stats.overflows += 1
            yield b

    def close(self):
        self._closed = True


def _blocks(audio):
    n = SAMPLE_RATE // 10
    return [audio[i : i + n] for i in range(0, len(audio), n)]


def _cfg():
    return Config(vad_backend="energy", vad_threshold=0.05, min_chunk_seconds=0.5)


def _engine():
    return FakeEngine([[Segment(0.0, 0.5, "так", "uk")]])


def test_dropped_audio_is_reported_as_lagging_and_logged(caplog):
    sink = _StatusSink()
    src = _DroppingSource(_blocks(np.full(3 * SAMPLE_RATE, 0.3, np.float32)), drops_per_block=1)
    with caplog.at_level(logging.WARNING):
        run_stream(_cfg(), src, _engine(), sink, language="uk")
    kinds = [e["status"] for e in sink.events]
    assert "lagging" in kinds
    assert kinds.count("lagging") <= 2, "one event per 5 s of audio, not per block"
    assert any("dropped" in r.message for r in caplog.records)


def test_sustained_lag_suggests_a_smaller_model():
    sink = _StatusSink()
    src = _DroppingSource(_blocks(np.full(12 * SAMPLE_RATE, 0.3, np.float32)), drops_per_block=1)
    run_stream(_cfg(), src, _engine(), sink, language="uk")
    slow = [e for e in sink.events if e["status"] == "slow"]
    assert len(slow) == 1 and "smaller model" in slow[0]["message"]


def test_overflow_is_reported():
    sink = _StatusSink()
    src = _DroppingSource(_blocks(np.full(2 * SAMPLE_RATE, 0.3, np.float32)), overflow_at=5)
    run_stream(_cfg(), src, _engine(), sink, language="uk")
    assert [e["status"] for e in sink.events].count("overflow") == 1


def test_long_silence_reports_idle_once():
    sink = _StatusSink()
    src = _DroppingSource(_blocks(np.zeros(25 * SAMPLE_RATE, np.float32)))
    run_stream(_cfg(), src, _engine(), sink, language="uk")
    assert [e["status"] for e in sink.events] == ["idle"]


def test_jsonl_writes_status_lines_and_tee_fans_them_out():
    buf = io.StringIO()
    j = JsonlSink()
    j._fh = buf
    tee = TeeSink(j, _StatusSink())
    tee.status({"status": "idle", "t": 12.0, "message": "no speech for 10 s"})
    assert json.loads(buf.getvalue()) == {"status": "idle", "t": 12.0,
                                          "message": "no speech for 10 s"}


def test_a_sink_without_status_is_left_alone():
    class Plain:
        def emit(self, seg):
            pass

        def close(self):
            pass

    src = _DroppingSource(_blocks(np.full(SAMPLE_RATE, 0.3, np.float32)), drops_per_block=1)
    run_stream(_cfg(), src, _engine(), Plain(), language="uk")  # must not raise
