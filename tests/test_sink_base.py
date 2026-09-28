"""`make_sink` dispatch: override > out_path extension > cfg.sink."""

import pytest

from gmst.config import Config
from gmst.sink.base import make_sink
from gmst.sink.console import ConsoleSink
from gmst.sink.jsonl import JsonlSink
from gmst.sink.srt import SrtSink


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("o.jsonl", JsonlSink),
        ("o.srt", SrtSink),
        ("o.vtt", SrtSink),
        ("o.txt", ConsoleSink),
    ],
)
def test_extension_picks_the_sink(tmp_path, name, kind):
    sink = make_sink(Config(), tmp_path / name)
    try:
        assert isinstance(sink, kind)
    finally:
        sink.close()


def test_vtt_extension_sets_the_webvtt_header(tmp_path):
    p = tmp_path / "o.vtt"
    sink = make_sink(Config(), p)
    sink.close()
    assert p.read_text(encoding="utf-8").startswith("WEBVTT")


def test_unknown_extension_falls_back_to_cfg_sink(tmp_path):
    sink = make_sink(Config(sink="jsonl"), tmp_path / "o.weird")
    try:
        assert isinstance(sink, JsonlSink)
    finally:
        sink.close()


def test_override_beats_the_extension(tmp_path):
    sink = make_sink(Config(), tmp_path / "o.srt", override="jsonl")
    try:
        assert isinstance(sink, JsonlSink)
    finally:
        sink.close()


def test_cfg_sink_is_the_fallback_with_no_path():
    for kind, cls in [("console", ConsoleSink), ("jsonl", JsonlSink), ("srt", SrtSink)]:
        sink = make_sink(Config(sink=kind), None)
        assert isinstance(sink, cls)
        if kind != "srt":  # SrtSink with no path writes to stdout on close
            sink.close()


def test_cfg_out_path_is_used_when_no_path_is_passed(tmp_path):
    p = tmp_path / "from-config.jsonl"
    sink = make_sink(Config(out_path=p), None)
    try:
        assert isinstance(sink, JsonlSink)
    finally:
        sink.close()
    assert p.exists()


def test_sse_sink_alone_when_there_is_no_path():
    from gmst.sink.sse import SseSink

    sink = make_sink(Config(sse_port=0), None, override="sse")
    try:
        assert isinstance(sink, SseSink)
        assert sink.port > 0
    finally:
        sink.close()


def test_sse_with_an_out_path_writes_the_file_too(tmp_path):
    from gmst.transcribe.types import Segment

    p = tmp_path / "also-write-this.jsonl"
    sink = make_sink(Config(sse_port=0, out_path=p), None, override="sse")
    try:
        assert sink.port > 0  # the live sink's port is still reachable through the tee
        sink.emit(Segment(0.0, 1.0, "hi", "en", is_final=True))
    finally:
        sink.close()
    # --sink sse with an -o path used to silently drop the file; it must be honoured too
    assert '"text": "hi"' in p.read_text(encoding="utf-8")
