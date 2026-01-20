---
tags:
  - keywords
  - Keywords
  - spacy
  - nltk
  - tfidf
  - cosine_similarity
---

# src.keywords

Short description: Keyword extraction and keyword similarity utilities. Uses spaCy for tokenization/lemmatization and TF‑IDF cosine similarity for semantic comparison.

## Python files and key classes

- `Keywords` — `src/keywords/keywords.py`

## Keywords (class)

### Purpose
- Extract a small set of representative keywords from a text string (typically conversation content).
- Compare keyword lists / texts for similarity.

### Key attributes
- `language_code: str` — language selector (currently `"en"` default, `"es"` supported for spaCy model loading).
- `nlp` — spaCy model instance loaded by `_initialize_nlp_model()`.

### Initialization / dependencies
- Loads spaCy model:
  - English: `en_core_web_sm`
  - Spanish: `es_core_news_sm`
- Verifies NLTK tokenizer data exists: `nltk.data.find("tokenizers/punkt")`
  - If missing, raises: `RuntimeError("NLTK data not found. Please run nltk.download('punkt') manually.")`

### Keyword extraction
- `extract_from_content(content: str, top_n: int = 10) -> List[str]`
  - Thin wrapper around `extract_keywords`.

- `extract_keywords(content: str, top_n: int = 10) -> List[str]`
  - Special case: if the text contains `"request keywords:"`, it will parse keywords from a fenced code block via `get_specified_keywords()`.
  - Otherwise:
    - lowercases content
    - spaCy parse
    - removes punctuation tokens
    - removes stop words (`spacy.lang.en.STOP_WORDS`)
    - keeps only tokens with POS in `["PROPN", "NOUN", "VERB"]`
    - lemmatizes
    - counts frequency (`collections.Counter`)
    - returns `top_n` most common lemmas

- `get_specified_keywords(input_str: str) -> List[str]`
  - Extracts text inside triple backticks ```...``` and splits by comma.
  - Returns `[]` if no fenced block is found.

### Similarity / comparison
- `compare_keyword_lists_semantic_similarity(keywords1: List[str], keywords2: List[str]) -> float`
  - Joins each list into a single string and compares via TF‑IDF cosine similarity.
  - Returns rounded to 6 decimals.

- `compare_semantic_similarity(text1: str, text2: str) -> float`
  - Uses `sklearn.feature_extraction.text.TfidfVectorizer`
  - Uses `sklearn.metrics.pairwise.cosine_similarity`
  - Returns rounded to 6 decimals.

- `compare_keywords(set1: set, set2: set, operator: str = "and") -> bool`
  - `"and"`: exact set equality
  - `"or"`: any intersection
  - else: raises `ValueError`

### Utility
- `concatenate_keywords(keyword_list: List[str]) -> str`
  - Joins keywords with spaces.
