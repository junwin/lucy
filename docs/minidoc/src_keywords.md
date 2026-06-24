---
tags:
  - src_keywords
  - lucyproject
  - Keywords
  - extract_keywords
  - semantic_similarity
  - NLP
  - spaCy
  - NLTK
  - TF-IDF
---

# Module: `src.keywords`

## Summary

The `src.keywords` module provides **keyword extraction and comparison** for Lucy's document indexing and search pipeline. It wraps spaCy (primary) and NLTK (tokenization) to extract meaningful keywords from text, and offers both set-based and semantic-similarity comparison methods. The module is designed to work with a fallback TF-IDF implementation when scikit-learn is unavailable.

## Key Classes

| Class | Purpose |
|---|---|
| `Keywords` | Manages keyword extraction from text, keyword list comparison (set overlap, semantic similarity), and concatenation. |

## Source Files

| File | Description |
|---|---|
| `keywords.py` | Single-file module — contains the `Keywords` class, helper functions (`ensure_nltk_data`), regex constants (`CODELIKE_RE`, `SYMBOL_RE`), and exclusion sets (`DEFAULT_CUSTOM_EXCLUDE`, `STOP_WORDS`). |

No `__init__.py` — the module is imported directly as `src.keywords.keywords`.

## Dependencies

- **Standard library**: `typing`, `collections.Counter`, `datetime`, `re`, `math`
- **Third-party (required)**: `nltk` (tokenization, SnowballStemmer, wordnet), `spacy` (NLP model loading, stop words)
- **Third-party (optional)**: `scikit-learn` (TfidfVectorizer, cosine_similarity — used for better semantic similarity; falls back to pure-Python implementation)
- **Internal**: none

## Methods — `Keywords`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(language_code: str = "en")` | Initialize with language code; loads spaCy model and ensures NLTK data. |
| `_initialize_nlp_model` | instance | `() -> None` | Load spaCy model (`en_core_web_sm` or `es_core_news_sm`), set `STOP_WORDS`. Raises `RuntimeError` on failure. |
| `extract_from_content` | instance | `(content: str, top_n: int = 10) -> List[str]` | Alias for `extract_keywords`. |
| `extract_keywords` | instance | `(content: str, top_n: int = 10) -> List[str]` | Main extraction: lowercases, POS-filters (PROPN, NOUN), lemmatizes, removes stop words / code-like tokens / symbols, returns top-N by frequency. |
| `get_specified_keywords` | instance | `(input_str: str) -> List[str]` | Parse keywords from a code-fenced block in the input string (for `request keywords:` prefix). |
| `compare_keyword_lists_semantic_similarity` | instance | `(keywords1: List[str], keywords2: List[str]) -> float` | Concatenate two keyword lists and compare via `compare_semantic_similarity`. |
| `compare_semantic_similarity` | instance | `(text1: str, text2: str) -> float` | Compute cosine similarity between two texts. Uses scikit-learn's TfidfVectorizer if available, otherwise falls back to a pure-Python token-frequency vector implementation. |
| `compare_keywords` | instance | `(set1: set, set2: set, operator: str = "and") -> bool` | Compare two keyword sets with `"and"` (exact match) or `"or"` (any overlap). |
| `concatenate_keywords` | instance | `(keyword_list: List[str]) -> str` | Join a list of keywords into a single space-separated string. |

## Module-level helpers

| Function | Signature | Description |
|---|---|---|
| `ensure_nltk_data` | `(*, logger=None) -> None` | Auto-download required NLTK datasets (`punkt`) on first run. |
