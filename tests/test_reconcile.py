from gmst.reconcile import LocalAgreement, tokenize


def test_commits_only_the_agreed_prefix():
    la = LocalAgreement()
    assert la.push(tokenize("the quick brown")) == ([], ["the", "quick", "brown"])
    # second hypothesis agrees on "the quick brown", diverges after
    newly, pending = la.push(tokenize("the quick brown fox jumps"))
    assert newly == ["the", "quick", "brown"]
    assert pending == ["fox", "jumps"]


def test_committed_prefix_is_not_re_emitted():
    la = LocalAgreement()
    la.push(tokenize("hello world"))
    la.push(tokenize("hello world how"))          # commits hello, world
    newly, pending = la.push(tokenize("hello world how are you"))
    assert newly == ["how"]
    assert pending == ["are", "you"]


def test_realigns_when_model_re_emits_the_whole_utterance():
    la = LocalAgreement()
    la.push(tokenize("let us start"))
    la.push(tokenize("let us start with"))        # commits let, us, start
    assert la.committed == ["let", "us", "start"]
    # next decode returns the full sentence again, plus more
    newly, pending = la.push(tokenize("let us start with the project"))
    assert newly == ["with"]
    assert pending == ["the", "project"]
    assert la.committed == ["let", "us", "start", "with"]


def test_normalized_comparison_ignores_case_and_trailing_punctuation():
    la = LocalAgreement()
    la.push(tokenize("Привіт, світ"))
    newly, _ = la.push(tokenize("привіт світ!"))
    assert newly == ["привіт", "світ!"]  # agreement is normalized; the emitted form is verbatim


def test_flush_force_commits_pending_tail():
    la = LocalAgreement()
    la.push(tokenize("one two three"))
    la.push(tokenize("one two three four"))       # commits one two three
    assert la.flush() == ["four"]
    assert la.committed == ["one", "two", "three", "four"]


def test_stalled_pushes_counter():
    la = LocalAgreement()
    la.push(tokenize("a b c"))
    la.push(tokenize("x y z"))                    # no agreement
    la.push(tokenize("p q r"))                    # still none
    assert la.stalled_pushes == 2
    la.push(tokenize("p q r"))                    # now agrees
    assert la.stalled_pushes == 0


def test_revised_prefix_never_re_commits():
    la = LocalAgreement()
    la.push(tokenize("hello world"))
    la.push(tokenize("hello world foo"))          # commits hello, world
    assert la.committed == ["hello", "world"]

    # the model now revises a word it already emitted as final ("hello" -> "hi").
    # Committing from index 0 would put "hello world" in the transcript a second time.
    assert la.push(tokenize("hi world foo")) == ([], [])
    assert la.stalled_pushes == 1
    assert la.push(tokenize("hi world foo")) == ([], [])
    assert la.stalled_pushes == 2
    assert la.committed == ["hello", "world"]
    assert la.contradicted is True
    # and the caller is told to emit nothing at all, not even a partial
    assert la.last_offset == 3


def test_flush_drops_a_tail_it_cannot_place():
    la = LocalAgreement()
    la.push(tokenize("hello world"))
    la.push(tokenize("hello world foo"))          # commits hello, world
    la.push(tokenize("hi world foo"))             # contradicts the committed prefix
    assert la.flush() == []                       # dropping beats duplicating the utterance
    assert la.committed == ["hello", "world"]


def test_rebase_re_anchors_on_the_audio_that_survived_a_trim():
    la = LocalAgreement()
    la.push(tokenize("one two three"))
    la.push(tokenize("one two three four"))       # commits one two three
    # the pipeline trimmed everything before "three"; only it and the pending tail remain
    la.rebase(["three"], ["four"])
    assert la.committed == ["three"]
    # the shorter buffer re-transcribes as "three four five": "three" must not commit twice
    newly, pending = la.push(tokenize("three four five"))
    assert newly == ["four"]
    assert pending == ["five"]
    assert la.committed == ["three", "four"]


def test_reset_clears_state():
    la = LocalAgreement()
    la.push(tokenize("a b"))
    la.push(tokenize("a b c"))
    la.reset()
    assert la.committed == []
    assert la.push(tokenize("new start")) == ([], ["new", "start"])


def _spans(n, start=0.0, step=0.3):
    return [(start + i * step, start + (i + 1) * step) for i in range(n)]


def test_a_misheard_anchor_word_does_not_block_the_utterance():
    """After a trim the last committed word is decoded again; a real model may hear it differently
    ("idle" -> "title"). With word times the reconciler places it by time, not by text, so the
    rest of the utterance still commits (R1: text-only alignment lost ~85 % of a real stream)."""
    la = LocalAgreement()
    la.push(["a", "b"], _spans(2))
    assert la.push(["a", "b", "c"], _spans(3))[0] == ["a", "b"]
    la.rebase(["b"], ["c"], spans=_spans(2))  # the trim kept "b" (committed) and "c" (pending)

    newly, pending = la.push(["bee", "c", "d"], _spans(3))
    assert not la.contradicted
    assert newly == ["c"] and pending == ["d"]
    assert "bee" not in la.committed


def test_a_dropped_anchor_word_does_not_block_the_utterance():
    la = LocalAgreement()
    la.push(["a", "b"], _spans(2))
    la.push(["a", "b", "c"], _spans(3))
    la.rebase(["b"], ["c"], spans=_spans(2))

    newly, _ = la.push(["c", "d"], _spans(2, start=0.3))  # the model skipped the re-heard "b"
    assert not la.contradicted
    assert newly == ["c"]


def test_a_repeated_committed_ngram_timed_past_the_boundary_is_not_committed_again():
    """Timestamps drift: the re-heard committed words can be timed after the committed end. A
    mis-heard head defeats the text prefix match, time drops only that head, and the n-gram
    de-dup must still recognise "a b" as already committed."""
    la = LocalAgreement()
    la.push(["a", "b"], _spans(2))
    la.push(["a", "b", "c"], _spans(3))
    la.rebase(["a", "b"], ["c"], spans=_spans(3))  # committed end = 0.6 s

    hyp = ["uh", "a", "b", "c"]
    newly, _ = la.push(hyp, [(0.0, 0.2), (0.8, 1.0), (1.0, 1.2), (1.2, 1.5)])
    assert newly == ["c"]
    assert la.committed == ["a", "b", "c"]


def test_absorb_commits_a_contradicting_tail_rather_than_dropping_it():
    """Shutdown only: no later decode can recover the tail, so a contradiction (text-only
    alignment) still commits everything — losing the meeting's last words is the worse failure."""
    la = LocalAgreement()
    la.push(tokenize("the quick brown"))
    la.push(tokenize("the quick brown"))
    start = la.absorb(tokenize("the quick brownish fox"))
    assert start == 0
    assert la.committed[-2:] == ["brownish", "fox"]


def test_a_new_word_stretched_back_to_the_buffer_head_is_kept():
    """Seen with faster-whisper after a trim (F.8 trace): the anchor word is not re-emitted and
    the first *new* word is timed from 0.00 ("for@0.00-0.56" with the committed end at 0.42).
    Its end is past the committed audio, so it is new speech and must not be dropped."""
    la = LocalAgreement()
    la.push(["was", "idle"], _spans(2))
    la.push(["was", "idle", "for"], _spans(3))
    la.rebase(["idle"], ["for"], spans=[(0.2, 0.42), (0.42, 0.68)])

    hyp, spans = ["for", "him", "to"], [(0.0, 0.56), (0.56, 0.94), (0.94, 1.1)]
    newly, _ = la.push(hyp, spans)
    assert newly == ["for"]
    newly, _ = la.push(hyp + ["move"], spans + [(1.1, 1.3)])
    assert newly == ["him", "to"]


def test_a_punctuation_only_token_does_not_block_agreement():
    """R1: a standalone dash normalizes to "" and never agreed, stalling every word after it."""
    la = LocalAgreement()
    la.push(["Так", "-", "звісно,", "давайте"])
    newly, _ = la.push(["Так", "-", "звісно,", "давайте", "далі"])
    assert newly == ["Так", "-", "звісно,", "давайте"]
