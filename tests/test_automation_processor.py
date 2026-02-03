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


class ProcFactoryMock:
    def __init__(self, processor):
        self._processor = processor

    def get(self, name):
        if name == "function_calling_processor":
            return self._processor
        raise KeyError(name)


class DummyFunctionProcessor:
    def __init__(self, response_text="ok", raise_exc: Exception | None = None):
        self.response_text = response_text
        self.raise_exc = raise_exc
        self.calls = []

    def process_message(self, *, primary_agent, account, message, conversation_id="0", context_name="", secondary_agent=None, processor_factory=None):
        self.calls.append((primary_agent, account, message, conversation_id, context_name, secondary_agent))
        if self.raise_exc:
            raise self.raise_exc
        return self.response_text


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

    # Create a dummy function processor that returns success
    func_proc = DummyFunctionProcessor(response_text="done")
    proc_factory = ProcFactoryMock(func_proc)

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "test-account"}
    msg = json.dumps({"action": "run", "tasklist_id": "tl1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx", processor_factory=proc_factory)

    assert "mode=single-step" in out
    assert "executed=1" in out

    # Step 3.3 persistence checkpoints:
    # - persist after setting task RUNNING
    # - persist after setting task COMPLETED
    # - final persist (tasklist state)
    save_calls = [c for c in storage.calls if c[0] == "save"]
    assert len(save_calls) == 3

    # ensure the stored tasklist now marks first task as completed but second remains pending
    persisted = storage.store[("test-account", "tl1")]
    # persisted may be dict
    persisted_tasks = persisted.get("tasks")
    assert persisted_tasks[0]["state"] == TASK_STATE_COMPLETED
    assert persisted_tasks[1]["state"] == TASK_STATE_PENDING

    # ensure function processor was invoked with the task title as message
    assert func_proc.calls and func_proc.calls[0][2] == "First task"


def test_multi_step_executes_all_and_completes():
    tl = make_tasklist_with_two_tasks()
    storage = DummyStorage({("acct", "t2"): tl.to_dict()})

    func_proc = DummyFunctionProcessor(response_text="ok")
    proc_factory = ProcFactoryMock(func_proc)

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "t2", "mode": "multi-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx", processor_factory=proc_factory)

    assert "mode=multi-step" in out
    assert "executed=2" in out
    assert "state=completed" in out

    save_calls = [c for c in storage.calls if c[0] == "save"]
    # Step 3.3 persistence checkpoints:
    # - for each task: persist after RUNNING and after COMPLETED (2 * tasks)
    # - final persist (tasklist state)
    assert len(save_calls) == 5

    persisted = storage.store[("acct", "t2")]
    persisted_tasks = persisted.get("tasks")
    assert all(t["state"] == TASK_STATE_COMPLETED for t in persisted_tasks)


def test_resumes_from_partial_progress():
    # first task already completed
    t1 = Task(id=1, title="First task", state=TASK_STATE_COMPLETED)
    t2 = Task(id=2, title="Second task", state=TASK_STATE_PENDING)
    tl = TaskList(id="r1", tasks=[t1, t2])
    storage = DummyStorage({("a", "r1"): tl.to_dict()})

    func_proc = DummyFunctionProcessor(response_text="ok")
    proc_factory = ProcFactoryMock(func_proc)

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "a"}
    msg = json.dumps({"action": "run", "tasklist_id": "r1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx", processor_factory=proc_factory)
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


def test_task_execution_failure_marks_task_failed_and_persists():
    tl = make_tasklist_with_two_tasks()
    storage = DummyStorage({("acct", "fail1"): tl.to_dict()})

    # Function processor will raise an exception for the first task
    func_proc = DummyFunctionProcessor(raise_exc=RuntimeError("handler failed"))
    proc_factory = ProcFactoryMock(func_proc)

    proc = AutomationProcessor(
        config=DummyConfig(),
        registry=DummyRegistry(),
        storage=storage,
        prompt_builder=DummyPromptBuilder(),
    )

    agent = make_agent()
    account = {"accountId": "acct"}
    msg = json.dumps({"action": "run", "tasklist_id": "fail1", "mode": "single-step"})

    out = proc.process_message(primary_agent=agent, account=account, message=msg, context_name="ctx", processor_factory=proc_factory)

    assert "state=failed" in out

    save_calls = [c for c in storage.calls if c[0] == "save"]
    # RUNNING checkpoint, per-task (FAILED) checkpoint, final persist
    assert len(save_calls) == 3

    persisted = storage.store[("acct", "fail1")]
    persisted_tasks = persisted.get("tasks")
    assert persisted_tasks[0]["state"] == "Failed"
    # second task should remain pending
    assert persisted_tasks[1]["state"] == TASK_STATE_PENDING
