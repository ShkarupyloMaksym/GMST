import numpy as np
import pytest

import gmst.cli as cli_mod
from gmst.audio.device_source import DeviceLost
from gmst.cli import build_parser, main
from gmst.config import Config


class _FakeSource:
    """Stands in for DeviceSource: records close() calls, yields a little audio."""

    def __init__(self, *, error=None, blocks=1):
        self.closes = 0
        self.device_label = "fake"
        self.in_rate = 16_000
        self._error = error
        self._blocks = blocks

    def open(self):
        return self

    def blocks(self):
        for _ in range(self._blocks):
            yield np.zeros(1600, dtype=np.float32)
        if self._error:
            raise self._error

    def close(self):
        self.closes += 1


def _stub_stream(monkeypatch, source, run=None):
    monkeypatch.setattr("gmst.audio.device_source.DeviceSource", lambda cfg, device=None: source)
    monkeypatch.setattr(cli_mod, "_load_engine_or_report", lambda cfg, **kw: object())
    if run is not None:
        monkeypatch.setattr("gmst.pipeline.stream.run_stream", run)


def test_parser_requires_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_batch_missing_file_returns_1(capsys):
    assert main(["batch", "does-not-exist.m4a"]) == 1
    assert "no such file" in capsys.readouterr().err


def test_stream_bad_device_returns_1(capsys, monkeypatch):
    monkeypatch.setattr("sounddevice.query_devices", lambda: [])
    assert main(["stream", "-d", "no-such-device"]) == 1
    assert "cannot open input" in capsys.readouterr().err


def test_config_is_loaded_and_validated(tmp_path):
    bad = tmp_path / "gmst.toml"
    bad.write_text('engine = "bogus"\n')
    # main() must load the config before dispatching, so a bad file surfaces here.
    with pytest.raises(ValueError, match="engine:"):
        main(["-c", str(bad), "stream"])


def test_stream_language_choice_is_restricted():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["stream", "--language", "de"])


def test_stream_closes_the_device_when_run_stream_raises(monkeypatch, tmp_path):
    source = _FakeSource()

    def boom(*a, **kw):
        raise RuntimeError("engine exploded")

    _stub_stream(monkeypatch, source, run=boom)
    with pytest.raises(RuntimeError, match="engine exploded"):
        main(["stream", "-o", str(tmp_path / "o.txt")])
    assert source.closes >= 1, "the PortAudio stream was left open"


def test_stream_reports_a_lost_device_with_exit_3(monkeypatch, capsys, tmp_path):
    source = _FakeSource(error=DeviceLost("input stream stopped unexpectedly"))
    _stub_stream(monkeypatch, source)
    code = main(["stream", "-o", str(tmp_path / "o.txt")])
    assert code == 3
    assert "audio input lost" in capsys.readouterr().err
    assert source.closes >= 1


def test_stream_sigint_handler_is_restored(monkeypatch, tmp_path):
    import signal

    from gmst.pipeline.stream import StreamStats

    source = _FakeSource()
    _stub_stream(monkeypatch, source, run=lambda *a, **kw: StreamStats())
    before = signal.getsignal(signal.SIGINT)
    assert main(["stream", "-o", str(tmp_path / "o.txt")]) == 0
    assert signal.getsignal(signal.SIGINT) is before


def test_sigterm_drains_and_flushes_like_ctrl_c(monkeypatch, tmp_path):
    """`kill`, `systemctl stop` and `docker stop` send SIGTERM: without a handler the process dies
    with no drain, no final flush and no sink.close()."""
    import signal

    from gmst.pipeline.stream import StreamStats

    source = _FakeSource()
    before = signal.getsignal(signal.SIGTERM)
    seen = {}

    def run(*a, **kw):
        handler = signal.getsignal(signal.SIGTERM)
        seen["installed"] = callable(handler) and handler is not before
        if seen["installed"]:
            handler(signal.SIGTERM, None)  # what the kernel would do; never kill the test run
        seen["closes"] = source.closes
        return StreamStats()

    _stub_stream(monkeypatch, source, run=run)
    assert main(["stream", "-o", str(tmp_path / "o.txt")]) == 0
    assert seen["installed"], "no SIGTERM handler while streaming"
    assert seen["closes"] >= 1, "SIGTERM did not start the drain"
    assert signal.getsignal(signal.SIGTERM) is before


def test_a_second_interrupt_exits_130_without_a_traceback(monkeypatch, capsys, tmp_path):
    source = _FakeSource()

    def run(*a, **kw):
        raise KeyboardInterrupt

    _stub_stream(monkeypatch, source, run=run)
    assert main(["stream", "-o", str(tmp_path / "o.txt")]) == 130
    assert "abandoned" in capsys.readouterr().err
    assert source.closes >= 1


def test_missing_config_path_is_a_one_line_error(capsys, tmp_path):
    assert main(["-c", str(tmp_path / "nope.toml"), "devices"]) == 1
    err = capsys.readouterr().err
    assert "nope.toml" in err and "Traceback" not in err


def test_missing_model_reports_warmup_hint(monkeypatch, capsys, tmp_path):
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"not really audio")

    def explode(self, cfg, **kw):
        raise OSError("no such file or directory: model.bin")

    monkeypatch.setattr(
        "gmst.transcribe.backends.faster_whisper.FasterWhisperEngine.__init__", explode
    )
    assert main(["batch", str(clip)]) == 2
    err = capsys.readouterr().err
    assert "gmst warmup" in err


def test_unimplemented_backend_reports_exit_2(monkeypatch, capsys, tmp_path):
    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"not really audio")
    monkeypatch.setattr(cli_mod.Config, "load", classmethod(lambda cls, p=None: Config(
        engine="canary")))
    assert main(["batch", str(clip)]) == 2
    assert "canary" in capsys.readouterr().err


def test_bench_exits_2_when_no_candidate_loads(monkeypatch, capsys, tmp_path):
    """R7: every candidate failed to load and `gmst bench` still exited 0."""
    import gmst.bench as bench_mod

    clip = tmp_path / "clip.wav"
    clip.write_bytes(b"x")
    monkeypatch.setattr(bench_mod, "run_bench",
                        lambda *a, **kw: [bench_mod.BenchRow("m", error="ModelUnavailable: x")])
    assert main(["bench", str(clip)]) == 2


def test_warmup_bench_loads_every_bench_candidate(monkeypatch):
    """R7: `gmst warmup` cached only the configured model; Setup -> `gmst bench` failed offline."""
    import gmst.bench as bench_mod

    cands = [("a", "m1", None), ("b", None, "r/2")]
    monkeypatch.setattr(bench_mod, "_candidates", lambda e: cands)
    loaded = []

    class _E:
        def transcribe(self, audio, **kw):
            return []

    def fake_load(cfg, **kw):
        loaded.append(cfg.model_repo or cfg.model_size)
        return _E()

    monkeypatch.setattr(cli_mod, "_load_engine_or_report", fake_load)
    assert main(["warmup", "--bench"]) == 0
    assert loaded == ["m1", "r/2"]
