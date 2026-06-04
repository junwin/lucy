---
tags:
  - agent
  - module
  - dataclass
  - language_code
  - context_type
  - max_prompt_conversation
  - max_prompt_document
  - temperature
  - save_response
  - message_processor
  - src/agent
---

# Module: `src/agent`

Agent configuration model with robust loading and logging. Backward compatible with legacy field names.

## Source Files

| File | Purpose |
|------|---------|
| `src/agent/__init__.py` | Exports `Agent` and `AgentManager` |
| `src/agent/agent.py` | `Agent` dataclass — config model, validation, serialization |
| `src/agent/agent_manager.py` | `AgentManager` — load/save/query agent definitions from JSON |

## Key Classes

### `Agent` (dataclass)

Configuration for a single agent. Fields:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `name` | `str` | (required) | |
| `language_code` | `str` | `"en-US"` | |
| `context_type` | `str` | `"hybrid"` | Legacy key `select_type` mapped automatically |
| `max_prompt_conversations` | `int` | `6` | |
| `max_prompt_documents` | `int` | `4` | |
| `temperature` | `float` | `0.0` | |
| `save_responses` | `bool` | `True` | Legacy key `save_reposnses` mapped automatically |
| `model` | `str` | `"gpt-5.1"` | |
| `message_processor` | `str` | `"function_calling_processor"` | |
| `max_function_call_iterations` | `int` | `10` | |
| `partner_agent` | `Optional[str]` | `None` | |
| `system_prompt` | `str` | `""` | |
| `style_prompt` | `str` | `""` | |
| `persona` | `str` | `""` | |
| `allowed_tools` | `Optional[List[str]]` | `None` | `None`/`[]` = no tools allowed |

### `AgentManager`

Manages loading, saving, and accessing `Agent` definitions from a JSON file.

| Method | Description |
|--------|-------------|
| `get_agent(name: str) -> Optional[Agent]` | Look up agent by name |
| `is_valid(name: str) -> bool` | Check if agent name exists |
| `load_agents() -> None` | Load agents from JSON file (robust per-item validation) |
| `save_agents() -> None` | Serialize agents to JSON file |
| `get_agent_names() -> List[str]` | List all agent names |
| `get_available_agents() -> List[Agent]` | Return all agent objects |
| `upsert_agent(agent: Agent) -> None` | Insert or update in memory (no auto-save) |

## Dependencies

- **Standard library**: `json`, `logging`, `pathlib.Path`, `typing` (`List`, `Dict`, `Optional`, `Any`), `dataclasses`
- **Internal**: none (leaf module)

## Consumers (who imports `src.agent`)

| Consumer | What it uses |
|----------|-------------|
| `src/prompt_builders/prompt_builder.py` | `AgentManager`, `Agent` |
| `src/message_processors/function_calling_processor.py` | `Agent` |
| `src/message_processors/automation_processor.py` | `Agent` |
| `src/message_processors/task_running_processor.py` | `Agent` |
| `src/message_processors/message_processor_interface.py` | `Agent` |
| `src/message_endpoints/ask_request_handler.py` | `AgentManager`, `Agent` |
| `src/http_endpoints/chats_endpoints.py` | `AgentManager` |
| `src/container_config.py` | `AgentManager` |
