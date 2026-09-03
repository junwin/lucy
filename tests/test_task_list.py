import pytest

from src.tasklists.task import Task
from src.tasklists.task_list import TaskList


def _make_list():
    return TaskList(id="tl1", name="My List", description="desc")


def _make_task(task_id, name="Task"):
    return Task(id=task_id, name=name, instructions="do it")


def test_add_task_appends_new_ids():
    tl = _make_list()
    tl.add_task(_make_task("t1", "A"))
    tl.add_task(_make_task("t2", "B"))
    assert [t.id for t in tl.tasks] == ["t1", "t2"]


def test_add_task_duplicate_id_raises_value_error():
    tl = _make_list()
    tl.add_task(_make_task("t1", "original"))
    with pytest.raises(ValueError, match="task with id 't1' already exists"):
        tl.add_task(_make_task("t1", "replacement"))
    assert len(tl.tasks) == 1
    assert tl.tasks[0].name == "original"


def test_add_task_duplicate_id_after_removal_allowed():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    tl.tasks.pop()
    tl.add_task(_make_task("t1", "new attempt"))
    assert len(tl.tasks) == 1
    assert tl.tasks[0].name == "new attempt"


def test_from_dict_accepts_unique_task_ids():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    tl.add_task(_make_task("t2"))
    restored = TaskList.from_dict(tl.to_dict())
    assert [t.id for t in restored.tasks] == ["t1", "t2"]


def test_from_dict_rejects_duplicate_task_ids():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    tl.add_task(_make_task("t2"))
    payload = tl.to_dict()
    payload["tasks"][1]["id"] = "t1"
    with pytest.raises(ValueError, match="duplicate task id"):
        TaskList.from_dict(payload)


def test_task_constructor_accepts_context():
    task = Task(id="t1", name="T", instructions="do it", context="junwin")
    assert task.context == "junwin"


def test_task_to_dict_omits_context_when_unset():
    task = _make_task("t1")
    assert "context" not in task.to_dict()


def test_task_to_dict_emits_context_when_set():
    task = Task(id="t1", name="T", instructions="do it", context="junwin")
    assert task.to_dict()["context"] == "junwin"


def test_task_round_trip_preserves_context():
    task = Task(id="t1", name="T", instructions="do it", context="junwin")
    restored = Task.from_dict(task.to_dict())
    assert restored.context == "junwin"
    assert restored.to_dict()["context"] == "junwin"


def test_task_from_dict_tolerates_missing_context():
    task = Task.from_dict({"id": "t1", "name": "T", "instructions": "do it"})
    assert task.context is None


def test_tasklist_round_trip_preserves_task_context():
    tl = _make_list()
    tl.add_task(Task(id="t1", name="T", instructions="do it", context="junwin"))
    tl.add_task(_make_task("t2"))
    restored = TaskList.from_dict(tl.to_dict())
    assert restored.get_task("t1").context == "junwin"
    assert restored.get_task("t2").context is None


def test_tasklist_from_dict_tolerates_legacy_task_without_context():
    payload = {
        "schema_version": 1,
        "id": "tl1",
        "name": "My List",
        "description": "desc",
        "tasks": [{"id": "t1", "name": "T", "instructions": "do it"}],
    }
    tl = TaskList.from_dict(payload)
    assert tl.get_task("t1").context is None
