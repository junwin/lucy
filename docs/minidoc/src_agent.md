```markdown
---
tags:
  - src_agent
  - lucyproject
  - Agent
  - AgentManager
---

## 1. Summary
The `src.agent` module is responsible for defining the `Agent` configuration model and managing the loading, saving, and accessing of agent definitions through the `AgentManager`. It provides a robust mechanism for creating agent instances from raw dictionary data, ensuring backward compatibility with legacy field names and offering helpful validation errors for configuration issues. This module fits into the overall architecture by serving as a foundational component for agent management, enabling the dynamic configuration of agents in a larger system. It solves the problem of managing agent configurations in a structured and error-tolerant manner, allowing for easy updates and retrieval of agent definitions.

## 2. Architecture & Design
The module employs several key design patterns:
- **Data Class Pattern**: The `Agent` class is implemented as a dataclass, which simplifies the creation of class instances and provides built-in methods for serialization.
- **Robust Loading Strategy**: The `AgentManager` class uses a strategy for loading agents that allows for partial success; if one agent fails to load due to configuration issues, others can still be processed.
- **Error Handling**: The design incorporates strict and lenient loading modes, allowing users to choose how to handle unknown fields in agent configurations.

The `AgentManager` class is composed of multiple `Agent` instances, managing their lifecycle and providing methods for retrieval and modification. The `Agent` class is designed to be flexible, allowing for legacy field names to be mapped to current ones, which is crucial for maintaining backward compatibility.

## 3. Key Classes

| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| Agent         | None        | Represents an agent configuration with validation.|
| AgentManager  | None        | Manages loading, saving, and accessing agents.   |

## 4. Source Files

| File                      | Responsibility                                      | Notable Exports            |
|---------------------------|----------------------------------------------------|-----------------------------|
| `__init__.py`            | Initializes the module and exports Agent and AgentManager. | Agent, AgentManager         |
| `agent.py`               | Defines the Agent class and its configuration logic. | Agent                       |
| `agent_manager.py`       | Implements the AgentManager for managing agents.   | AgentManager                |

## 5. Dependencies
- **Standard library**:
  - `json`
  - `logging`
  - `pathlib`
  - `typing`
- **Third-party packages**: None
- **Internal modules**:
  - `from .agent import Agent`
- **Optional dependencies**: None

## 6. Configuration / Settings

| Key                     | Type    | Default           | What it controls                          |
|-------------------------|---------|-------------------|-------------------------------------------|
| agents_path             | str     | "./agents.json"   | Path to the JSON file storing agent data.|
| strict_fields           | bool    | True              | Controls strictness of field validation.  |

## 7. Exceptions
| Exception               | Base         | When Raised                                      |
|-------------------------|--------------|-------------------------------------------------|
| None                    | None         | None                                            |

## 8. Module-Level Constants
| Constant                | Value        |
|-------------------------|--------------|
| None                    | None         |

## 9. Methods (by class)

### Agent

| Method                  | Type         | Signature                                      | Description                                                                 |
|-------------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| _coerce_bool            | staticmethod | _coerce_bool(value: Any) -> bool              | Coerces various types to a boolean value. Raises ValueError for invalid types. |
| _format_unknown_fields_message | staticmethod | _format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str | Formats a message for unknown fields in agent configuration.                |
| from_dict               | staticmethod | from_dict(data: Dict[str, Any], strict: bool = True) -> "Agent" | Creates an Agent from a dictionary, handling legacy field names and validation. |
| to_dict                 | instance     | to_dict() -> Dict[str, Any]                   | Serializes the Agent instance to a dictionary suitable for JSON storage.   |
| allows_tool             | instance     | allows_tool(tool_name: str) -> bool           | Checks if a specific tool is allowed for this agent based on allowed_tools. |

### AgentManager

| Method                  | Type         | Signature                                      | Description                                                                 |
|-------------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| __init__                | instance     | __init__(path: str = "./agents.json", strict_fields: bool = True) | Initializes the AgentManager with a path and strictness setting.          |
| get_agent               | instance     | get_agent(name: str) -> Optional[Agent]       | Retrieves an agent by name, returning None if not found.                  |
| is_valid                | instance     | is_valid(name: str) -> bool                    | Checks if an agent with the given name exists.                            |
| load_agents             | instance     | load_agents(strict: Optional[bool] = None) -> None | Loads agents from the configured JSON file, handling errors gracefully.   |
| save_agents             | instance     | save_agents() -> None                          | Saves the current list of agents to the JSON file.                        |
| get_agent_names         | instance     | get_agent_names() -> List[str]                | Returns a list of names of all loaded agents.                             |
| get_available_agents     | instance     | get_available_agents() -> List[Agent]         | Returns the list of currently loaded agents.                              |
| upsert_agent            | instance     | upsert_agent(agent: Agent) -> None            | Inserts or updates an agent in memory.                                    |
| remove_agent            | instance     | remove_agent(name: str) -> bool                | Removes an agent by name, returning True if successful.                   |

## 10. Usage Examples
```python
from src.agent import Agent, AgentManager

# Creating an agent from a dictionary
agent_data = {
    "name": "ExampleAgent",
    "allowed_tools": ["tool1", "tool2"],
    "use_embeddings": True
}
agent = Agent.from_dict(agent_data)

# Managing agents with AgentManager
manager = AgentManager()
manager.upsert_agent(agent)
print(manager.get_agent_names())
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The `AgentManager` is designed to be robust; if one agent fails to load, it logs the error and continues loading others.
- **Legacy Field Mapping**: The module supports legacy field names, which can lead to confusion if not documented properly.
- **Thread Safety**: The current implementation does not guarantee thread safety; concurrent modifications to the agent list may lead to inconsistent states.
- **Validation Logic**: The validation logic is forgiving in certain cases (e.g., coercing types), which may mask configuration errors if not used carefully.

## 12. Consumers

| Consumer                | What it uses                                   |
|-------------------------|------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |
```