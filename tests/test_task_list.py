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
