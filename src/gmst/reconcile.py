"""LocalAgreement-2 (whisper_streaming, UFAL).

A word is *committed* once it appears — at the same position past the commit point — in two
consecutive hypotheses. Comparison is on **normalized** tokens (``metrics.normalize_token``:
casefold, unify apostrophes, drop edge punctuation); the **original** token is what gets emitted.

Whisper re-emits the whole utterance on every decode, so each new hypothesis is realigned against
the committed words (drop the leading run that matches the committed tail) rather than sliced by
index.

Edge cases (PLAN.md "reconcile.py edge cases"):
- tail never agrees → ``flush()`` force-commits everything still pending
- ``stalled_pushes`` counts consecutive pushes that committed nothing, so the caller can force a
  flush after ``max_unconfirmed_seconds`` or N updates without progress
- the model revises text it already committed → the hypothesis **contradicts** the anchor;
  ``push`` commits nothing and flags ``contradicted`` rather than re-emitting final words
- the caller trims committed audio out of the buffer → ``rebase()`` re-anchors on what survived
- the caller caps the context prompt to ~600 characters; that is not this module's job
"""

from __future__ import annotations

from gmst.metrics import normalize_token as _norm  # one normalizer, shared with WER scoring


def tokenize(text: str) -> list[str]:
    return text.split()


class LocalAgreement:
    def __init__(self) -> None:
        self._committed: list[str] = []
        self._prev: list[str] = []
        self.stalled_pushes = 0
        self.last_offset = 0   # start of the uncommitted part in the last-pushed hypothesis
        self.contradicted = False  # last push revised words that were already committed

    @property
    def committed(self) -> list[str]:
        return list(self._committed)

    def _align(self, words: list[str]) -> int:
        """Index into ``words`` just past the run that matches the committed tail.

        ``-1`` means *contradiction*: there is committed text, ``words`` is non-empty, and no
        prefix of it matches the committed tail — the model revised something already emitted as
        final. Falling back to ``0`` there would commit those words a second time.
        """
        if not self._committed or not words:
            return 0
        for k in range(min(len(words), len(self._committed)), 0, -1):
            if [_norm(w) for w in words[:k]] == [_norm(w) for w in self._committed[-k:]]:
                return k
        return -1

    def push(self, hypothesis: list[str]) -> tuple[list[str], list[str]]:
        """Feed a new full-hypothesis token list. Returns ``(newly_committed, pending)``."""
        had_prev = bool(self._prev)
        h0 = self._align(hypothesis)
        if h0 < 0:
            # the hypothesis contradicts committed text; committing from 0 would duplicate it
            self.contradicted = True
            self._prev = list(hypothesis)
            self.stalled_pushes += 1
            self.last_offset = len(hypothesis)   # caller emits no words, no partial
            return [], []

        self.contradicted = False
        p0 = self._align(self._prev)
        prev_tail: list[str] = [] if p0 < 0 else self._prev[p0:]
        self.last_offset = h0

        agreed: list[str] = []
        for a, b in zip(hypothesis[h0:], prev_tail, strict=False):
            if _norm(a) and _norm(a) == _norm(b):
                agreed.append(a)
            else:
                break

        self._committed.extend(agreed)
        self._prev = list(hypothesis)
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
        a = self._align(self._prev)
        rest = [] if a < 0 else self._prev[a:]
        self._committed.extend(rest)
        return rest

    def absorb(self, hypothesis: list[str]) -> int:
        """Shutdown-only last-resort commit: never drops.

        Commits the whole ``hypothesis`` tail, skipping only a prefix that genuinely repeats the
        committed tail. On a contradiction (``_align`` returns ``-1``) it commits everything —
        a small seam artifact at end-of-session beats silently losing the last utterance
        (PLAN.md: "without it every session loses its last utterance"). Returns the index it
        started committing from, so the caller can emit ``hypothesis[start:]``.
        """
        h0 = self._align(hypothesis)
        start = h0 if h0 > 0 else 0
        self._committed.extend(hypothesis[start:])
        self._prev = list(hypothesis)
        self.contradicted = False
        return start

    def rebase(self, committed: list[str], pending: list[str]) -> None:
        """Re-anchor after the pipeline dropped audio from the front of the buffer.

        ``committed`` are already-final words whose audio survived the cut — they will be
        transcribed again, and keeping them as the anchor is what stops ``push`` from committing
        them twice. ``pending`` is the still-unconfirmed tail that survived. Everything older is
        forgotten, so alignment keeps working against the shorter buffer.
        """
        self._committed = list(committed)
        self._prev = list(committed) + list(pending)
        self.stalled_pushes = 0
        self.last_offset = 0
        self.contradicted = False

    def reset(self) -> None:
        self._committed.clear()
        self._prev.clear()
        self.stalled_pushes = 0
        self.last_offset = 0
        self.contradicted = False
