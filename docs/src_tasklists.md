# docs/tasklists.md

## YAML Front Matter
```yaml
tags:
  - tasklists
  - lucyproject
  - Task
  - TaskList
  - TaskListService
  - TasklistManager
```

## 1. Summary
The `tasklists` module provides a structured way to manage task lists and their associated tasks within a system. It serves as a CRUD (Create, Read, Update, Delete) facade over a persistence layer, allowing users to create, modify, and retrieve task lists and tasks efficiently. This module fits into a larger architecture that likely involves task management and execution, solving the problem of organizing and tracking tasks associated with various goals or projects.

## 2. Architecture & Design
The module employs several design patterns, including:

- **Abstract Base Class (ABC)**: The `TasklistManager` interface defines a contract for task list management, ensuring that any concrete implementation adheres to a specific API.
- **Dependency Injection**: The `TaskListService` class takes a `TasklistStore` as a dependency, allowing for flexible storage solutions without hardcoding any specific implementation.
- **Data Classes**: The `Task` and `TaskList` classes utilize Python's `dataclass` feature for clean and efficient data handling.

The classes are related through composition and inheritance. `TaskListService` implements the `TasklistManager` interface, while `TaskList` and `Task` are used as data models within the service. There is no explicit legacy or v2 split in the code, indicating a focus on maintaining a single, coherent design.

Important design decisions include the use of Pydantic for data validation in the `_TaskModel` and `_TaskListModel`, ensuring that data integrity is maintained throughout the application.

## 3. Key Classes
| Class               | Base/Parent        | Purpose                                           |
|---------------------|--------------------|---------------------------------------------------|
| Task                | None               | Represents a single task with its attributes.     |
| TaskList            | None               | Represents a collection of tasks and their state. |
| TaskListService     | TasklistManager     | Provides CRUD operations for task lists.          |
| TasklistManager     | ABC                | Abstract base class for task list management.     |

## 4. Source Files
| File                        | Responsibility                                      | Notable Exports                     |
|-----------------------------|----------------------------------------------------|-------------------------------------|
| `__init__.py`              | Public surface for the module                      | `Task`, `TaskList`, `TaskListService` |
| `interfaces.py`            | Defines the `TasklistManager` interface            | `TasklistManager`                   |
| `service.py`               | Implements the `TasklistManager` interface         | `TaskListService`                   |
| `task.py`                  | Defines the `Task` data model                      | `Task`                               |
| `task_list.py`             | Defines the `TaskList` data model                  | `TaskList`                           |
| `task_states.py`           | Defines shared constants for task and task list states | Constants for task states          |

## 5. Dependencies
- **Standard library**: `os`, `json`, `uuid`
- **Third-party packages**: `pydantic`
- **Internal modules**: `src.storage.interfaces` (imported in `service.py`)
- **Optional dependencies**: None

## 6. Configuration / Settings
None.

## 7. Exceptions
None.

## 8. Module-Level Constants
| Constant                        | Value                |
|---------------------------------|----------------------|
| TASK_LIST_STATE_CREATED         | "Created"            |
| TASK_LIST_STATE_RUNNING         | "Running"            |
| TASK_LIST_STATE_COMPLETED       | "Completed"          |
| TASK_LIST_STATE_FAILED          | "Failed"             |
| TASK_STATE_PENDING              | "Pending"            |
| TASK_STATE_RUNNING              | "Running"            |
| TASK_STATE_COMPLETED            | "Completed"          |
| TASK_STATE_COMPLETED_WITH_ERRORS| "Completed (with errors)" |
| TASK_STATE_FAILED               | "Failed"             |
| TASK_STATE_BLOCKED             | "Blocked"            |

## 9. Methods (by class)

### Task
| Method        | Type         | Signature                                                                 | Description                                                                 |
|---------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`    | Instance     | `def __init__(self, id: Any, name: str, instructions: str = "", ...)` | Initializes a Task instance with various attributes.                       |
| `to_dict`     | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the Task instance to a dictionary format for serialization.       |
| `from_dict`   | Class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task"`      | Creates a Task instance from a dictionary, validating the data.           |
| `to_json`     | Instance     | `def to_json(self) -> str`                                              | Serializes the Task instance to a JSON string.                            |
| `from_json`   | Class        | `@classmethod def from_json(cls, s: str) -> "Task"`                    | Creates a Task instance from a JSON string.                               |

### TaskList
| Method        | Type         | Signature                                                                 | Description                                                                 |
|---------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__post_init__` | Instance   | `def __post_init__(self) -> None`                                       | Validates and initializes the TaskList instance attributes.                |
| `task_list`   | Instance     | `def task_list(self) -> Iterable[Task]`                                 | Returns an iterable of tasks in the TaskList.                              |
| `get_task`    | Instance     | `def get_task(self, id: str) -> Optional[Task]`                        | Retrieves a task by its ID.                                                |
| `next_id`     | Instance     | `def next_id(self) -> str`                                              | Generates a new unique ID for a task.                                     |
| `add_task`    | Instance     | `def add_task(self, task: Task, *, after_index: Optional[int] = None) -> None` | Adds a task to the TaskList, optionally at a specified index.             |
| `update_task` | Instance     | `def update_task(self, id: str, **changes: Any) -> None`               | Updates an existing task's attributes.                                     |
| `remove_task` | Instance     | `def remove_task(self, id: str) -> None`                                | Removes a task from the TaskList by its ID.                               |
| `update_task_state` | Instance | `def update_task_state(self, id: str, new_state: str) -> None`       | Updates the state of a task.                                              |
| `set_task_result` | Instance | `def set_task_result(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None` | Sets the result of a task and optionally updates its state and error.     |
| `get_children` | Instance    | `def get_children(self, parent_id: str) -> List[Task]`                 | Returns all tasks whose parent_id matches the provided ID.                |
| `to_dict`     | Instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the TaskList instance to a dictionary format for serialization.   |
| `from_dict`   | Class       | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList"` | Creates a TaskList instance from a dictionary, validating the data.       |
| `to_json`     | Instance    | `def to_json(self) -> str`                                              | Serializes the TaskList instance to a JSON string.                        |
| `from_json`   | Class       | `@classmethod def from_json(cls, json_str: str) -> "TaskList"`        | Creates a TaskList instance from a JSON string.                           |

### TaskListService
| Method        | Type         | Signature                                                                 | Description                                                                 |
|---------------|--------------|---------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `__init__`    | Instance     | `def __init__(self, store: TasklistStore)`                             | Initializes the service with a storage interface.                          |
| `list`        | Instance     | `def list(self, account_name: str) -> List[str]`                       | Lists all task lists for a given account.                                   |
| `get`         | Instance     | `def get(self, account_name: str, tasklist_key: str) -> Optional[TaskList]` | Retrieves a specific task list by its key.                                 |
| `get_task_result` | Instance | `def get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict]` | Retrieves the result of a specific task.                                   |
| `save`        | Instance     | `def save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None` | Saves a task list to the storage.                                         |
| `delete`      | Instance     | `def delete(self, account_name: str, tasklist_key: str) -> None`      | Deletes a task list from the storage.                                      |
| `create`      | Instance     | `def create(self, tasklist_key: str, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Creates a new task list.                                                  |
| `create_from_goal` | Instance | `def create_from_goal(self, tasklist_key: str, goal: str, files: Optional[List[str]] = None, worker_agent: Optional[str] = None) -> TaskList` | Creates a task list from a specified goal.                                 |
| `add_task`    | Instance     | `def add_task(self, account_name: str, tasklist_key: str, *, task_id: str, task_name: str, task_instructions: str = "", ...) -> TaskList` | Adds a task to a task list.                                               |
| `update_task` | Instance     | `def update_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False, **changes: Any) -> TaskList` | Updates a task in a task list.                                            |
| `remove_task` | Instance     | `def remove_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False) -> TaskList` | Removes a task from a task list.                                          |
| `set_state`   | Instance     | `def set_state(self, account_name: str, tasklist_key: str, state: str, *, validate_only: bool = False) -> TaskList` | Sets the state of a task list.                                            |
| `set_name`    | Instance     | `def set_name(self, account_name: str, tasklist_key: str, name: str, *, validate_only: bool = False) -> TaskList` | Sets the name of a task list.                                             |
| `set_description` | Instance | `def set_description(self, account_name: str, tasklist_key: str, description: str, *, validate_only: bool = False) -> TaskList` | Sets the description of a task list.                                      |
| `set_general_instructions` | Instance | `def set_general_instructions(self, account_name: str, tasklist_key: str, instructions: str, *, validate_only: bool = False) -> TaskList` | Sets general instructions for a task list.                                 |
| `update_meta` | Instance     | `def update_meta(self, account_name: str, tasklist_key: str, meta: Dict[str, Any], *, validate_only: bool = False) -> TaskList` | Updates metadata for a task list.                                         |
| `_load_required` | Instance   | `def _load_required(self, account_name: str, tasklist_key: str) -> TaskList` | Loads a task list, raising an error if not found.                         |
| `reset`       | Instance     | `def reset(self, tasklist: TaskList) -> TaskList`                       | Resets a task list to its initial state.                                   |

## 10. Usage Examples
```python
from src.tasklists import TaskListService, TaskList

# Assuming `store` is an instance of TasklistStore
service = TaskListService(store)

# Create a new task list
task_list = service.create(tasklist_key="my-tasklist", name="My Tasks", description="A list of my tasks")

# Add a task to the task list
service.add_task(account_name="user1", tasklist_key="my-tasklist", task_id="task-1", task_name="First Task", task_instructions="Do the first task")
```

## 11. Edge Cases & Gotchas
- **Error Handling**: The module employs a fail-fast approach, raising exceptions when invalid data is encountered (e.g., invalid task IDs, missing required fields).
- **Validation**: The use of Pydantic ensures that data is validated before being processed, which helps maintain data integrity.
- **Thread Safety**: The module does not explicitly address thread safety, which may be a concern if multiple threads access the same task lists concurrently.
- **Known Limitations**: The current implementation does not support complex querying or filtering of tasks beyond basic CRUD operations.

## 12. Consumers
| Consumer                | What it uses                                      |
|-------------------------|--------------------------------------------------|
| Unknown — trace imports to confirm. | Unknown — trace imports to confirm. |