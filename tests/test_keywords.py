import pytest
from src.keywords import Keywords  # Assuming that the above class is saved in a file called keywords.py


@pytest.fixture(scope="module")
def keywords_obj():
    return Keywords()

def test_extract_from_content(keywords_obj):
    content = "The quick brown fox jumped over the lazy dog"
    # should produce['fox', 'jump', 'dog']
    result = keywords_obj.extract_from_content(content, top_n=5)
    assert isinstance(result, list)
    assert len(result) == 3

def test_extract_keywords(keywords_obj):
    content = "The quick brown fox jumped over the lazy dog"
    # should produce['fox', 'jump', 'dog']
    result = keywords_obj.extract_keywords(content, top_n=5)
    assert isinstance(result, list)
    assert len(result) == 3

def test_get_specified_keywords(keywords_obj):
    input_str = "```dog,cat,bird```"
    result = keywords_obj.get_specified_keywords(input_str)
    assert result == ['dog', 'cat', 'bird']

def test_compare_keyword_lists_semantic_similarity(keywords_obj):
    keywords1 = ['dog', 'cat', 'bird']
    keywords2 = ['dog', 'cat', 'bird']
    result = keywords_obj.compare_keyword_lists_semantic_similarity(keywords1, keywords2)
    assert result == 1.0

def test_compare_semantic_similarity(keywords_obj):
    text1 = "dog cat bird"
    text2 = "dog cat bird"
    result = keywords_obj.compare_semantic_similarity(text1, text2)
    assert round(result,8) == 1.0

def test_compare_keywords(keywords_obj):
    set1 = {'dog', 'cat', 'bird'}
    set2 = {'dog', 'cat', 'bird'}
    result = keywords_obj.compare_keywords(set1, set2, operator="and")
    assert result is True

def test_concatenate_keywords(keywords_obj):
    keyword_list = ['dog', 'cat', 'bird']
    result = keywords_obj.concatenate_keywords(keyword_list)
    assert result == 'dog cat bird'
