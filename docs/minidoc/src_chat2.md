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
  - Chat2Store
  - JfsChat2Primitives
  - FileChat2Primitives
```

## 1. Summary
The `src/chat2` module provides a robust storage system for chat events and sessions, designed to support multi-agent interactions and media-neutral storage primitives. It introduces an append-only JSONL event log system, ensuring backward compatibility with existing storage solutions like `JsonFileStorage`. This module is integral to the overall architecture of the chat application, facilitating efficient session management and event logging, thereby solving the problem of maintaining a reliable and scalable chat history.

## 2. Architecture & Design
The module employs several key design patterns:
- **Facade Pattern**: The `Chat2Store` class acts as a facade, simplifying interactions with the underlying storage primitives.
- **Protocol**: The `Chat2Primitives` interface defines a contract for various storage backends, promoting flexibility and testability.
- **Composition**: The `JfsChat2Primitives` and `FileChat2Primitives` classes compose with existing storage solutions, allowing for seamless integration without modifying the original implementations.

Classes within the module relate through composition and adherence to the `Chat2Primitives` protocol, ensuring that different storage backends can be used interchangeably. The design also reflects a clear separation of concerns, with distinct responsibilities for session management, event handling, and storage operations.

The module does not exhibit a legacy/v2 split, as it is a new implementation designed to replace older storage mechanisms. Important design decisions include the use of JSONL for event logging, which allows for efficient appending and retrieval of events.

## 3. Key Classes
| Class                     | Base/Parent               | Purpose                                                                 |
|---------------------------|---------------------------|-------------------------------------------------------------------------|
| `Chat2Store`              | None                      | High-level interface for managing chat sessions and events.             |
| `JfsChat2Primitives`      | None                      | Adapter for integrating with `JsonFileStorage`.                        |
| `FileChat2Primitives`     | None                      | Filesystem-backed implementation of `Chat2Primitives`.                 |
| `Chat2Error`              | Exception                 | Base class for all chat2-specific exceptions.                          |
| `SessionNotFoundError`    | `Chat2Error`             | Raised when a session operation targets a non-existent session.        |
| `EventNotFoundError`      | `Chat2Error`             | Raised when a specific event cannot be found.                          |
| `CorruptEventLogError`    | `Chat2Error`             | Raised when an event log contains unparseable data.                   |
| `CorruptMetaError`        | `Chat2Error`             | Raised when session metadata cannot be parsed.                         |
| `StorageOperationError`    | `Chat2Error`             | Raised when a storage backend operation fails unexpectedly.            |

## 4. Source Files
| File                          | Responsibility                                         | Notable Exports                                                                 |
|-------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| `src/chat2/__init__.py`       | Initializes the chat2 module and exports key classes | `Chat2Error`, `Chat2Store`, `CorruptEventLogError`, `CorruptMetaError`, `EventNotFoundError`, `SessionNotFoundError`, `StorageOperationError` |
| `src/chat2/adapters/__init__.py` | Initializes the adapters submodule                  | `JfsChat2Primitives`                                                            |
| `src/chat2/adapters/jfs_adapter.py` | Implements JFS adapter for chat2 primitives         | `JfsChat2Primitives`                                                            |
| `src/chat2/errors.py`         | Defines custom exceptions for chat2 operations       | `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, `CorruptEventLogError`, `CorruptMetaError`, `StorageOperationError` |
| `src/chat2/facade.py`         | Provides high-level operations for chat2 storage     | `Chat2Store`                                                                    |
| `src/chat2/fs_primitives.py`   | Implements filesystem-backed storage primitives       | `FileChat2Primitives`                                                           |
| `src/chat2/jsonl_store.py`    | Functions for managing JSONL storage                 | `create_session`, `get_session_meta`, `update_session_meta`, `delete_session`, `list_sessions`, `append_event`, `stream_events`, `read_events`, `reset_session_events` |
| `src/chat2/models.py`         | Defines Pydantic models for chat events and sessions | `ChatEvent`, `ChatSessionMeta`, `SessionLinks`                                 |
| `src/chat2/prompt_slice.py`   | Implements prompt slicing for chat events            | `get_last_n_events`                                                             |
| `src/chat2/store_primitives.py`| Defines storage primitives and interfaces            | `StoreKey`, `Chat2Primitives`, `InMemoryStore`                                 |

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
  - `src.chat2.adapters.jfs_adapter`
  - `src.chat2.store_primitives`
  - `src.storage.json_file_storage`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                | Type   | Default | What it controls |
|--------------------|--------|---------|------------------|
| None               | -      | -       | -                |

## 7. Exceptions
| Exception                  | Base        | When Raised                                           |
|----------------------------|-------------|------------------------------------------------------|
| `Chat2Error`               | `Exception` | Base class for all chat2-specific exceptions.       |
| `SessionNotFoundError`     | `Chat2Error`| When a session operation targets a non-existent session. |
| `EventNotFoundError`       | `Chat2Error`| When a specific event cannot be found.              |
| `CorruptEventLogError`     | `Chat2Error`| When an event log contains unparseable data.       |
| `CorruptMetaError`         | `Chat2Error`| When session metadata cannot be parsed.             |
| `StorageOperationError`     | `Chat2Error`| When a storage backend operation fails unexpectedly. |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     | -     | -           |

## 9. Methods (by class)

### `Chat2Store`
| Method                | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `create_session`      | instance    | `def create_session(self, user_id: str, account_name: str, agent_name: str, *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a new chat session and returns its metadata. If a session ID is provided, it uses that instead of generating a new one.                                                                 |
| `get_session`         | instance    | `def get_session(self, session_id: str) -> Optional[ChatSessionMeta]:` | Retrieves session metadata by ID. Returns `None` if the session does not exist.                                                                                                                         |
| `update_session`      | instance    | `def update_session(self, session_id: str, **patch_fields) -> ChatSessionMeta:` | Updates session metadata fields. Raises `ValueError` if the session does not exist.                                                                                                                     |
| `delete_session`      | instance    | `def delete_session(self, session_id: str) -> None:`                    | Deletes a session and all its events. No-op if the session does not exist.                                                                                                                                 |
| `session_exists`      | instance    | `def session_exists(self, session_id: str) -> bool:`                    | Checks if a session exists.                                                                                                                                                                               |
| `list_sessions`       | instance    | `def list_sessions(self, *, account_name: Optional[str] = None, agent_name: Optional[str] = None, limit: int = 50) -> List[ChatSessionMeta]:` | Lists sessions, optionally filtered by account name and/or agent name. Results are sorted by `updated_at` descending and capped at `limit`.                                                              |
| `add_event`           | instance    | `def add_event(self, session_id: str, event: ChatEvent) -> ChatEvent:`  | Appends an event to a session's event log. Returns the event with its generated event ID.                                                                                                               |
| `add_events`          | instance    | `def add_events(self, session_id: str, events: List[ChatEvent]) -> List[ChatEvent]:` | Appends multiple events to a session's event log. Returns the list of events.                                                                                                                            |
| `stream_events`       | instance    | `def stream_events(self, session_id: str) -> Iterator[ChatEvent]:`      | Yields events from a session in file order.                                                                                                                                                               |
| `get_events`          | instance    | `def get_events(self, session_id: str, *, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None, role_filter: Optional[str] = None, actor_filter: Optional[str] = None, kind_filter: Optional[str] = None) -> List[ChatEvent]:` | Gets events with optional filters. Returns a list of events.                                                                                                                                             |
| `reset_events`        | instance    | `def reset_events(self, session_id: str) -> None:`                      | Clears all events from a session, preserving metadata. Raises `ValueError` if the session does not exist.                                                                                               |
| `event_count`         | instance    | `def event_count(self, session_id: int) -> int:`                        | Returns the number of events in a session. Returns 0 if the session does not exist.                                                                                                                      |
| `create_and_add`      | instance    | `def create_and_add(self, user_id: str, account_name: str, agent_name: str, events: List[ChatEvent], *, session_id: Optional[str] = None, friendly_name: Optional[str] = None, context_name: Optional[str] = None, tags: Optional[List[str]] = None, session_type: str = "user", participants: Optional[List[str]] = None, links: Optional[SessionLinks] = None) -> ChatSessionMeta:` | Creates a session and adds events in one call. Returns the created session metadata.                                                                                                                     |

### `JfsChat2Primitives`
| Method                | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`            | instance    | `def __init__(self, storage: JsonFileStorage) -> None:`                | Initializes the JFS adapter with an existing `JsonFileStorage` instance.                                                                                                                                 |
| `_resolve`            | instance    | `def _resolve(self, key: StoreKey) -> Path:`                           | Resolves a `StoreKey` to an absolute filesystem path, ensuring it stays within the root directory. Raises `ValueError` if the path resolves outside the root.                                                                 |
| `_ensure_parent`      | instance    | `def _ensure_parent(self, path: Path) -> None:`                        | Creates parent directories if they don't exist.                                                                                                                                                          |
| `read_text`           | instance    | `def read_text(self, key: StoreKey) -> Optional[str]:`                | Reads text from the resolved path. Returns `None` if the path does not exist.                                                                                                                           |
| `write_text`          | instance    | `def write_text(self, key: StoreKey, text: str) -> None:`             | Writes text to the resolved path, creating parent directories as needed. Uses atomic write helpers from `JsonFileStorage`.                                                                              |
| `append_text`         | instance    | `def append_text(self, key: StoreKey, text: str) -> None:`            | Appends text to the resolved path, creating parent directories as needed.                                                                                                                                 |
| `exists`              | instance    | `def exists(self, key: StoreKey) -> bool:`                             | Checks if the resolved path exists.                                                                                                                                                                      |
| `delete`              | instance    | `def delete(self, key: StoreKey) -> None:`                             | Deletes the resolved path if it exists.                                                                                                                                                                   |
| `list_keys`           | instance    | `def list_keys(self, prefix: StoreKey) -> list[StoreKey]:`            | Lists all keys under the resolved prefix. Returns an empty list if the prefix does not exist or is not a directory.                                                                                     |

### `FileChat2Primitives`
| Method                | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`            | instance    | `def __init__(self, root_dir: str | Path) -> None:`                  | Initializes the filesystem-backed implementation with a root directory.                                                                                                                                   |
| `_resolve`            | instance    | `def _resolve(self, key: StoreKey) -> Path:`                           | Resolves a `StoreKey` to an absolute filesystem path, ensuring it stays within the root directory. Raises `ValueError` if the path resolves outside the root.                                                                 |
| `read_text`           | instance    | `def read_text(self, key: StoreKey) -> Optional[str]:`                | Reads text from the resolved path. Returns `None` if the path does not exist.                                                                                                                           |
| `write_text`          | instance    | `def write_text(self, key: StoreKey, text: str) -> None:`             | Writes text to the resolved path, creating parent directories as needed.                                                                                                                                 |
| `append_text`         | instance    | `def append_text(self, key: StoreKey, text: str) -> None:`            | Appends text to the resolved path, creating parent directories as needed.                                                                                                                                 |
| `exists`              | instance    | `def exists(self, key: StoreKey) -> bool:`                             | Checks if the resolved path exists.                                                                                                                                                                      |
| `delete`              | instance    | `def delete(self, key: StoreKey) -> None:`                             | Deletes the resolved path if it exists.                                                                                                                                                                   |
| `list_keys`           | instance    | `def list_keys(self, prefix: StoreKey) -> list[StoreKey]:`            | Lists all keys under the resolved prefix. Returns an empty list if the prefix does not exist or is not a directory.                                                                                     |

### `ChatEvent`
| Method                | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `model_dump_json`     | instance    | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the event to JSON, ensuring datetime fields are formatted as ISO strings.                                                                                                                    |
| `model_validate_json`  | class       | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent':` | Parses a JSON string into a `ChatEvent` instance.                                                                                                                                                        |

### `ChatSessionMeta`
| Method                | Type        | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|-------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `model_dump_json`     | instance    | `def model_dump_json(self, **kwargs) -> str:`                          | Serializes the session metadata to JSON, ensuring datetime fields are formatted as ISO strings.                                                                                                         |
| `model_validate_json`  | class       | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta':` | Parses a JSON string into a `ChatSessionMeta` instance.                                                                                                                                                 |

## 10. Usage Examples
```python
from src.chat2 import Chat2Store, JfsChat2Primitives
from src.storage.json_file_storage import JsonFileStorage

# Initialize the storage backend
json_storage = JsonFileStorage('/path/to/storage')
chat_primitives = JfsChat2Primitives(json_storage)

# Create a Chat2Store instance
chat_store = Chat2Store(chat_primitives)

# Create a new chat session
session_meta = chat_store.create_session(
    user_id="user123",
    account_name="account1",
    agent_name="agent1"
)

# Add an event to the session
chat_event = chat_store.add_event(session_meta.session_id, {
    "role": "user",
    "actor": "user123",
    "kind": "user_message",
    "payload": "Hello, how are you?"
})
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising exceptions when operations are attempted on non-existent sessions or events.
- **Backward Compatibility**: The design ensures that existing data from `JsonFileStorage` can be accessed without modification, allowing for a smooth transition to the new storage system.
- **Thread Safety**: The module does not explicitly handle thread safety; concurrent access to the same session may lead to race conditions.
- **Known Limitations**: The current implementation does not support complex querying or filtering beyond basic session and event retrieval.

## 12. Consumers
| Consumer                | What it uses                                                                 |
|-------------------------|------------------------------------------------------------------------------|
| Unknown — trace imports to confirm. | -                                                                              |