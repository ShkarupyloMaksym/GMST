"""Server-Sent Events sink — stream segments as JSON over stdlib ``http.server`` (no deps).

- ``GET /events`` → ``text/event-stream``; one ``data: {json}`` line per segment.
- ``GET /`` → a tiny viewer page (EventSource) for eyeballing a live meeting.

Event JSON matches the JSONL schema plus ``turn`` and (when present) ``words``:
``{"t0","t1","text","lang","final","turn","lid_prob"[, "words": [[w,t0,t1], …]]}``

``emit`` is called from the single reconcile thread; HTTP handlers run in their own threads and
each hold a **bounded** ``queue.Queue`` fed by ``emit`` under a lock. A viewer that stops reading
(closed laptop lid, suspended tab) back-pressures its socket, so its queue is capped and drops the
oldest events — a lagging viewer loses history, never liveness, and never unbounded memory.
"""

from __future__ import annotations

import contextlib
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from gmst.transcribe.types import Segment

_CLIENT_QUEUE_MAX = 512  # ~1 min of dense partials before a stalled viewer starts losing history

_INDEX_HTML = b"""<!doctype html><meta charset=utf-8><title>GMST live</title>
<style>body{font:16px/1.6 system-ui,sans-serif;margin:2rem;max-width:46rem}
.p{color:#999}.m{color:#0a7;font-variant-numeric:tabular-nums}</style><body><div id=o></div><script>
const o=document.getElementById('o');let p=null;
const es=new EventSource('/events');es.onmessage=e=>{const s=JSON.parse(e.data);
if(!s.final){if(!p){p=document.createElement('div');p.className='p';o.append(p)}p.textContent=s.text;return}
if(p){p.remove();p=null}const d=document.createElement('div');
const m=document.createElement('span');m.className='m';
m.textContent='['+s.t0.toFixed(1)+'] ('+s.lang+') T'+s.turn+' ';
d.append(m,s.text);
o.append(d);scrollTo(0,1e9)};</script>"""


def payload(seg: Segment) -> dict:
    obj = {
        "t0": round(seg.start, 3),
        "t1": round(seg.end, 3),
        "text": seg.text.strip(),
        "lang": seg.language,
        "final": seg.is_final,
        "turn": seg.turn,
        "lid_prob": round(seg.lid_prob, 4),
    }
    if seg.words:
        obj["words"] = [[w.text, round(w.start, 3), round(w.end, 3)] for w in seg.words]
    return obj


class SseSink:
    def __init__(self, port: int = 8765, host: str = "127.0.0.1") -> None:
        self._clients: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._closing = threading.Event()
        self.dropped = 0  # events discarded because a viewer stopped reading
        sink = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"  # read-until-close; no keep-alive framing needed

            def log_message(self, *_):  # silence stderr access log
                pass

            def do_GET(self):
                if self.path.split("?", 1)[0] != "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(_INDEX_HTML)))
                    self.end_headers()
                    self.wfile.write(_INDEX_HTML)
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q: queue.Queue = queue.Queue(maxsize=_CLIENT_QUEUE_MAX)
                with sink._lock:
                    sink._clients.add(q)
                try:
                    self.wfile.write(b"retry: 2000\n: connected\n\n")
                    self.wfile.flush()
                    while not sink._closing.is_set():
                        try:
                            item = q.get(timeout=15.0)
                        except queue.Empty:
                            self.wfile.write(b": keep-alive\n\n")  # keep proxies from idling out
                            self.wfile.flush()
                            continue
                        if item is None:
                            break
                        self.wfile.write(item)
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    with sink._lock:
                        sink._clients.discard(q)

        self._server = ThreadingHTTPServer((host, port), Handler)
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def emit(self, seg: Segment) -> None:
        line = ("data: " + json.dumps(payload(seg), ensure_ascii=False) + "\n\n").encode("utf-8")
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(line)
            except queue.Full:
                with contextlib.suppress(queue.Empty):
                    q.get_nowait()  # drop oldest: a lagging viewer loses history, not liveness
                    self.dropped += 1
                with contextlib.suppress(queue.Full):
                    q.put_nowait(line)

    def close(self) -> None:
        self._closing.set()  # a full queue must not make shutdown miss the sentinel
        with self._lock:
            clients = list(self._clients)
        for q in clients:
            with contextlib.suppress(queue.Full):
                q.put_nowait(None)
        self._server.shutdown()
        self._server.server_close()
