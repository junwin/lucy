---
tags:
  - src_agent
  - lucyproject
  - Agent
  - AgentManager
  - dataclass
  - configuration
  - tool_permissions
---

# Module: `src/agent`

## Summary

Provides the `Agent` configuration model (dataclass) and the `AgentManager` that loads, validates, and serves agent definitions from a JSON file. Handles legacy field name mapping, strict validation of unknown fields, and tool permission checking via the `allows_tool` method.

## Key Classes

| Class | Description |
|---|---|
| `Agent` | Dataclass representing a single agent's configuration (name, model, prompts, tool permissions, etc.) |
| `AgentManager` | Loads/saves agent definitions from a JSON file, provides lookup and upsert operations |

## Source Files

| File | Role |
|---|---|
| `src/agent/__init__.py` | Exports `Agent` and `AgentManager` |
| `src/agent/agent.py` | `Agent` dataclass with `from_dict`, `to_dict`, `allows_tool` |
| `src/agent/agent_manager.py` | `AgentManager` — loading, saving, lookup, upsert |

## Dependencies

- **Standard library:** `dataclasses`, `json`, `logging`, `pathlib`, `typing`
- **Internal:** none (standalone module)

## Methods — `Agent` (service/base class)

| Method | Signature | Description |
|---|---|---|
| `from_dict` | `static from_dict(data: Dict[str, Any]) -> Agent` | Construct an Agent from a dict, handling legacy field names and validation |
| `to_dict` | `to_dict() -> Dict[str, Any]` | Serialize Agent to a JSON-compatible dict |
| `allows_tool` | `allows_tool(tool_name: str) -> bool` | Check if a tool is permitted (strict intersection) |
| `_coerce_bool` | `static _coerce_bool(value: Any) -> bool` | Coerce various types to bool |
| `_format_unknown_fields_message` | `static _format_unknown_fields_message(agent_name, unknown_keys) -> str` | Build a helpful error message for unknown fields |

## Methods — `AgentManager`

| Method | Signature | Description |
|---|---|---|
| `get_agent` | `get_agent(name: str) -> Optional[Agent]` | Look up an agent by name |
| `is_valid` | `is_valid(name: str) -> bool` | Check if an agent name exists |
| `load_agents` | `load_agents() -> None` | Load agents from the JSON file (robust per-item validation) |
| `save_agents` | `save_agents() -> None` | Persist all agents to the JSON file |
| `get_agent_names` | `get_agent_names() -> List[str]` | Return all agent names |
| `get_available_agents` | `get_available_agents() -> List[Agent]` | Return all agent objects |
| `upsert_agent` | `upsert_agent(agent: Agent) -> None` | Insert or update an agent in memory |
