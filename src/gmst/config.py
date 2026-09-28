"""Runtime configuration.

Precedence (low to high): dataclass defaults < ``gmst.toml`` < ``GMST_*`` env vars.
Every field is a flat scalar so the TOML file is a flat table. ``_merge`` validates key names,
enum values, and scalar types — **every** field, not just the numeric and enum ones — so a bad
value fails at load rather than on the first decode of the meeting. A ``--config`` path that does
not exist is an error; only the *default* path is allowed to be absent.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("gmst.toml")


@dataclass(slots=True)
class Config:
    # --- transcription ---
    engine: str = "faster_whisper"     # faster_whisper | mlx_whisper | canary
    model_size: str = "large-v3"       # PROVISIONAL — Phase 1 `gmst bench` sets the real default
    model_repo: str | None = None      # explicit HF repo / mlx path; overrides model_size when set
    compute_device: str = "cpu"        # cpu | cuda | auto  (distinct from the audio --device)
    compute_type: str = "int8"         # int8 | int8_float16 | float16 | float32
    word_timestamps: bool = True       # per-word timing (accurate spans + turn detection)

    # --- language ---
    language: str | None = None        # None / "auto" => per-utterance LID; "en" / "uk" pins it
    lid_threshold: float = 0.7         # below this, keep the previous utterance's language
    lid_tiebreak_margin: float = 0.15  # uk/ru tie-break window; prefer uk inside it
    lid_languages: tuple[str, ...] = ("en", "uk")  # LID picks only among these; ru counts as uk

    # --- audio capture (stream / listen) ---
    input_device: int | str | None = None   # sounddevice id, or name substring
    block_ms: int = 100                      # capture callback block size

    # --- streaming segmentation / reconciliation ---
    min_silence_ms: int = 600               # endpointer trailing-silence cut
    min_chunk_seconds: float = 1.0          # min new audio before a decode
    max_buffer_seconds: float = 15.0        # unconfirmed-buffer cap + trim target
    max_unconfirmed_seconds: float = 8.0    # forced commit when the tail never agrees
    vad_backend: str = "silero"            # silero | energy
    vad_threshold: float = 0.5             # silero: speech probability; energy: 0..1 of full scale
    overlap_seconds: float = 0.5           # audio kept after an endpoint, to bridge the seam

    # --- output ---
    sink: str = "console"              # console | jsonl | srt | sse
    out_path: Path | None = None
    sse_port: int = 8765              # sink = "sse": http://127.0.0.1:<port>/events
    turn_gap_seconds: float = 1.5     # a longer pause starts a new conversational turn (0 = off)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        cfg = cls()
        explicit = path is not None
        path = path or DEFAULT_CONFIG_PATH
        if path.is_file():
            cfg = _merge(cfg, tomllib.loads(path.read_text(encoding="utf-8")))
        elif explicit:  # a typo in --config must not silently run with defaults
            raise FileNotFoundError(f"config file not found: {path}")
        return _merge(cfg, _from_env())


_ENUMS: dict[str, frozenset[str]] = {
    "engine": frozenset({"faster_whisper", "mlx_whisper", "canary"}),
    "compute_device": frozenset({"cpu", "cuda", "auto"}),
    "compute_type": frozenset({"int8", "int8_float16", "float16", "float32"}),
    "vad_backend": frozenset({"silero", "energy"}),
    "sink": frozenset({"console", "jsonl", "srt", "sse"}),
}

# name -> (python type, minimum inclusive, maximum inclusive or None)
_NUMERIC: dict[str, tuple[type, float, float | None]] = {
    "block_ms": (int, 1, None),
    "min_silence_ms": (int, 0, None),
    "min_chunk_seconds": (float, 0.0, None),
    "max_buffer_seconds": (float, 1.0, None),
    "max_unconfirmed_seconds": (float, 0.0, None),
    "lid_threshold": (float, 0.0, 1.0),
    "lid_tiebreak_margin": (float, 0.0, 1.0),
    "vad_threshold": (float, 0.0, 1.0),
    "overlap_seconds": (float, 0.0, None),
    "sse_port": (int, 1, 65535),
    "turn_gap_seconds": (float, 0.0, None),
}

_BOOLS = frozenset({"word_timestamps"})
_STRINGS = frozenset({"model_size", "model_repo"})
_LANGUAGES = frozenset({"en", "uk"})  # `stream --language` already restricts to these
_LANG_CODE_LEN = (2, 3)  # Whisper language codes: "en", "uk", "haw", "yue"


def _from_env() -> dict[str, str]:
    mapping = {
        "GMST_ENGINE": "engine",
        "GMST_MODEL": "model_size",
        "GMST_MODEL_REPO": "model_repo",
        "GMST_COMPUTE_DEVICE": "compute_device",
        "GMST_COMPUTE_TYPE": "compute_type",
        "GMST_LANGUAGE": "language",
        "GMST_LID_LANGUAGES": "lid_languages",
    }
    return {field: os.environ[env] for env, field in mapping.items() if os.environ.get(env)}


def _coerce(key: str, value: object) -> object:
    if key in _ENUMS:
        if value not in _ENUMS[key]:
            raise ValueError(f"{key}: {value!r} is not one of {sorted(_ENUMS[key])}")
        return value
    if key in _NUMERIC:
        typ, lo, hi = _NUMERIC[key]
        if isinstance(value, bool):
            raise ValueError(f"{key}: expected a number, got bool")
        if typ is float:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{key}: expected a number, got {type(value).__name__}")
            value = float(value)
        elif not isinstance(value, int):
            raise ValueError(f"{key}: expected an integer, got {type(value).__name__}")
        if value < lo or (hi is not None and value > hi):
            bound = f">= {lo}" if hi is None else f"in [{lo}, {hi}]"
            raise ValueError(f"{key}: {value} is out of range ({bound})")
        return value
    if key in _BOOLS:
        if not isinstance(value, bool):
            raise ValueError(f"{key}: expected true/false, got {type(value).__name__}")
        return value
    if key in _STRINGS:
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key}: expected a string, got {type(value).__name__}")
        return value
    if key == "language":
        # "auto" is already mapped to None by _merge before we get here
        if value is not None and value not in _LANGUAGES:
            raise ValueError(
                f'language: {value!r} is not one of {sorted(_LANGUAGES)} (or "auto")'
            )
        return value
    if key == "lid_languages":
        if isinstance(value, str):  # GMST_LID_LANGUAGES="en,uk"
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, (list, tuple)) or not value:
            raise ValueError('lid_languages: expected a non-empty list such as ["en", "uk"]')
        for code in value:
            if not (isinstance(code, str) and code.isalpha() and code.islower()
                    and len(code) in _LANG_CODE_LEN):
                raise ValueError(f"lid_languages: {code!r} is not a Whisper language code")
        return tuple(value)
    if key == "input_device":
        if value is not None and not isinstance(value, (int, str)):
            raise ValueError("input_device: expected an int id or a name substring")
        return value
    return value


def _merge(base: Config, data: dict[str, object]) -> Config:
    known = {f.name for f in fields(Config)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown config keys: {', '.join(sorted(unknown))}")
    updates: dict[str, object] = {}
    for key, value in data.items():
        if key == "out_path" and value is not None:
            value = Path(str(value))
        else:
            if key == "language" and value == "auto":
                value = None  # the sentinel, then validated like any other language
            value = _coerce(key, value)
        updates[key] = value
    return replace(base, **updates)
