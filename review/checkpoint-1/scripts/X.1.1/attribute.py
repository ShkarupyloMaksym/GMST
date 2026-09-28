"""X.1.1: where does the residual stream-vs-batch WER gap (X.1: +4.3 pts en, small) come from?

Re-runs X.1's en stream (20 clips, 1.5 s gaps, 100 ms blocks, shipped defaults, language pinned)
with `small`, keeps the FULL output, and logs every hypothesis word the aligner skips when the
text prefix match fails (time cut / n-gram de-dup), then aligns output vs reference word by word
and lists each deletion / substitution with context. Offline.

Run: HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/X.1.1/attribute.py [model]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import gmst.pipeline.stream as stream_mod  # noqa: E402
from gmst.audio.types import SAMPLE_RATE  # noqa: E402
from gmst.config import Config  # noqa: E402
from gmst.metrics import normalize_words  # noqa: E402
from gmst.reconcile import LocalAgreement, _norm  # noqa: E402
from gmst.transcribe.backends import load_engine  # noqa: E402
from tests.fakes import ListSource  # noqa: E402

SKIPS: list[dict] = []
FLUSHES: list[list[str]] = []


class TraceLA(LocalAgreement):
    def push(self, hypothesis, spans=None):
        committed, cend = list(self._committed), self._committed_end
        h0 = self._align(hypothesis, spans)
        exact = 0
        for k in range(min(len(hypothesis), len(committed)), 0, -1):
            if [_norm(w) for w in hypothesis[:k]] == [_norm(w) for w in committed[-k:]]:
                exact = k
                break
        if h0 > 0 and exact == 0:  # the time / n-gram path decided
            SKIPS.append({"skipped": hypothesis[:h0], "spans": [list(s) for s in spans[:h0]],
                          "committed_tail": committed[-3:], "committed_end": cend,
                          "next": hypothesis[h0:h0 + 3]})
        return super().push(hypothesis, spans)

    def flush(self):
        rest = super().flush()
        FLUSHES.append(rest)
        return rest


def align(ref, hyp):
    """Levenshtein backtrace -> list of (op, ref_word, hyp_word, ref_index)."""
    n, m = len(ref), len(hyp)
    d = np.zeros((n + 1, m + 1), dtype=np.int32)
    d[:, 0] = np.arange(n + 1)
    d[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1,
                          d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and d[i, j] == d[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            ops.append(("ok" if ref[i - 1] == hyp[j - 1] else "sub", ref[i - 1], hyp[j - 1], i - 1))
            i, j = i - 1, j - 1
        elif i and d[i, j] == d[i - 1, j] + 1:
            ops.append(("del", ref[i - 1], None, i - 1))
            i -= 1
        else:
            ops.append(("ins", None, hyp[j - 1], i))
            j -= 1
    return ops[::-1]


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "small"
    rows = [json.loads(x) for x in (ROOT / "eval/results/data/en.jsonl").read_text().splitlines()][:20]
    clips = [sf.read(ROOT / "eval/results/data" / r["wav"], dtype="float32")[0] for r in rows]
    gap = np.zeros(int(1.5 * SAMPLE_RATE), dtype=np.float32)
    audio = np.concatenate([x for c in clips for x in (c, gap)])
    ref_text = " ".join(r["text"] for r in rows)
    cfg = Config(model_size=model, compute_device="cpu", compute_type="int8")
    eng = load_engine(cfg, per_segment_lid=False)
    stream_mod.LocalAgreement = TraceLA

    class Sink:
        segs: list = []

        def emit(self, s):
            if s.is_final:
                self.segs.append(s)

        def close(self):
            pass

    sink = Sink()
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    stream_mod.run_stream(cfg, ListSource(blocks), eng, sink, language="en")
    out = " ".join(s.text for s in sink.segs)
    ref, hyp = normalize_words(ref_text), normalize_words(out)
    ops = align(ref, hyp)
    errs = [o for o in ops if o[0] != "ok"]
    skipped_norm = [_norm(w) for s in SKIPS for w in s["skipped"]]
    print(f"model={model} ref_words={len(ref)} out_words={len(hyp)} edits={len(errs)} "
          f"(del {sum(o[0] == 'del' for o in errs)}, sub {sum(o[0] == 'sub' for o in errs)}, "
          f"ins {sum(o[0] == 'ins' for o in errs)})")
    print(f"time/ngram-path skips: {len(SKIPS)} pushes, {len(skipped_norm)} words")
    del_in_skips = [o for o in errs if o[0] == "del" and o[1] in skipped_norm]
    print(f"deletions whose word was skipped by the time/ngram path: {len(del_in_skips)}")
    print("\n# errors with context (ref index, op, ref, hyp)")
    for o in errs:
        i = o[3]
        ctx = " ".join(ref[max(0, i - 4): i]) + " [" + (o[1] or "") + "] " + " ".join(ref[i + 1: i + 4])
        print(f"{i:4d} {o[0]:3s} {o[1]!s:>12} -> {o[2]!s:<12} | {ctx}")
    print("\n# time/ngram-path skips")
    for s in SKIPS:
        print(f"  skipped={s['skipped']} spans={s['spans']} end={s['committed_end']} "
              f"tail={s['committed_tail']} next={s['next']}")
    Path(__file__).with_name(f"out_{model}.txt").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
