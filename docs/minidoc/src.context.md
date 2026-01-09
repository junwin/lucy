---
tags:
  - src.storage
  - JsonFileStorage
  - ContextState
  - context
  - prompt
---

# src.context (storage-backed contexts)

Short description: File-backed “context state” used as optional durable memory that `PromptBuilder` can inject into prompts.

- Storage implementation: `src/repos/lucy/src/storage/json_file_storage.py`
- Model: `ContextState` in `src/repos/lucy/src/storage/models.py`
- Sample `lucydata/data/contexts/junwin/lucy_gptchum.json`
## On-disk layout

- `base_path/contexts/<account_name>/<context_id>.json`

## JSON shape

- `id` (context_id)
- `account_name`
- `data` (free-form JSON-serializable dict)
- `updated_at` (ISO timestamp; normalized to UTC)

## Key operations

- `get_context(account_name, context_id)` → load or `None`
- `get_or_create_context(account_name, context_id, default_data=None)` → creates + persists if missing
  - default `data`: `{context_name, agreed: False, tasklist_status: "draft"}`
- `save_context(context)` → atomic write (`*.tmp` then `os.replace`)
- `list_context_names(account_name)` → lists `*.json` stems

## Notes / edges

- No index; listing is filesystem-based.
- No locking beyond atomic replace (last writer wins).
- Corrupt JSON behaves like missing (logs warning/error).
