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


def test_list_empty(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    r = h.execute({"action": "list", "tasklist_key": "", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    assert r.get("tasklist_keys") == []


def test_put_validate_only_does_not_persist(tmp_path):
    """validate_only=True must validate, return the payload, but NOT write to storage."""
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    payload = {"schema_version": 1, "id": "tl1", "name": "X", "description": "d", "tasks": []}
    r = h.execute(
        {"action": "put", "tasklist_key": "tl1", "tasklist": payload, "validate_only": True},
        account_name="bob",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl is not None
    assert tl["id"] == "tl1"

    # Storage must NOT contain the tasklist
    r2 = h.execute(
        {"action": "get", "tasklist_key": "tl1", "tasklist": {}, "validate_only": False},
        account_name="bob",
    )
    assert r2.get("ok") is False
    assert r2.get("error", {}).get("code") == "not_found"


def test_put_persists_and_get(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    payload = {
        "schema_version": 1,
        "id": "tla",
        "name": "List A",
        "description": "d",
        "tasks": [{"id": "task-1", "name": "T1", "instructions": "do it"}],
    }
    r = h.execute({"action": "put", "tasklist_key": "tla", "tasklist": payload, "validate_only": False}, account_name="carol")
    assert r.get("ok") is True
    assert r.get("tasklist_key") == "tla"

    r2 = h.execute({"action": "get", "tasklist_key": "tla", "tasklist": {}, "validate_only": False}, account_name="carol")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["id"] == "tla"
    assert isinstance(tl.get("tasks"), list)


def test_get_missing_and_delete_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "get", "tasklist_key": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    assert r.get("ok") is False
    assert r.get("error") is not None

    r2 = h.execute({"action": "delete", "tasklist_key": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    # delete is idempotent and should succeed
    assert r2.get("ok") is True


def test_invalid_id_rejected(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    bad_ids = ["../x", "a/b", "", ".", "..", "has space", "a.b"]
    for bid in bad_ids:
        r = h.execute({"action": "put", "tasklist_key": bid, "tasklist": {"x": 1}, "validate_only": True}, account_name="eve")
        assert r.get("ok") is False


def test_put_rejects_uuid_mismatch_on_replace(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    tl_name = "tl1"
    # First write
    payload1 = {"schema_version": 1, "id": "uuid-1", "name": "X", "description": "d", "tasks": []}
    r1 = h.execute({"action": "put", "tasklist_key": tl_name, "tasklist": payload1, "validate_only": False}, account_name="bob")
    assert r1.get("ok") is True

    # Replace with different UUID should be rejected
    payload2 = {"schema_version": 1, "id": "uuid-2", "name": "X", "description": "d", "tasks": []}
    r2 = h.execute({"action": "put", "tasklist_key": tl_name, "tasklist": payload2, "validate_only": False}, account_name="bob")
    assert r2.get("ok") is False
    assert r2.get("error", {}).get("code") == "tasklist_uuid_mismatch"


def test_put_requires_uuid_on_replace(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    tl_name = "tl2"
    payload1 = {"schema_version": 1, "id": "uuid-1", "name": "X", "description": "d", "tasks": []}
    r1 = h.execute({"action": "put", "tasklist_key": tl_name, "tasklist": payload1, "validate_only": False}, account_name="bob")
    assert r1.get("ok") is True

    payload2 = {"schema_version": 1, "name": "X", "description": "d", "tasks": []}
    r2 = h.execute({"action": "put", "tasklist_key": tl_name, "tasklist": payload2, "validate_only": False}, account_name="bob")
    assert r2.get("ok") is False
    # The handler validates the payload before checking for replacement id, so
    # a missing id will currently surface as invalid_tasklist.
    assert r2.get("error", {}).get("code") == "invalid_tasklist"


def test_general_instructions_roundtrip(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    tl_name = "tl-generic"
    payload = {
        "schema_version": 1,
        "id": "tlg",
        "name": "TL G",
        "description": "desc",
        "general_instructions": "Please follow these steps.",
        "tasks": [],
    }
    r = h.execute({"action": "put", "tasklist_key": tl_name, "tasklist": payload, "validate_only": False}, account_name="sam")
    assert r.get("ok") is True

    got = h.execute({"action": "get", "tasklist_key": tl_name, "tasklist": {}, "validate_only": False}, account_name="sam")
    assert got.get("ok") is True
    tl = got.get("tasklist")
    assert tl.get("general_instructions") == "Please follow these steps."


def test_reset_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "reset", "tasklist_key": "nope", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "not_found"


def test_reset_clears_states(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    # Create a completed tasklist
    payload = {
        "schema_version": 1,
        "id": "tl-reset",
        "name": "Reset Test",
        "description": "desc",
        "state": TASK_LIST_STATE_COMPLETED,
        "current_task_id": "task-2",
        "tasks": [
            {"id": "task-1", "name": "T1", "instructions": "do 1", "state": TASK_STATE_COMPLETED, "result": {"ok": True}, "error": None},
            {"id": "task-2", "name": "T2", "instructions": "do 2", "state": TASK_STATE_COMPLETED, "result": {"ok": True}, "error": None},
        ],
    }
    r = h.execute({"action": "put", "tasklist_key": "tl-reset", "tasklist": payload, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True

    # Reset it
    r2 = h.execute({"action": "reset", "tasklist_key": "tl-reset", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
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

    payload = {
        "schema_version": 1,
        "id": "tl-reset-vo",
        "name": "Reset VO",
        "description": "desc",
        "state": TASK_LIST_STATE_COMPLETED,
        "tasks": [
            {"id": "task-1", "name": "T1", "instructions": "do 1", "state": TASK_STATE_COMPLETED, "result": {"ok": True}},
        ],
    }
    r = h.execute({"action": "put", "tasklist_key": "tl-reset-vo", "tasklist": payload, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True

    # Reset with validate_only=True — should return reset state but NOT persist
    r2 = h.execute({"action": "reset", "tasklist_key": "tl-reset-vo", "tasklist": {}, "validate_only": True}, account_name="alice")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["state"] == TASK_LIST_STATE_CREATED
    for task in tl["tasks"]:
        assert task["state"] == TASK_STATE_PENDING

    # Verify storage still has the original completed state
    r3 = h.execute({"action": "get", "tasklist_key": "tl-reset-vo", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r3.get("ok") is True
    tl_stored = r3.get("tasklist")
    assert tl_stored["state"] == TASK_LIST_STATE_COMPLETED


# ------------------------------------------------------------------
# Patch action tests
# ------------------------------------------------------------------


def _create_tl(h, account, name, tasks=None):
    """Helper: create a simple tasklist and return its name."""
    payload = {
        "schema_version": 1,
        "id": name,
        "name": name,
        "description": "test",
        "tasks": tasks or [],
    }
    r = h.execute({"action": "put", "tasklist_key": name, "tasklist": payload, "validate_only": False}, account_name=account)
    assert r.get("ok") is True
    return name


def test_patch_missing_key(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    r = h.execute({"action": "patch", "tasklist_key": "", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "missing_key"


def test_patch_not_found(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    r = h.execute(
        {"action": "patch", "tasklist_key": "nope", "tasklist": {"operations": [{"op": "set_name", "name": "X"}]}, "validate_only": False},
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "not_found"


def test_patch_empty_operations(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-empty-op")
    r = h.execute(
        {"action": "patch", "tasklist_key": "tl-empty-op", "tasklist": {"operations": []}, "validate_only": False},
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "empty_operations"


def test_patch_add_task_append(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-add-append")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-add-append",
            "tasklist": {
                "operations": [
                    {"op": "add_task", "task": {"id": "t1", "name": "Task 1", "instructions": "do step 1"}},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "t1"


def test_patch_add_task_at_index(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-add-idx", tasks=[
        {"id": "a", "name": "A", "instructions": "a"},
        {"id": "b", "name": "B", "instructions": "b"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-add-idx",
            "tasklist": {
                "operations": [
                    {"op": "add_task", "after_index": 0, "task": {"id": "c", "name": "C", "instructions": "c"}},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 3
    # C should be inserted after index 0, so at position 1
    assert tl["tasks"][1]["id"] == "c"


def test_patch_update_task(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-upd", tasks=[
        {"id": "t1", "name": "Old Name", "instructions": "old"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-upd",
            "tasklist": {
                "operations": [
                    {"op": "update_task", "task_id": "t1", "task": {"name": "New Name", "instructions": "new instructions"}},
                ]
            },
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


def test_patch_update_task_not_found(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-upd-nf", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-upd-nf",
            "tasklist": {
                "operations": [
                    {"op": "update_task", "task_id": "nonexistent", "task": {"name": "X"}},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "operation_failed"


def test_patch_remove_task(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rm", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
        {"id": "t2", "name": "T2", "instructions": "do 2"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-rm",
            "tasklist": {
                "operations": [
                    {"op": "remove_task", "task_id": "t1"},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 1
    assert tl["tasks"][0]["id"] == "t2"


def test_patch_remove_task_not_found(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rm-nf", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-rm-nf",
            "tasklist": {
                "operations": [
                    {"op": "remove_task", "task_id": "nonexistent"},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "operation_failed"


def test_patch_set_state(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-state")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-state",
            "tasklist": {
                "operations": [
                    {"op": "set_state", "state": TASK_LIST_STATE_RUNNING},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["state"] == TASK_LIST_STATE_RUNNING


def test_patch_set_state_validate_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-state-vo")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-state-vo",
            "tasklist": {
                "operations": [
                    {"op": "set_state", "state": TASK_LIST_STATE_RUNNING},
                ]
            },
            "validate_only": True,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    assert r["tasklist"]["state"] == TASK_LIST_STATE_RUNNING

    # Storage should still have the original state
    r2 = h.execute({"action": "get", "tasklist_key": "tl-state-vo", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    assert r2["tasklist"]["state"] == TASK_LIST_STATE_CREATED


def test_patch_update_meta(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-meta")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-meta",
            "tasklist": {
                "operations": [
                    {"op": "update_meta", "meta": {"key1": "val1", "key2": 42}},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["meta"]["key1"] == "val1"
    assert tl["meta"]["key2"] == 42


def test_patch_set_general_instructions(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-gi")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-gi",
            "tasklist": {
                "operations": [
                    {"op": "set_general_instructions", "instructions": "Follow these steps carefully."},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["general_instructions"] == "Follow these steps carefully."


def test_patch_set_name(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-rename")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-rename",
            "tasklist": {
                "operations": [
                    {"op": "set_name", "name": "New Name"},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["name"] == "New Name"


def test_patch_set_description(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-desc")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-desc",
            "tasklist": {
                "operations": [
                    {"op": "set_description", "description": "New description"},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl["description"] == "New description"


def test_patch_unknown_operation(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-unknown-op")

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-unknown-op",
            "tasklist": {
                "operations": [
                    {"op": "do_something_weird"},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is False
    assert r.get("error", {}).get("code") == "operation_failed"


def test_patch_multiple_operations(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-multi", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-multi",
            "tasklist": {
                "operations": [
                    {"op": "add_task", "task": {"id": "t2", "name": "T2", "instructions": "do 2"}},
                    {"op": "update_task", "task_id": "t1", "task": {"instructions": "updated 1"}},
                    {"op": "set_general_instructions", "instructions": "General guide"},
                    {"op": "update_meta", "meta": {"source": "test"}},
                ]
            },
            "validate_only": False,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 2
    assert tl["tasks"][0]["instructions"] == "updated 1"
    assert tl["tasks"][1]["id"] == "t2"
    assert tl["general_instructions"] == "General guide"
    assert tl["meta"]["source"] == "test"


def test_patch_validate_only(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-patch-vo", tasks=[
        {"id": "t1", "name": "T1", "instructions": "do 1"},
    ])

    # Patch with validate_only=True
    r = h.execute(
        {
            "action": "patch",
            "tasklist_key": "tl-patch-vo",
            "tasklist": {
                "operations": [
                    {"op": "add_task", "task": {"id": "t2", "name": "T2", "instructions": "do 2"}},
                ]
            },
            "validate_only": True,
        },
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 2  # returned with patch applied

    # Verify storage still has original (1 task)
    r2 = h.execute({"action": "get", "tasklist_key": "tl-patch-vo", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r2.get("ok") is True
    assert len(r2["tasklist"]["tasks"]) == 1


def test_patch_json_string_payload(tmp_path):
    """Patch should accept a JSON string payload."""
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)
    _create_tl(h, "alice", "tl-json-str")

    import json
    payload_str = json.dumps({
        "operations": [
            {"op": "add_task", "task": {"id": "t1", "name": "T1", "instructions": "do it"}},
        ]
    })
    r = h.execute(
        {"action": "patch", "tasklist_key": "tl-json-str", "tasklist": payload_str, "validate_only": False},
        account_name="alice",
    )
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert len(tl["tasks"]) == 1
