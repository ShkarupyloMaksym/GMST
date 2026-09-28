import numpy as np
import soxr

from gmst.audio.device_source import DeviceSource
from gmst.audio.resample import make_stream_resampler, to_contract
from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config


def test_passthrough_mono_float():
    x = np.linspace(-1, 1, SAMPLE_RATE, dtype=np.float32)
    out = to_contract(x, SAMPLE_RATE)
    assert out.dtype == np.float32
    assert out.shape == (SAMPLE_RATE,)
    np.testing.assert_allclose(out, x, atol=1e-6)


def test_downmix_stereo():
    stereo = np.stack([np.ones(1000), -np.ones(1000)], axis=1).astype(np.float32)
    out = to_contract(stereo, SAMPLE_RATE)
    assert out.shape == (1000,)
    np.testing.assert_allclose(out, 0.0, atol=1e-6)


def test_int16_is_scaled():
    x = np.full(500, 16384, dtype=np.int16)
    out = to_contract(x, SAMPLE_RATE)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, 16384 / 32767, atol=1e-4)


def test_resamples_rate():
    x = np.zeros(48_000, dtype=np.float32)
    out = to_contract(x, 48_000)
    assert abs(len(out) - SAMPLE_RATE) <= 2  # ~1 s at 16 kHz


def _error_db(got: np.ndarray, want: np.ndarray) -> float:
    """Error energy relative to signal energy, in dB (floored so an exact match is finite)."""
    err = float(np.mean((got - want) ** 2))
    ref = float(np.mean(want**2))
    return 10 * np.log10(max(err, 1e-30) / ref)


def test_streaming_resample_matches_whole_signal():
    """Block-wise capture must not restart the polyphase filter at every block boundary.

    A one-shot ``soxr.resample`` per 100 ms block does exactly that; the persistent
    ``ResampleStream`` carries filter state, so the concatenated blocks reproduce the
    whole-signal result.
    """
    in_rate = 44_100  # a non-integer ratio to 16 kHz, so filter state really matters
    t = np.arange(in_rate, dtype=np.float32) / in_rate
    tone = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)

    src = DeviceSource(Config(block_ms=100, max_buffer_seconds=60.0), in_rate=in_rate)
    src._rs = make_stream_resampler(in_rate)  # what open() does; we have no PortAudio here
    step = in_rate // 10  # 100 ms
    for i in range(0, len(tone) - step + 1, step):
        src.feed(tone[i : i + step])
    src.close()
    streamed = np.concatenate(list(src.blocks()))

    whole = soxr.resample(tone, in_rate, SAMPLE_RATE, quality="HQ").astype(np.float32)
    n = min(len(streamed), len(whole))
    assert n >= SAMPLE_RATE - SAMPLE_RATE // 10  # ~a full second came back

    err_db = _error_db(streamed[:n], whole[:n])
    assert err_db < -80.0, f"block-wise output is {err_db:.1f} dB off the whole-signal result"


def test_one_shot_per_block_is_the_error_this_guards_against():
    """Pin the defect: resampling each block on its own is far worse than the streaming path."""
    in_rate = 44_100
    t = np.arange(in_rate, dtype=np.float32) / in_rate
    tone = (0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    step = in_rate // 10

    per_block = np.concatenate(
        [to_contract(tone[i : i + step], in_rate) for i in range(0, len(tone) - step + 1, step)]
    )
    whole = soxr.resample(tone, in_rate, SAMPLE_RATE, quality="HQ").astype(np.float32)
    n = min(len(per_block), len(whole))
    assert _error_db(per_block[:n], whole[:n]) > -80.0
