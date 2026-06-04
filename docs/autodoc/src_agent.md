---
tags:
  - agent
  - json
  - agentmanager
  - dataclass
  - from_dict
  - to_dict
  - allows_tool
  - module
  - configuration
  - validate
  - src/agent
---

# Module: `src/agent`

Agent configuration model and manager — loads, validates, and serves agent definitions from a JSON file.

## Source Files

| File | Role |
|------|------|
| `src/agent/__init__.py` | Exports `Agent` and `AgentManager` |
| `src/agent/agent.py` | `Agent` dataclass — config model with `from_dict()` / `to_dict()` / `allows_tool()` |
| `src/agent/agent_manager.py` | `AgentManager` — loads/saves/upserts agents from a JSON file |

## Key Classes

### `Agent` (dataclass)
- **Fields:** `name`, `language_code`, `context_type`, `max_prompt_conversations`, `max_prompt_documents`, `temperature`, `save_responses`, `model`, `message_processor`, `max_function_call_iterations`, `partner_agent`, `system_prompt`, `style_prompt`, `persona`, `allowed_tools`
- **Key methods:**
  - `from_dict(data: Dict) -> Agent` — construct from dict with legacy field mapping and validation
  - `to_dict() -> Dict` — serialize back to dict
  - `allows_tool(tool_name: str) -> bool` — strict intersection check against `allowed_tools`
  - `_coerce_bool(value) -> bool` — static helper for bool coercion
  - `_format_unknown_fields_message(...)` — static helper for error messages

### `AgentManager`
- **Constructor:** `__init__(path: str = "./agents.json")` — loads agents on init
- **Key methods:**
  - `load_agents()` — robust JSON load, per-agent error isolation
  - `save_agents()` — serialize all agents to JSON
  - `get_agent(name: str) -> Optional[Agent]`
  - `is_valid(name: str) -> bool`
  - `get_agent_names() -> List[str]`
  - `get_available_agents() -> List[Agent]`
  - `upsert_agent(agent: Agent)` — insert or update in memory (no auto-save)

## Dependencies

| Dependency | Direction | Notes |
|------------|-----------|-------|
| `json` | stdlib | AgentManager serialization |
| `pathlib.Path` | stdlib | File path handling |
| `logging` | stdlib | Both modules |
| `typing` | stdlib | Type hints |
| `dataclasses` | stdlib | Agent dataclass |

**Consumers** (modules that import from `src.agent`):
- `src.prompt_builders.prompt_builder` — `AgentManager`, `Agent`
- `src.message_processors.function_calling_processor` — `Agent`
- `src.message_processors.automation_processor` — `Agent`
- `src.message_processors.task_running_processor` — `Agent`
- `src.message_processors.message_processor_interface` — `Agent`
- `src.message_endpoints.ask_request_handler` — `AgentManager`, `Agent`
- `src.http_endpoints.chats_endpoints` — `AgentManager`
- `src.container_config` — `AgentManager`
