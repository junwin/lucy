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
The `src/agent` module is responsible for managing agent configurations within the Lucy project. It provides a robust framework for defining agents through the `Agent` dataclass, which includes features for loading configurations from JSON files, validating fields, and handling legacy field names. The module fits into the overall architecture by serving as a central point for agent management, allowing for the dynamic creation, retrieval, and storage of agent definitions. It solves the problem of ensuring that agent configurations are both flexible and resilient to errors, enabling developers to define agents with varying levels of strictness regarding their configuration.

## 2. Architecture & Design
The module employs several key design patterns:
- **Data Class Pattern**: The `Agent` class is implemented as a dataclass, which simplifies the creation of class instances and provides built-in methods for serialization.
- **Robust Loading Strategy**: The `AgentManager` class encapsulates the logic for loading and managing multiple agents, ensuring that the loading process is resilient to individual agent configuration errors.
- **Legacy Support**: The design includes backward compatibility for legacy field names, allowing for a smooth transition from older configurations to the new schema.

The `Agent` class is composed of various fields that define its behavior, while the `AgentManager` class manages a collection of `Agent` instances. The two classes interact closely, with `AgentManager` relying on the `Agent` class for creating and validating agent configurations. There is no explicit legacy/v2 split, but the handling of legacy fields indicates a design decision to maintain compatibility with older configurations.

## 3. Key Classes
| Class         | Base/Parent | Purpose                                           |
|---------------|-------------|---------------------------------------------------|
| Agent         | None        | Represents an agent configuration with validation.|
| AgentManager   | None        | Manages loading, saving, and accessing multiple agents. |

## 4. Source Files
| File                        | Responsibility                                      | Notable Exports            |
|-----------------------------|----------------------------------------------------|----------------------------|
| `src/agent/__init__.py`    | Initializes the module and exports Agent and AgentManager. | Agent, AgentManager        |
| `src/agent/agent.py`       | Defines the Agent dataclass and its methods.      | Agent                      |
| `src/agent/agent_manager.py`| Manages loading and saving of Agent instances.    | AgentManager               |

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
| Key                  | Type    | Default           | What it controls                          |
|----------------------|---------|-------------------|-------------------------------------------|
| agents_path          | str     | "./agents.json"   | Path to the JSON file storing agent definitions. |
| strict_fields        | bool    | True              | Determines if unknown fields raise errors during loading. |

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
| Method               | Type         | Signature                                      | Description                                                                 |
|----------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| from_dict            | @staticmethod| `from_dict(data: Dict[str, Any], strict: bool = True) -> Agent` | Creates an Agent from a dictionary, validating and coercing fields as necessary. Raises ValueError for missing required fields or unknown fields based on strictness. |
| to_dict              | instance     | `to_dict() -> Dict[str, Any]`                | Serializes the Agent instance to a dictionary suitable for JSON storage.    |
| allows_tool          | instance     | `allows_tool(tool_name: str) -> bool`        | Checks if a specific tool is allowed for this agent based on the allowed_tools field. |

### AgentManager
| Method               | Type         | Signature                                      | Description                                                                 |
|----------------------|--------------|------------------------------------------------|-----------------------------------------------------------------------------|
| load_agents          | instance     | `load_agents(strict: Optional[bool] = None) -> None` | Loads agents from the configured JSON file, validating each agent's configuration. |
| save_agents          | instance     | `save_agents() -> None`                       | Saves the current list of agents to the JSON file.                         |
| get_agent            | instance     | `get_agent(name: str) -> Optional[Agent]`    | Retrieves an agent by name, returning None if not found.                  |
| is_valid             | instance     | `is_valid(name: str) -> bool`                 | Checks if an agent with the given name exists.                            |
| get_agent_names      | instance     | `get_agent_names() -> List[str]`             | Returns a list of names of all loaded agents.                             |
| get_available_agents  | instance     | `get_available_agents() -> List[Agent]`      | Returns the list of currently loaded agents.                              |
| upsert_agent         | instance     | `upsert_agent(agent: Agent) -> None`         | Inserts or updates an agent in memory.                                    |
| remove_agent         | instance     | `remove_agent(name: str) -> bool`             | Removes an agent by name, returning True if successful.                   |

## 10. Usage Examples
```python
from src.agent import Agent, AgentManager

# Create an agent from a dictionary
agent_data = {
    "name": "ExampleAgent",
    "allowed_tools": ["tool1", "tool2"],
    "use_embeddings": True
}
agent = Agent.from_dict(agent_data)

# Manage agents using AgentManager
manager = AgentManager(path="./agents.json")
manager.upsert_agent(agent)
manager.save_agents()
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The `AgentManager` class is designed to be robust, allowing the loading of valid agents even if some configurations are malformed. This is crucial for maintaining operational continuity.
- **Legacy Field Mapping**: The handling of legacy fields (e.g., `select_type` to `context_type`) is a key feature that allows for backward compatibility, but it may lead to confusion if not documented properly.
- **Thread Safety**: The current implementation does not explicitly address thread safety, which may be a concern if multiple threads attempt to modify the agent list concurrently.
- **Validation Logic**: The validation logic in `from_dict` is forgiving, allowing for various input formats (e.g., string vs. list for `allowed_tools`), but this may lead to unexpected behavior if not carefully managed.

## 12. Consumers
| Consumer             | What it uses                                   |
|----------------------|------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |