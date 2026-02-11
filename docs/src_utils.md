---
tags:
  - str
  - util
  - max_char
  - utils
  - account_name
  - path
  - tag
  - json
  - module
  - source
  - src/utils
---

# Module: `src/utils`

Small utility helpers used across Lucy for document context, file snippet loading, Obsidian vault indexing, and one-off legacy data migration.

## Source files

- `src/utils/document_context.py`
- `src/utils/text_snippet_loader.py`
- `src/utils/obsidian_importer.py`
- `src/utils/migrate_legacy_completions.py`

## Key classes

This module folder is mostly **functions** (no major service classes).

- Uses `Storage` (imported from `src.storage.base`) as an abstraction.
- Uses `DocumentRef` (imported from `src.storage.models`) as the document model for indexing.

## Main functions (service-like entry points)

### `get_document_context(...)` (in `document_context.py`)

**Signature**
- `get_document_context(storage, account_name, query, *, kind=None, docs_tag=None, limit=3, max_chars=6000) -> list[dict]`

**What it does**
- Calls `storage.search_documents_poor_man(...)` (if present) to find documents.
- Loads a bounded snippet from each document path using `load_text_snippet(...)`.
- Returns a list of dicts with:
  - `id`, `title`, `path`, `tags`, `snippet`, `truncated`

**Key behaviors**
- If `docs_tag` is provided, it passes that tag into the storage search call.
- If the storage backend does not implement `search_documents_poor_man`, it returns `[]`.

### `load_text_snippet(...)` (in `text_snippet_loader.py`)

**Signature**
- `load_text_snippet(path, max_chars=DEFAULT_MAX_CHARS) -> (snippet: str, truncated: bool)`

**What it does**
- Reads a text file as UTF-8 (ignoring decode errors).
- Returns the full text if it is within `max_chars`, otherwise returns a truncated prefix.
- On read failure, logs a warning and returns `("", False)`.

### `index_obsidian_vault(...)` (in `obsidian_importer.py`)

**Signature**
- `index_obsidian_vault(storage, account_name, vault_path, *, kind="obsidian_note", max_files=None) -> list[DocumentRef]`

**What it does**
- Recursively finds `*.md` files under an Obsidian vault directory.
- Creates a stable document id from the file path (`sha256`).
- Extracts tags from YAML frontmatter (`tags:` field).
- Builds a `DocumentRef` and calls `storage.upsert_document(doc)`.

**Notable internal helpers**
- `_stable_doc_id_from_path(path: Path) -> str`
- `_extract_title(md_path: Path, contents: Optional[str] = None) -> str`
- `_extract_tags(contents: str) -> list[str]`

### `migrate(...)` (in `migrate_legacy_completions.py`)

**Signature**
- `migrate(account_name="junwin", agent_name="lucy") -> None`

**What it does**
- Reads legacy completions from `data/completions/lucy_junwin_conv.json`.
- Groups records by `conversation_id`.
- Normalizes timestamps to UTC ISO.
- Writes per-conversation chat session JSON to `data/chats/<account_name>/conv_<id>.json`.
- Writes a lightweight `index.json` for sessions.

**Notable helpers**
- `parse_dt_utc(dt_str: str) -> datetime`
- `iso_utc(dt: datetime) -> str`
- `safe_first_line(text: str, max_len: int = 80) -> str`
