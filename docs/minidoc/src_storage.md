```markdown
---
tags:
  - storage
  - lucyproject
  - Storage
  - JsonFileStorage
  - UserProfile
  - Context
  - Skill
  - DocumentRef
  - EmbeddingRecord
---

## 1. Summary
The `src/storage` module provides a unified interface for storing and retrieving various data types, including user profiles, contexts, documents, and embeddings. It serves as the storage layer for the Lucy project, enabling efficient management of shared state and data persistence across different components.

## 2. Key Classes

| Class                | Base/Parent | Purpose                                           |
|----------------------|-------------|---------------------------------------------------|
| Storage              | ABC         | Abstract interface for various storage operations.|
| JsonFileStorage      | Storage     | JSON-backed implementation of the storage interface.|
| UserProfile          | -           | Represents a user account profile and preferences.|
| Context              | -           | Represents shared state for a conversation.       |
| Skill                | -           | Represents a reusable Markdown skill file.        |
| DocumentRef          | -           | Represents a reference to a document.             |
| EmbeddingRecord      | -           | Represents a vector embedding with metadata.      |

## 3. Source Files

| File                                      | Responsibility                                      | Notable Exports                                      |
|-------------------------------------------|-----------------------------------------------------|------------------------------------------------------|
| `__init__.py`                             | Initializes the storage module and exports classes. | Storage, JsonFileStorage, UserProfile, Context, Skill, DocumentRef, EmbeddingRecord |
| `base.py`                                 | Defines the abstract storage interface.             | Storage                                              |
| `interfaces.py`                           | Contains abstract classes for various storage types.| ContextStore, TasklistStore, DocumentStore, EmbeddingStore, HealthCheckable |
| `json_file_storage.py`                    | Implements JSON-backed storage functionality.       | JsonFileStorage                                      |
| `models.py`                               | Defines data models used in the storage layer.      | UserProfile, Context, Skill, DocumentRef, EmbeddingRecord |
| `json_file_storage_parts/contexts.py`    | Provides context management methods.                 | ContextsMixin                                        |
| `json_file_storage_parts/documents.py`    | Provides document management methods.                | DocumentsMixin                                       |
| `json_file_storage_parts/embeddings.py`  | Provides embedding management methods.               | EmbeddingsMixin                                      |
| `json_file_storage_parts/tasklists.py`    | Provides tasklist management methods.                | TasklistsMixin                                       |

## 4. Dependencies

- **Standard library**
  - abc
  - json
  - os
  - uuid
  - logging
  - pathlib
  - datetime
  - typing

- **Third-party packages**
  - yaml

- **Internal modules**
  - src.tasklists
  - src.topics.schemas
  - src.storage_paths.storage_paths

## 5. Methods (by class)

### Storage

| Method                     | Type         | Signature                                   | Description                                                                 |
|----------------------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_user_profile           | abstract     | def get_user_profile(self, account_name: str) -> Optional[UserProfile] | Returns stored user profile if it exists.                                  |

### JsonFileStorage

| Method                     | Type         | Signature                                   | Description                                                                 |
|----------------------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_user_profile           | instance     | def get_user_profile(self, account_name: str) -> Optional[UserProfile] | Loads user profile from JSON file.                                         |
| health_check               | instance     | def health_check(self) -> bool             | Checks if storage is reachable.                                            |

### ContextsMixin

| Method                     | Type         | Signature                                   | Description                                                                 |
|----------------------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| get_context                | instance     | def get_context(self, account_name: str, context_id: str) -> Optional[Context] | Loads a context from Markdown file.                                        |
| get_or_create_context      | instance     | def get_or_create_context(self, account_name: str, context_id: str, default_data: Optional[Dict[str, Any]] = None) -> Context | Loads or creates a context.                                                |
| save_context               | instance     | def save_context(self, context: Context) -> None | Persists a context as Markdown with YAML frontmatter.                     |

### DocumentsMixin

| Method                     | Type         | Signature                                   | Description                                                                 |
|----------------------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| list_documents             | instance     | def list_documents(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef] | Lists known documents for an account.                                      |
| get_document               | instance     | def get_document(self, document_id: str) -> Optional[DocumentRef] | Gets a document reference by id.                                           |
| upsert_document            | instance     | def upsert_document(self, doc: DocumentRef) -> None | Creates or updates a document reference.                                   |

### EmbeddingsMixin

| Method                     | Type         | Signature                                   | Description                                                                 |
|----------------------------|--------------|---------------------------------------------|-----------------------------------------------------------------------------|
| upsert_embedding           | instance     | def upsert_embedding(self, record: EmbeddingRecord) -> None | Inserts or updates an embedding vector record.                             |
| list_embedding_namespaces  | instance     | def list_embedding_namespaces(self, account_name: str) -> List[str] | Lists available embedding namespaces for an account.                      |
| list_embeddings            | instance     | def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord] | Returns all embedding records in a namespace for an account.              |
| delete_embeddings          | instance     | def delete_embeddings(self, namespace: str, account_name: str, *, source_id: Optional[str] = None, source_type: Optional[str] = None, record_id: Optional[str] = None) -> int | Deletes embedding records matching the given filters.                     |
| query_embeddings           | instance     | def query_embeddings(self, namespaces: List[str], account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]] | Vector search across one or more namespaces.                              |
```