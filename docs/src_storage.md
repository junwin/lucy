# Documentation for `src/storage` Module

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
The `src/storage` module serves as the storage layer for the Lucy project, providing a unified interface for storing and retrieving various types of data, including user profiles, contexts, documents, and embeddings. This module is crucial for maintaining the application's state and facilitating data persistence across sessions. It addresses the need for a structured and efficient way to manage user-related data and application contexts, ensuring that the system can retrieve and manipulate this data seamlessly.

## 2. Architecture & Design
The module employs several design patterns, including:

- **Abstract Base Classes (ABC)**: The `Storage` class serves as an abstract interface for various storage implementations, ensuring that all derived classes adhere to a consistent API.
- **Mixins**: The use of mixins (e.g., `ContextsMixin`, `DocumentsMixin`, `EmbeddingsMixin`, and `TasklistsMixin`) allows for modular functionality, enabling the `JsonFileStorage` class to incorporate various capabilities without becoming overly complex.
- **Dependency Injection**: The `JsonFileStorage` class receives its configuration through the `StoragePaths` object, promoting flexibility and testability.

The classes within the module relate to each other through inheritance and composition. For instance, `JsonFileStorage` inherits from `Storage` and composes various mixins to provide a comprehensive storage solution. The design also includes backward compatibility considerations, as seen in the non-abstract methods in the `ContextStore` and `TasklistStore` interfaces.

## 3. Key Classes
| Class                  | Base/Parent | Purpose                                                                 |
|------------------------|-------------|-------------------------------------------------------------------------|
| Storage                | ABC         | Abstract base class for storage implementations.                        |
| JsonFileStorage        | Storage     | JSON-backed storage implementation for Lucy.                           |
| ContextsMixin          | -           | Provides context-related methods for storage.                          |
| DocumentsMixin         | -           | Provides document-related methods for storage.                         |
| EmbeddingsMixin        | -           | Provides embedding-related methods for storage.                        |
| TasklistsMixin         | -           | Provides tasklist-related methods for storage.                         |
| UserProfile            | -           | Represents a user account profile and preferences.                     |
| Context                | -           | Represents shared state for a conversation.                            |
| Skill                  | -           | Represents a reusable Markdown skill file.                             |
| DocumentRef            | -           | Represents a reference to a document.                                  |
| EmbeddingRecord        | -           | Represents a vector embedding with metadata.                           |

## 4. Source Files
| File                                      | Responsibility                                           | Notable Exports                                                                 |
|-------------------------------------------|---------------------------------------------------------|---------------------------------------------------------------------------------|
| `__init__.py`                             | Initializes the storage module and exports key classes. | `Storage`, `JsonFileStorage`, `UserProfile`, `Context`, `Skill`, `DocumentRef`, `EmbeddingRecord` |
| `base.py`                                 | Defines the abstract storage interface.                 | `Storage`                                                                       |
| `interfaces.py`                           | Defines storage interfaces for contexts, documents, etc.| `ContextStore`, `TasklistStore`, `DocumentStore`, `EmbeddingStore`, `HealthCheckable` |
| `json_file_storage.py`                    | Implements JSON-backed storage.                         | `JsonFileStorage`                                                               |
| `json_file_storage_parts/__init__.py`    | Placeholder for mixin parts.                            | None                                                                            |
| `json_file_storage_parts/contexts.py`    | Provides context-related methods.                        | `ContextsMixin`                                                                 |
| `json_file_storage_parts/documents.py`   | Provides document-related methods.                       | `DocumentsMixin`                                                                |
| `json_file_storage_parts/embeddings.py`  | Provides embedding-related methods.                      | `EmbeddingsMixin`                                                               |
| `json_file_storage_parts/tasklists.py`   | Provides tasklist-related methods.                       | `TasklistsMixin`                                                                |
| `models.py`                               | Defines data models used in the storage layer.          | `UserProfile`, `Context`, `Skill`, `DocumentRef`, `EmbeddingRecord`          |
| `primitives_embedding_store.py`          | Embedding store backed by a generic-store protocol.     | `PrimitivesEmbeddingStore`, `build_primitives_embedding_store`                |
| `vec0_embedding_store.py`                | Embedding store using SQLite with vector support.       | `Vec0EmbeddingStore`, `DEFAULT_SQLITE_VEC_EXTENSION_PATH`                     |

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
  - `threading`
  
- **Third-party packages**:
  - `PyYAML` (for YAML parsing)
  
- **Internal modules**:
  - `src.tasklists`
  - `src.topics.schemas`
  - `src.storage_paths.storage_paths`
  
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                          | Type   | Default                | What it controls                                      |
|------------------------------|--------|------------------------|------------------------------------------------------|
| None                         | -      | -                      | None                                                 |

## 7. Exceptions
| Exception                   | Base   | When Raised                                   |
|-----------------------------|--------|-----------------------------------------------|
| None                        | -      | None                                          |

## 8. Module-Level Constants
| Constant                    | Value   |
|-----------------------------|---------|
| DEFAULT_RUN_TTL_DAYS       | 2       |

## 9. Methods (by class)

### Storage
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_user_profile           | instance   | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Retrieves the user profile for the specified account name. Returns `None` if not found. |

### JsonFileStorage
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_user_profile           | instance   | `def get_user_profile(self, account_name: str) -> Optional[UserProfile]:` | Retrieves the user profile for the specified account name. Returns `None` if not found. |
| health_check               | instance   | `def health_check(self) -> bool:`         | Checks if the storage is reachable. Returns `True` if accessible, `False` otherwise. |

### ContextsMixin
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_context                | instance   | `def get_context(self, account_name: str, context_id: str) -> Optional[Context]:` | Loads a context from storage. Returns `None` if not found.                |
| get_or_create_context      | instance   | `def get_or_create_context(self, account_name: str, context_id: str, default_data: Optional[Dict[str, Any]] = None) -> Context:` | Loads a context or creates it if missing.                                  |
| save_context               | instance   | `def save_context(self, context: Context) -> None:` | Saves the specified context to storage.                                    |

### DocumentsMixin
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| list_documents             | instance   | `def list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef]:` | Lists documents for the specified account.                                 |
| get_document               | instance   | `def get_document(self, document_id: str) -> Optional[DocumentRef]:` | Retrieves a document by its ID. Returns `None` if not found.              |
| upsert_document            | instance   | `def upsert_document(self, doc: DocumentRef) -> None:` | Creates or updates a document reference.                                   |

### EmbeddingsMixin
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| upsert_embedding           | instance   | `def upsert_embedding(self, record: EmbeddingRecord) -> None:` | Inserts or updates an embedding record.                                     |
| list_embedding_namespaces  | instance   | `def list_embedding_namespaces(self, account_name: str) -> List[str]:` | Lists available embedding namespaces for an account.                       |
| list_embeddings            | instance   | `def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord]:` | Returns all embedding records in a namespace for an account.              |

### TasklistsMixin
| Method                     | Type       | Signature                                   | Description                                                                 |
|----------------------------|------------|---------------------------------------------|-----------------------------------------------------------------------------|
| list_tasklists             | instance   | `def list_tasklists(self, account_name: str) -> List[str]:` | Lists tasklists for the specified account.                                 |
| get_tasklist               | instance   | `def get_tasklist(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:` | Loads a tasklist from storage. Returns `None` if not found.               |
| save_tasklist              | instance   | `def save_tasklist(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:` | Saves a tasklist to storage.                                               |

## 10. Usage Examples
```python
from src.storage import JsonFileStorage, UserProfile

# Initialize storage
storage = JsonFileStorage(storage_paths)

# Retrieve user profile
user_profile = storage.get_user_profile("john_doe")
if user_profile:
    print(f"User: {user_profile.full_name}")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module generally follows a fail-fast approach, raising exceptions when invalid data is encountered (e.g., missing required fields).
- **Backward Compatibility**: The design includes non-abstract methods in interfaces to maintain compatibility with older storage implementations.
- **Thread Safety**: The `Vec0EmbeddingStore` uses a threading lock to ensure thread-safe operations when accessing the SQLite database.

## 12. Consumers
| Consumer                   | What it uses                                      |
|----------------------------|--------------------------------------------------|
| Unknown                    | Unknown — trace imports to confirm.              |

---

This document provides a comprehensive overview of the `src/storage` module, detailing its architecture, key components, and usage patterns.