import numpy as np

import gmst.bench as bench_mod
from gmst.bench import UPDATE_INTERVAL_S, format_table, run_bench
from gmst.config import Config
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine


def test_run_bench_computes_amplification_and_wer(monkeypatch):
    monkeypatch.setattr(bench_mod, "decode_file", lambda _p: np.zeros(16_000, dtype=np.float32))
    monkeypatch.setattr(
        bench_mod,
        "_candidates",
        lambda engine: [("m-a", "large-v2", None), ("m-b", None, "some/repo")],
    )

    def fake_load_engine(cfg, **kw):
        return FakeEngine([[Segment(0.0, 1.0, "the quick brown fox", cfg.language or "en")]])

    monkeypatch.setattr("gmst.transcribe.backends.load_engine", fake_load_engine)

    cfg = Config(max_buffer_seconds=10.0)
    rows = run_bench("clip.wav", cfg, reference="the quick brown dog")

    assert [r.label for r in rows] == ["m-a", "m-b"]
    assert all(r.ok for r in rows)
    # amplification = rtf * (max_buffer_seconds / UPDATE_INTERVAL_S)
    assert rows[0].amplification == rows[0].rtf * (10.0 / UPDATE_INTERVAL_S)
    assert rows[0].wer == 0.25  # one substitution in four


def test_each_candidate_is_released(monkeypatch):
    """Two large-v3-class models resident at once is an OOM on the target Mac."""
    import gc
    import weakref

    monkeypatch.setattr(bench_mod, "decode_file", lambda _p: np.zeros(16_000, dtype=np.float32))
    monkeypatch.setattr(
        bench_mod,
        "_candidates",
        lambda engine: [("a", "m", None), ("b", "m", None), ("c", "m", None)],
    )

    refs = []

    class _Heavy(FakeEngine):
        pass

    def fake_load_engine(cfg, **kw):
        eng = _Heavy([[Segment(0.0, 1.0, "hi", "en")]])
        refs.append(weakref.ref(eng))
        return eng

    monkeypatch.setattr("gmst.transcribe.backends.load_engine", fake_load_engine)

    run_bench("clip.wav", Config())
    gc.collect()

    assert len(refs) == 3
    assert [r() is None for r in refs] == [True, True, True]


def test_a_failing_candidate_is_released_too(monkeypatch):
    import gc
    import weakref

    monkeypatch.setattr(bench_mod, "decode_file", lambda _p: np.zeros(16_000, dtype=np.float32))
    monkeypatch.setattr(
        bench_mod, "_candidates", lambda e: [("boom", "x", None), ("ok", "y", None)]
    )

    refs = []

    def fake_load_engine(cfg, **kw):
        eng = FakeEngine([[Segment(0.0, 1.0, "hi", "en")]])
        refs.append(weakref.ref(eng))
        if cfg.model_size == "x":
            raise RuntimeError("transcribe will never happen")
        return eng

    monkeypatch.setattr("gmst.transcribe.backends.load_engine", fake_load_engine)
    rows = run_bench("clip.wav", Config())
    gc.collect()

    assert rows[0].ok is False and rows[1].ok is True
    assert all(r() is None for r in refs)


def test_an_engine_without_a_candidate_list_is_an_error(monkeypatch):
    import pytest

    monkeypatch.setattr(bench_mod, "decode_file", lambda _p: np.zeros(16_000, dtype=np.float32))
    with pytest.raises(NotImplementedError, match="canary"):
        run_bench("clip.wav", Config(engine="canary"))


def test_run_bench_isolates_failing_candidate(monkeypatch):
    monkeypatch.setattr(bench_mod, "decode_file", lambda _p: np.zeros(16_000, dtype=np.float32))
    monkeypatch.setattr(bench_mod, "_candidates", lambda e: [("boom", "x", None)])

    def blow_up(cfg, **kw):
        raise RuntimeError("no CT2 model")

    monkeypatch.setattr("gmst.transcribe.backends.load_engine", blow_up)

    rows = run_bench("clip.wav", Config())
    assert rows[0].ok is False
    assert "no CT2 model" in rows[0].error
    assert "no CT2 model" in format_table(rows)
