# docs/tasklists.md

## YAML Front Matter
```yaml
tags:
  - tasklists
  - lucyproject
  - TaskList
  - Task
  - TaskListService
```

## 1. Summary
The `tasklists` module provides a structured way to manage task lists and their associated tasks within a system. It serves as a service layer that facilitates the creation, loading, saving, and resetting of task lists, while also managing the state of individual tasks. This module fits into a larger architecture that likely involves task execution and monitoring, solving the problem of organizing and tracking tasks in a coherent manner.

## 2. Architecture & Design
The module employs several design patterns, including:
- **Service Layer**: The `TaskListService` class acts as a service boundary, encapsulating the logic for task list management.
- **Data Model**: The `Task` and `TaskList` classes are designed as data models, utilizing Pydantic for validation and serialization.
- **Factory Method**: The `from_dict` and `from_json` methods in both `Task` and `TaskList` classes serve as factory methods for creating instances from various data formats.

The classes are related through composition, where `TaskList` contains multiple `Task` instances. The `TaskListService` interacts with these classes to perform operations, ensuring a clear separation of concerns. There is no evident legacy or v2 split in the code, indicating a focus on a single, cohesive implementation.

Important design decisions include:
- The use of Pydantic for data validation, which ensures that task and task list data adhere to defined schemas.
- The handling of task states through constants defined in `task_states.py`, promoting clarity and reducing the risk of errors.

## 3. Key Classes
| Class               | Base/Parent | Purpose                                                                 |
|---------------------|--------------|-------------------------------------------------------------------------|
| TaskListService     | None         | Manages the lifecycle of task lists, including creation, loading, and saving. |
| Task                | None         | Represents an individual task with its properties and behaviors.        |
| TaskList            | None         | Represents a collection of tasks, managing their states and relationships. |

## 4. Source Files
| File                        | Responsibility                                           | Notable Exports                     |
|-----------------------------|---------------------------------------------------------|-------------------------------------|
| `__init__.py`              | Public surface for the tasklists module.               | `Task`, `TaskList`, `TaskListService` |
| `service.py`               | Contains the `TaskListService` class.                  | `TaskListService`                   |
| `task.py`                  | Defines the `Task` class and its data model.           | `Task`                              |
| `task_list.py`             | Defines the `TaskList` class and its data model.      | `TaskList`                          |
| `task_states.py`           | Contains shared constants for task and task list states. | Various task state constants        |

## 5. Dependencies
- **Standard library**:
  - `uuid`
  - `json`
  - `typing`
- **Third-party packages**:
  - `pydantic`
- **Internal modules**:
  - `src.tasklists.task`
  - `src.tasklists.task_states`
- **Optional dependencies**:
  - None

## 6. Configuration / Settings
None.

## 7. Exceptions
None.

## 8. Module-Level Constants
| Constant                          | Value                      |
|-----------------------------------|----------------------------|
| TASK_LIST_STATE_CREATED           | "Created"                  |
| TASK_LIST_STATE_RUNNING           | "Running"                  |
| TASK_LIST_STATE_COMPLETED         | "Completed"                |
| TASK_LIST_STATE_FAILED            | "Failed"                   |
| TASK_STATE_PENDING                | "Pending"                  |
| TASK_STATE_RUNNING                | "Running"                  |
| TASK_STATE_COMPLETED              | "Completed"                |
| TASK_STATE_COMPLETED_WITH_ERRORS  | "Completed (with errors)"  |
| TASK_STATE_FAILED                 | "Failed"                   |
| TASK_STATE_BLOCKED                | "Blocked"                  |

## 9. Methods (by class)

### TaskListService
| Method   | Type         | Signature                                         | Description                                                                                                                                                                                                 |
|----------|--------------|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| load     | instance     | `def load(self, path: str) -> TaskList:`        | Loads a `TaskList` from a JSON file. Raises `FileNotFoundError` if the file does not exist.                                                                                                            |
| create   | instance     | `def create(self, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList:` | Creates a new `TaskList` with the specified name and description. Returns the created `TaskList`.                                                                                                       |
| save     | instance     | `def save(self, path: str, tasklist: TaskList) -> None:` | Normalizes and saves the `TaskList` to a JSON file.                                                                                                                                                      |
| reset    | instance     | `def reset(self, tasklist: TaskList) -> TaskList:` | Resets the `TaskList` to its initial state, mutating its tasks back to a fresh state.                                                                                                                  |
| _normalize | instance   | `def _normalize(self, tasklist: TaskList) -> None:` | Recomputes the state of the `TaskList` based on the states of its tasks.                                                                                                                                 |

### Task
| Method      | Type         | Signature                                         | Description                                                                                                                                                                                                 |
|-------------|--------------|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| to_dict     | instance     | `def to_dict(self) -> Dict[str, Any]:`         | Converts the `Task` instance to a dictionary representation.                                                                                                                                             |
| from_dict   | class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task":` | Creates a `Task` instance from a dictionary, validating the data using Pydantic. Raises `ValueError` for validation errors.                                                                              |
| to_json     | instance     | `def to_json(self) -> str:`                     | Serializes the `Task` instance to a JSON string.                                                                                                                                                         |
| from_json   | class        | `@classmethod def from_json(cls, s: str) -> "Task":` | Creates a `Task` instance from a JSON string. Raises `ValueError` for invalid JSON.                                                                                                                     |

### TaskList
| Method      | Type         | Signature                                         | Description                                                                                                                                                                                                 |
|-------------|--------------|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| task_list   | instance     | `def task_list(self) -> Iterable[Task]:`       | Returns an iterable of tasks in the `TaskList`.                                                                                                                                                          |
| get_task    | instance     | `def get_task(self, id: str) -> Optional[Task]:` | Retrieves a task by its ID. Returns `None` if not found.                                                                                                                                                 |
| next_id     | instance     | `def next_id(self) -> str:`                     | Generates a new unique ID for a task.                                                                                                                                                                    |
| add_task    | instance     | `def add_task(self, task: Task) -> None:`      | Adds a task to the `TaskList`, replacing it if a task with the same ID already exists.                                                                                                                  |
| update_task_state | instance | `def update_task_state(self, id: str, new_state: str) -> None:` | Updates the state of a task by its ID.                                                                                                                                                                   |
| set_task_result | instance | `def set_task_result(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None:` | Sets the result of a task and optionally updates its state and error.                                                                                                                                   |
| get_children | instance    | `def get_children(self, parent_id: str) -> List[Task]:` | Returns all tasks whose `parent_id` matches the provided ID.                                                                                                                                           |
| to_dict     | instance     | `def to_dict(self) -> Dict[str, Any]:`         | Converts the `TaskList` instance to a dictionary representation.                                                                                                                                         |
| from_dict   | class        | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList":` | Creates a `TaskList` instance from a dictionary, validating the data using Pydantic. Raises `ValueError` for validation errors.                                                                          |
| to_json     | instance     | `def to_json(self) -> str:`                     | Serializes the `TaskList` instance to a JSON string.                                                                                                                                                    |
| from_json   | class        | `@classmethod def from_json(cls, json_str: str) -> "TaskList":` | Creates a `TaskList` instance from a JSON string.                                                                                                                                                       |

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
- **Error Handling**: The module employs a fail-fast approach, raising exceptions for invalid states or data during initialization and method calls.
- **Data Validation**: The use of Pydantic ensures that data adheres to expected formats, but it may raise exceptions if the data is not structured correctly.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads interact with the same `TaskListService` instance.
- **State Management**: The state of tasks is managed through constants, which helps maintain consistency but requires careful handling to avoid invalid states.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |