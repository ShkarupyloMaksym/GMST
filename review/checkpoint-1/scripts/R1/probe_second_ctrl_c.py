"""R1 probe: where does the second Ctrl-C land, and does it really abandon the final decode?

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R1/probe_second_ctrl_c.py

`gmst stream`'s SIGINT handler (src/gmst/cli.py:171-178) raises KeyboardInterrupt on the second
Ctrl-C and resets SIGINT to SIG_DFL. After the first Ctrl-C the loop is still draining the queue
(up to max_buffer_seconds of audio), so the second one can land inside an *in-loop* decode. We
model that by an audio-reactive engine that raises KeyboardInterrupt from the Nth transcribe call
(exactly what the handler does when the signal arrives during that call), and record every call
made afterwards.

Part 2 shows what SIG_DFL means for a third Ctrl-C during that final decode: the process dies
without running `finally`, i.e. without `sink.close()`.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.pipeline.stream import run_stream  # noqa: E402
from gmst.transcribe.types import Segment, Word  # noqa: E402
from tests.fakes import FakeEngine, ListSource  # noqa: E402


def marked(n):
    return np.concatenate(
        [np.full(SAMPLE_RATE // 2, 0.1 + 0.01 * i, dtype=np.float32) for i in range(n)]
    )


class InterruptingEngine(FakeEngine):
    def __init__(self, at):
        super().__init__([[]])
        self.at = at
        self.after = []

    def transcribe(self, audio, *, language=None, prompt=None):
        idx = len(self.calls)
        self.calls.append({"samples": len(audio)})
        if idx == self.at:
            raise KeyboardInterrupt  # the second Ctrl-C, landing inside an in-loop decode
        if idx > self.at:
            self.after.append(len(audio) / SAMPLE_RATE)
        vals = np.asarray(audio)
        edges = np.flatnonzero(np.diff(vals)) + 1
        starts = np.concatenate(([0], edges))
        ends = np.concatenate((edges, [len(vals)]))
        words = [Word(f"w{s}", s / SAMPLE_RATE, e / SAMPLE_RATE) for s, e in zip(starts, ends)]
        return [Segment(0.0, len(vals) / SAMPLE_RATE, " ".join(w.text for w in words), "en",
                        words=words)]


class Sink:
    closed = False

    def emit(self, seg):
        pass

    def close(self):
        self.closed = True


def part1():
    audio = marked(20)
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    eng = InterruptingEngine(at=3)
    sink = Sink()
    try:
        run_stream(Config(vad_backend="energy", vad_threshold=0.05), ListSource(blocks), eng, sink,
                   language="en")
    except KeyboardInterrupt:
        print("part1: KeyboardInterrupt propagated out of run_stream")
    print(f"part1: transcribe calls after the interrupt: {len(eng.after)} "
          f"(buffer seconds each: {eng.after}); sink.closed={sink.closed}")


def part2():
    code = textwrap.dedent(
        """
        import signal, time, sys
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # what cli.py:174 leaves installed
        try:
            print("decoding", flush=True)
            time.sleep(5)   # the final decode
        finally:
            open(sys.argv[1], "w").write("closed")   # stands in for sink.close()
        """
    )
    marker = ROOT / "review/checkpoint-1/scripts/R1/_sigdfl_marker.tmp"
    marker.unlink(missing_ok=True)
    p = subprocess.Popen([sys.executable, "-c", code, str(marker)], stdout=subprocess.PIPE)
    p.stdout.readline()
    os.kill(p.pid, signal.SIGINT)
    rc = p.wait()
    print(f"part2: returncode={rc}; finally ran (sink.close stand-in)={marker.exists()}")
    marker.unlink(missing_ok=True)


if __name__ == "__main__":
    part1()
    part2()
