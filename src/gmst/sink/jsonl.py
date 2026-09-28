"""Append-only JSONL sink. Pinned schema — one object per line:

    {"t0": float, "t1": float, "text": str, "lang": str, "final": bool, "turn": int,
     "lid_prob": float[, "words": [[str, float, float], …]]}

``turn`` and ``words`` were added in Phase 4; ``words`` is present only when the engine produced
per-word timings. Non-final lines are written too (``"final": false``); a later line for an
overlapping span supersedes them.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from gmst.transcribe.types import Segment


class JsonlSink:
    def __init__(self, path: str | Path | None = None) -> None:
        self._fh = open(path, "w", encoding="utf-8") if path else sys.stdout  # noqa: SIM115
        self._owns = path is not None

    def emit(self, seg: Segment) -> None:
        obj = {
            "t0": round(seg.start, 3),
            "t1": round(seg.end, 3),
            "text": seg.text.strip(),
            "lang": seg.language,
            "final": seg.is_final,
            "turn": seg.turn,
            "lid_prob": round(seg.lid_prob, 4),
        }
        if seg.words:
            obj["words"] = [[w.text, round(w.start, 3), round(w.end, 3)] for w in seg.words]
        self._fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._owns:
            self._fh.close()
