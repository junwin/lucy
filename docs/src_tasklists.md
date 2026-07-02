---
tags:
  - src_tasklists
  - lucyproject
  - Task
  - TaskList
  - TaskListService
  - _TaskModel
  - _TaskListModel
  - TASK_STATE_PENDING
  - TASK_STATE_RUNNING
  - TASK_STATE_COMPLETED
  - TASK_STATE_COMPLETED_WITH_ERRORS
  - TASK_STATE_FAILED
  - TASK_STATE_BLOCKED
  - TASK_LIST_STATE_CREATED
  - TASK_LIST_STATE_RUNNING
  - TASK_LIST_STATE_COMPLETED
  - TASK_LIST_STATE_FAILED
---

## 1. Summary

`src/tasklists` is the domain model and service layer for the Lucy tasklist feature. It defines:

- **`Task`** — a single unit of work with id, name, instructions, state, result, error, and meta.
- **`TaskList`** — an ordered collection of `Task` objects with its own lifecycle state, metadata, and persistence (JSON round-trip).
- **`TaskListService`** — the single boundary for creation, loading, saving, resetting, and state-normalisation of `TaskList` objects. Currently in-memory only (no persistence path decisions embedded — that's deferred to storage).
- **`task_states.py`** — shared vocabulary constants for task-level and tasklist-level states (no persistence concerns).

The module is the "source of truth" for what a tasklist looks like and how it behaves. Storage and handler layers consume it; they do not re-implement tasklist logic.


## 2. Architecture & Design

### Data + behaviour split

`Task` and `TaskList` are `@dataclass` classes with both data fields and domain methods (`add_task`, `get_task`, `update_task_state`, `set_task_result`, `to_dict`/`from_dict`, `to_json`/`from_json`). They are **not** anemic models — they carry behaviour.

### Pydantic validation layer (private models)

Each domain dataclass has a private **Pydantic BaseModel** counterpart used only during deserialisation:

| Domain class | Pydantic model | Purpose |
|---|---|---|
| `Task` | `_TaskModel` | Strict validation of task JSON (`extra = "forbid"`) |
| `TaskList` | `_TaskListModel` | Strict validation of tasklist JSON (`schema_version` enforced to `1`, `extra = "forbid"`) |

`from_dict()` routes through `_TaskModel.model_validate()` / `_TaskListModel.model_validate()` before constructing the dataclass. This ensures that invalid payloads are rejected with clear `ValueError` messages.

### `__init__` is hand-written (not generated)

Both `Task` and `TaskList` use `@dataclass(init=False)` and a manually written `__init__`. This gives them:
- Flexible id coercion (`str(id)`)
- Defensive `None` → sensible-default conversions for `tasks`, `meta`, `general_instructions`
- Early `ValueError`/`TypeError` for schema_version checks and required fields (`name`, `description`)

### Service layer (`TaskListService`)

A single-coordination object that:
- Creates tasklists with a fresh UUID, valid state, and empty task list
- Loads/saves from JSON via `TaskList.from_json`/`.to_json`
- **Normalises** the tasklist aggregate state (`_normalize`) by inspecting individual task states — the aggregate state is derived, not independently settable
- Resets a tasklist back to `Created`/`Pending`

### State constants as plain strings

`task_states.py` defines **11 plain string constants**. These are not an enum. Rationale (from comments): "intentionally plain constants with no persistence concerns." This avoids coupling serialisation to a Python enum while still giving the codebase a shared vocabulary.

### No persistent storage decisions in this module

`TaskListService.load()` and `.save()` accept a file path string. The caller (storage layer or handler) decides where that path points. The service is intentionally agnostic about directory layout, file naming conventions, and storage backends.


## 3. Key Classes

| Class | Base/Parent | Purpose |
|---|---|---|
| `Task` | `@dataclass` | Single unit of work — id, name, instructions, state, result, error, meta. Serialises to/from JSON. |
| `_TaskModel` | `pydantic.BaseModel` | Private Pydantic model for strict validation of `Task` JSON payloads on deserialisation. |
| `TaskList` | `@dataclass` | Ordered collection of `Task` objects with aggregate lifecycle state, instructions, metadata. Full JSON round-trip via Pydantic validation. |
| `_TaskListModel` | `pydantic.BaseModel` | Private Pydantic model for strict validation of `TaskList` JSON, enforces `schema_version == 1`. |
| `TaskListService` | (plain class) | Single boundary for create/load/save/reset/normalise operations on `TaskList`. In-memory only. |


## 4. Source Files

| File | Responsibility | Notable Exports |
|---|---|---|
| `__init__.py` | Public surface — re-exports the three public classes | `Task`, `TaskList`, `TaskListService` |
| `task.py` | `Task` domain dataclass + `_TaskModel` Pydantic validator | `Task`, `_TaskModel` |
| `task_list.py` | `TaskList` domain dataclass + `_TaskListModel` Pydantic validator | `TaskList`, `_TaskListModel` |
| `service.py` | `TaskListService` — creation, I/O, reset, aggregate state normalisation | `TaskListService` |
| `task_states.py` | Shared string constants for all task/tasklist states | 4 tasklist-state constants + 6 task-state constants |


## 5. Dependencies

### Standard library
- `__future__.annotations`
- `dataclasses` (`dataclass`, `field`)
- `json`
- `uuid`
- `typing` (`Any`, `Dict`, `Iterable`, `List`, `Optional`)

### Third-party packages
- **pydantic** (`BaseModel`, `Field`, `field_validator`) — validation of JSON payloads during deserialisation

### Internal modules
- `.task` (from `task_list.py`) — `Task`, `_TaskModel`
- `.task_states` (from `task.py`, `task_list.py`, `service.py`) — all state constants
- `.task_list` (from `service.py`) — `TaskList`

### Optional dependencies
None.


## 6. Configuration / Settings

None. This module reads no `ConfigManager` keys, no env vars, no file-based configuration. All parameters are passed explicitly by callers.


## 7. Exceptions

None — no custom exception classes are defined. The module raises standard exceptions:

| What | Exception | When |
|---|---|---|
| Missing required fields | `ValueError` | `TaskList.__post_init__` when `name` or `description` is empty |
| Wrong schema version | `ValueError` | `TaskList.__post_init__` when `schema_version != 1` |
| Wrong types | `TypeError` | `TaskList.__post_init__` when `meta` is not a dict, `tasks` is not a list, `general_instructions` is not a str, or `schema_version` cannot be cast to int |
| Validation failure | `ValueError` | `Task.from_dict` / `TaskList.from_dict` when Pydantic validation of the payload fails; `Task.from_json` when the string is not valid JSON |
| Missing file | `FileNotFoundError` | `TaskListService.load()` when the file path does not exist |
| Serialisation with empty id | `ValueError` | `TaskList.to_dict()` when `id` is falsy |
| Non-dict input | `TypeError` | `Task.from_dict` / `TaskList.from_dict` when argument is not a `dict` |


## 8. Module-Level Constants

All defined in `task_states.py`:

### Task list states
| Constant | Value |
|---|---|
| `TASK_LIST_STATE_CREATED` | `"Created"` |
| `TASK_LIST_STATE_RUNNING` | `"Running"` |
| `TASK_LIST_STATE_COMPLETED` | `"Completed"` |
| `TASK_LIST_STATE_FAILED` | `"Failed"` |

### Task states
| Constant | Value |
|---|---|
| `TASK_STATE_PENDING` | `"Pending"` |
| `TASK_STATE_RUNNING` | `"Running"` |
| `TASK_STATE_COMPLETED` | `"Completed"` |
| `TASK_STATE_COMPLETED_WITH_ERRORS` | `"Completed (with errors)"` |
| `TASK_STATE_FAILED` | `"Failed"` |
| `TASK_STATE_BLOCKED` | `"Blocked"` |


## 9. Methods (by class)

### `Task`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__init__` | instance | `(self, id: Any, name: str, instructions: str = "", *, state: str = TASK_STATE_PENDING, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None` | Constructor. Coerces `id` to `str`. Accepts flexible id types (int, str, UUID). Defaults `state` to `"Pending"` if falsy. Defaults `meta` to `{}` if `None`. No validation beyond type coercion — validation happens in `from_dict` via Pydantic. |
| `to_dict` | instance | `(self) -> Dict[str, Any]` | Serialises the task to a plain dict. Always includes all 7 keys: `id`, `name`, `instructions`, `state`, `result`, `error`, `meta`. `meta` is always a dict (never `None`). |
| `from_dict` | classmethod | `(cls, data: Dict[str, Any]) -> Task` | Validates `data` via `_TaskModel.model_validate()`, then constructs a `Task` dataclass. Raises `TypeError` if `data` is not a dict. Raises `ValueError` if Pydantic validation fails (extra fields, wrong types). |
| `to_json` | instance | `(self) -> str` | Serialises to compact JSON string via `json.dumps(separators=(",", ":"))`. No indentation — compact format. |
| `from_json` | classmethod | `(cls, s: str) -> Task` | Parses JSON string, then delegates to `from_dict`. Raises `ValueError` if the string is not valid JSON. |

### `TaskList`

| Method | Type | Signature | Description |
|---|---|---|---|
| `__post_init__` | instance | `(self) -> None` | Post-init hook (runs after `@dataclass` `__init__`). Coerces `id` and `current_task_id` to `str`. Enforces `schema_version == 1` (raises `ValueError`/`TypeError`). Validates `name` and `description` are non-empty. Normalises `meta`→`{}`, `tasks`→`[]`, `general_instructions`→`""` on `None`. |
| `task_list` | instance | `(self) -> Iterable[Task]` | Returns a **copy** of the internal `tasks` list (`list(self.tasks)`). Safe for iteration while the original may be mutated. |
| `get_task` | instance | `(self, id: str) -> Optional[Task]` | Linear search by `id` (string comparison). Returns `None` if not found. |
| `next_id` | instance | `(self) -> str` | Returns a fresh UUID4 as a string. Does **not** mutate state — callers assign the result to a new `Task`. |
| `add_task` | instance | `(self, task: Task) -> None` | Adds a new task or **replaces** an existing one at the same index if `task.id` matches an existing task's id. Otherwise appends to the end. |
| `update_task_state` | instance | `(self, id: str, new_state: str) -> None` | Finds a task by id and sets its `state` in-place. No-op if id not found. No validation that `new_state` is a known state constant. |
| `set_task_result` | instance | `(self, id: str, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> None` | Sets `result` on a task by id. Optionally updates `state` and/or `error`. No-op if id not found. |
| `to_dict` | instance | `(self) -> Dict[str, Any]` | Serialises to a dict. Raises `ValueError` if `id` is falsy. Omits `current_task_id` key when `None`. Omits `general_instructions` key when empty (backward compatibility). Delegates to `task.to_dict()` for each task. |
| `from_dict` | classmethod | `(cls, data: Dict[str, Any], id: Optional[str] = None) -> TaskList` | Validates via `_TaskListModel.model_validate()`, then constructs a `TaskList`. Optional `id` override merges into payload if missing. Raises `TypeError` if `data` is not a dict. Raises `ValueError` if Pydantic validation fails. |
| `to_json` | instance | `(self) -> str` | Serialises to pretty-printed JSON with `indent=2`. |
| `from_json` | classmethod | `(cls, json_str: str) -> TaskList` | Parses JSON string via `json.loads()`, then delegates to `from_dict`. No explicit `JSONDecodeError` handling — lets it propagate. |

### `TaskListService`

| Method | Type | Signature | Description |
|---|---|---|---|
| `load` | instance | `(self, path: str) -> TaskList` | Opens `path`, reads content, delegates to `TaskList.from_json()`. Raises `FileNotFoundError` if file doesn't exist. No error handling for malformed JSON — lets it propagate. |
| `create` | instance | `(self, name: str, description: str, *, meta: Optional[Dict[str, Any]] = None, general_instructions: str = "") -> TaskList` | Creates a new `TaskList` with a fresh UUID4, `schema_version=1`, `state="Created"`, empty tasks list, and the given name/description. Optional `meta` dict (defaults to `{}`). Optional `general_instructions` (defaults to `""`). |
| `save` | instance | `(self, path: str, tasklist: TaskList) -> None` | Calls `_normalize(tasklist)`, then writes `tasklist.to_json()` to `path`. Normalisation is always applied before save — callers cannot opt out. |
| `reset` | instance | `(self, tasklist: TaskList) -> TaskList` | **Mutates in-place**: sets `tasklist.state = "Created"`, clears `current_task_id`, sets every task state to `"Pending"`, clears every task's `result` and `error`. Returns the same `TaskList` object. |
| `_normalize` | instance | `(self, tasklist: TaskList) -> None` | **Private.** Recomputes `tasklist.state` from task states. Rules (per John): **(1)** any task Failed or Completed-with-errors → `Failed`; **(2)** any task Running → `Running`; **(3)** all tasks Completed → `Completed`; **(4)** zero tasks → `Created`; **(5)** any other mix (e.g. Completed + Pending) → `Running`. |

### `_TaskModel` (private)

| Method | Type | Signature | Description |
|---|---|---|---|
| (model_config) | class-level | `{"extra": "forbid"}` | Rejects any JSON keys not declared in the model. |

### `_TaskListModel` (private)

| Method | Type | Signature | Description |
|---|---|---|---|
| `check_schema_version` | classmethod / `@field_validator("schema_version")` | `(cls, v) -> int` | Validates that `schema_version` can be cast to `int` and equals `1`. Raises `ValueError` otherwise. |
| (model_config) | class-level | `{"extra": "forbid"}` | Rejects any JSON keys not declared in the model. |


## 10. Usage Examples

### Create a tasklist, add tasks, save

```python
from src.tasklists import Task, TaskList, TaskListService

svc = TaskListService()
tl = svc.create("Deploy release", "Steps to deploy v2.1")

tl.add_task(Task(id=tl.next_id(), name="Run tests", instructions="pytest"))
tl.add_task(Task(id=tl.next_id(), name="Build image", instructions="docker build ."))

svc.save("/tmp/my_tasks.json", tl)
```

### Load and mutate

```python
tl = svc.load("/tmp/my_tasks.json")
tl.update_task_state(tl.tasks[0].id, "Completed")
tl.tasks[1].state = "Running"
svc.save("/tmp/my_tasks.json", tl)  # state normalised to "Running"
```


## 11. Edge Cases & Gotchas

1. **Aggregate state is derived, not stored.** `TaskList.state` is recomputed by `_normalize()` before every `save()`. If you set `tasklist.state = "Completed"` manually and then call `save()`, the normalisation will overwrite it based on actual task states. You cannot force an aggregate state that disagrees with task states.

2. **`reset()` mutates in-place.** It does not return a new `TaskList`. It modifies every task's state, result, and error, and returns `self`. This is intentional for simplicity, but callers should be aware it's destructive.

3. **`to_dict()` conditionally omits keys.** `current_task_id` is omitted when `None`. `general_instructions` is omitted when empty (falsy). This is for backward compatibility with older JSON that lacks these fields. However it means `to_dict()` output shape can differ between two `TaskList` objects.

4. **`add_task` replaces by id.** If you call `add_task` with a `Task` whose `id` already exists in the list, it silently replaces the existing task at the same index rather than appending a duplicate or raising an error. This is by design for idempotent updates.

5. **No task ordering beyond list position.** Tasks are stored in a plain `list`. There is no `order` field or explicit sorting. Order is insertion order, modified by `add_task` replacement (which preserves index).

6. **Flexible id types at construction; strict strings in storage.** `Task.__init__` and `TaskList.__post_init__` accept `int`, `str`, or `UUID` and coerce to `str`. But `_TaskModel` and `_TaskListModel` expect `str` — so JSON round-tripped data must have string ids. A `from_dict` call with `{"id": 42}` will fail Pydantic validation.

7. **`TaskList.from_dict` has an `id` override parameter.** When an `id` keyword argument is passed and the dict lacks an `"id"` key, the override is injected. This is used by storage to set the id from the filename. But if the dict already has an id, the override is silently ignored — there is no conflict detection.

8. **No validation of state string values.** `update_task_state` and `Task.__init__` accept any string as a state. The `_TaskModel` Pydantic model also has `state: Optional[str]` with no enum constraint. You can set `state = "Banana"` and nothing stops you. Only the `_normalize` method inspects states against the known constants; unknown states fall through to the final "Running" catch-all.

9. **`_normalize` catch-all makes any unknown mix → Running.** If tasks have states that don't match any known constant (due to the gotcha above), the catch-all on the final line produces `TASK_LIST_STATE_RUNNING`. This may be surprising.

10. **`TaskListService.save()` always normalises.** There is no "save raw" option. If a caller wants to preserve the current `tasklist.state` without recomputation, they must use `tasklist.to_json()` directly and handle file I/O themselves.

11. **Not thread-safe.** There is no locking in `TaskList` or `TaskListService`. Concurrent mutation of the same `TaskList` object will cause races.

12. **`task_list()` returns a copy, but tasks are mutable.** `list(self.tasks)` returns a new list but each `Task` inside it is the same object. Mutating a task's state through the returned list affects the original `TaskList`.

13. **No JSON error handling in `load()`.** If the file contains malformed JSON, the `JSONDecodeError` propagates directly to the caller without wrapping.

14. **`Task.to_json` is compact; `TaskList.to_json` is pretty-printed.** Inconsistent formatting between the two classes. Task uses `separators=(",", ":")` (no spaces, no newlines); TaskList uses `indent=2`.

15. **`general_instructions` defaults to `""` in `create()` but omitted in `to_dict()` when falsy.** Newly created tasklists have `general_instructions=""`, which means `to_dict()` will omit the key — so the saved JSON won't contain it. On reload, `from_dict` will default it to `""`. This is consistent, but means the key appears/disappears from JSON based on whether it was ever set.


## 12. Consumers

| Consumer | What it uses |
|---|---|
| `src/storage/base.py` | `Task`, `TaskList` (type annotations on abstract methods) |
| `src/storage/json_file_storage.py` | `TaskList`, `Task` (domain objects for CRUD), `TaskListService` (load/save/reset) |
| `src/message_processors/automation_processor.py` | `Task`, `TaskList`, `TASK_STATE_COMPLETED`, `TASK_STATE_FAILED`, `TASK_STATE_PENDING`, `TASK_STATE_RUNNING`, `TASK_LIST_STATE_COMPLETED`, `TASK_LIST_STATE_CREATED`, `TASK_LIST_STATE_FAILED`, `TASK_LIST_STATE_RUNNING` (executing tasklists) |
| `src/message_processors/task_running_processor.py` | `TASK_STATE_PENDING` (checking task state) |
| `src/handlers/tasklists_manage_handler.py` | `Task`, `TaskList`, `TASK_LIST_STATE_CREATED`, `TASK_STATE_PENDING` (CRUD handler for tasklists) |
| `src/handlers/tasklists_run_handler.py` | Indirect via `AutomationProcessor` (execution handler) |
| `tests/test_tasklists.py` | `Task`, `TaskList`, `TASK_STATE_PENDING` |
| `tests/test_tasklists_domain_bridge.py` | `Task`, `TaskList` |
| `tests/test_tasklists_storage.py` | `TaskList` |
| `tests/test_tasklists_manage_handler.py` | `TASK_LIST_STATE_CREATED`, `TASK_LIST_STATE_COMPLETED`, `TASK_STATE_PENDING`, `TASK_STATE_COMPLETED` |
| `tests/test_tasklists_run_handler.py` | Via `AutomationProcessor` invocation |
