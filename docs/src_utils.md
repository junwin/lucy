---
tags:
  - src_utils
  - lucyproject
  - get_document_context
  - load_text_snippet
  - migrate
  - index_obsidian_vault
  - index_obsidian_file
  - scrape_url
  - extract_text_from_html
  - DocumentRef
  - Storage
  - DEFAULT_MAX_CHARS
  - DEFAULT_TIMEOUT_SECONDS
  - USER_AGENT
  - _stable_doc_id_from_path
  - _extract_tags
  - _extract_title
  - _remove_elements
---

## 1. Summary

`src/utils` is a namespace package (no `__init__.py`) containing five standalone utility modules that provide side-effecting helpers: web scraping, Obsidian vault indexing, legacy chat migration, text-file snippet loading, and document-context retrieval. These are not a coherent library — each file solves a distinct operational need that didn't fit elsewhere in the architecture. The common thread is that all modules operate at the "edge" of the system: reading external files, talking to external services, or performing one-off data migrations.

## 2. Architecture & Design

- **Namespace package** — no `__init__.py`, so each module is imported directly (e.g. `from src.utils.scrape import scrape_url`).
- **Functional / procedural style** — all five modules expose plain functions rather than classes. There is no shared base class, registry, or protocol.
- **Dependency injection by argument** — shared services (e.g. `Storage`) are passed as parameters; no `injector` usage here.
- **CLI-first design in `scrape.py`** — the module doubles as a command-line tool (`python3 src/utils/scrape.py <url>`) with a `main()` entry point.
- **`migrate_legacy_completions.py` is a one-shot script** — it reads a hard-coded input path and writes to `data/chats/<account>/`. It is not imported by any production code; it's only run as `__main__`.
- **`document_context.py` is a thin orchestration layer** — it composes `Storage.search_documents_poor_man()` with `load_text_snippet()` to build a list of context dictionaries for prompt builders.
- **`obsidian_importer.py` uses `Storage.upsert_document()`** — it is storage-backend-agnostic, relying on the `Storage` protocol from `src.storage.base`.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| _(none)_ | — | This module defines no classes; all exports are functions. |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `document_context.py` | Retrieve document snippets for a query via storage search | `get_document_context` |
| `migrate_legacy_completions.py` | One-shot script to migrate legacy completion JSON into chat session files | `migrate`, `parse_dt_utc`, `iso_utc`, `safe_first_line` |
| `obsidian_importer.py` | Index Obsidian vault markdown files as `DocumentRef` entries | `index_obsidian_vault`, `index_obsidian_file`, `_stable_doc_id_from_path`, `_extract_title`, `_extract_tags` |
| `scrape.py` | Fetch a webpage and extract readable text | `scrape_url`, `extract_text_from_html`, `main` |
| `text_snippet_loader.py` | Load a bounded character window from a text file | `load_text_snippet`, `DEFAULT_MAX_CHARS` |

No `__init__.py` — this is a namespace package.

## 5. Dependencies

### Standard library

| Module | Used by |
|---|---|
| `hashlib` | `obsidian_importer.py` |
| `json` | `migrate_legacy_completions.py` |
| `logging` | `document_context.py`, `obsidian_importer.py`, `text_snippet_loader.py` |
| `pathlib.Path` | `migrate_legacy_completions.py`, `obsidian_importer.py`, `text_snippet_loader.py` |
| `re` | `scrape.py` |
| `sys` | `scrape.py` |
| `datetime` | `migrate_legacy_completions.py` |
| `collections.defaultdict` | `migrate_legacy_completions.py` |
| `typing` | all five files |

### Third-party packages

| Package | Used by | Notes |
|---|---|---|
| `requests` | `scrape.py` | HTTP GET with timeout |
| `bs4` (BeautifulSoup) | `scrape.py` | HTML parsing and text extraction |
| `yaml` (PyYAML) | `obsidian_importer.py` | Frontmatter tag extraction |

### Internal modules

| Internal import | Used by |
|---|---|
| `src.storage.base.Storage` | `document_context.py`, `obsidian_importer.py` |
| `src.storage.models.DocumentRef` | `obsidian_importer.py` |
| `src.utils.text_snippet_loader.load_text_snippet` | `document_context.py` |

### Optional dependencies

None — all imports are unconditional.

## 6. Configuration / Settings

None. This module reads no `ConfigManager` keys, env vars, or config files. The constants below are code-level defaults only.

| Constant | Type | Default | What it controls |
|---|---|---|---|
| `DEFAULT_MAX_CHARS` (text_snippet_loader) | `int` | `8000` | Default character limit when `load_text_snippet` is called without an explicit `max_chars` |
| `DEFAULT_TIMEOUT_SECONDS` (scrape) | `int` | `10` | HTTP request timeout for `scrape_url` |
| `USER_AGENT` (scrape) | `str` | `"Mozilla/5.0 … LucyScraper/1.0"` | User-Agent header sent with scrape requests |
| `INPUT_PATH` (migrate_legacy_completions) | `Path` | `"data/completions/lucy_junwin_conv.json"` | Hard-coded input file for migration |
| `OUT_BASE` (migrate_legacy_completions) | `Path` | `"data"` | Output root for migrated chat files |

## 7. Exceptions

None. No custom exception classes are defined in this module. All functions raise only standard-library exceptions:

| Exception type | Raised by | Condition |
|---|---|---|
| `ValueError` | `index_obsidian_file`, `index_obsidian_vault` | Missing/invalid file paths, file not inside vault root, wrong extension |
| `requests.exceptions.Timeout` | `scrape_url` | HTTP request exceeds `timeout_seconds` |
| `requests.exceptions.ConnectionError` | `scrape_url` | DNS failure, refused connection |
| `requests.exceptions.HTTPError` | `scrape_url` | Non-2xx HTTP status (via `resp.raise_for_status()`) |
| `Exception` (general) | `load_text_snippet`, obsidian file reads | Caught internally, logged as warning, returns empty/fallback — never propagated |

## 8. Module-Level Constants

| Constant | File | Value | Purpose |
|---|---|---|---|
| `DEFAULT_MAX_CHARS` | `text_snippet_loader.py` | `8000` | Default snippet size in characters |
| `DEFAULT_TIMEOUT_SECONDS` | `scrape.py` | `10` | Default HTTP timeout |
| `USER_AGENT` | `scrape.py` | `"Mozilla/5.0 …"` | HTTP User-Agent string |
| `INPUT_PATH` | `migrate_legacy_completions.py` | `Path("data/completions/lucy_junwin_conv.json")` | Legacy input file path |
| `OUT_BASE` | `migrate_legacy_completions.py` | `Path("data")` | Migration output root |

## 9. Methods (by class)

_No classes in this module. All exports are plain functions, documented below._

### `document_context.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `get_document_context` | function | `(storage: Storage, account_name: str, query: str, *, kind: str \| None = None, docs_tag: str \| None = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` | Retrieves context snippets from documents for a query. If `docs_tag` is set, filters strictly by tag (ignoring query relevance). Otherwise uses the storage backend's `search_documents_poor_man()`. For each result, loads up to `max_chars` via `load_text_snippet`. Returns a list of dicts with keys: `id`, `title`, `path`, `tags`, `snippet`, `truncated`. Falls back to `[]` if the storage backend lacks `search_documents_poor_man`. |

### `migrate_legacy_completions.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `parse_dt_utc` | function | `(dt_str: str) -> datetime` | Parses legacy timestamp strings (e.g. `"2023-06-07T22:12:14.041985Z"` or with trailing `Z`). Handles `Z` → `+00:00` conversion and normalises to UTC. Returns `datetime.now(timezone.utc)` for empty/missing input. |
| `iso_utc` | function | `(dt: datetime) -> str` | Converts a datetime to ISO-8601 string with `+00:00` offset. Normalises naive datetimes to UTC. |
| `safe_first_line` | function | `(text: str, max_len: int = 80) -> str` | Extracts the first line of text, truncated to `max_len` characters with ellipsis. Returns `"Conversation"` for empty input. Used to generate `friendly_name` from the first user message. |
| `migrate` | function | `(account_name: str = "junwin", agent_name: str = "lucy") -> None` | Reads `INPUT_PATH`, groups records by `conversation_id`, sorts turns by timestamp, and writes one JSON file per conversation to `data/chats/<account_name>/`. Also writes `index.json`. Side effect: prints a summary line to stdout. |

### `obsidian_importer.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `_stable_doc_id_from_path` | function | `(vault_name: str, relative_path: str) -> str` | Private helper. Produces a portable SHA-256 hex digest from `vault_name/relative_path` so the same vault produces identical IDs across machines. |
| `_extract_title` | function | `(md_path: Path, contents: Optional[str] = None) -> str` | Private helper. Derives a document title from the file stem (filename without extension). The `contents` parameter is accepted but currently unused; reserved for future heading-parsing logic. |
| `_extract_tags` | function | `(contents: str) -> list[str]` | Private helper. Parses YAML frontmatter (`--- … ---`) and extracts the `tags` field. Handles string tags and list-of-string tags. Returns `[]` on parse failure or missing frontmatter. |
| `index_obsidian_file` | function | `(storage: Storage, account_name: str, md_path: str \| Path, *, vault_root: Optional[str \| Path] = None, kind: str = "obsidian_note") -> list[DocumentRef]` | Indexes a single `.md` file as a `DocumentRef`. Validates the file exists, is a file, has `.md` extension, and (if `vault_root` given) resides under the vault root. Reads file contents, extracts title/tags, computes stable ID, and calls `storage.upsert_document`. Returns a list with the single `DocumentRef` or `[]` on failure. |
| `index_obsidian_vault` | function | `(storage: Storage, account_name: str, vault_path: str \| Path, *, kind: str = "obsidian_note", max_files: Optional[int] = None) -> list[DocumentRef]` | Recursively walks a vault directory (`vault.rglob("*.md")`) and indexes every `.md` file. Per-file error handling: continues on read/upsert failures. Optional `max_files` cap for testing. Returns list of all successfully upserted `DocumentRef` objects. |

### `scrape.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `_remove_elements` | function | `(soup: BeautifulSoup, selectors: Iterable[str]) -> None` | Private helper. Removes all elements matching each CSS selector from the BeautifulSoup tree via `.decompose()`. |
| `extract_text_from_html` | function | `(html: str) -> str` | Parses HTML, strips non-content elements (scripts, styles, nav, header, footer, forms, etc.), prefers `<main>` if present, extracts text with newline separation, normalises whitespace (collapses 3+ blank lines to 2). |
| `scrape_url` | function | `(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str` | HTTP GETs a URL with a browser-like User-Agent, returns extracted readable text. Raises `requests` exceptions on timeout, connection error, or non-2xx status. |
| `main` | function | `(argv: Optional[list[str]] = None) -> int` | CLI entry point. Accepts a URL as first argument. Prints help on `-h`/`--help`. Returns exit codes: `0` success, `1` error, `2` usage. Writes text to stdout, errors to stderr. |

### `text_snippet_loader.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `load_text_snippet` | function | `(path: str \| Path, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool]` | Reads a text file (UTF-8, errors ignored) and returns `(snippet, truncated)`. If the file exceeds `max_chars`, returns the first `max_chars` characters and `truncated=True`. On read failure, logs a warning and returns `("", False)`. |

## 10. Usage Examples

### Web scraping

```python
from src.utils.scrape import scrape_url

text = scrape_url("https://example.com")
print(text[:200])
```

### Obsidian vault indexing

```python
from src.storage.json_file_storage import JsonFileStorage
from src.utils.obsidian_importer import index_obsidian_vault

storage = JsonFileStorage(base_path="data")
docs = index_obsidian_vault(storage, "junwin", "/home/junwin/ObsidianVault")
print(f"Indexed {len(docs)} notes")
```

### Document context for prompt building

```python
from src.utils.document_context import get_document_context

contexts = get_document_context(
    storage, "junwin", "What is Lucy?",
    kind="obsidian_note", limit=3, max_chars=4000
)
for c in contexts:
    print(c["title"], c["truncated"])
```

### Legacy migration (one-shot CLI)

```bash
python3 -c "from src.utils.migrate_legacy_completions import migrate; migrate()"
```

## 11. Edge Cases & Gotchas

- **`document_context.py` depends on a duck-typed method** — if the storage backend doesn't have `search_documents_poor_man`, the function silently returns `[]`. This is checked via `hasattr`, not a protocol.
- **`migrate_legacy_completions.py` hard-codes paths** — `INPUT_PATH` and `OUT_BASE` are module-level constants, not parameterised. It only runs for `junwin`/`lucy` unless you pass different args.
- **`_extract_tags` eats YAML parse errors** — malformed frontmatter is logged as a warning and tags are silently dropped. There's no way for callers to detect parse failures.
- **`_extract_title` ignores `contents`** — the parameter is accepted but the function always uses `md_path.stem`. This is a deliberate stub for future heading parsing.
- **`index_obsidian_file` failure modes** — files that fail to read or upsert return `[]` (empty list). The caller can't distinguish "file not found" (raises) from "read failed" (returns `[]`) from "upsert failed" (returns `[]`).
- **`scrape_url` has no retry logic** — transient HTTP errors are raised directly to the caller. There's no backoff or rate limiting.
- **`scrape_url` element removal is CSS-selector-based** — some websites put content in `<header>` or `<footer>` elements; this removal is aggressive and may drop legitimate content.
- **`load_text_snippet` truncates at character boundary** — no attempt to split at word/sentence/paragraph boundaries. You may get mid-word breaks.
- **Thread-safety** — none of these functions maintain internal state, so they are thread-safe for reads. However, `migrate` and `index_obsidian_vault` write to disk concurrently through `Storage`; safe only if the storage backend itself is thread-safe.
- **No `__init__.py`** — you cannot do `import src.utils` and expect submodules to be available. Each submodule must be imported explicitly.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/prompt_builders/prompt_builder.py` | `get_document_context` — builds document context snippets for prompts |
| `src/http_endpoints/prompt_builder_debug_endpoints.py` | `get_document_context`, `load_text_snippet` — debug endpoint for inspecting prompt construction |
| `src/obsidian_index_cli.py` | `index_obsidian_vault` — CLI command for indexing an Obsidian vault |
| `src/utils/document_context.py` | `load_text_snippet` — internal cross-import within the module |
| `tests/test_obsidian_importer.py` | `_stable_doc_id_from_path`, `_extract_tags`, `_extract_title`, `index_obsidian_file` — unit tests |
| `tests/test_live_prompt_builder.py` | References `python_utils_path: "src/utils"` in test config (indirect) |
| `migrate_legacy_completions` (standalone) | Run directly as `__main__` — not imported by any production code |
