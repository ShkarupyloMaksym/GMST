from gmst.transcribe.lid import resolve_language

KW = {"threshold": 0.7, "tiebreak_margin": 0.15}


def test_confident_detection_is_kept():
    assert resolve_language("uk", 0.95, [("uk", 0.95), ("ru", 0.02)], prev_lang="en", **KW) == (
        "uk",
        0.95,
    )


def test_low_confidence_sticks_to_previous():
    lang, prob = resolve_language("de", 0.30, [("de", 0.30), ("en", 0.25)], prev_lang="en", **KW)
    assert lang == "en"
    assert prob == 0.30


def test_low_confidence_with_no_previous_takes_raw():
    assert resolve_language("de", 0.30, None, prev_lang=None, **KW) == ("de", 0.30)


def test_uk_ru_tiebreak_prefers_uk():
    lang, prob = resolve_language(
        "ru", 0.52, [("ru", 0.52), ("uk", 0.44)], prev_lang="en", **KW
    )
    assert lang == "uk"
    assert prob == 0.44


def test_tiebreak_still_respects_the_sticky_threshold():
    # a near-silent segment: uk/ru are the top pair, but the detector is not confident about
    # anything. Flipping an English meeting to uk on 0.11 would then stick for every utterance.
    lang, _ = resolve_language(
        "ru", 0.11, [("ru", 0.11), ("uk", 0.10)], prev_lang="en", **KW
    )
    assert lang == "en"


def test_tiebreak_wins_when_the_pair_is_jointly_confident():
    # 0.52 + 0.44 = 0.96 > threshold: we are sure it is Slavic, just not which one -> uk
    lang, prob = resolve_language(
        "ru", 0.52, [("ru", 0.52), ("uk", 0.44)], prev_lang="en", **KW
    )
    assert (lang, prob) == ("uk", 0.44)


def test_tiebreak_takes_uk_when_there_is_no_previous_language():
    lang, _ = resolve_language("ru", 0.11, [("ru", 0.11), ("uk", 0.10)], prev_lang=None, **KW)
    assert lang == "uk"


def test_uk_ru_gap_too_wide_no_tiebreak():
    lang, _ = resolve_language("ru", 0.85, [("ru", 0.85), ("uk", 0.05)], prev_lang="en", **KW)
    assert lang == "ru"
