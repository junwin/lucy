# Module Documentation for `src/tasklists`

## YAML Front Matter
```yaml
tags:
  - src_tasklists
  - lucyproject
  - Task
  - TaskList
  - TaskListService
```

## 1. Summary
The `src/tasklists` module provides a structured way to manage task lists and their associated tasks. It serves as a service layer that facilitates the creation, loading, saving, and resetting of task lists, encapsulating the logic for task management within a single service boundary. This module fits into a larger architecture that likely involves task processing or project management, solving the problem of organizing and tracking tasks through various states (e.g., created, running, completed).

## 2. Architecture & Design
The module employs several design patterns:
- **Service Layer**: The `TaskListService` class acts as a service layer, providing methods to manipulate task lists without exposing the underlying data structures directly.
- **Data Validation**: The use of Pydantic models (`_TaskModel` and `_TaskListModel`) ensures that data integrity is maintained when creating or manipulating tasks and task lists.
- **Composition**: The `TaskList` class is composed of multiple `Task` instances, allowing for a clear relationship between tasks and their parent task list.

There is no evident legacy or v2 split in the code, indicating that the module is likely in its initial version. Important design decisions include the use of UUIDs for task IDs and the strict validation of schema versions, which ensures backward compatibility and data integrity.

## 3. Key Classes
| Class               | Base/Parent | Purpose                                                                 |
|---------------------|-------------|-------------------------------------------------------------------------|
| Task                | None        | Represents an individual task with attributes like ID, name, and state. |
| TaskList            | None        | Represents a collection of tasks, managing their states and metadata.   |
| TaskListService     | None        | Provides methods for creating, loading, saving, and resetting task lists.|

## 4. Source Files
| File                          | Responsibility                                           | Notable Exports                     |
|-------------------------------|---------------------------------------------------------|-------------------------------------|
| `__init__.py`                 | Public surface for the tasklists module.               | `Task`, `TaskList`, `TaskListService` |
| `service.py`                  | Implements the `TaskListService` class.                | `TaskListService`                   |
| `task.py`                     | Defines the `Task` class and its data handling methods. | `Task`                               |
| `task_list.py`                | Defines the `TaskList` class and its data handling methods. | `TaskList`                           |
| `task_states.py`              | Contains shared constants for task and task list states. | None                                |

## 5. Dependencies
- **Standard library**:
  - `uuid`
  - `json`
  - `dataclasses`
  - `typing`
- **Third-party packages**:
  - `pydantic`
- **Internal modules**:
  - `src.tasklists.task`
  - `src.tasklists.task_states`
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
| Key                     | Type   | Default | What it controls                      |
|-------------------------|--------|---------|---------------------------------------|
| None                    | None   | None    | None                                  |

## 7. Exceptions
| Exception               | Base   | When Raised                                      |
|-------------------------|--------|-------------------------------------------------|
| None                    | None   | None                                            |

## 8. Module-Level Constants
| Constant                               | Value                          |
|----------------------------------------|--------------------------------|
| TASK_LIST_STATE_CREATED                | "Created"                     |
| TASK_LIST_STATE_RUNNING                | "Running"                     |
| TASK_LIST_STATE_COMPLETED              | "Completed"                   |
| TASK_LIST_STATE_FAILED                 | "Failed"                      |
| TASK_STATE_PENDING                     | "Pending"                     |
| TASK_STATE_RUNNING                     | "Running"                     |
| TASK_STATE_COMPLETED                   | "Completed"                   |
| TASK_STATE_COMPLETED_WITH_ERRORS       | "Completed (with errors)"     |
| TASK_STATE_FAILED                       | "Failed"                      |
| TASK_STATE_BLOCKED                     | "Blocked"                     |

## 9. Methods (by class)

### Task
| Method         | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|----------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`     | Instance     | `def __init__(self, id: Any, name: str, instructions: str = "", ...)` | Initializes a Task instance with the provided parameters, ensuring that the ID is a string and setting default values for state, result, error, meta, and agent.                                                                 |
| `to_dict`      | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the Task instance to a dictionary format for serialization.                                                                                                                                     |
| `from_dict`    | Class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task"`      | Validates input data using the Pydantic model and constructs a Task instance. Raises a ValueError if validation fails.                                                                                   |
| `to_json`      | Instance     | `def to_json(self) -> str`                                              | Serializes the Task instance to a JSON string.                                                                                                                                                            |
| `from_json`    | Class        | `@classmethod def from_json(cls, s: str) -> "Task"`                    | Deserializes a JSON string into a Task instance, raising a ValueError for invalid JSON.                                                                                                                 |

### TaskList
| Method                | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__post_init__`       | Instance     | `def __post_init__(self) -> None`                                        | Validates and normalizes the TaskList attributes after initialization, ensuring required fields are present and types are correct.                                                                         |
| `task_list`           | Instance     | `def task_list(self) -> Iterable[Task]`                                 | Returns an iterable of tasks contained in the TaskList.                                                                                                                                                   |
| `get_task`            | Instance     | `def get_task(self, id: str) -> Optional[Task]`                        | Retrieves a task by its ID, returning None if not found.                                                                                                                                                 |
| `next_id`             | Instance     | `def next_id(self) -> str`                                              | Generates a new UUID for a task ID.                                                                                                                                                                       |
| `add_task`            | Instance     | `def add_task(self, task: Task) -> None`                                | Adds a task to the TaskList, replacing it if a task with the same ID already exists.                                                                                                                    |
| `update_task_state`   | Instance     | `def update_task_state(self, id: str, new_state: str) -> None`         | Updates the state of a task identified by its ID.                                                                                                                                                         |
| `set_task_result`     | Instance     | `def set_task_result(self, id: str, result: Dict[str, Any], ...)`      | Sets the result and optionally the state and error for a task identified by its ID.                                                                                                                      |
| `to_dict`             | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Serializes the TaskList instance to a dictionary format for persistence.                                                                                                                                 |
| `from_dict`           | Class        | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList"` | Validates input data and constructs a TaskList instance, raising a ValueError if validation fails.                                                                                                       |
| `to_json`             | Instance     | `def to_json(self) -> str`                                              | Serializes the TaskList instance to a JSON string.                                                                                                                                                        |
| `from_json`           | Class        | `@classmethod def from_json(cls, json_str: str) -> "TaskList"`         | Deserializes a JSON string into a TaskList instance.                                                                                                                                                      |

### TaskListService
| Method         | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|----------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `load`         | Instance     | `def load(self, path: str) -> TaskList`                                 | Loads a TaskList from a JSON file, raising a FileNotFoundError if the file does not exist.                                                                                                             |
| `create`       | Instance     | `def create(self, name: str, description: str, ...) -> TaskList`       | Creates a new TaskList with the specified name and description, generating a unique ID and initializing the state to "Created".                                                                          |
| `save`         | Instance     | `def save(self, path: str, tasklist: TaskList) -> None`                | Normalizes the tasklist and saves it to a JSON file.                                                                                                                                                     |
| `reset`        | Instance     | `def reset(self, tasklist: TaskList) -> TaskList`                      | Resets the tasklist to its initial state, marking all tasks as pending and clearing results and errors.                                                                                                 |
| `_normalize`   | Instance     | `def _normalize(self, tasklist: TaskList) -> None`                     | Updates the state of the tasklist based on the states of its tasks, following specific rules for determining the overall state.                                                                          |

## 10. Usage Examples
```python
from src.tasklists import TaskListService

# Create a new TaskListService instance
service = TaskListService()

# Create a new task list
task_list = service.create(name="My Task List", description="A list of tasks to complete.")

# Save the task list to a file
service.save("my_task_list.json", task_list)

# Load the task list from a file
loaded_task_list = service.load("my_task_list.json")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising exceptions immediately when invalid data is encountered (e.g., invalid JSON, missing required fields).
- **Data Validation**: The use of Pydantic for validation ensures that only correctly structured data is accepted, but it may raise exceptions that need to be handled by the caller.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads are accessing or modifying task lists concurrently.
- **UUID Handling**: The module accepts flexible ID types but normalizes them to strings for consistency, which may lead to confusion if not documented properly.

## 12. Consumers
| Consumer               | What it uses                                      |
|-----------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |