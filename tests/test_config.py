import pytest

from gmst.config import Config


def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no gmst.toml at the default path
    cfg = Config.load()
    assert cfg.engine == "faster_whisper"
    assert cfg.model_size == "large-v3"  # provisional; Phase 1 sets the real default
    assert cfg.model_repo is None
    assert cfg.compute_device == "cpu"
    assert cfg.language is None
    assert cfg.lid_threshold == 0.7


def test_toml_overrides(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text(
        'engine = "mlx_whisper"\n'
        'max_buffer_seconds = 12\n'  # int accepted where float expected
        'out_path = "t.srt"\n'
    )
    cfg = Config.load(path)
    assert cfg.engine == "mlx_whisper"
    assert cfg.max_buffer_seconds == 12.0
    assert isinstance(cfg.max_buffer_seconds, float)
    assert cfg.out_path.name == "t.srt"


def test_env_beats_toml(tmp_path, monkeypatch):
    path = tmp_path / "gmst.toml"
    path.write_text('model_size = "medium"\n')
    monkeypatch.setenv("GMST_MODEL", "tiny")
    assert Config.load(path).model_size == "tiny"


def test_language_auto_sentinel_is_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GMST_LANGUAGE", "auto")
    assert Config.load().language is None


def test_unknown_key_rejected(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('modle_size = "tiny"\n')
    with pytest.raises(ValueError, match="unknown config keys"):
        Config.load(path)


def test_bad_enum_rejected(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('engine = "mlx"\n')
    with pytest.raises(ValueError, match="engine:"):
        Config.load(path)


def test_wrong_scalar_type_rejected(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('min_chunk_seconds = "soon"\n')
    with pytest.raises(ValueError, match="min_chunk_seconds:"):
        Config.load(path)


def test_out_of_range_rejected(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('lid_threshold = 1.5\n')
    with pytest.raises(ValueError, match="out of range"):
        Config.load(path)


@pytest.mark.parametrize(
    ("line", "match"),
    [
        ('word_timestamps = "yes"', "word_timestamps:"),   # truthy str would silently enable it
        ("model_size = 3", "model_size:"),
        ('language = "ukranian"', "language:"),            # would blow up on the first decode
        ("input_device = 1.5", "input_device:"),           # resolve_device matches neither
        ('model_repo = 7', "model_repo:"),
    ],
)
def test_non_numeric_scalar_types_are_validated(tmp_path, line, match):
    path = tmp_path / "gmst.toml"
    path.write_text(line + "\n")
    with pytest.raises(ValueError, match=match):
        Config.load(path)


def test_language_auto_still_maps_to_none(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('language = "auto"\n')
    assert Config.load(path).language is None


def test_language_en_and_uk_are_accepted(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('language = "uk"\n')
    assert Config.load(path).language == "uk"


def test_explicit_missing_config_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="config file not found"):
        Config.load(tmp_path / "typo.toml")


def test_default_missing_config_is_ok(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no gmst.toml here
    assert Config.load().engine == "faster_whisper"


def test_utf8_round_trip(tmp_path):
    path = tmp_path / "gmst.toml"
    path.write_text('model_repo = "Yehor/віспер-українська"\n', encoding="utf-8")
    assert Config.load(path).model_repo == "Yehor/віспер-українська"
