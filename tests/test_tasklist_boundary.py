import json

from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.service import TaskListService
from src.tasklists.task_states import (
    TASK_LIST_STATE_COMPLETED,
    TASK_LIST_STATE_CREATED,
    TASK_STATE_COMPLETED,
    TASK_STATE_PENDING,
)


def _make_storage(tmp_path):
    return JsonFileStorage(StoragePaths(str(tmp_path), "ns"))


def _write_raw_tasklist(storage, account_name, tasklist_key, tasks):
    path = storage._tasklist_path(account_name, tasklist_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "id": tasklist_key,
        "name": "n",
        "description": "d",
        "state": TASK_LIST_STATE_COMPLETED,
        "tasks": tasks,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_reset_of_legacy_inline_fields_adopts_into_runs_and_leaves_lean_file(tmp_path):
    storage = _make_storage(tmp_path)
    account, key = "alice", "tl-reset-legacy"
    legacy_task = {
        "id": "t1",
        "name": "T1",
        "instructions": "do",
        "state": TASK_STATE_COMPLETED,
        "result": {"output": "kept"},
        "run_metrics": {"iterations": 3, "total_tokens": 100},
    }
    path = _write_raw_tasklist(storage, account, key, [legacy_task])

    svc = TaskListService(storage)
    tl = svc.get(account, key)
    assert tl.tasks[0].result == {"output": "kept"}
    assert tl.tasks[0].run_metrics == {"iterations": 3, "total_tokens": 100}

    svc.reset(tl)
    assert tl.state == TASK_LIST_STATE_CREATED
    assert tl.tasks[0].state == TASK_STATE_PENDING
    assert tl.tasks[0].error is None
    assert tl.tasks[0].result == {"output": "kept"}
    assert tl.tasks[0].run_metrics == {"iterations": 3, "total_tokens": 100}

    svc.save(account, key, tl)

    runs_path = storage._tasklist_runs_path(account, key)
    records = [
        json.loads(line)
        for line in runs_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    record = records[0]
    assert record["legacy"] is True
    assert record["task_id"] == "t1"
    assert record["result"] == {"output": "kept"}
    assert record["run_metrics"] == {"iterations": 3, "total_tokens": 100}

    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["state"] == TASK_LIST_STATE_CREATED
    saved_task = saved["tasks"][0]
    assert saved_task["state"] == TASK_STATE_PENDING
    assert saved_task["error"] is None
    assert saved_task.get("result") is None
    assert "run_metrics" not in saved_task

    fetched = storage.get_task_result(account, key, "t1")
    assert fetched is not None
    assert fetched["legacy"] is True
    assert fetched["result"] == {"output": "kept"}
