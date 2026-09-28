"""LocalAgreement-2 (whisper_streaming, UFAL).

A word is *committed* once it appears — at the same position past the commit point — in two
consecutive hypotheses. Comparison is on **normalized** tokens (``metrics.normalize_token``:
casefold, unify apostrophes, drop edge punctuation); the **original** token is what gets emitted.

Whisper re-emits the whole utterance on every decode, so each new hypothesis is realigned against
the committed words rather than sliced by index: first by text (drop the leading run that matches
the committed tail), then — when the caller passes word ``spans`` — by time, as UFAL's
``whisper_streaming`` does: words that *end* by the last committed word's end (plus
``_TIME_TOLERANCE_S``) re-hear committed audio and are dropped, then an up-to-``_MAX_NGRAM`` repeat
of the committed tail is de-duplicated. Ends, not starts (UFAL uses starts): after a trim Whisper
often skips the anchor word and stretches the first *new* word back to the buffer head, so its
start says "committed audio" while its end does not. That is what keeps a re-heard word that the
model spells differently ("idle" → "title") from blocking the rest of the utterance (PLAN.md
"Review decisions", DECIDE-01).

Edge cases (PLAN.md "reconcile.py edge cases"):
- tail never agrees → ``flush()`` force-commits everything still pending
- ``stalled_pushes`` counts consecutive pushes that committed nothing, so the caller can force a
  flush after ``max_unconfirmed_seconds`` or N updates without progress
- the model revises text it already committed → with spans, the revised words lie over committed
  audio and are dropped by time; without spans the hypothesis **contradicts** the anchor, and
  ``push`` commits nothing and flags ``contradicted`` rather than re-emitting final words
- the caller trims committed audio out of the buffer → ``rebase()`` re-anchors on what survived
- the caller caps the context prompt (560 characters); that is not this module's job
"""

from __future__ import annotations

from collections.abc import Sequence

from gmst.metrics import normalize_token as _norm  # one normalizer, shared with WER scoring

Span = tuple[float, float]  # (start, end) of a word, seconds, buffer-relative
# A word ending within this of the committed end re-hears it. Kept at the timestamp resolution:
# a correctly re-heard anchor is already caught by the text match, so this only has to catch
# fragments and mis-heard anchors, and at 0.1 s it dropped real short words ("would" ending
# 0.06 s after the committed end — F.8 trace). A stray token beats a lost word.
_TIME_TOLERANCE_S = 0.02
_MAX_NGRAM = 5  # longest committed-tail repeat de-duplicated after the time cut


def tokenize(text: str) -> list[str]:
    return text.split()


class LocalAgreement:
    def __init__(self) -> None:
        self._committed: list[str] = []
        self._committed_end: float | None = None  # end of the last committed word, if timed
        self._prev: list[str] = []
        self._prev_spans: list[Span] | None = None
        self.stalled_pushes = 0
        self.last_offset = 0   # start of the uncommitted part in the last-pushed hypothesis
        self.contradicted = False  # last push revised words that were already committed

    @property
    def committed(self) -> list[str]:
        return list(self._committed)

    def _align(self, words: list[str], spans: Sequence[Span] | None = None) -> int:
        """Index into ``words`` just past the part that repeats committed text.

        Text first: the leading run that matches the committed tail. Failing that, and when both
        ``spans`` and the committed end time are known, time: skip words that end within the
        committed audio, then an up-to-``_MAX_NGRAM`` repeat of the committed tail.

        ``-1`` means *contradiction* (text-only callers): there is committed text, ``words`` is
        non-empty, and no prefix of it matches the committed tail — the model revised something
        already emitted as final. Falling back to ``0`` there would commit those words again.
        """
        if not self._committed or not words:
            return 0
        for k in range(min(len(words), len(self._committed)), 0, -1):
            if [_norm(w) for w in words[:k]] == [_norm(w) for w in self._committed[-k:]]:
                return k
        if spans is None or self._committed_end is None:
            return -1
        h = 0
        while h < len(words) and spans[h][1] <= self._committed_end + _TIME_TOLERANCE_S:
            h += 1
        for n in range(min(_MAX_NGRAM, len(self._committed), len(words) - h), 0, -1):
            if [_norm(w) for w in words[h : h + n]] == [_norm(w) for w in self._committed[-n:]]:
                return h + n
        return h

    def push(
        self, hypothesis: list[str], spans: Sequence[Span] | None = None
    ) -> tuple[list[str], list[str]]:
        """Feed a new full hypothesis (tokens, and their buffer-relative ``spans`` when the engine
        has word times). Returns ``(newly_committed, pending)``."""
        had_prev = bool(self._prev)
        h0 = self._align(hypothesis, spans)
        if h0 < 0:
            # the hypothesis contradicts committed text; committing from 0 would duplicate it
            self.contradicted = True
            self._prev = list(hypothesis)
            self._prev_spans = list(spans) if spans is not None else None
            self.stalled_pushes += 1
            self.last_offset = len(hypothesis)   # caller emits no words, no partial
            return [], []

        self.contradicted = False
        p0 = self._align(self._prev, self._prev_spans)
        prev_tail: list[str] = [] if p0 < 0 else self._prev[p0:]
        self.last_offset = h0

        agreed: list[str] = []
        for a, b in zip(hypothesis[h0:], prev_tail, strict=False):
            # a punctuation-only token ("-", "…") normalizes to "": it agrees with another one
            # rather than blocking every word after it (R1)
            if _norm(a) == _norm(b):
                agreed.append(a)
            else:
                break

        self._committed.extend(agreed)
        if agreed:
            self._committed_end = spans[h0 + len(agreed) - 1][1] if spans is not None else None
        self._prev = list(hypothesis)
        self._prev_spans = list(spans) if spans is not None else None
        if agreed or not had_prev:
            self.stalled_pushes = 0
        else:
            self.stalled_pushes += 1
        return agreed, hypothesis[h0 + len(agreed) :]

    def flush(self) -> list[str]:
        """Force-commit everything still pending (end of utterance, or a stuck tail).

        A contradicting tail cannot be placed against the committed text, so it is dropped:
        losing an unplaceable tail is strictly better than emitting an utterance twice. The
        caller's stall/endpoint machinery gets another decode to recover it. Use ``absorb`` on
        the shutdown path instead, where there is no "another decode".
        """
        a = self._align(self._prev, self._prev_spans)
        rest = [] if a < 0 else self._prev[a:]
        self._committed.extend(rest)
        if rest:
            self._committed_end = self._prev_spans[-1][1] if self._prev_spans else None
        return rest

    def absorb(self, hypothesis: list[str], spans: Sequence[Span] | None = None) -> int:
        """Shutdown-only last-resort commit: never drops.

        Commits the whole ``hypothesis`` tail, skipping only a prefix that genuinely repeats the
        committed tail. On a contradiction (``_align`` returns ``-1``) it commits everything —
        a small seam artifact at end-of-session beats silently losing the last utterance
        (PLAN.md: "without it every session loses its last utterance"). Returns the index it
        started committing from, so the caller can emit ``hypothesis[start:]``.
        """
        h0 = self._align(hypothesis, spans)
        start = h0 if h0 > 0 else 0
        self._committed.extend(hypothesis[start:])
        self._prev = list(hypothesis)
        self._prev_spans = list(spans) if spans is not None else None
        self.contradicted = False
        return start

    def rebase(
        self, committed: list[str], pending: list[str], spans: Sequence[Span] | None = None
    ) -> None:
        """Re-anchor after the pipeline dropped audio from the front of the buffer.

        ``committed`` are already-final words whose audio survived the cut — they will be
        transcribed again, and keeping them as the anchor is what stops ``push`` from committing
        them twice. ``pending`` is the still-unconfirmed tail that survived. Everything older is
        forgotten, so alignment keeps working against the shorter buffer. ``spans`` covers
        ``committed + pending`` in the *new* buffer's time base.
        """
        self._committed = list(committed)
        self._committed_end = spans[len(committed) - 1][1] if spans and committed else None
        self._prev = list(committed) + list(pending)
        self._prev_spans = list(spans) if spans is not None else None
        self.stalled_pushes = 0
        self.last_offset = 0
        self.contradicted = False

    def reset(self) -> None:
        self._committed.clear()
        self._committed_end = None
        self._prev.clear()
        self._prev_spans = None
        self.stalled_pushes = 0
        self.last_offset = 0
        self.contradicted = False
