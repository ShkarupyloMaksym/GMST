import numpy as np
import pytest

from gmst.audio.device_source import DeviceLost, DeviceSource, resolve_device
from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config

_FAKE_DEVICES = [
    {"name": "Built-in Microphone", "max_input_channels": 1},
    {"name": "BlackHole 2ch", "max_input_channels": 2},
    {"name": "Some Speakers", "max_input_channels": 0},
]


@pytest.fixture
def _patched_query(monkeypatch):
    monkeypatch.setattr("sounddevice.query_devices", lambda: _FAKE_DEVICES)


def test_resolve_device_passthrough_and_none():
    assert resolve_device(None) is None
    assert resolve_device(3) == 3
    assert resolve_device("2") == 2


def test_resolve_device_name_substring(_patched_query):
    assert resolve_device("blackhole") == 1
    assert resolve_device("microphone") == 0


def test_resolve_device_no_match(_patched_query):
    with pytest.raises(ValueError, match="no input device matching"):
        resolve_device("nonexistent")


def _src(**kw):
    return DeviceSource(Config(block_ms=100, max_buffer_seconds=0.3), in_rate=48_000, **kw)


def test_feed_resamples_and_downmixes_to_contract():
    src = _src()
    src.feed(np.zeros((4800, 2), dtype=np.float32))  # 100 ms stereo @ 48 kHz
    src.close()
    block = next(iter(src.blocks()))
    assert block.dtype == np.float32
    assert block.ndim == 1
    assert abs(len(block) - SAMPLE_RATE // 10) <= 2  # ~100 ms @ 16 kHz


def test_bounded_queue_drops_oldest():
    src = _src()  # maxsize = max(2, int(0.3 / 0.1)) = 3
    for i in range(5):  # each block carries its own level, so we can tell which survived
        src.feed(np.full((4800, 1), 0.1 * i, dtype=np.float32))
    assert src.stats.blocks_in == 5
    assert src.stats.blocks_dropped == 2
    assert src._q.qsize() == 3
    assert src.lagging is True
    # R4: with identical blocks this test passed for drop-*newest* too. The survivors must be the
    # three most recent (levels ~0.2, 0.3, 0.4; the resampler smears block edges a little).
    levels = [float(np.median(src._q.get_nowait())) for _ in range(3)]
    assert levels == sorted(levels) and levels[0] > 0.15 and levels[-1] > 0.35


def test_sample_counter_counts_all_captured_audio():
    src = _src()
    for _ in range(4):
        src.feed(np.zeros((4800, 1), dtype=np.float32))
    # 4 blocks * ~1600 samples @ 16 kHz ~= 0.4 s, dropped blocks included
    assert src.seconds_captured == pytest.approx(0.4, abs=0.01)


def test_blocks_drains_after_close():
    src = _src()
    src.feed(np.zeros((4800, 1), dtype=np.float32))
    src.feed(np.zeros((4800, 1), dtype=np.float32))
    src.close()
    assert len(list(src.blocks())) == 2


def test_unexpected_finish_raises():
    """An unplugged device must stop `blocks()` — but only after the captured tail is drained."""
    src = _src()
    src.feed(np.zeros((4800, 1), dtype=np.float32))
    src.feed(np.zeros((4800, 1), dtype=np.float32))
    src._on_finished()  # PortAudio stopped the stream on its own

    gen = src.blocks()
    drained = [next(gen), next(gen)]
    assert len(drained) == 2
    with pytest.raises(DeviceLost, match="device disconnected"):
        next(gen)


def test_explicit_close_does_not_raise_device_lost():
    src = _src()
    src.close()
    src._on_finished()  # the stop we asked for also fires the callback
    assert list(src.blocks()) == []
