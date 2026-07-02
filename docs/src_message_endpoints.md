---
tags:
  - src_message_endpoints
  - lucyproject
  - AskRequestHandler
  - ToolHandlerError
  - ChatMessage
---

## 1. Summary

`src/message_endpoints` is the HTTP-request-handler layer for the `/ask` endpoint. It contains a single class, `AskRequestHandler`, which is the canonical entry point for all chat requests — both from the Flask `app.py` route and from the `main.py` CLI REPL.

Its responsibilities:
- Validates the incoming payload (required fields, agent existence).
- Resolves or creates a chat session via `Storage` and optionally `Chat2Store`.
- Ensures context existence (`get_or_create_context`) for durable project state.
- Delegates actual message processing to a `ProcessorFactory`-resolved message processor.
- Provides a hook (`_maybe_autorun_tasklist`) for auto-executing delegate_tasks tasklists, though this path is currently non-functional (see Edge Cases).
- Returns a unified `(status_code, response_dict)` tuple.

The handler intentionally owns session creation and task execution — these do not live inside the message processor — so that different processors share the same request lifecycle.

## 2. Architecture & Design

**Single-class module.** `AskRequestHandler` is the sole class. There is no `__init__.py`, no base class, and no protocol to implement.

**Dependency injection.** All dependencies are passed to the constructor. The `EndpointsHandlersModule` in `src/container_config.py` wires them via the `injector` framework.

**Design decisions evident from comments:**
- Session creation is owned by `handle()`, not by the processor — this keeps processors stateless with respect to session lifecycle.
- `_maybe_autorun_tasklist` was designed so that when an LLM calls `delegate_tasks`, the resulting tasklist JSON is auto-executed. The comment explicitly says this is intentionally in the request handler rather than in `FunctionCallingProcessor`.
- The handler accepts both `selectType` (legacy) and `contextType` (new) for backward compatibility.
- `context_name=None` means "no context" — this is distinct from an empty string, which is normalized to `None`.
- `friendlyName` resolution supports both camelCase and snake_case keys from the client.

**Error handling strategy:**
- Three exception tiers: `ToolHandlerError` (caught specifically, error appended to session), generic `Exception` (500), and per-section try/except blocks for session creation and resolution (fail gracefully).
- Session creation errors in `chat2_store` are logged but non-fatal — the v1 session already exists.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `AskRequestHandler` | `object` | Validates `/ask` payloads, resolves/creates chat sessions, delegates to message processor, returns response |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `ask_request_handler.py` | Full `/ask` endpoint logic — validation, session management, processor dispatch, response formatting | `AskRequestHandler` |

No `__init__.py` exists in this module.

## 5. Dependencies

### Standard Library
- `json` — JSON parsing (tasklist detection, response serialization)
- `logging` — structured logging via `logging.getLogger(__name__)`
- `typing` — `Any`, `Dict`, `Tuple`, `Optional`

### Third-Party Packages
- None directly. All third-party usage is through injected dependencies.

### Internal Modules

| Module | Used For |
|---|---|
| `src.agent` | `AgentManager`, `Agent` — agent lookup and validation |
| `src.config_manager` | `ConfigManager` — injected but not directly used in current code |
| `src.storage.base` | `Storage` — session CRUD, context creation, message appending |
| `src.storage.models` | `ChatMessage` — constructing error messages for session append |
| `src.message_processors.processor_factory` | `ProcessorFactory` — resolving the message processor by name |
| `src.message_processors.function_calling_processor` | `ToolHandlerError` — caught specifically for tool execution failures |
| `src.chat2.facade` | `Chat2Store` — optional parallel session creation in chat2 layer |

### Optional Dependencies
- `Chat2Store` is `Optional` in the constructor — the handler works without it.
- `get_or_create_context` on `Storage` is checked via `hasattr` — older storage implementations are supported.

## 6. Configuration / Settings

None. `AskRequestHandler` reads no config keys, env vars, or file paths directly. All configuration flows through the injected `Agent`, `Storage`, and `ProcessorFactory` objects.

## 7. Exceptions

None. `AskRequestHandler` defines no custom exception classes. It catches:
- `ToolHandlerError` (from `src.message_processors.function_calling_processor`)
- `Exception` (broad catch-all)
- Specific `Exception` in nested try/except blocks for session and chat2 operations

## 8. Module-Level Constants

None. No constants are defined at module level.

## 9. Methods (by class)

### `AskRequestHandler`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, processor_factory: ProcessorFactory, chat2_store: Optional[Chat2Store] = None) -> None` | Stores all dependencies and initializes `self.logger`. The `config` parameter is stored but not currently accessed by any method. `chat2_store` is optional; when provided, new sessions are mirrored into the chat2 layer. |
| `_maybe_autorun_tasklist` | instance | `(self, *, primary_agent: Agent, secondary_agent: Optional[Agent], account: Dict[str, Any], conversation_id: str, context_name: Optional[str], response_text: str) -> str` | Checks if `response_text` is a JSON tasklist from `delegate_tasks`. If yes and a `secondary_agent` is available, attempts to execute the tasklist via `self.task_runner.run()`. Returns the task execution summary as JSON, or the original `response_text` if no tasklist was detected. **⚠️ Currently non-functional:** `self.task_runner` is never set in `__init__` and no `TaskRunner` class exists in the codebase, so this method will raise `AttributeError` if a tasklist is detected. All parameters are keyword-only. |
| `handle` | instance | `(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]` | Main entry point for `/ask` requests. Validates `question`, `agentName`, `accountName` (400 if missing/invalid). Resolves or creates a chat session via `Storage`, with optional `friendlyName` lookup. Optionally creates a parallel `chat2_store` session. Ensures context exists via `get_or_create_context` if `context_name` is provided. Resolves the primary agent and optional partner agent. Sets `processor.context_type` if supported. Delegates to `processor.process_message(...)` and returns `(200, {"response": ..., "conversation_id": ...})`. Catches `ToolHandlerError` (appends error to session, returns 500) and generic `Exception` (500). |

## 10. Usage Examples

### HTTP endpoint (app.py)

```python
from src.message_endpoints.ask_request_handler import AskRequestHandler

handler = container.get(AskRequestHandler)

@app.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json(silent=True) or {}
    status, body = handler.handle(payload)
    return jsonify(body), status
```

### CLI REPL (main.py)

```python
from src.message_endpoints.ask_request_handler import AskRequestHandler

ask_handler = container.get(AskRequestHandler)

status, body = ask_handler.handle({
    "question": "What is the weather?",
    "agentName": "lucy",
    "accountName": "junwin",
    "contextName": "lucyproject",
})
print(body["response"])
```

### Direct construction (tests)

```python
handler = AskRequestHandler(
    agent_manager=mock_agent_manager,
    config=mock_config,
    storage=mock_storage,
    processor_factory=mock_factory,
    chat2_store=None,  # optional
)
status, body = handler.handle({"question": "hi", "agentName": "test", "accountName": "test"})
```

## 11. Edge Cases & Gotchas

1. **`_maybe_autorun_tasklist` has an `AttributeError` bug.** The method calls `self.task_runner.run(...)` but `task_runner` is never set in `__init__` and is not injected. There is no `TaskRunner` class in the codebase. If an LLM triggers `delegate_tasks`, the method will crash. Currently, the method silently returns `response_text` if the JSON parse fails or the parsed object is not a tasklist — so the bug is only hit when a valid tasklist JSON is returned by the delegate_tasks tool.

2. **`config` parameter is stored but unused.** The constructor accepts and stores `config` but no method accesses `self.config`. It appears to be carried for future use or API symmetry.

3. **Context auto-creation depends on `hasattr`.** The call to `self.storage.get_or_create_context` is guarded by `hasattr`. If the storage backend lacks this method, context creation is silently skipped with a warning log. This means context-based features (durable tasklists, progress) will not work with older storage backends.

4. **`context_name` normalization:** `None` means "no context". An empty or whitespace-only string is normalized to `None`. The distinction matters because passing `contextName: ""` vs omitting the key entirely has the same effect.

5. **Partner agent resolution is lenient.** If `partner_agent_name` is specified but the agent is not found in `AgentManager`, the request continues with `partner_agent_obj = None`. The downstream processor decides how to handle a missing partner agent.

6. **Session creation is best-effort for chat2.** If `chat2_store.create_session()` fails, it is logged but does not fail the request — the v1 session already exists. This means v1 and chat2 can drift.

7. **`friendlyName` / `friendly_name` dual-key support.** The client may send either camelCase or snake_case. If both are present, camelCase takes precedence.

8. **No tests exist for this module.** There are no test files matching `*message_endpoint*` or `*ask_request*` anywhere in the `tests/` tree.

9. **Processor `context_type` is set by hasattr check.** The handler sets `processor.context_type = context_type` only if the processor has that attribute. This is a duck-typing pattern that silently ignores unsupported processors.

10. **Error messages appended to session are not guaranteed.** The `ToolHandlerError` handler tries to append an error `ChatMessage` to the session, but if `conversationId` is empty (which can happen if session creation failed), the append is skipped. If the append itself fails, it is logged and swallowed.

11. **`agentName` and `accountName` are lowercased.** This means agent definitions and account identifiers must be stored/compared in lowercase, or the system must handle case-insensitive lookups downstream.

## 12. Consumers

| Consumer | What It Uses |
|---|---|
| `app.py` (Flask `/ask` route) | `container.get(AskRequestHandler).handle(payload)` — the primary HTTP entry point |
| `main.py` (CLI REPL) | `container.get(AskRequestHandler).handle(payload)` — CLI single-query and interactive modes |
| `src/container_config.py` (`EndpointsHandlersModule`) | Constructs and provides `AskRequestHandler` via injector DI |
| No test files | No tests currently import or exercise this module |
