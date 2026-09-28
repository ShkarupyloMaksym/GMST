"""Live audio capture from an input device.

Design (PLAN.md "Failure modes"):
- open the device at its **native** rate; resample to the 16 kHz mono contract in ``feed``
- a **bounded** queue; when the consumer falls behind, **drop the oldest** block and flag it
- surface PortAudio status flags (``input_overflow`` and the rest) from the callback — never
  swallow them
- an unexpected end of the stream (the device was unplugged) stops ``blocks()`` with
  ``DeviceLost`` so the caller can log it and exit non-zero, instead of spinning forever
- a monotonic ``samples_captured`` counter (post-resample) is the only clock

The sounddevice ``InputStream`` is a thin shell over ``feed``; ``feed`` is public so tests and a
file-fed fake source can drive the same path without PortAudio.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

import numpy as np

from gmst.audio.resample import make_stream_resampler, to_contract, to_mono_float32
from gmst.audio.types import SAMPLE_RATE, AudioArray
from gmst.config import Config


class DeviceLost(RuntimeError):
    """The input stream ended on its own — almost always an unplugged / reconfigured device."""


@dataclass(slots=True)
class CaptureStats:
    blocks_in: int = 0
    blocks_dropped: int = 0
    overflows: int = 0
    status_flags: int = 0  # callbacks that carried any PortAudio status flag at all


def resolve_device(spec: int | str | None):
    """Map a device id / numeric string / name substring to a sounddevice index (None = default)."""
    if spec is None or spec == "":
        return None
    if isinstance(spec, int):
        return spec
    if isinstance(spec, str) and spec.isdigit():
        return int(spec)
    import sounddevice as sd

    matches = [
        idx
        for idx, dev in enumerate(sd.query_devices())
        if dev["max_input_channels"] > 0 and spec.lower() in dev["name"].lower()
    ]
    if not matches:
        raise ValueError(f"no input device matching {spec!r}")
    return matches[0]


class DeviceSource:
    def __init__(self, cfg: Config, *, device: int | str | None = None, in_rate: int | None = None):
        self._cfg = cfg
        self._device_spec = device if device is not None else cfg.input_device
        self._device = None
        self._in_rate = in_rate or SAMPLE_RATE   # real value discovered in open()
        self._channels = 1
        self._device_label = "default"

        block_s = max(cfg.block_ms, 1) / 1000
        self._q: queue.Queue[AudioArray] = queue.Queue(
            maxsize=max(2, round(cfg.max_buffer_seconds / block_s))
        )
        self._stats = CaptureStats()
        self._samples_captured = 0
        self._closed = threading.Event()
        self._stream = None
        self._error: str | None = None
        self._rs = None  # persistent block resampler, created in open()

    # --- lifecycle ---------------------------------------------------------

    def open(self) -> DeviceSource:
        import sounddevice as sd

        self._device = resolve_device(self._device_spec)
        info = sd.query_devices(self._device, "input")
        self._in_rate = int(info["default_samplerate"])
        self._channels = min(int(info["max_input_channels"]), 2) or 1
        self._device_label = info["name"]
        # one resampler for the whole session: per-block one-shot calls would restart the
        # polyphase filter at every 100 ms boundary
        self._rs = make_stream_resampler(self._in_rate)
        self._stream = sd.InputStream(
            device=self._device,
            samplerate=self._in_rate,
            channels=self._channels,
            dtype="float32",
            blocksize=int(self._in_rate * self._cfg.block_ms / 1000),
            callback=self._callback,
            finished_callback=self._on_finished,
        )
        self._stream.start()
        return self

    def close(self) -> None:
        self._closed.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def __enter__(self) -> DeviceSource:
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    # --- data flow -------------------------------------------------------

    def _callback(self, indata, frames, time_info, status) -> None:  # pragma: no cover - PortAudio
        # ``+=`` from the PortAudio thread is a read-modify-write; a simultaneous read from the
        # consumer can lose a count. These are diagnostics, so the imprecision is accepted rather
        # than paying for a lock in the realtime callback.
        if status:
            self._stats.status_flags += 1
            if getattr(status, "input_overflow", False):
                self._stats.overflows += 1
        self.feed(np.array(indata, copy=True))

    def _on_finished(self) -> None:
        """PortAudio stopped the stream without us asking — treat it as a lost device."""
        if not self._closed.is_set():
            self._error = "input stream stopped unexpectedly (device disconnected?)"
            self._closed.set()

    def feed(self, raw: np.ndarray) -> None:
        """Push one native-rate block, shape ``(frames,)`` or ``(frames, channels)``.

        Uses the session's stream resampler when ``open()`` made one, so filter state carries
        across block boundaries; a source constructed without ``open()`` (tests, file-fed fakes)
        falls back to the one-shot path.
        """
        self._stats.blocks_in += 1
        if self._rs is None:
            block = to_contract(raw, self._in_rate)
        else:
            block = np.reshape(self._rs.resample_chunk(to_mono_float32(raw)), -1)
        self._samples_captured += len(block)
        try:
            self._q.put_nowait(block)
        except queue.Full:
            try:
                self._q.get_nowait()
                self._stats.blocks_dropped += 1
            except queue.Empty:
                pass
            self._q.put_nowait(block)

    def blocks(self):
        """Yield 16 kHz mono float32 blocks until ``close()``, then drain what was captured.

        Raises ``DeviceLost`` after the drain if the stream ended on its own, so the caller still
        flushes the audio it did capture and *then* exits non-zero.
        """
        while not self._closed.is_set():
            try:
                yield self._q.get(timeout=0.25)
            except queue.Empty:
                continue
        while True:  # drain — lets the shutdown flush transcribe the tail
            try:
                yield self._q.get_nowait()
            except queue.Empty:
                break
        if self._error:
            raise DeviceLost(self._error)

    # --- introspection --------------------------------------------------

    @property
    def stats(self) -> CaptureStats:
        return self._stats

    @property
    def lagging(self) -> bool:
        return self._stats.blocks_dropped > 0

    @property
    def in_rate(self) -> int:
        return self._in_rate

    @property
    def device_label(self) -> str:
        return self._device_label

    @property
    def seconds_captured(self) -> float:
        return self._samples_captured / SAMPLE_RATE
