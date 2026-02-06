import json
import uuid

from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_PENDING


def test_task_unknown_key_rejection():
    data = {"id": "1", "instructions": "Do something", "extra": "not-allowed"}
    try:
        Task.from_dict(data)
        assert False, "Expected ValueError for unknown keys"
    except ValueError as e:
        assert "Unknown Task fields" in str(e) or "validation" in str(e).lower()


def test_task_missing_required_fields():
    data = {"id": "1"}
    try:
        Task.from_dict(data)
        assert False, "Expected ValueError for missing required fields"
    except ValueError as e:
        assert "Missing required Task field" in str(e) or "instructions" in str(e)


def test_migration_v1_title_and_int_id_converted():
    # v1 shape: numeric id, title, status
    v1 = {
        "schema_version": 1,
        "id": "tl-v1",
        "tasks": [{"id": 42, "title": "Old Task", "status": "pending"}],
    }

    tl = TaskList.from_dict(v1)
    assert tl.schema_version == 1
    assert tl.id == "tl-v1"
    assert len(tl.tasks) == 1
    t = tl.tasks[0]
    assert t.instructions == "Old Task"
    assert isinstance(t.id, str)
    # numeric id should have been converted to a UUID-like string
    try:
        uuid.UUID(t.id)
    except Exception:
        assert False, "Expected task id to be UUID string after migration"


def test_migration_v1_unknown_fields_moved_to_meta_when_allowed():
    v1 = {
        "schema_version": 1,
        "id": "tl-v1b",
        "tasks": [{"id": 7, "title": "T", "status": "pending", "foo": "bar"}],
    }

    # When allow_legacy_meta=False, this should raise due to unknown key
    try:
        TaskList.from_dict(v1, allow_legacy_meta=False)
        assert False, "Expected ValueError for unknown task key when legacy meta not allowed"
    except ValueError:
        pass

    # When allowed, unknown keys should be moved into task.meta
    tl = TaskList.from_dict(v1, allow_legacy_meta=True)
    t = tl.tasks[0]
    assert t.meta.get("foo") == "bar"


def test_round_trip_dump_load():
    t1 = Task(id=1, instructions="First", state=TASK_STATE_PENDING)
    t2 = Task(id=2, instructions="Second", state=TASK_STATE_PENDING)
    tl = TaskList(id="round-1", tasks=[t1, t2], meta={"a": 1})

    serialized = tl.to_dict()
    # Ensure serialization contains schema_version 2
    assert serialized.get("schema_version") == 2

    # Load back
    loaded = TaskList.from_dict(serialized)
    assert loaded.id == tl.id
    assert loaded.meta == tl.meta
    assert len(loaded.tasks) == 2
    # Tasks ids should be strings (UUIDs) not integers
    for orig, new in zip(tl.tasks, loaded.tasks):
        assert isinstance(new.id, str)
        assert new.instructions == orig.instructions
        assert new.state == orig.state

    # Round-trip Json
    js = tl.to_json()
    loaded2 = TaskList.from_json(js)
    assert loaded2.id == tl.id
    assert len(loaded2.tasks) == 2
