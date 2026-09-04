# Module Documentation for `src/chat2`

## YAML Front Matter
```yaml
tags:
  - src_chat2
  - lucyproject
  - Chat2Error
  - CorruptEventLogError
  - CorruptMetaError
  - EventNotFoundError
  - SessionNotFoundError
  - StorageOperationError
  - JfsChat2Primitives
  - FileChat2Primitives
  - Chat2Store
  - CorrelationLink
```

## 1. Summary
The `src/chat2` module provides a comprehensive storage solution for chat events and sessions, designed to support multiple storage backends, including file systems and SQLite databases. Its primary responsibility is to manage chat session metadata and event logs in a media-neutral format, allowing for efficient storage and retrieval of chat data. This module fits into the overall architecture of the Lucy project by enabling multi-agent chat interactions and ensuring backward compatibility with existing storage systems. It addresses the need for a robust, scalable, and flexible storage mechanism for chat applications.

## 2. Architecture & Design
The module employs several key design patterns:
- **Protocol and Interface**: The `Chat2Primitives` protocol defines a common interface for various storage backends, ensuring that all implementations adhere to the same method signatures.
- **Facade Pattern**: The `Chat2Store` class acts as a facade, providing a simplified interface for session and event management while delegating the actual storage operations to the underlying `Chat2Primitives` implementations.
- **Composition**: The `JfsChat2Primitives` and `FileChat2Primitives` classes compose with existing storage solutions, such as `JsonFileStorage`, to extend their functionality without modifying their internal logic.

The module does not exhibit a legacy/v2 split, as it is designed to be a standalone solution. Important design decisions include the use of JSONL for event logs, which allows for efficient appending and reading of events, and the validation of UUIDs for session and event identifiers to ensure data integrity.

## 3. Key Classes
| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| `Chat2Error`              | Exception                   | Base exception for all chat2 module errors.                            |
| `SessionNotFoundError`    | `Chat2Error`               | Raised when a session operation targets a non-existent session.        |
| `EventNotFoundError`      | `Chat2Error`               | Raised when a specific event cannot be found.                          |
| `CorruptEventLogError`    | `Chat2Error`               | Raised when an event log contains unparseable data.                   |
| `CorruptMetaError`        | `Chat2Error`               | Raised when session metadata cannot be parsed.                         |
| `StorageOperationError`    | `Chat2Error`               | Raised when a storage backend operation fails unexpectedly.            |
| `JfsChat2Primitives`      | `Chat2Primitives`          | Adapter for JsonFileStorage to implement Chat2Primitives.              |
| `FileChat2Primitives`     | `Chat2Primitives`          | Filesystem-backed implementation of Chat2Primitives.                   |
| `Chat2Store`              |                            | High-level facade for chat2 storage operations.                        |
| `CorrelationLink`         | `BaseModel`                | Represents a single correlation to event mapping entry.                |

## 4. Source Files
| File                          | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Module-level exports and versioning                     | `Chat2Error`, `Chat2Store`, `CorruptEventLogError`, `CorruptMetaError`, `EventNotFoundError`, `SessionNotFoundError`, `StorageOperationError` |
| `adapters/__init__.py`        | Exports for adapters                                    | `JfsChat2Primitives`                                                            |
| `adapters/jfs_adapter.py`     | JFS adapter for Chat2Primitives                        | `JfsChat2Primitives`                                                            |
| `correlation.py`              | Correlation to event mapping                            | `CorrelationLink`, `link_event`, `get_links`, `get_event_ids`                |
| `errors.py`                   | Custom exception classes                                | `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError` |
| `facade.py`                   | High-level operations for chat storage                 | `Chat2Store`                                                                    |
| `fs_primitives.py`            | Filesystem adapter for Chat2Primitives                 | `FileChat2Primitives`                                                           |
| `jsonl_store.py`              | JSONL store functions for session and event management | `create_session`, `get_session_meta`, `update_session_meta`, `delete_session`, `list_sessions`, `append_event`, `stream_events`, `read_events`, `reset_session_events` |
| `models.py`                   | Pydantic models for chat events and sessions           | `ChatEvent`, `ChatSessionMeta`, `SessionLinks`                                 |
| `prompt_slice.py`            | Prompt slicing for chat events                          | `get_last_n_events`                                                             |
| `sqlite/__init__.py`          | SQLite backend package for chat2 storage primitives     | `SqliteChat2Primitives`, `StoreKey`, `session_meta_key`, `session_events_key`, `sessions_prefix`, `correlation_key` |
| `sqlite/backend.py`           | SQLite backend implementation for storage primitives     | `SqliteChat2Primitives`                                                          |
| `store_primitives.py`         | Media-neutral storage primitives                        | `StoreKey`, `Chat2Primitives`, `InMemoryStore`                                 |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `datetime`
  - `uuid`
  - `sqlite3`
  - `threading`
  - `pathlib`
- **Third-party packages**:
  - `pydantic`
- **Internal modules**:
  - `src.chat2.adapters`
  - `src.chat2.errors`
  - `src.chat2.facade`
  - `src.chat2.correlation`
  - `src.chat2.jsonl_store`
  - `src.chat2.models`
  - `src.chat2.store_primitives`
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls |
|--------------------|--------|---------|------------------|
| None                |        |         | None             |

## 7. Exceptions
| Exception                     | Base        | When Raised                                           |
|-------------------------------|-------------|------------------------------------------------------|
| `Chat2Error`                  | `Exception` | Base exception for all chat2 module errors.         |
| `SessionNotFoundError`        | `Chat2Error`| Raised when a session operation targets a non-existent session. |
| `EventNotFoundError`          | `Chat2Error`| Raised when a specific event cannot be found.       |
| `CorruptEventLogError`        | `Chat2Error`| Raised when an event log contains unparseable data. |
| `CorruptMetaError`            | `Chat2Error`| Raised when session metadata cannot be parsed.      |
| `StorageOperationError`        | `Chat2Error`| Raised when a storage backend operation fails unexpectedly. |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     |       | None        |

## 9. Methods (by class)

### `Chat2Store`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `create_session`           | instance    | `def create_session(self, user_id: str, account_name: str, agent_name: str, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a new chat session and returns the created session metadata. If a session ID is provided, it uses that instead of generating a new UUID.                                                                                                                                                                                                 |
| `get_session`              | instance    | `def get_session(self, session_id: str) -> Optional[ChatSessionMeta]:` | Retrieves session metadata by ID. Returns None if the session does not exist.                                                                                                                                                                                                                                                                 |
| `update_session`           | instance    | `def update_session(self, session_id: str, **patch_fields) -> ChatSessionMeta:` | Updates session metadata fields. Raises ValueError if the session does not exist.                                                                                                                                                                                                                                                                 |
| `delete_session`           | instance    | `def delete_session(self, session_id: str) -> None:`                   | Deletes a session and all its events. No-op if the session does not exist.                                                                                                                                                                                                                                                                 |
| `session_exists`           | instance    | `def session_exists(self, session_id: str) -> bool:`                   | Checks if a session exists.                                                                                                                                                                                                                                                                                                                  |
| `list_sessions`            | instance    | `def list_sessions(self, *, account_name: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[ChatSessionMeta]:` | Lists sessions, optionally filtered by account name and/or agent name. Results are sorted by updated_at descending (most recent first) and capped at the specified limit.                                                                                                                                                                 |
| `add_event`                | instance    | `def add_event(self, session_id: str, event: ChatEvent) -> ChatEvent:` | Appends an event to a session's event log. Returns the event (with its generated event_id).                                                                                                                                                                                                                                                  |
| `add_events`               | instance    | `def add_events(self, session_id: str, events: List[ChatEvent]) -> List[ChatEvent]:` | Appends multiple events to a session's event log. Returns the list of events.                                                                                                                                                                                                                                                                 |
| `stream_events`            | instance    | `def stream_events(self, session_id: str) -> Iterator[ChatEvent]:`     | Yields events from a session in file order.                                                                                                                                                                                                                                                                                                   |
| `get_events`               | instance    | `def get_events(self, session_id: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, role_filter: Optional[str] = None, actor_filter: Optional[str] = None, kind_filter: Optional[str] = None) -> List[ChatEvent]:` | Gets events with optional filters. Returns a list of events.                                                                                                                                                                                                                                                                                |
| `reset_events`             | instance    | `def reset_events(self, session_id: str) -> None:`                     | Clears all events from a session, preserving metadata. Raises ValueError if the session does not exist.                                                                                                                                                                                                                                      |
| `event_count`              | instance    | `def event_count(self, session_id: int) -> int:`                       | Returns the number of events in a session. Returns 0 if the session does not exist.                                                                                                                                                                                                                                                          |
| `link_event`               | instance    | `def link_event(self, correlation_id: Optional[str], session_id: str, event_id: str) -> None:` | Links an event to a correlation id in the sidecar index. Falsy correlation ids (None or '') are a no-op and never raise.                                                                                                                                                                                                                     |
| `get_events_by_correlation`| instance    | `def get_events_by_correlation(self, correlation_id: Optional[str]) -> List[ChatEvent]:` | Returns events linked to a correlation id, in link order. Returns [] when the correlation id is unknown.                                                                                                                                                                                                                                     |
| `create_and_add`           | instance    | `def create_and_add(self, user_id: str, account_name: str, agent_name: str, events: List[ChatEvent], *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a session and adds events in one call. Returns the created session metadata.                                                                                                                                                                                                                                                        |

### `JfsChat2Primitives`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, storage: JsonFileStorage) -> None:`                | Initializes the JFS adapter with an existing JsonFileStorage instance.                                                                                                                                                                                                                                                                     |
| `_resolve`                 | instance    | `def _resolve(self, key: StoreKey) -> Path:`                           | Resolves a StoreKey to an absolute filesystem path, ensuring it stays within the root directory. Raises ValueError if the resolved path escapes the root.                                                                                                                                                                                |
| `_ensure_parent`           | instance    | `def _ensure_parent(self, path: Path) -> None:`                        | Creates parent directories if they don't exist.                                                                                                                                                                                                                                                                                            |
| `read_text`                | instance    | `def read_text(self, key: StoreKey) -> Optional[str]:`                | Reads text from the resolved path corresponding to the StoreKey. Returns None if the path does not exist.                                                                                                                                                                                                                               |
| `write_text`               | instance    | `def write_text(self, key: StoreKey, text: str) -> None:`             | Writes text to the resolved path, creating parent directories as needed. Uses atomic write helper from JsonFileStorage.                                                                                                                                                                                                                   |
| `append_text`              | instance    | `def append_text(self, key: StoreKey, text: str) -> None:`            | Appends text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                 |
| `read_lines`               | instance    | `def read_lines(self, key: StoreKey) -> Optional[list[str]]:`         | Reads lines from the resolved path. Returns None if the path does not exist.                                                                                                                                                                                                                                                              |
| `append_lines`             | instance    | `def append_lines(self, key: StoreKey, lines: Iterable[str]) -> None:`| Appends lines to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                 |
| `truncate`                 | instance    | `def truncate(self, key: StoreKey) -> None:`                           | Clears the content at the resolved path, if it exists.                                                                                                                                                                                                                                                                                    |
| `exists`                   | instance    | `def exists(self, key: StoreKey) -> bool:`                             | Checks if the resolved path exists.                                                                                                                                                                                                                                                                                                        |
| `delete`                   | instance    | `def delete(self, key: StoreKey) -> None:`                             | Deletes the resolved path if it exists.                                                                                                                                                                                                                                                                                                    |
| `list_keys`                | instance    | `def list_keys(self, prefix: StoreKey) -> list[StoreKey]:`            | Lists all keys under the resolved prefix.                                                                                                                                                                                                                                                                                                  |

### `FileChat2Primitives`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                 | instance    | `def __init__(self, root_dir: str | Path) -> None:`                  | Initializes the filesystem-backed implementation with a specified root directory.                                                                                                                                                                                                                                                        |
| `_key`                     | static      | `def _key(key: Union[StoreKey, str]) -> StoreKey:`                     | Coerces the input to a validated StoreKey.                                                                                                                                                                                                                                                                                                 |
| `_resolve`                 | instance    | `def _resolve(self, key: Union[StoreKey, str]) -> Path:`               | Resolves a StoreKey to an absolute filesystem path, ensuring it stays within the root directory. Raises ValueError if the resolved path escapes the root.                                                                                                                                                                                |
| `read_text`                | instance    | `def read_text(self, key: Union[StoreKey, str]) -> Optional[str]:`    | Reads text from the resolved path corresponding to the StoreKey. Returns None if the path does not exist.                                                                                                                                                                                                                               |
| `write_text`               | instance    | `def write_text(self, key: Union[StoreKey, str], text: str) -> None:` | Writes text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                   |
| `append_text`              | instance    | `def append_text(self, key: Union[StoreKey, str], text: str) -> None:`| Appends text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                 |
| `read_lines`               | instance    | `def read_lines(self, key: Union[StoreKey, str]) -> Optional[list[str]]:`| Reads lines from the resolved path. Returns None if the path does not exist.                                                                                                                                                                                                                                                              |
| `append_lines`             | instance    | `def append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None:`| Appends lines to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                 |
| `truncate`                 | instance    | `def truncate(self, key: Union[StoreKey, str]) -> None:`               | Clears the content at the resolved path, if it exists.                                                                                                                                                                                                                                                                                    |
| `exists`                   | instance    | `def exists(self, key: Union[StoreKey, str]) -> bool:`                 | Checks if the resolved path exists.                                                                                                                                                                                                                                                                                                        |
| `delete`                   | instance    | `def delete(self, key: Union[StoreKey, str]) -> None:`                 | Deletes the resolved path if it exists.                                                                                                                                                                                                                                                                                                    |
| `list_keys`                | instance    | `def list_keys(self, prefix: Union[StoreKey, str]) -> list[StoreKey]:`| Lists all keys under the resolved prefix.                                                                                                                                                                                                                                                                                                  |

### `CorrelationLink`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `validate_uuid`            | classmethod | `@field_validator("session_id", "event_id")`                            | Validates that the id is a UUID string.                                                                                                                                                                                                                                                                                                   |
| `ensure_utc`               | classmethod | `@field_validator("ts")`                                                | Normalizes the timestamp to timezone-naive UTC.                                                                                                                                                                                                                                                                                          |

### `ChatEvent`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `validate_event_id`        | classmethod | `@field_validator("event_id")`                                          | Validates that event_id is a valid UUID.                                                                                                                                                                                                                                                                                                   |
| `ensure_utc`               | classmethod | `@field_validator("ts")`                                                | Ensures the timestamp is timezone-naive (assumed UTC).                                                                                                                                                                                                                                                                                    |
| `validate_payload`         | classmethod | `@field_validator("payload")`                                           | Ensures payload is either a dict or string.                                                                                                                                                                                                                                                                                               |
| `model_dump_json`          | instance    | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the model to JSON with datetime as ISO string.                                                                                                                                                                                                                                                                                 |
| `model_validate_json`      | classmethod | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent':` | Parses a JSON string into a ChatEvent.                                                                                                                                                                                                                                                                                                     |

### `ChatSessionMeta`
| Method                     | Type        | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|-------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `validate_session_id`      | classmethod | `@field_validator("session_id")`                                        | Validates that session_id is a valid UUID.                                                                                                                                                                                                                                                                                                 |
| `ensure_utc`               | classmethod | `@field_validator("created_at", "updated_at")`                         | Ensures datetime is timezone-naive (assumed UTC).                                                                                                                                                                                                                                                                                          |
| `updated_at_not_before_created_at` | classmethod | `@field_validator("updated_at")`                                      | Ensures updated_at is not before created_at.                                                                                                                                                                                                                                                                                               |
| `model_dump_json`          | instance    | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the model to JSON with datetime as ISO string.                                                                                                                                                                                                                                                                                 |
| `model_validate_json`      | classmethod | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta':` | Parses a JSON string into a ChatSessionMeta.                                                                                                                                                                                                                                                                                               |

## 10. Usage Examples
```python
from src.chat2 import Chat2Store, JfsChat2Primitives
from src.storage.json_file_storage import JsonFileStorage

# Initialize the storage backend
json_storage = JsonFileStorage('/path/to/storage')
chat_primitives = JfsChat2Primitives(json_storage)

# Create a Chat2Store instance
chat_store = Chat2Store(chat_primitives)

# Create a new session
session_meta = chat_store.create_session(
    user_id="user123",
    account_name="account1",
    agent_name="agent1"
)

# Add an event to the session
event = {
    "role": "user",
    "actor": "user123",
    "kind": "user_message",
    "payload": "Hello, how can I help you?"
}
chat_store.add_event(session_meta.session_id, event)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising exceptions for invalid operations (e.g., attempting to access non-existent sessions or events).
- **UUID Validation**: All session and event IDs are validated to ensure they conform to UUID standards, preventing potential data integrity issues.
- **Thread Safety**: The SQLite backend uses a threading lock to ensure that concurrent access does not lead to data corruption.
- **Backward Compatibility**: The design allows for backward compatibility with existing storage solutions, ensuring that legacy data can still be accessed and manipulated.

## 12. Consumers
| Consumer                     | What it uses                                                                 |
|------------------------------|------------------------------------------------------------------------------|
| `src.chat2.adapters`         | Uses `JfsChat2Primitives` for bridging chat2 primitives to existing storage backends. |
| `src.chat2.facade`           | Uses `Chat2Store` for high-level operations on chat sessions and events.    |
| `src.chat2.correlation`      | Uses correlation functions to manage event mappings.                        |
| `src.chat2.jsonl_store`      | Uses functions for session and event management.                            |
| `src.chat2.sqlite`           | Uses `SqliteChat2Primitives` for SQLite-backed storage operations.          |
| `src.chat2.fs_primitives`    | Uses `FileChat2Primitives` for filesystem-backed storage operations.        |

This document provides a comprehensive overview of the `src/chat2` module, detailing its architecture, key components, and usage patterns.