---
tags:
  - src_prompt_builders
  - lucyproject
  - PromptBuilder
  - PromptBuilderInterface
  - ChatMessageDict
  - estimate_tokens_from_text
  - DEFAULT_PROMPT_BUDGET_TOKENS
  - DEFAULT_SOURCE_BUDGETS
---

## 1. Summary

`src/prompt_builders` assembles the full message array sent to the LLM for every `/ask` request. It takes a user query and enriches it with the agent's system message, chat history (from chat2 or v1 storage), optional named context text, and relevant Obsidian document snippets. The result is an OpenAI-compatible `List[Dict[str, str]]` that the `FunctionCallingProcessor` passes directly to the model.

This module sits between the request handler and the message processor — it is the **prompt assembly stage** before any model call. It solves the problem of gathering data from multiple sources (agent config, chat history storage, document index) and combining them into a single coherent prompt.

## 2. Architecture & Design

- **Interface-Implementation split via ABC.** `PromptBuilderInterface` defines a single abstract method `build_prompt()`. `PromptBuilder` is the concrete implementation. This allows consumers to depend on the interface (for test mocking or future alternatives).
- **Dependency injection via `injector`.** The concrete `PromptBuilder` uses `@inject` on its constructor. Dependencies (`AgentManager`, `ConfigManager`, `Storage`, `Chat2Store`) are resolved at wiring time. `Chat2Store` is optional (`Optional[Chat2Store]`).
- **Fail-soft everywhere.** Every non-trivial operation (loading context, fetching chat history, retrieving documents) is wrapped in try/except with `logging.warning` — the prompt is always returned even if some enrichments fail.
- **Chat history dual-path.** `_get_chat_history_messages()` tries chat2 first (if a `Chat2Store` is injected and the session exists). If no `chat2_store` is configured, it returns empty history immediately (no fallback to v1 `Storage` — deliberate design decision).
- **Document context is optional and gated.** Document snippets are only loaded when `context_type` is `"documents"` or `"hybrid"`. The optional `docs_tag` is read from the named context's `data` dict, allowing a context to specify which Obsidian tag to filter by.
- **Separated concerns via private helpers.** `_build_agent_system_message()`, `_get_chat_history_messages()`, `_get_context_text()`, `_get_context_state()`, and `_ensure_current_query()` each handle one data source or post-processing step.
- **Token estimation helper.** The module-level `estimate_tokens_from_text()` function is a rough heuristic (`len(text) // 4`) available for prompt budget planning, though the budget constants (`DEFAULT_PROMPT_BUDGET_TOKENS`, `DEFAULT_SOURCE_BUDGETS`) are currently defined but **not used** in `build_prompt()` itself — they appear to be intended for a future token-budgeting feature.
- **Character capping commented out.** The line `# messages = self._cap_prompt_by_chars_preserving_last_user(messages, max_prompt_chars)` is present but disabled, suggesting a historical or planned feature that was backed out.

## 3. Key Classes

| Class | Base / Parent | Purpose |
|---|---|---|
| `PromptBuilderInterface` | `ABC` | Abstract interface defining the `build_prompt()` contract |
| `PromptBuilder` | `PromptBuilderInterface` | Concrete implementation — assembles the full message list from agent config, history, context, and documents |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Empty — no re-exports | — |
| `prompt_builder_interface.py` | Defines the `PromptBuilderInterface` ABC and `ChatMessageDict` type alias | `PromptBuilderInterface`, `ChatMessageDict` |
| `prompt_builder.py` | Concrete `PromptBuilder` implementation, helper functions, budget constants | `PromptBuilder`, `estimate_tokens_from_text`, `DEFAULT_PROMPT_BUDGET_TOKENS`, `DEFAULT_SOURCE_BUDGETS` |

## 5. Dependencies

**Standard library**
- `abc` (ABC, abstractmethod)
- `logging`
- `typing` (Any, Dict, List, Optional)

**Third-party packages**
- `injector` (the `@inject` decorator) — required at construction time

**Internal modules**
- `src.config_manager` → `ConfigManager`
- `src.agent` → `AgentManager`, `Agent`
- `src.storage.base` → `Storage`
- `src.prompt_builders.prompt_builder_interface` → `PromptBuilderInterface` (self-reference)
- `src.utils.document_context` → `get_document_context`
- `src.chat2.facade` → `Chat2Store`
- `src.chat2.prompt_slice` → `get_last_n_events`

**Optional dependencies**
- `Chat2Store` is an optional constructor parameter (`Optional[Chat2Store]`). When `None`, chat history enrichment is skipped entirely. No try/except import guard — the class is always imported at the top of the file.

## 6. Configuration / Settings

None. `ConfigManager` is injected but its `get()` method is never called in this module. The two budget constants are hardcoded module-level values, not config keys.

## 7. Exceptions

None. No custom exception classes are defined in this module. All external errors are caught and logged via `logging.warning`.

## 8. Module-Level Constants

| Constant | Type | Value | Purpose |
|---|---|---|---|
| `DEFAULT_PROMPT_BUDGET_TOKENS` | `int` | `12000` | Planned total token budget for prompt assembly (currently unused in `build_prompt()`) |
| `DEFAULT_SOURCE_BUDGETS` | `dict` | `{"agent": 0.4, "account": 0.4, "context": 0.2}` | Planned allocation ratios for agent/account/context token budgets (currently unused) |
| `ChatMessageDict` | `TypeAlias` | `Dict[str, Any]` | Type alias for a single chat message dict (role + content) |
| `estimate_tokens_from_text` | `function` | `len(text) // 4` | Rough heuristic: 1 token ≈ 4 characters. Returns `max(1, result)` for non-empty text, `0` for empty. |

## 9. Methods (by class)

### PromptBuilderInterface

| Method | Type | Signature | Description |
|---|---|---|---|
| `build_prompt` | instance (abstract) | `(*, content_text: str, conversation_id: str, agent_name: str, account_name: str, context_type: str = "none", max_prompt_chars: int = 6000, context_name: str = "", extra_system_messages: Optional[List[str]] = None) -> List[ChatMessageDict]` | Builds an OpenAI-compatible messages array. All parameters are keyword-only. `context_type` controls document enrichment (`"none"`, `"documents"`, `"hybrid"`). `extra_system_messages` are injected between the system message and history. Returns a list of `{"role": ..., "content": ...}` dicts. |

### PromptBuilder

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, agent_manager: AgentManager, config: ConfigManager, storage: Storage, chat2_store: Optional[Chat2Store] = None)` | Constructor with `@inject` decorator. Stores all dependencies. `chat2_store` is optional — when `None`, chat history from chat2 is skipped. |
| `build_prompt` | instance | `(*, content_text, conversation_id, agent_name, account_name, context_type="none", max_prompt_chars=6000, context_name="", extra_system_messages=None) -> List[Dict[str, str]]` | Main entry point. Assembles the full message list in order: (1) agent system message, (2) session ID injection, (3) extra system messages, (4) chat history, (5) named context text, (6) document snippets (if context_type allows), (7) current user message. Logs summary counts at the end. Returns the complete messages list. |
| `_build_agent_system_message` | instance | `(self, agent_name: str, agent: Optional[Agent]) -> str` | Combines `agent.system_prompt`, `agent.persona`, and `agent.style_prompt` into one string joined by double newlines. Falls back to `"You are {agent_name}, a helpful assistant."` if agent is None. |
| `_get_chat_history_messages` | instance | `(self, conversation_id, account_name, agent_name, max_conversations) -> List[Dict[str, str]]` | Tries chat2 first: if `chat2_store` is not None and the session exists, streams events, slices with `get_last_n_events`, and returns role/content dicts. Returns `[]` if: `conversation_id` is missing/`"none"`/`"new"`, `max_conversations <= 0`, no `chat2_store` configured, session not found, or any exception. All errors logged as warnings. |
| `_get_context_state` | instance | `(self, account_name: str, context_name: str) -> Optional[Any]` | Returns the `ContextState` object for a named context. Prefers `storage.get_or_create_context()` if available, otherwise uses `storage.get_context()`. Returns `None` if `context_name` is `"none"`/empty or on any error. |
| `_get_context_text` | instance | `(self, account_name: str, context_name: str) -> str` | Extracts the `"text"` key from the context's `data` dict. Used to inject persistent context (like Obsidian notes or project instructions) into the prompt. Returns `""` if context is missing, has no `data` dict, or `data["text"]` is not a string. |
| `_ensure_current_query` | instance | `(self, messages: List[Dict[str, str]], current_query: str) -> List[Dict[str, str]]` | Idempotent guard: if the last message already has `role="user"` with `content == current_query`, returns messages unchanged. Otherwise appends a new user message. Prevents duplicate user messages in the final array. |

## 10. Usage Examples

**Example 1: Direct construction for testing (no DI)**

```python
from src.prompt_builders.prompt_builder import PromptBuilder
from unittest.mock import Mock

agent_mgr = Mock()
agent_mgr.get_agent.return_value = Mock(
    system_prompt="You are helpful.",
    persona="Patient and kind.",
    style_prompt="Keep answers short.",
    max_prompt_conversations=10,
)

pb = PromptBuilder(
    agent_manager=agent_mgr,
    config=Mock(),
    storage=Mock(),
    chat2_store=None,  # skip chat history
)

messages = pb.build_prompt(
    content_text="What is Python?",
    conversation_id="abc-123",
    agent_name="helper",
    account_name="test_user",
    context_type="none",
)

# messages is now:
# [
#   {"role": "system", "content": "You are helpful.\n\nPatient and kind.\n\nKeep answers short."},
#   {"role": "system", "content": "Current session ID: abc-123"},
#   {"role": "user", "content": "What is Python?"},
# ]
```

**Example 2: With document context (`hybrid` mode)**

```python
messages = pb.build_prompt(
    content_text="How do I deploy the app?",
    conversation_id="xyz-456",
    agent_name="devbot",
    account_name="dev_user",
    context_type="hybrid",
    context_name="deploy-context",
)

# If the storage has a context named "deploy-context" with data["text"] set,
# it gets injected as a system message. Additionally, get_document_context()
# is called with the query and any docs_tag from data["tag"], and matching
# Obsidian note snippets are appended.
```

## 11. Edge Cases & Gotchas

1. **Chat history only from chat2 — no v1 fallback.** If `chat2_store` is `None`, `_get_chat_history_messages()` returns `[]` immediately. It does not try to load history from `Storage`. This is by design: chat2 is the sole history source.

2. **`None` agent produces a generic fallback message.** If `agent_manager.get_agent(agent_name)` returns `None`, the system message becomes `"You are {agent_name}, a helpful assistant."` — no persona or style. The prompt still builds successfully.

3. **`max_prompt_conversations` defaults to 0 when agent is None.** The line `max_prompt_conversations = agent.max_prompt_conversations if agent else 0` means a missing agent produces zero history, even if `chat2_store` is available.

4. **Document context failure is silent beyond a warning.** If `get_document_context()` raises, the exception is logged at `WARNING` level and the prompt continues without document snippets. The response will simply lack the enrichment.

5. **Context auto-creation via `get_or_create_context`.** If storage supports `get_or_create_context`, a missing context is created on the fly with empty defaults. This means `_get_context_text()` may return `""` for a just-created context, which is expected.

6. **`data["text"]` typing is strict.** Only `str` values for `data["text"]` are used. If `data["text"]` is `None`, a number, or missing entirely, the method returns `""`. No implicit `str()` conversion.

7. **`_ensure_current_query` prevents duplicate user messages.** If `build_prompt()` is called with a `content_text` that already exists as the last message, it won't be duplicated. This is a defensive guard, likely to handle re-processing scenarios.

8. **`_cap_prompt_by_chars_preserving_last_user` is commented out.** The character-capping logic is disabled. The `max_prompt_chars` parameter is accepted but not used. Prompts can grow unbounded.

9. **`DEFAULT_PROMPT_BUDGET_TOKENS` and `DEFAULT_SOURCE_BUDGETS` are dead code.** These constants exist at module level but are never referenced by `build_prompt()` or any helper. They appear to be scaffolding for a future token-budgeting feature.

10. **Thread-safety.** The class stores injected dependencies but no mutable state between calls. `build_prompt()` is effectively stateless — safe for concurrent use.

11. **`conversation_id` of `"none"` or `"new"`.** These sentinel values suppress both the session ID injection message and chat history loading. They are treated as "no conversation" markers.

12. **`extra_system_messages` are whitespace-filtered.** Only non-empty, non-whitespace-only strings are added. `""` and `"   "` are silently skipped.

13. **`docs_tag` is read from the context's `data["tag"]`**, not from a direct parameter. This means context configuration drives document filtering, keeping the call site simple.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/message_processors/function_calling_processor.py` | `PromptBuilderInterface` as constructor parameter; calls `build_prompt()` on every LLM call iteration |
| `src/message_processors/automation_processor.py` | `PromptBuilderInterface` as parameter to `process_task()`; calls `build_prompt()` for each delegated task |
| `src/container_config.py` | Imports both `PromptBuilder` and `PromptBuilderInterface`; defines `PromptBuilderModule` for DI wiring; instantiates `PromptBuilder` with all dependencies |
| `src/http_endpoints/prompt_builder_endpoints.py` | Imports `PromptBuilder`; instantiates directly (with fallback DI via `container.get()`) for the `/prompt_builder` debug endpoint |
| `src/http_endpoints/prompt_and_docs_endpoints.py` | Imports `PromptBuilder`; same pattern as `prompt_builder_endpoints.py` for the `/build_prompt` debug endpoint |
| `tests/test_prompt_builder_chat2_integration.py` | Direct integration tests — constructs `PromptBuilder` with real `Chat2Store` and mock dependencies; tests 7 scenarios |
| `tests/test_live_prompt_builder.py` | Live integration tests via Flask app on port 5001; hits `/prompt_builder` endpoint |
| `tests/conftest.py` | Provides a `Mock()` fixture named `prompt_builder` used by all FCP unit tests |
| `tests/test_function_calling_processor.py` | Uses the mock `prompt_builder` fixture in 10 test functions |
| `tests/test_tasklists_run_handler.py` | Uses a `Mock()` for `prompt_builder` in handler test setup |
