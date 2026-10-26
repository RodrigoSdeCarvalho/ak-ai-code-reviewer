"""Readability report shown next to an article in the help-centre editor."""

from __future__ import annotations

from dataclasses import dataclass, field

from readability.metrics import flesch_reading_ease, long_sentences, sentences, top_words, words

STOPWORDS = [
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "with", "you", "your",
]
TARGET_EASE = 60.0


@dataclass
class Report:
    word_count: int
    sentence_count: int
    reading_ease: float | None
    frequent_words: list[tuple[str, int]]
    long_sentences: list[str] = field(default_factory=list)

    @property
    def needs_work(self) -> bool:
        if self.reading_ease is not None and self.reading_ease < TARGET_EASE:
            return True
        return bool(self.long_sentences)


def build_report(article: str, sentence_limit: int = 25) -> Report:
    """Readability figures for one article body (plain text)."""
    return Report(
        word_count=len(words(article)),
        sentence_count=len(sentences(article)),
        reading_ease=flesch_reading_ease(article),
        frequent_words=top_words(article, 5, STOPWORDS),
        long_sentences=long_sentences(article, sentence_limit),
    )


def summary_line(report: Report) -> str:
    ease = "n/a" if report.reading_ease is None else f"{report.reading_ease:.1f}"
    flag = " - needs work" if report.needs_work else ""
    return f"{report.word_count} words, {report.sentence_count} sentences, ease {ease}{flag}"
