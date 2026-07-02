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

## 1. Summary

This module provides the **Agent configuration model** (`Agent` dataclass) and the **AgentManager** service that loads, validates, serves, and persists agent definitions from a JSON file. It is the single source of truth for every configurable agent in the Lucy system — model selection, prompt assembly parameters, tool permission whitelists, and behavioural flags like response saving.

It solves the problem of centralising agent configuration so that the rest of the system (prompt builders, message processors, HTTP endpoints, app bootstrap) can simply ask the `AgentManager` for an agent by name and get a validated, type-safe `Agent` object without touching raw JSON.

## 2. Architecture & Design

- **Dataclass with static factory.** `Agent` is a frozen-set of fields but NOT frozen (mutable after creation). Construction from raw dicts is handled by `Agent.from_dict()` — the constructor itself is called only after validation and coercion.
- **Per-item robustness.** `AgentManager.load_agents()` parses the JSON array top-level, then iterates each entry. A single malformed agent logs an error but never blocks other agents from loading.
- **Strict/non-strict toggle.** The `strict` flag (default `True`) controls whether unknown fields in agent config raise `ValueError` or are silently logged and stripped. This catches typos in production but can be relaxed for development via `strict_agent_fields` (wired by callers of `AgentManager`).
- **Legacy field mapping.** `from_dict` transparently maps `select_type` → `context_type` and `save_reposnses` → `save_responses` before validation. The mapping is backward-compatible and logged at DEBUG level.
- **Coercion, not rejection.** Numeric fields (`max_prompt_conversations`, etc.) and `temperature` are coerced where possible (e.g. `"5"` → `5`). `allowed_tools` accepts both `["a","b"]` and `"a,b"` (comma-separated string) as input. `save_responses` uses a broad `_coerce_bool` that handles `bool`, `str`, and numeric types.
- **Strict-intersection tool model.** `allowed_tools=None` and `allowed_tools=[]` both deny all tools — there is no "allow everything" sentinel. Only an explicit non-empty list grants access.

## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `Agent` | (dataclass) | Immutable-ish configuration record for one agent: model, prompts, tool access, etc. |
| `AgentManager` | (none) | Loads, validates, serves, and persists agent definitions from a JSON file. |

## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Module public API | `Agent`, `AgentManager` |
| `agent.py` | `Agent` dataclass, `from_dict`/`to_dict`, `allows_tool`, coercion helpers | `Agent` |
| `agent_manager.py` | JSON file I/O, per-item loading, lookup, upsert | `AgentManager` |

## 5. Dependencies

### Standard library
- `dataclasses` (dataclass, fields)
- `json`
- `logging`
- `pathlib.Path`
- `typing` (Optional, List, Any, Dict)
- `__future__.annotations` (PEP 604 style)

### Third-party packages
- None

### Internal modules
- None. This is a standalone module — it imports only from within itself (`from .agent import Agent`).

### Optional dependencies
- None

## 6. Configuration / Settings

The module itself reads no config keys from `ConfigManager`, environment variables, or files internally. All configuration is injected via constructor parameters:

| Key | Type | Default | What it controls |
|---|---|---|---|
| `path` (AgentManager) | `str` | `"./agents.json"` | Filesystem path to the agents JSON file |
| `strict_fields` (AgentManager) | `bool` | `True` | Whether unknown fields in agent configs cause `ValueError` (True) or warn-and-strip (False) |

Callers (e.g. `container_config.py`, `app.py`) typically wire `strict_fields` from the `Config` object's `strict_agent_fields` key, and `path` from `config.agents_path`.

## 7. Exceptions

None. This module defines no custom exception classes. It raises standard `ValueError` and `TypeError` for validation failures, and lets `json.JSONDecodeError` propagate from `load_agents` (caught and logged internally).

## 8. Module-Level Constants

None. The only module-level name is `logger = logging.getLogger(__name__)`.

## 9. Methods (by class)

### Agent

| Method | Type | Signature | Description |
|---|---|---|---|
| `from_dict` | static | `from_dict(data: Dict[str, Any], strict: bool = True) -> Agent` | Constructs an `Agent` from a raw dictionary. Performs legacy field mapping (`select_type`→`context_type`, `save_reposnses`→`save_responses`), validates `name` is present, checks for unknown fields (hard-fail or warn-and-strip depending on `strict`), coerces/allows tolerant parsing for `allowed_tools`, integer fields, `temperature`, and `save_responses`. Returns a fully validated `Agent`. Raises `ValueError` for missing/malformed fields, `TypeError` if `data` is not a dict. |
| `to_dict` | instance | `to_dict() -> Dict[str, Any]` | Serialises the `Agent` to a flat dictionary suitable for `json.dump`. Always emits all 15 fields with their current values, including `None` for `partner_agent` and `allowed_tools`. No side effects beyond dict creation. |
| `allows_tool` | instance | `allows_tool(tool_name: str) -> bool` | Checks whether a named tool is permitted for this agent. Uses strict intersection: if `allowed_tools` is `None` or `[]`, returns `False`; otherwise returns `True` only if `tool_name` is in the list. No logging, no side effects. |
| `_coerce_bool` | static | `_coerce_bool(value: Any) -> bool` | Coerces a value to `bool`. Handles `bool` directly; strings `"true"`, `"1"`, `"yes"`, `"y"`, `"on"` (case-insensitive) return `True`; attempts `bool(int(value))` for numeric types; raises `ValueError` on unrecognised input. |
| `_format_unknown_fields_message` | static | `_format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str` | Builds a human-readable error message listing the unknown fields and, where relevant, suggests corrections (e.g. `allowed_tool` → hint "Did you mean 'allowed_tools'?"). |

### AgentManager

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `__init__(path: str = "./agents.json", strict_fields: bool = True)` | Initialises the manager. Stores `path` as a `Path` object, stores `strict_fields`, initialises an empty `self.agents` list, then immediately calls `load_agents()`. |
| `get_agent` | instance | `get_agent(name: str) -> Optional[Agent]` | Looks up an agent by name. Returns the `Agent` if found, `None` otherwise. O(n) scan — fine for the expected agent count (<100). |
| `is_valid` | instance | `is_valid(name: str) -> bool` | Returns `True` if any loaded agent has the given name. Convenience wrapper around `any()`. |
| `load_agents` | instance | `load_agents(strict: Optional[bool] = None) -> None` | Reads and parses the agents JSON file. Handles: file-not-found (logs info, empty list), JSON decode errors (logs error, empty list), single-object files (warns and wraps in list), non-list/non-dict structures (logs error, empty list). Validates each entry via `Agent.from_dict()`, logging and skipping malformed entries. The `strict` parameter can override `self.strict_fields` for a single load. Sets `self.agents` on success. |
| `save_agents` | instance | `save_agents() -> None` | Serialises all agents via `to_dict()` and writes as a JSON array to `self.path` with `indent=2` and `ensure_ascii=False` (supports Unicode/emoji in prompts). Logs errors on I/O failure; does not raise. |
| `get_agent_names` | instance | `get_agent_names() -> List[str]` | Returns a list of all loaded agent names. |
| `get_available_agents` | instance | `get_available_agents() -> List[Agent]` | Returns the full list of `Agent` objects. |
| `upsert_agent` | instance | `upsert_agent(agent: Agent) -> None` | Inserts or updates an agent in memory (by name). Does **not** auto-save — caller must invoke `save_agents()` to persist. |

## 10. Usage Examples

```python
from src.agent import Agent, AgentManager

# --- Construct an Agent from a raw dictionary ---
raw = {
    "name": "peace",
    "model": "gpt-5.1",
    "message_processor": "function_calling_processor",
    "system_prompt": "You are Peace, a helpful architect.",
    "allowed_tools": ["file_load", "file_save", "execute_command"],
}
agent = Agent.from_dict(raw)       # strict=True by default
print(agent.allows_tool("file_load"))   # True
print(agent.allows_tool("sudo"))        # False

# --- Load all agents from disk ---
mgr = AgentManager(path="static/data/agents.json", strict_fields=True)
peace = mgr.get_agent("peace")
if peace:
    print(peace.model)

# --- Add a new agent and persist ---
new_agent = Agent.from_dict({"name": "colin", "model": "gpt-4o"})
mgr.upsert_agent(new_agent)
mgr.save_agents()
```

## 11. Edge Cases & Gotchas

- **`allowed_tools=None` vs `allowed_tools=[]` are identical in behaviour** — both deny all tools. There is no way to "allow everything." You must explicitly list every permitted tool.
- **Legacy field `save_reposnses`** is mapped to `save_responses` automatically, so clients using the old name won't break, but the serialised output always uses `save_responses`.
- **Strict mode vs permissive mode.** When `strict=False`, unknown fields are silently stripped — useful for development or gradual rollout. When `strict=True` (default), a typo like `"namee"` will hard-fail that agent (but not others).
- **Per-item robustness in `load_agents`** means a single corrupt agent entry will not prevent the rest from loading. Always check `len(mgr.agents)` after loading if you expect a specific count.
- **Coercion can surprise.** A string `"true"` for `save_responses` works; a string `"maybe"` raises `ValueError`. Integer fields like `max_prompt_conversations` accept `"6"` but not `"six"`.
- **`allowed_tools` as comma-separated string** (`"tool_a, tool_b"`) is parsed into a list — but leading/trailing spaces are stripped per tool name.
- **Thread safety is not guaranteed.** `load_agents` and `upsert_agent` mutate `self.agents` without locking. Callers in multi-threaded contexts must synchronise externally.
- **`save_agents` never raises.** I/O errors are logged and swallowed. Always check logs if persistence seems to fail.
- **The `Agent` dataclass is not frozen.** Fields can be mutated after construction. This is by design (agents can be updated in-place before save) but means consumers should not assume immutability.

## 12. Consumers

| Consumer | What it uses |
|---|---|
| `app.py` | `AgentManager` — initialises the manager at startup |
| `main.py` | `AgentManager` — CLI entry point (via `src/agent_manager.py` re-export) |
| `src/container_config.py` | `AgentManager` — injects into the dependency container |
| `src/prompt_builders/prompt_builder.py` | `AgentManager`, `Agent` — looks up agents to build prompts |
| `src/message_endpoints/ask_request_handler.py` | `AgentManager`, `Agent` — resolves agent for incoming `/ask` requests |
| `src/http_endpoints/chats_endpoints.py` | `AgentManager` — agent validation in chat endpoints |
| `src/http_endpoints/prompt_builder_debug_endpoints.py` | `AgentManager` — debug endpoint agent resolution |
| `src/message_processors/function_calling_processor.py` | `Agent` — reads tool permissions and agent config during FCP |
| `src/message_processors/automation_processor.py` | `Agent` — reads agent config for automation workflows |
| `src/message_processors/task_running_processor.py` | `Agent` — reads agent config during task execution |
| `src/message_processors/message_processor_interface.py` | `Agent` — type annotation on processor interface |
| `tests/test_agent_allowed_tools.py` | `Agent` — unit tests for tool permission logic |
| `tests/test_allowed_tools.py` | `Agent` — additional tool permission tests |
| `tests/test_strict_agent_fields.py` | `Agent`, `AgentManager` — tests for strict/non-strict loading |
| `tests/test_agent_manager_unknown_field.py` | `AgentManager` — tests for unknown field handling |
| `tests/test_admin_reload.py` | `AgentManager` — admin reload integration tests |
