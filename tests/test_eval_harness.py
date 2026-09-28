"""The eval harness (eval/run_eval.py) is the instrument that picks the default model; these pin
the R5 fixes (F.2): cache keyed by model, corpus WER with a CI, merged scores, honest baselines."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ev(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("run_eval", ROOT / "eval" / "run_eval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "DATA", tmp_path / "data")
    monkeypatch.setattr(mod, "HYP", tmp_path / "hyp")
    monkeypatch.setattr(mod, "SCORES", tmp_path / "scores.json")
    (tmp_path / "data").mkdir()
    (tmp_path / "hyp").mkdir()
    return mod


def _manifest(ev, name, rows):
    (ev.DATA / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_gmst_hypotheses_are_cached_per_model(ev):
    ev.GMST_MODEL = "tiny"
    tiny = ev.hyp_path("gmst-batch")
    ev.GMST_MODEL = "large-v3"
    assert ev.hyp_path("gmst-batch") != tiny
    assert ev.hyp_path("fw-tiny-auto") == ev.HYP / "fw-tiny-auto.jsonl"  # model is in the name


def test_a_cache_written_by_another_model_is_refused(ev):
    ev.GMST_MODEL = "large-v3"
    p = ev.hyp_path("gmst-batch")
    p.write_text(json.dumps({"id": "a", "text": "x", "model": "tiny"}) + "\n")
    with pytest.raises(ValueError, match="tiny"):
        ev.cached_ids(p)


def test_wer_is_corpus_level_with_a_bootstrap_ci(ev):
    _manifest(ev, "en", [
        {"id": "a", "text": "one two three four five six seven eight nine ten"},
        {"id": "b", "text": "yes"},
    ])
    ev.HYP.joinpath("fw-tiny-forced.jsonl").write_text("\n".join(json.dumps(r) for r in [
        {"id": "a", "text": "one two three four five six seven eight nine ten"},
        {"id": "b", "text": "no"},
    ]) + "\n")
    s = ev.score("fw-tiny-forced")["en"]
    assert s["wer"] == pytest.approx(100 / 11, abs=0.01)  # 1 error / 11 words, not mean(0, 1)
    assert s["wer_macro"] == 50.0
    lo, hi = s["wer_ci95"]
    assert lo <= s["wer"] <= hi


def test_raw_baselines_report_switch_metrics_as_not_applicable(ev):
    _manifest(ev, "en", [])
    _manifest(ev, "uk", [])
    spans = [{"lang": "en", "text": "hi"}, {"lang": "uk", "text": "привіт"}]
    _manifest(ev, "mixed", [{"id": "m", "kind": "inter", "text": "hi привіт", "spans": spans}])
    ev.HYP.joinpath("fw-tiny-auto.jsonl").write_text(json.dumps(
        {"id": "m", "text": "hi privit", "segments": [{"text": "hi privit", "lang": "en"}]}) + "\n")
    m = ev.score("fw-tiny-auto")["mixed"]
    assert m["switch_detected"] == "n/a" and m["lid_recall"] is None
    assert "wer_uk_lid" in m and "wer_uk" not in m  # named for what it measures: LID x ASR


def test_scoring_one_system_keeps_the_others(ev):
    ev.SCORES.write_text(json.dumps([{"system": "old", "n": 1}]))
    ev.write_scores([{"system": "new", "n": 2}])
    assert {s["system"] for s in json.loads(ev.SCORES.read_text())} == {"old", "new"}
