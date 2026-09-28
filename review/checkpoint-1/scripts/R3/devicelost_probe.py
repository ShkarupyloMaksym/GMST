"""R3 probe: does DeviceLost propagate out of run_stream AFTER the shutdown flush runs, so
`_cmd_stream` can still exit 3 while not losing the last utterance?

PLAN.md: "Input device disconnects mid-call | `finished_callback` -> `DeviceSource.blocks()`
drains what was captured, then raises `DeviceLost`; the shutdown flush still runs, `gmst stream`
logs and exits 3"

Run: uv run python review/checkpoint-1/scripts/R3/devicelost_probe.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

import numpy as np

from gmst.audio.device_source import DeviceLost
from gmst.config import Config
from gmst.pipeline.stream import run_stream
from gmst.transcribe.types import Segment, Word


class DisconnectingSource:
    """Like DeviceSource.blocks(): drains captured blocks, THEN raises DeviceLost."""

    def __init__(self, blocks):
        self._blocks = list(blocks)

    def blocks(self):
        yield from self._blocks
        raise DeviceLost("input stream stopped unexpectedly (device disconnected?)")

    def close(self):
        pass


class RecordingSink:
    def __init__(self):
        self.closed = False
        self.emitted = []

    def emit(self, seg):
        self.emitted.append(seg)

    def close(self):
        self.closed = True


class OneShotEngine:
    def detect_language(self, audio, *, prev_lang=None):
        return "en", 0.99

    def transcribe(self, audio, *, language=None, prompt=None):
        return [Segment(0.0, 1.0, "final words", "en", True, 1.0, 1,
                         [Word("final", 0.0, 0.5), Word("words", 0.5, 1.0)])]


def main():
    cfg = Config(vad_backend="energy", min_chunk_seconds=100.0)  # never decode in the main loop
    blocks = [np.full(1600, 0.5, dtype=np.float32) for _ in range(3)]
    source = DisconnectingSource(blocks)
    sink = RecordingSink()
    engine = OneShotEngine()

    try:
        run_stream(cfg, source, engine, sink, language="en")
        print("run_stream returned normally (NO EXCEPTION) -- unexpected")
    except DeviceLost as exc:
        print(f"DeviceLost propagated out of run_stream: {exc}")
    print(f"sink.closed = {sink.closed}")
    print(f"segments emitted by shutdown flush = {[s.text for s in sink.emitted]}")


if __name__ == "__main__":
    main()
