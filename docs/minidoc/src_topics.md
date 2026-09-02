# Documentation for `src/topics` Module

## YAML Front Matter
```yaml
tags:
  - src_topics
  - lucyproject
  - TopicIndex
  - TopicMutations
  - TopicQueries
  - TopicStoreImpl
  - Chat2MigrationError
  - Chat2ReadError
  - TopicError
  - TopicNotFoundError
  - TopicArchivedError
```

## 1. Summary
The `src/topics` module is responsible for managing topics in a messaging or event-driven architecture. It provides functionalities for creating, renaming, linking, unlinking, merging, and archiving topics, as well as querying them. The module fits into a larger architecture that includes an event store, allowing for append-only event logging and retrieval. It solves the problem of managing topic lifecycles and their associated events, ensuring that topics can be derived from an append-only event log while maintaining a clear separation of concerns between data storage and business logic.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Event Sourcing**: The state of topics is derived from an append-only event log, allowing for reconstruction of the current state from historical events.
- **Command Query Responsibility Segregation (CQRS)**: The module separates the mutation (write) and query (read) operations through `TopicMutations` and `TopicQueries`, respectively.
- **Single Responsibility Principle**: Each class has a distinct responsibility, such as managing mutations or handling queries.

Classes within the module relate to each other through composition and inheritance. For example, `TopicStoreImpl` composes both `TopicMutations` and `TopicQueries`, allowing it to serve as a complete store interface. The module does not exhibit a legacy/v2 split, as it is designed to be cohesive and maintain backward compatibility.

Important design decisions include:
- Events never carry `topic_id`, ensuring that membership is derived from the event log.
- The `agent` field is treated as metadata, not as a partition key, allowing for a more flexible event handling mechanism.

## 3. Key Classes
| Class               | Base/Parent | Purpose                                                                 |
|---------------------|-------------|-------------------------------------------------------------------------|
| TopicIndex          | None        | Manages the derived index of topics from the event log.                |
| TopicMutations      | None        | Handles the creation, renaming, linking, unlinking, merging, and archiving of topics. |
| TopicQueries        | None        | Provides read-only access to topic data, including filtering and sorting. |
| TopicStoreImpl      | TopicStore  | Combines mutation and query functionalities into a single interface.    |
| Chat2MigrationError  | Exception   | Base class for errors during chat2 migration.                          |
| Chat2ReadError      | Chat2MigrationError | Raised when a legacy chat2 session cannot be read.                  |
| TopicError          | Exception   | Base class for topic-related errors.                                    |
| TopicNotFoundError  | TopicError  | Raised when a topic operation targets a non-existent topic.             |
| TopicArchivedError  | TopicError  | Raised when an operation targets an archived topic.                     |

## 4. Source Files
| File                | Responsibility                                                                 | Notable Exports                                                                 |
|---------------------|-------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`       | Exports key constants and classes for topic management.                       | `EVENT_LOG_SCHEMA_VERSION`, `Chat2EventPayload`, `TopicIndex`, `TopicMutations` |
| `index.py`          | Manages the derived topic index from the event log.                          | `TopicIndex`                                                                    |
| `migration.py`      | Handles migration from legacy chat2 sessions into topics.                    | `TopicMigrator`, `Chat2ReadError`                                             |
| `mutation.py`       | Provides the API for topic mutations (create, rename, link, etc.).           | `TopicMutations`, `TopicError`, `TopicNotFoundError`, `TopicArchivedError`    |
| `queries.py`        | Provides the API for querying topics.                                        | `TopicQueries`, `TopicStoreImpl`                                              |
| `schemas.py`        | Defines the event schemas and payloads for topics.                           | `TopicEvent`, `TopicRecord`, `EventProvenance`, `normalize_slug`             |
| `streams.py`        | Implements the event store using JSONL files for topic streams.              | `JsonlEventStore`, `StreamNotFoundError`, `StreamArchivedError`               |

## 5. Dependencies
- **Standard library**:
  - `datetime`
  - `json`
  - `pathlib`
  - `re`
  - `unicodedata`
  - `uuid`
- **Third-party packages**:
  - `pydantic`
- **Internal modules**:
  - `src.storage.interfaces`
  - `src.topics.schemas`
- **Optional dependencies**: None.

## 6. Configuration / Settings
| Key                  | Type   | Default | What it controls                                      |
|----------------------|--------|---------|------------------------------------------------------|
| None                 | N/A    | N/A     | None                                                 |

## 7. Exceptions
| Exception            | Base                | When Raised                                                  |
|----------------------|---------------------|-------------------------------------------------------------|
| Chat2MigrationError   | Exception           | During chat2 migration errors.                              |
| Chat2ReadError       | Chat2MigrationError  | When a legacy chat2 session cannot be read.                |
| TopicError           | Exception           | For general topic-related errors.                           |
| TopicNotFoundError   | TopicError          | When a topic operation targets a non-existent topic.       |
| TopicArchivedError   | TopicError          | When an operation targets an archived topic.               |

## 8. Module-Level Constants
| Constant             | Value               |
|----------------------|---------------------|
| EVENT_LOG_SCHEMA_VERSION | 2               |
| INBOX_STREAM         | "inbox"             |
| TOPICS_DIR           | "topics"            |
| SLUG_MIN_LENGTH      | 3                   |
| SLUG_MAX_LENGTH      | 64                  |

## 9. Methods (by class)

### TopicIndex
| Method               | Type       | Signature                                   | Description                                                                 |
|----------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| rebuild              | instance   | `def rebuild(self, account: str) -> None` | Rebuilds the index for the specified account from the event log.           |
| apply_event          | instance   | `def apply_event(self, account: str, event: TopicEvent) -> None` | Applies an event to the index, updating the state of topics.              |
| get_topic            | instance   | `def get_topic(self, account: str, topic_id: str) -> Optional[TopicRecord]` | Retrieves a topic record by its slug.                                     |
| list_topics          | instance   | `def list_topics(self, account: str, *, include_archived: bool = False) -> List[TopicRecord]` | Lists topic records, excluding archived ones by default.                  |

### TopicMutations
| Method               | Type       | Signature                                   | Description                                                                 |
|----------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| create_topic         | instance   | `def create_topic(self, account: str, name: str, slug_proposal: str, *, agent: str, description: Optional[str] = None) -> str` | Creates a new topic and returns its slug.                                 |
| rename_topic         | instance   | `def rename_topic(self, account: str, slug: str, new_name: str, *, agent: str) -> None` | Renames an existing topic.                                                 |
| link_events          | instance   | `def link_events(self, account: str, slug: str, event_ids: List[str], *, agent: str, reason: Optional[str] = None) -> None` | Links events to a topic.                                                  |
| unlink_events        | instance   | `def unlink_events(self, account: str, slug: str, event_ids: List[str], *, agent: str) -> None` | Unlinks events from a topic.                                              |
| merge_topics         | instance   | `def merge_topics(self, account: str, source: str, target: str, *, agent: str) -> None` | Merges one topic into another.                                            |
| archive_topic        | instance   | `def archive_topic(self, account: str, slug: str, *, agent: str, reason: Optional[str] = None) -> None` | Archives a topic, preventing further writes.                             |

### TopicQueries
| Method               | Type       | Signature                                   | Description                                                                 |
|----------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_topic            | instance   | `def get_topic(self, account: str, slug: str) -> Optional[TopicRecord]` | Returns a topic record by slug.                                           |
| list_topics          | instance   | `def list_topics(self, account: str, *, kind: Optional[str] = None, include_archived: bool = False) -> List[TopicRecord]` | Lists topic records, optionally filtered by kind.                        |
| events_in_topic      | instance   | `def events_in_topic(self, account: str, slug: str, *, limit: Optional[int] = None, start_ts: Optional[datetime] = None, end_ts: Optional[datetime] = None) -> List[TopicEvent]` | Returns events in a topic, sorted by timestamp.                          |

## 10. Usage Examples
```python
from src.topics import TopicMutations, TopicQueries, TopicStoreImpl

# Initialize the store
store = TopicStoreImpl(data_root="/path/to/data")

# Create a new topic
slug = store.create_topic(account="user1", name="My Topic", slug_proposal="my-topic", agent="user-agent")

# List topics
topics = store.list_topics(account="user1")

# Get a specific topic
topic = store.get_topic(account="user1", slug=slug)
```

## 11. Edge Cases & Gotchas
- **Error Handling Patterns**: The module follows a fail-fast approach, raising exceptions immediately when invalid operations are attempted (e.g., appending to an archived stream).
- **Legacy Field Mapping**: The migration from chat2 sessions is designed to be idempotent, ensuring that re-running the migration does not lead to duplicate entries.
- **Thread-Safety Concerns**: The module assumes a single-writer model, meaning that concurrent writes are not supported.
- **Known Limitations**: The current implementation does not support semantic search; topic discovery relies on event-based mechanisms.

## 12. Consumers
| Consumer             | What it uses                                           |
|----------------------|-------------------------------------------------------|
| src.storage          | Uses the `EventStore` interface for event management. |
| src.topics.mutation  | Uses the mutation API for topic management.          |
| src.topics.queries   | Uses the query API for retrieving topic information.  |

---

This document provides a comprehensive overview of the `src/topics` module, detailing its architecture, key components, and usage patterns.