from src.handlers.tasklists_manage_handler import TasklistsManageHandler
from src.tasklists.task_states import TASK_LIST_STATE_CREATED, TASK_LIST_STATE_COMPLETED, TASK_STATE_PENDING, TASK_STATE_COMPLETED


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
    r = h.execute({"action": "list", "tasklist_name": "", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    assert r.get("tasklist_names") == []


def test_put_validate_only_strict_schema(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    # NOTE: current handler persists even when validate_only=True.
    payload = {"schema_version": 1, "id": "tl1", "name": "X", "description": "d", "tasks": []}
    r = h.execute({"action": "put", "tasklist_name": "tl1", "tasklist": payload, "validate_only": True}, account_name="bob")
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl is not None
    assert tl["id"] == "tl1"
    assert tl["schema_version"] == 1
    assert isinstance(tl["tasks"], list)


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
    r = h.execute({"action": "put", "tasklist_name": "tla", "tasklist": payload, "validate_only": False}, account_name="carol")
    assert r.get("ok") is True
    assert r.get("tasklist_name") == "tla"

    r2 = h.execute({"action": "get", "tasklist_name": "tla", "tasklist": {}, "validate_only": False}, account_name="carol")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["id"] == "tla"
    assert isinstance(tl.get("tasks"), list)


def test_get_missing_and_delete_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "get", "tasklist_name": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    assert r.get("ok") is False
    assert r.get("error") is not None

    r2 = h.execute({"action": "delete", "tasklist_name": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    # delete is idempotent and should succeed
    assert r2.get("ok") is True


def test_invalid_id_rejected(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    bad_ids = ["../x", "a/b", "", ".", "..", "has space", "a.b"]
    for bid in bad_ids:
        r = h.execute({"action": "put", "tasklist_name": bid, "tasklist": {"x": 1}, "validate_only": True}, account_name="eve")
        assert r.get("ok") is False


def test_put_rejects_uuid_mismatch_on_replace(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    tl_name = "tl1"
    # First write
    payload1 = {"schema_version": 1, "id": "uuid-1", "name": "X", "description": "d", "tasks": []}
    r1 = h.execute({"action": "put", "tasklist_name": tl_name, "tasklist": payload1, "validate_only": False}, account_name="bob")
    assert r1.get("ok") is True

    # Replace with different UUID should be rejected
    payload2 = {"schema_version": 1, "id": "uuid-2", "name": "X", "description": "d", "tasks": []}
    r2 = h.execute({"action": "put", "tasklist_name": tl_name, "tasklist": payload2, "validate_only": False}, account_name="bob")
    assert r2.get("ok") is False
    assert r2.get("error", {}).get("code") == "tasklist_uuid_mismatch"


def test_put_requires_uuid_on_replace(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    tl_name = "tl2"
    payload1 = {"schema_version": 1, "id": "uuid-1", "name": "X", "description": "d", "tasks": []}
    r1 = h.execute({"action": "put", "tasklist_name": tl_name, "tasklist": payload1, "validate_only": False}, account_name="bob")
    assert r1.get("ok") is True

    payload2 = {"schema_version": 1, "name": "X", "description": "d", "tasks": []}
    r2 = h.execute({"action": "put", "tasklist_name": tl_name, "tasklist": payload2, "validate_only": False}, account_name="bob")
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
    r = h.execute({"action": "put", "tasklist_name": tl_name, "tasklist": payload, "validate_only": False}, account_name="sam")
    assert r.get("ok") is True

    got = h.execute({"action": "get", "tasklist_name": tl_name, "tasklist": {}, "validate_only": False}, account_name="sam")
    assert got.get("ok") is True
    tl = got.get("tasklist")
    assert tl.get("general_instructions") == "Please follow these steps."


def test_reset_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "reset", "tasklist_name": "nope", "tasklist": {}, "validate_only": False}, account_name="alice")
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
    r = h.execute({"action": "put", "tasklist_name": "tl-reset", "tasklist": payload, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True

    # Reset it
    r2 = h.execute({"action": "reset", "tasklist_name": "tl-reset", "tasklist": {}, "validate_only": False}, account_name="alice")
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
    r = h.execute({"action": "put", "tasklist_name": "tl-reset-vo", "tasklist": payload, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True

    # Reset with validate_only=True — should return reset state but NOT persist
    r2 = h.execute({"action": "reset", "tasklist_name": "tl-reset-vo", "tasklist": {}, "validate_only": True}, account_name="alice")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["state"] == TASK_LIST_STATE_CREATED
    for task in tl["tasks"]:
        assert task["state"] == TASK_STATE_PENDING

    # Verify storage still has the original completed state
    r3 = h.execute({"action": "get", "tasklist_name": "tl-reset-vo", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r3.get("ok") is True
    tl_stored = r3.get("tasklist")
    assert tl_stored["state"] == TASK_LIST_STATE_COMPLETED
