---
tags:
  - util
  - json
  - module
  - utils
  - account_name
  - query
  - list[documentref
  - yaml
  - base
  - doc
  - source
  - get_document_context(storage
  - src/utils
---

# `src/utils` mini doc

## Source files
- `src/utils/document_context.py`
- `src/utils/text_snippet_loader.py`
- `src/utils/obsidian_importer.py`
- `src/utils/migrate_legacy_completions.py`

## Key functions / classes
### `get_document_context(...)` (in `document_context.py`)
**Signature**
- `get_document_context(storage: Storage, account_name: str, query: str, *, kind: str | None = None, docs_tag: str | None = None, limit: int = 3, max_chars: int = 6000) -> List[Dict[str, Any]]`

**What it does**
- Thin helper over the storage layer to fetch document snippets for prompt context.
- Uses `storage.search_documents_poor_man(...)` if the storage backend provides it.
- Loads bounded snippets from each document path via `load_text_snippet(...)`.

**Returns**
- List of dicts with keys: `id`, `title`, `path`, `tags`, `snippet`, `truncated`.

### `load_text_snippet(...)` (in `text_snippet_loader.py`)
**Signature**
- `load_text_snippet(path: str | Path, max_chars: int = 8000) -> tuple[str, bool]`

**What it does**
- Reads a text file and returns at most `max_chars` characters.
- Returns `(snippet, truncated)`.

### `index_obsidian_vault(...)` (in `obsidian_importer.py`)
**Signature**
- `index_obsidian_vault(storage: Storage, account_name: str, vault_path: str | Path, *, kind: str = "obsidian_note", max_files: int | None = None) -> list[DocumentRef]`

**What it does**
- Walks an Obsidian vault (`*.md`).
- Extracts tags from YAML frontmatter (`tags:`) using PyYAML.
- Creates stable document IDs from file paths (sha256).
- Upserts `DocumentRef` entries via `Storage.upsert_document(...)`.

### `migrate(...)` (in `migrate_legacy_completions.py`)
**Signature**
- `migrate(account_name: str = "junwin", agent_name: str = "lucy") -> None`

**What it does**
- One-off migration script.
- Converts legacy completions JSON into per-session chat JSON files plus an `index.json`.

## Dependencies
### Standard library
- `logging`, `pathlib`, `typing`, `hashlib`, `json`, `datetime`, `collections`

### Third-party
- `yaml` (PyYAML)

### Internal
- `src.storage.base.Storage`
- `src.storage.models.DocumentRef`
- `src.utils.text_snippet_loader.load_text_snippet`

## Methods in the module service/base class
There is **no dedicated service/base class** in `src/utils`.

Utilities in this module rely on these storage-layer methods:
- `Storage.upsert_document(doc: DocumentRef) -> None`
- `JsonFileStorage.search_documents_poor_man(account_name, query, kind=None, limit=..., tag=...) -> list[DocumentRef]` *(backend-specific; checked via `hasattr`)*
