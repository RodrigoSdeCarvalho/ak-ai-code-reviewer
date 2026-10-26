import inspect

from readability.metrics import flesch_reading_ease, long_sentences, sentences, syllables, top_words, words
from readability.report import STOPWORDS, build_report, summary_line

TEXT = (
    "Reset your password from the sign-in page. Choose a new password and confirm it! "
    "The password must have twelve characters."
)


def test_words_and_sentences():
    assert words("Don't panic, it's fine.") == ["Don't", "panic", "it's", "fine"]
    assert sentences(TEXT) == [
        "Reset your password from the sign-in page",
        "Choose a new password and confirm it",
        "The password must have twelve characters",
    ]


def test_syllables():
    assert [syllables(w) for w in ["the", "table", "free", "make", "readability", "rhythm"]] == [1, 2, 1, 1, 5, 1]


def test_flesch_unchanged():
    assert flesch_reading_ease("The cat sat on the mat.") == 116.1
    assert flesch_reading_ease(TEXT) == 86.9
    assert flesch_reading_ease("") is None
    assert flesch_reading_ease("...") is None


def test_top_words_default_ignore_is_not_mutated_between_calls():
    default = inspect.signature(top_words).parameters["ignore"].default
    assert top_words("b a b c a b") == [("b", 3), ("a", 2), ("c", 1)]
    assert top_words("b a b c a b", 2, ["B"]) == [("a", 2), ("c", 1)]
    assert top_words("b a b c a b") == [("b", 3), ("a", 2), ("c", 1)]
    assert default == []


def test_caller_stopword_list_is_not_mutated():
    before = list(STOPWORDS)
    top_words(TEXT, 5, STOPWORDS)
    assert STOPWORDS == before


def test_long_sentences_and_report():
    long_text = " ".join(["word"] * 30) + ". Short one."
    assert long_sentences(long_text) == [" ".join(["word"] * 30)]
    report = build_report(TEXT)
    assert report.word_count == 21
    assert report.sentence_count == 3
    assert report.frequent_words[0] == ("password", 3)
    assert "the" not in dict(report.frequent_words)
    assert summary_line(report).startswith("21 words, 3 sentences, ease 86.9")
