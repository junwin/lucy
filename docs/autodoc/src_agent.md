---
tags:
  - agent
  - json
  - str
  - configuration
  - loading
  - entry
  - bool
  - to_dict
  - agentmanager
  - definition
  - src/agent
---

# `src/agent`

## Purpose
Agent configuration model and manager for loading/saving agent definitions.

## Source files
- `src/agent/agent.py`
- `src/agent/agent_manager.py`
- `src/agent/__init__.py`

## Key classes
### `Agent` (`src/agent/agent.py`)
Dataclass representing an agent configuration.

Responsibilities:
- Legacy field mapping:
  - `select_type` → `context_type`
  - `save_reposnses` → `save_responses`
- Validation: unknown fields hard-fail that agent entry (so typos are caught)
- Type coercion/validation:
  - `allowed_tools`: `None` | `list[str]` | comma-separated `str`
  - ints: `max_prompt_conversations`, `max_prompt_documents`, `max_function_call_iterations`
  - `temperature`: float
  - `save_responses`: bool
- Serialization: `to_dict()`

Key methods:
- `from_dict(data: dict) -> Agent`
- `to_dict() -> dict`

### `AgentManager` (`src/agent/agent_manager.py`)
Service class that manages a collection of `Agent` objects stored in JSON.

Responsibilities:
- Load agents from a JSON file (default `./agents.json`)
- Robust loading: malformed agent entries are logged and skipped
- Accepts JSON as either a list of agents or a single agent object

Methods (service/base class):
- `__init__(path: str = "./agents.json")`
- `load_agents() -> None`
- `save_agents() -> None`
- `get_agent(name: str) -> Agent | None`
- `is_valid(name: str) -> bool`
- `get_agent_names() -> list[str]`
- `get_available_agents() -> list[Agent]`
- `upsert_agent(agent: Agent) -> None`

## Dependencies
- Standard library: `dataclasses`, `typing`, `logging`, `json`, `pathlib`
- Internal:
  - `src.agent.agent.Agent` (used by `AgentManager`)
