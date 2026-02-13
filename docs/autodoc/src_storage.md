---
tags:
  - storage
  - contextstate
  - friendly_name
  - tag
  - json
  - chatmessage
  - chatsession
  - embeddingrecord
  - agent_name
  - context_id
  - doc
  - source
  - src/storage
---

# `src/storage`

## Source files
- `src/storage/__init__.py`
- `src/storage/base.py`
- `src/storage/json_file_storage.py`
- `src/storage/models.py`

## Key classes
- **`Storage`** (`src/storage/base.py`): abstract storage interface for Lucy.
- **`JsonFileStorage`** (`src/storage/json_file_storage.py`): JSON/Markdown file-backed implementation of `Storage`.
- **Storage data models** (`src/storage/models.py`):
  - `ChatMessage`, `ChatSession`
  - `UserProfile`, `AgentProfile`
  - `ContextState`
  - `DocumentRef`, `EmbeddingRecord`

## Dependencies
- **stdlib:** `abc`, `dataclasses`, `datetime`, `json`, `logging`, `os`, `pathlib`, `re`, `typing`, `uuid`
- **third-party:** `yaml` (PyYAML)
- **internal:**
  - `src.tasklists` (`Task`, `TaskList`)
  - `src.tasklists.service.TaskListService`
  - `src.tasklists.task_list` (`TaskList`, `Task`)
  - `src.storage_paths.storage_paths.StoragePaths`
  - `src.keywords.keywords.Keywords`

## Methods in the module service/base class
### `Storage` (abstract)
- `create_chat_session(account_name, agent_name, friendly_name=None, tags=None) -> ChatSession`
- `get_chat_session(session_id) -> Optional[ChatSession]`
- `list_chat_sessions(account_name, agent_name=None, limit=50, before=None) -> List[ChatSession]`
- `rename_chat_session(session_id, friendly_name) -> None`
- `update_chat_session(session_id, *, friendly_name=None, tags=None, summary=None, importance_score=None, include_in_context=None, metadata=None) -> None`
- `append_chat_message(session_id, message: ChatMessage) -> None`
- `delete_chat_session(session_id) -> None`

- `get_user_profile(account_name) -> Optional[UserProfile]`
- `upsert_user_profile(profile: UserProfile) -> None`
- `get_agent_profile(name) -> Optional[AgentProfile]`
- `upsert_agent_profile(agent: AgentProfile) -> None`

- `get_context(account_name, context_id) -> Optional[ContextState]`
- `get_or_create_context(account_name, context_id) -> ContextState`
- `save_context(context: ContextState) -> None`
- `list_context_names(account_name) -> List[str]` *(non-abstract default returns `[]`)*

- `list_tasklists(account_name) -> List[str]`
- `get_tasklist(account_name, tasklist_name) -> Optional[TaskList]`
- `save_tasklist(account_name, tasklist_name, tasklist: TaskList) -> None`
- `delete_tasklist(account_name, tasklist_name) -> None`

- `list_documents(account_name, kind=None, tag=None, select_limit=100) -> List[DocumentRef]`
- `get_document(document_id) -> Optional[DocumentRef]`
- `upsert_document(doc: DocumentRef) -> None`

- `upsert_embedding(record: EmbeddingRecord) -> None`
- `query_embeddings(namespace, query_vector, top_k=10, filters=None) -> List[Tuple[EmbeddingRecord, float]]`
- `delete_embeddings(namespace, source_type=None, source_id=None) -> int`
