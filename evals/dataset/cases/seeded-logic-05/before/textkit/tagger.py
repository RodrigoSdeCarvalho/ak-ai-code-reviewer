"""Suggest tags for articles before they are sent to the editors' queue."""

from __future__ import annotations

from dataclasses import dataclass, field

from textkit.keywords import extract_keywords

MAX_TAGS = 5
MIN_SCORE = 0.05


@dataclass
class Article:
    slug: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)


def suggest_tags(article: Article, max_tags: int = MAX_TAGS) -> list[str]:
    """Keywords above MIN_SCORE that the article is not already tagged with."""
    existing = {tag.lower() for tag in article.tags}
    keywords = extract_keywords(article.body, limit=max_tags + len(existing))
    suggestions = [kw.term for kw in keywords if kw.score >= MIN_SCORE and kw.term not in existing]
    return suggestions[:max_tags]


def tag_batch(articles: list[Article], max_tags: int = MAX_TAGS) -> dict[str, list[str]]:
    """Suggested tags per article slug, skipping articles with an empty body."""
    return {
        article.slug: suggest_tags(article, max_tags)
        for article in articles
        if article.body.strip()
    }


def apply_suggestions(article: Article, suggestions: list[str]) -> Article:
    """A copy of the article with accepted suggestions appended, without duplicates."""
    existing = {tag.lower() for tag in article.tags}
    added = [tag for tag in suggestions if tag.lower() not in existing]
    return Article(article.slug, article.title, article.body, [*article.tags, *added])
