import json

from gmst.sink.console import ConsoleSink
from gmst.sink.jsonl import JsonlSink
from gmst.sink.srt import SrtSink
from gmst.transcribe.types import Segment


def _segs():
    return [
        Segment(0.0, 1.5, "Привіт", "uk", is_final=True, lid_prob=0.97),
        Segment(1.5, 3.0, "hello there", "en", is_final=True, lid_prob=0.99),
    ]


def test_jsonl_schema(tmp_path):
    p = tmp_path / "o.jsonl"
    sink = JsonlSink(p)
    for s in _segs():
        sink.emit(s)
    sink.close()
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]
    assert rows[0] == {"t0": 0.0, "t1": 1.5, "text": "Привіт", "lang": "uk",
                       "final": True, "turn": 1, "lid_prob": 0.97}
    assert set(rows[1]) == {"t0", "t1", "text", "lang", "final", "turn", "lid_prob"}


def test_jsonl_includes_words_when_present():
    import io

    from gmst.transcribe.types import Word

    sink = JsonlSink()
    buf = io.StringIO()
    sink._fh = buf
    sink.emit(Segment(0.0, 1.0, "hi there", "en", is_final=True,
                      words=[Word("hi", 0.0, 0.4), Word("there", 0.4, 1.0)]))
    row = json.loads(buf.getvalue())
    assert row["words"] == [["hi", 0.0, 0.4], ["there", 0.4, 1.0]]


def test_srt_numbers_and_timestamps(tmp_path):
    p = tmp_path / "o.srt"
    sink = SrtSink(p)
    for s in _segs():
        sink.emit(s)
    sink.close()
    body = p.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\n(uk) Привіт" in body
    assert "2\n00:00:01,500 --> 00:00:03,000\n(en) hello there" in body


def test_srt_ignores_non_final(tmp_path):
    p = tmp_path / "o.srt"
    sink = SrtSink(p)
    sink.emit(Segment(0.0, 1.0, "partial", "en", is_final=False))
    sink.close()
    assert p.read_text(encoding="utf-8").strip() == ""


def test_console_file_omits_partials(tmp_path):
    p = tmp_path / "o.txt"
    sink = ConsoleSink(p)
    sink.emit(Segment(0.0, 1.0, "hello", "en", is_final=False))
    sink.emit(Segment(0.0, 1.5, "hello world", "en", is_final=False))
    sink.emit(Segment(0.0, 1.5, "hello world", "en", is_final=True))
    sink.close()
    body = p.read_text(encoding="utf-8")
    assert "\r" not in body                    # no terminal redraw control codes in a file
    assert body.splitlines() == ["[00:00.00–00:01.50] (en) hello world"]


def test_console_tty_redraws_partials():
    import io

    class _Tty(io.StringIO):
        def isatty(self):
            return True

    sink = ConsoleSink()
    sink._fh = buf = _Tty()
    sink._tty = True
    sink.emit(Segment(0.0, 1.0, "hello", "en", is_final=False))
    sink.emit(Segment(0.0, 1.5, "hello world", "en", is_final=True))
    assert "\r" in buf.getvalue()


def test_console_writes_final_lines(tmp_path):
    p = tmp_path / "o.txt"
    sink = ConsoleSink(p)
    for s in _segs():
        sink.emit(s)
    sink.close()
    lines = p.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "[00:00.00–00:01.50] (uk) Привіт"
    assert lines[1] == "[00:01.50–00:03.00] (en) hello there"
