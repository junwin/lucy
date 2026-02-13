---
tags:
  - message
  - prompt_builder
  - module
  - base
  - system
  - agent
  - config
  - document
  - context_name
  - doc
  - src/prompt_builders
---

# `src/prompt_builders`

## Source files
- `src/prompt_builders/__init__.py`
- `src/prompt_builders/prompt_builder_interface.py`
- `src/prompt_builders/prompt_builder.py`

## Key classes
- **`PromptBuilderInterface`** (`prompt_builder_interface.py`)
  - Abstract base class defining `build_prompt(...) -> List[ChatMessageDict]`.

- **`PromptBuilder`** (`prompt_builder.py`)
  - Concrete implementation that builds an OpenAI-compatible `messages` array.
  - Responsibilities:
    - Build the main system message from agent config (`system_prompt`, `persona`, `style_prompt`).
    - Append optional `extra_system_messages`.
    - Append chat history from `Storage.get_chat_session(...)` (bounded by `agent.max_prompt_conversations`).
    - Append named context from storage (`get_or_create_context` / `get_context`) using `ctx.data['text']`.
    - Optionally append document snippets via `get_document_context(...)` when `context_type` is `documents` or `hybrid`.
    - Append the current user message and ensure it is last.

## Dependencies
- **stdlib:** `abc`, `logging`, `typing`
- **third-party:** `injector`
- **internal:**
  - `src.config_manager.ConfigManager`
  - `src.agent.AgentManager`, `src.agent.Agent`
  - `src.storage.base.Storage`
  - `src.utils.document_context.get_document_context`

## Methods in the module service/base class
### `PromptBuilderInterface`
- `build_prompt(*, content_text, conversation_id, agent_name, account_name, context_type="none", max_prompt_chars=6000, context_name="", extra_system_messages=None) -> List[ChatMessageDict]`

### `PromptBuilder`
- `__init__(agent_manager, config, storage)`
- `build_prompt(...) -> List[Dict[str, str]]`
- `_build_agent_system_message(agent_name: str, agent: Optional[Agent]) -> str`
- `_get_chat_history_messages(conversation_id: str, account_name: str, agent_name: str, max_conversations: int) -> List[Dict[str, str]]`
- `_get_context_state(account_name: str, context_name: str) -> Optional[Any]`
- `_get_context_text(account_name: str, context_name: str) -> str`
- `_ensure_current_query(messages: List[Dict[str, str]], current_query: str) -> List[Dict[str, str]]`

## Other module-level functions/constants
- `estimate_tokens_from_text(text: str) -> int`
- `DEFAULT_PROMPT_BUDGET_TOKENS = 12000`
- `DEFAULT_SOURCE_BUDGETS = {"agent": 0.4, "account": 0.4, "context": 0.2}`
