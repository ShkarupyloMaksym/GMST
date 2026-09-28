"""R3 probe: is sink.close() unconditional when the final (shutdown) decode raises?

PLAN.md "Failure modes & degradation", "Engine raises mid-meeting":
    run_stream's shutdown flush is nested so sink.close() is unconditional — SrtSink only writes
    its file there, and one engine failure must not cost the whole transcript.

Drives run_stream with an engine whose transcribe() raises on every call (including the shutdown
flush's last decode), and a sink that records whether close() was called.

Run: uv run python review/checkpoint-1/scripts/R3/sink_close_on_raise_probe.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))

import numpy as np

from gmst.config import Config
from gmst.pipeline.stream import run_stream

from fakes import ListSource


class RaisingEngine:
    """Raises on the FIRST transcribe call — forces the raise to happen in the main decode
    loop (mid-meeting), not only in the shutdown flush, so we can see whether the original
    exception still propagates out of run_stream as PLAN.md claims."""

    def __init__(self):
        self.calls = 0

    def detect_language(self, audio, *, prev_lang=None):
        return "en", 0.99

    def transcribe(self, audio, *, language=None, prompt=None):
        self.calls += 1
        raise RuntimeError(f"engine exploded on call {self.calls}")


class RecordingSink:
    def __init__(self):
        self.closed = False
        self.emitted = []

    def emit(self, seg):
        self.emitted.append(seg)

    def close(self):
        self.closed = True


def main():
    cfg = Config(
        max_unconfirmed_seconds=100, overlap_seconds=0.5,
        vad_backend="energy", min_chunk_seconds=0.2,
    )
    engine = RaisingEngine()
    sink = RecordingSink()
    # loud, deterministic "speech" blocks well above the energy VAD threshold (0.02 RMS default)
    # so the main decode loop calls engine.transcribe() before any shutdown flush.
    blocks = [np.full(1600, 0.5, dtype=np.float32) for _ in range(20)]
    source = ListSource(blocks)

    try:
        run_stream(cfg, source, engine, sink, language="en")
    except Exception as exc:
        print(f"run_stream raised out of the pipeline: {exc!r}")
    else:
        print("run_stream returned normally")

    print(f"sink.closed = {sink.closed}")
    print(f"engine.calls = {engine.calls}")


if __name__ == "__main__":
    main()
