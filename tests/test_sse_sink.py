import json
import socket
import time

from gmst.sink.sse import SseSink, payload
from gmst.transcribe.types import Segment, Word


def test_payload_shape():
    seg = Segment(0.0, 1.0, "hi", "en", is_final=True, turn=2, lid_prob=0.9,
                  words=[Word("hi", 0.0, 1.0)])
    assert payload(seg) == {
        "t0": 0.0, "t1": 1.0, "text": "hi", "lang": "en", "final": True,
        "turn": 2, "lid_prob": 0.9, "words": [["hi", 0.0, 1.0]],
    }


def _read_until(sock, needle: bytes, deadline: float) -> bytes:
    buf = b""
    while needle not in buf and time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except TimeoutError:
            break
        if not chunk:
            break
        buf += chunk
    return buf


def test_sse_sink_streams_events_to_a_connected_client():
    sink = SseSink(port=0)
    try:
        sock = socket.create_connection(("127.0.0.1", sink.port), timeout=2)
        sock.settimeout(1.0)
        sock.sendall(b"GET /events HTTP/1.0\r\nHost: x\r\n\r\n")

        deadline = time.monotonic() + 3
        while sink.client_count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sink.client_count == 1

        sink.emit(Segment(0.0, 1.0, "привіт", "uk", is_final=False))
        sink.emit(Segment(0.0, 1.5, "привіт світ", "uk", is_final=True, turn=1))

        data = _read_until(sock, b"\xd1\x81\xd0\xb2\xd1\x96\xd1\x82", time.monotonic() + 3)
        text = data.decode("utf-8")
        assert "text/event-stream" in text
        payloads = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]
        assert [p["text"] for p in payloads] == ["привіт", "привіт світ"]
        assert payloads[1]["final"] is True
        sock.close()
    finally:
        sink.close()


def test_slow_client_queue_is_bounded():
    """A viewer that connects and never reads must not grow the sink's memory without limit."""
    sink = SseSink(port=0)
    try:
        sock = socket.create_connection(("127.0.0.1", sink.port), timeout=2)
        sock.sendall(b"GET /events HTTP/1.0\r\nHost: x\r\n\r\n")
        deadline = time.monotonic() + 3
        while sink.client_count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert sink.client_count == 1

        for i in range(5000):
            sink.emit(Segment(float(i), i + 1.0, "x" * 200, "en", is_final=False))

        q = next(iter(sink._clients))
        assert q.qsize() <= 512
        assert sink.dropped > 0
        sock.close()
    finally:
        sink.close()


def test_index_page_served():
    sink = SseSink(port=0)
    try:
        sock = socket.create_connection(("127.0.0.1", sink.port), timeout=2)
        sock.settimeout(1.0)
        sock.sendall(b"GET / HTTP/1.0\r\nHost: x\r\n\r\n")
        body = _read_until(sock, b"</script>", time.monotonic() + 3).decode("utf-8")
        assert "EventSource('/events')" in body
        sock.close()
    finally:
        sink.close()
