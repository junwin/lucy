from __future__ import annotations

import logging

from src.handlers.tasklist_dryrun_handler import TasklistDryrunHandler
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList


class SimpleConfig:
    def __init__(self, root: str, namespace: str):
        self.values = {
            "storage_root_path": root,
            "storage_namespace": namespace,
            "tasklists": {},
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


def _handler(tmp_path):
    return TasklistDryrunHandler(SimpleConfig(str(tmp_path), "ns"))


def _save_tasklist(handler, account_name="alice", tasklist_id="dryrun-1"):
    tasklist = TaskList(
        id=tasklist_id,
        name="Dry Run",
        description="Inspect only",
        tasks=[
            Task(id="t1", name="First", instructions="do first", state="Pending"),
            Task(id="t2", name="Second", instructions="do second", state="Completed"),
        ],
    )
    handler.tasklist_service.save(account_name, tasklist_id, tasklist)
    return tasklist


def test_dryrun_returns_tasks_in_order_with_required_fields(tmp_path):
    handler = _handler(tmp_path)
    _save_tasklist(handler)

    result = handler.execute(
        {"tasklist_id": "dryrun-1"},
        account_name="alice",
        correlation_id="corr-1",
    )

    assert result == {
        "ok": True,
        "tool": "tasklist_dryrun",
        "tasklist_id": "dryrun-1",
        "tasks": [
            {
                "id": "t1",
                "name": "First",
                "state": "Pending",
                "instructions": "do first",
            },
            {
                "id": "t2",
                "name": "Second",
                "state": "Completed",
                "instructions": "do second",
            },
        ],
    }


def test_dryrun_does_not_modify_persisted_tasklist(tmp_path):
    handler = _handler(tmp_path)
    _save_tasklist(handler)
    path = tmp_path / "ns" / "tasklists" / "alice" / "dryrun-1.json"
    before = path.read_bytes()

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["ok"] is True
    assert path.read_bytes() == before


def test_dryrun_missing_tasklist_is_read_only_error(tmp_path):
    handler = _handler(tmp_path)

    result = handler.execute({"tasklist_id": "missing"}, account_name="alice")

    assert result["ok"] is False
    assert result["error"]["code"] == "tasklist_not_found"


def test_dryrun_requires_tasklist_id(tmp_path):
    handler = _handler(tmp_path)

    result = handler.execute({}, account_name="alice")

    assert result["ok"] is False
    assert result["error"]["code"] == "missing_tasklist_id"


def test_dryrun_logs_start_and_end(tmp_path, caplog):
    handler = _handler(tmp_path)
    _save_tasklist(handler)

    with caplog.at_level(logging.INFO):
        handler.execute(
            {"tasklist_id": "dryrun-1"},
            account_name="alice",
            correlation_id="corr-42",
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "tasklist_dryrun start account=alice tasklist_id=dryrun-1 correlation_id=corr-42"
        in message
        for message in messages
    )
    assert any(
        "tasklist_dryrun end account=alice tasklist_id=dryrun-1 correlation_id=corr-42"
        in message
        for message in messages
    )


def test_dryrun_tool_definition_has_only_tasklist_id():
    tool_def = TasklistDryrunHandler.tool_def()

    assert tool_def["name"] == "tasklist_dryrun"
    assert tool_def["parameters"]["required"] == ["tasklist_id"]
    assert set(tool_def["parameters"]["properties"]) == {"tasklist_id"}
