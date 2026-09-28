"""DECIDE-08: the auto-growing term glossary (review F.12)."""

import numpy as np

from gmst.config import Config
from gmst.glossary import Glossary
from gmst.pipeline.stream import run_stream
from gmst.transcribe.types import Segment
from tests.fakes import FakeEngine, ListSource


def test_autogrow_learns_latin_terms_from_ukrainian_text_only():
    g = Glossary(autogrow=True)
    g.observe("ми зробили deploy на Kubernetes, і все ок", lang="uk")
    g.observe("the pull request is merged", lang="en")  # English speech: not a term source
    assert g.terms == ["deploy", "Kubernetes"]


def test_terms_are_deduplicated_case_insensitively_and_capped():
    g = Glossary(["Deploy"], autogrow=True, max_terms=3)
    g.observe("deploy CI CD API", lang="uk")
    assert [t.lower() for t in g.terms] == ["ci", "cd", "api"]  # most recent kept under the cap


def test_disabled_autogrow_never_grows():
    g = Glossary(["Jira"])
    g.observe("ми відкрили тікет у Jira і GitHub", lang="uk")
    assert g.terms == ["Jira"]


def test_glossary_persists_to_its_path(tmp_path):
    p = tmp_path / "terms.txt"
    g = Glossary(["Jira"], autogrow=True, path=p)
    g.observe("зробимо rebase", lang="uk")
    g.save()
    assert Glossary(path=p).terms == ["Jira", "rebase"]


def test_config_validates_the_glossary(tmp_path):
    import pytest

    bad = tmp_path / "g.toml"
    bad.write_text("glossary = [\"ok\", 3]\n")
    with pytest.raises(ValueError, match="glossary: "):
        Config.load(bad)


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
    text = "депутат замовив реквієм у кухні"
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
