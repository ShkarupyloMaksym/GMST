"""R3 probe: does the `[lagging]` flag PLAN.md promises ever reach a `gmst stream` sink?

PLAN.md "Failure modes & degradation" row "Bounded queues":
    on full, drop oldest audio and set a `[lagging]` flag the sink renders

This drives `run_stream` with a source whose `.lagging` is True and `.stats.blocks_dropped > 0`
(exactly what `DeviceSource` sets when the audio_queue drops a block — see
`test_device_source.py::test_bounded_queue_drops_oldest`), a real `ConsoleSink` writing to a
StringIO-like file, and an inspection of `run_stream`'s source to show it never reads
`source.lagging` or `source.stats` at all.

Run: uv run python review/checkpoint-1/scripts/R3/lagging_probe.py
"""

import inspect
import io
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

import numpy as np

from gmst.config import Config
from gmst.pipeline.stream import run_stream
from gmst.sink.console import ConsoleSink
from gmst.transcribe.types import Segment, Word

from fakes import FakeEngine  # tests/fakes.py


@dataclass
class LaggingCaptureStats:
    blocks_in: int = 10
    blocks_dropped: int = 7
    overflows: int = 0
    status_flags: int = 0


class LaggingSource:
    """Mimics DeviceSource after the bounded queue dropped several blocks mid-session."""

    def __init__(self, blocks):
        self._blocks = list(blocks)
        self.lagging = True  # DeviceSource.lagging is True whenever blocks_dropped > 0
        self.stats = LaggingCaptureStats()

    def blocks(self):
        yield from self._blocks

    def close(self):
        pass


def make_word_block(text, n=1600):
    return np.zeros(n, dtype=np.float32)


def main():
    # 1. static check: does run_stream's source code even reference lagging/stats anywhere?
    src_text = inspect.getsource(run_stream)
    mentions_lagging = "lagging" in src_text
    mentions_stats = ".stats" in src_text
    print(f"run_stream source mentions 'lagging': {mentions_lagging}")
    print(f"run_stream source mentions '.stats': {mentions_stats}")

    # 2. dynamic check: run the real pipeline with a source that IS lagging, capture what the
    #    sink actually receives.
    cfg = Config(max_unconfirmed_seconds=100, overlap_seconds=0.5)
    engine = FakeEngine(
        [[Segment(0.0, 1.0, "hello world", "en", True, 1.0, 1, [
            Word("hello", 0.0, 0.5), Word("world", 0.5, 1.0),
        ])]],
        lang="en",
    )
    buf = io.StringIO()
    sink = ConsoleSink(path=None)
    sink._fh = buf  # redirect from stdout
    sink._tty = False

    source = LaggingSource([make_word_block("x") for _ in range(20)])
    stats = run_stream(cfg, source, engine, sink, language="en")

    out = buf.getvalue()
    print(f"\nsource.lagging = {source.lagging}, blocks_dropped = {source.stats.blocks_dropped}")
    print(f"stream stats: utterances={stats.utterances} decodes={stats.decodes}")
    print("sink output:")
    print(out)
    print(f"'lagging' appears in sink output: {'lagging' in out.lower()}")


if __name__ == "__main__":
    main()
