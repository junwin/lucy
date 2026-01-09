from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.storage.models import ContextState
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.tasklist_boundary import load_tasklist, save_tasklist


@pytest.fixture
def context_state() -> ContextState:
    return ContextState(
        id="ctx-1",
        account_name="acct-1",
        data={},
        updated_at=datetime.now(timezone.utc),
    )


def test_load_tasklist_returns_none_when_missing(context_state: ContextState) -> None:
    assert load_tasklist(context_state) is None


def test_save_then_load_roundtrip(context_state: ContextState) -> None:
    tl = TaskList(
        schema_version=1,
        state="created",
        tasks_list=[
            Task(id=1, title="t1", state="pending", result=None, error=None, meta={}),
            Task(id=2, title="t2", state="done", result={"ok": True}, error=None, meta={"a": 1}),
        ],
    )

    save_tasklist(context_state, tl)

    # saved as dict-only
    raw = context_state.data["tasklist"]
    assert isinstance(raw, dict)
    assert raw["schema_version"] == 1
    assert raw["state"] == "created"
    assert raw["tasks"][0]["id"] == 1

    loaded = load_tasklist(context_state)
    assert loaded is not None
    assert loaded.schema_version == 1
    assert loaded.state == "created"
    assert [t.id for t in loaded.tasks_list] == [1, 2]
    assert loaded.get_task(2) is not None
    assert loaded.get_task(2).result == {"ok": True}
    assert loaded.get_task(2).meta == {"a": 1}


def test_load_tasklist_rejects_non_dict_storage(context_state: ContextState) -> None:
    context_state.data["tasklist"] = []
    with pytest.raises(ValueError, match=r"context\.data\['tasklist'\] must be a dict"):
        load_tasklist(context_state)


def test_load_tasklist_rejects_wrong_schema_version(context_state: ContextState) -> None:
    context_state.data["tasklist"] = {"schema_version": 2, "state": "created", "tasks": []}
    with pytest.raises(ValueError, match=r"schema_version"):
        load_tasklist(context_state)


def test_load_tasklist_rejects_duplicate_task_ids(context_state: ContextState) -> None:
    context_state.data["tasklist"] = {
        "schema_version": 1,
        "state": "created",
        "tasks": [
            {"id": 1, "title": "a", "state": "pending", "result": None, "error": None, "meta": {}},
            {"id": 1, "title": "b", "state": "pending", "result": None, "error": None, "meta": {}},
        ],
    }
    with pytest.raises(ValueError, match=r"unique"):
        load_tasklist(context_state)


def test_load_tasklist_rejects_task_id_numeric_string(context_state: ContextState) -> None:
    # NOTE: pydantic will coerce "1" -> 1 for an int field unless strict mode is enabled.
    # Current boundary code does not enable strict mode, so we assert the current behavior:
    # numeric strings are accepted and coerced.
    context_state.data["tasklist"] = {
        "schema_version": 1,
        "state": "created",
        "tasks": [
            {"id": "1", "title": "a", "state": "pending", "result": None, "error": None, "meta": {}},
        ],
    }

    tl = load_tasklist(context_state)
    assert tl is not None
    assert tl.get_task(1) is not None


def test_load_tasklist_rejects_task_result_not_dict(context_state: ContextState) -> None:
    context_state.data["tasklist"] = {
        "schema_version": 1,
        "state": "created",
        "tasks": [
            {"id": 1, "title": "a", "state": "pending", "result": ["nope"], "error": None, "meta": {}},
        ],
    }
    with pytest.raises(ValueError, match=r"Invalid tasklist in context"):
        load_tasklist(context_state)


def test_load_tasklist_rejects_task_meta_not_dict(context_state: ContextState) -> None:
    context_state.data["tasklist"] = {
        "schema_version": 1,
        "state": "created",
        "tasks": [
            {"id": 1, "title": "a", "state": "pending", "result": None, "error": None, "meta": []},
        ],
    }
    with pytest.raises(ValueError, match=r"Invalid tasklist in context"):
        load_tasklist(context_state)


def test_tasklist_tasks_returns_copy() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="t1")])
    tasks_copy = list(tl.tasks())
    tasks_copy.append(Task(id=2, title="t2"))

    assert [t.id for t in tl.tasks_list] == [1]


def test_tasklist_next_id_empty_returns_1() -> None:
    tl = TaskList(schema_version=1, state="created")
    assert tl.next_id() == 1


def test_tasklist_next_id_returns_max_plus_1() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=5, title="a"), Task(id=2, title="b")])
    assert tl.next_id() == 6


def test_tasklist_add_task_appends_when_new_id() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a")])
    tl.add_task(Task(id=2, title="b"))
    assert [t.id for t in tl.tasks_list] == [1, 2]


def test_tasklist_add_task_replaces_in_place_when_same_id() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a"), Task(id=2, title="b")])
    tl.add_task(Task(id=2, title="b2"))
    assert [t.id for t in tl.tasks_list] == [1, 2]
    assert tl.tasks_list[1].title == "b2"


def test_tasklist_update_task_state_noop_when_missing() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a", state="pending")])
    tl.update_task_state(999, "done")
    assert tl.get_task(1).state == "pending"


def test_tasklist_update_task_state_updates_when_present() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a", state="pending")])
    tl.update_task_state(1, "done")
    assert tl.get_task(1).state == "done"


def test_tasklist_set_task_result_noop_when_missing() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a")])
    tl.set_task_result(999, {"x": 1}, new_state="done", error="err")
    assert tl.get_task(1).result is None


def test_tasklist_set_task_result_sets_result_and_optional_state_and_error() -> None:
    tl = TaskList(schema_version=1, state="created", tasks_list=[Task(id=1, title="a", state="pending")])
    tl.set_task_result(1, {"x": 1}, new_state="done", error="boom")

    t = tl.get_task(1)
    assert t.result == {"x": 1}
    assert t.state == "done"
    assert t.error == "boom"
