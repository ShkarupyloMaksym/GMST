"""Word error rate, for `gmst bench` — and the one token normalizer GMST compares words with.

``reconcile`` needs the same notion of "these two words are the same word" as WER scoring does, so
that lives here once: casefold, unify the apostrophe variants, drop punctuation at the token edges
(a leading or trailing ``'`` / ``-`` included) while keeping it inside a word (``it's``,
``well-known``). Normalization is for *comparison* only; emitted text is never rewritten.

WER additionally splits hyphenated words (``normalize_words``): Common Voice writes ``що-небудь``
where models write ``що небудь``, which scored WER 2.0 for one word (R5). ``normalize_token`` — the
reconciler's notion of word identity — keeps them whole. Numerals are not verbalised: the CV10 and
LibriSpeech references are fully written out, so a model that writes digits pays for it.

``word_errors`` / ``char_errors`` return ``(edits, reference_length)`` so callers can pool a
**corpus** error rate (total edits / total reference length), which is what the Ukrainian
leaderboard reports — not a mean of per-clip rates.
"""

from __future__ import annotations

import re

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "ʼ": "'"})
_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)
_SPLIT = re.compile(r"[^\w'’‘`ʼ]+", re.UNICODE)  # hyphens split too (WER only)


def normalize_token(tok: str) -> str:
    """Canonical comparison form of a single word (may come back empty for pure punctuation)."""
    return _EDGE.sub("", tok.casefold().translate(_APOSTROPHES))


def normalize_words(text: str) -> list[str]:
    return [t for t in (normalize_token(w) for w in _SPLIT.sub(" ", text).split()) if t]


def _edits(ref: list[str] | str, hyp: list[str] | str) -> int:
    """Levenshtein distance, O(len(ref) * len(hyp)) time, O(len(hyp)) space."""
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cost = 0 if r == h else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def word_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """``(word edits, reference words)`` after normalization."""
    ref, hyp = normalize_words(reference), normalize_words(hypothesis)
    return _edits(ref, hyp), len(ref)


def char_errors(reference: str, hypothesis: str) -> tuple[int, int]:
    """``(character edits, reference characters)`` over the normalized, space-joined words."""
    ref, hyp = " ".join(normalize_words(reference)), " ".join(normalize_words(hypothesis))
    return _edits(ref, hyp), len(ref)


def word_error_rate(reference: str, hypothesis: str) -> float:
    errors, n = word_errors(reference, hypothesis)
    if not n:
        return 0.0 if not errors else 1.0
    return errors / n
