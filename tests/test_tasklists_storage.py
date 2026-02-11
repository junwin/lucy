from src.storage_paths.storage_paths import StoragePaths
from src.storage.json_file_storage import JsonFileStorage
from src.tasklists.task_list import TaskList


def make_storage(tmp_path, ns="ns"):
    sp = StoragePaths(str(tmp_path), ns)
    return JsonFileStorage(sp)


def test_save_and_get_tasklist_roundtrip(tmp_path):
    storage = make_storage(tmp_path)
    payload = {
        "schema_version": 1,
        "id": "tl1",
        "name": "My Tasks",
        "description": "d",
        "tasks": [],
    }
    storage.save_tasklist("alice", "tl1", payload)

    ids = storage.list_tasklists("alice")
    assert ids == ["tl1"]

    tl = storage.get_tasklist("alice", "tl1")
    assert isinstance(tl, TaskList)
    assert tl.id == "tl1"
    assert tl.schema_version == 1
    assert tl.tasks == []
    assert tl.name == "My Tasks"
    assert tl.description == "d"


def test_delete_tasklist_and_idempotent(tmp_path):
    storage = make_storage(tmp_path)
    payload = {"schema_version": 1, "id": "todelete", "name": "n", "description": "d", "tasks": []}
    storage.save_tasklist("carol", "todelete", payload)
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
            storage.save_tasklist("alice", bad, {"schema_version": 1, "id": "x", "name": "n", "description": "d", "tasks": []})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for id={bad!r}")


def test_id_mismatch_is_allowed_by_storage(tmp_path):
    # Current JsonFileStorage.save_tasklist does not enforce that the payload's
    # internal id matches the filename/tasklist_name.
    storage = make_storage(tmp_path)
    storage.save_tasklist(
        "alice",
        "tl1",
        {"schema_version": 1, "id": "other", "name": "n", "description": "d", "tasks": []},
    )
    tl = storage.get_tasklist("alice", "tl1")
    assert tl.id == "other"


def test_save_and_get_tasklist_with_meta(tmp_path):
    storage = make_storage(tmp_path)
    payload = {
        "schema_version": 1,
        "id": "tlmeta",
        "name": "n",
        "description": "d",
        "state": "Created",
        "tasks": [],
        "meta": {"supervisor_agent": "super", "notes": "from test"},
    }
    storage.save_tasklist("alice", "tlmeta", payload)

    ids = storage.list_tasklists("alice")
    assert ids == ["tlmeta"]

    tl = storage.get_tasklist("alice", "tlmeta")
    assert isinstance(tl, TaskList)
    assert tl.id == "tlmeta"
    assert tl.meta["supervisor_agent"] == "super"
    assert tl.meta["notes"] == "from test"
