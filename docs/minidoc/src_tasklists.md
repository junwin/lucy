```markdown
---
tags:
  - tasklists
  - lucyproject
  - Task
  - TaskList
  - TaskListService
  - TASK_LIST_STATE_CREATED
  - TASK_LIST_STATE_RUNNING
  - TASK_LIST_STATE_COMPLETED
  - TASK_LIST_STATE_FAILED
  - TASK_STATE_PENDING
  - TASK_STATE_RUNNING
  - TASK_STATE_COMPLETED
  - TASK_STATE_COMPLETED_WITH_ERRORS
  - TASK_STATE_FAILED
  - TASK_STATE_BLOCKED
---

## 1. Summary
The `tasklists` module provides a framework for managing task lists and their associated tasks. It includes functionality for creating, loading, saving, and resetting task lists, as well as managing the state of individual tasks. This module is designed to facilitate in-memory operations, making it easier to handle task management without immediate concerns for persistence.

## 2. Key Classes

| Class               | Base/Parent | Purpose                                                                 |
|---------------------|--------------|-------------------------------------------------------------------------|
| Task                | None         | Represents an individual task with attributes like state and result.    |
| TaskList            | None         | Represents a collection of tasks, managing their states and metadata.   |
| TaskListService     | None         | Provides methods for creating, loading, saving, and resetting task lists.|

## 3. Source Files

| File                     | Responsibility                                         | Notable Exports                     |
|--------------------------|-------------------------------------------------------|-------------------------------------|
| `__init__.py`           | Public surface for the tasklists module.              | Task, TaskList, TaskListService     |
| `service.py`            | Implements TaskListService for task list operations.  | TaskListService                     |
| `task.py`               | Defines the Task class and its serialization methods.  | Task                                |
| `task_list.py`          | Defines the TaskList class and its methods.           | TaskList                            |
| `task_states.py`        | Contains constants for task and task list states.     | TASK_LIST_STATE_* and TASK_STATE_*  |

## 4. Dependencies

- **Standard library**
  - `uuid`
  - `json`
  - `typing`
  
- **Third-party packages**
  - `pydantic`
  
- **Internal modules**
  - `src.tasklists.task`
  - `src.tasklists.task_states`

## 5. Methods (by class)

### TaskListService

| Method   | Type         | Signature                                                                 | Description                                                                                      |
|----------|--------------|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| load     | instance     | `def load(self, path: str) -> TaskList`                                 | Loads a TaskList from a JSON file. Raises `FileNotFoundError` if the file does not exist.      |
| create   | instance     | `def create(self, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Creates a new TaskList with the specified name and description.                                 |
| save     | instance     | `def save(self, path: str, tasklist: TaskList) -> None`                | Normalizes and saves the TaskList to a JSON file.                                              |
| reset    | instance     | `def reset(self, tasklist: TaskList) -> TaskList`                       | Resets the task list to a fresh state.                                                          |
| _normalize | instance   | `def _normalize(self, tasklist: TaskList) -> None`                      | Updates the state of the task list based on the states of its tasks.                           |

### Task

| Method      | Type         | Signature                                                                 | Description                                                                                      |
|-------------|--------------|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| to_dict     | instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the Task instance to a dictionary format.                                             |
| from_dict   | class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task"`      | Creates a Task instance from a dictionary, validating the data.                                |
| to_json     | instance     | `def to_json(self) -> str`                                              | Serializes the Task instance to a JSON string.                                                |
| from_json   | class        | `@classmethod def from_json(cls, s: str) -> "Task"`                    | Creates a Task instance from a JSON string.                                                    |

### TaskList

| Method              | Type         | Signature                                                                 | Description                                                                                      |
|---------------------|--------------|---------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| task_list           | instance     | `def task_list(self) -> Iterable[Task]`                                 | Returns an iterable of tasks in the TaskList.                                                  |
| get_task            | instance     | `def get_task(self, id: str) -> Optional[Task]`                        | Retrieves a task by its ID.                                                                      |
| next_id             | instance     | `def next_id(self) -> str`                                              | Generates a new unique ID for a task.                                                           |
| add_task            | instance     | `def add_task(self, task: Task) -> None`                                | Adds a task to the TaskList, replacing it if it already exists.                                 |
| update_task_state   | instance     | `def update_task_state(self, id: str, new_state: str) -> None`         | Updates the state of a task identified by its ID.                                              |
| set_task_result     | instance     | `def set_task_result(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None` | Sets the result and state of a task.                                                            |
| to_dict             | instance     | `def to_dict(self) -> Dict[str, Any]`                                   | Converts the TaskList instance to a dictionary format.                                         |
| from_dict           | class        | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList"` | Creates a TaskList instance from a dictionary, validating the data.                            |
| to_json             | instance     | `def to_json(self) -> str`                                              | Serializes the TaskList instance to a JSON string.                                            |
| from_json           | class        | `@classmethod def from_json(cls, json_str: str) -> "TaskList"`         | Creates a TaskList instance from a JSON string.                                               |
```