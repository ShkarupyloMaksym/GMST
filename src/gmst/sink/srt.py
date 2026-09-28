"""SRT / WebVTT sink. Buffers final segments and writes the file on ``close``.

Only final segments are kept; non-final (streaming partial) segments are ignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gmst.transcribe.types import Segment


def _srt_ts(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class SrtSink:
    def __init__(self, path: str | Path | None = None, *, vtt: bool = False) -> None:
        self._path = Path(path) if path else None
        self._vtt = vtt
        self._segs: list[Segment] = []

    def emit(self, seg: Segment) -> None:
        if seg.is_final:
            self._segs.append(seg)

    def close(self) -> None:
        lines: list[str] = ["WEBVTT", ""] if self._vtt else []
        for i, seg in enumerate(self._segs, start=1):
            a, b = _srt_ts(seg.start), _srt_ts(seg.end)
            if self._vtt:
                a, b = a.replace(",", "."), b.replace(",", ".")
            lines += [str(i), f"{a} --> {b}", f"({seg.language}) {seg.text.strip()}", ""]
        text = "\n".join(lines)
        if self._path:
            self._path.write_text(text, encoding="utf-8")
        else:
            sys.stdout.write(text)
