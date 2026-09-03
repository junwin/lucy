import json
import os
import time

from src.storage_paths.storage_paths import StoragePaths
from src.storage.json_file_storage import JsonFileStorage
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_LIST_STATE_CREATED,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_PENDING,
)


def make_storage(tmp_path, ns="ns"):
    sp = StoragePaths(str(tmp_path), ns)
    return JsonFileStorage(sp)


def _write_raw_tasklist(storage, account_name, tasklist_key, tasks):
    path = storage._tasklist_path(account_name, tasklist_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "id": tasklist_key,
        "name": "n",
        "description": "d",
        "tasks": tasks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def test_invalid_tasklist_key_rejected(tmp_path):
    storage = make_storage(tmp_path)
    for bad in ["../x", "a/b", "a\\b", "", ".", "..", "has space", "weird!", "a.b"]:
        try:
            storage.save_tasklist("alice", bad, {"schema_version": 1, "id": "x", "name": "n", "description": "d", "tasks": []})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected ValueError for key={bad!r}")


def test_id_auto_set_to_match_key(tmp_path):
    # JsonFileStorage.save_tasklist enforces key == id: if the payload's
    # internal id differs from the storage key, it is auto-set to match.
    storage = make_storage(tmp_path)
    storage.save_tasklist(
        "alice",
        "tl1",
        {"schema_version": 1, "id": "other", "name": "n", "description": "d", "tasks": []},
    )
    tl = storage.get_tasklist("alice", "tl1")
    assert tl.id == "tl1"


def test_save_all_pending_persists_created_state(tmp_path):
    storage = make_storage(tmp_path)
    payload = {
        "schema_version": 1,
        "id": "tlpending",
        "name": "n",
        "description": "d",
        "state": "Created",
        "tasks": [
            {"id": "t1", "name": "T1", "instructions": "do", "state": "Pending"},
        ],
    }
    storage.save_tasklist("alice", "tlpending", payload)

    tl = storage.get_tasklist("alice", "tlpending")
    assert tl.state == TASK_LIST_STATE_CREATED
    assert tl.tasks[0].state == TASK_STATE_PENDING


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


def test_save_tasklist_adopts_legacy_run_metrics(tmp_path):
    storage = make_storage(tmp_path)
    metrics = {"iterations": 40, "openai_calls": 40, "total_tokens": 12345}
    payload = {
        "schema_version": 1,
        "id": "tlrunmetrics",
        "name": "n",
        "description": "d",
        "tasks": [{"id": "t1", "name": "T1", "instructions": "do", "run_metrics": metrics}],
    }
    storage.save_tasklist("alice", "tlrunmetrics", payload)

    tl = storage.get_tasklist("alice", "tlrunmetrics")
    assert tl is not None
    assert tl.tasks[0].run_metrics is None

    record = storage.get_task_result("alice", "tlrunmetrics", "t1")
    assert record is not None
    assert record["legacy"] is True
    assert record["run_metrics"] == metrics


def test_save_tasklist_adopts_legacy_inline_fields_into_runs_file(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tladopt"
    completed = {
        "id": "t1",
        "name": "T1",
        "instructions": "do",
        "state": TASK_STATE_COMPLETED,
        "result": {"output": "big output"},
        "run_metrics": {"iterations": 3, "total_tokens": 100},
    }
    failed = {
        "id": "t2",
        "name": "T2",
        "instructions": "do",
        "state": TASK_STATE_FAILED,
        "error": "boom",
        "result": {"output": "partial"},
    }
    plain = {"id": "t3", "name": "T3", "instructions": "do"}
    path = _write_raw_tasklist(storage, account, key, [completed, failed, plain])

    tl = storage.get_tasklist(account, key)
    assert tl.tasks[0].result == {"output": "big output"}
    storage.save_tasklist(account, key, tl)

    runs_path = storage._tasklist_runs_path(account, key)
    records = [
        json.loads(line)
        for line in runs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 2
    by_task = {r["task_id"]: r for r in records}
    assert set(by_task) == {"t1", "t2"}

    t1 = by_task["t1"]
    assert t1["schema_version"] == 1
    assert t1["record_id"]
    assert t1["tasklist_key"] == key
    assert t1["task_name"] == "T1"
    assert t1["state"] == TASK_STATE_COMPLETED
    assert t1["error"] is None
    assert t1["legacy"] is True
    assert t1["result"] == {"output": "big output"}
    assert t1["run_metrics"] == {"iterations": 3, "total_tokens": 100}

    t2 = by_task["t2"]
    assert t2["legacy"] is True
    assert t2["state"] == TASK_STATE_FAILED
    assert t2["error"] == "boom"
    assert t2["result"] == {"output": "partial"}
    assert t2["run_metrics"] is None

    saved = json.loads(path.read_text(encoding="utf-8"))
    saved_by_id = {t["id"]: t for t in saved["tasks"]}
    assert saved_by_id["t1"].get("result") is None
    assert "run_metrics" not in saved_by_id["t1"]
    assert saved_by_id["t2"].get("result") is None
    assert "run_metrics" not in saved_by_id["t2"]
    assert saved_by_id["t2"]["error"] == "boom"
    assert saved_by_id["t2"]["state"] == TASK_STATE_FAILED
    assert "run_metrics" not in saved_by_id["t3"]


def test_save_tasklist_adoption_is_idempotent(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tlidem"
    legacy = {
        "id": "t1",
        "name": "T1",
        "instructions": "do",
        "state": TASK_STATE_COMPLETED,
        "result": {"output": "once"},
        "run_metrics": {"iterations": 1},
    }
    _write_raw_tasklist(storage, account, key, [legacy])

    def run_record_count():
        runs_path = storage._tasklist_runs_path(account, key)
        if not runs_path.exists():
            return 0
        return len([line for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()])

    tl = storage.get_tasklist(account, key)
    storage.save_tasklist(account, key, tl)
    assert run_record_count() == 1

    storage.save_tasklist(account, key, tl)
    assert run_record_count() == 1

    reloaded = storage.get_tasklist(account, key)
    assert reloaded.tasks[0].result is None
    assert reloaded.tasks[0].run_metrics is None
    storage.save_tasklist(account, key, reloaded)
    assert run_record_count() == 1


def test_tasklist_runs_path_is_safe_sibling_of_tasklist_json(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tl1"
    payload = {
        "schema_version": 1,
        "id": key,
        "name": "n",
        "description": "d",
        "tasks": [],
    }
    storage.save_tasklist(account, key, payload)

    json_path = storage._tasklist_path(account, key)
    runs_path = storage._tasklist_runs_path(account, key)

    assert runs_path == json_path.parent / f"{key}.runs.jsonl"
    assert runs_path.parent == json_path.parent
    assert json_path.exists()
    assert not runs_path.exists()

    for method in (storage._tasklist_path, storage._tasklist_runs_path):
        try:
            method(account, "../../../escape")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for escaping tasklist key")
        try:
            method("../../..", key)
        except ValueError:
            pass
        else:
            raise AssertionError("Expected ValueError for escaping account name")

def test_append_task_execution_record_writes_jsonl_line(tmp_path):
    storage = make_storage(tmp_path)
    payload = {"schema_version": 1, "id": "tlruns", "name": "n", "description": "d", "tasks": []}
    storage.save_tasklist("alice", "tlruns", payload)

    storage.append_task_execution_record(
        "alice",
        "tlruns",
        {"record_id": "r1", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "one"}},
    )
    storage.append_task_execution_record(
        "alice",
        "tlruns",
        {"record_id": "r2", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "two"}},
    )

    runs_path = storage._tasklist_runs_path("alice", "tlruns")
    assert runs_path.exists()
    lines = [line for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2

    got = storage.get_task_result("alice", "tlruns", "t1")
    assert got == {"record_id": "r2", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "two"}}


def test_get_task_result_returns_latest_record_for_task(tmp_path):
    storage = make_storage(tmp_path)
    task = Task(id="t1", name="T1", instructions="do")
    tasklist = TaskList(id="tllatest", name="n", description="d", tasks=[task])
    storage.save_tasklist("alice", "tllatest", tasklist)

    storage.append_task_execution_record("alice", "tllatest", {"record_id": "r1", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "first"}})
    storage.append_task_execution_record("alice", "tllatest", {"record_id": "r2", "task_id": "other", "state": TASK_STATE_COMPLETED, "result": {"output": "irrelevant"}})
    storage.append_task_execution_record("alice", "tllatest", {"record_id": "r3", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "last"}})

    got = storage.get_task_result("alice", "tllatest", "t1")
    assert got == {"record_id": "r3", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "last"}}


def test_get_task_result_legacy_inline_fallback(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tllegacy"
    failed = {
        "id": "t1",
        "name": "T1",
        "instructions": "do",
        "state": TASK_STATE_FAILED,
        "error": "boom",
        "result": {"output": "partial"},
        "run_metrics": {"iterations": 2},
    }
    _write_raw_tasklist(storage, account, key, [failed])

    got = storage.get_task_result(account, key, "t1")
    assert got == {
        "legacy": True,
        "task_id": "t1",
        "state": TASK_STATE_FAILED,
        "error": "boom",
        "result": {"output": "partial"},
        "run_metrics": {"iterations": 2},
    }


def test_get_task_result_prefers_record_over_legacy_inline(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tlprefer"
    legacy = {
        "id": "t1",
        "name": "T1",
        "instructions": "do",
        "state": TASK_STATE_COMPLETED,
        "result": {"output": "old"},
    }
    _write_raw_tasklist(storage, account, key, [legacy])

    storage.append_task_execution_record(account, key, {"record_id": "r9", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "new"}})

    got = storage.get_task_result(account, key, "t1")
    assert got == {"record_id": "r9", "task_id": "t1", "state": TASK_STATE_COMPLETED, "result": {"output": "new"}}


def test_get_task_result_none_when_no_record_and_no_legacy(tmp_path):
    storage = make_storage(tmp_path)
    assert storage.get_task_result("alice", "missing", "t1") is None

    task = Task(id="t1", name="T1", instructions="do")
    tasklist = TaskList(id="tlplain", name="n", description="d", tasks=[task])
    storage.save_tasklist("alice", "tlplain", tasklist)
    assert storage.get_task_result("alice", "tlplain", "t1") is None
    assert storage.get_task_result("alice", "tlplain", "unknown-task") is None


def test_append_task_execution_record_creates_runs_file_without_tasklist_json(tmp_path):
    storage = make_storage(tmp_path)
    runs_path = storage._tasklist_runs_path("bob", "tlx")
    assert not runs_path.exists()

    storage.append_task_execution_record("bob", "tlx", {"record_id": "r1", "task_id": "t1", "state": TASK_STATE_COMPLETED})

    assert runs_path.exists()
    assert runs_path.read_text(encoding="utf-8").strip() != ""
    assert storage.get_task_result("bob", "tlx", "t1") is None


def test_list_tasklists_ttl_sweep_removes_stale_runs_files(tmp_path):
    storage = make_storage(tmp_path)
    storage._tasklist_run_ttl_days = 1
    account = "alice"
    fresh_key, stale_key = "tlfresh", "tlstale"
    for key in (fresh_key, stale_key):
        storage.save_tasklist(account, key, {"schema_version": 1, "id": key, "name": "n", "description": "d", "tasks": []})
        runs_path = storage._tasklist_runs_path(account, key)
        runs_path.parent.mkdir(parents=True, exist_ok=True)
        runs_path.write_text("{}", encoding="utf-8")

    old_mtime = time.time() - 2 * 86400
    os.utime(storage._tasklist_runs_path(account, stale_key), (old_mtime, old_mtime))

    assert storage.list_tasklists(account) == [fresh_key, stale_key]
    assert storage._tasklist_runs_path(account, fresh_key).exists()
    assert not storage._tasklist_runs_path(account, stale_key).exists()


def test_delete_tasklist_removes_runs_file_sibling(tmp_path):
    storage = make_storage(tmp_path)
    account, key = "alice", "tldelruns"
    storage.save_tasklist(account, key, {"schema_version": 1, "id": key, "name": "n", "description": "d", "tasks": []})
    runs_path = storage._tasklist_runs_path(account, key)
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    runs_path.write_text("{}", encoding="utf-8")
    assert storage._tasklist_path(account, key).exists()
    assert runs_path.exists()

    storage.delete_tasklist(account, key)

    assert not storage._tasklist_path(account, key).exists()
    assert not runs_path.exists()
    assert storage.list_tasklists(account) == []
