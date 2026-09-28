"""Backend factory. Imports the chosen backend lazily so `faster_whisper` machines never import
`mlx_whisper` and vice versa.

A model that is not cached yet (or a typo in ``model_repo``) surfaces as ``ModelUnavailable`` with
the "run `gmst warmup`" hint, not as a raw `huggingface_hub` traceback (PLAN.md "Model not cached").
"""

from __future__ import annotations

from collections.abc import Callable

from gmst.config import Config
from gmst.transcribe.engine import Engine


class ModelUnavailable(RuntimeError):
    """The configured model could not be loaded — missing, not downloaded, or misnamed."""


def load_engine(cfg: Config, **kwargs) -> Engine:
    target = cfg.model_repo or cfg.model_size
    if cfg.engine == "faster_whisper":
        from gmst.transcribe.backends.faster_whisper import FasterWhisperEngine

        factory: Callable[..., Engine] = FasterWhisperEngine
    elif cfg.engine == "mlx_whisper":
        from gmst.transcribe.backends.mlx_whisper import MlxWhisperEngine

        factory = MlxWhisperEngine
    elif cfg.engine == "canary":
        raise NotImplementedError("canary backend is Phase 4")
    else:
        raise ValueError(f"unknown engine: {cfg.engine!r}")

    try:
        return factory(cfg, **kwargs)
    except (OSError, ValueError) as exc:
        raise ModelUnavailable(
            f"could not load {target!r}: {exc}\n"
            "if the model is not cached yet, run: gmst warmup"
        ) from exc
