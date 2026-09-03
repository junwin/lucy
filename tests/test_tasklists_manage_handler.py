import json
from unittest.mock import patch

from src.handlers.tasklists_manage_handler import TasklistsManageHandler
from src.tasklists.task_states import (
    TASK_LIST_STATE_CREATED,
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_PENDING,
    TASK_STATE_COMPLETED,
)


class SimpleConfig:
    def __init__(self, storage_root_path, storage_namespace):
        self._m = {
            "storage_root_path": storage_root_path,
            "storage_namespace": storage_namespace,
        }

    def get(self, k, default=None):
        return self._m.get(k, default)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _create_tl(h, account, name, tasks=None):
    """Helper: create a tasklist via explicit put, optionally add tasks."""
    r = h.execute(
        {"action": "put", "tasklist_key": name, "name": name, "description": "test", "validate_only": False},
        account_name=account,
    )
    assert r.get("ok") is True, f"_create_tl put failed: {r}"

    if tasks:
        for t in tasks:
            r = h.execute(
                {
                    "action": "add_task",
                    "tasklist_key": name,
                    "task_id": t["id"],
                    "task_name": t["name"],
                    "task_instructions": t.get("instructions", ""),
                    "validate_only": False,
                },
                account_name=account,
            )
            assert r.get("ok") is True, f"_create_tl add_task failed: {r}"

    return name


def _create_completed_tasklist(h, account, name):
    """Helper: create a tasklist with Completed state and two completed tasks.

    Builds via approved methods: put → add_task → update_task → set_state.
    """
    _create_tl(
        h, account, name,
        tasks=[
            {"id": "task-1", "name": "T1", "instructions": "do 1"},
            {"id": "task-2", "name": "T2", "instructions": "do 2"},
        ],
    )

    # Set each task to completed with result
    for tid in ("task-1", "task-2"):
        r = h.execute(
            {
                "action": "update_task",
                "tasklist_key": name,
                "task_id": tid,
                "task_state": TASK_STATE_COMPLETED,
                "task_result": {"ok": True},
                "validate_only": False,
            },
            account_name=account,
        )
        assert r.get("ok") is True, f"_create_completed_tasklist update_task {tid} failed: {r}"

    # Set tasklist state to Completed
    r = h.execute(
        {
            "action": "set_state",
            "tasklist_key": name,
            "state": TASK_LIST_STATE_COMPLETED,
            "validate_only": False,
        },
        account_name=account,
    )
    assert r.get("ok") is True, f"_create_completed_tasklist set_state failed: {r}"

    return name


# ------------------------------------------------------------------
# List / Get / Delete
# ------------------------------------------------------------------


def test_list_empty(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    r = h.execute({"action": "list", "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    assert r.get("tasklist_keys") == []


def test_get_missing_and_delete_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "get", "tasklist_key": "nope", "validate_only": False}, account_name="dave")
    assert r.get("ok") is False
    assert r.get("error") is not None

    r2 = h.execute({"action": "delete", "tasklist_key": "nope", "validate_only": False}, account_name="dave")
    # delete is idempotent and should succeed
    assert r2.get("ok") is True


def test_read_actions_route_through_tasklist_service(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(
        h,
        "alice",
        "tl-route",
        tasks=[{"id": "task-1", "name": "T1", "instructions": "do 1"}],
    )
    h.tasklist_service.store.append_task_execution_record(
        "alice",
        "tl-route",
        {
            "schema_version": 1,
            "record_id": "rec-route",
            "tasklist_key": "tl-route",
            "task_id": "task-1",
            "task_name": "T1",
            "state": TASK_STATE_COMPLETED,
            "started": "2026-09-02T17:00:00.000Z",
            "ended": "2026-09-02T17:01:00.000Z",
            "result": {"output": "routed"},
        },
    )

    svc = h.tasklist_service
    with (
        patch.object(svc, "list", wraps=svc.list) as m_list,
        patch.object(svc, "get", wraps=svc.get) as m_get,
        patch.object(svc, "get_task_result", wraps=svc.get_task_result) as m_get_result,
        patch.object(svc, "delete", wraps=svc.delete) as m_delete,
    ):
        r = h.execute({"action": "list", "validate_only": False}, account_name="alice")
        assert r.get("ok") is True
        assert r.get("tasklist_keys") == ["tl-route"]

        r = h.execute(
            {"action": "get", "tasklist_key": "tl-route", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True
        assert r["tasklist"]["id"] == "tl-route"
        assert r["tasklist"]["tasks"][0]["id"] == "task-1"

        r = h.execute(
            {"action": "get_result", "tasklist_key": "tl-route", "task_id": "task-1"},
            account_name="alice",
        )
        assert r.get("ok") is True
        assert r.get("result_record", {}).get("record_id") == "rec-route"

        r = h.execute(
            {"action": "delete", "tasklist_key": "tl-route", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

    assert m_list.call_count == 1
    assert m_get.call_count == 1
    assert m_get_result.call_count == 1
    assert m_delete.call_count == 1

def test_write_actions_route_through_tasklist_service(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    assert not hasattr(h, "storage")

    svc = h.tasklist_service
    with (
        patch.object(svc.store, "save_tasklist", wraps=svc.store.save_tasklist) as m_store_save,
        patch.object(svc, "create", wraps=svc.create) as m_create,
        patch.object(svc, "create_from_goal", wraps=svc.create_from_goal) as m_create_from_goal,
        patch.object(svc, "save", wraps=svc.save) as m_save,
        patch.object(svc, "reset", wraps=svc.reset) as m_reset,
        patch.object(svc, "add_task", wraps=svc.add_task) as m_add_task,
        patch.object(svc, "update_task", wraps=svc.update_task) as m_update_task,
        patch.object(svc, "remove_task", wraps=svc.remove_task) as m_remove_task,
        patch.object(svc, "set_state", wraps=svc.set_state) as m_set_state,
        patch.object(svc, "set_name", wraps=svc.set_name) as m_set_name,
        patch.object(svc, "set_description", wraps=svc.set_description) as m_set_description,
        patch.object(svc, "set_general_instructions", wraps=svc.set_general_instructions) as m_set_gi,
        patch.object(svc, "update_meta", wraps=svc.update_meta) as m_update_meta,
    ):
        r = h.execute(
            {"action": "put", "tasklist_key": "tl-write", "name": "TL", "description": "d", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        for tid in ("t1", "t2"):
            r = h.execute(
                {
                    "action": "add_task",
                    "tasklist_key": "tl-write",
                    "task_id": tid,
                    "task_name": f"Task {tid}",
                    "validate_only": False,
                },
                account_name="alice",
            )
            assert r.get("ok") is True

        r = h.execute(
            {
                "action": "update_task",
                "tasklist_key": "tl-write",
                "task_id": "t1",
                "task_state": TASK_STATE_COMPLETED,
                "validate_only": False,
            },
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "set_state", "tasklist_key": "tl-write", "state": TASK_LIST_STATE_RUNNING, "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "set_name", "tasklist_key": "tl-write", "name": "Renamed", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "set_description", "tasklist_key": "tl-write", "description": "desc2", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "set_general_instructions", "tasklist_key": "tl-write", "instructions": "gi", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "update_meta", "tasklist_key": "tl-write", "meta": {"k": "v"}, "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "remove_task", "tasklist_key": "tl-write", "task_id": "t2", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "put", "tasklist_key": "goal-write", "goal": "Do the goal", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

        r = h.execute(
            {"action": "reset", "tasklist_key": "goal-write", "validate_only": False},
            account_name="alice",
        )
        assert r.get("ok") is True

    assert m_create.call_count == 1
    assert m_create_from_goal.call_count == 1
    assert m_save.call_count == 3
    assert m_store_save.call_count == 12
    assert m_reset.call_count == 1
    assert m_add_task.call_count == 2
    assert m_update_task.call_count == 1
    assert m_remove_task.call_count == 1
    assert m_set_state.call_count == 1
    assert m_set_name.call_count == 1
    assert m_set_description.call_count == 1
    assert m_set_gi.call_count == 1
    assert m_update_meta.call_count == 1

    got = h.execute({"action": "get", "tasklist_key": "tl-write", "validate_only": False}, account_name="alice")
    assert got.get("ok") is True
    assert got["tasklist"]["name"] == "Renamed"
    assert got["tasklist"]["state"] == TASK_LIST_STATE_RUNNING
    assert got["tasklist"]["meta"]["k"] == "v"
    assert [t["id"] for t in got["tasklist"]["tasks"]] == ["t1"]
    assert got["tasklist"]["tasks"][0]["state"] == TASK_STATE_COMPLETED




# ------------------------------------------------------------------
# Put — explicit path
# ------------------------------------------------------------------


def test_put_validate_only_does_not_persist(tmp_path):
    """validate_only=True must validate, return the payload, but NOT write to storage."""
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {"action": "put", "tasklist_key": "tl1", "name": "X", "description": "d", "validate_only": True},
        account_name="bob",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl is not None
    assert tl["id"] == "tl1"

    # Storage must NOT contain the tasklist
    r2 = h.execute({"action": "get", "tasklist_key": "tl1", "validate_only": False}, account_name="bob")
    assert r2.get("ok") is False
    assert r2.get("error", {}).get("code") == "not_found"


def test_put_persists_and_get(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {"action": "put", "tasklist_key": "tla", "name": "List A", "description": "d", "validate_only": False},
        account_name="carol",
    )
    assert r.get("ok") is True
    assert r.get("tasklist_key") == "tla"

    # Add a task
    h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tla",
            "task_id": "task-1",
            "task_name": "T1",
            "task_instructions": "do it",
            "validate_only": False,
        },
        account_name="carol",
    )

    r2 = h.execute({"action": "get", "tasklist_key": "tla", "validate_only": False}, account_name="carol")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["id"] == "tla"
    assert isinstance(tl.get("tasks"), list)
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "task-1"


def test_general_instructions_roundtrip(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "tl-generic",
            "name": "TL G",
            "description": "desc",
            "general_instructions": "Please follow these steps.",
            "validate_only": False,
        },
        account_name="sam",
    )
    assert r.get("ok") is True

    got = h.execute({"action": "get", "tasklist_key": "tl-generic", "validate_only": False}, account_name="sam")
    assert got.get("ok") is True
    tl = got.get("tasklist")
    assert tl.get("general_instructions") == "Please follow these steps."


def test_invalid_id_rejected(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    bad_ids = ["../x", "a/b", "", ".", "..", "has space", "a.b"]
    for bid in bad_ids:
        r = h.execute(
            {
                "action": "put",
                "tasklist_key": bid,
                "name": "Test",
                "description": "desc",
                "validate_only": False,
            },
            account_name="eve",
        )
        assert r.get("ok") is False, f"expected failure for key={bid!r}, got {r}"


# ------------------------------------------------------------------
# Reset
# ------------------------------------------------------------------


def test_reset_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "reset", "tasklist_key": "nope", "validate_only": False}, account_name="alice")
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "not_found"


def test_reset_clears_states(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    _create_completed_tasklist(h, "alice", "tl-reset")

    # Reset it
    r = h.execute({"action": "reset", "tasklist_key": "tl-reset", "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl is not None
    assert tl["state"] == TASK_LIST_STATE_CREATED
    assert tl.get("current_task_id") is None

    for task in tl["tasks"]:
        assert task["state"] == TASK_STATE_PENDING
        assert task.get("result") is None
        assert task.get("error") is None


def test_reset_validate_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    _create_completed_tasklist(h, "alice", "tl-reset-vo")

    # Reset with validate_only=True — should return reset state but NOT persist
    r = h.execute({"action": "reset", "tasklist_key": "tl-reset-vo", "validate_only": True}, account_name="alice")
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["state"] == TASK_LIST_STATE_CREATED
    for task in tl["tasks"]:
        assert task["state"] == TASK_STATE_PENDING

    # Verify storage still has the original completed state
    r2 = h.execute({"action": "get", "tasklist_key": "tl-reset-vo", "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    tl_stored = r2.get("tasklist")
    assert tl_stored["state"] == TASK_LIST_STATE_COMPLETED


def test_reset_persists_to_same_on_disk_file(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    _create_completed_tasklist(h, "alice", "tl-reset-disk")

    r = h.execute({"action": "reset", "tasklist_key": "tl-reset-disk", "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    assert r["tasklist"]["state"] == TASK_LIST_STATE_CREATED

    expected_path = tmp_path / "ns" / "tasklists" / "alice" / "tl-reset-disk.json"
    assert expected_path.exists()
    raw = json.loads(expected_path.read_text(encoding="utf-8"))
    assert raw["id"] == "tl-reset-disk"
    assert raw["state"] == TASK_LIST_STATE_CREATED
    assert raw.get("current_task_id") is None
    for task in raw["tasks"]:
        assert task["state"] == TASK_STATE_PENDING
        assert task.get("result") is None
        assert task.get("error") is None

    r2 = h.execute({"action": "get", "tasklist_key": "tl-reset-disk", "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    assert r2["tasklist"]["state"] == TASK_LIST_STATE_CREATED
    for task in r2["tasklist"]["tasks"]:
        assert task["state"] == TASK_STATE_PENDING
        assert task.get("result") is None
        assert task.get("error") is None


def test_reset_persists_only_for_given_account(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    _create_completed_tasklist(h, "alice", "tl-acct")
    _create_completed_tasklist(h, "bob", "tl-acct")

    r = h.execute({"action": "reset", "tasklist_key": "tl-acct", "validate_only": False}, account_name="alice")
    assert r.get("ok") is True

    alice_raw = json.loads((tmp_path / "ns" / "tasklists" / "alice" / "tl-acct.json").read_text(encoding="utf-8"))
    assert alice_raw["state"] == TASK_LIST_STATE_CREATED
    for task in alice_raw["tasks"]:
        assert task["state"] == TASK_STATE_PENDING

    bob_raw = json.loads((tmp_path / "ns" / "tasklists" / "bob" / "tl-acct.json").read_text(encoding="utf-8"))
    assert bob_raw["state"] == TASK_LIST_STATE_COMPLETED

def test_reset_legacy_inline_result_adopts_to_runs(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(
        h,
        "alice",
        "tl-legacy-reset",
        tasks=[{"id": "task-1", "name": "T1", "instructions": "do 1"}],
    )

    legacy_path = tmp_path / "ns" / "tasklists" / "alice" / "tl-legacy-reset.json"
    raw = json.loads(legacy_path.read_text(encoding="utf-8"))
    raw["tasks"][0]["state"] = TASK_STATE_COMPLETED
    raw["tasks"][0]["result"] = {"output": "keep me"}
    raw["tasks"][0]["run_metrics"] = {"tokens": 3}
    legacy_path.write_text(json.dumps(raw), encoding="utf-8")

    r = h.execute(
        {"action": "reset", "tasklist_key": "tl-legacy-reset", "validate_only": False},
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r["tasklist"]["state"] == TASK_LIST_STATE_CREATED

    stored = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert stored["state"] == TASK_LIST_STATE_CREATED
    assert "result" not in stored["tasks"][0]
    assert "run_metrics" not in stored["tasks"][0]

    runs_path = tmp_path / "ns" / "tasklists" / "alice" / "tl-legacy-reset.runs.jsonl"
    assert runs_path.exists()
    records = [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    rec = records[0]
    assert rec.get("legacy") is True
    assert rec.get("task_id") == "task-1"
    assert rec["result"] == {"output": "keep me"}
    assert rec["run_metrics"] == {"tokens": 3}

    r2 = h.execute(
        {"action": "get_result", "tasklist_key": "tl-legacy-reset", "task_id": "task-1"},
        account_name="alice",
    )
    assert r2.get("ok") is True
    assert r2.get("result_record", {}).get("result") == {"output": "keep me"}




# ------------------------------------------------------------------
# Task CRUD
# ------------------------------------------------------------------


def test_add_task_append(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-add-append")

    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-add-append",
            "task_id": "t1",
            "task_name": "Task 1",
            "task_instructions": "do step 1",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "t1"


def test_add_task_at_index(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-add-idx", tasks=[
        {"id": "a", "name": "A", "instructions": "a"},
        {"id": "b", "name": "B", "instructions": "b"},
    ])

    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-add-idx",
            "task_id": "c",
            "task_name": "C",
            "task_instructions": "c",
            "after_index": 0,
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 3
    # C should be inserted after index 0, so at position 1
    assert tl["tasks"][1]["id"] == "c"


def test_update_task(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-upd", tasks=[
        {"id": "t1", "name": "Old Name", "instructions": "old"},
    ])

    r = h.execute(
        {
            "action": "update_task",
            "tasklist_key": "tl-upd",
            "task_id": "t1",
            "task_name": "New Name",
            "task_instructions": "new instructions",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["tasks"][0]["name"] == "New Name"
    assert tl["tasks"][0]["instructions"] == "new instructions"
    # id should remain unchanged
    assert tl["tasks"][0]["id"] == "t1"


def test_update_task_not_found(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-upd-nf", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "update_task",
            "tasklist_key": "tl-upd-nf",
            "task_id": "nonexistent",
            "task_name": "X",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "not_found"


def test_remove_task(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rm", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
        {"id": "t2", "name": "T2", "instructions": "do 2"},
    ])

    r = h.execute(
        {
            "action": "remove_task",
            "tasklist_key": "tl-rm",
            "task_id": "t1",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "t2"


def test_remove_task_not_found(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rm-nf", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "remove_task",
            "tasklist_key": "tl-rm-nf",
            "task_id": "nonexistent",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "not_found"


# ------------------------------------------------------------------
# Metadata mutations
# ------------------------------------------------------------------


def test_set_state(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-state")

    r = h.execute(
        {
            "action": "set_state",
            "tasklist_key": "tl-state",
            "state": TASK_LIST_STATE_RUNNING,
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["state"] == TASK_LIST_STATE_RUNNING


def test_set_state_validate_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-state-vo")

    r = h.execute(
        {
            "action": "set_state",
            "tasklist_key": "tl-state-vo",
            "state": TASK_LIST_STATE_RUNNING,
            "validate_only": True,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r["tasklist"]["state"] == TASK_LIST_STATE_RUNNING

    # Storage should still have the original state
    r2 = h.execute({"action": "get", "tasklist_key": "tl-state-vo", "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    assert r2["tasklist"]["state"] == TASK_LIST_STATE_CREATED


def test_update_meta(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-meta")

    r = h.execute(
        {
            "action": "update_meta",
            "tasklist_key": "tl-meta",
            "meta": {"key1": "val1", "key2": 42},
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["meta"]["key1"] == "val1"
    assert tl["meta"]["key2"] == 42


def test_set_general_instructions(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gi")

    r = h.execute(
        {
            "action": "set_general_instructions",
            "tasklist_key": "tl-gi",
            "instructions": "Follow these steps carefully.",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["general_instructions"] == "Follow these steps carefully."


def test_set_name(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rename")

    r = h.execute(
        {
            "action": "set_name",
            "tasklist_key": "tl-rename",
            "name": "New Name",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["name"] == "New Name"


def test_set_description(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-desc")

    r = h.execute(
        {
            "action": "set_description",
            "tasklist_key": "tl-desc",
            "description": "New description",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["description"] == "New description"


# ------------------------------------------------------------------
# validate_only on mutations
# ------------------------------------------------------------------


def test_add_task_validate_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-add-vo", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    # Add task with validate_only=True
    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-add-vo",
            "task_id": "t2",
            "task_name": "T2",
            "task_instructions": "do 2",
            "validate_only": True,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 2  # returned with task added

    # Verify storage still has original (1 task)
    r2 = h.execute({"action": "get", "tasklist_key": "tl-add-vo", "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    assert len(r2["tasklist"]["tasks"]) == 1


# ------------------------------------------------------------------
# Convenience put (goal path)
# ------------------------------------------------------------------


def test_put_convenience_goal_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "fix-handler-timeout",
            "goal": "Fix the handler timeout bug",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["id"] == "fix-handler-timeout"
    assert tl["name"] == "Fix Handler Timeout"
    assert tl["description"] == "Fix the handler timeout bug"
    assert tl["general_instructions"] == "Fix the handler timeout bug"
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "task-1"
    assert tl["tasks"][0]["name"] == "Execute goal"
    assert tl["tasks"][0]["instructions"] == "Fix the handler timeout bug"


def test_put_convenience_goal_with_files(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "refactor-storage",
            "goal": "Refactor the storage layer",
            "files": ["path/to/file_a.py", "path/to/file_b.py"],
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 2
    assert tl["tasks"][0]["id"] == "task-1"
    assert tl["tasks"][0]["name"] == "file_a"
    assert tl["tasks"][1]["id"] == "task-2"
    assert tl["tasks"][1]["name"] == "file_b"


def test_put_convenience_with_worker_agent(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "deploy-feature",
            "goal": "Deploy the new feature",
            "worker_agent": "colin",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["tasks"][0]["agent"] == "colin"


def test_put_explicit_empty(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "my-custom-list",
            "name": "My Custom List",
            "description": "A test list",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["id"] == "my-custom-list"
    assert tl["name"] == "My Custom List"
    assert tl["description"] == "A test list"
    assert len(tl["tasks"]) == 0


def test_put_explicit_with_general_instructions(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute(
        {
            "action": "put",
            "tasklist_key": "list-with-guide",
            "name": "List With Guide",
            "description": "Has general instructions",
            "general_instructions": "Always check the logs first.",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["general_instructions"] == "Always check the logs first."


def test_put_rejects_neither(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    # No goal, no name+description
    r = h.execute(
        {"action": "put", "tasklist_key": "bad-put", "validate_only": False},
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "missing_fields"


# ------------------------------------------------------------------
# Advanced task features
# ------------------------------------------------------------------


def test_add_task_with_meta(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-meta-task")

    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-meta-task",
            "task_id": "t1",
            "task_name": "Task With Meta",
            "task_instructions": "do it",
            "task_meta": {"priority": "high", "reviewer": "john"},
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["tasks"][0]["meta"]["priority"] == "high"
    assert tl["tasks"][0]["meta"]["reviewer"] == "john"


def test_update_task_partial(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-partial", tasks=[
        {"id": "t1", "name": "Original", "instructions": "original instructions"},
    ])

    r = h.execute(
        {
            "action": "update_task",
            "tasklist_key": "tl-partial",
            "task_id": "t1",
            "task_state": TASK_STATE_COMPLETED,
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    # Only state changed
    assert tl["tasks"][0]["state"] == TASK_STATE_COMPLETED
    # Name and instructions unchanged
    assert tl["tasks"][0]["name"] == "Original"
    assert tl["tasks"][0]["instructions"] == "original instructions"


def test_update_task_with_result_and_error(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-result", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "update_task",
            "tasklist_key": "tl-result",
            "task_id": "t1",
            "task_result": {"ok": True, "output": "done"},
            "task_error": "something went wrong",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert "result" not in tl["tasks"][0]
    assert "run_metrics" not in tl["tasks"][0]
    assert tl["tasks"][0]["error"] == "something went wrong"


def test_add_task_duplicate_id_rejected(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-dup", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-dup",
            "task_id": "t1",
            "task_name": "T1 Again",
            "task_instructions": "do 1 again",
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("action") == "add_task"
    assert r.get("tasklist_key") == "tl-dup"
    assert r.get("error", {}).get("code") == "duplicate_task_id"
    assert r.get("error", {}).get("message") == "task with id 't1' already exists"

    got = h.execute({"action": "get", "tasklist_key": "tl-dup", "validate_only": False}, account_name="alice")
    assert got.get("ok") is True
    tasks = got["tasklist"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["id"] == "t1"
    assert tasks[0]["name"] == "T1"
    assert tasks[0]["instructions"] == "do 1"


def test_add_task_duplicate_id_rejected_with_after_index(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-dup-idx", tasks=[
        {"id": "a", "name": "A", "instructions": "a"},
        {"id": "b", "name": "B", "instructions": "b"},
    ])

    r = h.execute(
        {
            "action": "add_task",
            "tasklist_key": "tl-dup-idx",
            "task_id": "a",
            "task_name": "A Dup",
            "task_instructions": "a again",
            "after_index": 0,
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("action") == "add_task"
    assert r.get("error", {}).get("code") == "duplicate_task_id"
    assert r.get("error", {}).get("message") == "task with id 'a' already exists"

    got = h.execute({"action": "get", "tasklist_key": "tl-dup-idx", "validate_only": False}, account_name="alice")
    assert got.get("ok") is True
    assert [t["id"] for t in got["tasklist"]["tasks"]] == ["a", "b"]


def test_get_result_completed_record_latest_wins(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gr-done", tasks=[
        {"id": "task-1", "name": "T1", "instructions": "do 1"},
    ])

    h.tasklist_service.store.append_task_execution_record(
        "alice",
        "tl-gr-done",
        {
            "schema_version": 1,
            "record_id": "rec-old",
            "tasklist_key": "tl-gr-done",
            "task_id": "task-1",
            "task_name": "T1",
            "state": TASK_STATE_COMPLETED,
            "started": "2026-09-02T14:00:00.000Z",
            "ended": "2026-09-02T14:01:00.000Z",
            "metrics": {"tokens": 10},
            "result": {"timestamp": "2026-09-02T14:01:00.000Z", "output": "first attempt"},
        },
    )
    h.tasklist_service.store.append_task_execution_record(
        "alice",
        "tl-gr-done",
        {
            "schema_version": 1,
            "record_id": "rec-new",
            "tasklist_key": "tl-gr-done",
            "task_id": "task-1",
            "task_name": "T1",
            "state": TASK_STATE_COMPLETED,
            "started": "2026-09-02T15:00:00.000Z",
            "ended": "2026-09-02T15:01:00.000Z",
            "metrics": {"tokens": 12},
            "result": {"timestamp": "2026-09-02T15:01:00.000Z", "output": "second attempt"},
        },
    )

    r = h.execute(
        {"action": "get_result", "tasklist_key": "tl-gr-done", "task_id": "task-1"},
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r.get("action") == "get_result"
    assert r.get("tasklist_key") == "tl-gr-done"
    assert r.get("task_id") == "task-1"
    rec = r.get("result_record")
    assert rec is not None
    assert rec.get("record_id") == "rec-new"
    assert rec.get("state") == TASK_STATE_COMPLETED
    assert rec["result"]["output"] == "second attempt"


def test_get_result_failure_record(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gr-fail", tasks=[
        {"id": "task-1", "name": "T1", "instructions": "do 1"},
    ])

    h.tasklist_service.store.append_task_execution_record(
        "alice",
        "tl-gr-fail",
        {
            "schema_version": 1,
            "record_id": "rec-fail",
            "tasklist_key": "tl-gr-fail",
            "task_id": "task-1",
            "task_name": "T1",
            "state": "failed",
            "started": "2026-09-02T16:00:00.000Z",
            "ended": "2026-09-02T16:05:00.000Z",
            "error": "Model reported it could not complete the task",
            "error_detail": "Traceback (most recent call last):\n  File \"worker.py\", line 42\nValueError: boom",
        },
    )

    r = h.execute(
        {"action": "get_result", "tasklist_key": "tl-gr-fail", "task_id": "task-1"},
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r.get("action") == "get_result"
    rec = r.get("result_record")
    assert rec is not None
    assert rec.get("task_id") == "task-1"
    assert rec.get("state") == "failed"
    assert rec.get("error") == "Model reported it could not complete the task"
    assert rec.get("error_detail", "").startswith("Traceback (most recent call last):")


def test_get_result_legacy_inline_fallback(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gr-legacy", tasks=[
        {"id": "task-1", "name": "T1", "instructions": "do 1"},
    ])

    legacy_path = tmp_path / "ns" / "tasklists" / "alice" / "tl-gr-legacy.json"
    raw = json.loads(legacy_path.read_text(encoding="utf-8"))
    raw["tasks"][0]["state"] = TASK_STATE_COMPLETED
    raw["tasks"][0]["result"] = {"timestamp": "2026-09-02T10:00:00.000Z", "output": "legacy inline output"}
    raw["tasks"][0]["run_metrics"] = {"tokens": 5}
    legacy_path.write_text(json.dumps(raw), encoding="utf-8")

    r = h.execute(
        {"action": "get_result", "tasklist_key": "tl-gr-legacy", "task_id": "task-1"},
        account_name="alice",
    )
    assert r.get("ok") is True
    rec = r.get("result_record")
    assert rec is not None
    assert rec.get("legacy") is True
    assert rec.get("task_id") == "task-1"
    assert rec.get("state") == TASK_STATE_COMPLETED
    assert rec["result"]["output"] == "legacy inline output"
    assert rec["run_metrics"]["tokens"] == 5


def test_get_result_no_result_message(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gr-none", tasks=[
        {"id": "task-1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {"action": "get_result", "tasklist_key": "tl-gr-none", "task_id": "task-1"},
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r.get("action") == "get_result"
    assert r.get("tasklist_key") == "tl-gr-none"
    assert r.get("task_id") == "task-1"
    assert r.get("result_record") is None
    assert r.get("message") == "no result for task task-1"

    r2 = h.execute(
        {"action": "get_result", "tasklist_key": "tl-gr-none", "task_id": "no-such-task"},
        account_name="alice",
    )
    assert r2.get("ok") is True
    assert r2.get("message") == "no result for task no-such-task"


def test_get_result_missing_params(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gr-missing")

    r = h.execute({"action": "get_result"}, account_name="alice")
    assert r.get("ok") is False
    assert r.get("action") == "get_result"
    assert r.get("error", {}).get("code") == "missing_key"

    r2 = h.execute({"action": "get_result", "tasklist_key": "tl-gr-missing"}, account_name="alice")
    assert r2.get("ok") is False
    assert r2.get("action") == "get_result"
    assert r2.get("tasklist_key") == "tl-gr-missing"
    assert r2.get("error", {}).get("code") == "missing_fields"
    assert "task_id" in r2.get("error", {}).get("message", "")
