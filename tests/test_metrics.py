from gmst.metrics import normalize_token, normalize_words, word_error_rate
from gmst.reconcile import _norm


def test_normalize_strips_punctuation_and_case():
    assert normalize_words("Hello, WORLD! it's fine—ok") == ["hello", "world", "it's", "fine", "ok"]


def test_normalize_token_drops_edge_quotes_and_dashes_but_keeps_internal_ones():
    assert normalize_token("'Hello'") == "hello"
    assert normalize_token("—well-known—") == "well-known"
    assert normalize_token("it's") == "it's"
    assert normalize_token("...") == ""


def test_apostrophe_variants_are_unified():
    assert normalize_token("don’t") == normalize_token("don't") == "don't"
    assert normalize_words("п’ять") == normalize_words("п'ять")


def test_reconcile_and_wer_share_one_normalizer():
    assert _norm is normalize_token


def test_wer_identical_is_zero():
    assert word_error_rate("привіт світ", "привіт світ") == 0.0


def test_wer_one_substitution_in_four():
    assert word_error_rate("the quick brown fox", "the quick brown dog") == 0.25


def test_wer_empty_reference():
    assert word_error_rate("", "") == 0.0
    assert word_error_rate("", "spurious") == 1.0


def test_wer_deletion_and_insertion():
    # ref 3 words, hyp drops one and adds one -> 2 edits / 3
    assert word_error_rate("one two three", "one three four") == 2 / 3


def test_wer_splits_hyphenated_words_on_both_sides():
    # R5: CV10 refs write "що-небудь", models often "що небудь" -> WER 2.0 before
    assert normalize_words("що-небудь") == ["що", "небудь"]
    assert word_error_rate("що-небудь", "що небудь") == 0.0
    assert normalize_token("well-known") == "well-known"  # reconcile's token identity unchanged


def test_word_errors_gives_the_counts_corpus_wer_needs():
    from gmst.metrics import word_errors

    assert word_errors("one two three", "one three four") == (2, 3)
    assert word_errors("", "spurious") == (1, 0)
