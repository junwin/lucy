---
tags:
  - storage
  - context
  - JsonFileStorage
  - src.storage
  - prompt
---

# Contexts (JsonFileStorage)

Contexts are stored as a simple JSON “whiteboard” per **account + context_id**, persisted on disk by `JsonFileStorage`.

## Where contexts live on disk

Contexts are stored under:

- `base_path/contexts/<account_name>/<context_id>.json`

There is no separate index file; listing contexts is filesystem-based.

## On-disk JSON shape

Each context file is shaped like:

```json
{
  "id": "<context_id>",
  "account_name": "<account_name>",
  "data": { "...": "arbitrary JSON-serializable dict" },
  "updated_at": "2026-01-08T12:34:56.789+00:00"
}
```

Notes:
- `data` is intentionally free-form; storage does not enforce a schema beyond JSON-serializable.
- `updated_at` is stored as an ISO timestamp and normalized to timezone-aware UTC when read/written.

## Main APIs

### `get_context(account_name, context_id) -> Optional[ContextState]`

- Loads the JSON file for that account/context.
- Returns `None` if missing or unreadable.
- Parses `updated_at` via `_parse_dt_utc()`.

### `get_or_create_context(account_name, context_id, default_data=None) -> ContextState`

- Calls `get_context(...)`.
- If missing, creates a new `ContextState` and persists it via `save_context()`.
- Seeds `data` with defaults (unless overridden/extended by `default_data`):

```python
{
  "context_name": context_id,
  "agreed": False,
  "tasklist_status": "draft",
}
```

This supports “durable project state without pre-creating it”.

### `save_context(context: ContextState) -> None`

- Ensures `base_path/contexts/<account_name>/` exists.
- Normalizes `updated_at` to UTC-aware.
- Writes JSON atomically (writes `*.tmp` then `os.replace`).

### `list_context_names(account_name) -> List[str]`

- Lists `*.json` files in `base_path/contexts/<account_name>/`.
- Returns filename stems sorted (these are the available `context_id`s).

## Notable behavior / edges

- No concurrency/locking beyond atomic replace; last writer wins.
- Corrupted JSON behaves like “missing” (`_load_json` returns `None` and logs warnings/errors).
- Minor oddity: `from flask import sessions` is imported but unused in this file.

## How contexts are used in the request flow (high level)

Request flow (project-level):

1. HTTP request hits `POST /ask`.
2. `FunctionCallingProcessor` starts for the selected agent and session.
3. `PromptBuilder` builds the prompt (history, agent config, optional storage-based context).
4. Model is called; tool calls are executed by `FunctionCallingProcessor`; final reply returned.

Contexts are the “optional storage-based context” that can be injected into the prompt.
