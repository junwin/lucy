"""Tests for AutomationProcessor mandatory-stop behavior (GH issue #123).

When the FunctionCallingProcessor returns a response indicating the model did
NOT complete the requested work (internal limit / empty response / stuck loop),
AutomationProcessor must abort the tasklist, mark the task failed/error, and
under no circumstances mark the task or tasklist completed.
"""

import uuid
from types import SimpleNamespace

from src.message_processors.automation_processor import (
    AutomationProcessor,
    _is_mandatory_stop_response,
)
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import (
    TASK_LIST_STATE_FAILED,
    TASK_STATE_COMPLETED,
    TASK_STATE_FAILED,
)

INTERNAL_LIMIT = (
    "I ran into an internal limit while trying to call tools multiple times. "
    "I may not have completed all requested actions. Please try rephrasing or splitting your request."
)
EMPTY_RESPONSE = "I received an empty response from the model — please try again."
STUCK_LOOP = (
    "I noticed I was repeating the same tool call without making progress. "
    "I've stopped to avoid getting stuck in a loop. "
    "Please rephrase your request or be more specific about what you need."
)


class FakeFunctionProcessor:
    def __init__(self, response):
        self.response = response
        self.calls = 0

    def process_message(self, **kwargs):
        self.calls += 1
        return self.response


class FakeProcessorFactory:
    def __init__(self, function_processor):
        self.function_processor = function_processor

    def get(self, name):
        if name == "function_calling_processor":
            return self.function_processor
        return None


class FakeStorage:
    def __init__(self, tasklist):
        self.tasklist = tasklist
        self.saved = []

    def get_tasklist(self, account_name, tasklist_id):
        return self.tasklist

    def list_tasklists(self, account_name):
        return [self.tasklist.id]

    def save_tasklist(self, account_name, tasklist_id, data):
        self.saved.append((tasklist_id, data))


def make_tasklist():
    task = Task(id=str(uuid.uuid4()), name="T1", instructions="Do the thing")
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def run_tasklist(processor_factory):
    tasklist = make_tasklist()
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
    result = ap.execute_tasklist(
        tasklist_id="tl-1",
        mode="single-step",
        account_name="acct",
        agent_name="test",
        conversation_id="conv-1",
        context_name="ctx",
        primary_agent=SimpleNamespace(name="test"),
        account={"accountId": "acct"},
        processor_factory=processor_factory,
    )
    return result, tasklist, tasklist.tasks[0]


def test_is_mandatory_stop_response_detects_markers():
    assert _is_mandatory_stop_response(INTERNAL_LIMIT)
    assert _is_mandatory_stop_response(EMPTY_RESPONSE)
    assert _is_mandatory_stop_response(STUCK_LOOP)
    assert not _is_mandatory_stop_response("All done, task completed.")
    assert not _is_mandatory_stop_response("")
    assert not _is_mandatory_stop_response(None)


def test_internal_limit_aborts_tasklist_and_marks_failed():
    result, tasklist, task = run_tasklist(
        FakeProcessorFactory(FakeFunctionProcessor(INTERNAL_LIMIT))
    )

    assert "state=Failed" in result
    assert task.state == TASK_STATE_FAILED
    assert task.state != TASK_STATE_COMPLETED
    assert task.error is not None
    assert tasklist.state == TASK_LIST_STATE_FAILED


def test_empty_response_aborts_tasklist():
    result, tasklist, task = run_tasklist(
        FakeProcessorFactory(FakeFunctionProcessor(EMPTY_RESPONSE))
    )

    assert "state=Failed" in result
    assert task.state == TASK_STATE_FAILED
    assert tasklist.state == TASK_LIST_STATE_FAILED


def test_stuck_loop_aborts_tasklist():
    result, tasklist, task = run_tasklist(
        FakeProcessorFactory(FakeFunctionProcessor(STUCK_LOOP))
    )

    assert "state=Failed" in result
    assert task.state == TASK_STATE_FAILED
    assert tasklist.state == TASK_LIST_STATE_FAILED


def test_normal_response_still_completes():
    result, tasklist, task = run_tasklist(
        FakeProcessorFactory(FakeFunctionProcessor("Task finished successfully."))
    )

    # Single-step leaves the tasklist "Running" (more pending tasks may remain),
    # but the executed task itself must be marked Completed, not Failed.
    assert "state=Failed" not in result
    assert task.state == TASK_STATE_COMPLETED
    assert task.error is None
    assert tasklist.state != TASK_LIST_STATE_FAILED
