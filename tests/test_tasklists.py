import json
import uuid

from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_PENDING


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
