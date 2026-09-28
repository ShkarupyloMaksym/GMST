"""Align a stream output (from a *.out file's 'OUT: ' line) against uk.jsonl rows [OFF, OFF+20)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "review/checkpoint-1/scripts/X.1.1"))
from attribute import align  # noqa: E402

from gmst.metrics import normalize_words  # noqa: E402

out_file, off, setname = sys.argv[1], int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "uk"
rows = [json.loads(x) for x in (ROOT / f"eval/results/data/{setname}.jsonl").read_text().splitlines()
        if x.strip()][off:off + 20]
ref = normalize_words(" ".join(r["text"] for r in rows))
out = Path(out_file).read_text().split("OUT: ", 1)[1].splitlines()[0]
for o in align(ref, normalize_words(out)):
    if o[0] != "ok":
        i = o[3]
        print(f"{o[0]:3s} {o[1]!s:>16} -> {o[2]!s:<16} | {' '.join(ref[max(0, i - 3):i])} "
              f"[{o[1] or ''}] {' '.join(ref[i + 1:i + 3])}")
