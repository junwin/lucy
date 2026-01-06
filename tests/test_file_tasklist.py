import json
from pathlib import Path

from src.tasklists.file_tasklist import (
    FileTask as Task,
    FileTaskList as TaskList,
    save_tasklist_to_file,
    load_tasklist_from_file,
)
from src.tasklists.task_runner import PlannedTaskList
from src.tasklists.tasklist_interface import (
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
    TASK_STATE_COMPLETED,
)


def test_task_and_tasklist_to_from_dict_roundtrip():
    # Create tasks
    t1 = Task(task_id="t-001", description="Run unit tests for module A")
    t2 = Task(task_id="t-002", description="Summarise failures for module A")

    assert t1.state == TASK_STATE_PENDING
    assert t1.result is None

    # Create task list
    tl = TaskList(
        task_list_id="tl-001",
        state=TASK_LIST_STATE_CREATED,
        _title="Process test suite",
        _description="Run and summarise a list of tests",
        _tasks=[t1, t2],
    )

    # Convert to dict and back
    tl_dict = tl.to_dict()
    assert tl_dict["task_list_id"] == "tl-001"
    assert tl_dict["state"] == TASK_LIST_STATE_CREATED
    assert len(tl_dict["tasks"]) == 2

    tl2 = TaskList.from_dict(tl_dict)

    # Check basic fields survived
    assert tl2.task_list_id == "tl-001"
    assert tl2.state == TASK_LIST_STATE_CREATED
    assert tl2.title == "Process test suite"
    assert len(list(tl2.tasks())) == 2

    # Check first task
    t1_copy = list(tl2.tasks())[0]
    assert t1_copy.task_id == "t-001"
    assert t1_copy.description == "Run unit tests for module A"
    assert t1_copy.state == TASK_STATE_PENDING
    assert t1_copy.result is None


def test_tasklist_json_roundtrip_and_task_updates(tmp_path: Path):
    # Build a simple task list
    tl = TaskList(
        task_list_id="tl-002",
        state=TASK_LIST_STATE_CREATED,
        _title="Simple list",
        _tasks=[
            Task(task_id="t-001", description="First task"),
            Task(task_id="t-002", description="Second task"),
        ],
    )

    # Update list and tasks
    tl.state = TASK_LIST_STATE_RUNNING
    tl.update_task_state("t-001", TASK_STATE_RUNNING)
    tl.set_task_result("t-001", "OK: did the thing", new_state=TASK_STATE_COMPLETED)

    # Serialize to JSON
    json_str = tl.to_json()
    parsed = json.loads(json_str)
    assert parsed["task_list_id"] == "tl-002"
    assert parsed["state"] == TASK_LIST_STATE_RUNNING
    assert len(parsed["tasks"]) == 2

    # Deserialize from JSON
    tl2 = TaskList.from_json(json_str)

    assert tl2.task_list_id == "tl-002"
    assert tl2.state == TASK_LIST_STATE_RUNNING
    assert len(list(tl2.tasks())) == 2

    # Check task 1 state and result
    t1 = tl2.get_task("t-001")
    assert t1 is not None
    assert t1.state == TASK_STATE_COMPLETED
    assert t1.result == "OK: did the thing"

    # Task 2 should still be pending
    t2 = tl2.get_task("t-002")
    assert t2 is not None
    assert t2.state == TASK_STATE_PENDING
    assert t2.result is None

    # Also test file save/load helpers
    path = tmp_path / "tasklist.json"
    save_tasklist_to_file(tl2, str(path))
    assert path.exists()

    tl3 = load_tasklist_from_file(str(path))
    assert tl3.task_list_id == "tl-002"
    assert tl3.state == TASK_LIST_STATE_RUNNING
    assert tl3.get_task("t-001").result == "OK: did the thing"


def test_add_task_replaces_existing_by_id():
    tl = TaskList(task_list_id="tl-003")

    t1 = Task(task_id="t-001", description="Task one")
    tl.add_task(t1)

    assert len(list(tl.tasks())) == 1
    assert tl.get_task("t-001") is t1

    # Adding another task with the same id should replace the old one
    t1_replacement = Task(task_id="t-001", description="Task one (updated)")
    tl.add_task(t1_replacement)

    tasks = list(tl.tasks())
    assert len(tasks) == 1
    t1_after = tl.get_task("t-001")
    assert t1_after is t1_replacement
    assert t1_after.description == "Task one (updated)"


def test_from_planned_tasklist_maps_title_to_description_and_preserves_instruction():
    planned = PlannedTaskList.model_validate(
        {
            "kind": "tasklist",
            "description": "Do things",
            "tasks": [
                {
                    "id": "task-1",
                    "type": "task",
                    "title": "Work",
                    "agent": "colin",
                    "instruction": "Say hi",
                    "file": "src/a.py",
                    "params": {"x": 1},
                }
            ],
        }
    )

    tl = TaskList.from_planned_tasklist(planned, task_list_id="tl-100")
    assert tl.title == "Do things"

    t = tl.get_task("task-1")
    assert t is not None
    assert t.description == "Work"
    assert t.extra["instruction"] == "Say hi"
    assert t.extra["file"] == "src/a.py"
    assert t.extra["agent"] == "colin"
    assert t.extra["params"] == {"x": 1}
