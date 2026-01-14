---
tags:
  - Storage
  - JsonFileStorage
  - ChatMessage
  - ChatSession
  - UserProfile
  - AgentProfile
  - ContextState
  - DocumentRef
  - EmbeddingRecord
  - src.storage
  - storage
---

# src.storage

Storage layer abstractions and the JSON file–backed implementation used by Lucy.

## Modules

- `src/storage/base.py`
  - `Storage` (ABC)

- `src/storage/json_file_storage.py`
  - `JsonFileStorage` (JSON-backed implementation)

- `src/storage/models.py`
  - `ChatMessage`, `ChatSession`
  - `UserProfile`, `AgentProfile`
  - `ContextState`
  - `DocumentRef`
  - `EmbeddingRecord`

- `src/storage_paths/storage_paths.py`
  - `StoragePaths` (authoritative filesystem layout resolver)

## StoragePaths (filesystem layout)

`StoragePaths(storage_root_path: str, storage_namespace: str)` builds:

- `StoragePaths.root` → resolved root path
- `StoragePaths.base` → `<root>/<namespace>` (guarded so namespace cannot escape root)

Key directories (properties):

- `StoragePaths.chats` → `<base>/chats`
- `StoragePaths.contexts` → `<base>/contexts`
- `StoragePaths.documents` → `<base>/documents`
- `StoragePaths.users` → `<base>/users`
- `StoragePaths.agents` → `<base>/agents`

Also:

- `StoragePaths.resolve_relative(relative_path: str) -> pathlib.Path`
  - Safely resolves a user-supplied relative path under `base`.

Note about indexes: StoragePaths does not expose a top-level `indexes` directory or property. Instead, index files are stored alongside the domain objects inside each domain directory (domain-local indexes). For example, per-account indexes live at:

- `chats/<account>/index.json`
- `contexts/<account>/index.json`
- `documents/<account>/index.json`

Code should construct or resolve these domain-local index paths using the appropriate domain directory (e.g., `StoragePaths.chats / account_name / 'index.json'`) rather than relying on a `StoragePaths.indexes` property.

## Storage API (selected)

Defined in `src/storage/base.py`.

Chat sessions:

- `create_chat_session(account_name, agent_name, friendly_name=None, tags=None) -> ChatSession`
- `get_chat_session(session_id) -> Optional[ChatSession]`
- `list_chat_sessions(account_name, agent_name=None, limit=50, before=None) -> List[ChatSession]`
- `update_chat_session(session_id, *, friendly_name=None, tags=None, summary=None, importance_score=None, include_in_context=None, metadata=None) -> None`
- `append_chat_message(session_id, message: ChatMessage) -> None`
- `delete_chat_session(session_id) -> None`

Profiles:

- `get_user_profile(account_name) -> Optional[UserProfile]`
- `upsert_user_profile(profile: UserProfile) -> None`
- `get_agent_profile(name) -> Optional[AgentProfile]`
- `upsert_agent_profile(agent: AgentProfile) -> None`

Contexts:

- `get_context(account_name, context_id) -> Optional[ContextState]`
- `get_or_create_context(account_name, context_id) -> ContextState`
- `save_context(context: ContextState) -> None`
- `list_context_names(account_name) -> List[str]` (non-abstract default in `Storage`)

Documents:

- `list_documents(account_name, kind=None, tag=None, limit=100) -> List[DocumentRef]`
- `get_document(document_id) -> Optional[DocumentRef]`
- `upsert_document(doc: DocumentRef) -> None`

Embeddings:

- `upsert_embedding(record: EmbeddingRecord) -> None`
- `query_embeddings(namespace, account_name, query_vector, top_k=10, filter=None) -> List[Tuple[EmbeddingRecord, float]]`

Other:

- `health_check() -> bool`

## JsonFileStorage notes (current behavior)

- Constructed as: `JsonFileStorage(storage_paths: StoragePaths)`.
- Chat sessions are stored under `StoragePaths.chats / <account_name>/` as `<session_id>.json`.
- Index files are stored per-domain alongside the domain objects. For example, a per-account chat index lives at `StoragePaths.chats / <account_name>/index.json`.

Notes on indexes and layout:

- Index files are stored within each domain directory alongside the domain objects. For example:
  - chats/<account>/index.json
  - contexts/<account>/index.json

Deprecated / compatibility:

- `JsonFileStorage.rename_chat_session(session_id, friendly_name)` is a backward-compatible alias that delegates to `update_chat_session(...)`.
- `JsonFileStorage.save_user(...)` / `load_user(...)` are compatibility wrappers around `upsert_user_profile(...)` / `get_user_profile(...)`.
