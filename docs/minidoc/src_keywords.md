---
tags:
  - spacy
  - module
  - nltk
  - keyword
  - word
  - extraction
  - comparison
  - nlp
  - punkt
  - similarity
  - src/keywords
  - lucyproject
---

# Module: `src/keywords`

## Source files

| File | Description |
|------|-------------|
| `src/keywords/keywords.py` | All module code (no `__init__.py`) |

## Key class: `Keywords`

Manages keyword extraction and comparison for conversation context.

**Attributes:**
- `language_code` (`str`) — language code for NLP processing
- `nlp` — spaCy language model instance

## Dependencies

| Type | Packages |
|------|----------|
| External | `spacy`, `nltk`, `sklearn` (optional), `collections.Counter`, `re`, `datetime`, `math` |
| Internal | None (standalone module) |

## Methods on `Keywords`

| Method | Description |
|--------|-------------|
| `__init__(language_code="en")` | Initializes language code and loads spaCy model |
| `_initialize_nlp_model()` | Lazy-loads spaCy, downloads NLTK punkt, sets `STOP_WORDS` |
| `extract_from_content(content, top_n=10)` | Alias for `extract_keywords` |
| `extract_keywords(content, top_n=10)` | Main extraction: lowercases, POS-filters (PROPN, NOUN), lemmatizes, removes stop words / custom excludes / code-like tokens, returns top_n by frequency |
| `get_specified_keywords(input_str)` | Parses keywords from a ` ```...``` ` block in the input |
| `compare_keyword_lists_semantic_similarity(keywords1, keywords2)` | Concatenates lists then calls `compare_semantic_similarity` |
| `compare_semantic_similarity(text1, text2)` | TF-IDF cosine similarity via sklearn, falls back to simple token-frequency cosine |
| `compare_keywords(set1, set2, operator="and")` | Set comparison with `"and"` (exact match) or `"or"` (any overlap) |
| `concatenate_keywords(keyword_list)` | Joins list into space-separated string |

## Module-level helpers

| Name | Description |
|------|-------------|
| `ensure_nltk_data(logger=None)` | Auto-downloads NLTK punkt if missing |
| `CODELIKE_RE` | Regex to detect file paths and filenames |
| `SYMBOL_RE` | Regex to detect pure-symbol tokens |
| `DEFAULT_CUSTOM_EXCLUDE` | Set of common noise words to filter out |
| `STOP_WORDS` | Module-level set populated from spaCy stop words |
