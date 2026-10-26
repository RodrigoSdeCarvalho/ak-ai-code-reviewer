from textkit.keywords import extract_keywords
from textkit.tagger import Article, suggest_tags

BODY = (
    "The school installed solar panels last spring. Solar panels now power the school library "
    "and the school gym. A grant paid for the panels and a second grant paid for battery storage. "
    "Battery storage keeps the school running after dark."
)


def test_ranking_without_title_is_by_body_frequency():
    keywords = extract_keywords(BODY, limit=4)
    assert [kw.term for kw in keywords] == ["school", "panels", "battery", "grant"]
    assert keywords[0].score == 0.1429


def test_title_terms_get_a_bonus_on_top_of_their_frequency():
    plain = {kw.term: kw.score for kw in extract_keywords(BODY, limit=30)}
    boosted = {kw.term: kw.score for kw in extract_keywords(BODY, limit=30, title="Solar at school")}
    assert boosted["solar"] == round(plain["solar"] + 0.1, 4)
    assert boosted["school"] == round(plain["school"] + 0.1, 4)
    assert boosted["panels"] == plain["panels"] == 0.1071
    assert boosted["battery"] == plain["battery"]


def test_title_bonus_reorders_but_keeps_body_terms():
    terms = [kw.term for kw in extract_keywords(BODY, limit=4, title="Solar power for schools")]
    assert terms == ["solar", "school", "power", "panels"]


def test_suggested_tags_include_body_terms_not_in_title():
    article = Article("solar-school", "Solar at school", BODY, tags=["School"])
    assert suggest_tags(article, max_tags=3) == ["solar", "panels", "battery"]


def test_empty_body_has_no_keywords():
    assert extract_keywords("the and of", title="Anything") == []
