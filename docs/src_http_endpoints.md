---
tags:
  - src_http_endpoints
  - lucyproject
  - Chat2Store
  - AgentManager
  - PromptBuilder
  - Storage
  - ConfigManager
  - ChatEvent
  - ChatSessionMeta
  - TaskList
  - get_agents_impl
  - list_context_names_impl
  - list_tasklists_impl
  - get_tasklist_impl
  - put_tasklist_impl
  - delete_tasklist_impl
  - build_prompt_impl
  - prompt_builder_debug_impl
  - search_documents_impl
  - post_chat_impl
  - get_chats_impl
  - get_chat_impl
  - post_chat_message_impl
  - delete_chat_impl
  - update_chat_impl
  - _chat2_session_to_response
---

## 1. Summary

`src.http_endpoints` is a namespace package containing the implementation functions for every HTTP route in the Lucy API. Each file is a self-contained set of pure-Python functions that:

- Receive dependency-injected collaborators (storage, agent manager, config, chat2 store, container) directly as parameters.
- Validate inputs, call the relevant service layer, and return a `(body, status_code)` tuple.
- Contain **no Flask code whatsoever** — the Flask routes (`app.py`) are the sole consumer, calling these `_impl` functions with the resolved dependencies.

The module is the thin translation layer between HTTP semantics (request parsing, status codes, JSON) and the core domain logic. It exists so that route handlers in `app.py` stay minimal (parse JSON, call impl, jsonify result) and the implementations are testable without a Flask test client — just call them with mocks.

## 2. Architecture & Design

**Pattern: "Impl Function" / procedural endpoint**

Every endpoint is a standalone module-level function named `*_impl`. There are no classes, no base classes, no inheritance, no ABCs. The design is deliberately flat and procedural:

- Each function accepts typed dependencies as parameters (e.g. `storage: Storage`, `chat2_store: Chat2Store`, `agent_manager: AgentManager`).
- Dependency injection (via `container_config.py`'s `injector`) wires the concrete implementations; the endpoint functions don't know or care about how those dependencies are constructed.
- Functions always return `Tuple[Any, int]` — response body (dict or list) and HTTP status code.
- Error handling follows a consistent pattern: validate inputs → 400, try/except with logging → 500, `ValueError` → 400.

**No `__init__.py`**

The module is a namespace package (no `__init__.py`). Each file is imported directly by `app.py` with `from src.http_endpoints.<file> import <func>`. This keeps the import graph flat and makes each file independently testable.

**File-to-domain mapping**

| File | Domain | Dependencies |
|---|---|---|
| `agents_endpoints.py` | Agent listing + context names + tasklist CRUD | `agent_manager`, `storage` |
| `chats_endpoints.py` | Chat v2 session CRUD + messages | `chat2_store`, `agent_manager` |
| `context_endpoints.py` | Context name listing | `storage` |
| `documents_endpoints.py` | Document search (poor man's) | `storage` |
| `prompt_builder_endpoints.py` | Prompt construction | `agent_manager`, `storage`, `container`, `config` |
| `prompt_builder_debug_endpoints.py` | Prompt builder debug/analysis | `storage`, `config` |
| `prompt_and_docs_endpoints.py` | (unused) duplicates of `build_prompt_impl` + `search_documents_impl` | `agent_manager`, `storage`, `container`, `config` |
| `tasklist_endpoints.py` | Tasklist CRUD | `storage` |

**Duplicate implementations**

Two functions exist in two places and are identical:

- `list_context_names_impl` appears in both `agents_endpoints.py` (line 13) and `context_endpoints.py` (line 5). `app.py` imports from `context_endpoints`.
- `search_documents_impl` appears in both `documents_endpoints.py` and `prompt_and_docs_endpoints.py`. `app.py` imports from `documents_endpoints`.
- `build_prompt_impl` appears in both `prompt_builder_endpoints.py` and `prompt_and_docs_endpoints.py`. `app.py` imports from `prompt_builder_endpoints`.

The `prompt_and_docs_endpoints.py` file is effectively dead code — nothing imports from it, and its functions are superseded by `prompt_builder_endpoints.py` and `documents_endpoints.py`.

## 3. Key Classes

None. Every export is a plain function. The module is entirely class-free.

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `agents_endpoints.py` | Agent listing, context name listing, tasklist CRUD | `get_agents_impl`, `list_context_names_impl` (dup), `list_tasklists_impl`, `get_tasklist_impl`, `put_tasklist_impl`, `delete_tasklist_impl` |
| `chats_endpoints.py` | Chat v2 session CRUD, message posting, response formatting | `post_chat_impl`, `get_chats_impl`, `get_chat_impl`, `post_chat_message_impl`, `delete_chat_impl`, `update_chat_impl`, `_chat2_session_to_response` |
| `context_endpoints.py` | Context name listing | `list_context_names_impl` |
| `documents_endpoints.py` | Document search (poor man's) | `search_documents_impl` |
| `prompt_builder_endpoints.py` | Prompt construction | `build_prompt_impl` |
| `prompt_builder_debug_endpoints.py` | Debug/analysis of prompt builder doc loading | `prompt_builder_debug_impl` |
| `prompt_and_docs_endpoints.py` | (unused) duplicates of `build_prompt_impl` and `search_documents_impl` | `build_prompt_impl`, `search_documents_impl` |
| `tasklist_endpoints.py` | Tasklist CRUD | `list_tasklists_impl`, `get_tasklist_impl`, `put_tasklist_impl`, `delete_tasklist_impl` |

No `__init__.py` — namespace package.

## 5. Dependencies

### Standard library

| Module | Used In |
|---|---|
| `logging` | All files except `chats_endpoints.py` (inherits from `__future__` annotation) |
| `typing` | All files: `Any`, `Dict`, `Tuple`, `List`, `Optional` |
| `__future__` | `chats_endpoints.py`, `prompt_builder_debug_endpoints.py` (for `annotations` import) |

### Third-party packages

None directly. The endpoint functions receive dependency-injected objects (Pydantic models, etc.) but don't import any third-party packages themselves, with one exception: `prompt_builder_debug_endpoints.py` imports `src.keywords.keywords.Keywords` which may transitively pull in `yake` or similar, but the endpoint file itself only has direct internal imports.

### Internal modules

| Import | Used In | Purpose |
|---|---|---|
| `src.agent.AgentManager` | `chats_endpoints.py`, `prompt_builder_debug_endpoints.py`, `prompt_builder_endpoints.py`, `prompt_and_docs_endpoints.py` | Agent validation + resolution |
| `src.chat2.facade.Chat2Store` | `chats_endpoints.py` | Chat session/event persistence |
| `src.chat2.models.ChatEvent` | `chats_endpoints.py` | Constructing events for message posting |
| `src.config_manager.ConfigManager` | `prompt_builder_debug_endpoints.py` | Type hint |
| `src.keywords.keywords.Keywords` | `prompt_builder_debug_endpoints.py` | Keyword extraction |
| `src.prompt_builders.prompt_builder.PromptBuilder` | `prompt_builder_endpoints.py`, `prompt_and_docs_endpoints.py` | Prompt construction |
| `src.storage.base.Storage` | `prompt_builder_debug_endpoints.py` | Type hint |
| `src.utils.document_context.get_document_context` | `prompt_builder_debug_endpoints.py` | Document context loading |
| `src.utils.text_snippet_loader.load_text_snippet` | `prompt_builder_debug_endpoints.py` | Snippet loading for debug info |

### Optional dependencies

None.

## 6. Configuration / Settings

None. The endpoint functions do not read any config keys, environment variables, or file paths. All configuration is handled by the dependency-injected objects (`config`, `agent_manager`, `storage`) that are passed in by `app.py`.

## 7. Exceptions

None. No custom exception classes are defined in this module. All error handling uses standard exception catching (`Exception`, `ValueError`) and maps them to HTTP status codes in the return tuple.

## 8. Module-Level Constants

None. No constants, sentinels, or default values are defined at module level in any of the 8 files.

## 9. Methods (by class)

No classes exist. All exports are standalone functions. Below, each file's functions are documented.

---

### agents_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `get_agents_impl` | `(agent_manager) -> Tuple[Any, int]` | Returns list of available agents as dicts via `agent_manager.get_available_agents()`. Wraps in try/except → 500 on failure. Returns `([a.to_dict() for a in agents], 200)`. |
| `list_context_names_impl` | `(storage, account_name: str) -> Tuple[Any, int]` | Validates `account_name` is non-empty (400 if missing). Calls `storage.list_context_names(account_name)`. Returns `(list_of_names, 200)` or `({"error": "An error occurred"}, 500)`. **Duplicate**: also exists in `context_endpoints.py`. |
| `list_tasklists_impl` | `(storage, account_name: str) -> Tuple[Any, int]` | Validates `account_name` is non-empty. Calls `storage.list_tasklists(account_name)`. Returns `(list_of_ids, 200)` or `({"error": "An error occurred"}, 500)`. |
| `get_tasklist_impl` | `(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]` | Validates `account_name`. Calls `storage.get_tasklist(account_name, tasklist_name)`. Returns 404 if `None`, `(tl.to_dict(), 200)` if found, 400 for `ValueError`, 500 otherwise. |
| `put_tasklist_impl` | `(storage, account_name: str, tasklist_name: str, payload: Dict) -> Tuple[Any, int]` | Validates `account_name` and non-None payload (400). Calls `storage.save_tasklist(...)`. Returns `({"ok": True}, 200)`. |
| `delete_tasklist_impl` | `(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]` | Validates `account_name`. Calls `storage.delete_tasklist(...)`. Returns `({"ok": True}, 200)` or 500 on exception. No 404 check — silently succeeds if tasklist doesn't exist. |

---

### chats_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `_chat2_session_to_response` | `(meta, events: Optional[List[ChatEvent]] = None) -> Dict[str, Any]` | Private helper. Converts a `ChatSessionMeta` + optional `ChatEvent` list into the standard response dict shape. Hardcodes `summary=None`, `importance_score=0.5`, `include_in_context=True` — these fields are legacy/v1 artifacts preserved for API compatibility. Events are mapped to `{"role", "content", "utc_timestamp", "metadata"}` dicts. |
| `post_chat_impl` | `(chat2_store: Chat2Store, agent_manager: AgentManager, payload: Dict[str, Any]) -> tuple[Dict[str, Any], int]` | Creates a new chat session. Validates `agentName` and `accountName` are present and that the agent is valid (400 otherwise). Calls `chat2_store.create_session(...)`. Returns full session dict with empty `messages` list. |
| `get_chats_impl` | `(chat2_store: Chat2Store, agent_manager: AgentManager, agent_name: str, account_name: str, limit: int) -> tuple[Any, int]` | Lists sessions. Requires `account_name` (400 if missing). If `agentName` provided, validates it. Calls `chat2_store.list_sessions(...)`. Returns list of session summary dicts (no messages). |
| `get_chat_impl` | `(chat2_store: Chat2Store, session_id: str) -> tuple[Dict[str, Any], int]` | Gets a single session with all events. Returns 404 if session not found. Events are streamed via `chat2_store.stream_events()` and materialized into a list. |
| `post_chat_message_impl` | `(chat2_store: Chat2Store, session_id: str, data: Dict[str, Any]) -> tuple[Dict[str, Any], int]` | Adds a message event to a session. Validates `role` and `content` are present (400). Checks session exists (404). Constructs a `ChatEvent` with `actor=role`, `kind` derived from role (`"user_message"` or `"assistant_message"`). Calls `chat2_store.add_event(...)`. Returns `{"status": "ok"}`. |
| `delete_chat_impl` | `(chat2_store: Chat2Store, session_id: str) -> tuple[Dict[str, Any], int]` | Deletes a session. Returns 404 if not found. Wraps `chat2_store.delete_session` in try/except → 500. Returns `{"ok": True}`. |
| `update_chat_impl` | `(chat2_store: Chat2Store, session_id: str, payload: Optional[Dict[str, Any]]) -> tuple[Dict[str, Any], int]` | Patches a session. Only fields `friendlyName`, `tags`, and `metadata` are patchable — other fields in the payload are silently ignored. Returns 404 if session not found. Calls `chat2_store.update_session(...)` with only the non-None patch fields. |

---

### context_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `list_context_names_impl` | `(storage, account_name: str) -> Tuple[Any, int]` | Identical to the function in `agents_endpoints.py`. Validates `account_name`, calls `storage.list_context_names(...)`, returns `(list, 200)` or `({"error": "An error occurred"}, 500)`. This is the version actually imported by `app.py`. |

---

### documents_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `search_documents_impl` | `(storage, data: dict) -> Tuple[...]` | Performs a poor man's document search. Extracts `account_name`, `query` (from `question` or `q`), optional `kind`, `tag`, `limit` (default 10). Validates non-empty `account_name` and `query` (400). Checks `storage` has `search_documents_poor_man` method (501 if not). Returns list of document dicts with fields: `id`, `account_name`, `path`, `kind`, `title`, `tags`, `metadata`. |

---

### prompt_builder_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `build_prompt_impl` | `(agent_manager, storage, container, config, payload: dict) -> Tuple[Any, int]` | Builds a prompt for the given query/agent/account. Extracts: `query`, `agentName`, `accountName`, `selectType`/`contextType`, `conversationId`, `contextName`/`context_name`, `extraSystemMessages`, `maxPromptChars` (default 6000). Validates required fields (400). Resolves `PromptBuilder` from DI container (fallback: manual construction). Calls `prompt_builder.build_prompt(...)`. Returns the built prompt dict. |

---

### prompt_builder_debug_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `prompt_builder_debug_impl` | `(storage: Storage, config: ConfigManager, payload: dict) -> Tuple[Any, int]` | Debug endpoint. Executes a 4-stage pipeline: (1) extract keywords from query via `Keywords.extract_keywords(top_n=20)`, (2) load context's `data.tag` if available, (3) score all candidate documents (up to 100) by keyword overlap against title+tags+metadata, (4) run `get_document_context` and report snippet info. Returns detailed JSON trace: keywords, scored docs (top 20), selected docs with snippet lengths and truncation status, and a summary object. Read-only — no state changes. |

---

### prompt_and_docs_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `build_prompt_impl` | `(agent_manager, storage, container, config, payload: dict) -> Tuple[Any, int]` | **Dead code.** Identical to the version in `prompt_builder_endpoints.py`. Not imported by `app.py`. |
| `search_documents_impl` | `(storage, data: dict) -> Tuple[...]` | **Dead code.** Identical to the version in `documents_endpoints.py`. Not imported by `app.py`. |

---

### tasklist_endpoints.py

| Function | Signature | Description |
|---|---|---|
| `list_tasklists_impl` | `(storage, account_name: str) -> Tuple[Any, int]` | Identical to function in `agents_endpoints.py`. |
| `get_tasklist_impl` | `(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]` | Identical to function in `agents_endpoints.py`. |
| `put_tasklist_impl` | `(storage, account_name: str, tasklist_name: str, payload: Dict) -> Tuple[Any, int]` | Identical to function in `agents_endpoints.py`. |
| `delete_tasklist_impl` | `(storage, account_name: str, tasklist_name: str) -> Tuple[Any, int]` | Identical to function in `agents_endpoints.py`. |

## 10. Usage Examples

### Building a prompt (e.g., from a Flask route)

```python
from src.http_endpoints.prompt_builder_endpoints import build_prompt_impl

payload = {
    "query": "What is the weather?",
    "agentName": "lucy",
    "accountName": "junwin",
    "contextType": "hybrid",
    "contextName": "lucyproject",
    "maxPromptChars": 6000,
}
body, status = build_prompt_impl(agent_manager, storage, container, config, payload)
# body is the built prompt dict; status is 200
```

### Chat session CRUD

```python
from src.http_endpoints.chats_endpoints import post_chat_impl, get_chat_impl

# Create a session
body, status = post_chat_impl(chat2_store, agent_manager, {
    "agentName": "lucy",
    "accountName": "junwin",
    "friendlyName": "My Session",
})
session_id = body["id"]

# Get session with all events
body, status = get_chat_impl(chat2_store, session_id)
# body["messages"] contains the full event history
```

### Debug document loading

```python
from src.http_endpoints.prompt_builder_debug_endpoints import prompt_builder_debug_impl

payload = {
    "query": "How does the chat storage work?",
    "accountName": "junwin",
    "contextName": "lucyproject",
}
body, status = prompt_builder_debug_impl(storage, config, payload)
# body["all_scored_docs"] — top 20 candidate docs with scores and matched terms
# body["docs_selected_by_get_document_context"] — which docs were actually selected
# body["summary"] — aggregate stats
```

## 11. Edge Cases & Gotchas

### Duplicate / dead code

1. **`prompt_and_docs_endpoints.py` is dead code.** Both functions are identical copies of functions in `prompt_builder_endpoints.py` and `documents_endpoints.py`. Nothing imports from this file. It should be deleted to prevent confusion.
2. **`tasklist_endpoints.py` duplicates `agents_endpoints.py`.** The four tasklist CRUD functions exist in both files. `app.py` imports from `tasklist_endpoints.py`. The copies in `agents_endpoints.py` are dead code for those four functions. The `list_context_names_impl` in `agents_endpoints.py` is also dead — `app.py` imports it from `context_endpoints.py`.

### Error swallowing

3. **No 404 for `delete_tasklist_impl`.** Unlike `get_tasklist_impl` (which returns 404), `delete_tasklist_impl` has no existence check — it calls `storage.delete_tasklist` and returns `{"ok": True}` even if nothing was deleted. The storage layer likely handles this silently.
4. **Generic 500 messages.** Most `except Exception` blocks return `{"error": "An error occurred"}` without exposing the actual error string to the client. The detail is logged but not returned. This is intentional (security) but makes debugging opaque for API consumers.

### Chat v2 response compatibility

5. **Hardcoded legacy fields.** `_chat2_session_to_response` and `post_chat_impl` hardcode `"summary": None`, `"importance_score": 0.5`, `"include_in_context": True`. These are v1 artifacts preserved for backwards compatibility with existing clients. They are never populated from real data.
6. **`metadata` field is type-ambiguous.** `Chat2Store.update_session` accepts `**kwargs` but there's no allowlist — the endpoint only patches `friendly_name`, `tags`, and `metadata`. Any other fields in the payload are silently dropped.
7. **Event type inference is crude.** `post_chat_message_impl` sets `kind` to `"user_message"` if `role == "user"`, else `"assistant_message"`. This doesn't handle system messages, tool calls, or any other role/kind.

### Prompt builder quirks

8. **Fallback to manual construction.** `build_prompt_impl` tries `container.get(PromptBuilder)` but catches all exceptions and falls back to manual construction. This masks DI configuration errors and could cause subtle behavior differences if the container-provided `PromptBuilder` has different dependencies than the manual one.
9. **`extraSystemMessages` default is `["my system Message"]`.** If the payload omits this field, a hardcoded placeholder message is used. This is almost certainly a development artifact that should be removed.

### Debug endpoint

10. **Document scoring is keyword-overlap based, not actual poor-man's search.** The debug endpoint reimplements scoring (keyword overlap of title+tags+metadata) independently of `storage.search_documents_poor_man`. These could yield different results. The endpoint then calls `get_document_context` which uses the actual `search_documents_poor_man` — so the "all_scored_docs" in the debug output and the actual selection may differ.
11. **The `config` parameter is unused.** `prompt_builder_debug_impl` accepts `config: ConfigManager` but never reads from it.

### Thread safety

12. **All functions are stateless.** Since every dependency is passed in as a parameter and there are no module-level mutable globals, the module is inherently thread-safe. Thread safety depends entirely on the injected dependencies.

### Validation patterns

13. **`account_name` is lowercased inconsistently.** `chats_endpoints.py` lowercases `agentName` and `accountName` before processing. Other files (e.g., `context_endpoints.py`, `documents_endpoints.py`) do not lowercase. This means `ContextNames` lookups are case-sensitive while chat lookups are case-insensitive.
14. **No `agent_name` validation on message posting.** `post_chat_message_impl` only checks `role` and `content` — it doesn't validate that the role is a known value.

## 12. Consumers

| Consumer | What It Uses |
|---|---|
| `app.py` | All 7 active files — imports `get_agents_impl`, `list_context_names_impl` (from `context_endpoints`), 4 tasklist impls (from `tasklist_endpoints`), `build_prompt_impl` (from `prompt_builder_endpoints`), `prompt_builder_debug_impl`, `search_documents_impl` (from `documents_endpoints`), 6 chat impls + `_chat2_session_to_response` (from `chats_endpoints`) |
| `tests/test_chats_endpoints.py` | Imports `post_chat_impl`, `get_chats_impl`, `get_chat_impl`, `post_chat_message_impl`, `delete_chat_impl`, `update_chat_impl` from `chats_endpoints` |
