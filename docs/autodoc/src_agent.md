---
tags:
  - agent
  - bool
  - agentmanager
  - str
  - doc
  - source
  - dataclass
  - configuration
  - support
  - mapping
  - src/agent
---

# `src/agent` mini doc

## Purpose
Agent configuration models and a small manager for loading/saving agent definitions (JSON) and looking them up by name.

## Source files
- `src/agent/agent.py`
- `src/agent/agent_manager.py`
- `src/agent/__init__.py`

## Key classes
### `Agent` (`src/agent/agent.py`)
Dataclass representing an agent configuration.

Notable behaviors:
- Loads from raw dicts with legacy key mapping:
  - `select_type` → `context_type`
  - `save_reposnses` → `save_responses`
- Strict validation: unknown fields hard-fail that agent entry.
- Type coercion for common config mistakes (ints, floats, bools, `allowed_tools`).
- Tool allowlist check via `allows_tool()`.

Key methods:
- `from_dict(data: dict) -> Agent`
- `to_dict() -> dict`
- `allows_tool(tool_name: str) -> bool`

### `AgentManager` (`src/agent/agent_manager.py`)
Loads/saves a list of `Agent` objects from a JSON file and provides lookup/list/upsert helpers.

## Main service/base class methods
### `AgentManager`
- `__init__(path: str = "./agents.json")`
- `get_agent(name: str) -> Optional[Agent]`
- `is_valid(name: str) -> bool`
- `load_agents() -> None`
  - Robust loading: JSON must parse, but individual bad agent entries are logged and skipped.
- `save_agents() -> None`
- `get_agent_names() -> List[str]`
- `get_available_agents() -> List[Agent]`
- `upsert_agent(agent: Agent) -> None` (in-memory only; does not auto-save)
