"""Result snippets shown under each search hit."""

from __future__ import annotations

from dataclasses import dataclass

from docsearch.text import words

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


def make_snippet(body: str, query: str, width: int = DEFAULT_WIDTH) -> Snippet:
    """Return the opening `width` words of `body`.

    `query` is accepted so callers do not change when snippets start following the match.
    """
    if width < 1:
        raise ValueError("width must be >= 1")
    tokens = words(body)
    shown = tokens[:width]
    return Snippet(" ".join(shown), False, len(tokens) > width)


def preview(body: str, width: int = DEFAULT_WIDTH) -> str:
    """Plain preview for listings that have no query."""
    return make_snippet(body, "", width).render()
