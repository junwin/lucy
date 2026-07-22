# src/tasklists.md

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
The `src/tasklists` module provides a structured way to manage task lists and their associated tasks. It serves as a service layer that facilitates the creation, loading, saving, and resetting of task lists, encapsulating the logic for task state management. This module fits into a larger architecture that likely involves task management or workflow systems, solving the problem of organizing and tracking tasks through various states, from creation to completion.

## 2. Architecture & Design
The module employs several design patterns:
- **Service Layer**: The `TaskListService` class acts as a service boundary, managing operations related to task lists.
- **Data Model**: The `Task` and `TaskList` classes are designed as data models, utilizing Pydantic for validation and serialization.
- **Composition**: The `TaskList` class contains a list of `Task` instances, demonstrating a composition relationship.

There is no explicit legacy/v2 split noted in the code, indicating that the module is likely in its initial version. Important design decisions include the use of Pydantic for data validation, which ensures that task and task list data adhere to defined schemas, and the handling of task states through constants defined in `task_states.py`.

## 3. Key Classes
| Class               | Base/Parent | Purpose                                                                 |
|---------------------|--------------|-------------------------------------------------------------------------|
| Task                | None         | Represents an individual task with attributes and methods for validation.|
| TaskList            | None         | Represents a collection of tasks, managing their states and serialization.|
| TaskListService     | None         | Provides methods to create, load, save, and reset task lists.          |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                     |
|-----------------------------|---------------------------------------------------------|-------------------------------------|
| `__init__.py`              | Public surface for the tasklists module.               | `Task`, `TaskList`, `TaskListService` |
| `service.py`               | Implements the `TaskListService` class.                | `TaskListService`                   |
| `task.py`                  | Defines the `Task` class and its validation logic.     | `Task`                               |
| `task_list.py`             | Defines the `TaskList` class and its methods.          | `TaskList`                           |
| `task_states.py`           | Contains shared constants for task and task list states.| `TASK_LIST_STATE_*`, `TASK_STATE_*` |

## 5. Dependencies
- **Standard library**: `uuid`, `json`, `dataclasses`, `typing`
- **Third-party packages**: `pydantic`
- **Internal modules**: `src.tasklists.task`, `src.tasklists.task_states`
- **Optional dependencies**: None

## 6. Configuration / Settings
None.

## 7. Exceptions
None.

## 8. Module-Level Constants
| Constant                          | Value                          |
|-----------------------------------|--------------------------------|
| TASK_LIST_STATE_CREATED           | "Created"                      |
| TASK_LIST_STATE_RUNNING           | "Running"                      |
| TASK_LIST_STATE_COMPLETED         | "Completed"                    |
| TASK_LIST_STATE_FAILED            | "Failed"                       |
| TASK_STATE_PENDING                | "Pending"                      |
| TASK_STATE_RUNNING                | "Running"                      |
| TASK_STATE_COMPLETED              | "Completed"                    |
| TASK_STATE_COMPLETED_WITH_ERRORS  | "Completed (with errors)"     |
| TASK_STATE_FAILED                 | "Failed"                       |
| TASK_STATE_BLOCKED                | "Blocked"                      |

## 9. Methods (by class)

### Task
| Method         | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|----------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__init__`     | Instance     | `def __init__(self, id: Any, name: str, instructions: str = "", ...)` | Initializes a Task instance with provided attributes. Accepts flexible ID types and ensures that the state defaults to `TASK_STATE_PENDING`.                                                                 |
| `to_dict`      | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the Task instance to a dictionary format for serialization.                                                                                                                                       |
| `from_dict`    | Class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task"`      | Validates input data using Pydantic and constructs a Task instance. Raises `ValueError` if validation fails.                                                                                              |
| `to_json`      | Instance     | `def to_json(self) -> str`                                              | Serializes the Task instance to a JSON string.                                                                                                                                                             |
| `from_json`    | Class        | `@classmethod def from_json(cls, s: str) -> "Task"`                    | Deserializes a JSON string into a Task instance. Raises `ValueError` if the JSON is invalid.                                                                                                             |

### TaskList
| Method                | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|-----------------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `__post_init__`       | Instance     | `def __post_init__(self) -> None`                                        | Validates and normalizes attributes after initialization. Ensures required fields are present and types are correct.                                                                                     |
| `task_list`           | Instance     | `def task_list(self) -> Iterable[Task]`                                 | Returns an iterable of tasks in the task list.                                                                                                                                                             |
| `get_task`            | Instance     | `def get_task(self, id: str) -> Optional[Task]`                        | Retrieves a task by its ID. Returns `None` if the task is not found.                                                                                                                                     |
| `next_id`             | Instance     | `def next_id(self) -> str`                                              | Generates a new unique ID for a task.                                                                                                                                                                     |
| `add_task`            | Instance     | `def add_task(self, task: Task) -> None`                                | Adds a task to the task list, replacing it if a task with the same ID already exists.                                                                                                                    |
| `update_task_state`   | Instance     | `def update_task_state(self, id: str, new_state: str) -> None`        | Updates the state of a task identified by its ID.                                                                                                                                                         |
| `set_task_result`     | Instance     | `def set_task_result(self, id: str, result: Dict[str, Any], ...)`     | Sets the result and optionally the state and error for a task identified by its ID.                                                                                                                       |
| `to_dict`             | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Serializes the TaskList instance to a dictionary format for persistence.                                                                                                                                 |
| `from_dict`           | Class        | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList"` | Validates input data and constructs a TaskList instance. Raises `ValueError` if validation fails.                                                                                                        |
| `to_json`             | Instance     | `def to_json(self) -> str`                                              | Serializes the TaskList instance to a JSON string.                                                                                                                                                         |
| `from_json`           | Class        | `@classmethod def from_json(cls, json_str: str) -> "TaskList"`         | Deserializes a JSON string into a TaskList instance.                                                                                                                                                      |

### TaskListService
| Method         | Type         | Signature                                                                 | Description                                                                                                                                                                                                 |
|----------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `load`         | Instance     | `def load(self, path: str) -> TaskList`                                 | Loads a TaskList from a JSON file. Raises `FileNotFoundError` if the file does not exist.                                                                                                               |
| `create`       | Instance     | `def create(self, name: str, description: str, ...) -> TaskList`       | Creates a new TaskList with the specified name and description, initializing it to a created state.                                                                                                     |
| `save`         | Instance     | `def save(self, path: str, tasklist: TaskList) -> None`                | Normalizes and saves a TaskList to a JSON file.                                                                                                                                                          |
| `reset`        | Instance     | `def reset(self, tasklist: TaskList) -> TaskList`                      | Resets the task list to its initial state, marking all tasks as pending.                                                                                                                                 |
| `_normalize`   | Instance     | `def _normalize(self, tasklist: TaskList) -> None`                     | Updates the state of the task list based on the states of its tasks.                                                                                                                                     |

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
- **Error Handling**: The module employs a fail-fast approach, raising exceptions when invalid data is encountered during initialization or method calls.
- **Validation Logic**: The use of Pydantic for validation ensures that data adheres to expected formats, but it may raise exceptions that need to be handled by the caller.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if instances are shared across threads.
- **State Management**: The state management logic in `TaskListService` and `TaskList` is crucial; incorrect state transitions could lead to inconsistent task lists.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |