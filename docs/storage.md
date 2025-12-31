# Storage and conversations

This document describes how storage works in Lucy, with a focus on how chat
conversations are created, identified, and named.

## Storage implementation

Lucy uses a `Storage` interface with a JSON-backed implementation:

- `src/storage/base.py` – abstract `Storage` interface.
- `src/storage/json_file_storage.py` – concrete `JsonFileStorage`.
- `src/storage/models.py` – dataclasses for stored entities.

`JsonFileStorage` persists data under a configurable base directory, with
subdirectories for different entity types:

- `chats/<account_name>/...` – chat sessions and per-account chat index.
- `users/<account_name>.json` – user profiles.
- `agents/<agent_name>.json` – agent profiles.
- `contexts/<account_name>/<context_id>.json` – whiteboard/context state.
- `documents/<account_name>/<document_id>.json` – document metadata.
- `embeddings/<account_name>/<namespace>/<id>.json` – vector embeddings.

The DI container wires `JsonFileStorage` into the rest of the system so that
message processors, handlers, and endpoints can depend only on the `Storage`
interface.

## Chat sessions and messages

### Data model

Defined in `src/storage/models.py`:

- `ChatMessage`
  - `role`: `"user"`, `"assistant"`, `"system"`, etc.
  - `content`: message text.
  - `utc_timestamp`: optional `datetime`; default is `datetime.utcnow()`.
  - `metadata`: free-form dict for extra info.

- `ChatSession`
  - `id`: internal GUID (string) – **canonical conversation id**.
  - `account_name`: e.g. `"junwin"`.
  - `agent_name`: e.g. `"lucy"`.
  - `friendly_name`: optional human label, e.g. `"CLI – 2025-12-28"`.
  - `created_at`, `updated_at`: `datetime` in UTC.
  - `messages`: list of `ChatMessage`.
  - `tags`: list of strings.
  - `summary`: optional short summary.
  - `importance_score`: float, used for ranking/pruning.
  - `include_in_context`: whether this chat is eligible for prompts.
  - `metadata`: free-form dict for extra info.

### On-disk layout

For each account, chat sessions live under `chats/<account_name>/`:

- `chats/<account_name>/<session_id>.json` – full session, including messages.
- `chats/<account_name>/index.json` – per-account index of sessions:

  ```jsonc
  {
    "<session_id>": {
      "friendly_name": "CLI – 2025-12-28",
      "agent_name": "lucy",
      "account_name": "junwin",
      "updated_at": "2025-12-28T13:26:08.401234+00:00",
      "include_in_context": true
    },
    "...": { "...": "..." }
  }
  ```

### Creating a chat session

`JsonFileStorage.create_chat_session` is the only place that creates new chat
sessions on disk:

```python
session = storage.create_chat_session(
    account_name=account_name,
    agent_name=agent_name,
    friendly_name=friendly_name,  # optional human label
    tags=tags,
)
```

Behavior:

- Generates a new UUID for `session.id`.
- Sets `created_at` and `updated_at` to the current UTC time.
- Uses the provided `friendly_name` if given; otherwise defaults to
  `"Chat <first 8 chars of id>"`.
- Writes `chats/<account_name>/<session_id>.json` with an empty `messages` list.
- Updates `chats/<account_name>/index.json` with a summary entry.

The returned `session.id` is the **canonical conversation id** that must be
used for all subsequent operations on that chat.

### Looking up and listing sessions

- `get_chat_session(session_id: str) -> Optional[ChatSession]`
  - Searches all `chats/<account_name>/` directories for a file named
    `<session_id>.json`.
  - Returns a `ChatSession` or `None`.

- `list_chat_sessions(account_name: str, agent_name: Optional[str], ...)`
  - Lists sessions for a given account (optionally filtered by agent).
  - Sorts by `updated_at` (most recent first).

- `find_chat_sessions_by_friendly_name(account_name, agent_name, friendly_name)`
  - Convenience helper that filters `list_chat_sessions` by `friendly_name`.

### Updating and deleting sessions

- `update_chat_session(session_id, friendly_name=..., tags=..., ...)`
  - Loads the session, applies changes, updates `updated_at`, and rewrites the
    JSON file.
  - Keeps `index.json` in sync when `friendly_name` changes.

- `rename_chat_session(session_id, friendly_name)`
  - Thin wrapper around `update_chat_session`.

- `delete_chat_session(session_id)`
  - Locates the session to determine `account_name`.
  - Deletes `chats/<account_name>/<session_id>.json` if present.
  - Removes the entry from `index.json`.

### Appending messages

`append_chat_message(session_id: str, message: ChatMessage)`:

- Uses `get_chat_session(session_id)` to locate the session.
- Loads `chats/<account_name>/<session_id>.json`.
- Normalizes `message.utc_timestamp` to an aware UTC `datetime`.
- Appends a JSON representation of the message to the `messages` list.
- Updates `updated_at` to the current UTC time.
- Writes the file back atomically.

If the session or JSON file cannot be found, it raises `FileNotFoundError`.

## Conversation ids vs friendly names

There are two distinct identifiers for a conversation:

1. **Conversation id** – `ChatSession.id`
   - Generated by storage (UUID).
   - Used as the primary key for all storage operations.
   - Exposed to clients as `conversation_id`.

2. **Friendly name** – `ChatSession.friendly_name`
   - Optional human-readable label.
   - Can be provided by the client when opening a session.
   - Stored in the session JSON and in `index.json`.
   - Can be changed later via `update_chat_session` / `rename_chat_session`.

Clients should treat `conversation_id` as the opaque, canonical identifier and
use `friendly_name` purely for display.

## Dependencies

- `JsonFileStorage` is used by:
  - Message processors (e.g., `FunctionCallingProcessor`) to read/write chats.
  - Request handlers (e.g., `/ask`) to create and resolve sessions.
  - Other components that manage users, agents, contexts, documents, and embeddings.

This separation keeps HTTP concerns (payload shape, session opening rules) out
of the storage layer, which remains a generic persistence mechanism.
