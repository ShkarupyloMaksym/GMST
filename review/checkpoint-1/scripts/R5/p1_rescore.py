"""R5 probe 1: re-score cached hyps WITHOUT writing scores.json; compare macro (mean per-clip)
WER, which run_eval reports, with corpus WER (sum errors / sum ref words), which leaderboards report.
Also: real_cs size, and does faster-whisper's Segment carry a per-segment language?
Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run --with jiwer python review/checkpoint-1/scripts/R5/p1_rescore.py
"""
import importlib.util, json, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_eval", "eval/run_eval.py")
re_ = importlib.util.module_from_spec(spec); spec.loader.exec_module(re_)
from gmst.metrics import normalize_words
import jiwer

stored = {s["system"]: s for s in json.loads(Path("eval/results/scores.json").read_text())}
for system in ("fw-tiny-auto", "fw-tiny-forced", "gmst-batch"):
    s = re_.score(system)
    same = json.dumps(s, sort_keys=True) == json.dumps(stored[system], sort_keys=True)
    print(f"{system}: rescore == scores.json: {same}")
    hyps = {json.loads(l)["id"]: json.loads(l) for l in Path(f"eval/results/hyp/{system}.jsonl").read_text().splitlines() if l.strip()}
    for name in ("en", "uk"):
        rows = [m for m in re_._load_manifest(name) if m["id"] in hyps]
        refs = [" ".join(normalize_words(m["text"])) for m in rows]
        hs = [" ".join(normalize_words(hyps[m["id"]]["text"])) for m in rows]
        corpus = 100 * jiwer.wer(refs, hs)
        print(f"   {name}: n={len(rows)} macro={s[name]['wer']}  corpus={corpus:.2f}")
    # models / settings recorded?
    print("   keys in hyp record:", sorted(next(iter(hyps.values())).keys()))

print("real_cs manifest lines:", [l for l in Path("eval/results/data/real_cs.jsonl").read_text().splitlines()])
from faster_whisper.transcribe import Segment
import dataclasses, faster_whisper
print("faster_whisper", faster_whisper.__version__, "Segment fields:", [f.name for f in dataclasses.fields(Segment)])
