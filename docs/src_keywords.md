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
  - cosine_similarity
  - SnowballStemmer
  - word_tokenize
  - ensure_nltk_data
  - STOP_WORDS
  - DEFAULT_CUSTOM_EXCLUDE
  - CODELIKE_RE
  - SYMBOL_RE
---

# Module: `src.keywords`

## 1. Summary

The `src.keywords` module provides **keyword extraction and semantic comparison** from natural-language text. It wraps spaCy (primary NLP pipeline) and NLTK (tokenization/stemming) to extract meaningful keywords, and offers both set-based and cosine-similarity comparison methods. It also supports pre-specified keywords via a `request keywords:` code-fence convention.

This is a **leaf module** — it has no internal dependencies on other `src.*` modules. It is consumed by the storage layer (document indexing), the `get_keywords` tool handler, and the prompt-builder debug endpoint.

## 2. Architecture & Design

- **Single-class module.** The entire public API is the `Keywords` class. There is no `__init__.py`; consumers import `from src.keywords.keywords import Keywords`.
- **Lazy NLP loading.** spaCy is imported inside `_initialize_nlp_model()` rather than at module level, so tests can monkeypatch the method and avoid the heavy dependency entirely.
- **Fallback TF-IDF.** `compare_semantic_similarity` tries scikit-learn's `TfidfVectorizer` first; if that raises any exception it falls back to a pure-Python token-frequency cosine-similarity implementation.
- **Auto-download.** `ensure_nltk_data()` is called during spaCy initialisation and downloads the `punkt` tokenizer data on first run if missing. This avoids a common new-machine failure mode.
- **Multi-layer filtering.** Keyword extraction applies stop-word removal, custom exclusions (`DEFAULT_CUSTOM_EXCLUDE`), minimum-length filtering (`len < 2`), symbol-pattern rejection (`SYMBOL_RE`), and code-like token rejection (`CODELIKE_RE`). POS-based filtering was intentionally **removed** to prevent domain terms that spaCy mis-tags as VERB (e.g. "endpoints") from being lost.
- **`request keywords:` convention.** If the input text contains the literal substring `request keywords:`, extraction switches to parsing a code-fenced block (` ``` ... ``` `) and splitting on commas rather than running the NLP pipeline. This supports explicit keyword lists embedded in prompts.
- **Set comparison with operator.** `compare_keywords` supports `"and"` (exact set equality) and `"or"` (any overlap), raising `ValueError` for unknown operators.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `Keywords` | `object` | NLP-backed keyword extraction, set comparison, and cosine-similarity comparison. |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `keywords.py` | Single-file module — keyword extraction, comparison, and NLP model management. | `Keywords`, `ensure_nltk_data`, `CODELIKE_RE`, `SYMBOL_RE`, `DEFAULT_CUSTOM_EXCLUDE`, `STOP_WORDS` |

No `__init__.py` — the module is imported directly as `src.keywords.keywords`.

## 5. Dependencies

### Standard library
`typing` (List, Dict, Set), `collections.Counter`, `datetime`, `re`, `math`

### Third-party packages
| Package | Purpose | Required? |
|---|---|---|
| `nltk` | `SnowballStemmer`, `word_tokenize`, `wordnet` (`nltk.corpus`), `nltk.data.find`, `nltk.download` | **Yes** |
| `spacy` | NLP model loading (`en_core_web_sm`, `es_core_news_sm`), `STOP_WORDS` set | **Yes** |
| `scikit-learn` | `TfidfVectorizer`, `cosine_similarity` for semantic comparison | **Optional** — falls back to pure-Python TF vectors |

### Internal modules
None — this is a leaf module with no `src.*` imports.

### Optional dependencies
`sklearn.feature_extraction.text.TfidfVectorizer` and `sklearn.metrics.pairwise.cosine_similarity` are imported inside `compare_semantic_similarity` within a try/except. If unavailable, a pure-Python `Counter`-based cosine similarity is used instead.

## 6. Configuration / Settings

None. The module reads no `ConfigManager` keys and no environment variables. Language is selected by the `language_code` constructor parameter (default `"en"`).

## 7. Exceptions

None. The module defines no custom exception classes. `compare_keywords` raises built-in `ValueError` for invalid operators; `_initialize_nlp_model` raises built-in `RuntimeError` if spaCy cannot load.

## 8. Module-Level Constants

| Constant | Type | Value / Purpose |
|---|---|---|
| `CODELIKE_RE` | `re.Pattern` | Regex matching Unix-style paths (`/...`) and dotted filenames (`config_manager.py`). Used to exclude code-like tokens from keyword extraction. |
| `SYMBOL_RE` | `re.Pattern` | Regex matching purely symbolic tokens (`=+-*/<>:;,.()[]{}|\\`). Used to exclude punctuation-like tokens. |
| `DEFAULT_CUSTOM_EXCLUDE` | `set[str]` | Hardcoded set of ~60 words to always exclude from keywords: repo path noise (`src`, `repo_lucy`), generic nouns (`file`, `task`, `tool`, `function`, `class`), chatty verbs (`let`, `use`, `add`, `want`, `see`, `look`, `check`), and normalisation variants (`normalize`, `normalized`). |
| `STOP_WORDS` | `set[str]` | Module-level set populated by `_initialize_nlp_model()` from spaCy's `STOP_WORDS`. Defaults to empty `set()` before initialisation; tests can monkeypatch it directly. |

## 9. Methods (by class)

### `Keywords`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, language_code: str = "en")` | Stores `language_code`, calls `_initialize_nlp_model()` to load spaCy and NLTK data. Sets `self.nlp` to the loaded spaCy model. |
| `_initialize_nlp_model` | instance | `(self) -> None` | Lazy-imports spaCy, loads the appropriate model (`en_core_web_sm` for English, `es_core_news_sm` for Spanish), calls `ensure_nltk_data()`, and populates the module-level `STOP_WORDS` set. Raises `RuntimeError` on any failure. Side effects: mutates module-level `STOP_WORDS`, may trigger NLTK data download. |
| `extract_from_content` | instance | `(self, content: str, top_n: int = 10) -> List[str]` | Alias for `extract_keywords`. Exists for backward compatibility and readability. |
| `extract_keywords` | instance | `(self, content: str, top_n: int = 10) -> List[str]` | **Main extraction pipeline.** If content contains `"request keywords:"`, delegates to `get_specified_keywords`. Otherwise: lowercases input, runs spaCy NLP pipeline, filters out punctuation/whitespace tokens, lemmatises, removes stop words and custom exclusions, drops tokens with `len < 2`, filters symbol-only and code-like tokens, counts frequencies, and returns top-N. Side effect: none (pure computation). |
| `get_specified_keywords` | instance | `(self, input_str: str) -> List[str]` | Extracts keywords from a code-fenced block (` ``` ... ``` `) triggered by `request keywords:`. Splits the block contents on commas. Returns `[]` if no fenced block is found. **Note:** returned keywords are NOT whitespace-stripped (e.g. `" alpha"` rather than `"alpha"`). |
| `compare_keyword_lists_semantic_similarity` | instance | `(self, keywords1: List[str], keywords2: List[str]) -> float` | Concatenates each keyword list into a space-joined string via `concatenate_keywords`, then delegates to `compare_semantic_similarity`. Returns cosine similarity rounded to 6 decimal places. |
| `compare_semantic_similarity` | instance | `(self, text1: str, text2: str) -> float` | Computes cosine similarity between two text strings. Prefers scikit-learn's `TfidfVectorizer` + `cosine_similarity`; falls back to a pure-Python `Counter`-based TF vector implementation. Returns 0.0 if either text has a zero-length norm vector. Always rounded to 6 decimal places. Side effect: may import `sklearn` on first call. |
| `compare_keywords` | instance | `(self, set1: set, set2: set, operator: str = "and") -> bool` | Compares two keyword sets. `operator="and"` requires exact equality; `operator="or"` requires at least one common element. Raises `ValueError` for unknown operators. Both arguments are re-wrapped in `set()` even if already sets (idempotent). |
| `concatenate_keywords` | instance | `(self, keyword_list: List[str]) -> str` | Joins a list of keywords into a single space-separated string. Used as a helper for semantic comparison. |

### Module-level functions

| Function | Signature | Description |
|---|---|---|
| `ensure_nltk_data` | `(*, logger=None) -> None` | Checks for and auto-downloads required NLTK datasets (`punkt`). Uses `nltk.data.find` to check; downloads via `nltk.download(pkg, quiet=True)` on `LookupError`. Re-checks after download and will raise if still missing. Accepts an optional logger for informational messages. |

## 10. Usage Examples

**Basic keyword extraction:**
```python
from src.keywords.keywords import Keywords

kw = Keywords()                                    # loads en_core_web_sm, downloads punkt if needed
keywords = kw.extract_keywords(
    "Lucy uses spaCy and NLTK for keyword extraction from documents.",
    top_n=5,
)
# => ["lucy", "spacy", "nltk", "keyword", "extraction", "document"]
```

**Semantic similarity comparison:**
```python
kw = Keywords()
sim = kw.compare_keyword_lists_semantic_similarity(
    ["machine", "learning", "model"],
    ["deep", "learning", "neural", "network"],
)
# => 0.408248  (example; actual value depends on TF-IDF vectors)
```

**Set-based keyword matching:**
```python
kw = Keywords()
assert kw.compare_keywords({"a", "b"}, {"b", "a"}, operator="and") is True
assert kw.compare_keywords({"a", "b"}, {"c", "b"}, operator="or")  is True
```

## 11. Edge Cases & Gotchas

1. **spaCy must be installed at runtime.** The module cannot be imported without spaCy unless the caller monkeypatches `_initialize_nlp_model`. Tests do this; production code must have spaCy available.
2. **NLTK `punkt` auto-download.** On first run in a fresh environment, `ensure_nltk_data` will download the `punkt` tokenizer data (~13 MB) from NLTK's servers. This is a network call with no timeout.
3. **`get_specified_keywords` does not strip whitespace.** Keywords from a `request keywords:` code fence are split on commas only. A block containing `alpha, beta, gamma` returns `["alpha", " beta", "gamma"]`. Callers should strip the results themselves.
4. **`compare_semantic_similarity` catches all exceptions.** If scikit-learn raises anything (ImportError, ValueError, etc.), the fallback path runs silently. This means broken scikit-learn installations will silently degrade rather than fail.
5. **`STOP_WORDS` is module-level mutable state.** `_initialize_nlp_model` overwrites it with `global STOP_WORDS`. Tests monkeypatch it directly. If multiple `Keywords` instances are created with different languages, the last one's stop words win globally.
6. **No POS filtering.** Domain terms that spaCy mis-tags as VERB (e.g. "endpoints", "logging") survive extraction because the POS filter was deliberately removed. This is by design, but it means some VERB tokens that should be noise may also survive — the `DEFAULT_CUSTOM_EXCLUDE` set mitigates this for common chatty verbs.
7. **`DEFAULT_CUSTOM_EXCLUDE` is hardcoded.** The exclude set is tuned for Lucy's specific chat/document domain. It is not configurable and must be edited in source to change.
8. **Thread-unsafe.** Module-level `STOP_WORDS` mutation and NLTK download are not guarded by locks. Concurrent creation of `Keywords` instances from multiple threads is unsafe.
9. **Cosine similarity with empty input.** `compare_semantic_similarity` returns `0.0` when either text produces a zero-length norm vector (e.g. empty string, or all tokens filtered out).

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/storage/json_file_storage.py` | `Keywords()` → `extract_keywords()` for query keyword extraction (`top_n=20`) and document-blob keyword extraction (`top_n=50`) during indexing. |
| `src/handlers/get_keywords_handler.py` | `Keywords(language_code=...)` → `extract_keywords()` as a tool exposed to the LLM via the `get_keywords` handler. Wraps errors into `{ok: False, error: ...}` dicts. |
| `src/http_endpoints/prompt_builder_debug_endpoints.py` | `Keywords()` → `extract_keywords()` for query and document keywords in the prompt-builder debug view. |
| `tests/test_keywords.py` | Tests all public methods of `Keywords`. Monkeypatches `_initialize_nlp_model` and `STOP_WORDS` to avoid spaCy/NLTK requirements. |
