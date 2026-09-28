"""Batch pipeline: decode a whole file, transcribe, emit every segment as final.

Language pinned (``cfg.language``): one ``transcribe`` call over the whole file — the engine does
its own 30 s chunking.

Not pinned (PLAN.md "Review decisions", DECIDE-03): the file is split into speech regions by the
pipeline's VAD (``segment/vad.py``; regions closer than ``min_silence_ms`` are merged, each padded
by ``_REGION_PAD_S``), and each region is decoded **in the language detected on it**
(``Engine.detect_language``, restricted to ``lid_languages`` and sticky across regions) — the same
sentence-level code-switching the stream does. Until the 2026-09-28 review the engine decoded the
whole file in faster-whisper's single autodetected language and GMST's per-segment LID only
relabelled the result (R2 F3). Known limit: LID reads the first 30 s of a region, so a switch
inside one long unbroken region is not seen.

The returned ``BatchResult`` carries timing so ``gmst batch`` can print RTF.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from gmst.audio.file_source import decode_file
from gmst.audio.types import SAMPLE_RATE, AudioArray, duration_seconds
from gmst.config import Config
from gmst.glossary import make_glossary
from gmst.segment.vad import make_vad
from gmst.sink.base import Sink
from gmst.transcribe.engine import Engine
from gmst.transcribe.types import Segment, Word

_REGION_PAD_S = 0.2  # context kept around each speech region, so edges are not clipped


@dataclass(slots=True)
class BatchResult:
    audio_seconds: float
    transcribe_seconds: float
    n_segments: int

    @property
    def rtf(self) -> float:
        return self.transcribe_seconds / self.audio_seconds if self.audio_seconds else float("nan")


def speech_regions(audio: AudioArray, cfg: Config) -> list[tuple[int, int]]:
    """VAD regions as sample ranges, merged across gaps shorter than ``min_silence_ms`` and
    padded by ``_REGION_PAD_S`` (clamped to the file)."""
    gap = cfg.min_silence_ms / 1000
    merged: list[list[float]] = []
    for t0, t1 in make_vad(cfg).speech_regions(audio):
        if merged and t0 - merged[-1][1] < gap:
            merged[-1][1] = t1
        else:
            merged.append([t0, t1])
    n = len(audio)
    return [
        (max(0, int((t0 - _REGION_PAD_S) * SAMPLE_RATE)),
         min(n, int((t1 + _REGION_PAD_S) * SAMPLE_RATE)))
        for t0, t1 in merged
    ]


def transcribe_by_region(audio: AudioArray, cfg: Config, engine: Engine) -> list[Segment]:
    """Decode ``audio`` as batch does: whole-file when the language is pinned, otherwise each
    speech region in its own detected language. Segment times are file-relative."""
    glossary = make_glossary(cfg)

    def decode(clip, lang):
        if not glossary:  # DECIDE-08: terms as prompt + hotwords only when there are any
            return engine.transcribe(clip, language=lang)
        segs = engine.transcribe(clip, language=lang, prompt=glossary.prompt(None, max_chars=600),
                                 hotwords=glossary.hotwords())
        for s in segs:
            glossary.observe(s.text, lang=lang)
        return segs

    try:
        if cfg.language is not None:
            return decode(audio, cfg.language)
        return _by_region(audio, cfg, engine, decode)
    finally:
        glossary.save()


def _by_region(audio: AudioArray, cfg: Config, engine: Engine, decode) -> list[Segment]:
    out: list[Segment] = []
    prev_lang: str | None = None
    for a, b in speech_regions(audio, cfg):
        lang, prob = engine.detect_language(audio[a:b], prev_lang=prev_lang)
        off = a / SAMPLE_RATE
        for s in decode(audio[a:b], lang):
            out.append(Segment(
                s.start + off, s.end + off, s.text, lang, s.is_final, prob, s.turn,
                [Word(w.text, w.start + off, w.end + off) for w in s.words],
            ))
        prev_lang = lang
    return out


def run_batch(path: str | Path, cfg: Config, engine: Engine, sink: Sink) -> BatchResult:
    audio = decode_file(path)
    started = time.monotonic()
    segments = transcribe_by_region(audio, cfg, engine)
    elapsed = time.monotonic() - started

    for seg in segments:
        seg.is_final = True
        sink.emit(seg)
    sink.close()

    return BatchResult(duration_seconds(audio), elapsed, len(segments))
