---
tags:
  - json
  - module
  - serialization
  - to_dict
  - from_dict
  - to_json
  - from_json
  - doc
  - source
  - tasklistservice
  - boundary
  - creation
  - src/tasklists
---

# `src/tasklists`

## Source files
- `src/tasklists/__init__.py`
- `src/tasklists/service.py`
- `src/tasklists/task_list.py`
- `src/tasklists/task.py`
- `src/tasklists/task_states.py`

## Key classes
- **`TaskListService`** (`service.py`)
  - Service boundary for tasklist creation/load/save/reset.
  - Normalizes `TaskList.state` from task states.

- **`TaskList`** (`task_list.py`)
  - Domain model for a task list: `tasks`, `state`, `meta`, `current_task_id`, `general_instructions`.
  - Domain helpers: add/get tasks, update task state, set task result.
  - Persistence helpers: dict/JSON serialization.
  - Validation: Pydantic model `_TaskListModel` (extra fields forbidden, schema_version must be `1`).

- **`Task`** (`task.py`)
  - Domain model for a task: `id`, `name`, `instructions`, `state`, `result`, `error`, `meta`.
  - Persistence helpers: dict/JSON serialization.
  - Validation: Pydantic model `_TaskModel` (extra fields forbidden).

- **State constants** (`task_states.py`)
  - TaskList states: `Created`, `Running`, `Completed`, `Failed`
  - Task states: `Pending`, `Running`, `Completed`, `Completed (with errors)`, `Failed`, `Blocked`

## Dependencies
- **stdlib:** `json`, `uuid`, `dataclasses`, `typing`
- **third-party:** `pydantic`
- **internal:** `src.tasklists.task_states`

## Methods in the module service/base class
### `TaskListService`
- `load(path: str) -> TaskList`
- `create(name: str, description: str, *, meta: dict | None = None, general_instructions: str = "") -> TaskList`
- `save(path: str, tasklist: TaskList) -> None`
- `reset(tasklist: TaskList) -> TaskList`
- `_normalize(tasklist: TaskList) -> None`

### `TaskList`
- `__post_init__()`
- `task_list() -> Iterable[Task]`
- `get_task(id: str) -> Task | None`
- `next_id() -> str`
- `add_task(task: Task) -> None`
- `update_task_state(id: str, new_state: str) -> None`
- `set_task_result(id: str, result: dict, *, new_state: str | None = None, error: str | None = None) -> None`
- `to_dict() -> dict`
- `from_dict(data: dict, id: str | None = None) -> TaskList`
- `to_json() -> str`
- `from_json(json_str: str) -> TaskList`

### `Task`
- `__init__(id, name, instructions="", *, state="Pending", result=None, error=None, meta=None)`
- `to_dict() -> dict`
- `from_dict(data: dict) -> Task`
- `to_json() -> str`
- `from_json(s: str) -> Task`
