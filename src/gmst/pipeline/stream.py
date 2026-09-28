"""Streaming pipeline, two passes (PLAN.md "Review decisions", DECIDE-09):
device blocks -> endpointer -> per-utterance LID -> engine -> LocalAgreement-2 -> **provisional**
text, and at each utterance end -> the utterance decoded whole -> **final** text.

Live pass, per decode (buffer has >= ``min_chunk_seconds`` new audio and contains speech):
1. detect the utterance's language (unless pinned) on every decode until the buffer holds
   ``lid_settle_seconds`` (3 s) of audio (DECIDE-04), then keep it for the live pass
2. transcribe the buffer, prompted with glossary terms and this utterance's live-agreed words
   (F.15/F.16), <= 560 characters
3. push the hypothesis through LocalAgreement-2; the agreed words plus the unconfirmed tail are
   emitted as one **provisional** segment (``is_final=False``) — they are never final
4. after an agreement, ``ep.trim_to`` keeps the live buffer short (back-off before the last agreed
   word) and ``agree.rebase`` re-anchors with word times

Final pass: at an endpoint, the utterance's own audio (kept since its start, up to
``max_buffer_seconds``) is cropped to its speech by the VAD and decoded in one call — like batch:
the language re-detected on the whole utterance (X.2: >= 98 % on full clips), the prompt holding
only glossary terms. Its segments are the **final** text and supersede the provisional ones. A
monologue that reaches ``max_buffer_seconds`` with no endpoint is finalised up to its latest pause.
Why: four rounds of fixes to committing live words each exposed a new failure on unseen clips —
dropped words, non-deterministic Ukrainian, replayed utterances, hallucinated boilerplate (review
X.1 ... X.1c).

Clock: every decision is on the **audio** clock (``ep.t0_seconds + ep.buffer_seconds``), never
``time.monotonic()``. Turn tracking uses the final spans.

Shutdown: when the source stops (Ctrl-C calls ``source.close()``, which drains its queue), the
``finally`` block runs the final pass on whatever the utterance holds. If that decode is abandoned
(a second Ctrl-C) or fails, the live-agreed words are emitted as final instead — ``salvage`` — so
the transcript survives; ``sink.close()`` is unconditional.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

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
# _PROMPT_WORDS (100 words ~ 126 tokens). The glossary is never in the prompt (X.6, F.18).
_PROMPT_CHARS = 560
_PROMPT_WORDS = 100  # words scanned before the character cap does the real trimming
_MAX_COMMITTED = 4000  # the session's committed word list is bounded (2 h+ meetings)
_MIN_FLUSH_SAMPLES = SAMPLE_RATE // 5  # 0.2 s — below this, nothing worth a final decode
_MAX_STALLED_PUSHES = 3  # PLAN.md: forced commit after "N updates without progress"
_FINAL_PAD_S = 0.2  # context kept around the utterance's speech for the final pass


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

    utt_words: list[str] = []  # live-committed words of this utterance: the live prompt source
    prev_lang = language
    utt_lang: str | None = language
    settled = language is not None  # pinned: nothing to settle
    last_commit_seconds = 0.0  # audio-time of the last live commit, on the sample clock
    last_pending: list[Word] = []

    # --- the final pass (DECIDE-09): the utterance's own audio, decoded whole once it ends ---
    utt_audio: list[np.ndarray] = []  # every block since the last final
    utt_t0 = 0.0  # session time of utt_audio[0]
    utt_prov: list[Word] = []  # live-committed words of this utterance, session times
    utt_heard = False  # the VAD saw speech in this utterance

    def now() -> float:
        return ep.t0_seconds + ep.buffer_seconds

    def emit_provisional(pending: list[Word], lang: str) -> None:
        """The utterance so far — live-agreed words plus the unconfirmed tail — as one partial."""
        words = utt_prov + [Word(w.text, ep.t0_seconds + w.start, ep.t0_seconds + w.end)
                            for w in pending]
        if words:
            sink.emit(Segment(words[0].start, words[-1].end, " ".join(w.text for w in words),
                              lang or "", is_final=False, turn=turns.turn, words=words))

    def live_commit(new_words: list[Word], texts: list[str]) -> None:
        utt_words.extend(texts)
        utt_prov.extend(Word(w.text, ep.t0_seconds + w.start, ep.t0_seconds + w.end)
                        for w in new_words)

    def final_pass(upto: float | None = None) -> None:
        """Decode the utterance audio up to session time ``upto`` (all of it by default) in one
        call, cropped to its speech, and emit it as final. Like batch: the language is detected
        on the whole utterance unless pinned, and the prompt holds only glossary terms — no
        committed text, which Whisper regurgitates (X.1c)."""
        nonlocal utt_audio, utt_t0, utt_prov, utt_heard, prev_lang
        audio = np.concatenate(utt_audio) if utt_audio else np.zeros(0, dtype=np.float32)
        n = len(audio) if upto is None else max(0, min(len(audio),
                                                       int(round((upto - utt_t0) * SAMPLE_RATE))))
        part, rest = audio[:n], audio[n:]
        regions = vad.speech_regions(part) if len(part) >= _MIN_FLUSH_SAMPLES else []
        if regions:
            a0 = max(0, int((regions[0][0] - _FINAL_PAD_S) * SAMPLE_RATE))
            a1 = min(len(part), int((regions[-1][1] + _FINAL_PAD_S) * SAMPLE_RATE))
            clip, off = part[a0:a1], utt_t0 + a0 / SAMPLE_RATE
            lang = language
            if lang is None:
                lang, _ = engine.detect_language(clip, prev_lang=prev_lang)
            segs = engine.transcribe(clip, language=lang)
            stats.decodes += 1
            emitted = False
            for s in segs:
                words = [Word(w.text, off + w.start, off + w.end) for w in _words_of([s])]
                words = glossary.correct_words(words)  # terms back to Latin (DECIDE-08, F.18)
                if not words:
                    continue
                text = " ".join(w.text for w in words)
                t0, t1 = words[0].start, words[-1].end
                glossary.observe(text, lang=lang)
                stats.committed_words += len(words)
                sink.emit(Segment(t0, t1, text, lang, is_final=True,
                                  turn=turns.update(t0, t1), words=words))
                emitted = True
            if emitted:
                stats.utterances += 1
            prev_lang = lang
        cut = utt_t0 + n / SAMPLE_RATE
        utt_audio = [rest] if len(rest) else []
        utt_t0 = cut
        utt_prov = [w for w in utt_prov if w.start >= cut]
        utt_heard = bool(utt_prov)

    def salvage() -> None:
        """No final pass is coming (engine failure, or a second Ctrl-C abandoned it): keep what
        the live pass agreed on rather than losing the utterance — the transcript must survive."""
        nonlocal utt_prov
        if utt_prov:
            text = " ".join(w.text for w in utt_prov)
            t0, t1 = utt_prov[0].start, utt_prov[-1].end
            stats.committed_words += len(utt_prov)
            sink.emit(Segment(t0, t1, text, utt_lang or prev_lang or "", is_final=True,
                              turn=turns.update(t0, t1), words=list(utt_prov)))
            utt_prov = []

    def monologue_cut() -> float:
        """Where to end a final when an utterance outgrows ``max_buffer_seconds`` with no
        endpoint: the middle of the latest pause in its second half, else right now."""
        audio = np.concatenate(utt_audio)
        regions = vad.speech_regions(audio)
        half = len(audio) / SAMPLE_RATE / 2
        gaps = [(b0 + a1) / 2 for (_, a1), (b0, _) in zip(regions, regions[1:], strict=False)
                if (b0 + a1) / 2 >= half]
        return utt_t0 + gaps[-1] if gaps else now()

    def live_decode(audio) -> tuple[list[Word], str]:
        """The live pass: transcribe the buffer, reporting the language it was decoded as."""
        nonlocal utt_lang, settled
        if not settled:
            utt_lang, _ = engine.detect_language(audio, prev_lang=prev_lang)
            settled = len(audio) >= cfg.lid_settle_seconds * SAMPLE_RATE
        call_lang = language or utt_lang or "en"
        # this utterance's live-committed words only (F.16), anchor words included (F.15); the
        # glossary is never in the prompt (X.6, F.18)
        prompt = " ".join(utt_words[-_PROMPT_WORDS:])[-_PROMPT_CHARS:] or None
        segs = engine.transcribe(audio, language=call_lang, prompt=prompt)
        stats.decodes += 1
        return _words_of(segs), call_lang

    def end_utterance() -> None:
        """Live-pass state back to a clean utterance, after the final pass took the audio."""
        nonlocal utt_lang, settled, last_pending, last_commit_seconds
        agree.reset()
        utt_lang, settled = language, language is not None
        ep.reset(keep_overlap=False)
        last_pending = []
        utt_words.clear()
        last_commit_seconds = now()

    abandoned = False
    try:
        for block in source.blocks():
            if not utt_audio:
                utt_t0 = now()
            utt_audio.append(np.asarray(block, dtype=np.float32))
            ep.add(block)
            monitor.tick(now())
            silent_samples = sum(len(b) for b in utt_audio)
            if not utt_heard and silent_samples > cfg.max_buffer_seconds * SAMPLE_RATE:
                keep = np.concatenate(utt_audio)[-SAMPLE_RATE:]  # silence: keep the last second
                utt_t0 = now() - len(keep) / SAMPLE_RATE
                utt_audio = [keep]
            if not ep.ready_to_decode():
                continue
            ep.mark_decoded()

            a = ep.assess()
            monitor.speech(now(), bool(a.regions))
            if not a.regions:
                if a.forced:  # silence-only buffer that grew too big — drop it
                    ep.reset(keep_overlap=False)
                continue
            utt_heard = True

            was_settled = settled
            hyp, call_lang = live_decode(ep.buffer)
            if a.is_endpoint:
                final_pass()
                end_utterance()
                continue
            if not was_settled:
                # language not fixed yet: show, never commit (DECIDE-04)
                last_pending = hyp
                emit_provisional(hyp, call_lang)
                continue
            newly, _pending = agree.push([w.text for w in hyp], _spans(hyp))
            o = agree.last_offset
            new_words = hyp[o : o + len(newly)]
            last_pending = hyp[o + len(newly) :]

            audio_now = now()
            if newly:
                live_commit(new_words, newly)
                last_commit_seconds = audio_now
            emit_provisional(last_pending, call_lang)

            # "stalled" means an unconfirmed tail that will not agree — with nothing pending
            # there is nothing to force-commit, and cutting would only churn the live pass.
            stalled = bool(last_pending) and (
                audio_now - last_commit_seconds >= cfg.max_unconfirmed_seconds
                or agree.stalled_pushes >= _MAX_STALLED_PUSHES
            )
            if a.forced or stalled:
                rest = agree.flush()
                if rest:
                    done = o + len(newly)
                    live_commit(hyp[done : done + len(rest)], rest)
                keep_overlap = not agree.contradicted
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
                ep.reset(keep_overlap=keep_overlap)
                last_pending = []
                last_commit_seconds = now()
            elif new_words:
                # committed audio has served the live pass; drop it so the next decode is short.
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
            # a monologue with no endpoint: finalise up to its latest pause
            if now() - utt_t0 >= cfg.max_buffer_seconds:
                final_pass(upto=monologue_cut())
    except KeyboardInterrupt:
        # the second Ctrl-C / SIGTERM: the user asked not to wait for the final decode
        abandoned = True
        raise
    finally:
        try:
            if abandoned:
                salvage()
            elif utt_audio:  # final_pass runs its own VAD: a tail shorter than one decode
                final_pass()  # chunk was never assessed, and must not be lost
        except Exception:  # noqa: BLE001 - never lose the sink because the final flush failed
            logging.getLogger(__name__).exception("final flush failed; closing sink anyway")
            salvage()
        finally:
            try:
                glossary.save()
            except OSError:  # a read-only glossary_path must not cost the transcript
                logging.getLogger(__name__).exception("could not save the glossary")
            sink.close()

    return stats
