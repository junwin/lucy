import inspect

import pytest

from src.tasklists.interfaces import TasklistManager
from src.tasklists.service import TaskListService
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_STATE_PENDING,
)


def _make_tl(key, name="n", description="d"):
    return TaskList(id=key, name=name, description=description)


def _seed(store, account="alice", key="tl1", meta=None):
    tl = TaskList(
        id=key,
        name="List",
        description="desc",
        meta=meta or {},
        tasks=[
            Task(id="t1", name="One", instructions="i1"),
            Task(id="t2", name="Two", instructions="i2"),
        ],
    )
    store.save_tasklist(account, key, tl)
    return TaskListService(store)


def _reload(store, account="alice", key="tl1"):
    return store.get_tasklist(account, key)


def test_tasklist_manager_abc_declares_crud_and_task_ops_surface():
    expected = {
        "list", "get", "save", "delete", "create", "create_from_goal",
        "add_task", "update_task", "remove_task",
        "set_state", "set_name", "set_description",
        "set_general_instructions", "update_meta",
    }
    assert inspect.isabstract(TasklistManager)
    assert expected <= set(TasklistManager.__abstractmethods__)


def test_service_conforms_to_tasklist_manager_interface(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    assert isinstance(svc, TasklistManager)


def test_list_delegates_to_store_with_sorted_keys(fake_tasklist_store):
    fake_tasklist_store.save_tasklist("alice", "b", _make_tl("b"))
    fake_tasklist_store.save_tasklist("alice", "a", _make_tl("a"))
    fake_tasklist_store.save_tasklist("bob", "z", _make_tl("z"))
    svc = TaskListService(fake_tasklist_store)
    assert svc.list("alice") == ["a", "b"]
    assert svc.list("bob") == ["z"]
    assert svc.list("carol") == []


def test_get_returns_tasklist_object(fake_tasklist_store):
    fake_tasklist_store.save_tasklist("alice", "tl1", _make_tl("tl1", name="List A", description="desc"))
    svc = TaskListService(fake_tasklist_store)
    tl = svc.get("alice", "tl1")
    assert isinstance(tl, TaskList)
    assert tl.id == "tl1"
    assert tl.name == "List A"
    assert tl.description == "desc"


def test_get_missing_returns_none(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    assert svc.get("alice", "missing") is None


def test_get_scoped_per_account(fake_tasklist_store):
    fake_tasklist_store.save_tasklist("alice", "tl1", _make_tl("tl1"))
    svc = TaskListService(fake_tasklist_store)
    assert svc.get("bob", "tl1") is None


def test_get_returns_reloaded_copy_not_shared_reference(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    svc.save("alice", "tl1", _make_tl("tl1"))
    first = svc.get("alice", "tl1")
    first.name = "mutated"
    second = svc.get("alice", "tl1")
    assert second.name == "n"


def test_get_task_result_passthrough_to_store(fake_tasklist_store):
    fake_tasklist_store.save_tasklist("alice", "tl1", _make_tl("tl1"))
    fake_tasklist_store.append_task_execution_record(
        "alice",
        "tl1",
        {"record_id": "r1", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "x"}},
    )
    svc = TaskListService(fake_tasklist_store)
    rec = svc.get_task_result("alice", "tl1", "t1")
    assert rec is not None
    assert rec["record_id"] == "r1"
    assert rec["result"]["output"] == "x"
    assert svc.get_task_result("alice", "tl1", "missing") is None
    assert svc.get_task_result("bob", "tl1", "t1") is None


def test_save_persists_through_store(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    svc.save("alice", "tl1", _make_tl("tl1"))
    assert fake_tasklist_store.list_tasklists("alice") == ["tl1"]
    stored = fake_tasklist_store.get_tasklist("alice", "tl1")
    assert isinstance(stored, TaskList)
    assert stored.id == "tl1"


def test_delete_removes_and_is_idempotent(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    svc.save("alice", "tl1", _make_tl("tl1"))
    svc.delete("alice", "tl1")
    assert svc.list("alice") == []
    assert svc.get("alice", "tl1") is None
    svc.delete("alice", "tl1")


def test_delete_scoped_per_account(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    svc.save("alice", "tl1", _make_tl("tl1"))
    svc.save("bob", "tl1", _make_tl("tl1"))
    svc.delete("alice", "tl1")
    assert svc.get("alice", "tl1") is None
    assert svc.get("bob", "tl1") is not None


def test_create_builds_tasklist_with_id_equal_to_key(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create("my-key", "My Key", "desc")
    assert isinstance(tl, TaskList)
    assert tl.id == "my-key"
    assert tl.name == "My Key"
    assert tl.description == "desc"
    assert tl.state == TASK_LIST_STATE_CREATED
    assert tl.tasks == []
    assert tl.meta == {}
    assert tl.general_instructions == ""


def test_create_accepts_meta_and_general_instructions(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create("k", "n", "d", meta={"owner": "alice"}, general_instructions="gi")
    assert tl.meta == {"owner": "alice"}
    assert tl.general_instructions == "gi"


def test_create_does_not_persist_until_save(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    svc.create("k", "n", "d")
    assert svc.list("alice") == []


def test_create_then_save_round_trips(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create("k1", "Name", "Desc", meta={"m": 1})
    svc.save("alice", tl.id, tl)
    loaded = svc.get("alice", "k1")
    assert loaded is not None
    assert loaded.id == "k1"
    assert loaded.name == "Name"
    assert loaded.meta == {"m": 1}


def test_create_from_goal_no_files_builds_execute_goal_task(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create_from_goal("fix-handler-timeout", "Fix the timeout bug")
    assert tl.id == "fix-handler-timeout"
    assert tl.name == "Fix Handler Timeout"
    assert tl.description == "Fix the timeout bug"
    assert tl.general_instructions == "Fix the timeout bug"
    assert tl.state == TASK_LIST_STATE_CREATED
    assert len(tl.tasks) == 1
    task = tl.tasks[0]
    assert task.id == "task-1"
    assert task.name == "Execute goal"
    assert task.instructions == "Fix the timeout bug"
    assert task.state == TASK_STATE_PENDING
    assert task.agent is None


def test_create_from_goal_with_files_builds_one_task_per_file(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create_from_goal("multi-file", "Do it", files=["/work/alpha.txt", "beta.py"], worker_agent="debo")
    assert [t.id for t in tl.tasks] == ["task-1", "task-2"]
    assert [t.name for t in tl.tasks] == ["alpha", "beta"]
    assert all(t.instructions == "Do it" for t in tl.tasks)
    assert all(t.agent == "debo" for t in tl.tasks)


def test_create_from_goal_underscore_key_name_derivation(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create_from_goal("my_goal_key", "Do it")
    assert tl.name == "My Goal Key"


def test_create_from_goal_empty_files_list_falls_back_to_execute_goal(fake_tasklist_store):
    svc = TaskListService(fake_tasklist_store)
    tl = svc.create_from_goal("k", "g", files=[])
    assert len(tl.tasks) == 1
    assert tl.tasks[0].id == "task-1"


def test_add_task_appends_and_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.add_task("alice", "tl1", Task(id="t3", name="Three", instructions="i3"))
    assert isinstance(tl, TaskList)
    assert [t.id for t in tl.tasks] == ["t1", "t2", "t3"]
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t1", "t2", "t3"]
    assert loaded.tasks[2].name == "Three"


def test_add_task_after_index_inserts_and_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.add_task("alice", "tl1", Task(id="t3", name="Three", instructions="i3"), after_index=0)
    assert [t.id for t in tl.tasks] == ["t1", "t3", "t2"]
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t1", "t3", "t2"]


def test_add_task_duplicate_id_raises_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    with pytest.raises(ValueError, match="already exists"):
        svc.add_task("alice", "tl1", Task(id="t1", name="Duplicate", instructions="x"))
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t1", "t2"]
    assert loaded.tasks[0].name == "One"


def test_update_task_merges_whitelisted_fields_and_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.update_task(
        "alice",
        "tl1",
        "t1",
        name="Renamed",
        instructions="instr2",
        state=TASK_STATE_COMPLETED,
        error="boom",
        meta={"priority": "high"},
        agent="debo",
        position=7,
        parent_id="parent-x",
        files=["a.txt"],
    )
    task = tl.get_task("t1")
    assert task.name == "Renamed"
    assert task.instructions == "instr2"
    assert task.state == TASK_STATE_COMPLETED
    assert task.error == "boom"
    assert task.meta == {"priority": "high"}
    assert task.agent == "debo"
    assert task.position == 7
    assert task.parent_id == "parent-x"
    assert task.files == ["a.txt"]
    loaded = _reload(fake_tasklist_store)
    t = loaded.get_task("t1")
    assert t.name == "Renamed"
    assert t.instructions == "instr2"
    assert t.state == TASK_STATE_COMPLETED
    assert t.error == "boom"
    assert t.meta == {"priority": "high"}
    assert t.agent == "debo"
    assert t.position == 7
    assert t.parent_id == "parent-x"
    assert t.files == ["a.txt"]
    assert loaded.get_task("t2").name == "Two"


def test_update_task_partial_change_leaves_other_fields(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    svc.update_task("alice", "tl1", "t1", name="OnlyName")
    loaded = _reload(fake_tasklist_store)
    t = loaded.get_task("t1")
    assert t.name == "OnlyName"
    assert t.instructions == "i1"
    assert t.state == TASK_STATE_PENDING


def test_update_task_rejects_result_field_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    with pytest.raises(ValueError, match="result"):
        svc.update_task("alice", "tl1", "t1", result={"ok": True})
    loaded = _reload(fake_tasklist_store)
    assert loaded.get_task("t1").name == "One"


def test_update_task_rejects_unknown_field_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    with pytest.raises(ValueError, match="cannot update task field"):
        svc.update_task("alice", "tl1", "t1", task_result={"ok": True})
    loaded = _reload(fake_tasklist_store)
    assert loaded.get_task("t1").name == "One"


def test_update_task_missing_task_raises_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    with pytest.raises(ValueError, match="not found"):
        svc.update_task("alice", "tl1", "nope", name="X")
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t1", "t2"]


def test_remove_task_removes_and_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.remove_task("alice", "tl1", "t1")
    assert isinstance(tl, TaskList)
    assert [t.id for t in tl.tasks] == ["t2"]
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t2"]


def test_remove_task_missing_task_raises_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    with pytest.raises(ValueError, match="not found"):
        svc.remove_task("alice", "tl1", "nope")
    loaded = _reload(fake_tasklist_store)
    assert [t.id for t in loaded.tasks] == ["t1", "t2"]


def test_set_state_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.set_state("alice", "tl1", TASK_LIST_STATE_COMPLETED)
    assert isinstance(tl, TaskList)
    assert tl.state == TASK_LIST_STATE_COMPLETED
    assert _reload(fake_tasklist_store).state == TASK_LIST_STATE_COMPLETED


def test_set_name_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.set_name("alice", "tl1", "New Name")
    assert tl.name == "New Name"
    assert _reload(fake_tasklist_store).name == "New Name"


def test_set_description_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.set_description("alice", "tl1", "New desc")
    assert tl.description == "New desc"
    assert _reload(fake_tasklist_store).description == "New desc"


def test_set_general_instructions_persists_and_can_clear(fake_tasklist_store):
    svc = _seed(fake_tasklist_store)
    tl = svc.set_general_instructions("alice", "tl1", "gi")
    assert tl.general_instructions == "gi"
    assert _reload(fake_tasklist_store).general_instructions == "gi"
    svc.set_general_instructions("alice", "tl1", "")
    assert _reload(fake_tasklist_store).general_instructions == ""


def test_update_meta_merges_and_persists(fake_tasklist_store):
    svc = _seed(fake_tasklist_store, meta={"a": 1})
    tl = svc.update_meta("alice", "tl1", {"b": 2})
    assert isinstance(tl, TaskList)
    assert tl.meta == {"a": 1, "b": 2}
    assert _reload(fake_tasklist_store).meta == {"a": 1, "b": 2}


def test_update_meta_overwrites_existing_key(fake_tasklist_store):
    svc = _seed(fake_tasklist_store, meta={"a": 1})
    svc.update_meta("alice", "tl1", {"a": 9})
    assert _reload(fake_tasklist_store).meta == {"a": 9}


def test_update_meta_non_dict_raises_and_does_not_persist(fake_tasklist_store):
    svc = _seed(fake_tasklist_store, meta={"a": 1})
    with pytest.raises(TypeError):
        svc.update_meta("alice", "tl1", "nope")
    assert _reload(fake_tasklist_store).meta == {"a": 1}


def test_mutating_op_is_scoped_per_account(fake_tasklist_store):
    _seed(fake_tasklist_store, account="alice", key="tl1")
    _seed(fake_tasklist_store, account="bob", key="tl1")
    svc = TaskListService(fake_tasklist_store)
    svc.set_name("alice", "tl1", "Alice List")
    assert _reload(fake_tasklist_store, account="alice").name == "Alice List"
    assert _reload(fake_tasklist_store, account="bob").name == "List"


def test_task_op_on_other_accounts_tasklist_raises(fake_tasklist_store):
    _seed(fake_tasklist_store, account="alice", key="tl1")
    svc = TaskListService(fake_tasklist_store)
    with pytest.raises(ValueError, match="not found"):
        svc.add_task("bob", "tl1", Task(id="t9", name="T", instructions="i"))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda svc: svc.add_task("alice", "missing", Task(id="t9", name="T", instructions="i")),
        lambda svc: svc.update_task("alice", "missing", "t1", name="x"),
        lambda svc: svc.remove_task("alice", "missing", "t1"),
        lambda svc: svc.set_state("alice", "missing", TASK_LIST_STATE_RUNNING),
        lambda svc: svc.set_name("alice", "missing", "x"),
        lambda svc: svc.set_description("alice", "missing", "x"),
        lambda svc: svc.set_general_instructions("alice", "missing", "x"),
        lambda svc: svc.update_meta("alice", "missing", {"k": "v"}),
    ],
)
def test_task_ops_on_missing_tasklist_raise(fake_tasklist_store, mutate):
    svc = TaskListService(fake_tasklist_store)
    with pytest.raises(ValueError, match="not found"):
        mutate(svc)
