---
tags:
  - str
  - keyword
  - set
  - module
  - top_n
  - int
  - float
  - doc
  - source
  - extraction
  - src/keywords
---

# `src/keywords`

## Source files
- `src/keywords/keywords.py`

## Key classes
- **`Keywords`** (`src/keywords/keywords.py`)
  - Extracts keywords from text using spaCy (POS + lemmatization) and frequency counting.
  - Supports a “request keywords:” escape hatch to accept explicitly provided keywords.
  - Provides semantic similarity helpers (TF‑IDF cosine similarity when sklearn is available; otherwise a lightweight fallback).

## Dependencies
- **stdlib**: `typing` (`List`, `Dict`, `Set`), `collections.Counter`, `datetime`, `re`
- **third-party**:
  - **NLTK**: `nltk`, `nltk.tokenize.word_tokenize`, `nltk.stem.SnowballStemmer`, `nltk.corpus.wordnet`
  - **spaCy** (lazy import in `_initialize_nlp_model`): loads `en_core_web_sm` or `es_core_news_sm`; uses spaCy `STOP_WORDS`
  - **scikit-learn** (optional): `TfidfVectorizer`, `cosine_similarity` (preferred implementation)

## Main service/base class: `Keywords`

### Methods
- `__init__(language_code: str = "en")`
- `_initialize_nlp_model()`
  - Imports/loads spaCy model, ensures required NLTK data is present, and populates module-level `STOP_WORDS`.
- `extract_from_content(content: str, top_n: int = 10) -> List[str]`
- `extract_keywords(content: str, top_n: int = 10) -> List[str]`
  - Lowercases, runs spaCy, filters to `PROPN`/`NOUN`, lemmatizes, removes stopwords + custom excludes + code-like tokens, then returns top-N by frequency.
- `get_specified_keywords(input_str: str) -> List[str]`
  - Extracts comma-separated keywords from a fenced code block.
- `compare_keyword_lists_semantic_similarity(keywords1: List[str], keywords2: List[str]) -> float`
- `compare_semantic_similarity(text1: str, text2: str) -> float`
  - Uses sklearn TF‑IDF cosine similarity when available; otherwise uses a token-frequency cosine similarity fallback.
- `compare_keywords(set1: set, set2: set, operator: str = "and") -> bool`
  - `and`: exact set equality; `or`: any intersection.
- `concatenate_keywords(keyword_list: List[str]) -> str`

## Other module-level items
- `ensure_nltk_data(*, logger=None) -> None` (auto-downloads required NLTK datasets, currently `punkt`)
- Constants/regex:
  - `DEFAULT_CUSTOM_EXCLUDE`, `STOP_WORDS`
  - `CODELIKE_RE` (paths/filenames), `SYMBOL_RE` (symbol-only tokens)
