# Module Documentation for `src/storage`

## YAML Front Matter
```yaml
tags:
  - src_storage
  - lucyproject
  - Storage
  - JsonFileStorage
  - UserProfile
  - Context
  - Skill
  - DocumentRef
  - EmbeddingRecord
```

## 1. Summary
The `src/storage` module serves as the storage layer for the Lucy project, providing a unified interface for storing and retrieving various data types, including user profiles, contexts, documents, and embeddings. This module is crucial for maintaining the application's state and facilitating data persistence, enabling seamless interactions between different components of the Lucy architecture. By abstracting the storage mechanisms, it allows for flexibility in how data is stored, whether in JSON files or other formats, thus solving the problem of data management and retrieval in a structured manner.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Abstract Base Classes (ABC)**: The `Storage` class serves as an abstract interface for various storage implementations, ensuring that all derived classes adhere to a consistent API.
- **Mixin Pattern**: The use of mixins (e.g., `ContextsMixin`, `DocumentsMixin`, `EmbeddingsMixin`, `TasklistsMixin`) allows for modular functionality, enabling the `JsonFileStorage` class to incorporate various capabilities without a rigid class hierarchy.

The classes within the module relate to each other through composition and inheritance. For instance, `JsonFileStorage` inherits from `Storage` and incorporates multiple mixins to provide a comprehensive storage solution. The design also reflects a clear separation of concerns, with distinct classes handling specific data types and operations.

There is no explicit legacy/v2 split mentioned in the code, but the comments indicate a transition from JSON to Markdown for context storage, suggesting an evolution in data handling practices.

Key design decisions include:
- The choice to use YAML frontmatter for context storage, allowing for structured metadata alongside the content.
- The implementation of atomic file operations to ensure data integrity during writes.

## 3. Key Classes
| Class                  | Base/Parent | Purpose                                                                 |
|------------------------|-------------|-------------------------------------------------------------------------|
| Storage                | ABC         | Abstract base class for storage interfaces.                             |
| JsonFileStorage        | Storage     | JSON-backed storage implementation for Lucy.                           |
| ContextsMixin          | -           | Provides context-related methods for storage.                          |
| DocumentsMixin         | -           | Provides document-related methods for storage.                         |
| EmbeddingsMixin        | -           | Provides embedding-related methods for storage.                        |
| TasklistsMixin         | -           | Provides tasklist-related methods for storage.                         |
| UserProfile            | -           | Represents a user account profile and preferences.                     |
| Context                | -           | Represents shared state for a conversation.                            |
| Skill                  | -           | Represents a reusable Markdown skill file importable by a Context.    |
| DocumentRef            | -           | Represents a reference to a document.                                  |
| EmbeddingRecord        | -           | Represents a vector embedding with metadata.                           |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                             | Initializes the storage module and exports key classes. | `Storage`, `JsonFileStorage`, `UserProfile`, `Context`, `Skill`, `DocumentRef`, `EmbeddingRecord` |
| `base.py`                                 | Defines the abstract storage interface.                 | `Storage`                                                                       |
| `interfaces.py`                           | Defines various storage interfaces.                      | `ContextStore`, `TasklistStore`, `DocumentStore`, `EmbeddingStore`, `HealthCheckable` |
| `json_file_storage.py`                    | Implements JSON-backed storage.                          | `JsonFileStorage`                                                               |
| `json_file_storage_parts/__init__.py`     | Initializes the parts of the JSON file storage.         | None                                                                            |
| `json_file_storage_parts/contexts.py`     | Provides context-related methods for JSON storage.       | `ContextsMixin`                                                                 |
| `json_file_storage_parts/documents.py`    | Provides document-related methods for JSON storage.      | `DocumentsMixin`                                                                |
| `json_file_storage_parts/embeddings.py`   | Provides embedding-related methods for JSON storage.     | `EmbeddingsMixin`                                                               |
| `json_file_storage_parts/tasklists.py`     | Provides tasklist-related methods for JSON storage.      | `TasklistsMixin`                                                                |
| `models.py`                               | Defines data models used in the storage layer.          | `UserProfile`, `Context`, `Skill`, `DocumentRef`, `EmbeddingRecord`          |
| `primitives_embedding_store.py`          | Implements embedding store backed by generic-store.      | `PrimitivesEmbeddingStore`, `build_primitives_embedding_store`                |

## 5. Dependencies
- **Standard library**:
  - `abc`
  - `json`
  - `os`
  - `uuid`
  - `logging`
  - `pathlib`
  - `datetime`
  - `math`
  - `re`
  
- **Third-party packages**:
  - `yaml` (for YAML parsing)
  
- **Internal modules**:
  - `src.tasklists`
  - `src.topics.schemas`
  - `src.storage_paths.storage_paths`
  - `src.keywords.keywords`
  
- **Optional dependencies**:
  - None identified.

## 6. Configuration / Settings
| Key                          | Type   | Default | What it controls                                      |
|------------------------------|--------|---------|------------------------------------------------------|
| None                         | -      | -       | None                                                 |

## 7. Exceptions
| Exception | Base | When Raised |
|-----------|------|-------------|
| None      | -    | None        |

## 8. Module-Level Constants
| Constant | Value | Description |
|----------|-------|-------------|
| None     | -     | None        |

## 9. Methods (by class)

### Storage
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| get_user_profile      | instance     | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Returns stored user profile if it exists. |

### JsonFileStorage
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| get_user_profile      | instance     | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Loads user profile from JSON file. |
| health_check          | instance     | `def health_check(self) -> bool:`         | Checks if storage is reachable. |
| _atomic_write         | instance     | `def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:` | Writes JSON atomically. |
| _load_json            | instance     | `def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:` | Loads JSON data from a file. |
| save_context          | instance     | `def save_context(self, context: Context) -> None:` | Persists a Context as Markdown with YAML frontmatter. |

### ContextsMixin
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| get_context           | instance     | `def get_context(self, account_name: str, context_id: str) -> Optional[Context]:` | Loads a context from Markdown with YAML frontmatter. |
| get_or_create_context | instance     | `def get_or_create_context(self, account_name: str, context_id: str, default_data: Optional[Dict[str, Any]] = None) -> Context:` | Loads a context; if missing, creates and saves it. |
| save_context          | instance     | `def save_context(self, context: Context) -> None:` | Persists a Context as Markdown with YAML frontmatter. |

### DocumentsMixin
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| list_documents        | instance     | `def list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef]:` | Lists known documents for an account. |
| get_document          | instance     | `def get_document(self, document_id: str) -> Optional[DocumentRef]:` | Gets a document reference by id. |
| upsert_document       | instance     | `def upsert_document(self, doc: DocumentRef) -> None:` | Creates or updates a document reference. |

### EmbeddingsMixin
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| upsert_embedding      | instance     | `def upsert_embedding(self, record: EmbeddingRecord) -> None:` | Inserts or updates an embedding vector record. |
| query_embeddings      | instance     | `def query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]]:` | Vector search across namespaces. |
| delete_embeddings     | instance     | `def delete_embeddings(self, namespace: str, account_name: str, source_id: Optional[str] = None, source_type: Optional[str] = None) -> int:` | Deletes embedding records matching filters. |

### TasklistsMixin
| Method                | Type         | Signature                                   | Description |
|-----------------------|--------------|---------------------------------------------|-------------|
| list_tasklists        | instance     | `def list_tasklists(self, account_name: str) -> List[str]:` | Lists tasklists for an account. |
| get_tasklist          | instance     | `def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:` | Loads a tasklist from storage. |
| save_tasklist         | instance     | `def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:` | Saves a tasklist to storage. |

## 10. Usage Examples
```python
from src.storage import JsonFileStorage, UserProfile

# Initialize storage
storage = JsonFileStorage(storage_paths)

# Get user profile
user_profile = storage.get_user_profile("john_doe")

# Save a new context
context = Context(id="context1", account_name="john_doe", text="Sample context")
storage.save_context(context)
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach in many methods, raising exceptions for invalid inputs (e.g., invalid tasklist keys).
- **Backward Compatibility**: The `list_context_names` and `get_skill` methods provide backward compatibility with older storage implementations.
- **Thread Safety**: The atomic write methods ensure that concurrent writes do not corrupt data, but the overall thread safety of the module is not explicitly guaranteed.
- **Known Limitations**: The context import resolution is single-level only, which may limit the complexity of context compositions.

## 12. Consumers
| Consumer                     | What it uses                                      |
|------------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |