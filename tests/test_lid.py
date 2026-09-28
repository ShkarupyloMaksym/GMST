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


# --- lid_languages (DECIDE-02): the detector is restricted to the meeting's languages ---------

EN_UK = ("en", "uk")


def test_restricted_lid_never_returns_a_language_outside_the_meeting():
    # R2: small labelled a Ukrainian clip "bg"; tiny "tr", "ja", "ar" — and decoded in that script
    probs = [("bg", 0.40), ("uk", 0.30), ("ru", 0.20), ("en", 0.05)]
    lang, prob = resolve_language("bg", 0.40, probs, prev_lang=None, allowed=EN_UK, **KW)
    assert lang == "uk"
    assert prob == 0.5  # uk + ru, the Slavic mass folded into the allowed "uk"


def test_restricted_lid_covers_the_first_utterance_of_a_meeting():
    # R2: "LID on 2.00s prev=None raw=ar@0.21 -> used ar" -> Arabic-script transcript
    probs = [("ar", 0.21), ("ru", 0.15), ("uk", 0.10), ("en", 0.05)]
    lang, _ = resolve_language("ar", 0.21, probs, prev_lang=None, allowed=EN_UK, **KW)
    assert lang == "uk"


def test_restricted_lid_folds_ru_into_uk_even_when_ru_clearly_wins():
    # R2: "uk-3541 top3=[('ru', 0.972), ('uk', 0.012)]" on Ukrainian speech, far outside the margin
    probs = [("ru", 0.972), ("uk", 0.012), ("en", 0.004)]
    lang, _ = resolve_language("ru", 0.972, probs, prev_lang="en", allowed=EN_UK, **KW)
    assert lang == "uk"


def test_restricted_lid_stays_sticky_when_no_allowed_language_is_confident():
    # the noise case the tie-break rule was written for: uk+ru = 0.21 must not flip English to uk
    probs = [("ru", 0.11), ("uk", 0.10), ("en", 0.01)]
    lang, _ = resolve_language("ru", 0.11, probs, prev_lang="en", allowed=EN_UK, **KW)
    assert lang == "en"


def test_restricted_lid_keeps_confident_english():
    probs = [("en", 0.90), ("uk", 0.03)]
    assert resolve_language("en", 0.90, probs, prev_lang="uk", allowed=EN_UK, **KW) == ("en", 0.90)


def test_restricted_lid_with_ru_allowed_uses_the_tiebreak():
    probs = [("ru", 0.52), ("uk", 0.44), ("en", 0.02)]
    lang, _ = resolve_language("ru", 0.52, probs, prev_lang="en", allowed=("en", "uk", "ru"), **KW)
    assert lang == "uk"


def test_restricted_lid_without_a_distribution_never_leaves_the_allowed_set():
    assert resolve_language("de", 0.9, None, prev_lang="en", allowed=EN_UK, **KW)[0] == "en"
    assert resolve_language("de", 0.9, None, prev_lang=None, allowed=EN_UK, **KW)[0] == "en"
    assert resolve_language("ru", 0.9, None, prev_lang=None, allowed=EN_UK, **KW)[0] == "uk"
