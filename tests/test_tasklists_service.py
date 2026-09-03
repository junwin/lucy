import inspect

from src.tasklists.interfaces import TasklistManager
from src.tasklists.service import TaskListService
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_LIST_STATE_CREATED, TASK_STATE_PENDING


def _make_tl(key, name="n", description="d"):
    return TaskList(id=key, name=name, description=description)


def test_tasklist_manager_abc_declares_crud_and_task_ops_surface():
    expected = {
        "list", "get", "save", "delete", "create", "create_from_goal",
        "add_task", "update_task", "remove_task",
        "set_state", "set_name", "set_description",
        "set_general_instructions", "update_meta",
    }
    assert inspect.isabstract(TasklistManager)
    assert expected <= set(TasklistManager.__abstractmethods__)


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
