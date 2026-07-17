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

# src/storage — Module Documentation

## 1. Summary

Unified persistence layer for Lucy. Provides an abstract interface (`Storage`, an ABC with 24 abstract methods) and a concrete JSON-file-backed implementation (`JsonFileStorage`) that persists all core entities to disk: chat sessions/messages, user/agent profiles, context states (whiteboards), document references, tasklists, and vector embeddings. Contexts are stored as Markdown (`.md`) with YAML frontmatter; everything else uses JSON files. The module sits at the bottom of the architecture — every message processor, handler, and utility that needs durable state goes through `Storage`.

## 2. Architecture & Design

| Pattern | Where / Why |
|---|---|
| **ABC interface-implementation split** | `Storage` (ABC) in `base.py` defines the full contract; `JsonFileStorage` implements it. DI via `injector` across the codebase binds `Storage` → `JsonFileStorage`. |
| **Partial extraction of chat helpers** | `json_file_storage_parts/chats.py` contains extracted pure functions for chat CRUD. `JsonFileStorage` delegates its chat methods to these functions (thin wrappers). This is an in-progress refactor to keep the main class file manageable. |
| **Delegation to domain services** | Tasklist persistence delegates to `TaskListService` (`src/tasklists/service.py`) for loading/saving. Document search delegates to `Keywords` (`src/keywords/keywords.py`) for keyword extraction. |
| **Atomic writes** | All writes use a `.tmp` → `os.replace()` pattern. Two variants: `_atomic_write` (JSON) and `_atomic_write_text` (plain text / Markdown). |
| **Context format migration** | Contexts were originally JSON files (`<id>.json`). They are now Markdown (`.md`) with YAML frontmatter. A `migrate_context_json_to_md()` method handles the one-time conversion, skipping any context that already has an `.md` file. |
| **Idempotent delete** | `delete_chat_session` and `delete_tasklist` are explicitly idempotent — no error if missing. |
| **Fail-soft on read** | `_load_json` returns `None` on JSON decode errors (logged as warning), never raises. |
| **Compatibility wrappers** | `save_user` / `load_user` provide backward-compatible dict-based APIs for older tests. `rename_chat_session` delegates to `update_chat_session`. |
| **Non-abstract default** | `list_context_names` is concrete (not abstract) on `Storage` — returns `[]` — so custom implementations don't break. |

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `Storage` | `ABC` | Abstract contract for all persistence operations (24 abstract methods + 1 concrete default) |
| `JsonFileStorage` | `Storage` | Full JSON-file-backed implementation. Uses `StoragePaths` for directory layout and `TaskListService`/`Keywords` for sub-domains |
| `ChatMessage` | `dataclass` | Single chat message: role, content, timestamp, metadata |
| `ChatSession` | `dataclass` | Full chat session: messages list, tags, summary, importance score, context-eligibility flag |
| `UserProfile` | `dataclass` | User account profile: name, preferences, active flag |
| `AgentProfile` | `dataclass` | Agent configuration: model, temperature, message processor type, config dict |
| `ContextState` | `dataclass` | Shared whiteboard state: id, account_name, data dict, updated_at |
| `DocumentRef` | `dataclass` | Reference to a document: path, kind, title, tags, metadata (not content) |
| `EmbeddingRecord` | `dataclass` | Vector embedding: namespace, vector floats, source_type/id/metadata, created_at |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Package exports | `Storage`, `JsonFileStorage`, `ChatMessage`, `ChatSession`, `UserProfile`, `AgentProfile`, `ContextState`, `DocumentRef`, `EmbeddingRecord` |
| `base.py` | `Storage` ABC — 24 abstract + 1 concrete method | `Storage` |
| `models.py` | All dataclass models (7 classes) | `ChatMessage`, `ChatSession`, `UserProfile`, `AgentProfile`, `ContextState`, `DocumentRef`, `EmbeddingRecord` |
| `json_file_storage.py` | Concrete `JsonFileStorage` — full persistence with helpers, migration, poor-man's search, embeddings | `JsonFileStorage` |
| `json_file_storage_parts/__init__.py` | Placeholder sub-package init | `__all__ = []` (empty; namespace marker) |
| `json_file_storage_parts/chats.py` | Extracted chat CRUD functions (`create`, `get`, `list`, `update`, `append`, `delete`, `rename`, `find_by_friendly_name`, `_chat_dict_to_session`) | All functions are called via `JsonFileStorage` delegation; not directly exported to package top-level |

## 5. Dependencies

### Standard library
`abc`, `datetime`, `json`, `logging`, `math`, `os`, `pathlib`, `re`, `typing`, `uuid`

### Third-party packages
| Package | Usage |
|---|---|
| `yaml` (PyYAML) | Parsing and emitting YAML frontmatter in context `.md` files |
| `injector` | (Declared as a dep via DI system; not imported directly in storage files) |

### Internal modules
| Module | Used by | Purpose |
|---|---|---|
| `src.keywords.keywords.Keywords` | `JsonFileStorage` | Keyword extraction for poor-man's document search |
| `src.storage_paths.storage_paths.StoragePaths` | `JsonFileStorage` | Resolves all storage directory paths |
| `src.tasklists.task_list.TaskList, Task` | `base.py`, `json_file_storage.py` | Tasklist model types for CRUD (compatibility re-export from `src.tasklists`) |
| `src.tasklists.service.TaskListService` | `JsonFileStorage` | Loading/saving tasklists from disk |
| `src.storage.models.*` | `base.py`, `chats.py`, `__init__.py` | All domain dataclasses |
| `src.storage.json_file_storage_parts.chats` | `json_file_storage.py` | Extracted chat helper functions |

### Optional dependencies
None — all imports are required.

## 6. Configuration / Settings

The module does **not** read from `ConfigManager` directly. Configuration is implicit via the `StoragePaths` object passed to the `JsonFileStorage` constructor:

| Parameter | Type | Source | What it controls |
|---|---|---|---|
| `storage_paths.base` | `Path` | `StoragePaths` constructor (typically `data/` under the repo root) | Root of all data directories |
| `storage_paths.chats` | `Path` | Derived from `base` | Chat session JSON files (`chats/<account>/<id>.json` + `index.json`) |
| `storage_paths.users` | `Path` | Derived from `base` | User profile JSON files (`users/<account>.json`) |
| `storage_paths.agents` | `Path` | Derived from `base` | Agent profile JSON files (`agents/<name>.json`) |
| `storage_paths.contexts` | `Path` | Derived from `base` | Context Markdown files (`contexts/<account>/<id>.md`) |
| `storage_paths.documents` | `Path` | Derived from `base` | Document reference JSON files (`documents/<account>/<id>.json`) |
| `storage_paths.tasklists` | `Path` | Derived from `base` | Tasklist JSON files (`tasklists/<account>/<id>.json`) |
| `storage_paths.resolve_relative(rel)` | method | `StoragePaths` | Resolves safe sub-paths for tasklist storage (prevents path traversal) |

## 7. Exceptions

**None.** This module defines no custom exception classes. It uses standard exceptions:

- `ValueError` — raised by `update_chat_session` when the session or its data is missing; raised by `save_tasklist` for invalid tasklist names.
- `FileNotFoundError` — raised by `append_chat_message` when the session or its chat JSON is missing.

All JSON decode errors are caught internally and logged as warnings (fail-soft).

## 8. Module-Level Constants

| Name | Location | Description |
|---|---|---|
| `_now_utc()` | `json_file_storage.py` | Returns `datetime.now(timezone.utc)` — used throughout for timestamp generation |
| `_parse_dt_utc(dt_str)` | `json_file_storage.py` | Parses ISO timestamps from storage into aware UTC datetimes; handles `Z` suffix, explicit offsets, and naive timestamps |
| `_now_utc()` | `chats.py` | Local copy (duplicated) of the same helper for the extracted chat module |
| `_parse_dt_utc(dt_str)` | `chats.py` | Local copy (duplicated) of the same ISO parsing helper |
| `_chat_dict_to_session(self, data)` | `chats.py` | Converts stored JSON dict → `ChatSession` dataclass (extracted from `JsonFileStorage`) |

The `chats.py` module duplicates `_now_utc` and `_parse_dt_utc` from `json_file_storage.py` to avoid importing from the parent module (circular import risk during the refactor).

## 9. Methods (by class)

### 9.1 Storage (ABC) — `base.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `create_chat_session` | abstract instance | `(self, account_name: str, agent_name: str, friendly_name: Optional[str] = None, tags: Optional[List[str]] = None) -> ChatSession` | Creates a new chat session with a generated UUID. Returns the full `ChatSession` object. |
| `get_chat_session` | abstract instance | `(self, session_id: str) -> Optional[ChatSession]` | Loads a full session (including messages) by ID. Returns `None` if not found. |
| `list_chat_sessions` | abstract instance | `(self, account_name: str, agent_name: Optional[str] = None, limit: int = 50, before: Optional[datetime] = None) -> List[ChatSession]` | Lists recent sessions for an account, optionally filtered by agent and a `before` cutoff. Sorted by recency. |
| `rename_chat_session` | abstract instance | `(self, session_id: str, friendly_name: str) -> None` | Updates the human-friendly name of a session. Backward-compatible wrapper around `update_chat_session`. |
| `update_chat_session` | abstract instance | `(self, session_id: str, *, friendly_name, tags, summary, importance_score, include_in_context, metadata) -> None` | Updates session metadata fields. All keyword args are optional — only provided fields change. |
| `append_chat_message` | abstract instance | `(self, session_id: str, message: ChatMessage) -> None` | Appends a single message to the session's message list. |
| `delete_chat_session` | abstract instance | `(self, session_id: str) -> None` | Deletes a session and all its messages. Idempotent — no error if already missing. |
| `get_user_profile` | abstract instance | `(self, account_name: str) -> Optional[UserProfile]` | Loads a user profile. Returns `None` if not found. |
| `upsert_user_profile` | abstract instance | `(self, profile: UserProfile) -> None` | Creates or updates a user profile. |
| `get_agent_profile` | abstract instance | `(self, name: str) -> Optional[AgentProfile]` | Loads an agent profile by name. Returns `None` if not found. |
| `upsert_agent_profile` | abstract instance | `(self, agent: AgentProfile) -> None` | Creates or updates an agent profile. |
| `get_context` | abstract instance | `(self, account_name: str, context_id: str) -> Optional[ContextState]` | Loads a context state (whiteboard). Returns `None` if missing. |
| `get_or_create_context` | abstract instance | `(self, account_name: str, context_id: str) -> ContextState` | Loads a context; creates and persists it with defaults if missing. Always returns a `ContextState`. |
| `save_context` | abstract instance | `(self, context: ContextState) -> None` | Persists a context state. Inserts or updates. |
| `list_context_names` | **concrete** instance | `(self, account_name: str) -> List[str]` | Lists context names for an account. Default returns `[]`. Non-abstract for backward compatibility with older `Storage` implementations. |
| `list_tasklists` | abstract instance | `(self, account_name: str) -> List[str]` | Lists persisted tasklist IDs for an account. Sorted ascending. |
| `get_tasklist` | abstract instance | `(self, account_name: str, tasklist_name: str) -> Optional[TaskList]` | Loads a tasklist. Returns `None` if missing. |
| `save_tasklist` | abstract instance | `(self, account_name: str, tasklist_name: str, tasklist: TaskList) -> None` | Persists a tasklist (accepts dict or `TaskList` model). |
| `delete_tasklist` | abstract instance | `(self, account_name: str, tasklist_name: str) -> None` | Deletes a tasklist. Idempotent — no error if missing. |
| `list_documents` | abstract instance | `(self, account_name: str, kind: Optional[str] = None, tag: Optional[str] = None, select_limit: int = 100) -> List[DocumentRef]` | Lists documents, optionally filtered by kind and/or tag. Results capped at `select_limit`. |
| `get_document` | abstract instance | `(self, document_id: str) -> Optional[DocumentRef]` | Gets a single document reference by ID. Returns `None` if missing. |
| `upsert_document` | abstract instance | `(self, doc: DocumentRef) -> None` | Creates or updates a document reference. |
| `upsert_embedding` | abstract instance | `(self, record: EmbeddingRecord) -> None` | Inserts or updates an embedding vector record. |
| `query_embeddings` | abstract instance | `(self, namespace: str, account_name: str, query_vector: List[float], top_k: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Tuple[EmbeddingRecord, float]]` | Vector similarity search. Returns `[(record, cosine_similarity), ...]` sorted by score descending. |
| `health_check` | abstract instance | `(self) -> bool` | Quick reachability check. Returns `True` if storage is accessible and writable. |

### 9.2 JsonFileStorage — `json_file_storage.py`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, storage_paths: StoragePaths)` | Injects `StoragePaths` for directory layout. Creates a `TaskListService` instance for tasklist persistence. |
| `_atomic_write` | instance (private) | `(self, path: Path, data: Dict[str, Any]) -> None` | Writes JSON atomically via `.tmp` + `os.replace()`. |
| `_atomic_write_text` | instance (private) | `(self, path: Path, text: str) -> None` | Writes text atomically (used for Markdown contexts). Same `.tmp` pattern. |
| `_load_json` | instance (private) | `(self, path: Path) -> Optional[Dict[str, Any]]` | Loads and parses a JSON file. Returns `None` if missing or corrupt (logs warning on `JSONDecodeError`, error on other exceptions). Never raises. |
| `_ensure_dir` | instance (private) | `(self, path: Path) -> None` | Creates directory tree with `parents=True, exist_ok=True`. |
| `create_chat_session` | instance | `(self, account_name, agent_name, friendly_name=None, tags=None) -> ChatSession` | Delegates to `chats.create_chat_session()`. Generates UUID, writes session JSON, updates per-account `index.json`. |
| `find_chat_sessions_by_friendly_name` | instance | `(self, account_name, agent_name, friendly_name, limit=20) -> List[ChatSession]` | Delegates to `chats.find_chat_sessions_by_friendly_name()`. Case-insensitive substring match against friendly names. **Not part of the `Storage` ABC** — implementation-specific extension. |
| `get_chat_session` | instance | `(self, session_id) -> Optional[ChatSession]` | Delegates to `chats.get_chat_session()`. Scans all account directories for the session (uses `index.json` to locate). |
| `list_chat_sessions` | instance | `(self, account_name, agent_name=None, limit=50, before=None) -> List[ChatSession]` | Delegates to `chats.list_chat_sessions()`. Reads `index.json`, filters by agent and `before` timestamp, loads each matching session. |
| `rename_chat_session` | instance | `(self, session_id, friendly_name) -> None` | Delegates to `chats.rename_chat_session()`, which calls `update_chat_session`. |
| `update_chat_session` | instance | `(self, session_id, *, friendly_name, tags, summary, importance_score, include_in_context, metadata) -> None` | Delegates to `chats.update_chat_session()`. Loads the session, checks each keyword arg for `None`, updates only changed fields, writes `updated_at`. Also updates `index.json` when `friendly_name` changes. Raises `ValueError` if session or data missing. |
| `append_chat_message` | instance | `(self, session_id, message) -> None` | Delegates to `chats.append_chat_message()`. Normalizes message timestamp to UTC-aware, appends to `messages` array, bumps `updated_at`. Raises `FileNotFoundError` if session missing. |
| `delete_chat_session` | instance | `(self, session_id) -> None` | Delegates to `chats.delete_chat_session()`. Removes session JSON and updates `index.json`. Best-effort and idempotent. |
| `_chat_dict_to_session` | instance (private) | `(self, data) -> ChatSession` | Delegates to `chats._chat_dict_to_session()`. Converts stored JSON dict → `ChatSession` dataclass (parsing messages, timestamps). |
| `get_user_profile` | instance | `(self, account_name) -> Optional[UserProfile]` | Loads `<users>/<account>.json`. Returns `None` if missing. |
| `upsert_user_profile` | instance | `(self, profile) -> None` | Writes user profile JSON atomically. |
| `save_user` | instance | `(self, account_name, profile: Dict) -> None` | **Compatibility wrapper** for older tests. Converts `{"name": ..., "preferences": ...}` dict → `UserProfile` → `upsert_user_profile`. |
| `load_user` | instance | `(self, account_name) -> Optional[Dict]` | **Compatibility wrapper** for older tests. Converts `UserProfile` → `{"name": ..., "preferences": ...}` dict. |
| `get_agent_profile` | instance | `(self, name) -> Optional[AgentProfile]` | Loads `<agents>/<name>.json`. Returns `None` if missing. |
| `upsert_agent_profile` | instance | `(self, agent) -> None` | Writes agent profile JSON atomically. |
| `get_context` | instance | `(self, account_name, context_id) -> Optional[ContextState]` | Loads context from `<contexts>/<account>/<id>.md`. Parses YAML frontmatter → `data` dict, body → `data["text"]`. `updated_at` from frontmatter `updated_at` key if present, else file mtime. Returns `None` if file missing or read error. |
| `get_or_create_context` | instance | `(self, account_name, context_id, *, default_data=None) -> ContextState` | Loads context; if missing, creates with defaults (`context_name`, `agreed=False`, `tasklist_status="draft"`, `text=""`), merges `default_data`, saves, returns. The `default_data` kwarg is an **implementation extension** not on the ABC. |
| `save_context` | instance | `(self, context) -> None` | Persists context as Markdown. All `context.data` keys except `"text"` → YAML frontmatter; `data["text"]` → Markdown body. Sets file mtime to `context.updated_at` via `os.utime`. |
| `list_context_names` | instance | `(self, account_name) -> List[str]` | Lists `.md` file stems in `<contexts>/<account>/`. Sorted ascending. Returns `[]` if directory missing. |
| `migrate_context_json_to_md` | instance | `(self) -> None` | One-time migration: scans all `<contexts>/*/` for `.json` files, converts to `.md` via `save_context`, skips if `.md` already exists. Logs errors per-file, does not abort. |
| `_tasklists_dir` | instance (private) | `(self, account_name) -> Path` | Returns `<base>/tasklists/<account>/` directory path. |
| `_tasklist_path` | instance (private) | `(self, account_name, tasklist_id) -> Path` | Resolves a safe tasklist file path via `StoragePaths.resolve_relative()`. Prevents path traversal. |
| `list_tasklists` | instance | `(self, account_name) -> List[str]` | Lists `*.json` file stems in the tasklists directory. Sorted ascending. |
| `get_tasklist` | instance | `(self, account_name, tasklist_id) -> Optional[TaskList]` | Loads via `TaskListService.load()`. Returns `None` on `FileNotFoundError`. |
| `save_tasklist` | instance | `(self, account_name, tasklist_name, tasklist) -> None` | Validates name (alnum/dash/underscore only, raises `ValueError`). Converts dict → `TaskList` if needed via `TaskList.from_dict()`. Saves via `TaskListService.save()`. |
| `delete_tasklist` | instance | `(self, account_name, tasklist_id) -> None` | Unlinks the tasklist file. Catches and logs errors — idempotent. |
| `list_documents` | instance | `(self, account_name, kind=None, tag=None, select_limit=100) -> List[DocumentRef]` | Scans `<documents>/<account>/*.json`. Filters by `kind` (exact match) and `tag` (membership check). Caps results at `select_limit`. |
| `get_document` | instance | `(self, document_id) -> Optional[DocumentRef]` | Scans all account directories for `<document_id>.json`. Returns `None` if not found. |
| `upsert_document` | instance | `(self, doc) -> None` | Writes document JSON atomically to `<documents>/<account>/<id>.json`. |
| `_doc_dict_to_ref` | instance (private) | `(self, data) -> DocumentRef` | Converts stored JSON dict → `DocumentRef` dataclass. |
| `search_documents_poor_man` | instance | `(self, account_name, query, kind=None, tag=None, limit=10) -> List[DocumentRef]` | Keyword-based document search. Extracts keywords from query and each doc's title/tags/metadata via `Keywords`, scores by Jaccard-like set intersection, sorts descending. **Not part of the `Storage` ABC** — implementation-specific extension. |
| `upsert_embedding` | instance | `(self, record) -> None` | Writes embedding JSON atomically to `<embeddings>/<account>/<namespace>/<id>.json`. Normalizes `created_at` to UTC-aware. |
| `query_embeddings` | instance | `(self, namespace, account_name, query_vector, top_k=10, filter=None) -> List[Tuple[EmbeddingRecord, float]]` | Linear scan of all embedding JSON files in the namespace directory. Computes cosine similarity, optionally filters by `source_type`, sorts descending, returns top_k. |
| `_cosine_similarity` | instance (private) | `(self, vec1, vec2) -> float` | Standard cosine similarity: dot product / (mag1 * mag2). Returns `0.0` if either vector has zero magnitude. |
| `health_check` | instance | `(self) -> bool` | Returns `True` if `storage_paths.base` exists and is writable. |

### 9.3 Dataclass models — `models.py`

All seven classes are plain dataclasses with no instance methods beyond `__post_init__` for timestamp defaults.

| Class | Fields with defaults | `__post_init__` behavior |
|---|---|---|
| `ChatMessage` | `utc_timestamp=None`, `metadata={}` | Sets `utc_timestamp` to `datetime.now(timezone.utc)` if `None` |
| `ChatSession` | `messages=[]`, `tags=[]`, `summary=None`, `importance_score=0.5`, `include_in_context=True`, `metadata={}` | None |
| `UserProfile` | `full_name=None`, `preferences={}`, `active=True` | None |
| `AgentProfile` | `config={}` | None |
| `ContextState` | (none) | Sets `updated_at` to `datetime.now(timezone.utc)` if `None` |
| `DocumentRef` | `title=None`, `tags=[]`, `metadata={}` | None |
| `EmbeddingRecord` | `source_metadata={}`, `created_at=field(default_factory=lambda: datetime.now(timezone.utc))` | None |

### 9.4 Chat helper functions — `chats.py`

| Function | Signature | Description |
|---|---|---|
| `create_chat_session` | `(self, account_name, agent_name, friendly_name=None, tags=None) -> ChatSession` | Generates UUID, builds `ChatSession`, writes session JSON + updates index. |
| `get_chat_session` | `(self, session_id) -> Optional[ChatSession]` | Scans account dirs for session, loads JSON, converts to `ChatSession`. |
| `list_chat_sessions` | `(self, account_name, agent_name=None, limit=50, before=None) -> List[ChatSession]` | Reads index, filters, loads sessions, sorts by `updated_at` desc. |
| `find_chat_sessions_by_friendly_name` | `(self, account_name, agent_name, friendly_name, limit=20) -> List[ChatSession]` | Case-insensitive substring match on friendly names. |
| `rename_chat_session` | `(self, session_id, friendly_name) -> None` | Delegates to `self.update_chat_session()`. |
| `update_chat_session` | `(self, session_id, *, friendly_name, tags, summary, importance_score, include_in_context, metadata) -> None` | Loads session, patches only provided fields, writes JSON + updates index for name changes. |
| `append_chat_message` | `(self, session_id, message) -> None` | Loads session, appends message dict, writes JSON with updated timestamp. |
| `delete_chat_session` | `(self, session_id) -> None` | Removes session JSON + updates index. Best-effort, idempotent. |
| `_chat_dict_to_session` | `(self, data) -> ChatSession` | Converts stored JSON dict to `ChatSession` dataclass. |

## 10. Usage Examples

### Example 1: Creating a session and appending a message

```python
from src.storage import JsonFileStorage, ChatMessage, ChatSession
from src.storage_paths import StoragePaths

paths = StoragePaths(base=Path("./data"))
storage = JsonFileStorage(storage_paths=paths)

# Create a new chat session
session = storage.create_chat_session("junwin", "lucy", "Bug triage")
print(f"Created: {session.id} — {session.friendly_name}")

# Append a message
msg = ChatMessage(role="user", content="What's the status of issue #42?")
storage.append_chat_message(session.id, msg)
```

### Example 2: Loading and updating a context (whiteboard)

```python
# Load or create a context
ctx = storage.get_or_create_context("junwin", "lucyproject")

# Update and save
ctx.data["agreed"] = True
ctx.data["text"] = "# Current Status\n\nAll green."
ctx.data["tasklist_status"] = "active"
storage.save_context(ctx)
```

### Example 3: Poor-man's document search

```python
# Keyword-based document search (no embeddings needed)
results = storage.search_documents_poor_man(
    "junwin", "retirement planning", kind="obsidian", limit=5
)
for doc in results:
    print(f"{doc.title} — {doc.path}")
```

## 11. Edge Cases & Gotchas

1. **Index-first scan for sessions.** `get_chat_session` scans all account directories to find a session — it does not assume where the session lives. This is O(accounts) per lookup but avoids a global index.

2. **`get_or_create_context` has an extra `default_data` parameter.** The ABC signature does not include `default_data` — it's an implementation extension on `JsonFileStorage`. Code typed against `Storage` cannot pass it.

3. **Context `updated_at` from mtime, not stored in file.** `save_context` sets `os.utime` on the file to preserve the timestamp. `get_context` reads mtime as a fallback if frontmatter lacks `updated_at`. This means copying context files can lose the intended timestamp.

4. **Duplicate `_now_utc` / `_parse_dt_utc` in `chats.py`.** These are intentionally duplicated to avoid circular imports during the ongoing extraction refactor. If you change one, change the other.

5. **`find_chat_sessions_by_friendly_name` and `search_documents_poor_man` are not on the ABC.** They exist only on `JsonFileStorage`. Code typed against `Storage` cannot call them without a cast or `hasattr` guard.

6. **Embedding query is a linear scan.** `query_embeddings` loads and scores every embedding file in the namespace directory. For large collections this will be slow — no ANN index.

7. **Migration `migrate_context_json_to_md` is best-effort.** It skips any context with an existing `.md` file and logs but swallows per-file errors. It never deletes the original `.json` files — the caller must clean up afterward.

8. **`save_user` / `load_user` are compatibility wrappers.** They use dict shapes (`{"name": ..., "preferences": ...}`) rather than `UserProfile` dataclasses. New code should use `upsert_user_profile` / `get_user_profile`.

9. **`_load_json` returns `None` on any error.** Callers must handle `None` — no exception propagation for corrupt files. This is intentional fail-soft behavior.

10. **Tasklist name validation.** `save_tasklist` enforces `^[A-Za-z0-9_-]+$` on names and raises `ValueError` otherwise. The `_tasklist_path` also routes through `StoragePaths.resolve_relative` to prevent path traversal.

11. **`delete_chat_session` catches all exceptions from file operations.** It logs errors but never re-raises. The index update is also wrapped in try/except.

12. **Atomic writes are not transactional across multiple files.** `create_chat_session` writes both the session JSON and the index JSON — if the process crashes between them, the index will be stale or the session orphaned. There is no WAL or journal.

13. **Context Markdown: no frontmatter → whole file is body.** If a `.md` file has no YAML frontmatter delimiters (`---`), the entire content becomes `data["text"]` with an empty frontmatter dict.

14. **`search_documents_poor_man` uses set intersection, not term frequency.** The score is `len(set(doc_keywords) & set(query_keywords))` — a Jaccard-like overlap, not weighted by frequency. Short documents may be disadvantaged.

15. **The `chats.py` functions receive `self` as first argument but are not methods.** They're plain functions that duck-type the `JsonFileStorage` interface (`.storage_paths`, `._load_json`, `._atomic_write`, `._ensure_dir`). This works because `JsonFileStorage` delegates to them with `self`.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/container_config.py` | `Storage` (ABC for DI binding), `JsonFileStorage` (concrete binding) |
| `src/message_endpoints/ask_request_handler.py` | `Storage` (ABC), `ChatMessage` (appending messages to session) |
| `src/message_processors/automation_processor.py` | `Storage` (ABC), `ChatMessage` (saving tool-call events) |
| `src/message_processors/task_running_processor.py` | `Storage` (ABC — passed through for delegation) |
| `src/prompt_builders/prompt_builder.py` | `Storage` (ABC — loading sessions/contexts for prompt assembly) |
| `src/handlers/chat2_handler.py` | `JsonFileStorage` (lazy import — session CRUD for chat2 API) |
| `src/handlers/curate_chat_handler.py` | `JsonFileStorage` (lazy import — loading sessions for curation) |
| `src/handlers/tasklists_manage_handler.py` | `JsonFileStorage` (tasklist CRUD) |
| `src/chat2/adapters/jfs_adapter.py` | `JsonFileStorage` (chat2 session adapter) |
| `src/utils/obsidian_importer.py` | `Storage` (ABC), `DocumentRef` (upserting documents) |
| `src/utils/document_context.py` | `Storage` (ABC — loading document context snippets) |
| `src/obsidian_index_cli.py` | `JsonFileStorage` (CLI tool for document indexing) |
| `src/http_endpoints/prompt_builder_debug_endpoints.py` | `Storage` (ABC — debug endpoint) |
| `tests/conftest.py` | `ChatSession` (test fixture factory) |
| `tests/test_storage_chats.py` | `ChatMessage`, `ChatSession` (chat CRUD tests) |
| `tests/test_storage_contexts.py` | `ContextState` (context CRUD tests) |
| `tests/test_storage_profiles.py` | `UserProfile`, `AgentProfile` (profile CRUD tests) |
| `tests/test_storage_embeddings.py` | Embedding models (embedding CRUD tests) |
| `tests/test_tasklists_storage.py` | Tasklist storage tests |
| `tests/test_json_filestorage_users.py` | User profile storage tests |
| `tests/test_json_filestorage_chat_method_guardrails.py` | Chat method guardrail tests |
