---
tags:
  - promptbuilderinterface
  - abc
  - promptbuilder
  - storage
  - context_name
  - define
  - base
  - concrete
  - config
  - chat2_store
  - src/prompt_builders
  - lucyproject
---

# Module: `src/prompt_builders`

## Source Files

| File | Description |
|------|-------------|
| `__init__.py` | Empty init |
| `prompt_builder_interface.py` | Abstract base class `PromptBuilderInterface` |
| `prompt_builder.py` | Concrete implementation `PromptBuilder` |

## Key Classes

### `PromptBuilderInterface` (ABC)
- **File:** `prompt_builder_interface.py`
- Abstract base class defining the prompt-building contract.

### `PromptBuilder`
- **File:** `prompt_builder.py`
- Concrete implementation of `PromptBuilderInterface`.
- Injected with `AgentManager`, `ConfigManager`, `Storage`, and optional `Chat2Store`.

## Dependencies

**Internal (src):**
- `src.config_manager` — `ConfigManager`
- `src.agent` — `AgentManager`, `Agent`
- `src.storage.base` — `Storage`
- `src.utils.document_context` — `get_document_context`
- `src.chat2.facade` — `Chat2Store`
- `src.chat2.prompt_slice` — `get_last_n_events`

**External:**
- `injector` — `inject`
- `logging` (stdlib)
- `typing` — `Any`, `Dict`, `List`, `Optional`
- `abc` — `ABC`, `abstractmethod`

## Methods

### `PromptBuilderInterface` (base — abstract)

| Method | Signature |
|--------|-----------|
| `build_prompt` | `(*, content_text, conversation_id, agent_name, account_name, context_type="none", max_prompt_chars=6000, context_name="", extra_system_messages=None) -> List[ChatMessageDict]` |

### `PromptBuilder` (concrete)

| Method | Description |
|--------|-------------|
| `__init__(agent_manager, config, storage, chat2_store)` | Constructor — stores injected dependencies |
| `build_prompt(...)` | Builds full OpenAI-compatible messages array (system + history + context + docs + user) |
| `_build_agent_system_message(agent_name, agent) -> str` | Combines system_prompt, persona, and style_prompt |
| `_get_chat_history_messages(conversation_id, account_name, agent_name, max_conversations) -> List[Dict]` | Loads chat history from chat2 store |
| `_get_context_state(account_name, context_name) -> Optional[Any]` | Loads ContextState from storage |
| `_get_context_text(account_name, context_name) -> str` | Extracts text from context state |
| `_ensure_current_query(messages, current_query) -> List[Dict]` | Ensures the last message is the current user query |
