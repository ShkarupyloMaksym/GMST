"""R1 probe: the per-commit trim cuts *inside* the last committed word; what happens when the
engine does what a real model does with the leftover sliver?

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R1/probe_trim_fragment.py

Audio is built like tests/test_stream_pipeline.py::_marked (every 0.5 s chunk carries its own
amplitude = its own word), followed by silence so a real endpoint fires. The engine reads words
back from the audio it is handed (audio-reactive, like _marked_engine), with one twist per variant
for a word whose audio is *cut short at the head of the buffer* (the 0.2 s back-off sliver):

  faithful  - sliver still decodes to the full word (what _marked_engine does; the tests' assumption)
  fragment  - sliver decodes to a fragment token ("w30" -> "p30"), as a real model would for the
              last 0.2 s of a 0.5 s word
  dropped   - sliver decodes to nothing (the model ignores 0.2 s of a trailing phoneme)

Config is the shipped default for everything that matters here (min_chunk 1.0, min_silence 600,
max_buffer 15, max_unconfirmed 8, overlap 0.5), with the energy VAD so no model is loaded.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for tests.fakes

import numpy as np

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.pipeline.stream import run_stream
from gmst.transcribe.types import Segment, Word
from tests.fakes import FakeEngine, ListSource

CHUNK = 0.5
CHUNK_N = int(CHUNK * SAMPLE_RATE)


def marked(indices):
    return np.concatenate(
        [np.full(CHUNK_N, 0.1 + 0.01 * i, dtype=np.float32) for i in indices]
    )


def silence(sec):
    return np.zeros(int(sec * SAMPLE_RATE), dtype=np.float32)


def name(v):
    return f"w{int(round((float(v) - 0.1) * 100))}"


def engine(variant):
    def script(audio, _i):
        vals = np.asarray(audio)
        if len(vals) == 0:
            return []
        edges = np.flatnonzero(np.diff(vals)) + 1
        starts = np.concatenate(([0], edges))
        ends = np.concatenate((edges, [len(vals)]))
        words = []
        for s, e in zip(starts, ends, strict=True):
            if vals[s] == 0.0:
                continue  # silence -> no word
            tok = name(vals[s])
            if s == 0 and (e - s) < CHUNK_N - 1:  # a word cut short at the buffer head
                if variant == "fragment":
                    tok = "p" + tok[1:]  # a different token: "w30" -> "p30"
                elif variant == "dropped":
                    continue
            words.append(Word(tok, s / SAMPLE_RATE, e / SAMPLE_RATE))
        if not words:
            return []
        return [Segment(words[0].start, words[-1].end, " ".join(w.text for w in words), "en",
                        words=words)]

    return FakeEngine(script)


class RecSink:
    def __init__(self):
        self.segs = []

    def emit(self, seg):
        self.segs.append(seg)

    def close(self):
        pass


def main():
    cfg = Config(vad_backend="energy", vad_threshold=0.05)  # every other field at its default
    print("cfg:", {k: getattr(cfg, k) for k in (
        "min_chunk_seconds", "min_silence_ms", "max_buffer_seconds", "max_unconfirmed_seconds",
        "overlap_seconds")})
    utt1, utt2 = list(range(0, 12)), list(range(20, 32))  # two 6 s utterances
    audio = np.concatenate([marked(utt1), silence(1.5), marked(utt2), silence(1.5)])
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    expected = [f"w{i}" for i in utt1 + utt2]
    for variant in ("faithful", "fragment", "dropped"):
        sink = RecSink()
        eng = engine(variant)
        stats = run_stream(cfg, ListSource(blocks), eng, sink, language="en")
        finals = " ".join(s.text for s in sink.segs if s.is_final).split()
        clean = ["w" + w[1:] if w.startswith("p") else w for w in finals]
        lost = [w for w in expected if w not in clean]
        dup = sorted({w for w in clean if clean.count(w) > 1})
        biggest = max(c["samples"] for c in eng.calls) / SAMPLE_RATE
        print(f"\n[{variant}] decodes={stats.decodes} committed={stats.committed_words} "
              f"biggest_decode={biggest:.1f}s")
        print("  finals:", " ".join(finals))
        print(f"  lost {len(lost)}/{len(expected)}: {' '.join(lost)}")
        print(f"  duplicated: {dup}")


if __name__ == "__main__":
    main()
