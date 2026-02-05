from src.handlers.tasklists_manage_handler import TasklistsManageHandler


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
    r = h.execute({"action": "list", "tasklist_id": "", "tasklist": {}, "validate_only": False}, account_name="alice")
    assert r.get("ok") is True
    assert r.get("tasklist_ids") == []


def test_put_validate_only_and_canonicalization(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    payload = {"title": "X"}  # missing tasks/schema_version -> canonicalized
    r = h.execute({"action": "put", "tasklist_id": "tl1", "tasklist": payload, "validate_only": True}, account_name="bob")
    assert r.get("ok") is True
    tl = r.get("tasklist")
    assert tl is not None
    assert tl["id"] == "tl1"
    assert tl["schema_version"] == 1
    assert isinstance(tl["tasks"], list)

    # ensure not persisted
    r2 = h.execute({"action": "list", "tasklist_id": "", "tasklist": {}, "validate_only": False}, account_name="bob")
    assert r2.get("tasklist_ids") == []


def test_put_persists_and_get(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    payload = {"tasks": [{"id": "task-1", "type": "task"}]}
    r = h.execute({"action": "put", "tasklist_id": "tla", "tasklist": payload, "validate_only": False}, account_name="carol")
    assert r.get("ok") is True
    assert r.get("tasklist_id") == "tla"

    r2 = h.execute({"action": "get", "tasklist_id": "tla", "tasklist": {}, "validate_only": False}, account_name="carol")
    assert r2.get("ok") is True
    tl = r2.get("tasklist")
    assert tl["id"] == "tla"
    assert isinstance(tl.get("tasks"), list)


def test_get_missing_and_delete_missing(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    r = h.execute({"action": "get", "tasklist_id": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    assert r.get("ok") is False
    assert r.get("error") is not None

    r2 = h.execute({"action": "delete", "tasklist_id": "nope", "tasklist": {}, "validate_only": False}, account_name="dave")
    # delete is idempotent and should succeed
    assert r2.get("ok") is True


def test_invalid_id_rejected(tmp_path):
    cfg = SimpleConfig(str(tmp_path), "ns")
    h = TasklistsManageHandler(cfg)

    bad_ids = ["../x", "a/b", "", ".", "..", "has space", "a.b"]
    for bid in bad_ids:
        r = h.execute({"action": "put", "tasklist_id": bid, "tasklist": {"x": 1}, "validate_only": True}, account_name="eve")
        assert r.get("ok") is False

