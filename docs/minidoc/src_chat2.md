```markdown
---
tags:
  - chat2
  - lucyproject
  - Chat2Error
  - CorruptEventLogError
  - CorruptMetaError
  - EventNotFoundError
  - SessionNotFoundError
  - StorageOperationError
  - JfsChat2Primitives
  - Chat2Store
  - FileChat2Primitives
  - InMemoryStore
  - ChatEvent
  - ChatSessionMeta
  - SessionLinks
---

## 1. Summary
The `chat2` module provides a robust storage system for chat events and sessions, designed to support multi-agent interactions and media-neutral storage primitives. It introduces an append-only JSONL event log and ensures backward compatibility with existing storage solutions. This module is integral to the overall architecture of the chat application, facilitating the management of chat sessions and events while ensuring data integrity and accessibility.

The primary problem it addresses is the need for a flexible and reliable storage mechanism that can handle various chat interactions, maintain session metadata, and support future enhancements without disrupting existing functionalities.

## 2. Architecture & Design
The `chat2` module employs several key design patterns:

- **Facade Pattern**: The `Chat2Store` class acts as a facade, providing a simplified interface for session and event management while delegating the actual storage operations to implementations of `Chat2Primitives`.
- **Protocol**: The `Chat2Primitives` interface defines a contract for various storage backends, allowing for different implementations (e.g., filesystem, in-memory) without changing the higher-level logic.
- **Composition**: The `JfsChat2Primitives` and `FileChat2Primitives` classes compose with existing storage solutions, such as `JsonFileStorage`, to enhance functionality without modifying the original classes.

The module does not exhibit a legacy/v2 split, as it is designed to be a standalone solution. Important design decisions include the use of JSONL for event logging, which allows for efficient appending and retrieval of events, and the validation logic in Pydantic models to ensure data integrity.

## 3. Key Classes

| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| `Chat2Error`              | Exception                   | Base exception for all chat2 module errors.                            |
| `SessionNotFoundError`    | `Chat2Error`               | Raised when a session operation targets a non-existent session.        |
| `EventNotFoundError`      | `Chat2Error`               | Raised when a specific event cannot be found.                          |
| `CorruptEventLogError`    | `Chat2Error`               | Raised when an event log contains unparseable data.                   |
| `CorruptMetaError`        | `Chat2Error`               | Raised when session metadata cannot be parsed.                         |
| `StorageOperationError`    | `Chat2Error`               | Raised when a storage backend operation fails unexpectedly.            |
| `JfsChat2Primitives`      | -                          | Adapter for Chat2Primitives backed by JsonFileStorage.                 |
| `Chat2Store`              | -                          | High-level facade for chat2 storage operations.                        |
| `FileChat2Primitives`     | -                          | Filesystem-backed implementation of Chat2Primitives.                   |
| `InMemoryStore`           | -                          | In-memory implementation of Chat2Primitives for testing.               |
| `ChatEvent`               | BaseModel                  | Represents a single chat event in a conversation.                      |
| `ChatSessionMeta`         | BaseModel                  | Metadata for a chat session.                                          |
| `SessionLinks`            | BaseModel                  | Links between different types of sessions.                             |

## 4. Source Files

| File                          | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Module-level exports and documentation                   | `Chat2Error`, `Chat2Store`, `CorruptEventLogError`, `CorruptMetaError`, `EventNotFoundError`, `SessionNotFoundError`, `StorageOperationError` |
| `adapters/__init__.py`        | Exports for adapters                                     | `JfsChat2Primitives`                                                            |
| `adapters/jfs_adapter.py`     | JFS adapter for Chat2Primitives                         | `JfsChat2Primitives`                                                            |
| `errors.py`                   | Custom exception classes for chat2 operations           | `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError` |
| `facade.py`                   | High-level operations for chat2 storage                 | `Chat2Store`                                                                    |
| `fs_primitives.py`            | Filesystem adapter for Chat2Primitives                  | `FileChat2Primitives`                                                           |
| `jsonl_store.py`              | JSONL store functions for chat2                          | `create_session`, `get_session_meta`, `update_session_meta`, `delete_session`, `list_sessions`, `append_event`, `stream_events`, `read_events`, `reset_session_events` |
| `models.py`                   | Pydantic models for chat events and sessions            | `ChatEvent`, `ChatSessionMeta`, `SessionLinks`                                 |
| `prompt_slice.py`             | Prompt slicing for chat events                           | `get_last_n_events`                                                             |
| `store_primitives.py`         | Media-neutral storage primitives                          | `StoreKey`, `Chat2Primitives`, `InMemoryStore`                                |

## 5. Dependencies

- **Standard library**:
  - `datetime`
  - `json`
  - `pathlib`
  - `typing`
  - `uuid`

- **Third-party packages**:
  - `pydantic`

- **Internal modules**:
  - `src.chat2.adapters`
  - `src.chat2.errors`
  - `src.chat2.facade`
  - `src.chat2.jsonl_store`
  - `src.chat2.models`
  - `src.chat2.store_primitives`
  - `src.storage.json_file_storage`

- **Optional dependencies**:
  - None

## 6. Configuration / Settings
None.

## 7. Exceptions

| Exception                   | Base         | When Raised                                                      |
|-----------------------------|--------------|------------------------------------------------------------------|
| `Chat2Error`                | Exception    | Base exception for all chat2 module errors.                     |
| `SessionNotFoundError`      | `Chat2Error` | Raised when a session operation targets a non-existent session. |
| `EventNotFoundError`        | `Chat2Error` | Raised when a specific event cannot be found.                   |
| `CorruptEventLogError`      | `Chat2Error` | Raised when an event log contains unparseable data.            |
| `CorruptMetaError`          | `Chat2Error` | Raised when session metadata cannot be parsed.                  |
| `StorageOperationError`      | `Chat2Error` | Raised when a storage backend operation fails unexpectedly.     |

## 8. Module-Level Constants
None.

## 9. Methods (by class)

### `Chat2Store`

| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `create_session`           | instance     | `def create_session(self, user_id: str, account_name: str, agent_name: str, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a new chat session and returns the created session metadata. If `session_id` is provided, it uses that instead of generating a new UUID.                                                                                                                                                                                                 |
| `get_session`              | instance     | `def get_session(self, session_id: str) -> Optional[ChatSessionMeta]:` | Retrieves session metadata by ID. Returns `None` if the session does not exist.                                                                                                                                                                                                                                                                 |
| `update_session`           | instance     | `def update_session(self, session_id: str, **patch_fields) -> ChatSessionMeta:` | Updates session metadata fields. Raises `ValueError` if the session does not exist.                                                                                                                                                                                                                                                                 |
| `delete_session`           | instance     | `def delete_session(self, session_id: str) -> None:`                   | Deletes a session and all its events. No-op if the session does not exist.                                                                                                                                                                                                                                                                         |
| `session_exists`           | instance     | `def session_exists(self, session_id: str) -> bool:`                   | Checks if a session exists.                                                                                                                                                                                                                                                                                                                        |
| `list_sessions`            | instance     | `def list_sessions(self, *, account_name: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[ChatSessionMeta]:` | Lists sessions, optionally filtered by account name and/or agent name. Results are sorted by `updated_at` descending and capped at `limit`.                                                                                                                                                                                                         |
| `add_event`                | instance     | `def add_event(self, session_id: str, event: ChatEvent) -> ChatEvent:` | Appends an event to a session's event log. Returns the event (with its generated `event_id`).                                                                                                                                                                                                                                                     |
| `add_events`               | instance     | `def add_events(self, session_id: str, events: List[ChatEvent]) -> List[ChatEvent]:` | Appends multiple events to a session's event log. Returns the list of events.                                                                                                                                                                                                                                                                       |
| `stream_events`            | instance     | `def stream_events(self, session_id: str) -> Iterator[ChatEvent]:`     | Yields events from a session in file order.                                                                                                                                                                                                                                                                                                        |
| `get_events`               | instance     | `def get_events(self, session_id: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, role_filter: Optional[str] = None, actor_filter: Optional[str] = None, kind_filter: Optional[str] = None) -> List[ChatEvent]:` | Gets events with optional filters. Returns a list of events.                                                                                                                                                                                                                                                                                      |
| `reset_events`             | instance     | `def reset_events(self, session_id: str) -> None:`                     | Clears all events from a session, preserving metadata. Raises `ValueError` if the session does not exist.                                                                                                                                                                                                                                         |
| `event_count`              | instance     | `def event_count(self, session_id: int) -> int:`                       | Returns the number of events in a session. Returns 0 if the session does not exist.                                                                                                                                                                                                                                                                 |
| `create_and_add`           | instance     | `def create_and_add(self, user_id: str, account_name: str, agent_name: str, events: List[ChatEvent], *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a session and adds events in one call. Returns the created session metadata.                                                                                                                                                                                                                                                               |

### `JfsChat2Primitives`

| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, storage: JsonFileStorage) -> None:`                | Initializes the JFS adapter with an existing `JsonFileStorage` instance.                                                                                                                                                                                                                                                                     |
| `_resolve`                 | instance     | `def _resolve(self, key: StoreKey) -> Path:`                           | Resolves a `StoreKey` to an absolute filesystem path, ensuring it stays within the root directory. Raises `ValueError` if the resolved path is outside the root.                                                                                                                                                                          |
| `_ensure_parent`           | instance     | `def _ensure_parent(self, path: Path) -> None:`                        | Creates parent directories if they don't exist.                                                                                                                                                                                                                                                                                             |
| `read_text`                | instance     | `def read_text(self, key: StoreKey) -> Optional[str]:`                | Reads text from the resolved path. Returns `None` if the path does not exist.                                                                                                                                                                                                                                                                 |
| `write_text`               | instance     | `def write_text(self, key: StoreKey, text: str) -> None:`             | Writes text to the resolved path, creating parent directories as needed. Uses atomic write helpers from `JsonFileStorage`.                                                                                                                                                                                                                   |
| `append_text`              | instance     | `def append_text(self, key: StoreKey, text: str) -> None:`            | Appends text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                   |
| `exists`                   | instance     | `def exists(self, key: StoreKey) -> bool:`                             | Checks if the resolved path exists.                                                                                                                                                                                                                                                                                                          |
| `delete`                   | instance     | `def delete(self, key: StoreKey) -> None:`                             | Deletes the resolved path if it exists.                                                                                                                                                                                                                                                                                                      |
| `list_keys`                | instance     | `def list_keys(self, prefix: StoreKey) -> list[StoreKey]:`            | Lists all keys under the resolved prefix. Returns an empty list if the prefix does not exist or is not a directory.                                                                                                                                                                                                                         |

### `FileChat2Primitives`

| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`                 | instance     | `def __init__(self, root_dir: str | Path) -> None:`                  | Initializes the filesystem-backed implementation with a root directory.                                                                                                                                                                                                                                                                   |
| `_resolve`                 | instance     | `def _resolve(self, key: StoreKey) -> Path:`                           | Resolves a `StoreKey` to an absolute filesystem path, ensuring it stays within the root directory. Raises `ValueError` if the resolved path is outside the root.                                                                                                                                                                          |
| `read_text`                | instance     | `def read_text(self, key: StoreKey) -> Optional[str]:`                | Reads text from the resolved path. Returns `None` if the path does not exist.                                                                                                                                                                                                                                                                 |
| `write_text`               | instance     | `def write_text(self, key: StoreKey, text: str) -> None:`             | Writes text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                     |
| `append_text`              | instance     | `def append_text(self, key: StoreKey, text: str) -> None:`            | Appends text to the resolved path, creating parent directories as needed.                                                                                                                                                                                                                                                                   |
| `exists`                   | instance     | `def exists(self, key: StoreKey) -> bool:`                             | Checks if the resolved path exists.                                                                                                                                                                                                                                                                                                          |
| `delete`                   | instance     | `def delete(self, key: StoreKey) -> None:`                             | Deletes the resolved path if it exists.                                                                                                                                                                                                                                                                                                      |
| `list_keys`                | instance     | `def list_keys(self, prefix: StoreKey) -> list[StoreKey]:`            | Lists all keys under the resolved prefix. Returns an empty list if the prefix does not exist or is not a directory.                                                                                                                                                                                                                         |

### `ChatEvent`

| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `model_dump_json`          | instance     | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the event to JSON, ensuring datetime fields are formatted as ISO strings.                                                                                                                                                                                                                                                      |
| `model_validate_json`      | class        | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent':` | Parses a JSON string into a `ChatEvent` instance.                                                                                                                                                                                                                                                                                          |

### `ChatSessionMeta`

| Method                     | Type         | Signature                                                                 | Description                                                                                                                                                                                                                                                                                                                                 |
|----------------------------|--------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `model_dump_json`          | instance     | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the session metadata to JSON, ensuring datetime fields are formatted as ISO strings.                                                                                                                                                                                                                                          |
| `model_validate_json`      | class        | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta':` | Parses a JSON string into a `ChatSessionMeta` instance.                                                                                                                                                                                                                                                                                    |

## 10. Usage Examples

```python
from src.chat2.facade import Chat2Store
from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
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
chat_store.add_event(session_meta.session_id, {
    "role": "user",
    "actor": "user123",
    "kind": "user_message",
    "payload": "Hello, how can I help you?"
})
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising exceptions when operations cannot be completed (e.g., trying to access a non-existent session).
- **Backward Compatibility**: The design ensures that existing data structures from previous versions can still be accessed and manipulated without data loss.
- **Thread Safety**: The module does not explicitly handle thread safety; concurrent access to the same session may lead to race conditions.
- **Validation Logic**: The Pydantic models enforce strict validation rules, which may raise exceptions if the data does not conform to expected formats.

## 12. Consumers

| Consumer                     | What it uses                                                                 |
|------------------------------|-------------------------------------------------------------------------------|
| `src.chat2.adapters`         | Uses `JfsChat2Primitives` for storage operations.                             |
| `src.chat2.facade`           | Uses `Chat2Store` for high-level session and event management.               |
| `src.chat2.jsonl_store`      | Uses `Chat2Primitives` for session and event storage operations.              |
| `src.chat2.models`           | Defines data models used throughout the module.                               |
| `src.chat2.prompt_slice`     | Uses `ChatEvent` for processing chat events.                                  |
| `src.chat2.fs_primitives`    | Provides filesystem-backed storage for testing.                               |
| `src.chat2.errors`           | Defines custom exceptions for error handling.                                 |
```