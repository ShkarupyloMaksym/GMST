"""R2 probe: does every realistic model-load failure surface as ModelUnavailable ("run gmst
warmup"), and is the hint right for each?  Offline; loads only `tiny` (cached).

    HF_HUB_OFFLINE=1 uv run python review/checkpoint-1/scripts/R2/model_unavailable_probe.py
"""
from gmst.config import Config
from gmst.transcribe.backends import ModelUnavailable, load_engine

cases = {
    "uncached size (medium), offline": Config(model_size="medium"),
    "typo size (large-v9)": Config(model_size="large-v9"),
    "typo repo (Systran/nope)": Config(model_repo="Systran/faster-whisper-nope"),
    "cuda on a CPU-only box": Config(model_size="tiny", compute_device="cuda"),
    "float16 on cpu": Config(model_size="tiny", compute_type="float16"),
    "mlx engine on linux": Config(engine="mlx_whisper", model_size="tiny"),
}
for name, cfg in cases.items():
    try:
        load_engine(cfg)
        print(f"{name}: loaded OK")
    except ModelUnavailable as e:
        first = str(e).splitlines()
        print(f"{name}: ModelUnavailable  {first[0][:110]!r} | hint={first[-1]!r}")
    except BaseException as e:  # noqa: BLE001
        print(f"{name}: NOT wrapped -> {type(e).__module__}.{type(e).__name__}: {str(e)[:110]!r}")
