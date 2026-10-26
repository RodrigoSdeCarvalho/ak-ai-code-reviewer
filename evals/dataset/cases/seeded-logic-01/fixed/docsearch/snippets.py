"""Result snippets shown under each search hit."""

from __future__ import annotations

from dataclasses import dataclass

from docsearch.text import normalize, terms, words

DEFAULT_WIDTH = 24


@dataclass(frozen=True)
class Snippet:
    text: str
    truncated_start: bool
    truncated_end: bool

    def render(self) -> str:
        prefix = "... " if self.truncated_start else ""
        suffix = " ..." if self.truncated_end else ""
        return f"{prefix}{self.text}{suffix}"


def _first_match(tokens: list[str], wanted: set[str]) -> int | None:
    for position, token in enumerate(tokens):
        if normalize(token) in wanted:
            return position
    return None


def make_snippet(body: str, query: str, width: int = DEFAULT_WIDTH) -> Snippet:
    """Return `width` words of `body` centred on the first word that matches a query term.

    Near the end of the body the window slides back so it still shows `width` words. Without a
    matching term the snippet is the opening `width` words.
    """
    if width < 1:
        raise ValueError("width must be >= 1")
    tokens = words(body)
    hit = _first_match(tokens, set(terms(query)))
    if hit is None:
        start = 0
    else:
        start = max(0, min(hit - width // 2, len(tokens) - width))
    end = start + width
    shown = tokens[start:end]
    return Snippet(" ".join(shown), start > 0, end < len(tokens))


def preview(body: str, width: int = DEFAULT_WIDTH) -> str:
    """Plain preview for listings that have no query."""
    return make_snippet(body, "", width).render()
