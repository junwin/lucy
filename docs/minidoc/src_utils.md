---
tags:
  - module
  - collection
  - base
  - text
  - account_name
  - query
  - hashlib
  - request
  - json
  - datetime
  - src/utils
---

# Module: `src/utils`

A collection of standalone utility modules. No shared base class or service. No `__init__.py`.

## Source Files

| File | Purpose |
|------|---------|
| `text_snippet_loader.py` | Load a text file snippet with character limit |
| `document_context.py` | Retrieve document snippets for a query via storage |
| `obsidian_importer.py` | Index Obsidian vault `.md` files into storage |
| `scrape.py` | Scrape a webpage and extract readable text |
| `migrate_legacy_completions.py` | One-shot migration script for legacy completion data |

## Key Functions (no classes)

### `text_snippet_loader.py`
- `load_text_snippet(path, max_chars=8000)` → `(str, bool)` — loads a text file, returns content and truncated flag.

### `document_context.py`
- `get_document_context(storage, account_name, query, kind, docs_tag, limit, max_chars)` → `List[Dict]` — retrieves relevant document snippets using `storage.search_documents_poor_man()`.

### `obsidian_importer.py`
- `index_obsidian_vault(storage, account_name, vault_path, kind, max_files)` → `List[DocumentRef]` — indexes all `.md` files in an Obsidian vault via `storage.upsert_document()`.

### `scrape.py`
- `scrape_url(url, timeout_seconds=20)` → `str` — fetches and extracts readable text from a URL.
- `extract_text_from_html(html)` → `str` — parses HTML with BeautifulSoup, removes non-content elements.
- `main(argv)` → `int` — CLI entry point.

### `migrate_legacy_completions.py`
- `migrate(account_name, agent_name)` → `None` — one-shot migration of legacy JSON completions to chat session format.

## Dependencies

### Internal (within `src/utils`)
- `document_context.py` → `text_snippet_loader.py` (imports `load_text_snippet`)

### External consumers
- `src/prompt_builders/prompt_builder.py` → imports `get_document_context`
- `src/obsidian_index_cli.py` → imports `index_obsidian_vault`

### External packages
| Package | Used by |
|---------|---------|
| `requests` | `scrape.py` |
| `beautifulsoup4` | `scrape.py` |
| `pyyaml` | `obsidian_importer.py` |

### Stdlib
`pathlib`, `hashlib`, `json`, `datetime`, `re`, `sys`, `logging`, `collections`, `typing`
