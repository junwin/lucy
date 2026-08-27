"""Test that AutomationProcessor attaches per-task run metrics and persists them."""

import uuid
from types import SimpleNamespace

from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_COMPLETED
from src.tasklists.task_states import TASK_STATE_FAILED


class MetricsFunctionProcessor:
    def __init__(self, text="Task finished successfully.", metrics=None):
        self.text = text
        self.metrics = metrics or RunMetrics(
            correlation_id="corr-123",
            iterations=3,
            max_iterations=10,
            openai_calls=4,
            tool_calls=2,
            prompt_tokens=100,
            completion_tokens=50,
            failures=0,
            duration_ms=1500,
        )
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return FCPResult(text=self.text, metrics=self.metrics)


class RecordingProcessorFactory:
    def __init__(self, function_processor):
        self.function_processor = function_processor

    def get(self, name):
        if name == "function_calling_processor":
            return self.function_processor
        return None


class RecordingStorage:
    def __init__(self, tasklist):
        self.tasklist = tasklist
        self.saved = []

    def get_tasklist(self, account_name, tasklist_id):
        return self.tasklist

    def list_tasklists(self, account_name):
        return [self.tasklist.id]

    def save_tasklist(self, account_name, tasklist_id, data):
        self.saved.append(data)


def run_tasklist(function_processor, tasklist, **overrides):
    storage = RecordingStorage(tasklist)
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
    return result, storage, tasklist.tasks[0]


def make_tasklist(*, instructions="Do the thing"):
    task = Task(id=str(uuid.uuid4()), name="T1", instructions=instructions)
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def test_automation_attaches_run_metrics():
    fcp = MetricsFunctionProcessor()
    tasklist = make_tasklist()
    result, storage, task = run_tasklist(fcp, tasklist)

    expected = fcp.metrics.to_dict()

    assert "state=Failed" not in result
    assert task.state == TASK_STATE_COMPLETED
    assert task.run_metrics == expected
    assert task.result["output"] == fcp.text

    assert storage.saved
    saved_task = storage.saved[-1]["tasks"][0]
    assert saved_task["run_metrics"] == expected


def test_automation_mandatory_stop_uses_text_only():
    fcp = MetricsFunctionProcessor(
        text="I received an empty response from the model",
        metrics=RunMetrics(correlation_id="corr-456", failures=1),
    )
    tasklist = make_tasklist()
    result, storage, task = run_tasklist(fcp, tasklist)

    assert "state=Failed" in result
    assert task.state == TASK_STATE_FAILED
    assert task.error is not None
    assert task.run_metrics == fcp.metrics.to_dict()
