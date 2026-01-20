Storage and conversations

This document describes Lucy’s storage layer and the current implementation.
It focuses on chat conversations, on-disk layout, and the JSON-backed storage
used in most running configurations.

Summary of relevant modules

- src/storage/base.py — abstract Storage interface (Storage class).
- src/storage/json_file_storage.py — concrete JSON-backed implementation (JsonFileStorage).
- src/storage/models.py — dataclasses used by the storage layer:
  - ChatMessage, ChatSession
  - UserProfile, AgentProfile
  - ContextState
  - DocumentRef
  - EmbeddingRecord
- src/storage_paths/storage_paths.py — StoragePaths helper providing canonical filesystem locations.

Key APIs (Storage interface)

The Storage ABC in src/storage/base.py defines the contract used throughout the
codebase.

Chat sessions

- create_chat_session(
    account_name: str,
    agent_name: str,
    friendly_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
  ) -> ChatSession

- get_chat_session(session_id: str) -> Optional[ChatSession]

- list_chat_sessions(
    account_name: str,
    agent_name: Optional[str] = None,
    limit: int = 50,
    before: Optional[datetime] = None,
  ) -> List[ChatSession]

- update_chat_session(
    session_id: str,
    *,
    friendly_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    summary: Optional[str] = None,
    importance_score: Optional[float] = None,
    include_in_context: Optional[bool] = None,
    metadata: Optional[Dict[str, Any]] = None,
  ) -> None

- rename_chat_session(session_id: str, friendly_name: str) -> None
  - Compatibility alias that delegates to update_chat_session in JsonFileStorage.

- append_chat_message(session_id: str, message: ChatMessage) -> None

- delete_chat_session(session_id: str) -> None

Profiles

- get_user_profile(account_name: str) -> Optional[UserProfile]
- upsert_user_profile(profile: UserProfile) -> None

- get_agent_profile(name: str) -> Optional[AgentProfile]
- upsert_agent_profile(agent: AgentProfile) -> None

Contexts (“whiteboards”)

- get_context(account_name: str, context_id: str) -> Optional[ContextState]
- get_or_create_context(
    account_name: str,
    context_id: str,
    *,
    default_data: Optional[Dict[str, Any]] = None,
  ) -> ContextState
- save_context(context: ContextState) -> None
- list_context_names(account_name: str) -> List[str]

Documents

- list_documents(account_name: str) -> List[DocumentRef]
- get_document(account_name: str, document_id: str) -> Optional[DocumentRef]
- upsert_document(doc: DocumentRef) -> None

Embeddings

- upsert_embedding(record: EmbeddingRecord) -> None
- query_embeddings(
    namespace: str,
    account_name: str,
    query_vector: List[float],
    top_k: int = 10,
    filter: Optional[Dict[str, Any]] = None,
  ) -> List[Tuple[EmbeddingRecord, float]]

Other

- health_check() -> bool

JsonFileStorage (src/storage/json_file_storage.py)

JsonFileStorage is initialized with a StoragePaths instance:

    JsonFileStorage(storage_paths: StoragePaths)

It stores data under storage_paths.base with the following conventions
(StoragePaths properties map these directories):

- chats/<account_name>/<session_id>.json
  - Full chat session JSON (messages included).

- chats/<account_name>/index.json
  - Per-account summary index mapping session_id -> summary metadata
    (friendly_name, agent_name, account_name, updated_at, include_in_context).

- users/<account_name>.json — user profile.
- agents/<agent_name>.json — agent profile.
- contexts/<account_name>/<context_id>.json — context/whiteboard JSON.
- documents/<account_name>/<document_id>.json — document references.
- embeddings/<account_name>/<namespace>/<id>.json — embedding records.

Note on index files

Index files are stored inside each domain directory rather than in a single
top-level directory. For example, chat indexes live at
chats/<account_name>/index.json. Any domain that needs an index follows the same
pattern (e.g., contexts/<account_name>/index.json or a similar per-account index
file within the domain directory).

On-disk chat JSON shape (common fields)

- id, account_name, agent_name, friendly_name
- created_at, updated_at — ISO8601 timestamps (UTC)
- messages — list of { role, content, utc_timestamp, metadata }
- tags — list of strings
- importance_score — float (default 0.5)
- include_in_context — bool
- summary (optional)
- metadata (optional)

Chat lifecycle and behavior

- Creating a chat session
  - create_chat_session(...) generates a UUID id, sets timestamps, writes a
    minimal JSON file (messages = []), and updates chats/<account_name>/index.json.

- Looking up sessions
  - get_chat_session(session_id) searches all accounts under chats/ for a
    matching <session_id>.json and returns a ChatSession (or None).
  - list_chat_sessions(...) enumerates files under chats/<account_name>/,
    filters by agent and before timestamp, sorts by updated_at desc, and returns
    up to limit results.

- Updating sessions
  - update_chat_session(...) loads the stored JSON, applies changes, updates
    updated_at, writes the file, and keeps index.json in sync.
  - If the session is missing, JsonFileStorage raises ValueError.

- Appending messages
  - append_chat_message(...) normalizes message.utc_timestamp to an aware UTC
    datetime, appends it, and updates updated_at.
  - If the session/file is missing, JsonFileStorage raises FileNotFoundError.

- Deleting sessions
  - delete_chat_session(session_id) removes the per-session JSON file (if
    present) and removes the entry from the per-account index.json.
  - The operation is best-effort and intended to be idempotent.

Documents and simple search

JsonFileStorage exposes list_documents/get_document/upsert_document for
DocumentRef objects.

It also includes search_documents_poor_man(...), a simple keyword-based search
over stored DocumentRef metadata using the project’s Keywords utility.

Embeddings

- upsert_embedding(record)
  - Writes an embedding record JSON under embeddings/<account_name>/<namespace>/<id>.json
    with created_at normalized to UTC.

- query_embeddings(...)
  - Loads embedding JSON files for the given namespace/account, optionally
    applies a simple filter, computes cosine similarity against query_vector,
    and returns the top_k matches sorted by score (desc).

Backwards compatibility / legacy behavior

JsonFileStorage provides compatibility wrappers for older tests and callers:

- save_user(account_name: str, profile: Dict[str, Any])
  - Wraps upsert_user_profile. Preferred API: upsert_user_profile(UserProfile).

- load_user(account_name: str) -> Optional[Dict[str, Any]]
  - Wraps get_user_profile and returns the older dict shape.
  - Preferred API: get_user_profile(account_name) -> UserProfile.

- rename_chat_session(session_id: str, friendly_name: str)
  - Compatibility alias that delegates to update_chat_session.

Notes and caveats

- StoragePaths determines file locations; pass a StoragePaths instance when
  constructing JsonFileStorage.
- Timestamps are stored/parsed as ISO8601; the implementation accepts trailing
  "Z" and naive timestamps (assumed UTC).
- Missing resources are signaled via Python exceptions (not sentinel return
  values) in some methods; callers should handle FileNotFoundError/ValueError.
