# src_storage.md

## YAML Front Matter
```yaml
tags:
  - src_storage
  - lucyproject
  - ChatMessage
  - ChatSession
  - UserProfile
  - AgentProfile
  - ContextState
  - DocumentRef
  - EmbeddingRecord
```

## 1. Summary
The `src/storage` module serves as the storage layer for the Lucy project, providing a unified interface for storing and retrieving various data types, including chat sessions, user and agent profiles, contexts, documents, and embeddings. This module is crucial in the overall architecture as it abstracts the underlying data storage mechanisms, allowing other components of the Lucy project to interact with data in a consistent manner. By offering a structured way to manage data, it solves the problem of data persistence and retrieval, ensuring that user interactions and system states are maintained across sessions.

## 2. Architecture & Design
The module employs several key design patterns, including:

- **Abstract Base Class (ABC)**: The `Storage` class serves as an abstract base class, defining a common interface for all storage implementations. This allows for different storage backends (e.g., JSON, databases) to be easily swapped in and out.
- **Composition**: The `JsonFileStorage` class composes various helper functions from the `json_file_storage_parts` module, promoting separation of concerns and modularity.
- **Data Models**: The use of data classes (e.g., `ChatMessage`, `ChatSession`) provides a clear structure for the data being managed, enhancing readability and maintainability.

The module does not appear to have a legacy/v2 split, indicating a focus on maintaining a single, coherent design. Important design decisions include the choice to store contexts as Markdown files with YAML frontmatter, which allows for more flexible data representation.

## 3. Key Classes
| Class              | Base/Parent | Purpose                                           |
|--------------------|-------------|---------------------------------------------------|
| Storage            | ABC         | Abstract base class for storage implementations.   |
| JsonFileStorage    | Storage     | JSON-backed implementation of the storage interface. |
| ChatMessage        | N/A         | Represents a single message in a chat.            |
| ChatSession        | N/A         | Represents a complete chat session with messages.  |
| UserProfile        | N/A         | Represents a user account profile and preferences. |
| AgentProfile       | N/A         | Represents agent configuration and behavior settings. |
| ContextState       | N/A         | Represents shared state for a conversation.       |
| DocumentRef        | N/A         | Represents a reference to a document.             |
| EmbeddingRecord    | N/A         | Represents a vector embedding with metadata.      |

## 4. Source Files
| File                                      | Responsibility                                         | Notable Exports                                                                 |
|-------------------------------------------|-------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                             | Initializes the storage module and exports key classes. | `Storage`, `JsonFileStorage`, `ChatMessage`, `ChatSession`, `UserProfile`, `AgentProfile`, `ContextState`, `DocumentRef`, `EmbeddingRecord` |
| `base.py`                                 | Defines the abstract storage interface.               | `Storage`                                                                       |
| `json_file_storage.py`                    | Implements JSON-backed storage functionality.         | `JsonFileStorage`                                                               |
| `json_file_storage_parts/__init__.py`     | Placeholder for chat-related helper functions.        | None                                                                            |
| `json_file_storage_parts/chats.py`       | Contains chat-related helper functions.                | Various helper functions for chat session management.                          |
| `models.py`                               | Defines data models used in the storage layer.        | `ChatMessage`, `ChatSession`, `UserProfile`, `AgentProfile`, `ContextState`, `DocumentRef`, `EmbeddingRecord` |

## 5. Dependencies
- **Standard library**:
  - `abc`
  - `datetime`
  - `json`
  - `logging`
  - `os`
  - `pathlib`
  - `re`
  - `uuid`
  - `yaml`
  
- **Third-party packages**:
  - `PyYAML` (for YAML parsing)
  
- **Internal modules**:
  - `src.tasklists` (for task-related types)
  - `src.keywords.keywords` (for keyword extraction)
  - `src.storage_paths.storage_paths` (for storage path management)
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                     | Type   | Default | What it controls |
|-------------------------|--------|---------|-------------------|
| None                    | N/A    | N/A     | None              |

## 7. Exceptions
| Exception              | Base | When Raised |
|------------------------|------|-------------|
| None                   | N/A  | None        |

## 8. Module-Level Constants
| Constant               | Value | Description |
|------------------------|-------|-------------|
| None                   | N/A   | None        |

## 9. Methods (by class)

### Storage
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| create_chat_session        | abstract     | `def create_chat_session(self, account_name: str, agent_name: str, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None) -> ChatSession:` | Creates a new chat session and returns it. |
| get_chat_session           | abstract     | `def get_chat_session(self, session_id: str) -> Optional[ChatSession]:` | Returns a full chat session (including messages), or None. |
| list_chat_sessions         | abstract     | `def list_chat_sessions(self, account_name: str, agent_name: Optional[str] = None, limit: int = 50, before: Optional[datetime] = None) -> List[ChatSession]:` | Lists recent chat sessions for a user. |
| rename_chat_session        | abstract     | `def rename_chat_session(self, session_id: str, friendly_name: str) -> None:` | Updates the human-friendly name for a session. |
| update_chat_session        | abstract     | `def update_chat_session(self, session_id: str, *, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None, summary: Optional[str] = None, importance_score: Optional[float] = None, include_in_context: Optional[bool] = None, metadata: Optional[Dict[str, Any]] = None) -> None:` | Updates chat session metadata. |
| append_chat_message        | abstract     | `def append_chat_message(self, session_id: str, message: ChatMessage) -> None:` | Appends a message to a session. |
| delete_chat_session        | abstract     | `def delete_chat_session(self, session_id: str) -> None:` | Deletes a chat session and all its messages. |
| get_user_profile           | abstract     | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Returns stored user profile if it exists. |
| upsert_user_profile        | abstract     | `def upsert_user_profile(self, profile: UserProfile) -> None:` | Creates or updates user profile. |
| get_agent_profile          | abstract     | `def get_agent_profile(self, name: str) -> Optional[AgentProfile]:` | Returns agent profile. |
| upsert_agent_profile       | abstract     | `def upsert_agent_profile(self, agent: AgentProfile) -> None:` | Creates or updates agent profile. |
| get_context                | abstract     | `def get_context(self, account_name: str, context_id: str) -> Optional[ContextState]:` | Fetches the context state. |
| get_or_create_context      | abstract     | `def get_or_create_context(self, account_name: str, context_id: str) -> ContextState:` | Fetches the context state, creating it if it does not exist. |
| save_context               | abstract     | `def save_context(self, context: ContextState) -> None:` | Inserts or updates a context state. |
| list_context_names         | instance     | `def list_context_names(self, account_name: str) -> List[str]:` | Lists context names for an account. |
| get_skill_text             | instance     | `def get_skill_text(self, account_name: str, skill_name: str) -> Optional[str]:` | Returns the body text of a skill file, or None if missing. |
| list_tasklists             | abstract     | `def list_tasklists(self, account_name: str) -> List[str]:` | Returns a list of persisted tasklist ids for an account. |
| get_tasklist               | abstract     | `def get_tasklist(self, account_name: str, tasklist_name: str) -> Optional[TaskList]:` | Returns a persisted tasklist or None if missing. |
| save_tasklist              | abstract     | `def save_tasklist(self, account_name: str, tasklist_name: str, tasklist: TaskList) -> None:` | Persists a tasklist model for the account. |
| delete_tasklist            | abstract     | `def delete_tasklist(self, account_name: str, tasklist_name: str) -> None:` | Deletes a persisted tasklist. |
| list_documents             | abstract     | `def list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef]:` | Lists known documents for an account. |
| get_document               | abstract     | `def get_document(self, document_id: str) -> Optional[DocumentRef]:` | Gets a document reference by id. |
| upsert_document            | abstract     | `def upsert_document(self, doc: DocumentRef) -> None:` | Creates or updates a document reference. |
| upsert_embedding           | abstract     | `def upsert_embedding(self, record: EmbeddingRecord) -> None:` | Inserts or updates an embedding vector record. |
| query_embeddings           | abstract     | `def query_embeddings(self, namespace: str, account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]]:` | Vector search: returns a list of embeddings and their scores. |
| health_check               | abstract     | `def health_check(self) -> bool:` | Quick check that storage is reachable. |

### JsonFileStorage
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| create_chat_session        | instance     | `def create_chat_session(self, account_name: str, agent_name: str, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None) -> ChatSession:` | Creates a new chat session and returns it. |
| find_chat_sessions_by_friendly_name | instance | `def find_chat_sessions_by_friendly_name(self, account_name: str, agent_name: str, friendly_name: str, limit: int = 20) -> List[ChatSession]:` | Finds sessions by friendly name. |
| get_chat_session           | instance     | `def get_chat_session(self, session_id: str) -> Optional[ChatSession]:` | Loads a single chat session by id. |
| list_chat_sessions         | instance     | `def list_chat_sessions(self, account_name: str, agent_name: Optional[str] = None, limit: int = 50, before: Optional[datetime] = None) -> List[ChatSession]:` | Lists chat sessions for an account. |
| rename_chat_session        | instance     | `def rename_chat_session(self, session_id: str, friendly_name: str) -> None:` | Updates the friendly name for a session. |
| update_chat_session        | instance     | `def update_chat_session(self, session_id: str, *, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None, summary: Optional[str] = None, importance_score: Optional[float] = None, include_in_context: Optional[bool] = None, metadata: Optional[Dict[str, Any]] = None) -> None:` | Updates chat session metadata. |
| append_chat_message        | instance     | `def append_chat_message(self, session_id: str, message: ChatMessage) -> None:` | Appends a message to a session. |
| delete_chat_session        | instance     | `def delete_chat_session(self, session_id: str) -> None:` | Deletes a chat session and all its messages. |
| get_user_profile           | instance     | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Returns stored user profile if it exists. |
| upsert_user_profile        | instance     | `def upsert_user_profile(self, profile: UserProfile) -> None:` | Creates or updates user profile. |
| get_agent_profile          | instance     | `def get_agent_profile(self, name: str) -> Optional[AgentProfile]:` | Returns agent profile. |
| upsert_agent_profile       | instance     | `def upsert_agent_profile(self, agent: AgentProfile) -> None:` | Creates or updates agent profile. |
| get_context                | instance     | `def get_context(self, account_name: str, context_id: str) -> Optional[ContextState]:` | Fetches the context state. |
| get_or_create_context      | instance     | `def get_or_create_context(self, account_name: str, context_id: str, *, default_data: Optional[Dict[str, Any]] = None) -> ContextState:` | Fetches the context state, creating it if it does not exist. |
| save_context               | instance     | `def save_context(self, context: ContextState) -> None:` | Inserts or updates a context state. |
| list_context_names         | instance     | `def list_context_names(self, account_name: str) -> List[str]:` | Lists context names for an account. |
| get_skill_text             | instance     | `def get_skill_text(self, account_name: str, skill_name: str) -> Optional[str]:` | Returns the body text of a skill file, or None if missing. |
| list_tasklists             | instance     | `def list_tasklists(self, account_name: str) -> List[str]:` | Returns a list of persisted tasklist ids for an account. |
| get_tasklist               | instance     | `def get_tasklist(self, account_name: str, tasklist_id: str) -> Optional[TaskList]:` | Returns a persisted tasklist or None if missing. |
| save_tasklist              | instance     | `def save_tasklist(self, account_name: str, tasklist_name: str, tasklist: TaskList) -> None:` | Persists a tasklist model for the account. |
| delete_tasklist            | instance     | `def delete_tasklist(self, account_name: str, tasklist_id: str) -> None:` | Deletes a persisted tasklist. |
| list_documents             | instance     | `def list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef]:` | Lists known documents for an account. |
| get_document               | instance     | `def get_document(self, document_id: str) -> Optional[DocumentRef]:` | Gets a document reference by id. |
| upsert_document            | instance     | `def upsert_document(self, doc: DocumentRef) -> None:` | Creates or updates a document reference. |
| upsert_embedding           | instance     | `def upsert_embedding(self, record: EmbeddingRecord) -> None:` | Inserts or updates an embedding vector record. |
| query_embeddings           | instance     | `def query_embeddings(self, namespace: str, account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]]:` | Vector search: returns a list of embeddings and their scores. |
| health_check               | instance     | `def health_check(self) -> bool:` | Quick check that storage is reachable. |

### json_file_storage_parts/chats
| Method                     | Type         | Signature                                                                 | Description |
|----------------------------|--------------|---------------------------------------------------------------------------|-------------|
| _now_utc                   | function     | `def _now_utc() -> datetime:`                                            | Returns the current UTC time. |
| _parse_dt_utc              | function     | `def _parse_dt_utc(dt_str: str) -> datetime:`                          | Parses ISO timestamps into UTC datetime. |
| _chat_dict_to_session       | function     | `def _chat_dict_to_session(self, data: Dict[str, Any]) -> ChatSession:` | Converts stored JSON dict to ChatSession dataclass. |
| list_chat_sessions         | function     | `def list_chat_sessions(self, account_name: str, agent_name: Optional[str] = None, limit: int = 50, before: Optional[datetime] = None) -> List[ChatSession]:` | Lists chat sessions for an account. |
| get_chat_session           | function     | `def get_chat_session(self, session_id: str) -> Optional[ChatSession]:` | Loads a single chat session by id. |
| find_chat_sessions_by_friendly_name | function | `def find_chat_sessions_by_friendly_name(self, account_name: str, agent_name: str, friendly_name: str, limit: int = 20) -> List[ChatSession]:` | Finds sessions by friendly name. |
| create_chat_session        | function     | `def create_chat_session(self, account_name: str, agent_name: str, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None) -> ChatSession:` | Creates a new chat session and returns it. |
| rename_chat_session        | function     | `def rename_chat_session(self, session_id: str, friendly_name: str) -> None:` | Updates the friendly name for a session. |
| update_chat_session        | function     | `def update_chat_session(self, session_id: str, *, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None, summary: Optional[str] = None, importance_score: Optional[float] = None, include_in_context: Optional[bool] = None, metadata: Optional[Dict[str, Any]] = None) -> None:` | Updates chat session metadata. |
| append_chat_message        | function     | `def append_chat_message(self, session_id: str, message: ChatMessage) -> None:` | Appends a message to a session. |
| delete_chat_session        | function     | `def delete_chat_session(self, session_id: str) -> None:` | Deletes a chat session and all its messages. |

## 10. Usage Examples
```python
from src.storage import JsonFileStorage, ChatMessage

# Initialize storage
storage = JsonFileStorage(base_path="/data/lucy")

# Create a new chat session
session = storage.create_chat_session("junwin", "lucy", "My chat")

# Append a message to the chat session
msg = ChatMessage(role="user", content="Hello!")
storage.append_chat_message(session.id, msg)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module generally follows a fail-safe approach, allowing for idempotent operations (e.g., deleting a non-existent session does not raise an error).
- **Backward Compatibility**: The `rename_chat_session` method serves as a backward-compatible API, ensuring that older code can still function with the new implementation.
- **Thread Safety**: The module does not explicitly mention thread safety, so concurrent access to the storage may lead to race conditions.
- **Known Limitations**: The JSON storage format may not be suitable for very large datasets or high-frequency read/write operations due to potential performance bottlenecks.

## 12. Consumers
| Consumer               | What it uses                                      |
|-----------------------|---------------------------------------------------|
| Unknown               | Trace imports to confirm.                         |