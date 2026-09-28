"""Backend factory. Imports the chosen backend lazily so `faster_whisper` machines never import
`mlx_whisper` and vice versa.

A model that is not cached yet (or a typo in ``model_repo``) surfaces as ``ModelUnavailable`` with
the "run `gmst warmup`" hint, not as a raw `huggingface_hub` traceback (PLAN.md "Model not cached").
The hint goes only on ``OSError`` — a missing file, an offline cache miss, an unknown repo — which
a download can fix; a ``ValueError`` (a bad ``compute_type`` for the device, an unknown model size)
is reported without it (R2 F7). A backend whose package is not installed (``mlx_whisper`` off a
Mac, or on a Mac without the ``mac`` extra) is ``ModelUnavailable`` too, with the install command,
so every CLI path exits 2 instead of printing a traceback (R2 F5).
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
        try:
            import mlx_whisper  # noqa: F401
        except ImportError as exc:
            raise ModelUnavailable(
                f"the mlx_whisper backend is not installed ({exc}); it runs on Apple Silicon only:"
                " uv sync --extra mac"
            ) from exc
    elif cfg.engine == "canary":
        raise NotImplementedError("canary backend is Phase 4")
    else:
        raise ValueError(f"unknown engine: {cfg.engine!r}")

    try:
        return factory(cfg, **kwargs)
    except OSError as exc:  # not cached / offline / no such repo: a download can fix these
        raise ModelUnavailable(
            f"could not load {target!r}: {exc}\n"
            "if the model is not cached yet, run: gmst warmup"
        ) from exc
    except ValueError as exc:  # a bad size / compute type: warmup would not help
        raise ModelUnavailable(f"could not load {target!r}: {exc}") from exc
