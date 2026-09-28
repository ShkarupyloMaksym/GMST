"""R5 probe 3: the hyp cache is keyed by (system, clip id) only — not by --gmst-model. A cached
tiny `gmst-batch` run is silently resumed by a later `--gmst-model large-v3` run.
Runs run_eval.main() against a scratch copy (HYP / scores.json redirected), with dispatch stubbed.
Run: HF_HUB_OFFLINE=1 UV_OFFLINE=1 uv run --with jiwer python review/checkpoint-1/scripts/R5/p3_cache_mixes_models.py
"""
import importlib.util, json, shutil, sys, tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("run_eval", "eval/run_eval.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

tmp = Path(tempfile.mkdtemp())
(tmp / "results" / "hyp").mkdir(parents=True)
shutil.copy("eval/results/hyp/gmst-batch.jsonl", tmp / "results" / "hyp" / "gmst-batch.jsonl")
m.HYP = tmp / "results" / "hyp"
m.__dict__["__file__"] = str(tmp / "run_eval.py")   # scores.json goes to tmp, not eval/results
calls = []
def fake_dispatch(system, wav, clip_lang):
    calls.append(m.GMST_MODEL)
    return {"text": "x", "segments": [{"text": "x", "lang": clip_lang or "?"}], "rtf": 0.0}
m.dispatch = fake_dispatch
m._wav = lambda rel: None
sys.argv = ["run_eval", "--systems", "gmst-batch", "--gmst-model", "large-v3", "--limit", "6"]
m.main()
recs = [json.loads(l) for l in (m.HYP / "gmst-batch.jsonl").read_text().splitlines() if l.strip()]
print("records now in gmst-batch.jsonl:", len(recs), "| new decodes with large-v3:", len(calls),
      "| cached (tiny) records reused:", len(recs) - len(calls))
print("any record naming its model?", any("model" in r for r in recs))
