# Chat v2 — Storage Layer

A storage abstraction layer for chat sessions and events. Foundation for the chat curation feature.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Chat2 Facade                       │
│                  (src/chat2/__init__.py)              │
├─────────────────────────────────────────────────────┤
│                   JSONL Store Functions              │
│                  (src/chat2/jsonl_store.py)           │
├─────────────────────────────────────────────────────┤
│              Chat2Primitives (Protocol)              │
│              (src/chat2/store_primitives.py)          │
├──────────────────┬──────────────────────────────────┤
│  InMemoryStore   │  FileChat2Primitives              │
│  (tests only)    │  (src/chat2/fs_primitives.py)     │
└──────────────────┴──────────────────────────────────┘
```

## Key Concepts

- **StoreKey**: A validated logical path (no leading `/`, no `..`). All storage operations use `StoreKey` objects, never raw filesystem paths.
- **Chat2Primitives**: A Protocol defining 6 primitive operations: `read_text`, `write_text`, `append_text`, `exists`, `delete`, `list_keys`.
- **JSONL Store Functions**: Higher-level operations built on primitives — session CRUD, event append/stream/filter.
- **FileChat2Primitives**: Filesystem adapter mapping `StoreKey` paths to real files under a root directory.

## Modules

### `src/chat2/store_primitives.py`
- `StoreKey` — frozen dataclass with validation
- `Chat2Primitives` — Protocol for storage backends

### `src/chat2/fs_primitives.py`
- `FileChat2Primitives` — filesystem-backed implementation

### `src/chat2/jsonl_store.py`
- `create_session(store, user_id, account_name, agent_name, ...)` → `ChatSessionMeta`
- `get_session_meta(store, session_id)` → `ChatSessionMeta | None`
- `update_session_meta(store, session_id, **fields)` → `ChatSessionMeta`
- `delete_session(store, session_id)` — removes meta + events
- `append_event(store, session_id, event)` → `ChatEvent`
- `stream_events(store, session_id)` → `Iterator[ChatEvent]`
- `read_events(store, session_id, *, filters...)` → `List[ChatEvent]`
- `reset_session_events(store, session_id)` — clears events, preserves meta

### `src/chat2/models.py`
- `ChatEvent` — single event in a conversation
- `ChatSessionMeta` — session metadata
- `SessionLinks` — cross-session linking

### `src/chat2/errors.py`
- `Chat2Error` — base exception
- `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError`

## Storage Key Layout

```
sessions/<session_id>/meta.json    — ChatSessionMeta (JSON)
sessions/<session_id>/events.jsonl — append-only event log (JSONL)
```

## Usage

```python
from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.jsonl_store import create_session, append_event, stream_events
from src.chat2.models import ChatEvent

store = FileChat2Primitives("/path/to/data")

# Create a session
meta = create_session(store, user_id="user-1", account_name="acme", agent_name="lucy")

# Append events
ev = ChatEvent(role="user", actor="john", kind="user_message", payload="Hello")
append_event(store, meta.session_id, ev)

# Stream events back
for event in stream_events(store, meta.session_id):
    print(event.role, event.payload)
```

## Testing

```bash
# Run all chat2 tests
pytest tests/chat2/ -v

# With coverage
pytest tests/chat2/ --cov=src/chat2 --cov-report=term-missing
```

### Test files

| File | Tests |
|---|---|
| `test_primitives.py` | StoreKey validation + InMemoryStore + Chat2Primitives protocol |
| `test_fs_primitives.py` | FileChat2Primitives read/write/append/exists/delete/list_keys |
| `test_jsonl_store.py` | Session CRUD, event append/stream/filter, reset |
| `test_models.py` | Pydantic model validation, serialization, defaults |
| `test_errors.py` | Exception hierarchy, fields, string representation |
| `test_edge_cases.py` | Empty JSONL lines, timezone handling, payload validation |

## Status

✅ Step 1 — RouterApi  
✅ Step 2 — container_config.py  
✅ Step 3 — Storage primitives interface  
✅ Step 4 — JSONL store functions  
✅ Step 5 — Filesystem primitives adapter  
✅ Step 7 — Errors and helpers  
✅ Step 8 — Test coverage + README  

⏳ Step 6 — Token estimator + prompt slice (design pending)  
⏳ Step 9 — Integration adapter (JFS adapter)  
⏳ Step 10 — Facade
