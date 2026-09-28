import numpy as np
import pytest

import gmst.pipeline.stream as stream_mod
from gmst.audio.types import SAMPLE_RATE
from gmst.config import Config
from gmst.pipeline.stream import run_stream
from gmst.sink.srt import SrtSink
from gmst.transcribe.types import Segment, Word
from tests.fakes import FakeEngine, ListSource


class RecSink:
    def __init__(self):
        self.segs: list[Segment] = []
        self.closed = False

    def emit(self, seg):
        self.segs.append(seg)

    def close(self):
        self.closed = True

    def final_words(self):
        return " ".join(s.text for s in self.segs if s.is_final).split()


def _loud(seconds):
    return np.full(int(seconds * SAMPLE_RATE), 0.3, dtype=np.float32)


def _silent(seconds):
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


def _marked(n_chunks, chunk_seconds=0.5):
    """Audio whose every chunk carries its own amplitude.

    A fake engine can then name the word living at each position from the audio alone — the way a
    real model re-transcribes the same speech to the same words whenever the pipeline hands that
    audio back (overlap after a forced cut, the back-off sliver left by a trim).
    """
    return np.concatenate(
        [
            np.full(int(chunk_seconds * SAMPLE_RATE), 0.1 + 0.05 * i, dtype=np.float32)
            for i in range(n_chunks)
        ]
    )


def _marked_engine():
    """A FakeEngine that reads the marks back out of whatever buffer it is handed."""

    def script(audio, _call):
        vals = np.asarray(audio)
        if len(vals) == 0:
            return []
        edges = np.flatnonzero(np.diff(vals)) + 1
        starts = np.concatenate(([0], edges))
        ends = np.concatenate((edges, [len(vals)]))
        words = [
            Word(f"w{int(round(float(vals[s]) * 100))}", s / SAMPLE_RATE, e / SAMPLE_RATE)
            for s, e in zip(starts, ends, strict=True)
        ]
        text = " ".join(w.text for w in words)
        return [Segment(words[0].start, words[-1].end, text, "en", words=words)]

    return FakeEngine(script)


def _cfg(**kw):
    base = dict(
        min_chunk_seconds=0.1,
        min_silence_ms=250,
        max_buffer_seconds=100.0,
        max_unconfirmed_seconds=100.0,
        overlap_seconds=0.0,
        vad_backend="energy",
        vad_threshold=0.05,
    )
    base.update(kw)
    return Config(**base)


def test_progressive_commit_endpoint_and_shutdown_flush():
    blocks = [_loud(0.1)] * 5 + [_silent(0.1)] * 4
    src = ListSource(blocks)
    engine = FakeEngine(
        [
            [Segment(0.0, 0.5, "hello", "en")],
            [Segment(0.0, 0.6, "hello world", "en")],
            [Segment(0.0, 0.6, "hello world", "en")],
        ]
    )
    sink = RecSink()

    stats = run_stream(_cfg(), src, engine, sink, language="en")

    assert sink.closed is True
    assert sink.final_words() == ["hello", "world"]
    assert stats.committed_words == 2
    assert stats.decodes >= 3
    assert stats.utterances >= 1
    # partials only ever showed unconfirmed text from the running hypothesis
    for s in sink.segs:
        if not s.is_final:
            assert s.text in ("hello", "hello world", "world")


def test_language_is_detected_per_utterance_when_not_pinned():
    src = ListSource([_loud(0.1)] * 4 + [_silent(0.1)] * 3)
    engine = FakeEngine(
        [[Segment(0.0, 0.4, "привіт", "uk")], [Segment(0.0, 0.4, "привіт", "uk")]],
        lang="uk",
        lang_prob=0.93,
    )
    sink = RecSink()

    run_stream(_cfg(), src, engine, sink, language=None)

    assert [s.language for s in sink.segs if s.is_final] == ["uk"]
    # every emit — partials included — carries the language the decode actually used, not the
    # pre-detection default
    assert sink.segs and all(s.language == "uk" for s in sink.segs)
    # detect_language was consulted (FakeEngine records transcribe calls with the resolved language)
    assert engine.calls and engine.calls[0]["language"] == "uk"


def test_shutdown_flush_labels_the_last_utterance_with_the_detected_language():
    # loud, silent (endpoint -> utt_lang reset to None), then a tail shorter than
    # min_chunk_seconds: the only decode of that last utterance happens in the `finally` flush.
    src = ListSource([_loud(1.0), _silent(1.0), _loud(0.5)])
    engine = FakeEngine(
        [[Segment(0.0, 0.5, "привіт", "uk")]], lang="uk", lang_prob=0.93
    )
    sink = RecSink()

    run_stream(_cfg(min_chunk_seconds=1.0, min_silence_ms=500), src, engine, sink, language=None)

    finals = [s for s in sink.segs if s.is_final]
    assert len(finals) >= 2
    assert finals[-1].language == "uk"  # not the pre-detection "en"
    assert engine.calls[-1]["language"] == "uk"


class _AllSpeechVad:
    def speech_regions(self, audio):
        return [(0.0, len(audio) / SAMPLE_RATE)]


class _EndpointEveryTime:
    """Reports a big trailing silence, so every assess() is an endpoint."""

    def speech_regions(self, audio):
        return [(0.0, max(0.0, len(audio) / SAMPLE_RATE - 5.0))]


def test_emitted_spans_use_word_timestamps(monkeypatch):
    monkeypatch.setattr(stream_mod, "make_vad", lambda cfg: _AllSpeechVad())
    src = ListSource([_loud(0.1)] * 4)
    w = [Word("hello", 0.2, 0.6), Word("world", 0.6, 1.1)]
    engine = FakeEngine(
        [
            [Segment(0.0, 1.1, "hello world", "en", words=w)],
            [Segment(0.0, 1.1, "hello world", "en", words=w)],
        ]
    )
    sink = RecSink()
    run_stream(_cfg(max_buffer_seconds=100.0), src, engine, sink, language="en")

    finals = [s for s in sink.segs if s.is_final]
    assert finals and finals[0].text == "hello world"
    # span comes from the words (0.2 .. 1.1), not the whole buffer (0 .. 0.4)
    assert finals[0].start == 0.2
    assert finals[0].end == 1.1
    assert [x.text for x in finals[0].words] == ["hello", "world"]


def test_turn_bumps_after_a_long_gap_between_committed_spans(monkeypatch):
    monkeypatch.setattr(stream_mod, "make_vad", lambda cfg: _EndpointEveryTime())

    def script(audio, i):
        if i == 0:
            return [Segment(0.0, 0.3, "first", "en", words=[Word("first", 0.0, 0.3)])]
        dur = len(audio) / SAMPLE_RATE  # utterance 2 sits at the end of a long buffer
        return [Segment(dur - 0.3, dur, "second", "en", words=[Word("second", dur - 0.3, dur)])]

    src = ListSource([_loud(0.3), _loud(2.0)])
    sink = RecSink()
    cfg = _cfg(
        min_chunk_seconds=0.2, min_silence_ms=300, turn_gap_seconds=1.0, max_buffer_seconds=100.0
    )
    run_stream(cfg, src, FakeEngine(script), sink, language="en")
    finals = [s for s in sink.segs if s.is_final]
    assert [s.text for s in finals] == ["first", "second"]
    assert [s.turn for s in finals] == [1, 2]


def test_shutdown_flush_commits_unconfirmed_tail():
    # Exactly two blocks -> exactly two in-loop decodes. The second one commits "alpha beta" and
    # leaves "gamma" pending, so only the `finally` flush can turn it final: delete that flush and
    # this test fails.
    src = ListSource([_loud(0.1)] * 2)
    engine = FakeEngine(
        [[Segment(0.0, 0.1, "alpha beta", "en")], [Segment(0.0, 0.2, "alpha beta gamma", "en")]]
    )
    sink = RecSink()

    run_stream(_cfg(), src, engine, sink, language="en")

    assert sink.final_words() == ["alpha", "beta", "gamma"]
    # "gamma" arrived after the loop ended, in the shutdown decode
    assert len(engine.calls) == 3


def test_shutdown_flush_keeps_a_contradicting_tail_instead_of_dropping_it():
    # The in-loop decodes commit "the quick brown"; the final tail decode revises "brown" ->
    # "brownish" so it contradicts the anchor. F03's drop-on-contradiction is right mid-stream
    # (a later decode recovers) but at end-of-session there is no later decode — absorb() must
    # keep the tail rather than silently lose the last words of the meeting.
    def script(audio, i):
        dur = len(audio) / SAMPLE_RATE
        toks = ["the", "quick", "brown"] if i < 2 else \
            ["the", "quick", "brownish", "fox", "jumps"]
        step = dur / len(toks)
        words = [Word(t, k * step, (k + 1) * step) for k, t in enumerate(toks)]
        return [Segment(0.0, dur, " ".join(toks), "en", words=words)]

    src = ListSource([_loud(0.2), _loud(0.2)])
    sink = RecSink()
    run_stream(_cfg(min_chunk_seconds=0.15), src, FakeEngine(script), sink, language="en")

    words = sink.final_words()
    assert "fox" in words and "jumps" in words  # the contradicting tail was not dropped
    assert sink.closed


def test_sink_is_closed_even_when_the_engine_dies_mid_meeting(tmp_path):
    """An engine failure must not cost the transcript: SrtSink only writes its file in close()."""

    class DyingEngine(FakeEngine):
        def transcribe(self, audio, *, language=None, prompt=None):
            if len(self.calls) >= 3:
                self.calls.append({"samples": len(audio), "language": language, "prompt": prompt})
                raise RuntimeError("engine died")
            return super().transcribe(audio, language=language, prompt=prompt)

    p = tmp_path / "o.srt"
    engine = DyingEngine(
        [
            [Segment(0.0, 0.1, "w0", "en")],
            [Segment(0.0, 0.2, "w0 w1", "en")],
            [Segment(0.0, 0.3, "w0 w1", "en")],
        ]
    )
    sink = SrtSink(p)

    with pytest.raises(RuntimeError, match="engine died"):
        run_stream(_cfg(), ListSource([_loud(0.1)] * 6), engine, sink, language="en")

    assert p.exists()
    body = p.read_text(encoding="utf-8")
    assert "w0" in body and "w1" in body


def test_forced_cut_never_re_commits_the_overlap_or_moves_time_backwards():
    # max_buffer_seconds=1.0 with overlap_seconds=0.5 forces a cut roughly every second, and the
    # retained half-second is handed straight back to the engine.
    cfg = _cfg(
        min_chunk_seconds=0.5,
        max_buffer_seconds=1.0,
        overlap_seconds=0.5,
        min_silence_ms=100_000,  # all-speech input; only forced cuts can fire
    )
    audio = _marked(6)  # 3 s, one word per 0.5 s
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    sink = RecSink()

    run_stream(cfg, ListSource(blocks), _marked_engine(), sink, language="en")

    words = sink.final_words()
    assert words, "nothing was committed"
    assert len(words) == len(set(words)), f"the seam was committed twice: {words}"
    assert words == sorted(words, key=lambda w: int(w[1:]))

    finals = [s for s in sink.segs if s.is_final]
    prev_end = -1.0
    for s in finals:
        assert s.start >= prev_end - 1e-9, f"{s.text} starts at {s.start}, before {prev_end}"
        prev_end = s.end


def test_committed_audio_is_trimmed_so_the_decoded_buffer_stays_bounded():
    cfg = _cfg(min_chunk_seconds=0.5, max_buffer_seconds=15.0, min_silence_ms=100_000)
    audio = _marked(40)  # 20 s of unbroken speech — no endpoint, no forced cut
    blocks = [audio[i : i + SAMPLE_RATE // 10] for i in range(0, len(audio), SAMPLE_RATE // 10)]
    engine = _marked_engine()
    sink = RecSink()

    run_stream(cfg, ListSource(blocks), engine, sink, language="en")

    biggest = max(c["samples"] for c in engine.calls)
    assert biggest < 4 * SAMPLE_RATE, f"buffer grew to {biggest / SAMPLE_RATE:.1f}s without a trim"
    words = sink.final_words()
    assert len(words) >= 30
    assert len(words) == len(set(words)), "a trimmed word was committed twice"


def _stuck_tail_script(audio, i):
    """"alpha beta" is stable; the last word is different on every decode, so it never agrees.

    The words sit inside the trim back-off, so no trim fires and the only way out is a forced
    commit.
    """
    words = [Word("alpha", 0.0, 0.05), Word("beta", 0.05, 0.1), Word(f"tail{i}", 0.1, 0.15)]
    return [Segment(0.0, 0.15, " ".join(w.text for w in words), "en", words=words)]


def test_forced_commit_on_a_never_agreeing_tail(monkeypatch):
    """The forced commit is on the audio clock, not the wall clock.

    The whole test runs in milliseconds, so a `time.monotonic()` threshold of 2 s could never
    fire; 6 s of *audio* goes past it.
    """
    monkeypatch.setattr(stream_mod, "_MAX_STALLED_PUSHES", 10_000)  # isolate the time condition

    cfg = _cfg(min_chunk_seconds=0.5, max_unconfirmed_seconds=2.0, min_silence_ms=100_000)
    sink = RecSink()

    run_stream(
        cfg, ListSource([_loud(0.1)] * 60), FakeEngine(_stuck_tail_script), sink, language="en"
    )

    words = sink.final_words()
    assert "alpha" in words and "beta" in words
    assert any(w.startswith("tail") for w in words), "the stuck tail was never force-committed"


def test_forced_commit_after_n_updates_without_progress():
    # max_unconfirmed_seconds is far beyond the clip, so only the stalled-push counter can fire
    cfg = _cfg(min_chunk_seconds=0.5, max_unconfirmed_seconds=1000.0, min_silence_ms=100_000)
    sink = RecSink()

    run_stream(
        cfg, ListSource([_loud(0.1)] * 40), FakeEngine(_stuck_tail_script), sink, language="en"
    )

    assert any(w.startswith("tail") for w in sink.final_words())


def test_prompt_is_bounded():
    def script(audio, _i):
        n = len(audio) / SAMPLE_RATE
        return [Segment(0.0, n, " ".join(f"слово{i}" for i in range(400)), "en")]

    cfg = _cfg(min_chunk_seconds=0.5, min_silence_ms=100_000)
    engine = FakeEngine(script)

    run_stream(cfg, ListSource([_loud(0.1)] * 60), engine, RecSink(), language="en")

    assert max(len(c["prompt"] or "") for c in engine.calls) <= 600
