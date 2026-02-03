from __future__ import annotations
from typing import Any

from src.message_processors.processor_factory import ProcessorFactory
from src.tasklists.task_states import TASK_STATE_PENDING
from src.agent.agent import Agent


class FakeStorage:
    def get_tasklist(self, account_name: str, tasklist_id: str):
        # Return a plain dict representation of a TaskList with one pending task
        return {
            "id": tasklist_id,
            "schema_version": 1,
            "state": "Created",
            "tasks": [
                {"id": 1, "title": "first", "state": "Completed"},
                {"id": 2, "title": "second", "state": TASK_STATE_PENDING},
                {"id": 3, "title": "third", "state": "Pending"},
            ],
            "meta": {},
        }


class DummyInjector:
    def get(self, cls: type) -> Any:
        # If the processor expects storage, provide FakeStorage
        try:
            return cls(storage=FakeStorage())
        except TypeError:
            return cls()


def test_processor_factory_returns_task_running_processor():
    pf = ProcessorFactory(injector=DummyInjector())
    proc = pf.get("task_running_processor")
    assert proc is not None
    assert proc.__class__.__name__ == "TaskRunningProcessor"

    # Provide minimal args
    primary = Agent(name="doris")
    account = {"accountId": "acct1"}
    cmd = '{"action": "run", "tasklist_id": "tl1", "mode": "single-step"}'

    out = proc.process_message(primary_agent=primary, account=account, message=cmd, context_name="ctx1")
    assert "mode=single-step" in out
    assert "next_task_index=" in out
    assert "next_task_name=" in out
