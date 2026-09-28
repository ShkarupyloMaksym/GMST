"""Streaming pipeline: device blocks -> endpointer -> per-utterance LID -> engine ->
LocalAgreement-2 -> sink.

Loop per decode (buffer has >= ``min_chunk_seconds`` new audio and contains speech):
1. detect the utterance's language (unless pinned), sticky vs the previous utterance — on every
   decode until the buffer holds ``lid_settle_seconds`` (3 s) of audio, then fixed for the rest of
   the utterance. Until it settles nothing is committed, only shown as a partial (DECIDE-04: an
   utterance that opens with an English term must not be committed as English; X.2 measured
   restricted LID >= 95 % at 3 s, 88-90 % on Ukrainian at 2 s). An utterance that ends first
   commits with its last detection.
2. transcribe the whole buffer, prompted with the glossary terms and the tail of the committed text
   (<= 560 characters)
3. push the hypothesis' words through LocalAgreement-2 → emit newly-agreed words as **final**,
   the unconfirmed tail as a **partial**; spans use per-word timestamps when the engine provides
   them, else an even split of the segment span
4. after a commit, ``ep.trim_to`` drops the audio before the last committed word (with a small
   back-off, so that word survives whole) and ``agree.rebase`` re-anchors on what survived, with
   word times, so the re-decoded buffer stays short
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
from gmst.glossary import make_glossary
from gmst.reconcile import LocalAgreement
from gmst.segment.endpointer import Endpointer
from gmst.segment.turns import TurnTracker
from gmst.segment.vad import make_vad
from gmst.sink.base import Sink
from gmst.transcribe.engine import Engine
from gmst.transcribe.types import Segment, Word

# faster-whisper keeps the last 223 prompt tokens. Ukrainian runs ~0.39 tokens/char (R1: 600
# chars = 235 tokens), so 560 chars stays inside the window; English is bound first by
# _PROMPT_WORDS (100 words ~ 126 tokens). Glossary terms (DECIDE-08) share this cap, first.
_PROMPT_CHARS = 560
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


_LAG_REPORT_EVERY_S = 5.0  # at most one "lagging" / "overflow" event per this much audio
_SLOW_AFTER_S = 10.0  # PLAN.md: dropping sustained this long -> suggest a smaller model
_IDLE_AFTER_S = 10.0  # no speech this long -> one "idle" event per silent stretch


class _StatusMonitor:
    """Runtime status for the user (PLAN.md "Review decisions", DECIDE-05; R3): dropped audio,
    PortAudio overflows, a sustained lag, and long silence. Each becomes a ``logging`` warning
    (stderr) and a ``{"status", "t", "message", ...}`` event for a sink that has ``status()``.
    Rate-limited, and timed on the audio clock like everything else here."""

    def __init__(self, source, sink) -> None:
        self._stats = getattr(source, "stats", None)
        self._send = getattr(sink, "status", None)
        self._log = logging.getLogger("gmst.stream")
        self._dropped = self._overflows = 0
        self._last_lag_event = self._last_ovf_event = -1e9
        self._lag_since: float | None = None
        self._last_drop = -1e9
        self._slow_sent = False
        self._last_speech = 0.0
        self._idle_sent = False

    def _event(self, kind: str, t: float, message: str, **detail) -> None:
        self._log.warning("%s at %.1f s: %s", kind, t, message)
        if self._send is not None:
            self._send({"status": kind, "t": round(t, 3), "message": message, **detail})

    def tick(self, now: float) -> None:
        if self._stats is None:
            return
        dropped = int(getattr(self._stats, "blocks_dropped", 0))
        if dropped > self._dropped:
            if self._lag_since is None or now - self._last_drop > _SLOW_AFTER_S:
                self._lag_since, self._slow_sent = now, False  # a new lagging episode
            self._last_drop = now
            if now - self._last_lag_event >= _LAG_REPORT_EVERY_S:
                self._event("lagging", now, f"{dropped} audio blocks dropped so far — the engine "
                            "is behind real time", dropped=dropped)
                self._last_lag_event = now
            if not self._slow_sent and now - self._lag_since >= _SLOW_AFTER_S:
                self._event("slow", now, f"audio dropped for {now - self._lag_since:.0f} s — try "
                            "a smaller model (model_size) or a pinned --language", dropped=dropped)
                self._slow_sent = True
            self._dropped = dropped
        overflows = int(getattr(self._stats, "overflows", 0))
        if overflows > self._overflows:
            if now - self._last_ovf_event >= _LAG_REPORT_EVERY_S:
                self._event("overflow", now, f"{overflows} PortAudio input overflows",
                            overflows=overflows)
                self._last_ovf_event = now
            self._overflows = overflows

    def speech(self, now: float, heard: bool) -> None:
        if heard:
            self._last_speech, self._idle_sent = now, False
        elif not self._idle_sent and now - self._last_speech >= _IDLE_AFTER_S:
            self._event("idle", now, f"no speech for {now - self._last_speech:.0f} s — "
                        "still listening")
            self._idle_sent = True


def _spans(words: list[Word], shift: float = 0.0) -> list[tuple[float, float]]:
    return [(w.start - shift, w.end - shift) for w in words]


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
    glossary = make_glossary(cfg)
    monitor = _StatusMonitor(source, sink)
    stats = StreamStats()

    committed: list[str] = []
    prev_lang = language
    utt_lang: str | None = language
    settled = language is not None  # pinned: nothing to settle
    last_commit_seconds = 0.0  # audio-time of the last commit, on the sample clock
    last_pending: list[Word] = []

    def emit(words: list[Word], *, final: bool, lang: str) -> None:
        if not words:
            return
        t0 = ep.t0_seconds + words[0].start
        t1 = ep.t0_seconds + words[-1].end
        turn = turns.update(t0, t1) if final else turns.turn
        if final:
            glossary.observe(" ".join(w.text for w in words), lang=lang)
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
        nonlocal utt_lang, settled
        if not settled:
            utt_lang, _ = engine.detect_language(audio, prev_lang=prev_lang)
            settled = len(audio) >= cfg.lid_settle_seconds * SAMPLE_RATE
        call_lang = language or utt_lang or "en"
        tail = " ".join(committed[-_PROMPT_WORDS:])
        if glossary:  # terms first, inside the same cap (DECIDE-08)
            prompt = glossary.prompt(tail, max_chars=_PROMPT_CHARS)
            segs = engine.transcribe(audio, language=call_lang, prompt=prompt,
                                     hotwords=glossary.hotwords())
        else:
            prompt = tail[-_PROMPT_CHARS:] or None
            segs = engine.transcribe(audio, language=call_lang, prompt=prompt)
        stats.decodes += 1
        return _words_of(segs), call_lang

    abandoned = False
    try:
        for block in source.blocks():
            ep.add(block)
            monitor.tick(ep.t0_seconds + ep.buffer_seconds)
            if not ep.ready_to_decode():
                continue
            ep.mark_decoded()

            a = ep.assess()
            monitor.speech(ep.t0_seconds + ep.buffer_seconds, bool(a.regions))
            if not a.regions:
                if a.forced:  # silence-only buffer that grew too big — drop it
                    ep.reset(keep_overlap=False)
                continue

            was_settled = settled
            hyp, call_lang = decode(ep.buffer)
            if not was_settled:
                # language not fixed yet: show, never commit (DECIDE-04); at an endpoint or a
                # forced cut there is no later decode, so the hypothesis commits whole
                if a.is_endpoint or a.forced:
                    start = agree.absorb([w.text for w in hyp], _spans(hyp))
                    if hyp[start:]:
                        commit([w.text for w in hyp[start:]])
                        emit(hyp[start:], final=True, lang=call_lang)
                    agree.reset()
                    prev_lang = utt_lang or prev_lang
                    utt_lang, settled = language, language is not None
                    ep.reset(keep_overlap=False)
                    last_pending = []
                    if a.is_endpoint:
                        stats.utterances += 1
                    last_commit_seconds = ep.t0_seconds + ep.buffer_seconds
                else:
                    last_pending = hyp
                    emit(hyp, final=False, lang=call_lang)
                continue
            newly, _pending = agree.push([w.text for w in hyp], _spans(hyp))
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
                    kept_c = [w for w in hyp[:done] if w.end > cut]
                    kept_p = [w for w in hyp[done:] if w.end > cut]
                    agree.rebase(
                        [w.text for w in kept_c], [w.text for w in kept_p],
                        _spans(kept_c + kept_p, shift=cut),
                    )
                else:
                    agree.reset()
                prev_lang = utt_lang or prev_lang
                if a.is_endpoint:  # a forced cut / stall splits the utterance, same language
                    utt_lang, settled = language, language is not None
                ep.reset(keep_overlap=keep_overlap)
                last_pending = []
                if a.is_endpoint:  # a forced cut / stall is not a new utterance
                    stats.utterances += 1
                last_commit_seconds = ep.t0_seconds + ep.buffer_seconds
            elif new_words:
                # committed audio has served its purpose; drop it so the next decode is short.
                # Cut *before* the last committed word so it survives whole as the anchor.
                cut = ep.trim_to(new_words[-1].start)
                if cut > 0:
                    done = o + len(newly)
                    kept_c = [w for w in hyp[:done] if w.end > cut]
                    agree.rebase(
                        [w.text for w in kept_c], [w.text for w in hyp[done:]],
                        _spans(kept_c + hyp[done:], shift=cut),
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
                start = agree.absorb([w.text for w in hyp], _spans(hyp))
                final_words = hyp[start:]
                if final_words:
                    stats.committed_words += len(final_words)
                    stats.utterances += 1
                    emit(final_words, final=True, lang=call_lang)
        except Exception:  # noqa: BLE001 - never lose the sink because the final flush failed
            logging.getLogger(__name__).exception("final flush failed; closing sink anyway")
        finally:
            try:
                glossary.save()
            except OSError:  # a read-only glossary_path must not cost the transcript
                logging.getLogger(__name__).exception("could not save the glossary")
            sink.close()

    return stats
