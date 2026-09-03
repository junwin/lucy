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
    tl.remove_task("t1")
    tl.add_task(_make_task("t1", "new attempt"))
    assert len(tl.tasks) == 1
    assert tl.tasks[0].name == "new attempt"


def test_add_task_after_index_inserts_after_position():
    tl = _make_list()
    tl.add_task(_make_task("t1", "A"))
    tl.add_task(_make_task("t2", "B"))
    tl.add_task(_make_task("t3", "C"))
    tl.add_task(_make_task("t4", "D"), after_index=1)
    assert [t.id for t in tl.tasks] == ["t1", "t2", "t4", "t3"]


def test_add_task_after_index_out_of_range_appends():
    tl = _make_list()
    tl.add_task(_make_task("t1", "A"))
    tl.add_task(_make_task("t2", "B"))
    tl.add_task(_make_task("t3", "C"), after_index=99)
    assert [t.id for t in tl.tasks] == ["t1", "t2", "t3"]


def test_add_task_after_index_negative_raises():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    with pytest.raises(ValueError, match="after_index"):
        tl.add_task(_make_task("t2"), after_index=-1)
    assert len(tl.tasks) == 1


def test_add_task_after_index_rejects_duplicate():
    tl = _make_list()
    tl.add_task(_make_task("t1", "original"))
    with pytest.raises(ValueError, match="already exists"):
        tl.add_task(_make_task("t1", "duplicate"), after_index=0)
    assert len(tl.tasks) == 1


def test_update_task_applies_whitelisted_fields():
    tl = _make_list()
    tl.add_task(_make_task("t1", "A"))
    tl.update_task(
        "t1",
        name="B",
        instructions="new instructions",
        state="Running",
        error="boom",
        agent="worker",
        position=2,
        parent_id="p1",
        files=["f1.py", "f2.py"],
    )
    t = tl.get_task("t1")
    assert t.name == "B"
    assert t.instructions == "new instructions"
    assert t.state == "Running"
    assert t.error == "boom"
    assert t.agent == "worker"
    assert t.position == 2
    assert t.parent_id == "p1"
    assert t.files == ["f1.py", "f2.py"]


def test_update_task_partial_update_leaves_other_fields():
    tl = _make_list()
    tl.add_task(Task(id="t1", name="A", instructions="do it", agent="old", position=1, meta={"k": "v"}))
    tl.update_task("t1", name="B")
    t = tl.get_task("t1")
    assert t.name == "B"
    assert t.instructions == "do it"
    assert t.agent == "old"
    assert t.position == 1
    assert t.meta == {"k": "v"}


def test_update_task_merges_meta():
    tl = _make_list()
    tl.add_task(Task(id="t1", name="T", instructions="do it", meta={"a": 1, "b": 2}))
    tl.update_task("t1", meta={"b": 3, "c": 4})
    assert tl.get_task("t1").meta == {"a": 1, "b": 3, "c": 4}


def test_update_task_rejects_result_field():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    with pytest.raises(ValueError, match="result"):
        tl.update_task("t1", result={"ok": True})
    assert tl.get_task("t1").result is None


def test_update_task_rejects_unknown_fields():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    with pytest.raises(ValueError, match="cannot update task field"):
        tl.update_task("t1", context="junwin")
    with pytest.raises(ValueError, match="cannot update task field"):
        tl.update_task("t1", run_metrics={"x": 1})
    with pytest.raises(ValueError, match="cannot update task field"):
        tl.update_task("t1", typo_field="x")
    assert tl.get_task("t1").context is None
    assert tl.get_task("t1").run_metrics is None


def test_update_task_missing_task_raises():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    with pytest.raises(ValueError, match="not found"):
        tl.update_task("nope", name="X")
    assert [t.id for t in tl.tasks] == ["t1"]


def test_remove_task_removes_only_target():
    tl = _make_list()
    tl.add_task(_make_task("t1", "A"))
    tl.add_task(_make_task("t2", "B"))
    tl.remove_task("t1")
    assert [t.id for t in tl.tasks] == ["t2"]


def test_remove_task_missing_raises():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    with pytest.raises(ValueError, match="not found"):
        tl.remove_task("nope")
    assert len(tl.tasks) == 1


def test_update_task_state_updates_state():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    tl.update_task_state("t1", "Running")
    assert tl.get_task("t1").state == "Running"


def test_update_task_state_missing_raises():
    tl = _make_list()
    with pytest.raises(ValueError, match="not found"):
        tl.update_task_state("nope", "Running")


def test_set_task_result_replaces_result():
    tl = _make_list()
    tl.add_task(_make_task("t1"))
    tl.set_task_result("t1", {"ok": True}, new_state="Completed")
    t = tl.get_task("t1")
    assert t.result == {"ok": True}
    assert t.state == "Completed"
    tl.set_task_result("t1", {"ok": False}, new_state="Failed")
    assert tl.get_task("t1").result == {"ok": False}
    assert tl.get_task("t1").state == "Failed"


def test_set_task_result_missing_raises():
    tl = _make_list()
    with pytest.raises(ValueError, match="not found"):
        tl.set_task_result("nope", {"ok": True})


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
