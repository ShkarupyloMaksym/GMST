"""load_engine's failure contract (review F.4): what reaches the user, and when."""

import sys
import types

import pytest

from gmst.config import Config
from gmst.transcribe.backends import ModelUnavailable, load_engine


def test_mlx_not_installed_is_model_unavailable_with_an_install_hint(monkeypatch):
    """R2 F5: the ModuleNotFoundError escaped as a traceback instead of exit 2."""
    monkeypatch.setitem(sys.modules, "mlx_whisper", None)  # import raises ImportError
    with pytest.raises(ModelUnavailable, match="mac"):
        load_engine(Config(engine="mlx_whisper", model_size="small"))


def test_mlx_engine_loads_its_model_at_construction(monkeypatch):
    """R2 F6: a lazy load meant a missing repo failed at the meeting's first utterance, unwrapped,
    and bench timed ~0 s of load and folded the real load into RTF."""
    monkeypatch.setitem(sys.modules, "mlx_whisper", types.ModuleType("mlx_whisper"))
    from gmst.transcribe.backends import mlx_whisper as mw

    def missing(self):
        raise FileNotFoundError("repo not in the local cache")

    monkeypatch.setattr(mw.MlxWhisperEngine, "_load", missing)
    with pytest.raises(ModelUnavailable, match="gmst warmup"):
        load_engine(Config(engine="mlx_whisper", model_size="small"))


def test_warmup_hint_only_where_warmup_can_help(monkeypatch):
    """R2 F7: "run gmst warmup" was attached to errors a download cannot fix."""
    from gmst.transcribe.backends import faster_whisper as fw

    def bad_compute_type(self, cfg, **kw):
        raise ValueError("Requested float16 compute type, but the device does not support it")

    monkeypatch.setattr(fw.FasterWhisperEngine, "__init__", bad_compute_type)
    with pytest.raises(ModelUnavailable) as exc:
        load_engine(Config())
    assert "float16" in str(exc.value) and "gmst warmup" not in str(exc.value)

    def not_cached(self, cfg, **kw):
        raise FileNotFoundError("model.bin")

    monkeypatch.setattr(fw.FasterWhisperEngine, "__init__", not_cached)
    with pytest.raises(ModelUnavailable, match="gmst warmup"):
        load_engine(Config())
