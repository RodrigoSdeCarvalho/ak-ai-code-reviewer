"""Tokenising helpers shared by the index and the snippet builder."""

from __future__ import annotations

import re
import unicodedata

_WORD_RE = re.compile(r"\S+")
_EDGE_PUNCT = ".,;:!?\"'()[]{}"

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
)


def words(text: str) -> list[str]:
    """Split on whitespace, keeping punctuation attached so snippets read naturally."""
    return _WORD_RE.findall(text)


def normalize(word: str) -> str:
    """Lower-case `word` and strip accents and surrounding punctuation."""
    stripped = word.strip(_EDGE_PUNCT)
    decomposed = unicodedata.normalize("NFKD", stripped)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return ascii_only.casefold()


def terms(text: str) -> list[str]:
    """Normalised index terms of `text`, without stopwords or empty tokens."""
    out: list[str] = []
    for word in words(text):
        term = normalize(word)
        if term and term not in STOPWORDS:
            out.append(term)
    return out
