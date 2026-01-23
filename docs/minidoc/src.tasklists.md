---
tags:
  - tasklists
  - src.tasklists
  - Task
  - TaskList
  - task_states
---

# src.tasklists

Task list domain objects and shared state constants.

This minidoc reflects the current code in:

- `src/tasklists/task.py`
- `src/tasklists/task_list.py`
- `src/tasklists/task_states.py`

## Domain objects

### `src/tasklists/task.py`

#### `Task` (dataclass)
A single task/step in a task list.

Fields:

- `id: int`
- `title: str`
- `state: str = TASK_STATE_PENDING`
- `result: dict[str, Any] | None = None`
- `error: str | None = None`
- `meta: dict[str, Any] = {}`

Notes:

- This is a **domain object only** (no Pydantic).
- The docstring mentions a “boundary module” for validation/persistence, but that is **not part of the files covered by this minidoc**.

### `src/tasklists/task_list.py`

#### `TaskList` (dataclass)
A collection of `Task` objects plus a small amount of domain behavior.

Fields:

- `schema_version: int = 1`
- `state: str = TASK_LIST_STATE_CREATED`
- `tasks: list[Task] = []`

Domain helpers / behavior:

- `task_list() -> Iterable[Task]`
  - Returns a copy of the internal list (`list(self.tasks)`).
- `get_task(id: int) -> Task | None`
- `next_id() -> int`
  - Returns `1` if empty, else `max(id) + 1`.
- `add_task(task: Task) -> None`
  - Upserts by `task.id` (replaces existing task with same id, else appends).
- `update_task_state(id: int, new_state: str) -> None`
  - No-op if task id not found.
- `set_task_result(id: int, result: dict, *, new_state: str | None = None, error: str | None = None) -> None`
  - No-op if task id not found.
  - Sets `task.result`.
  - Sets `task.error` only if `error is not None`.
  - Sets `task.state` only if `new_state is not None`.

## Shared state constants

### `src/tasklists/task_states.py`

Task list states:

- `TASK_LIST_STATE_CREATED = "Created"`
- `TASK_LIST_STATE_RUNNING = "Running"`
- `TASK_LIST_STATE_COMPLETED = "Completed"`
- `TASK_LIST_STATE_FAILED = "Failed"`

Task states:

- `TASK_STATE_PENDING = "Pending"`
- `TASK_STATE_RUNNING = "Running"`
- `TASK_STATE_COMPLETED = "Completed"`
- `TASK_STATE_COMPLETED_WITH_ERRORS = "Completed (with errors)"`
- `TASK_STATE_FAILED = "Failed"`
- `TASK_STATE_BLOCKED = "Blocked"`

## Persistence

`TaskList` currently includes **simple JSON helpers**:

- `TaskList.to_json() -> str`
- `TaskList.from_json(json_str: str) -> TaskList`

These serialize/deserialize a structure like:

```json
{
  "schema_version": 1,
  "state": "Created",
  "tasks": [
    {
      "id": 1,
      "title": "Run pytest",
      "state": "Completed",
      "result": {"exit_code": 0},
      "error": null,
      "meta": {"command": "pytest"}
    }
  ]
}
```
