---
tags:
  - storage
  - dataclass
  - jsonfilestorage
  - account_name
  - abc
  - metadata
  - module
  - session
  - agent
  - profile
  - src/storage
  - lucyproject
---

# Module: `src/storage`

Lucy's storage layer — provides a unified interface for persisting chat sessions, user/agent profiles, contexts, tasklists, documents, and embeddings.

## Source Files

| File | Purpose |
|------|---------|
| `src/storage/__init__.py` | Exports `Storage`, `JsonFileStorage`, and all dataclass models |
| `src/storage/base.py` | `Storage` ABC with 25 abstract methods |
| `src/storage/models.py` | 7 dataclass definitions |
| `src/storage/json_file_storage.py` | `JsonFileStorage` implementation (~500 lines) |
| `src/storage/json_file_storage_parts/__init__.py` | Package placeholder |
| `src/storage/json_file_storage_parts/chats.py` | Chat CRUD helper functions extracted from `JsonFileStorage` |

## Key Classes

| Class | Type | Description |
|-------|------|-------------|
| `Storage` | ABC | Abstract base class — the storage interface contract |
| `JsonFileStorage` | Concrete | JSON-backed implementation using `StoragePaths` for directory layout |
| `ChatMessage` | dataclass | Single message: `role`, `content`, `utc_timestamp`, `metadata` |
| `ChatSession` | dataclass | Complete session: `id`, `account_name`, `agent_name`, `friendly_name`, timestamps, messages, tags, summary, importance_score, include_in_context, metadata |
| `UserProfile` | dataclass | User account: `account_name`, `full_name`, `preferences`, `active` |
| `AgentProfile` | dataclass | Agent config: `name`, `model`, `temperature`, `message_processor`, `config` |
| `ContextState` | dataclass | Shared whiteboard: `id`, `account_name`, `data` dict, `updated_at` |
| `DocumentRef` | dataclass | Document metadata: `id`, `account_name`, `path`, `kind`, `title`, `tags`, `metadata` |
| `EmbeddingRecord` | dataclass | Vector embedding: `id`, `namespace`, `account_name`, `vector`, `source_type`, `source_id`, `source_metadata`, `created_at` |

## Dependencies

**Internal:**
- `src.keywords.keywords` — `Keywords` utility for document search
- `src.storage_paths.storage_paths` — `StoragePaths` for directory layout
- `src.tasklists.task_list` — `TaskList`, `Task` types
- `src.tasklists.service` — `TaskListService` for tasklist persistence
- `src.storage.json_file_storage_parts.chats` — extracted chat CRUD functions

**External:**
- `json`, `os`, `uuid`, `logging`, `pathlib.Path`, `datetime`, `typing`
- `yaml`, `re`, `math`, `abc`, `dataclasses`, `functools`

## Storage ABC — Abstract Methods (25)

### Chat Sessions
- `create_chat_session(account_name, agent_name, friendly_name, tags) -> ChatSession`
- `get_chat_session(session_id) -> Optional[ChatSession]`
- `list_chat_sessions(account_name, agent_name, limit, before) -> List[ChatSession]`
- `rename_chat_session(session_id, friendly_name) -> None`
- `update_chat_session(session_id, *, friendly_name, tags, summary, importance_score, include_in_context, metadata) -> None`
- `append_chat_message(session_id, message) -> None`
- `delete_chat_session(session_id) -> None`

### User / Agent Profiles
- `get_user_profile(account_name) -> Optional[UserProfile]`
- `upsert_user_profile(profile) -> None`
- `get_agent_profile(name) -> Optional[AgentProfile]`
- `upsert_agent_profile(agent) -> None`

### Contexts (Whiteboards)
- `get_context(account_name, context_id) -> Optional[ContextState]`
- `get_or_create_context(account_name, context_id) -> ContextState`
- `save_context(context) -> None`
- `list_context_names(account_name) -> List[str]` *(non-abstract default)*

### Tasklists
- `list_tasklists(account_name) -> List[str]`
- `get_tasklist(account_name, tasklist_name) -> Optional[TaskList]`
- `save_tasklist(account_name, tasklist_name, tasklist) -> None`
- `delete_tasklist(account_name, tasklist_name) -> None`

### Documents
- `list_documents(account_name, kind, tag, select_limit) -> List[DocumentRef]`
- `get_document(document_id) -> Optional[DocumentRef]`
- `upsert_document(doc) -> None`

### Embeddings
- `upsert_embedding(record) -> None`
- `query_embeddings(namespace, account_name, query_vector, top_k, filter) -> List[Tuple[EmbeddingRecord, float]]`

### Health
- `health_check() -> bool`

## JsonFileStorage — Additional Methods

- `_atomic_write(path, data)` — Write JSON atomically via `.tmp` + `os.replace`
- `_atomic_write_text(path, text)` — Write text atomically
- `_load_json(path) -> Optional[Dict]` — Safe JSON load with logging
- `_ensure_dir(path)` — `mkdir(parents=True, exist_ok=True)`
- `_chat_dict_to_session(data) -> ChatSession` — JSON dict → dataclass
- `_tasklists_dir(account_name) -> Path` — Tasklist directory path
- `_tasklist_path(account_name, tasklist_id) -> Path` — Safe resolved path
- `_doc_dict_to_ref(data) -> DocumentRef` — JSON dict → dataclass
- `_cosine_similarity(vec1, vec2) -> float` — Cosine similarity for embedding search
- `search_documents_poor_man(account_name, query, kind, tag, limit) -> List[DocumentRef]` — Keyword-based document search
- `migrate_context_json_to_md()` — One-time migration from `.json` to `.md` contexts
- `save_user(account_name, profile)` — Backward-compat alias for `upsert_user_profile`
- `load_user(account_name) -> Optional[Dict]` — Backward-compat alias for `get_user_profile`
- `find_chat_sessions_by_friendly_name(account_name, agent_name, friendly_name, limit) -> List[ChatSession]` — Case-insensitive substring search
