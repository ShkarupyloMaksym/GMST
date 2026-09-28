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


def test_prompt_puts_terms_first_within_the_cap():
    g = Glossary(["Kubernetes", "deploy"])
    prompt = g.prompt("попередній текст " * 100, max_chars=80)
    assert prompt.startswith("Kubernetes, deploy.")
    assert len(prompt) <= 80
    assert Glossary().prompt("хвіст", max_chars=80) == "хвіст"


def test_config_validates_the_glossary(tmp_path):
    import pytest

    bad = tmp_path / "g.toml"
    bad.write_text("glossary = [\"ok\", 3]\n")
    with pytest.raises(ValueError, match="glossary: "):
        Config.load(bad)


def test_stream_sends_terms_as_prompt_and_hotwords():
    engine = FakeEngine([[Segment(0.0, 0.3, "так", "uk")]])
    audio = np.full(16_000, 0.3, dtype=np.float32)
    blocks = [audio[i : i + 1600] for i in range(0, len(audio), 1600)]
    cfg = Config(glossary=("Kubernetes",), vad_backend="energy", vad_threshold=0.05,
                 min_chunk_seconds=0.2)
    run_stream(cfg, ListSource(blocks), engine, _Sink(), language="uk")
    assert engine.calls and all(c["prompt"].startswith("Kubernetes") for c in engine.calls)
    assert all(c["hotwords"] == "Kubernetes" for c in engine.calls)


def test_no_glossary_leaves_the_engine_call_unchanged():
    engine = FakeEngine([[Segment(0.0, 0.3, "так", "uk")]])
    audio = np.full(16_000, 0.3, dtype=np.float32)
    blocks = [audio[i : i + 1600] for i in range(0, len(audio), 1600)]
    cfg = Config(vad_backend="energy", vad_threshold=0.05, min_chunk_seconds=0.2)
    run_stream(cfg, ListSource(blocks), engine, _Sink(), language="uk")
    assert all(c["hotwords"] is None for c in engine.calls)


class _Sink:
    def emit(self, seg):
        pass

    def close(self):
        pass
