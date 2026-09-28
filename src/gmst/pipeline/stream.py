"""Streaming pipeline: device blocks -> endpointer -> per-utterance LID -> engine ->
LocalAgreement-2 -> sink.

Loop per decode (buffer has >= ``min_chunk_seconds`` new audio and contains speech):
1. detect the utterance's language once (unless pinned), sticky vs the previous utterance
2. transcribe the whole buffer, prompted with the tail of the committed text (<= ~600 characters)
3. push the hypothesis' words through LocalAgreement-2 → emit newly-agreed words as **final**,
   the unconfirmed tail as a **partial**; spans use per-word timestamps when the engine provides
   them, else an even split of the segment span
4. after a commit, ``ep.trim_to`` drops the committed audio (with a small back-off) and
   ``agree.rebase`` re-anchors on what survived, so the re-decoded buffer stays short
5. on an endpoint / forced cut / stalled tail: ``flush()`` the reconciler (commit the rest),
   reset the endpointer, re-detect language next utterance

Clock: every decision here is on the **audio** clock (``ep.t0_seconds + ep.buffer_seconds``), never
``time.monotonic()``, so a source that does not run at 1x real time behaves identically.

Turn tracking: every committed span's absolute times feed ``TurnTracker``; a pause longer than
``turn_gap_seconds`` bumps ``Segment.turn``.

Graceful shutdown: when the source stops (Ctrl-C calls ``source.close()``, which drains its queue),
the ``finally`` block decodes whatever is left in the buffer and commits it. ``sink.close()`` is
unconditional — a failing engine must never cost us the transcript written on close.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.reconcile import LocalAgreement
from gmst.segment.endpointer import Endpointer
from gmst.segment.turns import TurnTracker
from gmst.segment.vad import make_vad
from gmst.sink.base import Sink
from gmst.transcribe.engine import Engine
from gmst.transcribe.types import Segment, Word

_PROMPT_CHARS = 600  # ~200 Whisper tokens for both en and uk; the window is 224
_PROMPT_WORDS = 100  # words scanned before the character cap does the real trimming
_MAX_COMMITTED = 4000  # the session's committed word list is bounded (2 h+ meetings)
_MIN_FLUSH_SAMPLES = SAMPLE_RATE // 5  # 0.2 s — below this, nothing worth a final decode
_MAX_STALLED_PUSHES = 3  # PLAN.md: forced commit after "N updates without progress"


@dataclass(slots=True)
class StreamStats:
    """``utterances`` counts real endpoints (a pause the VAD called a boundary) plus the shutdown
    flush — **not** forced cuts or stalls, which split one utterance rather than ending it."""

    utterances: int = 0
    decodes: int = 0
    committed_words: int = 0


def _words_of(segs: list[Segment]) -> list[Word]:
    """Flatten segments to a word list, synthesising even spacing when there are no word times."""
    out: list[Word] = []
    for s in segs:
        if s.words:
            out.extend(Word(w.text, w.start, w.end) for w in s.words if w.text)
            continue
        toks = s.text.split()
        if not toks:
            continue
        step = (s.end - s.start) / len(toks)
        for i, t in enumerate(toks):
            out.append(Word(t, s.start + i * step, s.start + (i + 1) * step))
    return out


def run_stream(
    cfg: Config,
    source,
    engine: Engine,
    sink: Sink,
    *,
    language: str | None = None,
) -> StreamStats:
    vad = make_vad(cfg)
    ep = Endpointer(cfg, vad)
    agree = LocalAgreement()
    turns = TurnTracker(cfg.turn_gap_seconds)
    stats = StreamStats()

    committed: list[str] = []
    prev_lang = language
    utt_lang: str | None = language
    last_commit_seconds = 0.0  # audio-time of the last commit, on the sample clock
    last_pending: list[Word] = []

    def emit(words: list[Word], *, final: bool, lang: str) -> None:
        if not words:
            return
        t0 = ep.t0_seconds + words[0].start
        t1 = ep.t0_seconds + words[-1].end
        turn = turns.update(t0, t1) if final else turns.turn
        abs_words = [Word(w.text, ep.t0_seconds + w.start, ep.t0_seconds + w.end) for w in words]
        sink.emit(
            Segment(t0, t1, " ".join(w.text for w in words), lang or "",
                    is_final=final, turn=turn, words=abs_words)
        )

    def commit(words: list[str]) -> None:
        committed.extend(words)
        stats.committed_words += len(words)
        if len(committed) > _MAX_COMMITTED:
            del committed[:-_MAX_COMMITTED]

    def decode(audio) -> tuple[list[Word], str]:
        """Transcribe ``audio`` and report the language it was actually decoded as."""
        nonlocal utt_lang
        if language is None and utt_lang is None:
            utt_lang, _ = engine.detect_language(audio, prev_lang=prev_lang)
        call_lang = language or utt_lang or "en"
        prompt = " ".join(committed[-_PROMPT_WORDS:])[-_PROMPT_CHARS:] or None
        segs = engine.transcribe(audio, language=call_lang, prompt=prompt)
        stats.decodes += 1
        return _words_of(segs), call_lang

    abandoned = False
    try:
        for block in source.blocks():
            ep.add(block)
            if not ep.ready_to_decode():
                continue
            ep.mark_decoded()

            a = ep.assess()
            if not a.regions:
                if a.forced:  # silence-only buffer that grew too big — drop it
                    ep.reset(keep_overlap=False)
                continue

            hyp, call_lang = decode(ep.buffer)
            newly, _pending = agree.push([w.text for w in hyp])
            o = agree.last_offset
            new_words = hyp[o : o + len(newly)]
            last_pending = hyp[o + len(newly) :]

            audio_now = ep.t0_seconds + ep.buffer_seconds
            if newly:
                commit(newly)
                last_commit_seconds = audio_now
                emit(new_words, final=True, lang=call_lang)
            emit(last_pending, final=False, lang=call_lang)

            # "stalled" means an unconfirmed tail that will not agree — with nothing pending
            # there is nothing to force-commit, and cutting would only churn the utterance.
            stalled = bool(last_pending) and (
                audio_now - last_commit_seconds >= cfg.max_unconfirmed_seconds
                or agree.stalled_pushes >= _MAX_STALLED_PUSHES
            )
            if a.is_endpoint or a.forced or stalled:
                rest = agree.flush()
                if rest:
                    commit(rest)
                    emit(last_pending, final=True, lang=call_lang)
                # Keep the seam audio only when we can keep an anchor for it too: it gets
                # transcribed again, and without the anchor those words are committed twice
                # with times that run backwards. A contradicting hypothesis has no usable
                # anchor at all, so that path restarts clean.
                keep_overlap = not a.is_endpoint and not agree.contradicted
                if keep_overlap:
                    cut = max(0.0, ep.buffer_seconds - cfg.overlap_seconds)
                    done = o + len(newly) + len(rest)
                    agree.rebase(
                        [w.text for w in hyp[:done] if w.end > cut],
                        [w.text for w in hyp[done:] if w.end > cut],
                    )
                else:
                    agree.reset()
                prev_lang = utt_lang or prev_lang
                utt_lang = language
                ep.reset(keep_overlap=keep_overlap)
                last_pending = []
                if a.is_endpoint:  # a forced cut / stall is not a new utterance
                    stats.utterances += 1
                last_commit_seconds = ep.t0_seconds + ep.buffer_seconds
            elif new_words:
                # committed audio has served its purpose; drop it so the next decode is short
                cut = ep.trim_to(new_words[-1].end)
                if cut > 0:
                    done = o + len(newly)
                    agree.rebase(
                        [w.text for w in hyp[:done] if w.end > cut],
                        [w.text for w in hyp[done:]],
                    )
                    last_pending = []  # its spans are relative to the pre-trim buffer
    except KeyboardInterrupt:
        # the second Ctrl-C / SIGTERM: the user asked not to wait for the final decode
        abandoned = True
        raise
    finally:
        try:
            tail = ep.buffer
            if not abandoned and len(tail) >= _MIN_FLUSH_SAMPLES and ep.assess().regions:
                hyp, call_lang = decode(tail)
                # last decode of the session — commit the whole tail, never drop it, skipping
                # only a prefix that repeats what is already committed.
                start = agree.absorb([w.text for w in hyp])
                final_words = hyp[start:]
                if final_words:
                    stats.committed_words += len(final_words)
                    stats.utterances += 1
                    emit(final_words, final=True, lang=call_lang)
        except Exception:  # noqa: BLE001 - never lose the sink because the final flush failed
            logging.getLogger(__name__).exception("final flush failed; closing sink anyway")
        finally:
            sink.close()

    return stats
