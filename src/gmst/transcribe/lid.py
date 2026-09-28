"""Language-ID post-processing shared by every backend and the streaming pipeline.

A raw detector result (top language + probability + the full distribution) is turned into the
language GMST will actually use, applying:

- **uk/ru tie-break** — Whisper confuses the two; when they are the top pair and within
  ``tiebreak_margin``, prefer ``uk`` (a ``ru`` label on Ukrainian speech is the visible failure).
- **sticky threshold** — below ``threshold``, keep the previous utterance's language rather than
  flipping on a low-confidence guess.

The two rules compose: the tie-break says *which* Slavic language, never *whether* the speech is
Slavic at all. On a noisy or near-silent segment the top pair can be ``uk 0.11 / ru 0.10``, and
switching an English meeting to ``uk`` on 0.11 confidence would then stick for every following
utterance. So the tie-break is applied to the pair's **combined** mass against ``threshold``.
"""

from __future__ import annotations

from collections.abc import Sequence

ProbList = Sequence[tuple[str, float]]


def resolve_language(
    raw_lang: str,
    raw_prob: float,
    all_probs: ProbList | None,
    *,
    prev_lang: str | None,
    threshold: float,
    tiebreak_margin: float,
) -> tuple[str, float]:
    if all_probs:
        ranked = sorted(all_probs, key=lambda kv: kv[1], reverse=True)
        if len(ranked) >= 2:
            (l0, p0), (l1, p1) = ranked[0], ranked[1]
            if {l0, l1} == {"uk", "ru"} and (p0 - p1) <= tiebreak_margin:
                uk_prob = next((p for lang, p in all_probs if lang == "uk"), raw_prob)
                if (p0 + p1) < threshold and prev_lang is not None:
                    return prev_lang, uk_prob  # not even jointly confident — stay sticky
                return "uk", uk_prob

    if raw_prob < threshold and prev_lang is not None:
        return prev_lang, raw_prob
    return raw_lang, raw_prob
