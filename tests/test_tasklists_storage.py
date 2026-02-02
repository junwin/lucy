from src.storage_paths.storage_paths import StoragePaths
from src.storage.json_file_storage import JsonFileStorage


def make_storage(tmp_path, ns="ns"):
    sp = StoragePaths(str(tmp_path), ns)
    return JsonFileStorage(sp)


def test_save_and_get_tasklist_dict(tmp_path):
    storage = make_storage(tmp_path)
    storage.save_tasklist("alice", "tl1", {"title": "My Tasks", "items": ["a", "b"]})

    ids = storage.list_tasklists("alice")
    assert ids == ["tl1"]

    data = storage.get_tasklist("alice", "tl1")
    assert isinstance(data, dict)
    assert data["id"] == "tl1"
    assert data["schema_version"] == 1
    assert data["tasks"] == []
    assert data["title"] == "My Tasks"
    assert data["items"] == ["a", "b"]


def test_save_tasklist_string_stores_value(tmp_path):
    storage = make_storage(tmp_path)
    storage.save_tasklist("bob", "s1", "hello world")

    ids = storage.list_tasklists("bob")
    assert ids == ["s1"]

    data = storage.get_tasklist("bob", "s1")
    assert data["id"] == "s1"
    assert data["schema_version"] == 1
    assert data["tasks"] == []
    assert data["value"] == "hello world"


def test_delete_tasklist_and_idempotent(tmp_path):
    storage = make_storage(tmp_path)
    storage.save_tasklist("carol", "todelete", {"x": 1})
    assert storage.list_tasklists("carol") == ["todelete"]

    storage.delete_tasklist("carol", "todelete")
    assert storage.list_tasklists("carol") == []

    # deleting again should not raise
    storage.delete_tasklist("carol", "todelete")
    assert storage.list_tasklists("carol") == []


def test_invalid_tasklist_id_rejected(tmp_path):
    storage = make_storage(tmp_path)
    for bad in ["../x", "a/b", "a\\b", "", ".", "..", "has space", "weird!", "a.b"]:
        try:
            storage.save_tasklist("alice", bad, {"x": 1})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for id={bad!r}")


def test_id_mismatch_rejected(tmp_path):
    storage = make_storage(tmp_path)
    try:
        storage.save_tasklist("alice", "tl1", {"id": "other", "tasks": []})
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for id mismatch")


def test_save_and_get_tasklist_with_meta(tmp_path):
    storage = make_storage(tmp_path)
    payload = {"schema_version": 1, "state": "Created", "tasks": [], "meta": {"supervisor_agent": "super", "notes": "from test"}}
    storage.save_tasklist("alice", "tlmeta", payload)

    ids = storage.list_tasklists("alice")
    assert ids == ["tlmeta"]

    data = storage.get_tasklist("alice", "tlmeta")
    assert isinstance(data, dict)
    assert data["id"] == "tlmeta"
    assert data["meta"]["supervisor_agent"] == "super"
    assert data["meta"]["notes"] == "from test"
