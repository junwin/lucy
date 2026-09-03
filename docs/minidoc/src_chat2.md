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
The `src/chat2` module provides a comprehensive storage solution for chat events and sessions, designed to support multiple storage backends, including filesystem and SQLite. Its primary responsibility is to manage chat session metadata and event logs in a media-neutral format, allowing for efficient storage and retrieval of chat data. This module fits into the overall architecture of the Lucy project by enabling multi-agent chat interactions, ensuring backward compatibility with existing storage systems, and providing a robust API for developers to manage chat sessions and events seamlessly. The module addresses the need for a flexible and extensible storage system that can handle various data formats and storage mechanisms.

## 2. Architecture & Design
The design of the `src/chat2` module employs several key patterns:
- **Protocol and Dependency Injection**: The `Chat2Primitives` protocol allows for different implementations (e.g., `FileChat2Primitives`, `JfsChat2Primitives`, `SqliteChat2Primitives`), enabling dependency injection for flexibility in storage solutions.
- **Facade Pattern**: The `Chat2Store` class acts as a facade, providing a simplified interface for session and event management while delegating the actual storage operations to the underlying `Chat2Primitives` implementations.
- **Data Validation**: The use of Pydantic models (e.g., `ChatEvent`, `ChatSessionMeta`) ensures that data integrity is maintained through validation and serialization.

The module does not exhibit a legacy/v2 split, as it is designed to be a standalone solution. Important design decisions include the choice to separate session metadata and event logs, allowing for efficient data management and retrieval.

## 3. Key Classes
| Class                     | Base/Parent                | Purpose                                                                 |
|---------------------------|----------------------------|-------------------------------------------------------------------------|
| `Chat2Store`              | None                       | High-level facade for chat storage operations.                          |
| `JfsChat2Primitives`      | None                       | Adapter for JSON File Storage, implementing `Chat2Primitives`.         |
| `FileChat2Primitives`     | None                       | Filesystem-backed implementation of `Chat2Primitives`.                 |
| `SqliteChat2Primitives`   | None                       | SQLite-backed implementation of `Chat2Primitives`.                     |
| `CorrelationLink`         | `BaseModel`                | Represents a mapping between correlation IDs and chat events.          |
| `ChatEvent`               | `BaseModel`                | Represents a single chat event in a conversation.                      |
| `ChatSessionMeta`         | `BaseModel`                | Metadata for a chat session.                                           |

## 4. Source Files
| File                          | Responsibility                                         | Notable Exports                                                                 |
|-------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                 | Module-level exports and versioning                   | `Chat2Error`, `Chat2Store`, `CorruptEventLogError`, `CorruptMetaError`, etc. |
| `adapters/__init__.py`        | Expose adapter classes                                 | `JfsChat2Primitives`                                                            |
| `adapters/jfs_adapter.py`     | JFS adapter for chat storage primitives                | `JfsChat2Primitives`                                                            |
| `correlation.py`              | Correlation to event mapping                           | `CorrelationLink`, `link_event`, `get_links`, `get_event_ids`                |
| `errors.py`                   | Custom exception classes for chat operations           | `Chat2Error`, `SessionNotFoundError`, `EventNotFoundError`, etc.              |
| `facade.py`                   | High-level operations for chat storage                 | `Chat2Store`                                                                    |
| `fs_primitives.py`            | Filesystem adapter for chat storage primitives         | `FileChat2Primitives`                                                           |
| `jsonl_store.py`              | JSONL store functions for chat storage                 | `create_session`, `get_session_meta`, `append_event`, etc.                   |
| `models.py`                   | Pydantic models for chat events and sessions           | `ChatEvent`, `ChatSessionMeta`, `SessionLinks`                                |
| `prompt_slice.py`            | Prompt slicing for chat events                          | `get_last_n_events`                                                            |
| `sqlite/__init__.py`          | SQLite backend package for chat storage primitives      | `SqliteChat2Primitives`, `StoreKey`, etc.                                     |
| `sqlite/backend.py`           | SQLite backend implementation for chat storage          | `SqliteChat2Primitives`                                                         |
| `store_primitives.py`         | Media-neutral storage primitives                        | `StoreKey`, `Chat2Primitives`, `InMemoryStore`                                |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `datetime`
  - `sqlite3`
  - `threading`
  - `pathlib`
  - `typing`
  - `uuid`
  
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
|--------------------|--------|---------|-------------------|
| None                | -      | -       | None              |

## 7. Exceptions
| Exception                     | Base         | When Raised                                           |
|-------------------------------|--------------|------------------------------------------------------|
| `Chat2Error`                  | `Exception`  | Base class for all chat2 module errors.             |
| `SessionNotFoundError`        | `Chat2Error` | Raised when a session operation targets a non-existent session. |
| `EventNotFoundError`          | `Chat2Error` | Raised when a specific event cannot be found.       |
| `CorruptEventLogError`        | `Chat2Error` | Raised when an event log contains unparseable data. |
| `CorruptMetaError`            | `Chat2Error` | Raised when session metadata cannot be parsed.      |
| `StorageOperationError`       | `Chat2Error` | Raised when a storage backend operation fails unexpectedly. |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     | -     | None        |

## 9. Methods (by class)

### `Chat2Store`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `create_session`           | instance     | `def create_session(...) -> ChatSessionMeta`                             | Creates a new chat session and returns its metadata. |
| `get_session`              | instance     | `def get_session(session_id: str) -> Optional[ChatSessionMeta]`        | Retrieves session metadata by ID. |
| `update_session`           | instance     | `def update_session(session_id: str, **patch_fields) -> ChatSessionMeta`| Updates session metadata fields. |
| `delete_session`           | instance     | `def delete_session(session_id: str) -> None`                           | Deletes a session and all its events. |
| `session_exists`           | instance     | `def session_exists(session_id: str) -> bool`                           | Checks if a session exists. |
| `list_sessions`            | instance     | `def list_sessions(...) -> List[ChatSessionMeta]`                       | Lists sessions, optionally filtered. |
| `add_event`                | instance     | `def add_event(session_id: str, event: ChatEvent) -> ChatEvent`        | Appends an event to a session's event log. |
| `add_events`               | instance     | `def add_events(session_id: str, events: List[ChatEvent]) -> List[ChatEvent]` | Appends multiple events to a session's event log. |
| `stream_events`            | instance     | `def stream_events(session_id: str) -> Iterator[ChatEvent]`            | Yields events from a session in file order. |
| `get_events`               | instance     | `def get_events(session_id: str, ...) -> List[ChatEvent]`              | Gets events with optional filters. |
| `reset_events`             | instance     | `def reset_events(session_id: str) -> None`                             | Clears all events from a session, preserving metadata. |
| `event_count`              | instance     | `def event_count(session_id: int) -> int`                               | Returns the number of events in a session. |
| `link_event`               | instance     | `def link_event(correlation_id: Optional[str], session_id: str, event_id: str) -> None` | Links an event to a correlation id. |
| `get_events_by_correlation`| instance     | `def get_events_by_correlation(correlation_id: Optional[str]) -> List[ChatEvent]` | Returns events linked to a correlation id. |
| `create_and_add`           | instance     | `def create_and_add(...) -> ChatSessionMeta`                            | Creates a session and adds events in one call. |

### `JfsChat2Primitives`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `read_text`                | instance     | `def read_text(key: StoreKey) -> Optional[str]`                        | Reads text from the specified key. |
| `write_text`               | instance     | `def write_text(key: StoreKey, text: str) -> None`                     | Writes text to the specified key. |
| `append_text`              | instance     | `def append_text(key: StoreKey, text: str) -> None`                    | Appends text to the specified key. |
| `read_lines`               | instance     | `def read_lines(key: StoreKey) -> Optional[list[str]]`                 | Reads lines from the specified key. |
| `append_lines`             | instance     | `def append_lines(key: StoreKey, lines: Iterable[str]) -> None`        | Appends lines to the specified key. |
| `truncate`                 | instance     | `def truncate(key: StoreKey) -> None`                                   | Truncates the content at the specified key. |
| `exists`                   | instance     | `def exists(key: StoreKey) -> bool`                                     | Checks if the specified key exists. |
| `delete`                   | instance     | `def delete(key: StoreKey) -> None`                                     | Deletes the specified key. |
| `list_keys`                | instance     | `def list_keys(prefix: StoreKey) -> list[StoreKey]`                   | Lists keys under the specified prefix. |

### `FileChat2Primitives`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `read_text`                | instance     | `def read_text(key: Union[StoreKey, str]) -> Optional[str]`            | Reads text from the specified key. |
| `write_text`               | instance     | `def write_text(key: Union[StoreKey, str], text: str) -> None`         | Writes text to the specified key. |
| `append_text`              | instance     | `def append_text(key: Union[StoreKey, str], text: str) -> None`        | Appends text to the specified key. |
| `read_lines`               | instance     | `def read_lines(key: Union[StoreKey, str]) -> Optional[list[str]]`     | Reads lines from the specified key. |
| `append_lines`             | instance     | `def append_lines(key: Union[StoreKey, str], lines: Iterable[str]) -> None` | Appends lines to the specified key. |
| `truncate`                 | instance     | `def truncate(key: Union[StoreKey, str]) -> None`                       | Truncates the content at the specified key. |
| `exists`                   | instance     | `def exists(key: Union[StoreKey, str]) -> bool`                         | Checks if the specified key exists. |
| `delete`                   | instance     | `def delete(key: Union[StoreKey, str]) -> None`                         | Deletes the specified key. |
| `list_keys`                | instance     | `def list_keys(prefix: Union[StoreKey, str]) -> list[StoreKey]`       | Lists keys under the specified prefix. |

### `SqliteChat2Primitives`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `read_text`                | instance     | `def read_text(key: Union[StoreKey, str]) -> Optional[str]`            | Reads text from the specified key. |
| `write_text`               | instance     | `def write_text(key: Union[StoreKey, str], text: str) -> None`         | Writes text to the specified key. |
| `exists`                   | instance     | `def exists(key: Union[StoreKey, str]) -> bool`                         | Checks if the specified key exists. |
| `delete`                   | instance     | `def delete(key: Union[StoreKey, str]) -> None`                         | Deletes the specified key. |
| `read_lines`               | instance     | `def read_lines(key: Union[StoreKey, str]) -> Optional[List[str]]`     | Reads lines from the specified key. |
| `append_lines`             | instance     | `def append_lines(key: Union[StoreKey, str], lines: Iterable[str]) -> None` | Appends lines to the specified key. |
| `truncate`                 | instance     | `def truncate(key: Union[StoreKey, str]) -> None`                       | Truncates the content at the specified key. |
| `list_keys`                | instance     | `def list_keys(prefix: Union[StoreKey, str]) -> List[StoreKey]`       | Lists keys under the specified prefix. |

### `CorrelationLink`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `validate_uuid`            | class method | `@classmethod def validate_uuid(cls, v: str) -> str`                   | Validates that the ID is a UUID string. |

### `ChatEvent`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `validate_event_id`        | class method | `@classmethod def validate_event_id(cls, v: str) -> str`               | Validates that the event ID is a valid UUID. |
| `ensure_utc`               | class method | `@classmethod def ensure_utc(cls, v: datetime) -> datetime`             | Ensures the timestamp is timezone-naive (assumed UTC). |
| `validate_payload`         | class method | `@classmethod def validate_payload(cls, v: dict | str) -> dict | str` | Ensures the payload is either a dict or string. |
| `model_dump_json`          | instance     | `def model_dump_json(self, **kwargs) -> str`                            | Serializes the event to JSON. |
| `model_validate_json`      | class method | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent'` | Parses JSON string into a ChatEvent. |

### `ChatSessionMeta`
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| `validate_session_id`      | class method | `@classmethod def validate_session_id(cls, v: str) -> str`              | Validates that the session ID is a valid UUID. |
| `ensure_utc`               | class method | `@classmethod def ensure_utc(cls, v: datetime) -> datetime`             | Ensures the timestamps are timezone-naive (assumed UTC). |
| `updated_at_not_before_created_at` | class method | `@classmethod def updated_at_not_before_created_at(cls, v: datetime, info) -> datetime` | Ensures updated_at is not before created_at. |
| `model_dump_json`          | instance     | `def model_dump_json(self, **kwargs) -> str`                            | Serializes the session metadata to JSON. |
| `model_validate_json`      | class method | `@classmethod def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta'` | Parses JSON string into ChatSessionMeta. |

## 10. Usage Examples
```python
from src.chat2 import Chat2Store, JfsChat2Primitives
from src.storage.json_file_storage import JsonFileStorage

# Initialize storage
json_storage = JsonFileStorage('/path/to/storage')
chat_storage = JfsChat2Primitives(json_storage)
chat_store = Chat2Store(chat_storage)

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
- **Error Handling**: The module employs a fail-fast approach, raising exceptions for invalid operations (e.g., attempting to access a non-existent session).
- **Data Integrity**: The use of Pydantic models ensures that data is validated before being stored, reducing the risk of corrupt data.
- **Thread Safety**: The SQLite backend uses a threading lock to ensure that concurrent access does not lead to data corruption.
- **Backward Compatibility**: The design allows for backward compatibility with existing storage systems, ensuring that legacy data can still be accessed and managed.

## 12. Consumers
| Consumer                     | What it uses                                         |
|------------------------------|-----------------------------------------------------|
| `src.chat2.adapters`         | Uses `JfsChat2Primitives` for storage operations.   |
| `src.chat2.facade`           | Uses `Chat2Store` for high-level storage operations.|
| `src.chat2.correlation`      | Uses `link_event` and `get_links` for correlation management. |
| `src.chat2.jsonl_store`      | Uses various functions for session and event management. |
| `src.chat2.models`           | Uses Pydantic models for data validation.          |
| `src.chat2.errors`           | Defines and raises custom exceptions.               |

This documentation provides a comprehensive overview of the `src/chat2` module, detailing its architecture, key components, and usage patterns.