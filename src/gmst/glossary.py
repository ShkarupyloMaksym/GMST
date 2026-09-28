"""The term glossary (PLAN.md "Review decisions", DECIDE-08).

The meetings GMST is for are Ukrainian with English technical terms. Per-utterance LID correctly
picks ``uk`` for those, and Whisper then tends to write the terms in Cyrillic or mishear them. A
glossary of the terms, written the way they should come out, is fed to every decode:

- as the head of ``initial_prompt`` (before the committed-text tail, inside the same character
  cap) — Whisper continues the style of its prompt, Latin script included;
- as faster-whisper's ``hotwords``, which unlike the prompt reaches every 30 s window of a long
  batch region. Backends without it (``mlx_whisper``) rely on the prompt.

**Auto-growing** (``glossary_autogrow``): Latin-script tokens of two or more letters that the model
*committed inside Ukrainian text* are added — they are the terms it got right, so later occurrences
stay consistent. English utterances are not a source (every word would qualify). The list is
de-duplicated case-insensitively, keeps the most recent ``max_terms``, and persists to
``glossary_path`` when the session ends. Off by default: a longer prompt costs decode time, and the
user wants it removable for speed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*[A-Za-z0-9+#]|[A-Za-z]{2}")
_EDGE = re.compile(r"^\W+|\W+$")


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

    def hotwords(self) -> str | None:
        return " ".join(self._terms) or None

    def prompt(self, tail: str | None, *, max_chars: int) -> str | None:
        """``"<terms>. <tail>"``, terms first, trimmed to ``max_chars`` from the tail's front."""
        head = (", ".join(self._terms) + ".") if self._terms else ""
        if len(head) >= max_chars:
            return head[:max_chars]
        room = max_chars - len(head) - (1 if head else 0)
        tail = (tail or "")[-room:] if room > 0 else ""
        out = f"{head} {tail}".strip() if head else tail
        return out or None

    def save(self) -> None:
        if self.path and self.autogrow:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self._terms) + "\n", encoding="utf-8")


def make_glossary(cfg) -> Glossary:
    return Glossary(cfg.glossary, autogrow=cfg.glossary_autogrow, path=cfg.glossary_path,
                    max_terms=cfg.glossary_max_terms)
