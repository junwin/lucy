import json
import logging

from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task_states import (
    TASK_LIST_STATE_FAILED,
    TASK_LIST_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
    TASK_STATE_PENDING,
)


class DummyStorage:
    def __init__(self, initial_tasklist_dict):
        self._tasklist = initial_tasklist_dict
        self.saved = []

    def get_tasklist(self, account_name, tasklist_id):
        return self._tasklist

    def save_tasklist(self, account_name, tasklist_id, serialized):
        if isinstance(serialized, str):
            data = json.loads(serialized)
        else:
            data = serialized
        self._tasklist = data
        self.saved.append(data)


class DummyFCP:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def process_message(self, *args, **kwargs):
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if outcome == "fail":
            raise RuntimeError("boom")
        return "ok"


class DummyFactory:
    def __init__(self, fcp):
        self._fcp = fcp

    def get(self, name: str):
        assert name == "function_calling_processor"
        return self._fcp


def _mk_tasklist_dict(states):
    return {
        "id": "tl1",
        "schema_version": 1,
        "state": TASK_LIST_STATE_RUNNING,
        "meta": {},
        "tasks": [
            {"id": f"t{i}", "title": f"t{i}", "name": f"t{i}", "state": s, "result": None, "error": None}
            for i, s in enumerate(states)
        ],
    }


def _find_structured_log(caplog, *, tasklist_id: str, mode: str, outcome: str) -> bool:
    """Search caplog for the structured AutomationProcessor end log with the fields present.

    We require the message contains tasklist_id, mode and outcome fields and also
    the presence of a task_id= token (its value may be numeric or falsy for 0).
    """
    for rec in caplog.records:
        if rec.levelno != logging.INFO:
            continue
        msg = rec.getMessage()
        if "AutomationProcessor end" in msg and (
            f"tasklist_id={tasklist_id}" in msg and f"mode={mode}" in msg and f"outcome={outcome}" in msg and "task_id=" in msg
        ):
            return True
    return False


def test_tasklist_marked_failed_when_task_fails(caplog):
    caplog.set_level(logging.INFO)
    storage = DummyStorage(_mk_tasklist_dict([TASK_STATE_PENDING, TASK_STATE_PENDING]))
    fcp = DummyFCP(["fail"])
    ap = AutomationProcessor(config=None, registry=None, storage=storage, prompt_builder=None)

    msg = json.dumps({"action": "run", "tasklist_id": "tl1", "mode": "multi-step"})
    out = ap.process_message(
        message=msg,
        primary_agent=None,
        secondary_agent=None,
        account={"name": "acc"},
        conversation_id="c1",
        processor_factory=DummyFactory(fcp),
        context_name="ctx",
    )

    assert "state=failed" in out
    final = storage.saved[-1]
    assert final["state"] == TASK_LIST_STATE_FAILED
    assert final["tasks"][0]["state"] == TASK_STATE_FAILED
    assert final["tasks"][1]["state"] == TASK_STATE_PENDING

    # Check structured log was emitted with expected fields
    assert _find_structured_log(caplog, tasklist_id="tl1", mode="multi-step", outcome="failed")


def test_tasklist_marked_completed_when_all_tasks_complete(caplog):
    caplog.set_level(logging.INFO)
    storage = DummyStorage(_mk_tasklist_dict([TASK_STATE_PENDING, TASK_STATE_PENDING]))
    fcp = DummyFCP(["ok", "ok"])
    ap = AutomationProcessor(config=None, registry=None, storage=storage, prompt_builder=None)

    msg = json.dumps({"action": "run", "tasklist_id": "tl1", "mode": "multi-step"})
    out = ap.process_message(
        message=msg,
        primary_agent=None,
        secondary_agent=None,
        account={"name": "acc"},
        conversation_id="c1",
        processor_factory=DummyFactory(fcp),
        context_name="ctx",
    )

    assert "state=completed" in out
    final = storage.saved[-1]
    assert final["tasks"][0]["state"] == TASK_STATE_COMPLETED
    assert final["tasks"][1]["state"] == TASK_STATE_COMPLETED
    assert final["state"] != TASK_LIST_STATE_FAILED

    # Check structured log was emitted with expected fields
    assert _find_structured_log(caplog, tasklist_id="tl1", mode="multi-step", outcome="completed")
