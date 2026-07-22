# Module Documentation for `src/agent`

## YAML Front Matter
```yaml
tags:
  - src_agent
  - lucyproject
  - Agent
  - AgentManager
```

## 1. Summary
The `src/agent` module is responsible for managing agent configurations within the Lucy project. It provides a robust framework for defining agents through the `Agent` dataclass, which includes features for loading configurations from JSON files, validating fields, and handling legacy field names. The module fits into the overall architecture by serving as a foundational component for agent management, ensuring that agents can be easily created, modified, and validated. It solves the problem of maintaining a flexible and user-friendly interface for agent configuration, allowing for both backward compatibility and strict validation.

## 2. Architecture & Design
The module employs several key design patterns:
- **Data Class Pattern**: The `Agent` class is implemented as a dataclass, which simplifies the creation of class instances and provides built-in methods for serialization.
- **Robust Loading Strategy**: The `AgentManager` class manages the loading and saving of agents, ensuring that individual agent configurations are validated without halting the entire loading process.
- **Error Handling**: The design incorporates detailed logging and error handling, allowing for graceful degradation when encountering malformed agent configurations.

The `Agent` class is composed of various fields that define its properties, while the `AgentManager` class manages a collection of `Agent` instances. The two classes interact closely, with `AgentManager` relying on the `Agent` class for creating and validating agent configurations. There is no explicit legacy/v2 split, but the handling of legacy field names in the `Agent` class indicates a design decision to maintain backward compatibility.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| Agent         | None        | Represents an agent configuration with validation. |
| AgentManager  | None        | Manages loading, saving, and accessing agent definitions. |

## 4. Source Files
| File                        | Responsibility                                         | Notable Exports            |
|-----------------------------|-------------------------------------------------------|----------------------------|
| `src/agent/__init__.py`     | Initializes the module and exports key classes.      | `Agent`, `AgentManager`    |
| `src/agent/agent.py`        | Defines the `Agent` dataclass and its methods.       | `Agent`                    |
| `src/agent/agent_manager.py`| Manages agent loading and saving functionalities.     | `AgentManager`             |

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
| Key                  | Type    | Default          | What it controls                          |
|----------------------|---------|------------------|-------------------------------------------|
| `path`               | str     | `"./agents.json"`| Path to the JSON file for agent storage. |
| `strict_fields`      | bool    | `True`           | Controls strictness of field validation. |

## 7. Exceptions
| Exception            | Base         | When Raised                                      |
|----------------------|--------------|-------------------------------------------------|
| None                 | None         | None                                            |

## 8. Module-Level Constants
| Constant             | Value        |
|----------------------|--------------|
| None                 | None         |

## 9. Methods (by class)

### Agent
| Method                | Type         | Signature                                      | Description                                                                                                                                                                                                 |
|-----------------------|--------------|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `_coerce_bool`        | static       | `def _coerce_bool(value: Any) -> bool:`      | Coerces various types to a boolean. Accepts strings, integers, and booleans. Raises `ValueError` if coercion fails.                                                                                       |
| `_format_unknown_fields_message` | static | `def _format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str:` | Formats a message for unknown fields, providing hints for common typos.                                                                                                                                 |
| `from_dict`           | static       | `def from_dict(data: Dict[str, Any], strict: bool = True) -> "Agent":` | Creates an `Agent` instance from a dictionary. Validates required fields and handles legacy field names. Raises `ValueError` for unknown fields based on the `strict` parameter.                          |
| `to_dict`             | instance     | `def to_dict(self) -> Dict[str, Any]:`      | Serializes the `Agent` instance to a dictionary suitable for JSON storage.                                                                                                                                 |
| `allows_tool`         | instance     | `def allows_tool(self, tool_name: str) -> bool:` | Checks if a specific tool is allowed for this agent based on the `allowed_tools` field. Returns `True` or `False`.                                                                                      |

### AgentManager
| Method                | Type         | Signature                                      | Description                                                                                                                                                                                                 |
|-----------------------|--------------|------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`            | instance     | `def __init__(self, path: str = "./agents.json", strict_fields: bool = True):` | Initializes the `AgentManager` with a path and strictness setting. Loads agents from the specified file.                                                                                                 |
| `get_agent`           | instance     | `def get_agent(self, name: str) -> Optional[Agent]:` | Retrieves an `Agent` by name. Returns `None` if not found.                                                                                                                                              |
| `is_valid`            | instance     | `def is_valid(self, name: str) -> bool:`     | Checks if an agent with the specified name exists.                                                                                                                                                       |
| `load_agents`         | instance     | `def load_agents(self, strict: Optional[bool] = None) -> None:` | Loads agents from the configured JSON file. Handles errors gracefully, allowing other agents to load even if one fails.                                                                                  |
| `save_agents`         | instance     | `def save_agents(self) -> None:`              | Saves the current list of agents to the JSON file. Logs any errors encountered during the save process.                                                                                                 |
| `get_agent_names`     | instance     | `def get_agent_names(self) -> List[str]:`    | Returns a list of names of all loaded agents.                                                                                                                                                            |
| `get_available_agents` | instance    | `def get_available_agents(self) -> List[Agent]:` | Returns the list of currently loaded `Agent` instances.                                                                                                                                                 |
| `upsert_agent`        | instance     | `def upsert_agent(self, agent: Agent) -> None:` | Inserts or updates an agent in memory. Does not automatically save changes to the file.                                                                                                                |

## 10. Usage Examples
```python
from src.agent import Agent, AgentManager

# Create an agent from a dictionary
agent_data = {
    "name": "ExampleAgent",
    "allowed_tools": ["tool1", "tool2"],
    "max_prompt_conversations": 5
}
agent = Agent.from_dict(agent_data)

# Manage agents with AgentManager
manager = AgentManager(path="./agents.json")
manager.upsert_agent(agent)
manager.save_agents()
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module is designed to be robust, allowing individual agent configurations to fail without affecting the loading of others. This is crucial for maintaining a smooth user experience.
- **Legacy Field Mapping**: The `Agent` class includes logic to map legacy field names to current ones, which is important for backward compatibility.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads attempt to load or save agents simultaneously.
- **Validation Logic**: The validation logic is forgiving in certain cases (e.g., coercing types), but strict in others (e.g., missing required fields).

## 12. Consumers
| Consumer              | What it uses                                   |
|-----------------------|------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |