"""Frequency-based keyword extraction for article tagging."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

WORD_RE = re.compile(r"[a-z][a-z0-9'-]*")

STOPWORDS = frozenset(
    {
        "about", "after", "also", "and", "are", "but", "can", "for", "from", "had",
        "has", "have", "her", "his", "into", "its", "more", "not", "our", "out",
        "over", "she", "than", "that", "the", "their", "them", "then", "there",
        "these", "they", "this", "was", "were", "what", "when", "which", "who",
        "will", "with", "would", "you", "your",
    }
)


@dataclass(frozen=True)
class Keyword:
    term: str
    score: float


def tokenize(text: str) -> list[str]:
    """Lower-case words with surrounding apostrophes and hyphens removed."""
    words = (word.strip("'-") for word in WORD_RE.findall(text.lower()))
    return [word for word in words if word]


def candidate_terms(text: str, min_length: int = 3) -> list[str]:
    """Tokens long enough to be meaningful and not in the stopword list."""
    return [word for word in tokenize(text) if len(word) >= min_length and word not in STOPWORDS]


def extract_keywords(body: str, limit: int = 5, min_length: int = 3) -> list[Keyword]:
    """Top `limit` terms by relative frequency, ties broken alphabetically."""
    counts = Counter(candidate_terms(body, min_length))
    total = sum(counts.values())
    if total == 0:
        return []
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [Keyword(term, round(count / total, 4)) for term, count in ranked[:limit]]
