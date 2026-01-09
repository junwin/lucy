---
tags:
  - tasklists
  - src.tasklists
  - Task
  - TaskList
  - TaskModel
  - TaskListModel
  - tasklist_boundary
---

# src.tasklists

Task list domain objects plus a strict boundary layer for validating and persisting tasklists inside `ContextState.data["tasklist"]`.

## What lives in this module now

### Domain (plain dataclasses, no persistence)

- `src/tasklists/task.py`
  - `Task`
    - Fields: `id: int`, `title: str`, `state: str`, `result: dict|None`, `error: str|None`, `meta: dict`

- `src/tasklists/task_list.py`
  - `TaskList`
    - Fields: `schema_version: int = 1`, `state: str`, `tasks_list: list[Task]`
    - Helpers: `tasks()`, `get_task(id)`, `next_id()`, `add_task(task)`, `update_task_state(id, new_state)`, `set_task_result(id, result, new_state=None, error=None)`

- `src/tasklists/task_states.py`
  - Constants for task list states and task states (e.g. `TASK_LIST_STATE_CREATED`, `TASK_STATE_PENDING`, etc.)

### Boundary (Pydantic validation + dict-only persistence)

- `src/tasklists/tasklist_boundary.py`
  - `TaskModel` (Pydantic)
    - `extra="forbid"`
    - Enforces:
      - `id` must be a real `int` (no numeric strings, no bool)
      - `result` must be `dict | None`
      - `meta` must be `dict`
  - `TaskListModel` (Pydantic)
    - `extra="forbid"`
    - Enforces:
      - `schema_version == 1`
      - task ids are unique
  - `load_tasklist(context: ContextState) -> TaskList | None`
    - Reads `context.data["tasklist"]`
    - Requires dict-only storage
    - Returns `None` if no tasklist is present
    - Raises `ValueError("Invalid tasklist in context: ...")` on validation errors
  - `save_tasklist(context: ContextState, tasklist: TaskList) -> None`
    - Writes a plain dict into `context.data["tasklist"]`

## Package exports

`src/tasklists/__init__.py` exports:

- Domain: `Task`, `TaskList`
- Boundary: `TaskModel`, `TaskListModel`, `load_tasklist`, `save_tasklist`

## Backward compatibility shims

These remain to reduce breakage for older imports, but are deprecated:

- `src/tasklists/tasklist_interface.py`
  - `AbstractTask`, `AbstractTaskList` Protocols (compatibility only)

- `src/tasklists/file_tasklist.py`
  - `FileTask` and `FileTaskList` are aliases to `Task` and `TaskList`
  - No file/JSON persistence remains here
