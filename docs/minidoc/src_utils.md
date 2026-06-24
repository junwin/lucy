---
tags:
  - src_utils
  - lucyproject
  - document_context
  - text_snippet_loader
  - obsidian_importer
  - scrape
  - migrate_legacy_completions
  - utility
  - helper
---

# Module: `src.utils`

## Summary

Collection of standalone utility/helper modules for common tasks: document context retrieval, text snippet loading, Obsidian vault importing, webpage scraping, and legacy completion migration. Each file is self-contained with a single responsibility. No `__init__.py` — the package is implicit.

## Key Classes / Functions

| Name | Type | File | Purpose |
|---|---|---|---|
| `get_document_context` | function | `document_context.py` | Retrieve relevant document snippets for a query via storage backend. |
| `load_text_snippet` | function | `text_snippet_loader.py` | Load a bounded text snippet from a file path. |
| `index_obsidian_vault` | function | `obsidian_importer.py` | Index all `.md` files in an Obsidian vault as `DocumentRef` entries. |
| `scrape_url` | function | `scrape.py` | Fetch and extract readable text from a webpage URL. |
| `migrate` | function | `migrate_legacy_completions.py` | Migrate legacy completion JSON into per-session chat files. |

## Source Files

| File | Description |
|---|---|
| `document_context.py` | Thin helper over storage layer — searches documents and loads text snippets. |
| `text_snippet_loader.py` | Single function to read a file and truncate at `max_chars`. |
| `obsidian_importer.py` | Walks an Obsidian vault, extracts YAML frontmatter tags, upserts documents via `Storage`. |
| `scrape.py` | Webpage scraper using `requests` + `BeautifulSoup` — strips non-content elements. |
| `migrate_legacy_completions.py` | One-shot migration script — groups legacy completions by conversation ID and writes session files. |

## Dependencies

- **Standard library**: `json`, `datetime`, `pathlib.Path`, `hashlib`, `re`, `sys`, `collections.defaultdict`, `typing`
- **Third-party**: `requests`, `beautifulsoup4` (`bs4`), `yaml` (PyYAML)
- **Internal**: `src.storage.base.Storage`, `src.storage.models.DocumentRef`

### Consumers (who imports from `src.utils`)

| Consumer | What it imports |
|---|---|
| `src.prompt_builders.prompt_builder` | `get_document_context` |
| `src.obsidian_index_cli` | `index_obsidian_vault` |
| `src.http_endpoints.prompt_builder_debug_endpoints` | `get_document_context`, `load_text_snippet` |
| `src.utils.document_context` | `load_text_snippet` (internal) |

## Functions — `document_context.py`

| Function | Signature | Description |
|---|---|---|
| `get_document_context` | `(storage: Storage, account_name: str, query: str, *, kind: str \| None = None, docs_tag: str \| None = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]` | Search documents via storage backend, load bounded snippets, return list of context dicts. |

## Functions — `text_snippet_loader.py`

| Function | Signature | Description |
|---|---|---|
| `load_text_snippet` | `(path: str \| Path, max_chars: int = 8000) -> Tuple[str, bool]` | Read a text file, return `(content, truncated)` — truncated if file exceeds `max_chars`. |

## Functions — `obsidian_importer.py`

| Function | Signature | Description |
|---|---|---|
| `index_obsidian_vault` | `(storage: Storage, account_name: str, vault_path: str \| Path, *, kind: str = "obsidian_note", max_files: int \| None = None) -> list[DocumentRef]` | Walk vault, parse frontmatter tags, upsert documents via storage. |
| `_stable_doc_id_from_path` | `(path: Path) -> str` | SHA-256 hash of path for stable dedup IDs. |
| `_extract_title` | `(md_path: Path, contents: str \| None = None) -> str` | Derive title from filename stem. |
| `_extract_tags` | `(contents: str) -> list[str]` | Parse YAML frontmatter `tags` field. |

## Functions — `scrape.py`

| Function | Signature | Description |
|---|---|---|
| `scrape_url` | `(url: str, *, timeout_seconds: int = 20) -> str` | Fetch URL, strip non-content elements, return readable text. |
| `extract_text_from_html` | `(html: str) -> str` | Parse HTML with BeautifulSoup, remove scripts/styles/nav, extract text. |

## Functions — `migrate_legacy_completions.py`

| Function | Signature | Description |
|---|---|---|
| `migrate` | `(account_name: str = "junwin", agent_name: str = "lucy") -> None` | Read legacy completions JSON, group by conversation, write session files + index. |
| `parse_dt_utc` | `(dt_str: str) -> datetime` | Parse legacy ISO timestamps (with/without trailing Z) to UTC-aware datetime. |
| `iso_utc` | `(dt: datetime) -> str` | Format datetime as ISO 8601 with `+00:00`. |
| `safe_first_line` | `(text: str, max_len: int = 80) -> str` | Extract first line of text, truncated to `max_len`. |
