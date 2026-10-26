"""In-memory inverted index over a small document collection."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from docsearch.snippets import make_snippet
from docsearch.text import terms


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    body: str


@dataclass(frozen=True)
class Hit:
    doc_id: str
    title: str
    score: int
    snippet: str


class Index:
    """Term-frequency index; documents are ranked by how often query terms occur in them."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._postings: defaultdict[str, Counter[str]] = defaultdict(Counter)

    def __len__(self) -> int:
        return len(self._docs)

    def add(self, doc: Document) -> None:
        if doc.doc_id in self._docs:
            raise ValueError(f"duplicate document id {doc.doc_id!r}")
        self._docs[doc.doc_id] = doc
        for term in terms(f"{doc.title} {doc.body}"):
            self._postings[term][doc.doc_id] += 1

    def search(self, query: str, limit: int = 10) -> list[Hit]:
        query_terms = terms(query)
        if not query_terms:
            return []
        scores: Counter[str] = Counter()
        for term in query_terms:
            for doc_id, count in self._postings.get(term, Counter()).items():
                scores[doc_id] += count
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        hits: list[Hit] = []
        for doc_id, score in ranked:
            doc = self._docs[doc_id]
            snippet = make_snippet(doc.body, query).render()
            hits.append(Hit(doc_id, doc.title, score, snippet))
        return hits
