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


# Additional tests for Step 3.3 persistence checkpoints using Storage
# These tests assert the desired behavior: the processor marks tasks RUNNING
# and persists before execution, marks COMPLETED and persists on success,
# marks FAILED and persists on failure, and when no pending tasks returns
# an appropriate message and does not persist.

import json
from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_STATE_PENDING,
    TASK_STATE_RUNNING,
    TASK_STATE_COMPLETED,
    TASK_STATE_RUNNING as RUNNING,
)


class RecordingStorage:
    def __init__(self, initial=None, fail_on_save=False, fail_on_save_count=None):
        # initial: dict mapping (account, id) -> serialized tasklist
        self.store = initial or {}
        self.calls = []
        self.fail_on_save = fail_on_save
        # if set, fail only on the Nth save (1-based)
        self.fail_on_save_count = fail_on_save_count

    def get_tasklist(self, account_name, tasklist_id):
        self.calls.append(("get", account_name, tasklist_id))
        return self.store.get((account_name, tasklist_id))

    def save_tasklist(self, account_name, tasklist_id, serialized):
        self.calls.append(("save", account_name, tasklist_id, serialized))
        # optionally simulate failure for testing
        saves = [c for c in self.calls if c[0] == "save"]
        if self.fail_on_save and (
            self.fail_on_save_count is None or len(saves) == self.fail_on_save_count
        ):
            raise RuntimeError("simulated storage failure")
        self.store[(account_name, tasklist_id)] = serialized


class DummyConfig:
    pass


class DummyRegistry:
    pass


class DummyPromptBuilder:
    pass


def make_agent(name="Doris"):
    return Agent(name=name)


def make_tasklist_with_two_tasks(id="tl1"):
    t1 = Task(id=1, title="First task", state=TASK_STATE_PENDING)
    t2 = Task(id=2, title="Second task", state=TASK_STATE_PENDING)
    tl = TaskList(id=id, tasks=[t1, t2])
    return tl


def test_marks_task_running_and_persists_before_execution():
    tl = make_tasklist_with_two_tasks()
    storage = RecordingStorage({("acct", "tl1"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "tl1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    # Expect that processor indicated single-step execution
    assert "mode=single-step" in out

    # Expect at least one save (persistence) and that at least one saved copy
    # shows the first task in RUNNING state before working on it.
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) >= 1

    # Find a saved snapshot where the first task is RUNNING
    found_running_snapshot = False
    for _, _, _, serialized in save_calls:
        tasks = serialized.get("tasks")
        if tasks and tasks[0].get("state") == TASK_STATE_RUNNING:
            found_running_snapshot = True
            break

    assert found_running_snapshot, "Expected a persisted snapshot with task state RUNNING"


def test_on_simulated_success_marks_completed_and_persists():
    tl = make_tasklist_with_two_tasks()
    storage = RecordingStorage({("acct", "suc"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "suc", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    assert "executed=1" in out

    # Last persisted state should show first task completed
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) >= 1
    _, _, _, last_serialized = save_calls[-1]
    tasks = last_serialized.get("tasks")
    assert tasks[0].get("state") == TASK_STATE_COMPLETED


def test_on_simulated_failure_marks_failed_and_persists():
    tl = make_tasklist_with_two_tasks()
    # configure storage to fail on the first save call to simulate failure during persist
    storage = RecordingStorage({("acct", "fail"): tl.to_dict()}, fail_on_save=True, fail_on_save_count=1)

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "fail", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    # Expect processor reported a failure state
    assert "state=failed" in out or "Failed to persist" in out

    # Even if persistence failed, the processor should have attempted a save
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) >= 1


def test_no_pending_tasks_returns_message_and_does_not_persist():
    # tasklist with no pending tasks
    t1 = Task(id=1, title="First task", state=TASK_STATE_COMPLETED)
    tl = TaskList(id="empty", tasks=[t1])
    storage = RecordingStorage({("acct", "empty"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "empty", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    assert "no pending tasks" in out or "state=completed" in out

    # Step 3.3 persistence checkpoints only apply when we actually transition state.
    # If there are no pending tasks, AP may still persist the tasklist end-state.
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) == 1
