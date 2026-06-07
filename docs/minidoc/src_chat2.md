---
tags:
  - src_chat2
  - lucyproject
  - Chat2Store
  - Chat2Primitives
  - StoreKey
  - ChatEvent
  - ChatSessionMeta
  - JSONL
  - JfsChat2Primitives
  - FileChat2Primitives
  - InMemoryStore
  - prompt_slice
---

# Module: `src/chat2` — Chat v2 Storage

## Summary

A storage abstraction layer for chat sessions and events. Provides media-neutral storage primitives, append-only JSONL event logs, multi-agent support, and backward compatibility with existing `JsonFileStorage`. Foundation for the chat curation feature.

## Key Classes

| Class | File | Role |
|---|---|---|
| `Chat2Store` | `facade.py` | High-level facade wrapping `Chat2Primitives` |
| `Chat2Primitives` | `store_primitives.py` | Protocol (interface) for any storage backend |
| `InMemoryStore` | `store_primitives.py` | Dict-backed implementation for testing |
| `FileChat2Primitives` | `fs_primitives.py` | Filesystem-backed implementation (pathlib) |
| `JfsChat2Primitives` | `adapters/jfs_adapter.py` | Adapter wrapping `JsonFileStorage` |
| `StoreKey` | `store_primitives.py` | Frozen dataclass for logical storage keys |
| `ChatEvent` | `models.py` | Pydantic model for a single chat event |
| `ChatSessionMeta` | `models.py` | Pydantic model for session metadata |
| `SessionLinks` | `models.py` | Pydantic model for links between session types |
| `Chat2Error` | `errors.py` | Base exception for all chat2 errors |
| `SessionNotFoundError` | `errors.py` | Session not found |
| `EventNotFoundError` | `errors.py` | Event not found |
| `CorruptEventLogError` | `errors.py` | Unparseable event log |
| `CorruptMetaError` | `errors.py` | Unparseable session metadata |
| `StorageOperationError` | `errors.py` | Storage backend failure |

## Source Files (10)

| File | Purpose |
|---|---|
| `__init__.py` | Module exports |
| `models.py` | Pydantic domain models |
| `store_primitives.py` | `StoreKey`, `Chat2Primitives` Protocol, `InMemoryStore` |
| `jsonl_store.py` | JSONL event log functions |
| `fs_primitives.py` | `FileChat2Primitives` adapter |
| `facade.py` | `Chat2Store` convenience wrapper |
| `errors.py` | Exception hierarchy |
| `prompt_slice.py` | `get_last_n_events` function |
| `adapters/__init__.py` | Adapter exports |
| `adapters/jfs_adapter.py` | `JfsChat2Primitives` adapter |

## Dependencies

**Internal consumers** (6 files):
- `src/container_config.py` — wires `Chat2Store` + `JfsChat2Primitives`
- `src/http_endpoints/chats_endpoints.py` — reads/writes via `Chat2Store`
- `src/message_endpoints/ask_request_handler.py` — session creation
- `src/message_processors/automation_processor.py` — event logging
- `src/message_processors/function_calling_processor.py` — event logging
- `src/prompt_builders/prompt_builder.py` — reads history via `get_last_n_events`

**External packages**: `pydantic`, `json`, `uuid`, `datetime`, `pathlib`, `dataclasses`, `typing`

**Internal dependency**: `src.storage.json_file_storage` (for `JfsChat2Primitives`)

## Methods — Service / Base Classes

### `Chat2Store` (facade.py) — 14 methods

**Session lifecycle:**
- `create_session(user_id, account_name, agent_name, ...)` → `ChatSessionMeta`
- `get_session(session_id)` → `Optional[ChatSessionMeta]`
- `update_session(session_id, **patch_fields)` → `ChatSessionMeta`
- `delete_session(session_id)` → `None`
- `session_exists(session_id)` → `bool`
- `list_sessions(account_name=, agent_name=, limit=)` → `List[ChatSessionMeta]`

**Event management:**
- `add_event(session_id, event)` → `ChatEvent`
- `add_events(session_id, events)` → `List[ChatEvent]`
- `stream_events(session_id)` → `Iterator[ChatEvent]`
- `get_events(session_id, start_ts=, end_ts=, role_filter=, actor_filter=, kind_filter=)` → `List[ChatEvent]`
- `reset_events(session_id)` → `None`
- `event_count(session_id)` → `int`

**Convenience:**
- `create_and_add(user_id, account_name, agent_name, events, ...)` → `ChatSessionMeta`

### `Chat2Primitives` Protocol (store_primitives.py) — 6 methods

- `read_text(key: StoreKey)` → `Optional[str]`
- `write_text(key: StoreKey, text: str)` → `None`
- `append_text(key: StoreKey, text: str)` → `None`
- `exists(key: StoreKey)` → `bool`
- `delete(key: StoreKey)` → `None`
- `list_keys(prefix: StoreKey)` → `list[StoreKey]`

### `jsonl_store.py` — 9 standalone functions

- `create_session(...)` → `ChatSessionMeta`
- `get_session_meta(store, session_id)` → `Optional[ChatSessionMeta]`
- `update_session_meta(store, session_id, **patch_fields)` → `ChatSessionMeta`
- `delete_session(store, session_id)` → `None`
- `list_sessions(store, account_name=, agent_name=, limit=)` → `List[ChatSessionMeta]`
- `append_event(store, session_id, event)` → `ChatEvent`
- `stream_events(store, session_id)` → `Iterator[ChatEvent]`
- `read_events(store, session_id, ...)` → `List[ChatEvent]`
- `reset_session_events(store, session_id)` → `None`
