import numpy as np
import pytest

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.segment.endpointer import Endpointer


class ScriptedVad:
    """Returns a fixed region list regardless of input."""

    def __init__(self, regions):
        self.regions = regions

    def speech_regions(self, audio):
        return list(self.regions)


def _block(seconds, val=0.2):
    return np.full(int(seconds * SAMPLE_RATE), val, dtype=np.float32)


def test_ready_to_decode_gate():
    ep = Endpointer(Config(min_chunk_seconds=0.5), ScriptedVad([]))
    ep.add(_block(0.3))
    assert ep.ready_to_decode() is False
    ep.add(_block(0.3))
    assert ep.ready_to_decode() is True
    ep.mark_decoded()
    assert ep.ready_to_decode() is False


def test_endpoint_when_trailing_silence_exceeds_min():
    cfg = Config(min_silence_ms=500, max_buffer_seconds=100)
    ep = Endpointer(cfg, ScriptedVad([(0.0, 1.0)]))  # speech ends at 1.0s
    ep.add(_block(2.0))                               # 2.0s buffer -> 1.0s trailing silence
    a = ep.assess()
    assert a.is_endpoint is True
    assert a.forced is False
    assert a.trailing_silence == 2.0 - 1.0


def test_forced_cut_on_max_buffer():
    cfg = Config(min_silence_ms=500, max_buffer_seconds=1.0)
    ep = Endpointer(cfg, ScriptedVad([(0.0, 1.2)]))  # no trailing silence
    ep.add(_block(1.5))
    a = ep.assess()
    assert a.is_endpoint is False
    assert a.forced is True


def test_trim_to_advances_t0_and_shrinks_buffer():
    ep = Endpointer(Config(), ScriptedVad([(0.0, 3.0)]))
    ep.add(_block(3.0))
    cut = ep.trim_to(2.0)                             # 0.2 s back-off -> drop 1.8 s
    assert cut == pytest.approx(1.8)
    assert ep.t0_seconds == pytest.approx(1.8)
    assert ep.buffer_seconds == pytest.approx(1.2)
    assert len(ep.buffer) == int(1.2 * SAMPLE_RATE)
    # absolute time is preserved: what was at 2.0 s is now at 0.2 s
    assert ep.t0_seconds + 0.2 == pytest.approx(2.0)


def test_trim_to_is_a_no_op_inside_the_back_off():
    ep = Endpointer(Config(), ScriptedVad([(0.0, 1.0)]))
    ep.add(_block(1.0))
    assert ep.trim_to(0.15) == 0.0                    # 0.15 - 0.2 < 0
    assert ep.t0_seconds == 0.0
    assert ep.buffer_seconds == pytest.approx(1.0)


def test_reset_advances_t0_and_keeps_overlap():
    cfg = Config(overlap_seconds=0.5)
    ep = Endpointer(cfg, ScriptedVad([(0.0, 2.0)]))
    ep.add(_block(2.0))
    ep.reset(keep_overlap=True)
    assert ep.t0_seconds == 1.5                       # 2.0 consumed - 0.5 kept
    assert abs(ep.buffer_seconds - 0.5) < 1e-6

    ep.add(_block(1.0))
    ep.reset(keep_overlap=False)
    assert abs(ep.t0_seconds - (1.5 + 1.5)) < 1e-6    # everything consumed
    assert ep.buffer_seconds == 0.0
