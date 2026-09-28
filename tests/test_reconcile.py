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
