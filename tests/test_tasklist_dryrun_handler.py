from __future__ import annotations

import json
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


class FakeDelegateHandler:
    DEFAULT_TIMEOUT = 120

    def __init__(self, results=None):
        self.calls = []
        self.results = list(results or [])

    def execute(self, args, *, account_name="auto"):
        self.calls.append((args, account_name))
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return {
            "ok": True,
            "tool": "delegate_task",
            "agent": args["agentName"],
            "result": json.dumps(
                {
                    "task_results": [
                        {
                            "task": args["task"],
                            "ready": True,
                        }
                    ]
                }
            ),
        }


def _handler(tmp_path, results=None):
    delegate = FakeDelegateHandler(results=results)
    handler = TasklistDryrunHandler(
        SimpleConfig(str(tmp_path), "ns"),
        delegate_handler=delegate,
    )
    return handler


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


def _result(ready, reason=None, detail=""):
    item = {
        "task": "ignored by handler",
        "ready": ready,
    }
    if not ready:
        item["reason"] = reason
        item["detail"] = detail
    return {
        "ok": True,
        "result": json.dumps({"task_results": [item]}),
    }


def test_dryrun_returns_structured_results_in_order(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            _result(True),
            _result(False, "decompose", "Too large for the tool budget."),
        ],
    )
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
                "persisted_state": "Pending",
                "ready": True,
                "reason": None,
                "detail": "",
            },
            {
                "id": "t2",
                "name": "Second",
                "persisted_state": "Completed",
                "ready": False,
                "reason": "decompose",
                "detail": "Too large for the tool budget.",
            },
        ],
    }


def test_dryrun_delegates_each_task_to_colin_with_dryrun_context(tmp_path):
    handler = _handler(tmp_path)
    _save_tasklist(handler)

    handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert len(handler.delegate_handler.calls) == 2
    first_args, first_account = handler.delegate_handler.calls[0]
    second_args, second_account = handler.delegate_handler.calls[1]

    assert first_account == second_account == "alice"
    assert first_args == {
        "task": "do first",
        "agentName": "colin",
        "capabilities": [],
        "project": "",
        "machine": "",
        "contextName": "dry-run-task",
        "accountName": "alice",
        "timeout_seconds": 120,
    }
    assert second_args["task"] == "do second"
    assert second_args["agentName"] == "colin"
    assert second_args["contextName"] == "dry-run-task"


def test_dryrun_allows_agent_and_context_overrides(tmp_path):
    handler = _handler(tmp_path)
    _save_tasklist(handler)

    handler.execute(
        {
            "tasklist_id": "dryrun-1",
            "agentName": "star",
            "contextName": "alternate-dry-run",
        },
        account_name="alice",
    )

    assert len(handler.delegate_handler.calls) == 2
    for args, account in handler.delegate_handler.calls:
        assert account == "alice"
        assert args["agentName"] == "star"
        assert args["contextName"] == "alternate-dry-run"


def test_dryrun_records_delegate_failure_and_continues(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            {"ok": False, "error": "no eligible machine"},
            _result(False, "blocked", "Missing dependency."),
        ],
    )
    _save_tasklist(handler)

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["ok"] is True
    assert result["tasks"][0] == {
        "id": "t1",
        "name": "First",
        "persisted_state": "Pending",
        "ready": None,
        "reason": None,
        "detail": "",
        "error": "no eligible machine",
    }
    assert result["tasks"][1]["ready"] is False
    assert result["tasks"][1]["reason"] == "blocked"


def test_dryrun_records_invalid_json_and_continues(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            {"ok": True, "result": "not json"},
            _result(False, "invalid", "Malformed task."),
        ],
    )
    _save_tasklist(handler)

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["tasks"][0]["ready"] is None
    assert "invalid dry-run JSON" in result["tasks"][0]["error"]
    assert result["tasks"][1]["ready"] is False
    assert result["tasks"][1]["reason"] == "invalid"


def test_dryrun_records_unexpected_reason(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            _result(False, "maybe", "Not sure."),
            _result(True),
        ],
    )
    _save_tasklist(handler)

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["tasks"][0]["ready"] is None
    assert "unexpected dry-run reason" in result["tasks"][0]["error"]
    assert result["tasks"][1]["ready"] is True


def test_dryrun_requires_one_task_result_per_delegated_task(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            {"ok": True, "result": json.dumps({"task_results": []})},
            _result(True),
        ],
    )
    _save_tasklist(handler)

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["tasks"][0]["ready"] is None
    assert result["tasks"][0]["error"] == (
        "dry-run response returned 0 task_results; expected exactly 1"
    )
    assert result["tasks"][1]["ready"] is True


def test_dryrun_records_raised_task_error_and_continues(tmp_path):
    handler = _handler(
        tmp_path,
        results=[
            RuntimeError("boom"),
            _result(True),
        ],
    )
    _save_tasklist(handler)

    result = handler.execute({"tasklist_id": "dryrun-1"}, account_name="alice")

    assert result["ok"] is True
    assert result["tasks"][0]["ready"] is None
    assert result["tasks"][0]["error"] == "boom"
    assert result["tasks"][1]["ready"] is True


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
    assert handler.delegate_handler.calls == []


def test_dryrun_requires_tasklist_id(tmp_path):
    handler = _handler(tmp_path)

    result = handler.execute({}, account_name="alice")

    assert result["ok"] is False
    assert result["error"]["code"] == "missing_tasklist_id"
    assert handler.delegate_handler.calls == []


def test_dryrun_logs_delegate_result(tmp_path, caplog):
    handler = _handler(
        tmp_path,
        results=[
            _result(True),
            _result(False, "blocked", "Need dependency."),
        ],
    )
    _save_tasklist(handler)

    with caplog.at_level(logging.INFO):
        handler.execute(
            {
                "tasklist_id": "dryrun-1",
                "agentName": "colin",
                "contextName": "dry-run-task",
            },
            account_name="alice",
        )

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "tasklist_dryrun delegate start tasklist_id=dryrun-1 task_id=t1 "
        "agent=colin context=dry-run-task" in message
        for message in messages
    )
    assert any(
        "tasklist_dryrun delegate result tasklist_id=dryrun-1 task_id=t1 "
        "ok=True" in message
        and '"ready": true' in message.lower()
        for message in messages
    )


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


def test_dryrun_tool_definition_uses_nullable_required_overrides():
    tool_def = TasklistDryrunHandler.tool_def()

    assert tool_def["name"] == "tasklist_dryrun"
    assert tool_def["parameters"]["required"] == [
        "tasklist_id",
        "agentName",
        "contextName",
    ]
    assert tool_def["parameters"]["properties"]["agentName"]["type"] == [
        "string",
        "null",
    ]
    assert tool_def["parameters"]["properties"]["contextName"]["type"] == [
        "string",
        "null",
    ]
