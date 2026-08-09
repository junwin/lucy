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
The `src/agent` module is responsible for managing agent configurations within the Lucy project. It provides a robust framework for defining agents through the `Agent` dataclass, which includes features for loading configurations from JSON files, validating fields, and handling legacy field names. The module fits into the overall architecture by serving as a foundational component for agent management, allowing for the dynamic creation and manipulation of agent instances based on user-defined configurations. It solves the problem of ensuring that agent configurations are both flexible and resilient to errors, enabling developers to define agents with varying capabilities while maintaining backward compatibility.

## 2. Architecture & Design
The module employs several key design patterns:
- **Data Class Pattern**: The `Agent` class is implemented as a dataclass, which simplifies the creation of class instances and provides built-in methods for serialization.
- **Robust Loading Strategy**: The `AgentManager` class encapsulates the logic for loading and saving agents, ensuring that individual agent configurations are validated independently. This design allows for partial failures during loading, where malformed entries do not prevent the loading of valid agents.
- **Legacy Support**: The module includes mechanisms to handle legacy field names, allowing for backward compatibility with older configurations.

The `Agent` class is composed of various fields that define its behavior, while the `AgentManager` class manages a collection of `Agent` instances. The two classes interact closely, with `AgentManager` relying on the `Agent` class for instantiation and validation.

There is no explicit legacy/v2 split, but the handling of legacy field names indicates a design decision to maintain compatibility with previous versions of agent configurations.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| Agent         | None        | Represents an agent configuration with validation. |
| AgentManager   | None        | Manages loading, saving, and accessing agent definitions. |

## 4. Source Files
| File                        | Responsibility                                         | Notable Exports                |
|-----------------------------|-------------------------------------------------------|--------------------------------|
| `src/agent/__init__.py`    | Initializes the module and exports Agent and AgentManager. | Agent, AgentManager            |
| `src/agent/agent.py`       | Defines the Agent dataclass and its methods.         | Agent                          |
| `src/agent/agent_manager.py`| Manages the loading and saving of Agent instances.   | AgentManager                   |

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
| Key                     | Type    | Default               | What it controls                                   |
|-------------------------|---------|-----------------------|----------------------------------------------------|
| agents_path             | str     | "./agents.json"       | Path to the JSON file containing agent definitions. |
| strict_fields           | bool    | True                  | Controls whether unknown fields raise errors.      |

## 7. Exceptions
| Exception               | Base       | When Raised                                      |
|-------------------------|------------|--------------------------------------------------|
| None                    | None       | None                                             |

## 8. Module-Level Constants
| Constant                | Value      |
|-------------------------|------------|
| None                    | None       |

## 9. Methods (by class)

### Agent
| Method                  | Type         | Signature                                      | Description                                                                 |
|-------------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| _coerce_bool            | staticmethod | def _coerce_bool(value: Any) -> bool          | Coerces various types to a boolean value. Raises ValueError for invalid types. |
| _format_unknown_fields_message | staticmethod | def _format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str | Formats a message for unknown fields in agent configuration.               |
| from_dict               | staticmethod | def from_dict(data: Dict[str, Any], strict: bool = True) -> "Agent" | Creates an Agent from a dictionary, validating and coercing fields.       |
| to_dict                 | instance     | def to_dict(self) -> Dict[str, Any]          | Serializes the Agent instance to a dictionary suitable for JSON storage.   |
| allows_tool             | instance     | def allows_tool(self, tool_name: str) -> bool | Checks if a specific tool is allowed for this agent based on its configuration. |

### AgentManager
| Method                  | Type         | Signature                                      | Description                                                                 |
|-------------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| __init__                | instance     | def __init__(self, path: str = "./agents.json", strict_fields: bool = True) | Initializes the AgentManager with a path and strict field validation option. |
| get_agent               | instance     | def get_agent(self, name: str) -> Optional[Agent] | Retrieves an agent by name, returning None if not found.                  |
| is_valid                | instance     | def is_valid(self, name: str) -> bool        | Checks if an agent with the given name exists.                            |
| load_agents             | instance     | def load_agents(self, strict: Optional[bool] = None) -> None | Loads agents from the configured JSON file, validating each entry.        |
| save_agents             | instance     | def save_agents(self) -> None                 | Saves the current list of agents to the JSON file.                        |
| get_agent_names         | instance     | def get_agent_names(self) -> List[str]       | Returns a list of names of all loaded agents.                             |
| get_available_agents     | instance     | def get_available_agents(self) -> List[Agent] | Returns the list of all loaded agents.                                    |
| upsert_agent            | instance     | def upsert_agent(self, agent: Agent) -> None  | Inserts or updates an agent in memory without auto-saving.                |

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

# Manage agents using AgentManager
manager = AgentManager(path="./agents.json")
manager.upsert_agent(agent)
manager.save_agents()
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module is designed to be robust, allowing for partial failures during agent loading. Malformed entries are logged, and valid agents continue to load.
- **Legacy Field Mapping**: The handling of legacy field names allows for backward compatibility but may lead to confusion if users are unaware of the changes.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads access the `AgentManager` concurrently.
- **Validation Logic**: The validation logic for fields is forgiving, allowing for various input types but may lead to unexpected behavior if users provide incorrect types.

## 12. Consumers
| Consumer                | What it uses                                   |
|-------------------------|------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |