---
tags:
  - src_storage
  - lucyproject
  - Storage
  - JsonFileStorage
  - ChatSession
  - ChatMessage
  - ContextState
  - DocumentRef
  - EmbeddingRecord
  - UserProfile
  - AgentProfile
---

# src/storage — Module Overview

## Summary

Unified storage layer for Lucy. Provides an abstract interface (`Storage`) and a concrete JSON-file-backed implementation (`JsonFileStorage`) for persisting chat sessions, user/agent profiles, context states (whiteboards), documents, embeddings, and tasklists. Contexts are stored as Markdown (`.md`) with YAML frontmatter; everything else uses JSON files.

## Key Classes

| Class | Description |
|---|---|
| `Storage` (ABC) | Abstract base defining the full storage contract |
| `JsonFileStorage` | Concrete implementation — JSON files on disk via `StoragePaths` |
| `ChatMessage` | Dataclass — a single chat message (role, content, timestamp, metadata) |
| `ChatSession` | Dataclass — a complete chat session with messages, tags, summary, importance score |
| `UserProfile` | Dataclass — user account profile and preferences |
| `AgentProfile` | Dataclass — agent configuration (model, temperature, processor) |
| `ContextState` | Dataclass — shared state/whiteboard for a conversation |
| `DocumentRef` | Dataclass — reference to a document (metadata only) |
| `EmbeddingRecord` | Dataclass — vector embedding with source metadata |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Package exports — `Storage`, `JsonFileStorage`, all models |
| `base.py` | `Storage` ABC — 20 abstract methods covering all persistence concerns |
| `models.py` | Pydantic-style dataclasses for all storage entities |
| `json_file_storage.py` | `JsonFileStorage` — full JSON/Markdown-backed implementation |
| `json_file_storage_parts/__init__.py` | Package init (placeholder) |
| `json_file_storage_parts/chats.py` | Extracted chat helper functions (CRUD for sessions, messages, index) |

## Dependencies

| Dependency | Usage |
|---|---|
| `src.storage_paths.StoragePaths` | Resolves storage directory paths |
| `src.tasklists.TaskList`, `Task`, `TaskListService` | Tasklist persistence |
| `src.keywords.Keywords` | Keyword extraction for poor-man's document search |
| `yaml` (PyYAML) | YAML frontmatter parsing/writing for context `.md` files |
| `json`, `os`, `uuid`, `pathlib`, `re`, `math`, `logging` | Stdlib — file I/O, ID generation, path resolution, cosine similarity |
| `datetime`, `typing`, `abc`, `dataclasses` | Stdlib — types, ABC, dataclass decorators |

## Methods — `Storage` (ABC)

| Method | Signature | Description |
|---|---|---|
| `create_chat_session` | `(account_name, agent_name, friendly_name, tags) -> ChatSession` | Create a new chat session |
| `get_chat_session` | `(session_id) -> Optional[ChatSession]` | Load a session by ID |
| `list_chat_sessions` | `(account_name, agent_name, limit, before) -> List[ChatSession]` | List recent sessions |
| `rename_chat_session` | `(session_id, friendly_name) -> None` | Update session friendly name |
| `update_chat_session` | `(session_id, *, friendly_name, tags, summary, importance_score, include_in_context, metadata) -> None` | Update session metadata |
| `append_chat_message` | `(session_id, message) -> None` | Append a message to a session |
| `delete_chat_session` | `(session_id) -> None` | Delete session (idempotent) |
| `get_user_profile` | `(account_name) -> Optional[UserProfile]` | Load user profile |
| `upsert_user_profile` | `(profile) -> None` | Create or update user profile |
| `get_agent_profile` | `(name) -> Optional[AgentProfile]` | Load agent profile |
| `upsert_agent_profile` | `(agent) -> None` | Create or update agent profile |
| `get_context` | `(account_name, context_id) -> Optional[ContextState]` | Load context state |
| `get_or_create_context` | `(account_name, context_id) -> ContextState` | Load or create context |
| `save_context` | `(context) -> None` | Insert or update context |
| `list_context_names` | `(account_name) -> List[str]` | List context names (non-abstract, default `[]`) |
| `list_tasklists` | `(account_name) -> List[str]` | List tasklist IDs |
| `get_tasklist` | `(account_name, tasklist_name) -> Optional[TaskList]` | Load a tasklist |
| `save_tasklist` | `(account_name, tasklist_name, tasklist) -> None` | Persist a tasklist |
| `delete_tasklist` | `(account_name, tasklist_name) -> None` | Delete a tasklist (idempotent) |
| `list_documents` | `(account_name, kind, tag, select_limit) -> List[DocumentRef]` | List documents |
| `get_document` | `(document_id) -> Optional[DocumentRef]` | Get document by ID |
| `upsert_document` | `(doc) -> None` | Create or update document |
| `upsert_embedding` | `(record) -> None` | Insert or update embedding |
| `query_embeddings` | `(namespace, account_name, query_vector, top_k, filter) -> List[Tuple[EmbeddingRecord, float]]` | Vector similarity search |
| `health_check` | `() -> bool` | Quick reachability check |
