"""Text statistics for the readability checker."""

from __future__ import annotations

import re
from collections import Counter

WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SENTENCE_END = re.compile(r"[.!?]+(?:\s+|$)")
VOWEL_GROUPS = re.compile(r"[aeiouy]+")


def words(text: str) -> list[str]:
    return WORD.findall(text)


def sentences(text: str) -> list[str]:
    parts = SENTENCE_END.split(text.strip())
    return [p for p in parts if p.strip()]


def syllables(word: str) -> int:
    """Estimated syllables: vowel groups, minus a silent final `e`, at least one."""
    w = word.lower()
    n = len(VOWEL_GROUPS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(n, 1)


def flesch_reading_ease(text: str) -> float | None:
    """Flesch reading-ease score rounded to one decimal, or None for text without words."""
    all_words = words(text)
    all_sentences = sentences(text)
    if not all_words or not all_sentences:
        return None
    total_syllables = sum(syllables(w) for w in all_words)
    return round(206.835 - 1.015 * (len(all_words) / len(all_sentences)) - 84.6 * (total_syllables / len(all_words)), 1)


def top_words(text: str, n: int = 10, ignore: list[str] = []) -> list[tuple[str, int]]:
    """The `n` most frequent lower-cased words not in `ignore`, ties broken alphabetically."""
    skip = {w.lower() for w in ignore}
    counts = Counter(w.lower() for w in words(text) if w.lower() not in skip)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def long_sentences(text: str, limit: int = 25) -> list[str]:
    return [s for s in sentences(text) if len(words(s)) > limit]
