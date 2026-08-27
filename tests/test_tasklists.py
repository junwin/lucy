import json
import uuid
from dataclasses import fields

from src.tasklists.service import TaskListService
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_STATE_COMPLETED,
    TASK_STATE_PENDING,
)


def test_task_unknown_key_rejection():
    data = {"id": str(uuid.uuid4()), "name": "T", "instructions": "Do something", "extra": "not-allowed"}
    try:
        Task.from_dict(data)
        assert False, "Expected ValueError for unknown keys"
    except ValueError as e:
        assert "Unknown Task fields" in str(e) or "validation" in str(e).lower()


def test_task_missing_required_fields():
    data = {"id": str(uuid.uuid4()), "name": "Only name"}
    try:
        Task.from_dict(data)
        assert False, "Expected ValueError for missing required fields"
    except ValueError as e:
        assert "Missing required Task field" in str(e) or "instructions" in str(e)


def test_migration_v1_title_and_int_id_converted():
    # legacy/v1 shapes are not supported by the strict loader; expect rejection
    v1 = {
        "schema_version": 1,
        "id": "tl-v1",
        "tasks": [{"id": 42, "title": "Old Task", "status": "pending"}],
    }

    try:
        TaskList.from_dict(v1)
        assert False, "Expected ValueError for invalid v1 task shape"
    except ValueError as e:
        assert "Unknown Task fields" in str(e) or "Unsupported TaskList" in str(e) or "validation" in str(e).lower()


def test_migration_v1_unknown_fields_moved_to_meta_when_allowed():
    # Legacy migration and allow_legacy_meta behavior has been removed; ensure v1 is rejected
    v1 = {
        "schema_version": 1,
        "id": "tl-v1b",
        "tasks": [{"id": 7, "title": "T", "status": "pending", "foo": "bar"}],
    }

    try:
        TaskList.from_dict(v1)
        assert False, "Expected ValueError for unsupported v1 shape"
    except ValueError:
        pass


def test_round_trip_dump_load():
    t1 = Task(id=str(uuid.uuid4()), name="First", instructions="First instr", state=TASK_STATE_PENDING)
    t2 = Task(id=str(uuid.uuid4()), name="Second", instructions="Second instr", state=TASK_STATE_PENDING)
    tl = TaskList(id="round-1", tasks=[t1, t2], meta={"a": 1}, name="demo", description="d")

    serialized = tl.to_dict()
    # Ensure serialization contains schema_version 1
    assert serialized.get("schema_version") == 1

    # Load back
    loaded = TaskList.from_dict(serialized)
    assert loaded.id == tl.id
    assert loaded.meta == tl.meta
    assert len(loaded.tasks) == 2
    # Tasks ids should be strings (UUIDs)
    for orig, new in zip(tl.tasks, loaded.tasks):
        assert isinstance(new.id, str)
        # should be parseable as UUID
        uuid.UUID(new.id)
        assert new.instructions == orig.instructions
        assert new.name == orig.name
        assert new.state == orig.state

    # Round-trip Json
    js = tl.to_json()
    loaded2 = TaskList.from_json(js)
    assert loaded2.id == tl.id
    assert len(loaded2.tasks) == 2


# -------------------------
# New tests for Task additions
# -------------------------


def test_task_creation_with_new_fields():
    tid = str(uuid.uuid4())
    t = Task(id=tid, name="T1", instructions="Do", position=5, files=["a.txt", "b.txt"], parent_id="parent-1")
    assert t.id == tid
    assert t.position == 5
    assert t.files == ["a.txt", "b.txt"]
    assert t.parent_id == "parent-1"


def test_task_defaults_for_new_fields():
    t = Task(id=str(uuid.uuid4()), name="T2", instructions="Do")
    assert t.position is None
    assert isinstance(t.files, list) and t.files == []
    assert t.parent_id is None


def test_task_to_dict_omits_none_and_empty_fields():
    t = Task(id=str(uuid.uuid4()), name="T3", instructions="Do")
    d = t.to_dict()
    assert "position" not in d
    assert "files" not in d
    assert "parent_id" not in d

    t2 = Task(id=str(uuid.uuid4()), name="T4", instructions="Do", position=0, files=["f"], parent_id="p")
    d2 = t2.to_dict()
    assert d2["position"] == 0
    assert d2["files"] == ["f"]
    assert d2["parent_id"] == "p"


def test_task_from_dict_with_missing_new_fields():
    data = {"id": str(uuid.uuid4()), "name": "T5", "instructions": "Do"}
    t = Task.from_dict(data)
    assert t.position is None
    assert t.files == []
    assert t.parent_id is None


def test_task_from_dict_with_all_new_fields_present():
    data = {
        "id": str(uuid.uuid4()),
        "name": "T6",
        "instructions": "Do",
        "position": 7,
        "files": ["x"],
        "parent_id": "p6",
    }
    t = Task.from_dict(data)
    assert t.position == 7
    assert t.files == ["x"]
    assert t.parent_id == "p6"


def test_task_full_round_trip_dict_task():
    t1 = Task(id=str(uuid.uuid4()), name="T7", instructions="Do", position=3, files=["z"], parent_id="par")
    d = t1.to_dict()
    t2 = Task.from_dict(d)
    assert t2.id == t1.id
    assert t2.name == t1.name
    assert t2.instructions == t1.instructions
    assert t2.position == t1.position
    assert t2.files == t1.files
    assert t2.parent_id == t1.parent_id


def test_tasklist_get_children_basic_filter():
    t1 = Task(id="1", name="A", instructions="x", parent_id="p")
    t2 = Task(id="2", name="B", instructions="y", parent_id="p")
    t3 = Task(id="3", name="C", instructions="z", parent_id="other")
    tl = TaskList(id="tl1", name="n", description="d", tasks=[t1, t2, t3])
    children = tl.get_children("p")
    assert len(children) == 2
    ids = {c.id for c in children}
    assert ids == {"1", "2"}


def test_tasklist_service_save_all_pending_normalizes_to_created(tmp_path):
    svc = TaskListService()
    tl = TaskList(
        id="svc-tl",
        name="n",
        description="d",
        tasks=[Task(id="t1", name="T", instructions="i")],
    )
    path = tmp_path / "tl.json"
    svc.save(str(path), tl)

    loaded = svc.load(str(path))
    assert loaded.state == TASK_LIST_STATE_CREATED
    assert loaded.tasks[0].state == TASK_STATE_PENDING


def test_tasklist_service_reset_clears_execution_state():
    svc = TaskListService()
    tl = TaskList(
        id="reset-tl",
        name="n",
        description="d",
        state=TASK_LIST_STATE_COMPLETED,
        current_task_id="t1",
        meta={"owner": "alice"},
        tasks=[
            Task(
                id="t1",
                name="T1",
                instructions="i",
                state=TASK_STATE_COMPLETED,
                result={"ok": True},
                error="boom",
                meta={"priority": "high"},
                position=0,
                files=["a.txt"],
                parent_id="p",
            ),
        ],
    )
    svc.reset(tl)
    assert tl.state == TASK_LIST_STATE_CREATED
    assert tl.current_task_id is None
    task = tl.tasks[0]
    assert task.state == TASK_STATE_PENDING
    assert task.result is None
    assert task.error is None
    assert task.meta == {"priority": "high"}
    assert task.position == 0
    assert task.files == ["a.txt"]
    assert task.parent_id == "p"
    assert tl.meta == {"owner": "alice"}


def test_tasklist_get_children_no_matches_returns_empty():
    t1 = Task(id="1", name="A", instructions="x", parent_id="p")
    tl = TaskList(id="tl2", name="n", description="d", tasks=[t1])
    children = tl.get_children("nomatch")
    assert children == []


def test_task_run_metrics_persist():
    metrics = {
        "correlation_id": "c-1",
        "iterations": 3,
        "max_iterations": 10,
        "hit_iteration_cap": False,
        "openai_calls": 3,
        "tool_calls": 2,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "failures": 0,
        "duration_ms": 42,
    }
    assert "run_metrics" in {f.name for f in fields(Task)}

    t = Task(id=str(uuid.uuid4()), name="T10", instructions="Do", run_metrics=metrics)
    assert t.run_metrics == metrics
    d = t.to_dict()
    assert d["run_metrics"] == metrics
    loaded = Task.from_dict(d)
    assert loaded.run_metrics == metrics

    plain = Task(id=str(uuid.uuid4()), name="T11", instructions="Do")
    assert plain.run_metrics is None
    assert "run_metrics" not in plain.to_dict()
    loaded_plain = Task.from_dict(plain.to_dict())
    assert loaded_plain.run_metrics is None

    legacy = {"id": str(uuid.uuid4()), "name": "T12", "instructions": "Do"}
    legacy_loaded = Task.from_dict(legacy)
    assert legacy_loaded.run_metrics is None


def test_task_reset_clears_run_metrics():
    svc = TaskListService()
    tl = TaskList(
        id="reset-metrics-tl",
        name="n",
        description="d",
        state=TASK_LIST_STATE_COMPLETED,
        current_task_id="t1",
        tasks=[
            Task(
                id="t1",
                name="T1",
                instructions="i",
                state=TASK_STATE_COMPLETED,
                result={"ok": True},
                error="boom",
                run_metrics={"iterations": 5, "failures": 1},
            ),
        ],
    )
    svc.reset(tl)
    task = tl.tasks[0]
    assert task.state == TASK_STATE_PENDING
    assert task.result is None
    assert task.error is None
    assert task.run_metrics is None

def test_tasklist_round_trip_preserves_task_run_metrics():
    metrics = {"iterations": 40, "openai_calls": 40}
    task = Task(id=str(uuid.uuid4()), name="T", instructions="Do", run_metrics=metrics)
    tasklist = TaskList(id="tl-run-metrics", name="n", description="d", tasks=[task])

    loaded = TaskList.from_dict(tasklist.to_dict())

    assert loaded.tasks[0].run_metrics == metrics
