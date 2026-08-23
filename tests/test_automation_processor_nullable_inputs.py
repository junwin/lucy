"""Regression tests for GH issue #132.

AutomationProcessor.execute_tasklist must tolerate nullable inputs
(context_name=None, worker_agent=None, task.agent=None, empty
task.instructions) instead of crashing with
'NoneType' object has no attribute 'strip'.
"""

import uuid
from types import SimpleNamespace

from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_COMPLETED


class RecordingFunctionProcessor:
    def __init__(self, response="Task finished successfully."):
        self.response = response
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class RecordingProcessorFactory:
    def __init__(self, function_processor):
        self.function_processor = function_processor

    def get(self, name):
        if name == "function_calling_processor":
            return self.function_processor
        return None


class FakeStorage:
    def __init__(self, tasklist):
        self.tasklist = tasklist

    def get_tasklist(self, account_name, tasklist_id):
        return self.tasklist

    def list_tasklists(self, account_name):
        return [self.tasklist.id]

    def save_tasklist(self, account_name, tasklist_id, data):
        pass


def make_tasklist(*, instructions="Do the thing", agent=None):
    task = Task(
        id=str(uuid.uuid4()),
        name="T1",
        instructions=instructions,
        agent=agent,
    )
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def run_tasklist(function_processor, tasklist, **overrides):
    storage = FakeStorage(tasklist)
    ap = AutomationProcessor(
        config=None,
        registry=None,
        storage=storage,
        prompt_builder=None,
        chat2_store=None,
        llm_adapter=None,
        agent_manager=None,
    )
    kwargs = {
        "tasklist_id": "tl-1",
        "mode": "single-step",
        "account_name": "acct",
        "agent_name": "test",
        "conversation_id": "conv-1",
        "context_name": "ctx",
        "primary_agent": SimpleNamespace(name="test"),
        "account": {"accountId": "acct"},
        "processor_factory": RecordingProcessorFactory(function_processor),
    }
    kwargs.update(overrides)
    result = ap.execute_tasklist(**kwargs)
    return result, tasklist, tasklist.tasks[0]


def test_none_context_name_does_not_crash():
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, task = run_tasklist(fcp, tasklist, context_name=None)

    assert "state=Failed" not in result
    assert task.state == TASK_STATE_COMPLETED
    assert fcp.calls
    assert fcp.calls[0]["context_name"] == ""


def test_none_worker_agent_does_not_crash():
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, task = run_tasklist(fcp, tasklist, worker_agent=None)

    assert "state=Failed" not in result
    assert task.state == TASK_STATE_COMPLETED
    assert fcp.calls


def test_nullable_task_fields_do_not_crash():
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist(instructions="", agent=None)
    result, tasklist, task = run_tasklist(fcp, tasklist, context_name=None)

    assert "state=Failed" not in result
    assert task.state == TASK_STATE_COMPLETED
    assert not fcp.calls
