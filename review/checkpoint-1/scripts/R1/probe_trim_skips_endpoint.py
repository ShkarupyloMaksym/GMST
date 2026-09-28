"""R1 probe: when a commit trims the buffer down to "sliver + silence", does the endpoint (and the
per-utterance LID re-detection it triggers) still happen?

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R1/probe_trim_skips_endpoint.py

The endpoint needs `has_speech(regions)` (`src/gmst/segment/endpointer.py:76`), and the
`not a.regions` branch in `src/gmst/pipeline/stream.py:131-134` just `continue`s. After a trim the
buffer holds 0.2 s of the last committed word plus trailing silence. Two VADs:

  energy        - the shipped energy gate (30 ms frames): calls the sliver speech
  min_speech    - the same gate but ignoring regions < 0.25 s, i.e. a VAD that does not call a
                  0.2 s trailing-phoneme sliver speech (the realistic case for Silero on the tail
                  of a word is unverified here; this variant isolates the code path)

Engine: faithful audio-reactive (the sliver decodes to the full word, so the F1 contradiction path
is NOT involved). `detect_language` is audio-reactive too: "uk" when the buffer's loudest mark is
>= 0.30, else "en". Utterance 1 is en (marks 0.10..0.21), utterance 2 is uk (marks 0.35..0.46).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import gmst.pipeline.stream as stream_mod  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.segment.vad import EnergyVad  # noqa: E402
from gmst.transcribe.types import Segment, Word  # noqa: E402
from tests.fakes import FakeEngine, ListSource  # noqa: E402

N = SAMPLE_RATE // 2


def marked(idx):
    return np.concatenate([np.full(N, 0.1 + 0.01 * i, dtype=np.float32) for i in idx])


class MarkedEngine(FakeEngine):
    def __init__(self):
        super().__init__([[]])
        self.lid_calls = []

    def detect_language(self, audio, *, prev_lang=None):
        lang = "uk" if float(np.max(audio)) >= 0.30 - 1e-6 else "en"
        self.lid_calls.append(lang)
        return lang, 0.99

    def transcribe(self, audio, *, language=None, prompt=None):
        self.calls.append({"samples": len(audio), "language": language})
        vals = np.asarray(audio)
        edges = np.flatnonzero(np.diff(vals)) + 1
        starts = np.concatenate(([0], edges))
        ends = np.concatenate((edges, [len(vals)]))
        words = [Word(f"w{int(round((float(vals[s]) - 0.1) * 100))}", s / SAMPLE_RATE,
                      e / SAMPLE_RATE) for s, e in zip(starts, ends) if vals[s] != 0.0]
        if not words:
            return []
        return [Segment(words[0].start, words[-1].end, " ".join(w.text for w in words),
                        language or "", words=words)]


class MinSpeechVad(EnergyVad):
    def speech_regions(self, audio):
        return [(a, b) for a, b in super().speech_regions(audio) if b - a >= 0.25]


class Sink:
    def __init__(self):
        self.segs = []

    def emit(self, s):
        self.segs.append(s)

    def close(self):
        pass


def main():
    cfg = Config(vad_backend="energy", vad_threshold=0.05)
    audio = np.concatenate([marked(range(0, 12)), np.zeros(2 * SAMPLE_RATE, np.float32),
                            marked(range(25, 37)), np.zeros(2 * SAMPLE_RATE, np.float32)])
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    for name, vad in (("energy", EnergyVad(0.05)), ("min_speech", MinSpeechVad(0.05))):
        stream_mod.make_vad = lambda _cfg, v=vad: v
        eng = MarkedEngine()
        sink = Sink()
        stats = stream_mod.run_stream(cfg, ListSource(blocks), eng, sink, language=None)
        finals = [s for s in sink.segs if s.is_final]
        by_lang = {}
        for s in finals:
            by_lang.setdefault(s.language, []).extend(s.text.split())
        print(f"[{name}] utterances={stats.utterances} detect_language calls={eng.lid_calls} "
              f"biggest_decode={max(c['samples'] for c in eng.calls) / SAMPLE_RATE:.1f}s")
        for lang, ws in by_lang.items():
            print(f"   final words labelled {lang!r}: {' '.join(ws)}")


if __name__ == "__main__":
    main()
