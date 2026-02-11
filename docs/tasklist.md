---
tags:
  - tasklist
  - lucyproject
  - docs
  - documentation
  - tasklists
  - planning
  - python
---

# Task Lists Module (src/tasklists) — Quick Reference

Overview
- Domain models for tasks and task lists, plus a simple service boundary to create, load, save, and normalize TaskList objects.
- Core domain classes:
  - Task: a single task with id, name, instructions, state, result, and metadata.
  - TaskList: a collection of Task instances with lifecycle state and serialization helpers.
  - TaskListService: main service boundary handling creation, loading, saving, and normalization of TaskList objects.
- Supporting constants live in task_states.py (TASK_LIST_STATE_* and TASK_STATE_*) and are used by the domain models.

Core domain models (summary)
- Task
  - Fields: id, name, instructions, state, result, error, meta
  - Validation: _TaskModel (Pydantic) used for input validation
  - Serialization: to_dict, to_json; deserialization: from_dict, from_json
- TaskList
  - Fields: id, name, description, schema_version, state, tasks, meta, current_task_id
  - Validation: _TaskListModel (Pydantic) used for input validation
  - Serialization: to_dict, to_json; deserialization: from_dict, from_json
- TaskListService
  - Boundary for high-level operations: load, create, save, reset, and internal normalization
  - Normalization logic derives TaskList.state from contained Task states

Key source files (high level)
- src/tasklists/task_states.py
  - Purpose: Shared constants for task lists and tasks
  - Exposed constants (examples):
    - TASK_LIST_STATE_CREATED, TASK_LIST_STATE_RUNNING, TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_FAILED
    - TASK_STATE_PENDING, TASK_STATE_RUNNING, TASK_STATE_COMPLETED, TASK_STATE_COMPLETED_WITH_ERRORS, TASK_STATE_FAILED, TASK_STATE_BLOCKED
- src/tasklists/task.py
  - Purpose: Domain model for Task with validation and (de)serialization helpers
  - Key components:
    - _TaskModel: Pydantic model for validation (id, name, instructions, state, result, error, meta)
    - Task: domain object with fields id, name, instructions, state, result, error, meta
  - Main methods:
    - __init__(id, name, instructions="", state=TASK_STATE_PENDING, result=None, error=None, meta=None)
    - to_dict()
    - from_dict(data)
    - to_json()
    - from_json(s)
- src/tasklists/task_list.py
  - Purpose: Domain model for TaskList with serialization and basic in-memory behavior
  - Key elements:
    - _TaskListModel: Pydantic model for validation of TaskList dicts/maps
    - TaskList: domain object with fields id, name, description, schema_version, state, tasks, meta, current_task_id
  - Main methods:
    - task_list()
    - get_task(id)
    - next_id()
    - add_task(task)
    - update_task_state(id, new_state)
    - set_task_result(id, result, new_state=None, error=None)
    - to_dict()
    - from_dict(data, id=None)
    - to_json()
    - from_json(json_str)
- src/tasklists/service.py
  - Purpose: Main service boundary for TaskList operations (load, create, save, reset) and normalization logic
  - Class: TaskListService
    - load(path: str) -> TaskList
      - Reads JSON from path and returns a TaskList via TaskList.from_json
    - create(name: str, description: str, meta: Optional[Dict[str, Any]] = None) -> TaskList
      - Creates a new TaskList with a new UUID, schema_version 1, initial empty tasks, and provided meta
    - save(path: str, tasklist: TaskList) -> None
      - Normalizes the tasklist via _normalize then writes JSON via tasklist.to_json
    - reset(tasklist: TaskList) -> TaskList
      - Resets state: tasklist.state to Created, clears current_task_id, resets all tasks to Pending with no result/error
    - _normalize(tasklist: TaskList) -> None
      - Internal normalization logic to derive overall tasklist state from individual task states
        - If no tasks: state becomes Created
        - If any task is Failed or Completed_with_errors: state becomes Failed
        - If any task is Running: state becomes Running
        - If all tasks Completed: state becomes Completed
        - Otherwise (mixed or Pending), state defaults to Running
- src/tasklists/__init__.py
  - Purpose: Public surface for the tasklists package
  - Exports: TaskListService, Task, TaskList

Public API usage (quick reference)
- Create a new task list:
  - service = TaskListService()
  - tl = service.create(name="Test List", description="Sample list")
- Save to a file:
  - service.save("./path/to/tasklist.json", tl)
- Load from a file:
  - tl2 = service.load("./path/to/tasklist.json")
- Reset a task list:
  - tl_reset = service.reset(tl)

Normalization logic (high level)
- TaskListService._normalize(tasklist) derives the overall task list state from its tasks:
  - No tasks: Created
  - Any task in Failed or Completed_with_errors: Failed
  - Any task in Running: Running
  - All tasks Completed: Completed
  - Otherwise: Running

Notes
- Validation uses Pydantic models for incoming data (Task and TaskList).
- The module intentionally separates domain models from service orchestration.
- This page documents the current public surface; internal helper methods may evolve.

If you want, I can tailor this into a shorter one-page markdown or adjust the level of detail.
