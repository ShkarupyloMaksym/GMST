"""Sink interface.

A sink is **single-writer**: only one thread (the reconcile thread, in streaming) calls ``emit``.
Sinks are not thread-safe and do not pretend to be.

``emit`` may be called with non-final segments (streaming partials); a later ``emit`` for an
overlapping span supersedes an earlier non-final one. In batch every segment is final.

``sse`` is the one kind that is not a file: asked for it *and* an output path, ``make_sink``
returns both behind a ``TeeSink`` rather than dropping the file the user asked for.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from gmst.config import Config
from gmst.transcribe.types import Segment

_EXTENSIONS = {".jsonl": "jsonl", ".srt": "srt", ".vtt": "srt", ".txt": "console"}


class Sink(Protocol):
    def emit(self, seg: Segment) -> None: ...
    def close(self) -> None: ...


class TeeSink:
    """Fan one segment stream out to several sinks; still single-writer."""

    def __init__(self, *sinks: Sink) -> None:
        self._sinks = sinks

    def emit(self, seg: Segment) -> None:
        for s in self._sinks:
            s.emit(seg)

    def close(self) -> None:
        for s in self._sinks:
            s.close()

    def __getattr__(self, name):
        # let callers reach a wrapped sink's extras (SseSink.port) through the tee
        for s in self.__dict__.get("_sinks", ()):
            if hasattr(s, name):
                return getattr(s, name)
        raise AttributeError(name)


def _file_sink(kind: str, path: Path | None) -> Sink:
    from gmst.sink.console import ConsoleSink
    from gmst.sink.jsonl import JsonlSink
    from gmst.sink.srt import SrtSink

    if kind == "jsonl":
        return JsonlSink(path)
    if kind == "srt":
        return SrtSink(path, vtt=path is not None and path.suffix.lower() == ".vtt")
    return ConsoleSink(path)


def make_sink(cfg: Config, out_path: str | Path | None, *, override: str | None = None) -> Sink:
    """Pick a sink: ``override`` wins, else ``out_path``'s extension, else ``cfg.sink``."""
    path = Path(out_path) if out_path else cfg.out_path
    kind = override or cfg.sink
    if override is None and path is not None:
        kind = _EXTENSIONS.get(path.suffix.lower(), kind)

    if kind == "sse":
        from gmst.sink.sse import SseSink

        live = SseSink(cfg.sse_port)
        if path is None:
            return live
        # an -o path alongside --sink sse used to be silently dropped
        return TeeSink(live, _file_sink(_EXTENSIONS.get(path.suffix.lower(), "jsonl"), path))
    return _file_sink(kind, path)
