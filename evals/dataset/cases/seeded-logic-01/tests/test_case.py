from docsearch.search import Document, Index
from docsearch.snippets import make_snippet, preview


def _body(n: int, marks: dict[int, str]) -> str:
    return " ".join(marks.get(i, f"w{i}") for i in range(n))


def test_match_near_the_start_of_a_long_body_is_shown():
    body = _body(100, {3: "Refund"})
    snippet = make_snippet(body, "refund policy", width=24)
    assert snippet.text.split() == [f"w{i}" if i != 3 else "Refund" for i in range(24)]
    assert not snippet.truncated_start
    assert snippet.truncated_end


def test_search_hit_snippet_contains_the_term():
    index = Index()
    index.add(Document("d1", "Refunds", _body(80, {1: "refunds,"})))
    index.add(Document("d2", "Shipping", _body(80, {50: "refunds"})))
    hits = index.search("refunds")
    assert [h.doc_id for h in hits] == ["d1", "d2"]
    assert all("refunds" in h.snippet for h in hits)


def test_match_in_the_middle_is_centred():
    snippet = make_snippet(_body(100, {50: "invoice"}), "invoice", width=10)
    assert snippet.text.split() == ["w45", "w46", "w47", "w48", "w49", "invoice", "w51", "w52", "w53", "w54"]
    assert snippet.truncated_start and snippet.truncated_end


def test_match_near_the_end_keeps_full_width():
    snippet = make_snippet(_body(100, {98: "invoice"}), "invoice", width=10)
    assert snippet.text.split()[-2:] == ["invoice", "w99"]
    assert len(snippet.text.split()) == 10
    assert snippet.truncated_start and not snippet.truncated_end


def test_short_body_and_no_match():
    assert make_snippet("Reset your password here.", "password", width=24).render() == "Reset your password here."
    assert preview(_body(30, {}), width=5) == "w0 w1 w2 w3 w4 ..."
    assert make_snippet(_body(30, {}), "missing", width=5).text == "w0 w1 w2 w3 w4"
