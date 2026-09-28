"""Probe: does test_bounded_queue_drops_oldest actually verify which blocks survive?

Feeds distinguishable blocks (value = index) past the queue's maxsize and reads back what
survives, against the *real* (unmutated) device_source.py. Run from repo root with `uv run python`.
"""
import numpy as np

from gmst.audio.device_source import DeviceSource
from gmst.config import Config


def _src():
    return DeviceSource(Config(block_ms=100, max_buffer_seconds=0.3), in_rate=48_000)


src = _src()  # maxsize = 3
for i in range(5):
    src.feed(np.full((4800, 1), i / 10, dtype=np.float32))

survivors = []
while True:
    try:
        b = src._q.get_nowait()
    except Exception:
        break
    survivors.append(round(float(b[0]), 2))

print("blocks_in:", src.stats.blocks_in, "blocks_dropped:", src.stats.blocks_dropped)
print("surviving block marks (real drop-oldest code):", survivors)
print("expected under correct drop-oldest: [0.2, 0.3, 0.4] (the 3 most recent)")
print("would ALSO be [0.0, 0.1, 0.2] under a drop-NEWEST bug -- same blocks_in/blocks_dropped/qsize")
