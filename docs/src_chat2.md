---
tags:
  - src_chat2
  - lucyproject
  - Chat2Store
  - ChatEvent
  - ChatSessionMeta
  - SessionLinks
  - Chat2Primitives
  - StoreKey
  - InMemoryStore
  - FileChat2Primitives
  - JfsChat2Primitives
  - Chat2Error
  - SessionNotFoundError
  - EventNotFoundError
  - CorruptEventLogError
  - CorruptMetaError
  - StorageOperationError
  - get_last_n_events
---

# Module: `src.chat2`

## 1. Summary

The `src.chat2` module is the **Chat v2 storage system** — a complete replacement for Lucy's legacy chat persistence. It provides a media-neutral, append-only JSONL-based storage layer for chat sessions and events, designed for multi-agent support and decoupled from any single filesystem layout.

The module sits at the data layer of the Lucy architecture, below the HTTP endpoints (`src.http_endpoints.chats_endpoints`) and message processors (`src.message_processors.function_calling_processor`), above the raw filesystem. It solves the problem of chat persistence being tightly coupled to a single storage backend by introducing a `Protocol`-based abstraction (`Chat2Primitives`) that allows swapping backends (filesystem, in-memory, JFS adapter) without changing any business logic.

## 2. Architecture & Design

### Key Design Patterns

- **Protocol-based storage abstraction** — `Chat2Primitives` is a `typing.Protocol` (runtime-checkable) that defines six methods (`read_text`, `write_text`, `append_text`, `exists`, `delete`, `list_keys`). Three implementations exist: `FileChat2Primitives` (direct filesystem), `InMemoryStore` (dict-backed, for tests), and `JfsChat2Primitives` (adapter wrapping legacy `JsonFileStorage`).

- **Facade pattern** — `Chat2Store` wraps the stateless functions in `jsonl_store.py` into a single object with a simpler API. All underlying functions remain importable for direct use.

- **Adapter pattern** — `JfsChat2Primitives` composes with (does not inherit from) `JsonFileStorage`, reusing its `_atomic_write_text` helper and mapping logical `StoreKey` paths to a `chat2/` subdirectory under the existing storage base.

- **Append-only event log** — Events are stored as JSONL (one JSON object per line). New events are appended; the log is never rewritten in place (except for `reset_session_events` which truncates). This is safe for concurrent writers at the OS level and makes the event log an audit trail.

- **Pydantic v2 domain models** — `ChatEvent` and `ChatSessionMeta` are Pydantic `BaseModel` subclasses with `field_validator` decorators for UUID format, UTC-normalised datetimes, and payload type checking. Models have explicit `model_dump_json` and `model_validate_json` methods.

- **Logical key abstraction** — `StoreKey` is a `frozen=True` dataclass that enforces rules: no leading `/`, no `..` traversal, `/` as separator. This is not a filesystem path — it's a logical identifier that backends map to their own storage.

### Phased Design ("Phase 4")

The `chat2` module was introduced as "Phase 4" to replace legacy chat storage. The old system stored completions in `JsonFileStorage` under a different key layout. Chat2 coexists with the old system by using a `chat2/` subdirectory (via `JfsChat2Primitives`) or by being backed by a completely independent root (via `FileChat2Primitives`). No legacy data migration is required — chat2 is a clean-slate design.

### Important Design Decisions

- **All functions accept `store: Chat2Primitives`** — no function in `jsonl_store.py` or `facade.py` touches the filesystem directly. This makes every operation testable with `InMemoryStore`.
- **`from __future__ import annotations`** is used throughout — all type hints are strings at runtime, avoiding circular import issues.
- **`jsonl_store.py` is a namespace of pure functions** — no class, no state. It reads/writes through the injected `store`.
- **Event log is keyed per session** — `sessions/<session_id>/events.jsonl` and `sessions/<session_id>/meta.json` are the only two files per session.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `ChatEvent` | `pydantic.BaseModel` | Domain model for a single chat event (user message, assistant message, tool call, etc.) |
| `ChatSessionMeta` | `pydantic.BaseModel` | Domain model for session metadata (ID, user, agent, timestamps, tags, links) |
| `SessionLinks` | `pydantic.BaseModel` | Links between user and internal sessions (UUID-validated optional strings) |
| `Chat2Store` | `object` | High-level facade wrapping `jsonl_store` functions into session/event CRUD |
| `StoreKey` | `dataclass` (frozen) | Logical storage key with validation (no leading `/`, no `..`) |
| `Chat2Primitives` | `typing.Protocol` | Storage abstraction protocol (6 methods) |
| `InMemoryStore` | `object` | Dict-backed `Chat2Primitives` implementation for testing |
| `FileChat2Primitives` | `object` | Filesystem-backed `Chat2Primitives` implementation using `pathlib.Path` |
| `JfsChat2Primitives` | `object` | Adapter wrapping `JsonFileStorage` to implement `Chat2Primitives` |
| `Chat2Error` | `Exception` | Base exception for all chat2 module errors |
| `SessionNotFoundError` | `Chat2Error` | Raised when a session operation targets a non-existent session |
| `EventNotFoundError` | `Chat2Error` | Raised when a specific event cannot be found |
| `CorruptEventLogError` | `Chat2Error` | Raised when an event log contains unparseable data |
| `CorruptMetaError` | `Chat2Error` | Raised when session metadata cannot be parsed |
| `StorageOperationError` | `Chat2Error` | Raised when a storage backend operation fails unexpectedly |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Package init; defines `__version__` and public API surface | `Chat2Store`, `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError` |
| `models.py` | Pydantic domain models for events and sessions | `ChatEvent`, `ChatSessionMeta`, `SessionLinks` |
| `errors.py` | Exception hierarchy | `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError` |
| `store_primitives.py` | Protocol definition, StoreKey, and InMemoryStore | `StoreKey`, `Chat2Primitives`, `InMemoryStore` |
| `fs_primitives.py` | Filesystem implementation of Chat2Primitives | `FileChat2Primitives` |
| `jsonl_store.py` | Stateless JSONL-backed store functions | `create_session`, `get_session_meta`, `update_session_meta`, `delete_session`, `list_sessions`, `append_event`, `stream_events`, `read_events`, `reset_session_events` |
| `facade.py` | High-level Chat2Store wrapper | `Chat2Store` |
| `prompt_slice.py` | Conversational event slicing for prompt building | `get_last_n_events` |
| `adapters/__init__.py` | Adapter sub-package init | `JfsChat2Primitives` |
| `adapters/jfs_adapter.py` | JFS adapter bridging to legacy JsonFileStorage | `JfsChat2Primitives` |

## 5. Dependencies

### Standard Library
- `datetime` — `datetime`, `timezone` (models, jsonl_store, facade)
- `typing` — `Literal`, `Optional`, `Protocol`, `runtime_checkable`, `Iterator`, `List`, `Iterable` (all files)
- `uuid` — `UUID`, `uuid4` (models, jsonl_store)
- `json` — `json` (jsonl_store — imported but unused in current code; `model_dump_json()` / `model_validate_json()` are used instead)
- `pathlib` — `Path` (fs_primitives, jfs_adapter)
- `dataclasses` — `dataclass` (store_primitives)

### Third-Party Packages
- `pydantic` — `BaseModel`, `Field`, `field_validator` (models)

### Internal Modules
- `src.storage.json_file_storage.JsonFileStorage` — used by `JfsChat2Primitives` adapter
- `src.chat2.models` — imported by `__init__` (re-exports not needed), `jsonl_store`, `facade`, `prompt_slice`, `adapters/jfs_adapter`
- `src.chat2.store_primitives` — imported by `fs_primitives`, `jsonl_store`, `facade`, `adapters/jfs_adapter`
- `src.chat2.errors` — imported by `__init__`
- `src.chat2.jsonl_store` — imported by `facade`

### Optional Dependencies
None. All imports are unconditional.

## 6. Configuration / Settings

None. The module reads no config keys, env vars, or file paths from any configuration system. All paths and roots are passed explicitly to constructors (`FileChat2Primitives(root_dir)`, `JfsChat2Primitives(storage)`).

## 7. Exceptions

| Exception | Base | When Raised |
|---|---|---|
| `Chat2Error` | `Exception` | Base class — never raised directly |
| `SessionNotFoundError` | `Chat2Error` | Session operation on non-existent session ID |
| `EventNotFoundError` | `Chat2Error` | Event lookup on non-existent event ID (defined but not yet raised by any code path) |
| `CorruptEventLogError` | `Chat2Error` | Event log line is unparseable JSON or fails Pydantic validation |
| `CorruptMetaError` | `Chat2Error` | Session metadata file is unparseable JSON or fails Pydantic validation |
| `StorageOperationError` | `Chat2Error` | Generic backend operation failure (defined but not yet raised by any code path) |

**Note:** `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, and `StorageOperationError` are defined in `errors.py` but are **not currently raised** by any code in the module. The `jsonl_store.list_sessions` function silently skips corrupt meta files with a bare `except Exception: continue`. The `stream_events` function will propagate Pydantic validation errors from `ChatEvent.model_validate_json` rather than wrapping them. These exception classes exist as a forward-looking API contract.

## 8. Module-Level Constants

| Constant | File | Value | Purpose |
|---|---|---|---|
| `_CONVERSATION_KINDS` | `prompt_slice.py` | `frozenset({"user_message", "assistant_message"})` | Defines which event kinds count as conversational turns for slicing |
| `__version__` | `__init__.py` | `"0.1.0"` | Module version string |

## 9. Methods (by Class)

### `StoreKey` (frozen dataclass)

| Method | Type | Signature | Description |
|---|---|---|---|
| `__post_init__` | instance | `() -> None` | Validates that `value` is a `str`, does not start with `/`, and contains no `..` path segments. Raises `TypeError` or `ValueError` on violation. |
| `__str__` | instance | `() -> str` | Returns `self.value`. Enables use of `StoreKey` in string contexts. |

### `Chat2Primitives` (Protocol)

| Method | Type | Signature | Description |
|---|---|---|---|
| `read_text` | instance | `(key: StoreKey) -> Optional[str]` | Read full text content at `key`. Returns `None` if the key does not exist. |
| `write_text` | instance | `(key: StoreKey, text: str) -> None` | Write `text` to `key`, overwriting any existing content. Should be atomic if possible. |
| `append_text` | instance | `(key: StoreKey, text: str) -> None` | Append `text` to existing content at `key`. Required for append-only JSONL event logs. |
| `exists` | instance | `(key: StoreKey) -> bool` | Return `True` if `key` exists in the store. |
| `delete` | instance | `(key: StoreKey) -> None` | Remove content at `key`. No-op if the key does not exist. |
| `list_keys` | instance | `(prefix: StoreKey) -> list[StoreKey]` | Return all keys starting with `prefix`. Optional operation — backends may raise `NotImplementedError`. |

### `InMemoryStore`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `() -> None` | Initializes an empty `dict[str, str]` as `self._data`. |
| `read_text` | instance | `(key: StoreKey) -> Optional[str]` | Returns `self._data.get(key.value)`. Returns `None` for missing keys. |
| `write_text` | instance | `(key: StoreKey, text: str) -> None` | Sets `self._data[key.value] = text`. Overwrites existing keys. |
| `append_text` | instance | `(key: StoreKey, text: str) -> None` | Appends `text` to existing value (or empty string if key missing). |
| `exists` | instance | `(key: StoreKey) -> bool` | Returns `key.value in self._data`. |
| `delete` | instance | `(key: StoreKey) -> None` | Removes key with `dict.pop(key.value, None)`. No-op for missing keys. |
| `list_keys` | instance | `(prefix: StoreKey) -> list[StoreKey]` | Returns all keys in `_data` that start with `prefix.value`, wrapped as `StoreKey` objects. |

### `FileChat2Primitives`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(root_dir: str \| Path) -> None` | Resolves `root_dir` to an absolute path and stores as `self._root`. |
| `_resolve` | instance | `(key: StoreKey) -> Path` | Resolves a `StoreKey` to an absolute filesystem path under `self._root`. Security: raises `ValueError` if the resolved path escapes `self._root`. |
| `read_text` | instance | `(key: StoreKey) -> Optional[str]` | Returns file contents as UTF-8 string, or `None` if file does not exist. |
| `write_text` | instance | `(key: StoreKey, text: str) -> None` | Creates parent directories, then writes `text` as UTF-8. Overwrites existing files. Not atomic. |
| `append_text` | instance | `(key: StoreKey, text: str) -> None` | Creates parent directories, then opens file in append mode and writes `text`. |
| `exists` | instance | `(key: StoreKey) -> bool` | Returns `True` if the resolved path exists on the filesystem. |
| `delete` | instance | `(key: StoreKey) -> None` | Unlinks the file. No-op if it does not exist. |
| `list_keys` | instance | `(prefix: StoreKey) -> list[StoreKey]` | Recursively lists all files under the resolved prefix directory, returning their paths relative to `self._root` as `StoreKey` objects. Returns `[]` if the prefix directory does not exist or is not a directory. |

### `JfsChat2Primitives`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(storage: JsonFileStorage) -> None` | Stores the `JsonFileStorage` reference and derives `self._root` as `storage.storage_paths.base / "chat2"`. |
| `_resolve` | instance | `(key: StoreKey) -> Path` | Resolves `StoreKey` to absolute path under `self._root`. Security: raises `ValueError` if path escapes root. |
| `_ensure_parent` | instance | `(path: Path) -> None` | Creates parent directories if they don't exist (`mkdir(parents=True, exist_ok=True)`). |
| `read_text` | instance | `(key: StoreKey) -> Optional[str]` | Returns file contents as UTF-8, or `None` if the file does not exist. |
| `write_text` | instance | `(key: StoreKey, text: str) -> None` | Creates parent directories, then writes using `JsonFileStorage._atomic_write_text` (write-to-temp-then-rename for atomicity). |
| `append_text` | instance | `(key: StoreKey, text: str) -> None` | Creates parent directories, then appends to file. **Not atomic.** |
| `exists` | instance | `(key: StoreKey) -> bool` | Returns `True` if the resolved path exists on the filesystem. |
| `delete` | instance | `(key: StoreKey) -> None` | Unlinks the file. No-op if it does not exist. |
| `list_keys` | instance | `(prefix: StoreKey) -> list[StoreKey]` | Recursively lists all files under the resolved prefix, returning relative paths as `StoreKey` objects. Returns `[]` if prefix directory does not exist or is not a directory. |

### `ChatEvent` (Pydantic model)

| Method | Type | Signature | Description |
|---|---|---|---|
| `validate_event_id` | classmethod (validator) | `(v: str) -> str` | Validates that `event_id` is a valid UUID string. Raises `ValueError` on invalid format. |
| `ensure_utc` | classmethod (validator) | `(v: datetime) -> datetime` | Strips timezone info from `ts`. If timezone-aware, converts to UTC first then makes naive. |
| `validate_payload` | classmethod (validator) | `(v: dict \| str) -> dict \| str` | Ensures payload is `dict` or `str`. Raises `ValueError` for other types. |
| `model_dump_json` | instance | `(**kwargs) -> str` | Serializes to JSON string with ISO-formatted datetimes. Delegates to Pydantic's `BaseModel.model_dump_json`. |
| `model_validate_json` | classmethod | `(json_data: str, **kwargs) -> ChatEvent` | Parses JSON string into a `ChatEvent`. Delegates to Pydantic's `BaseModel.model_validate_json`. |

**Fields:**
- `event_id: str` — auto-generated UUID4 string
- `ts: datetime` — auto-set to `datetime.utcnow()` at creation
- `role: Literal["user", "assistant", "tool", "system"]`
- `actor: str`
- `kind: Literal["user_message", "assistant_message", "assistant_tool_call", "tool_result", "system_note", "summary"]`
- `payload: dict | str`
- `metadata: dict` — defaults to `{}`

### `ChatSessionMeta` (Pydantic model)

| Method | Type | Signature | Description |
|---|---|---|---|
| `validate_session_id` | classmethod (validator) | `(v: str) -> str` | Validates `session_id` is a valid UUID string. Raises `ValueError` on invalid format. |
| `ensure_utc` | classmethod (validator) | `(v: datetime) -> datetime` | Applied to both `created_at` and `updated_at`. Strips timezone info (converts to UTC first if aware). |
| `updated_at_not_before_created_at` | classmethod (validator) | `(v: datetime, info) -> datetime` | Ensures `updated_at >= created_at`. Raises `ValueError` if violated. |
| `model_dump_json` | instance | `(**kwargs) -> str` | Serializes to JSON string with ISO-formatted datetimes. |
| `model_validate_json` | classmethod | `(json_data: str, **kwargs) -> ChatSessionMeta` | Parses JSON string into `ChatSessionMeta`. |

**Fields:**
- `session_id: str`
- `user_id: str`
- `account_name: str`
- `agent_name: str`
- `participants: list[str]` — defaults to `[]`
- `session_type: Literal["user", "internal"]` — defaults to `"user"`
- `friendly_name: Optional[str]` — defaults to `None`
- `created_at: datetime`
- `updated_at: datetime`
- `tags: list[str]` — defaults to `[]`
- `links: Optional[SessionLinks]` — defaults to `None`
- `metadata: dict` — defaults to `{}`

### `SessionLinks` (Pydantic model)

| Method | Type | Signature | Description |
|---|---|---|---|
| `validate_uuid` | classmethod (validator) | `(v: Optional[str]) -> Optional[str]` | Applied to both `user_session_id` and `internal_session_id`. If non-`None`, validates the string is a valid UUID. Returns `None` as-is. Raises `ValueError` on invalid UUID. |

**Fields:**
- `user_session_id: Optional[str]` — defaults to `None`
- `internal_session_id: Optional[str]` — defaults to `None`

### `Chat2Store` (Facade)

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(store: Chat2Primitives) -> None` | Stores the backend reference as `self._store`. |
| `create_session` | instance | `(user_id, account_name, agent_name, *, session_id=None, friendly_name=None, tags=None, session_type="user", participants=None, links=None) -> ChatSessionMeta` | Creates a new session with metadata. If `session_id` is provided, uses it instead of generating a new UUID (for caller-controlled IDs). Delegates to `jsonl_store.create_session`. |
| `get_session` | instance | `(session_id: str) -> Optional[ChatSessionMeta]` | Returns session metadata or `None` if not found. Delegates to `jsonl_store.get_session_meta`. |
| `update_session` | instance | `(session_id: str, **patch_fields) -> ChatSessionMeta` | Updates session metadata fields by keyword. Raises `ValueError` if session does not exist. Automatically bumps `updated_at`. Delegates to `jsonl_store.update_session_meta`. |
| `delete_session` | instance | `(session_id: str) -> None` | Deletes session metadata and all events. No-op if session does not exist. Delegates to `jsonl_store.delete_session`. |
| `session_exists` | instance | `(session_id: str) -> bool` | Returns `True` if session metadata can be read. |
| `list_sessions` | instance | `(*, account_name=None, agent_name=None, limit=50) -> List[ChatSessionMeta]` | Lists sessions, optionally filtered. Results sorted by `updated_at` descending, capped at `limit`. Delegates to `jsonl_store.list_sessions`. |
| `add_event` | instance | `(session_id: str, event: ChatEvent) -> ChatEvent` | Appends one event to the session's JSONL log. Returns the event. Delegates to `jsonl_store.append_event`. |
| `add_events` | instance | `(session_id: str, events: List[ChatEvent]) -> List[ChatEvent]` | Appends multiple events sequentially. Each call to `append_event` updates `updated_at` individually. Returns the event list. |
| `stream_events` | instance | `(session_id: str) -> Iterator[ChatEvent]` | Yields events from the session's JSONL log in file order. Lazily parsed. Delegates to `jsonl_store.stream_events`. |
| `get_events` | instance | `(session_id, *, start_ts=None, end_ts=None, role_filter=None, actor_filter=None, kind_filter=None) -> List[ChatEvent]` | Reads all events and applies filters. Materialized (not lazy). Delegates to `jsonl_store.read_events`. |
| `reset_events` | instance | `(session_id: str) -> None` | Clears all events while preserving metadata. Raises `ValueError` if session does not exist. Delegates to `jsonl_store.reset_session_events`. |
| `event_count` | instance | `(session_id: int) -> int` | Returns the number of events in a session by materializing the full event stream. Returns 0 if session does not exist. **Note:** the type hint says `session_id: int` (likely a bug — should be `str`). |
| `create_and_add` | instance | `(user_id, account_name, agent_name, events, *, session_id=None, friendly_name=None, tags=None, session_type="user", participants=None, links=None) -> ChatSessionMeta` | Convenience method: creates a session and adds the provided events in one call. Returns the session metadata. |

### `get_last_n_events` (standalone function in `prompt_slice.py`)

| Function | Signature | Description |
|---|---|---|
| `get_last_n_events` | `(events: Iterable[ChatEvent], n: int) -> List[ChatEvent]` | Returns the last N conversational events (kind `user_message` or `assistant_message`) in chronological order. Excludes tool calls, tool results, system notes, and summaries. If `n <= 0`, returns empty list. May return fewer than `n` if the session has fewer matching events. |

### Standalone Functions in `jsonl_store.py`

#### Key Helpers (private)

| Function | Signature | Description |
|---|---|---|
| `_meta_key` | `(session_id: str) -> StoreKey` | Returns `StoreKey(f"sessions/{session_id}/meta.json")`. |
| `_events_key` | `(session_id: str) -> StoreKey` | Returns `StoreKey(f"sessions/{session_id}/events.jsonl")`. |
| `_sessions_prefix` | `() -> StoreKey` | Returns `StoreKey("sessions/")`. |

#### Session Meta Operations

| Function | Signature | Description |
|---|---|---|
| `create_session` | `(store, user_id, account_name, agent_name, *, session_id=None, friendly_name=None, tags=None, session_type="user", participants=None, links=None) -> ChatSessionMeta` | Creates a new session. Writes `meta.json` and an empty `events.jsonl`. If `session_id` is provided, uses it instead of generating a UUID. Both `created_at` and `updated_at` are set to `datetime.now(timezone.utc)` with timezone stripped. |
| `get_session_meta` | `(store, session_id) -> Optional[ChatSessionMeta]` | Reads and parses `meta.json`. Returns `None` if the file does not exist (via `store.read_text` returning `None`). |
| `update_session_meta` | `(store, session_id, **patch_fields) -> ChatSessionMeta` | Reads existing meta, applies `setattr` for each kwarg, bumps `updated_at`, and rewrites. Raises `ValueError` if session not found. Skips fields that don't exist on the model. |
| `delete_session` | `(store, session_id) -> None` | Deletes both `meta.json` and `events.jsonl`. No-op if either does not exist. |
| `list_sessions` | `(store, *, account_name=None, agent_name=None, limit=50) -> List[ChatSessionMeta]` | Lists all `meta.json` files under `sessions/`, parses each, filters by account/agent, sorts by `updated_at` descending, caps at `limit`. Silently skips corrupt meta files (`except Exception: continue`). |

#### Event Operations

| Function | Signature | Description |
|---|---|---|
| `append_event` | `(store, session_id, event) -> ChatEvent` | Serializes event to JSON line + newline, appends to `events.jsonl`, and bumps session `updated_at`. Returns the event. |
| `stream_events` | `(store, session_id) -> Iterator[ChatEvent]` | Reads `events.jsonl`, splits by newlines, and yields parsed `ChatEvent` objects. Yields nothing if file is missing or empty. Each line is parsed with `ChatEvent.model_validate_json`. |
| `read_events` | `(store, session_id, *, start_ts=None, end_ts=None, role_filter=None, actor_filter=None, kind_filter=None) -> List[ChatEvent]` | Materializes all events via `stream_events`, then applies timestamp, role, actor, and kind filters. All filters are AND-ed together. |
| `reset_session_events` | `(store, session_id) -> None` | Truncates `events.jsonl` by writing empty string. Bumps `updated_at`. Raises `ValueError` if session not found. |

## 10. Usage Examples

### Example 1: Create a session, add events, read them back

```python
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.store_primitives import InMemoryStore

store = Chat2Store(InMemoryStore())

# Create a session
meta = store.create_session(
    user_id="john",
    account_name="junwin",
    agent_name="lucy",
    friendly_name="My Chat",
    tags=["demo"],
)

# Add events
store.add_event(ChatEvent(
    role="user",
    actor="john",
    kind="user_message",
    payload="What is the weather?",
))
store.add_event(ChatEvent(
    role="assistant",
    actor="lucy",
    kind="assistant_message",
    payload="It's sunny today!",
))

# Read events back
events = store.get_events(meta.session_id)
for e in events:
    print(f"{e.role}: {e.payload}")
```

### Example 2: Use prompt slicing for conversation history

```python
from src.chat2.prompt_slice import get_last_n_events

all_events = store.stream_events(meta.session_id)
recent = get_last_n_events(all_events, n=5)
# recent contains the last 5 user_message/assistant_message events in order
```

### Example 3: Direct filesystem backend (no facade)

```python
from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.jsonl_store import create_session, append_event, get_session_meta
from src.chat2.models import ChatEvent

fs = FileChat2Primitives("/tmp/chat2_test")
meta = create_session(fs, "john", "junwin", "lucy")
append_event(fs, meta.session_id, ChatEvent(
    role="user", actor="john", kind="user_message", payload="Hello"
))
restored = get_session_meta(fs, meta.session_id)
```

## 11. Edge Cases & Gotchas

1. **`list_sessions` silently skips corrupt meta** — If a `meta.json` file contains unparseable JSON or fails Pydantic validation, it is silently skipped (`except Exception: continue`). The session simply disappears from listings. No error is logged.

2. **`stream_events` does NOT skip corrupt lines** — Unlike `list_sessions`, `stream_events` will raise a Pydantic `ValidationError` (or JSON decode error) if any line is corrupt. There is no per-line error resilience.

3. **`add_events` bumps `updated_at` for every event** — When adding multiple events via `add_events`, each call to `append_event` reads and rewrites `meta.json`, bumping `updated_at` N times. This is O(N) reads + writes of the meta file for N events.

4. **`append_text` in `FileChat2Primitives` and `JfsChat2Primitives` is not atomic** — Writes use Python's `open(path, "a")` with no locking. Concurrent writers can interleave lines. For production, use `JfsChat2Primitives` with `write_text` (which is atomic via temp-file-and-rename) for meta files.

5. **`write_text` in `JfsChat2Primitives` uses `_atomic_write_text` (protected method)** — This reaches into `JsonFileStorage`'s private API (`self._storage._atomic_write_text`). If `JsonFileStorage` changes its internal method, this will break.

6. **`create_session` writes an empty `events.jsonl`** — This is intentional so that `store.exists(_events_key(sid))` can be used to check session existence, and so that `append_event` never needs to create the file. However, `session_exists()` checks meta, not the events file.

7. **`update_session_meta` uses `hasattr` + `setattr`** — Any kwarg passed to `update_session_meta` (or `Chat2Store.update_session`) that matches a field name on `ChatSessionMeta` will be set, including internal fields like `session_id` or `created_at`. There is no allowlist of patchable fields. Setting `created_at` to a value after `updated_at` would violate the Pydantic validator.

8. **`event_count` has wrong type hint** — The signature says `session_id: int` but should be `session_id: str`. The method works correctly because `stream_events` and all downstream functions accept `str`.

9. **`read_events` materializes all events before filtering** — For large sessions, this loads the entire event log into memory. There is no lazy filtering or pagination.

10. **`json` module is imported but unused in `jsonl_store.py`** — The import `import json` is present but `json.dumps` / `json.loads` are never called. All serialization goes through Pydantic's `model_dump_json` / `model_validate_json`.

11. **No custom JSON encoder for `datetime`** — Serialization relies on Pydantic's default JSON encoder, which outputs ISO 8601 strings for datetimes. This is correct but worth noting.

12. **`StoreKey` validation uses `self.value.split("/")`** — This splits on `/`, so a key like `foo/../bar` would be split into `["foo", "..", "bar"]` and `".." in [...]` would catch it. But a key like `foo/..bar` (no slash before `..`) would pass validation — though this is harmless since `..` without surrounding slashes is not a traversal.

13. **`InMemoryStore` is not thread-safe** — The dict-backed store has no locking. For concurrent test scenarios, use `FileChat2Primitives` with `tmp_path`.

14. **`JfsChat2Primitives` root includes `chat2/` subdirectory** — All chat2 data lives under `<storage_base>/chat2/`, which isolates it from legacy v1 data. This is hard-coded and not configurable.

15. **`reset_session_events` assumes meta exists** — It raises `ValueError` if `get_session_meta` returns `None`, but does not check whether the events file exists before writing.

16. **`list_keys` in `FileChat2Primitives` treats the prefix as a directory** — If the prefix resolves to a file (not a directory), it returns `[]`. For example, `list_keys(StoreKey("sessions/abc/meta.json"))` returns `[]`.

17. **Error classes `CorruptEventLogError`, `CorruptMetaError`, `EventNotFoundError`, and `StorageOperationError` are defined but not raised** — They exist as an API contract for future use. Current code uses bare `ValueError`, Pydantic `ValidationError`, or silent `except Exception: continue`.

## 12. Consumers

| Consumer | What it Uses |
|---|---|
| `src/container_config.py` | `Chat2Store`, `JfsChat2Primitives` — constructs the dependency injection wiring |
| `src/http_endpoints/chats_endpoints.py` | `Chat2Store`, `ChatEvent` — session CRUD for the HTTP API |
| `src/message_endpoints/ask_request_handler.py` | `Chat2Store` — session creation for incoming `/ask` requests |
| `src/message_processors/function_calling_processor.py` | `Chat2Store`, `ChatEvent` — event appending during tool-calling loops |
| `src/message_processors/automation_processor.py` | `Chat2Store`, `ChatEvent` — event appending during automation runs |
| `src/prompt_builders/prompt_builder.py` | `Chat2Store`, `get_last_n_events` — loading conversation history for prompt construction |
| `src/handlers/chat2_handler.py` | `Chat2Store`, `ChatEvent`, `JfsChat2Primitives` — tool handler for the `chat2_handler` tool |
| `src/handlers/curate_chat_handler.py` | `JfsChat2Primitives`, `Chat2Store` — tool handler for the `curate_chat` tool |
| `src/curation/archiver.py` | `Chat2Store`, `ChatEvent` — chat archiving logic |
| `src/curation/core.py` | `Chat2Store`, `ChatEvent` — core curation operations |
| `src/curation/resolver.py` | `Chat2Store`, `ChatSessionMeta` — session resolution for curation |
| `src/curation/summarizer.py` | `ChatEvent` — event summarization |
| `src/curation/templates.py` | `ChatEvent` — template-based digest formatting |
| `tests/chat2/test_models.py` | `ChatEvent`, `ChatSessionMeta`, `SessionLinks` |
| `tests/chat2/test_primitives.py` | `Chat2Primitives`, `StoreKey` |
| `tests/chat2/test_facade.py` | `Chat2Store`, `ChatEvent`, `ChatSessionMeta`, `SessionLinks`, `InMemoryStore` |
| `tests/chat2/test_jsonl_store.py` | All `jsonl_store` functions, `ChatEvent`, `SessionLinks`, `Chat2Primitives`, `StoreKey` |
| `tests/chat2/test_fs_primitives.py` | `FileChat2Primitives`, `Chat2Primitives`, `StoreKey`, `jsonl_store` functions, `ChatEvent` |
| `tests/chat2/test_jfs_adapter.py` | `JfsChat2Primitives`, `jsonl_store` functions, `ChatEvent`, `SessionLinks`, `StoreKey` |
| `tests/chat2/test_edge_cases.py` | `FileChat2Primitives`, `jsonl_store` functions, `ChatEvent`, `ChatSessionMeta`, `SessionLinks`, `Chat2Primitives`, `StoreKey` |
| `tests/chat2/test_errors.py` | All error classes from `errors.py` |
| `tests/test_chat2_handler.py` | `Chat2Store`, `InMemoryStore`, `ChatEvent` |
| `tests/test_chats_endpoints.py` | `Chat2Store`, `ChatEvent`, `InMemoryStore` |
| `tests/test_prompt_builder_chat2_integration.py` | `InMemoryStore`, `Chat2Store`, `ChatEvent`, `get_last_n_events` |
