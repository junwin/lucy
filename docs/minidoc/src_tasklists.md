---
tags:
  - src_tasklists
  - lucyproject
  - TaskList
  - Task
  - TaskListService
  - task_states
  - schema_version
  - serialization
  - normalization
---

# Module: `src.tasklists`

## Summary

Domain model and service layer for task lists — the data structure behind Lucy's sequential task execution system. Defines `Task` and `TaskList` as Pydantic-validated dataclasses with JSON serialization, plus `TaskListService` for create/load/save/reset operations and state normalization.

## Key Classes

| Class | File | Purpose |
|---|---|---|
| `Task` | `task.py` | Single task unit — id, name, instructions, state, result, error, meta. Pydantic-validated dataclass with `to_dict`/`from_dict`/`to_json`/`from_json`. |
| `TaskList` | `task_list.py` | Ordered collection of tasks — id, name, description, schema_version, state, tasks, meta, current_task_id, general_instructions. Domain methods for task lookup, add, state updates, and full serialization. |
| `TaskListService` | `service.py` | Service boundary — `create()`, `load()` from file, `save()` to file, `reset()` to fresh state, and `_normalize()` to recompute tasklist state from task states. |

## Source Files

| File | Description |
|---|---|
| `__init__.py` | Package exports — `Task`, `TaskList`, `TaskListService`. |
| `task.py` | `Task` dataclass with Pydantic-backed validation (`_TaskModel`), dict/JSON serialization. |
| `task_list.py` | `TaskList` dataclass with Pydantic-backed validation (`_TaskListModel`), domain methods (`get_task`, `add_task`, `update_task_state`, `set_task_result`), and full serialization. |
| `service.py` | `TaskListService` — create, load, save, reset, and state normalization logic. |
| `task_states.py` | Plain string constants for all task and tasklist states (Created, Running, Completed, Failed, Pending, Blocked, etc.). |

## Dependencies

- **Standard library**: `json`, `uuid`, `dataclasses`, `typing`
- **Third-party**: `pydantic` (`BaseModel`, `Field`, `field_validator`)
- **Internal consumers**: `src.handlers.tasklists_manage_handler`, `src.handlers.tasklists_run_handler`, `src.message_processors.automation_processor`

## Methods — `TaskListService`

| Method | Type | Signature | Description |
|---|---|---|---|
| `load` | instance | `(path: str) -> TaskList` | Load a `TaskList` from a JSON file path. Raises `FileNotFoundError` if missing. |
| `create` | instance | `(name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Create a new empty `TaskList` with a fresh UUID and `Created` state. |
| `save` | instance | `(path: str, tasklist: TaskList) -> None` | Normalize then serialize to a JSON file path. |
| `reset` | instance | `(tasklist: TaskList) -> TaskList` | Reset tasklist to `Created` state, clear `current_task_id`, reset all tasks to `Pending` with no result/error. |
| `_normalize` | instance (private) | `(tasklist: TaskList) -> None` | Recompute `tasklist.state` from task states: any Failed → Failed, any Running → Running, all Completed → Completed, zero tasks → Created, else Running. |
