---
tags:
  - tasklistservice
  - dataclass
  - description
  - to_dict
  - from_dict
  - to_json
  - tasklistmodel
  - storage
  - module
  - boundary
  - src/tasklists
---

# Module: `src/tasklists`

## Key Classes

| Class | Type | File | Description |
|-------|------|------|-------------|
| `TaskListService` | Service | `service.py` | Single service boundary for create/load/save/reset operations on TaskList objects |
| `TaskList` | Dataclass | `task_list.py` | Persisted task list with id, name, description, schema_version, state, tasks, meta, current_task_id, general_instructions |
| `Task` | Dataclass | `task.py` | Single task with id, name, instructions, state, result, error, meta |
| `_TaskListModel` | Pydantic model | `task_list.py` | Validation model for TaskList (schema_version=1, extra=forbid) |
| `_TaskModel` | Pydantic model | `task.py` | Validation model for Task (extra=forbid) |

## Source Files

| File | Contents |
|------|----------|
| `src/tasklists/__init__.py` | Exports `Task`, `TaskList`, `TaskListService` |
| `src/tasklists/service.py` | `TaskListService` class |
| `src/tasklists/task_list.py` | `TaskList` dataclass + `_TaskListModel` Pydantic model |
| `src/tasklists/task.py` | `Task` dataclass + `_TaskModel` Pydantic model |
| `src/tasklists/task_states.py` | State constants (task list + task states) |

## Dependencies

### Internal consumers (import from this module)

| Consumer | What it uses |
|----------|-------------|
| `src/handlers/tasklists_manage_handler.py` | `TaskList`, `TASK_LIST_STATE_CREATED`, `TASK_STATE_PENDING` |
| `src/message_processors/automation_processor.py` | `Task`, `TaskList`, task states |
| `src/message_processors/task_running_processor.py` | `TASK_STATE_PENDING` |
| `src/storage/base.py` | `Task`, `TaskList` |
| `src/storage/json_file_storage.py` | `TaskList`, `Task`, `TaskListService` |

### External dependencies

- `pydantic` — `BaseModel`, `Field`, `field_validator`
- `json` — serialization/deserialization
- `uuid` — ID generation
- `dataclasses` — `@dataclass`, `field`
- `typing` — type hints

## Methods — Service / Base Class

### `TaskListService` (service boundary)

| Method | Signature | Description |
|--------|-----------|-------------|
| `load` | `(path: str) -> TaskList` | Load a TaskList from a JSON file path. Raises `FileNotFoundError`. |
| `create` | `(name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Create a new TaskList with a generated UUID, schema_version=1, state=Created, empty tasks. |
| `save` | `(path: str, tasklist: TaskList) -> None` | Normalize then save to a JSON file path. |
| `reset` | `(tasklist: TaskList) -> TaskList` | Mutate the tasklist back to Created/Pending state (clears current_task_id, resets all task states/results/errors). |
| `_normalize` | `(tasklist: TaskList) -> None` | Recompute tasklist.state from task states (private helper). |

### `TaskList` (domain dataclass)

| Method | Signature | Description |
|--------|-----------|-------------|
| `task_list` | `() -> Iterable[Task]` | Return all tasks as a list. |
| `get_task` | `(id: str) -> Optional[Task]` | Find a task by ID. |
| `next_id` | `() -> str` | Generate a new UUID string. |
| `add_task` | `(task: Task) -> None` | Add or replace a task by ID. |
| `update_task_state` | `(id: str, new_state: str) -> None` | Update a task's state by ID. |
| `set_task_result` | `(id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None` | Set a task's result, optional new state, optional error. |
| `to_dict` | `() -> Dict[str, Any]` | Serialize to dict (conditional fields: current_task_id, general_instructions). |
| `from_dict` | `(data: Dict[str, Any], id: Optional[str] = None) -> TaskList` | Deserialize from dict with Pydantic validation. |
| `to_json` | `() -> str` | Serialize to JSON string. |
| `from_json` | `(json_str: str) -> TaskList` | Deserialize from JSON string. |

### `Task` (domain dataclass)

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_dict` | `() -> Dict[str, Any]` | Serialize to dict. |
| `from_dict` | `(data: Dict[str, Any]) -> Task` | Deserialize from dict with Pydantic validation. |
| `to_json` | `() -> str` | Serialize to compact JSON string. |
| `from_json` | `(s: str) -> Task` | Deserialize from JSON string. |

### State Constants (`task_states.py`)

**Task list states:** `Created`, `Running`, `Completed`, `Failed`

**Task states:** `Pending`, `Running`, `Completed`, `Completed (with errors)`, `Failed`, `Blocked`
