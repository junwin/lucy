from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
import json
import pytest


def test_round_trip_to_dict_and_from_dict():
    t1 = Task(id=1, title="First task")
    t2 = Task(id=2, title="Second task", state="Done", result={"ok": True})

    tl = TaskList(id="list-123", tasks=[t1, t2], state="Running")

    d = tl.to_dict()

    # exact top-level JSON shape
    assert set(d.keys()) == {"schema_version", "id", "state", "tasks", "meta"}
    assert d["schema_version"] == 1
    assert d["id"] == "list-123"
    assert d["state"] == "Running"
    assert isinstance(d["tasks"], list)
    assert len(d["tasks"]) == 2

    # tasks shape should match Task.to_dict()
    assert d["tasks"][0] == t1.to_dict()
    assert d["tasks"][1] == t2.to_dict()

    # round-trip via from_dict yields equivalent dict
    tl2 = TaskList.from_dict(d)
    assert tl2.to_dict() == d

    # json serialization should produce valid JSON and match dict when loaded
    j = tl.to_json()
    loaded = json.loads(j)
    assert loaded == d


def test_from_dict_requires_id_unless_provided():
    data = {"schema_version": 1, "state": "Created", "tasks": []}

    with pytest.raises(ValueError):
        TaskList.from_dict(data)

    # should succeed when id is provided as parameter
    tl = TaskList.from_dict(data, id="provided-id")
    assert tl.id == "provided-id"
    assert tl.to_dict()["id"] == "provided-id"


def test_from_dict_rejects_unknown_schema_version():
    data = {"schema_version": 2, "id": "x", "state": "Created", "tasks": []}
    with pytest.raises(ValueError):
        TaskList.from_dict(data)


def test_to_dict_always_includes_id():
    t = Task(id=1, title="T")
    tl = TaskList(id="abc", tasks=[t])
    d = tl.to_dict()
    assert "id" in d and d["id"] == "abc"


def test_meta_roundtrip_in_model():
    # Task-level meta and TaskList-level meta should be preserved through to_dict/from_dict
    t1 = Task(id=1, title="T1", meta={"task_meta": "v"})
    tl = TaskList(id="list-meta", tasks=[t1], meta={"supervisor_agent": "super", "notes": "x"})

    d = tl.to_dict()
    assert "meta" in d
    assert d["meta"] == {"supervisor_agent": "super", "notes": "x"}
    assert d["tasks"][0]["meta"] == {"task_meta": "v"}

    tl2 = TaskList.from_dict(d)
    assert tl2.meta == tl.meta
    assert tl2.tasks[0].meta == t1.meta
