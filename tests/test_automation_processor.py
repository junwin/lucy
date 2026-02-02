import json
from datetime import datetime

from src.agent.agent import Agent
from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_STATE_PENDING,
    TASK_STATE_COMPLETED,
)


class DummyStorage:
    def __init__(self, initial=None):
        # initial should be a dict mapping (account, id) -> serialized tasklist
        self.store = initial or {}
        self.calls = []

    def get_tasklist(self, account_name, tasklist_id):
        self.calls.append(("get", account_name, tasklist_id))
        return self.store.get((account_name, tasklist_id))

    def save_tasklist(self, account_name, tasklist_id, serialized):
        # serialized may be dict
        self.calls.append(("save", account_name, tasklist_id, serialized))
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


def test_single_step_executes_one_and_persists():
    tl = make_tasklist_with_two_tasks()
    storage = DummyStorage({("test-account", "tl1"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "test-account"}
    msg = json.dumps({"action": "run", "tasklist_id": "tl1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    assert "mode=single-step" in out
    assert "executed=1" in out
    # should have persisted after executing the one task and once more final persist
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) == 2

    # ensure the stored tasklist now marks first task as completed but second remains pending
    persisted = storage.store[("test-account", "tl1")]
    # persisted may be dict
    persisted_tasks = persisted.get("tasks")
    assert persisted_tasks[0]["state"] == TASK_STATE_COMPLETED
    assert persisted_tasks[1]["state"] == TASK_STATE_PENDING


def test_multi_step_executes_all_and_completes():
    tl = make_tasklist_with_two_tasks()
    storage = DummyStorage({("acct", "t2"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "t2", "mode": "multi-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")

    assert "mode=multi-step" in out
    assert "executed=2" in out
    assert "state=completed" in out

    save_calls = [c for c in storage.calls if c[0] == "save"]
    # two saves (one per task) + final persist
    assert len(save_calls) == 3

    persisted = storage.store[("acct", "t2")]
    persisted_tasks = persisted.get("tasks")
    assert all(t["state"] == TASK_STATE_COMPLETED for t in persisted_tasks)


def test_resumes_from_partial_progress():
    # first task already completed
    t1 = Task(id=1, title="First task", state=TASK_STATE_COMPLETED)
    t2 = Task(id=2, title="Second task", state=TASK_STATE_PENDING)
    tl = TaskList(id="r1", tasks=[t1, t2])
    storage = DummyStorage({("a", "r1"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "a"}
    msg = json.dumps({"action": "run", "tasklist_id": "r1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")
    assert "executed=1" in out

    persisted = storage.store[("a", "r1")]
    persisted_tasks = persisted.get("tasks")
    assert persisted_tasks[0]["state"] == TASK_STATE_COMPLETED
    assert persisted_tasks[1]["state"] == TASK_STATE_COMPLETED


def test_non_doris_agent_ignored():
    tl = make_tasklist_with_two_tasks()
    storage = DummyStorage({("acct", "t3"): tl.to_dict()})

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent(name="Alice")
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "t3", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx")
    assert "Not responsible for agent" in out or "Not responsible" in out
