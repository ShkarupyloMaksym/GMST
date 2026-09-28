"""Human-readable console sink.

Batch: one line per final segment. Streaming: committed lines stay, the current non-final segment
is redrawn on a single trailing line.

The redraw needs a terminal. Written to a file or a pipe (``gmst stream -o notes.txt``) the same
path would persist every partial plus its padding, so **partials are dropped off a TTY** and the
destination gets final lines only.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gmst.transcribe.types import Segment


def _ts(seconds: float) -> str:
    m, s = divmod(max(0.0, seconds), 60)
    return f"{int(m):02d}:{s:05.2f}"


class ConsoleSink:
    def __init__(self, path: str | Path | None = None) -> None:
        self._fh = open(path, "w", encoding="utf-8") if path else sys.stdout  # noqa: SIM115
        self._owns = path is not None
        try:
            self._tty = bool(self._fh.isatty())
        except (AttributeError, ValueError):
            self._tty = False
        self._partial_len = 0
        self._turn = 1

    def emit(self, seg: Segment) -> None:
        line = f"[{_ts(seg.start)}–{_ts(seg.end)}] ({seg.language}) {seg.text.strip()}"
        if seg.is_final:
            if self._tty and self._partial_len:
                self._fh.write("\r" + " " * self._partial_len + "\r")
                self._partial_len = 0
            if seg.turn != self._turn:
                self._fh.write(f"\n— turn {seg.turn} —\n")
                self._turn = seg.turn
            self._fh.write(line + "\n")
        else:
            if not self._tty:
                return  # files and pipes get final lines only
            self._fh.write("\r" + line.ljust(self._partial_len))
            self._partial_len = len(line)
        self._fh.flush()

    def status(self, event: dict) -> None:
        """Runtime status on its own line — on a terminal only: in a transcript file it would be
        noise, and stderr already carries it as a log warning."""
        if not self._tty:
            return
        if self._partial_len:
            self._fh.write("\r" + " " * self._partial_len + "\r")
            self._partial_len = 0
        self._fh.write(f"[{event['status']}] {event.get('message', '')}\n")
        self._fh.flush()

    def close(self) -> None:
        if self._tty and self._partial_len:
            self._fh.write("\n")
        if self._owns:
            self._fh.close()
