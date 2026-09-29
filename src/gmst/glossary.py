"""The term glossary — **experimental** (PLAN.md "Review decisions", DECIDE-08, revised twice).

The meetings GMST is for are Ukrainian with English technical terms. Whisper decoding Ukrainian
tends to write those terms in Cyrillic ("деплой", "кубернетіс", "пул реквест"). A *curated* list
of terms corrects the decoded text: a run of 1-3 Cyrillic words whose transliteration sounds like
a term becomes the term, keeping word timings and edge punctuation. Off by default (empty list).

What the review measured (film-podcast terms set, 200 clips; the IT-meeting case is unmeasured):
- fed to Whisper as prompt + ``hotwords`` (F.12): WER +28 to +61 pts, loops, decodes > 45 s (X.6)
  — **never put the glossary into the decoder's context**;
- post-decode correction with a frequency-mined 100-term list or autogrow: term recall +1 to +6.5
  pts but WER +2.5 to +4.6 pts, because short common English words ("me", "to", "time", "men")
  matched ordinary Ukrainian words ("мені", "тому", "цим") (X.6b). Hence: curated terms only, each
  **>= 5 letters and not a common English word** (``unsafe_term``, enforced at config load), and no
  autogrow.

Matching (fixed before X.6b scored it): Ukrainian -> Latin transliteration, then both sides reduced
to a crude sound-alike key (``_key``); a match needs SequenceMatcher >= ``_MATCH``, the same first
letter, >= 4 letters, lengths within +-35 %, no more words than the term, and tolerates up to 2
trailing letters on the Cyrillic side (Ukrainian case endings: "кубернетісі").
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from gmst.transcribe.types import Word

_EDGE = re.compile(r"^\W+|\W+$")
_CYR = re.compile(r"[а-яіїєґА-ЯІЇЄҐ'ʼ’]+")
_MATCH = 0.75  # SequenceMatcher ratio on the sound-alike keys
_MAX_ENDING = 2  # trailing Cyrillic letters tolerated (case endings)
_TRANSLIT = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "ґ": "g",
        "д": "d",
        "е": "e",
        "є": "ye",
        "ж": "zh",
        "з": "z",
        "и": "y",
        "і": "i",
        "ї": "yi",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ь": "",
        "ю": "yu",
        "я": "ya",
        "'": "",
        "ʼ": "",
        "’": "",
    }
)
_SOUNDS = (
    ("ph", "f"),
    ("th", "t"),
    ("ck", "k"),
    ("qu", "kv"),
    ("ch", "\x01"),
    ("sh", "\x02"),
    ("c", "k"),
    ("\x01", "ch"),
    ("\x02", "sh"),
    ("x", "ks"),
    ("w", "v"),
    ("j", "dzh"),
    ("ee", "i"),
    ("oo", "u"),
    ("ea", "i"),
    ("y", "i"),
)


def _key(latin: str) -> str:
    """A crude sound-alike key for a Latin string: English spelling and a transliteration of the
    same word land close together ("request" and "реквест" both become "rekvest")."""
    s = re.sub(r"[^a-z]", "", latin.lower())
    for a, b in _SOUNDS:
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)


def _cyrillic_key(tokens: list[str]) -> str:
    return _key("".join(_EDGE.sub("", t).lower().translate(_TRANSLIT) for t in tokens))


def _matches(cyr: str, term: str) -> bool:
    if len(cyr) < 4 or not term or cyr[0] != term[0]:
        return False
    if not 0.65 * len(term) <= len(cyr) <= 1.35 * len(term) + _MAX_ENDING:
        return False
    extra = len(cyr) - len(term)
    cands = [cyr] + ([cyr[: len(term) + k] for k in range(0, _MAX_ENDING + 1)] if extra > 0 else [])
    return any(SequenceMatcher(None, c, term).ratio() >= _MATCH for c in cands)


# common English words of 5+ letters that a sound-alike match could find inside Ukrainian speech;
# shorter words are rejected by length alone
_COMMON = frozenset(
    [
        "about",
        "above",
        "after",
        "again",
        "against",
        "along",
        "already",
        "also",
        "always",
        "among",
        "another",
        "answer",
        "anything",
        "around",
        "because",
        "become",
        "before",
        "began",
        "being",
        "below",
        "between",
        "black",
        "bring",
        "build",
        "called",
        "cannot",
        "carry",
        "cause",
        "change",
        "close",
        "could",
        "country",
        "different",
        "doing",
        "during",
        "early",
        "earth",
        "every",
        "example",
        "family",
        "father",
        "feel",
        "field",
        "first",
        "follow",
        "found",
        "friend",
        "going",
        "great",
        "group",
        "happen",
        "heard",
        "heavy",
        "house",
        "human",
        "important",
        "large",
        "later",
        "learn",
        "leave",
        "light",
        "little",
        "living",
        "local",
        "means",
        "might",
        "money",
        "month",
        "mother",
        "music",
        "never",
        "night",
        "nothing",
        "number",
        "often",
        "order",
        "other",
        "paper",
        "party",
        "people",
        "place",
        "plant",
        "point",
        "power",
        "present",
        "problem",
        "public",
        "question",
        "quite",
        "rather",
        "really",
        "right",
        "river",
        "round",
        "school",
        "second",
        "seems",
        "seven",
        "shall",
        "short",
        "should",
        "since",
        "small",
        "something",
        "sound",
        "south",
        "space",
        "start",
        "state",
        "still",
        "story",
        "study",
        "super",
        "their",
        "there",
        "these",
        "thing",
        "things",
        "think",
        "those",
        "three",
        "through",
        "today",
        "together",
        "under",
        "until",
        "water",
        "where",
        "which",
        "while",
        "white",
        "whole",
        "world",
        "would",
        "write",
        "young",
    ]
)


def unsafe_term(term: str) -> str | None:
    """Why ``term`` is not safe to correct towards, or ``None`` when it is."""
    letters = re.sub(r"[^A-Za-z]", "", term)
    if len(letters) < 5:
        return "fewer than 5 letters"
    if term.strip().casefold() in _COMMON:
        return "a common English word"
    return None


class Glossary:
    def __init__(self, terms: Iterable[str] = ()) -> None:
        self._terms: list[str] = []
        for t in terms:
            if t.strip() and t.casefold() not in (x.casefold() for x in self._terms):
                self._terms.append(t.strip())

    @property
    def terms(self) -> list[str]:
        return list(self._terms)

    def __bool__(self) -> bool:
        return bool(self._terms)

    def correct_words(self, words: list[Word]) -> list[Word]:
        """Replace runs of 1-3 Cyrillic words that sound like a term with the term: one Word
        spanning the run's times, the run's leading/trailing punctuation kept."""
        if not self._terms or not words:
            return list(words)
        keyed = [(t, _key(t), len(t.split())) for t in self._terms]
        out: list[Word] = []
        i = 0
        while i < len(words):
            done = False
            for n in (3, 2, 1):
                run = words[i : i + n]
                if len(run) < n or not all(
                    _CYR.fullmatch(_EDGE.sub("", w.text) or "-") for w in run
                ):
                    continue
                cyr = _cyrillic_key([w.text for w in run])
                for term, tkey, n_words in keyed:
                    # never more words than the term: the case-ending tolerance must not swallow
                    # the next short word ("деплой на" is not "deploy"); fewer is fine (fused
                    # transliterations: "демонслеера" for "Demon Slayer")
                    if n <= n_words and _matches(cyr, tkey):
                        lead = re.match(r"^\W*", run[0].text).group(0)
                        trail = re.search(r"\W*$", run[-1].text).group(0)
                        out.append(Word(f"{lead}{term}{trail}", run[0].start, run[-1].end))
                        i += n
                        done = True
                        break
                if done:
                    break
            if not done:
                out.append(words[i])
                i += 1
        return out

    def correct(self, text: str) -> str:
        """``correct_words`` on plain text (no timings)."""
        words = [Word(t, 0.0, 0.0) for t in text.split()]
        return " ".join(w.text for w in self.correct_words(words))


def make_glossary(cfg) -> Glossary:
    return Glossary(cfg.glossary)
