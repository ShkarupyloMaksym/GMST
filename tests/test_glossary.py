"""DECIDE-08: the auto-growing term glossary (review F.12)."""

import numpy as np

from gmst.config import Config
from gmst.glossary import Glossary
from gmst.pipeline.stream import run_stream
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine, ListSource


def test_config_accepts_curated_terms_and_rejects_short_or_common_ones(tmp_path):
    """X.6b: short, common English words in the glossary matched ordinary Ukrainian words
    ("мені" -> "Men", "тому" -> "To", "цим" -> "time") and raised WER 2.5-4.6 pts. Curated-only
    (DECIDE-08, 2026-09-29): >= 5 letters and not a common English word, checked at load."""
    import pytest

    ok = tmp_path / "ok.toml"
    ok.write_text('glossary = ["Kubernetes", "deploy", "pull request"]\n')
    assert Config.load(ok).glossary == ("Kubernetes", "deploy", "pull request")
    for bad in ('["me"]', '["time"]', '["people"]', '["Kubernetes", "to"]'):
        f = tmp_path / "bad.toml"
        f.write_text(f"glossary = {bad}\n")
        with pytest.raises(ValueError, match="glossary: "):
            Config.load(f)


def test_autogrow_is_gone(tmp_path):
    """X.6b: autogrow learned "me", "to", "time" from speakers' English phrases."""
    import pytest

    f = tmp_path / "g.toml"
    f.write_text("glossary_autogrow = true\n")
    with pytest.raises(ValueError, match="glossary_autogrow"):
        Config.load(f)


def test_the_glossary_never_reaches_the_decoder():
    """X.6: fed to Whisper (prompt + hotwords, which faster-whisper puts in the same context block)
    the glossary made WER +28 to +61 pts worse. Since F.18 it only corrects the decoded text."""
    engine = FakeEngine([[Segment(0.0, 0.3, "так", "uk")]])
    audio = np.full(16_000, 0.3, dtype=np.float32)
    blocks = [audio[i : i + 1600] for i in range(0, len(audio), 1600)]
    cfg = Config(glossary=("Kubernetes",), vad_backend="energy", vad_threshold=0.05,
                 min_chunk_seconds=0.2)
    run_stream(cfg, ListSource(blocks), engine, _Sink(), language="uk")
    assert engine.calls
    assert all("Kubernetes" not in (c["prompt"] or "") for c in engine.calls)
    assert all(c["hotwords"] is None for c in engine.calls)


def test_correction_restores_terms_from_cyrillic_transliterations():
    g = Glossary(["deploy", "Kubernetes", "pull request"])
    assert g.correct("ми зробили деплой на кубернетіс") == "ми зробили deploy на Kubernetes"
    assert g.correct("відкрий пул реквест, будь ласка") == "відкрий pull request, будь ласка"


def test_correction_tolerates_ukrainian_case_endings():
    g = Glossary(["Kubernetes"])
    assert g.correct("у кубернетісі") == "у Kubernetes"


def test_correction_leaves_ordinary_ukrainian_words_alone():
    g = Glossary(["deploy", "request", "Kubernetes"])
    text = "депутат замовив реквієм у кухні, мені тому цим"
    assert g.correct(text) == text


def test_correction_keeps_word_timings():
    from gmst.transcribe.types import Word

    g = Glossary(["pull request"])
    words = [Word("відкрий", 0.0, 0.4), Word("пул", 0.4, 0.6), Word("реквест,", 0.6, 1.0)]
    out = g.correct_words(words)
    assert [(w.text, w.start, w.end) for w in out] == [("відкрий", 0.0, 0.4),
                                                       ("pull request,", 0.4, 1.0)]


def test_stream_finals_are_corrected():
    from gmst.transcribe.types import Word

    def script(audio, i):
        d = len(audio) / 16_000
        return [Segment(0.0, d, "зробимо деплой", "uk",
                        words=[Word("зробимо", 0.0, d / 2), Word("деплой", d / 2, d)])]

    audio = np.concatenate([np.full(16_000, 0.3, np.float32), np.zeros(16_000, np.float32)])
    blocks = [audio[i : i + 1600] for i in range(0, len(audio), 1600)]
    sink = _Sink()
    cfg = Config(glossary=("deploy",), vad_backend="energy", vad_threshold=0.05,
                 min_chunk_seconds=0.2, min_silence_ms=300)
    run_stream(cfg, ListSource(blocks), FakeEngine(script), sink, language="uk")
    finals = [s for s in sink.segs if s.is_final]
    assert finals and all("deploy" in s.text and "деплой" not in s.text for s in finals)


class _Sink:
    def __init__(self):
        self.segs = []

    def emit(self, seg):
        self.segs.append(seg)

    def close(self):
        pass
