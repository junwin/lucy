```markdown
---
tags:
  - src_tasklists
  - lucyproject
  - Task
  - TaskList
  - TaskListService
  - TasklistManager
  - TASK_LIST_STATE_CREATED
  - TASK_STATE_PENDING
---

## 1. Summary
The `src/tasklists` module provides domain models and a CRUD service for managing task lists and their associated tasks. It facilitates the creation, retrieval, updating, and deletion of task lists, allowing users to manage tasks effectively within a structured framework.

## 2. Key Classes

| Class                | Base/Parent        | Purpose                                               |
|----------------------|--------------------|-------------------------------------------------------|
| Task                 | -                  | Represents an individual task with various attributes. |
| TaskList             | -                  | Represents a collection of tasks with metadata.       |
| TaskListService      | TasklistManager     | Provides CRUD operations for task lists.              |
| TasklistManager      | ABC                | Abstract base class for managing task lists.          |

## 3. Source Files

| File                     | Responsibility                                      | Notable Exports                     |
|--------------------------|----------------------------------------------------|-------------------------------------|
| `__init__.py`           | Public surface for the tasklists module            | Task, TaskList, TaskListService     |
| `interfaces.py`         | Defines the TasklistManager interface               | TasklistManager                     |
| `service.py`            | Implements TaskListService for CRUD operations     | TaskListService                     |
| `task.py`               | Defines the Task model and its methods              | Task                                |
| `task_list.py`          | Defines the TaskList model and its methods          | TaskList                            |
| `task_states.py`        | Contains shared constants for task and task list states | TASK_LIST_STATE_CREATED, TASK_STATE_PENDING |

## 4. Dependencies

- **Standard library**
  - `abc`
  - `json`
  - `os`
  - `uuid`
  - `dataclasses`
  - `typing`

- **Third-party packages**
  - `pydantic`

- **Internal modules**
  - `src.storage.interfaces`

## 5. Methods (by class)

### TaskListService

| Method                | Type         | Signature                                                                 | Description                                                                                     |
|-----------------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| list                  | instance     | `def list(self, account_name: str) -> List[str]`                       | Lists all task lists for a given account.                                                      |
| get                   | instance     | `def get(self, account_name: str, tasklist_key: str) -> Optional[TaskList]` | Retrieves a specific task list by account name and key.                                        |
| get_task_result       | instance     | `def get_task_result(self, account_name: str, tasklist_key: str, task_id: str) -> Optional[dict]` | Gets the result of a specific task in a task list.                                            |
| save                  | instance     | `def save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None` | Saves a task list to the store.                                                                 |
| delete                | instance     | `def delete(self, account_name: str, tasklist_key: str) -> None`      | Deletes a task list from the store.                                                             |
| create                | instance     | `def create(self, tasklist_key: str, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Creates a new task list.                                                                        |
| create_from_goal      | instance     | `def create_from_goal(self, tasklist_key: str, goal: str, files: Optional[List[str]] = None, worker_agent: Optional[str] = None) -> TaskList` | Creates a task list from a specified goal.                                                      |
| add_task              | instance     | `def add_task(self, account_name: str, tasklist_key: str, *, task_id: str, task_name: str, task_instructions: str = "", task_state: Optional[str] = None, task_agent: Optional[str] = None, task_meta: Optional[Dict[str, Any]] = None, task_position: Optional[int] = None, task_parent_id: Optional[str] = None, task_files: Optional[List[str]] = None, task_context: Optional[str] = None, after_index: Optional[int] = None, validate_only: bool = False) -> TaskList` | Adds a task to a task list.                                                                     |
| update_task           | instance     | `def update_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False, **changes: Any) -> TaskList` | Updates a task in a task list.                                                                  |
| remove_task           | instance     | `def remove_task(self, account_name: str, tasklist_key: str, task_id: str, *, validate_only: bool = False) -> TaskList` | Removes a task from a task list.                                                                |
| set_state             | instance     | `def set_state(self, account_name: str, tasklist_key: str, state: str, *, validate_only: bool = False) -> TaskList` | Sets the state of a task list.                                                                   |
| set_name              | instance     | `def set_name(self, account_name: str, tasklist_key: str, name: str, *, validate_only: bool = False) -> TaskList` | Sets the name of a task list.                                                                    |
| set_description       | instance     | `def set_description(self, account_name: str, tasklist_key: str, description: str, *, validate_only: bool = False) -> TaskList` | Sets the description of a task list.                                                             |
| set_general_instructions | instance   | `def set_general_instructions(self, account_name: str, tasklist_key: str, instructions: str, *, validate_only: bool = False) -> TaskList` | Sets general instructions for a task list.                                                      |
| update_meta           | instance     | `def update_meta(self, account_name: str, tasklist_key: str, meta: Dict[str, Any], *, validate_only: bool = False) -> TaskList` | Updates metadata for a task list.                                                                |
| reset                 | instance     | `def reset(self, tasklist: TaskList) -> TaskList`                       | Resets a task list to its initial state.                                                        |

### Task

| Method                | Type         | Signature                                                                 | Description                                                                                     |
|-----------------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| to_dict               | instance     | `def to_dict(self) -> Dict[str, Any]`                                  | Converts the task to a dictionary representation.                                              |
| from_dict             | class        | `@classmethod def from_dict(cls, data: Dict[str, Any]) -> "Task"`     | Creates a Task instance from a dictionary.                                                    |
| to_json               | instance     | `def to_json(self) -> str`                                             | Serializes the task to a JSON string.                                                         |
| from_json             | class        | `@classmethod def from_json(cls, s: str) -> "Task"`                   | Creates a Task instance from a JSON string.                                                  |

### TaskList

| Method                | Type         | Signature                                                                 | Description                                                                                     |
|-----------------------|--------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| task_list             | instance     | `def task_list(self) -> Iterable[Task]`                                | Returns an iterable of tasks in the task list.                                               |
| get_task              | instance     | `def get_task(self, id: str) -> Optional[Task]`                        | Retrieves a task by its ID.                                                                    |
| next_id               | instance     | `def next_id(self) -> str`                                             | Generates a new unique ID for a task.                                                         |
| add_task              | instance     | `def add_task(self, task: Task, *, after_index: Optional[int] = None) -> None` | Adds a task to the task list.                                                                  |
| update_task           | instance     | `def update_task(self, id: str, **changes: Any) -> None`              | Updates a task's attributes.                                                                   |
| remove_task           | instance     | `def remove_task(self, id: str) -> None`                               | Removes a task from the task list.                                                            |
| update_task_state     | instance     | `def update_task_state(self, id: str, new_state: str) -> None`       | Updates the state of a task.                                                                   |
| set_task_result       | instance     | `def set_task_result(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None` | Sets the result of a task.                                                                     |
| get_children          | instance     | `def get_children(self, parent_id: str) -> List[Task]`                | Returns all tasks whose parent_id matches the provided ID.                                    |
| to_dict               | instance     | `def to_dict(self) -> Dict[str, Any]`                                  | Converts the task list to a dictionary representation.                                        |
| from_dict             | class        | `@classmethod def from_dict(cls, data: Dict[str, Any], id: Optional[str] = None) -> "TaskList"` | Creates a TaskList instance from a dictionary.                                               |
| to_json               | instance     | `def to_json(self) -> str`                                             | Serializes the task list to a JSON string.                                                   |
| from_json             | class        | `@classmethod def from_json(cls, json_str: str) -> "TaskList"`       | Creates a TaskList instance from a JSON string.                                             |
```