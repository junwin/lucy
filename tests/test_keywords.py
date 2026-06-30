import pytest

from src.keywords.keywords import Keywords


class FakeToken:
    def __init__(self, text, lemma_, *, is_punct=False, pos_="NOUN"):
        self.text = text
        self.lemma_ = lemma_
        self.is_punct = is_punct
        self.is_space = False
        self.pos_ = pos_


class FakeDoc(list):
    pass


def make_fake_nlp(tokens):
    def _nlp(_text):
        return FakeDoc(tokens)

    return _nlp


@pytest.fixture
def keywords(monkeypatch):
    # Avoid spaCy model loading + NLTK data checks
    monkeypatch.setattr(Keywords, "_initialize_nlp_model", lambda self: None)
    kw = Keywords(language_code="en")
    return kw


def test_extract_keywords_filters_stopwords_punct_and_respects_top_n(keywords, monkeypatch):
    """POS filter has been removed, so ADV tokens like 'quickly' are no
    longer excluded by POS. Stopwords, punctuation, and custom excludes
    still work."""
    import src.keywords.keywords as kw_mod

    monkeypatch.setattr(kw_mod, "STOP_WORDS", {"the", "and"})

    tokens = [
        FakeToken("the", "the", pos_="DET"),       # stopword -> dropped
        FakeToken(",", ",", is_punct=True, pos_="PUNCT"),  # punct -> dropped
        FakeToken("Cats", "cat", pos_="NOUN"),
        FakeToken("cats", "cat", pos_="NOUN"),
        FakeToken("run", "run", pos_="VERB"),       # in DEFAULT_CUSTOM_EXCLUDE -> dropped
        FakeToken("quickly", "quickly", pos_="ADV"),
        FakeToken("and", "and", pos_="CCONJ"),      # stopword -> dropped
        FakeToken("Dogs", "dog", pos_="PROPN"),
    ]

    keywords.nlp = make_fake_nlp(tokens)

    # cat appears twice, quickly appears once, dog appears once
    # top_n=3 should return all three
    result = keywords.extract_keywords("ignored", top_n=3)
    assert result == ["cat", "quickly", "dog"], f"Got: {result}"


def test_extract_keywords_retains_nouns_mistagged_as_verb(keywords, monkeypatch):
    """Domain terms like 'endpoints' that spaCy mis-tags as VERB should
    still be retained after removing the POS filter."""
    import src.keywords.keywords as kw_mod

    monkeypatch.setattr(kw_mod, "STOP_WORDS", set())

    tokens = [
        FakeToken("endpoints", "endpoint", pos_="VERB"),
        FakeToken("database", "database", pos_="NOUN"),
    ]

    keywords.nlp = make_fake_nlp(tokens)

    result = keywords.extract_keywords("ignored", top_n=10)
    assert "endpoint" in result, (
        f"'endpoint' should be in extracted keywords when 'endpoints' is "
        f"tagged as VERB. Got: {result}"
    )
    assert "database" in result, (
        f"'database' (NOUN) should still be in extracted keywords. Got: {result}"
    )


def test_extract_keywords_request_keywords_fenced_block_parsing(keywords):
    content = """please do this\nrequest keywords:\n```alpha, beta,gamma```\nthanks"""
    # Current implementation splits by comma and does not strip whitespace
    assert keywords.extract_keywords(content, top_n=10) == ["alpha", " beta", "gamma"]


def test_get_specified_keywords_returns_empty_when_missing(keywords):
    assert keywords.get_specified_keywords("no fenced block here") == []


def test_compare_keywords_and_or_and_invalid_operator(keywords):
    assert keywords.compare_keywords({"a", "b"}, {"b", "a"}, operator="and") is True
    assert keywords.compare_keywords({"a", "b"}, {"b", "c"}, operator="and") is False

    assert keywords.compare_keywords({"a", "b"}, {"c", "b"}, operator="or") is True
    assert keywords.compare_keywords({"a"}, {"b"}, operator="or") is False

    with pytest.raises(ValueError):
        keywords.compare_keywords({"a"}, {"a"}, operator="xor")


def test_compare_semantic_similarity_identical_is_1_and_different_is_lower(keywords):
    assert keywords.compare_semantic_similarity("cat dog", "cat dog") == 1.0
    sim = keywords.compare_semantic_similarity("cat dog", "banana orange")
    assert sim < 1.0
    # ensure rounding to 6 decimals
    assert sim == round(sim, 6)


def test_compare_keyword_lists_semantic_similarity_identical_is_1_and_different_is_lower(keywords):
    assert keywords.compare_keyword_lists_semantic_similarity(["cat", "dog"], ["cat", "dog"]) == 1.0
    sim = keywords.compare_keyword_lists_semantic_similarity(["cat", "dog"], ["banana", "orange"])
    assert sim < 1.0
    assert sim == round(sim, 6)
