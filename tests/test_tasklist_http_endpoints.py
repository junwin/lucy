from src.http_endpoints.agents_endpoints import put_tasklist_impl as agents_put_tasklist_impl
from src.http_endpoints.tasklist_endpoints import put_tasklist_impl as tasklists_put_tasklist_impl
from src.tasklists.task_list import TaskList


def _payload():
    return {
        "schema_version": 1,
        "id": "tl1",
        "name": "My Tasks",
        "description": "d",
        "tasks": [],
    }


def test_tasklist_endpoints_put_converts_dict_to_tasklist_at_edge(fake_tasklist_store):
    result = tasklists_put_tasklist_impl(fake_tasklist_store, "alice", "tl1", _payload())
    assert result == ({"ok": True}, 200)

    tl = fake_tasklist_store.get_tasklist("alice", "tl1")
    assert isinstance(tl, TaskList)
    assert tl.id == "tl1"
    assert tl.name == "My Tasks"


def test_agents_endpoints_put_converts_dict_to_tasklist_at_edge(fake_tasklist_store):
    result = agents_put_tasklist_impl(fake_tasklist_store, "alice", "tl1", _payload())
    assert result == ({"ok": True}, 200)

    tl = fake_tasklist_store.get_tasklist("alice", "tl1")
    assert isinstance(tl, TaskList)
    assert tl.id == "tl1"
    assert tl.name == "My Tasks"
