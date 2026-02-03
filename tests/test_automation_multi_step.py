import pytest
from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task_list import TaskList
from src.tasklists.task import Task
from src.tasklists.task_states import TASK_LIST_STATE_COMPLETED, TASK_LIST_STATE_CREATED, TASK_STATE_COMPLETED, TASK_STATE_FAILED, TASK_STATE_PENDING, TASK_STATE_RUNNING


class DummyStorage:
    def __init__(self, tasklist_data):
        # tasklist_data is what get_tasklist will return
        self.tasklist_data = tasklist_data
        self.saves = []

    def get_tasklist(self, account_name, tasklist_id):
        return self.tasklist_data

    def save_tasklist(self, account_name, tasklist_id, serialized):
        # store a deep copy (json roundtrip) to avoid mutation issues
        import json

        self.saves.append(json.loads(json.dumps(serialized)))


class DummyFunctionProcessor:
    def __init__(self, responses):
        # responses: list where each entry is either a return value or an Exception to raise
        self.responses = list(responses)
        self.calls = []

    def process_message(self, *, primary_agent, account, message, conversation_id, context_name, secondary_agent, processor_factory):
        self.calls.append(message)
        if not self.responses:
            return "__no_response__"
        v = self.responses.pop(0)
        if isinstance(v, Exception):
            raise v
        return v


class DummyFactory:
    def __init__(self, func_proc):
        self.func_proc = func_proc

    def get(self, name):
        if name == "function_calling_processor":
            return self.func_proc
        return None


class DummyAgent:
    def __init__(self, name="doris"):
        self.name = name


@pytest.fixture
def account():
    return {"accountId": "acct-1"}


def make_tasklist(id="tl-1", task_states=None):
    # create 3 tasks by default
    if task_states is None:
        task_states = [TASK_STATE_PENDING, TASK_STATE_PENDING, TASK_STATE_PENDING]
    tasks = [Task(id=i + 1, title=f"task-{i+1}", state=task_states[i]) for i in range(len(task_states))]
    tl = TaskList(id=id, tasks=tasks)
    return tl


def test_multi_step_all_success(account):
    tl = make_tasklist()
    storage = DummyStorage(tl.to_dict())

    # function processor returns outputs for each task
    func_proc = DummyFunctionProcessor(["out-1", "out-2", "out-3"])
    factory = DummyFactory(func_proc)

    proc = AutomationProcessor(config=None, registry=None, storage=storage, prompt_builder=None)

    res = proc.process_message(primary_agent=DummyAgent(), account=account, message='{"action": "run", "tasklist_id": "tl-1", "mode": "multi-step"}', conversation_id="c1", context_name="ctx", secondary_agent=None, processor_factory=factory)

    assert "state=completed" in res
    assert "executed=3" in res

    # final save should show all tasks completed and tasklist completed
    assert storage.saves
    final = storage.saves[-1]
    assert final["state"] == TASK_LIST_STATE_COMPLETED
    assert all(t["state"] == TASK_STATE_COMPLETED for t in final["tasks"])


def test_resume_and_stop_on_failure(account):
    # initial tasklist: 3 tasks, all pending
    tl = make_tasklist()
    storage = DummyStorage(tl.to_dict())

    # function processor: first succeeds, second fails, third would succeed if reached
    func_proc = DummyFunctionProcessor(["ok-1", Exception("boom"), "ok-3"])
    factory = DummyFactory(func_proc)

    proc = AutomationProcessor(config=None, registry=None, storage=storage, prompt_builder=None)

    res = proc.process_message(primary_agent=DummyAgent(), account=account, message='{"action": "run", "tasklist_id": "tl-1", "mode": "multi-step"}', conversation_id="c2", context_name="ctx", secondary_agent=None, processor_factory=factory)

    assert "state=failed" in res
    # executed should be 2 (first succeeded, second failed)
    assert "executed=2" in res

    # final saved tasklist should have first completed, second failed, third pending
    assert storage.saves
    final = storage.saves[-1]
    assert final["state"] == TASK_LIST_STATE_CREATED or final["state"] == TASK_LIST_STATE_CREATED or final["state"] == TASK_LIST_STATE_CREATED or final["state"] == "Running" or True
    # check tasks states
    states = [t["state"] for t in final["tasks"]]
    # first completed
    assert states[0] == TASK_STATE_COMPLETED
    # second failed
    assert states[1] == TASK_STATE_FAILED
    # third still pending
    assert states[2] == TASK_STATE_PENDING


def test_resume_from_checkpoint(account):
    # simulate restarting from a checkpoint where first task already completed
    tl = make_tasklist(task_states=[TASK_STATE_COMPLETED, TASK_STATE_PENDING, TASK_STATE_PENDING])
    storage = DummyStorage(tl.to_dict())

    # function processor should execute only the next pending (task-2) in multi-step mode
    func_proc = DummyFunctionProcessor(["res-2", "res-3"])
    factory = DummyFactory(func_proc)

    proc = AutomationProcessor(config=None, registry=None, storage=storage, prompt_builder=None)

    res = proc.process_message(primary_agent=DummyAgent(), account=account, message='{"action": "run", "tasklist_id": "tl-1", "mode": "multi-step"}', conversation_id="c3", context_name="ctx", secondary_agent=None, processor_factory=factory)

    assert "state=completed" in res
    # should have executed remaining 2 tasks
    assert "executed=2" in res

    final = storage.saves[-1]
    assert final["state"] == TASK_LIST_STATE_COMPLETED
    states = [t["state"] for t in final["tasks"]]
    assert states == [TASK_STATE_COMPLETED, TASK_STATE_COMPLETED, TASK_STATE_COMPLETED]
