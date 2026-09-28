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

**Restricted LID** (``allowed`` = ``cfg.lid_languages``, PLAN.md "Review decisions", DECIDE-02):
the answer is always one of the meeting's languages. Each allowed language's probability is summed
from the detector's distribution, with ``ru`` folded into ``uk`` when ``ru`` is not itself allowed
(the tie-break generalised: Whisper hears Ukrainian as Russian far outside any margin). The best
allowed language wins; its folded mass is the confidence the sticky threshold checks, so noise that
is jointly unconfident still keeps the previous language. The first utterance has no previous
language and takes the best allowed one — safe now, because it cannot be ``ar`` or ``tr`` (R2).
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
    allowed: Sequence[str] | None = None,
) -> tuple[str, float]:
    if allowed:
        return _resolve_restricted(
            raw_lang, raw_prob, all_probs, prev_lang=prev_lang, threshold=threshold,
            tiebreak_margin=tiebreak_margin, allowed=tuple(allowed),
        )
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


def _fold(lang: str, allowed: tuple[str, ...]) -> str | None:
    if lang in allowed:
        return lang
    if lang == "ru" and "uk" in allowed:
        return "uk"
    return None


def _resolve_restricted(
    raw_lang: str,
    raw_prob: float,
    all_probs: ProbList | None,
    *,
    prev_lang: str | None,
    threshold: float,
    tiebreak_margin: float,
    allowed: tuple[str, ...],
) -> tuple[str, float]:
    fallback = prev_lang if prev_lang in allowed else allowed[0]
    if not all_probs:
        folded = _fold(raw_lang, allowed)
        if folded is None or (raw_prob < threshold and prev_lang in allowed):
            return fallback, raw_prob
        return folded, raw_prob

    mass: dict[str, float] = {}
    for lang, p in all_probs:
        folded = _fold(lang, allowed)
        if folded is not None:
            mass[folded] = mass.get(folded, 0.0) + p
    if not mass:
        return fallback, 0.0
    best = max(mass, key=mass.__getitem__)
    if "ru" in allowed and {best, "uk"} <= set(mass) and best == "ru" \
            and mass["ru"] - mass["uk"] <= tiebreak_margin:
        best = "uk"  # both allowed and close: the visible failure is ru on Ukrainian speech
        conf = mass["ru"] + mass["uk"]
    else:
        conf = mass[best]
    if conf < threshold and prev_lang in allowed:
        return prev_lang, conf
    return best, conf
