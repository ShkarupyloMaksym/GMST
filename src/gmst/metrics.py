"""Word error rate, for `gmst bench` — and the one token normalizer GMST compares words with.

``reconcile`` needs the same notion of "these two words are the same word" as WER scoring does, so
that lives here once: casefold, unify the apostrophe variants, drop punctuation at the token edges
(a leading or trailing ``'`` / ``-`` included) while keeping it inside a word (``it's``,
``well-known``). Normalization is for *comparison* only; emitted text is never rewritten.
"""

from __future__ import annotations

import re

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "ʼ": "'"})
_EDGE = re.compile(r"^\W+|\W+$", re.UNICODE)
_SPLIT = re.compile(r"[^\w'’‘`ʼ-]+", re.UNICODE)


def normalize_token(tok: str) -> str:
    """Canonical comparison form of a single word (may come back empty for pure punctuation)."""
    return _EDGE.sub("", tok.casefold().translate(_APOSTROPHES))


def normalize_words(text: str) -> list[str]:
    return [t for t in (normalize_token(w) for w in _SPLIT.sub(" ", text).split()) if t]


def word_error_rate(reference: str, hypothesis: str) -> float:
    ref = normalize_words(reference)
    hyp = normalize_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    # Levenshtein over word lists, O(len(ref) * len(hyp)) time, O(len(hyp)) space.
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, start=1):
            cost = 0 if r == h else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1] / len(ref)
