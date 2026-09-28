"""The term glossary (PLAN.md "Review decisions", DECIDE-08, revised 2026-09-29 after X.6).

The meetings GMST is for are Ukrainian with English technical terms. Whisper decoding Ukrainian
tends to write those terms in Cyrillic ("деплой", "кубернетіс", "пул реквест"). The glossary lists
the terms as they should appear and **corrects the decoded text**: a run of 1-3 Cyrillic words
whose transliteration sounds like a term is replaced by the term, keeping word timings and edge
punctuation.

It is **never fed to Whisper**. Until F.18 it went in as the head of ``initial_prompt`` and as
faster-whisper ``hotwords`` — which faster-whisper puts in the same context block, so the terms
appeared twice — and review X.6 measured WER +28 to +61 pts worse, loops, glossary-only
hallucinations and decodes running past 45 s. Correction cannot hurt the decode.

Matching (fixed before X.6b scored it): Ukrainian → Latin transliteration, then both sides reduced
to a crude sound-alike key (``_key``); a match needs SequenceMatcher ≥ ``_MATCH``, the same first
letter, ≥ 4 letters, lengths within ±35 %, no more words than the term, and tolerates up to 2
trailing letters on the Cyrillic side (Ukrainian case endings: "кубернетісі").

**Auto-growing** (``glossary_autogrow``): Latin-script tokens of two or more letters that appear
*inside Ukrainian text* are added — terms the model already wrote correctly, so later
transliterations of them get corrected. English utterances are not a source. De-duplicated
case-insensitively, the most recent ``max_terms`` kept, persisted to ``glossary_path`` at the end
of the session.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher
from pathlib import Path

from gmst.transcribe.types import Word

_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z]{2}")
_EDGE = re.compile(r"^\W+|\W+$")
_CYR = re.compile(r"[а-яіїєґА-ЯІЇЄҐ'ʼ’]+")
_MATCH = 0.75  # SequenceMatcher ratio on the sound-alike keys
_MAX_ENDING = 2  # trailing Cyrillic letters tolerated (case endings)
_TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "ґ": "g", "д": "d", "е": "e", "є": "ye", "ж": "zh",
    "з": "z", "и": "y", "і": "i", "ї": "yi", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "yu", "я": "ya", "'": "", "ʼ": "", "’": "",
})
_SOUNDS = (("ph", "f"), ("th", "t"), ("ck", "k"), ("qu", "kv"), ("ch", "\x01"), ("sh", "\x02"),
           ("c", "k"), ("\x01", "ch"), ("\x02", "sh"), ("x", "ks"), ("w", "v"), ("j", "dzh"),
           ("ee", "i"), ("oo", "u"), ("ea", "i"), ("y", "i"))


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


class Glossary:
    def __init__(
        self,
        terms: Iterable[str] = (),
        *,
        autogrow: bool = False,
        path: Path | None = None,
        max_terms: int = 100,
    ) -> None:
        self.autogrow = autogrow
        self.path = Path(path) if path else None
        self.max_terms = max_terms
        self._terms: list[str] = []
        for t in terms:
            self._add(t)
        if self.path and self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._add(line.strip())

    @property
    def terms(self) -> list[str]:
        return list(self._terms)

    def __bool__(self) -> bool:
        return bool(self._terms)

    def _add(self, term: str) -> None:
        key = term.casefold()
        self._terms = [t for t in self._terms if t.casefold() != key] + [term]
        if len(self._terms) > self.max_terms:
            del self._terms[: len(self._terms) - self.max_terms]

    def observe(self, text: str, *, lang: str) -> None:
        """Learn the Latin-script terms in committed ``text`` decoded as ``lang``."""
        if not self.autogrow or lang != "uk":
            return
        for raw in text.split():
            tok = _EDGE.sub("", raw)
            if _TERM.fullmatch(tok) and not any(t.casefold() == tok.casefold() for t in
                                                 self._terms):
                self._add(tok)

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
                if len(run) < n or not all(_CYR.fullmatch(_EDGE.sub("", w.text) or "-")
                                           for w in run):
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

    def save(self) -> None:
        if self.path and self.autogrow:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self._terms) + "\n", encoding="utf-8")


def make_glossary(cfg) -> Glossary:
    return Glossary(cfg.glossary, autogrow=cfg.glossary_autogrow, path=cfg.glossary_path,
                    max_terms=cfg.glossary_max_terms)
