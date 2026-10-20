"""Stage-two automation regressions through the public coordinator.

Run these on the stage-one base as well as this branch; no live model is used.
"""
from copy import deepcopy
from types import SimpleNamespace
import uuid

import pytest

from src.message_processors.automation_processor import AutomationProcessor
from src.tasklists.task import Task
from src.tasklists.task_states import (
    TASK_STATE_COMPLETED, TASK_STATE_FAILED, TASK_STATE_PENDING,
    TASK_STATE_RUNNING, TASK_LIST_STATE_FAILED, TASK_LIST_STATE_RUNNING,
)
from tests.test_automation_processor_run_metrics import (
    MetricsFunctionProcessor, RecordingProcessorFactory, RecordingStorage,
    make_tasklist,
)


class TimelineStorage(RecordingStorage):
    def __init__(self, tasklist, timeline, *, fail_append=False, fail_completed=False):
        super().__init__(tasklist)
        self.timeline = timeline
        self.fail_append = fail_append
        self.fail_completed = fail_completed

    def save_tasklist(self, account, key, data):
        self.timeline.append(("save", tuple(t.state for t in data.tasks), data.state))
        if self.fail_completed and data.tasks[0].state == TASK_STATE_COMPLETED:
            self.fail_completed = False
            raise OSError("completed checkpoint unavailable")
        super().save_tasklist(account, key, deepcopy(data))

    def append_task_execution_record(self, account, key, record):
        self.timeline.append(("record", record["task_id"], record["state"]))
        if self.fail_append:
            raise OSError("record store unavailable")
        super().append_task_execution_record(account, key, record)


class ProbeProcessor(MetricsFunctionProcessor):
    def __init__(self, timeline, failure=None):
        super().__init__()
        self.timeline = timeline
        self.failure = failure

    def process_message(self, **kwargs):
        self.timeline.append(("call", kwargs["message"]))
        result = super().process_message(**kwargs)
        if self.failure == "exception":
            raise RuntimeError("worker failed")
        if self.failure == "stop":
            return result._replace(text="I received an empty response from the model")
        if self.failure == "metrics":
            return SimpleNamespace(text="worker returned", metrics=BrokenMetrics())
        return result


class BrokenMetrics:
    def to_dict(self):
        raise ValueError("metrics unavailable")


def run_probe(monkeypatch, *, mode="multi-step", failure=None, **storage_options):
    timeline = []
    tasklist = make_tasklist(instructions="first")
    tasklist.tasks[0].id = "t1"
    tasklist.tasks.append(Task(id="t2", name="T2", instructions="second"))
    storage = TimelineStorage(tasklist, timeline, **storage_options)
    worker = ProbeProcessor(timeline, failure)
    processor = AutomationProcessor(
        config=None, registry=None, storage=storage, prompt_builder=None,
        episodic_store=None, llm_adapter=None, agent_manager=None,
    )

    def event(self, **kwargs):
        timeline.append(("event", kwargs["kind"]))

    monkeypatch.setattr(AutomationProcessor, "_write_episodic_event", event)
    result = processor.execute_tasklist(
        tasklist_id="tl-1", mode=mode, account_name="acct", agent_name="test",
        conversation_id="conv-1", context_name="ctx",
        primary_agent=SimpleNamespace(name="test"), account={"accountId": "acct"},
        processor_factory=RecordingProcessorFactory(worker),
        correlation_id="parent", trace_id="root",
    )
    return result, tasklist, storage, worker, timeline


@pytest.mark.parametrize("mode, calls", [("single-step", 1), ("multi-step", 2)])
def test_checkpoint_call_record_event_order_and_lineage(monkeypatch, mode, calls):
    result, tasklist, storage, worker, timeline = run_probe(monkeypatch, mode=mode)
    assert len(worker.calls) == len(storage.records) == calls
    expected = []
    for index in range(calls):
        states = [TASK_STATE_COMPLETED] * index + [TASK_STATE_RUNNING] + [TASK_STATE_PENDING] * (1-index)
        expected.extend([
            ("save", tuple(states), TASK_LIST_STATE_RUNNING),
            ("call", ["first", "second"][index]),
            ("record", ["t1", "t2"][index], "completed"),
            ("event", "task_completed"),
            ("save", tuple([TASK_STATE_COMPLETED] * (index+1) + [TASK_STATE_PENDING] * (1-index)), TASK_LIST_STATE_RUNNING),
        ])
    assert timeline[:-2] == expected
    assert timeline[-2][0] == "save"
    assert timeline[-1] == ("event", "automation_summary")
    assert "executed=" + str(calls) in result
    child_ids = []
    for call, (_, _, record) in zip(worker.calls, storage.records):
        assert record["schema_version"] == 1
        assert uuid.UUID(record["record_id"]).hex == record["record_id"]
        assert record["tasklist_key"] == "tl-1"
        assert record["correlation_id"] == "parent"
        assert record["trace_id"] == call["trace_id"] == "root"
        assert record["parent_run_id"] == "parent"
        assert record["run_id"] == call["correlation_id"] != "parent"
        assert record["metrics"] == worker.metrics.to_dict()
        assert record["result"]["output"] == worker.text
        assert record["started"] <= record["result"]["timestamp"] <= record["ended"]
        assert "error" not in record and "error_detail" not in record
        child_ids.append(record["run_id"])
    assert len(set(child_ids)) == calls
    assert all(t.result is None and t.run_metrics is None for t in tasklist.tasks)


@pytest.mark.parametrize("failure", ["exception", "stop", "metrics"])
def test_failed_worker_or_result_interpretation_stops_before_next_task(monkeypatch, failure):
    _, tasklist, storage, worker, timeline = run_probe(monkeypatch, failure=failure)
    assert len(worker.calls) == len(storage.records) == 1
    assert [t.state for t in tasklist.tasks] == [TASK_STATE_FAILED, TASK_STATE_PENDING]
    assert tasklist.state == TASK_LIST_STATE_FAILED
    record = storage.records[0][2]
    assert record["state"] == "failed"
    assert record["error"] == tasklist.tasks[0].error
    if failure == "stop":
        assert record["metrics"] == worker.metrics.to_dict()
        assert record["result"]["output"].startswith("I received an empty response")
        assert "error_detail" not in record
    else:
        assert "Traceback" in record["error_detail"]
        assert "result" not in record and "metrics" not in record
    assert [e for e in timeline if e[0] == "event"] == [
        ("event", "task_failed"), ("event", "automation_summary"),
    ]


def test_append_failure_preserves_completed_record_attempt_but_fails_task(monkeypatch):
    result, tasklist, storage, worker, timeline = run_probe(monkeypatch, fail_append=True)
    assert "Failed to append task execution record" in result
    assert len(worker.calls) == 1 and storage.records == []
    assert ("record", "t1", "completed") in timeline
    assert [t.state for t in tasklist.tasks] == [TASK_STATE_FAILED, TASK_STATE_PENDING]
    assert tasklist.state == TASK_LIST_STATE_FAILED
    assert not any(e[0] == "event" for e in timeline)


def test_completed_checkpoint_failure_stops_without_reexecuting_worker(monkeypatch):
    result, tasklist, storage, worker, timeline = run_probe(monkeypatch, fail_completed=True)
    assert "Failed to persist task state" in result
    assert len(worker.calls) == len(storage.records) == 1
    assert [t.state for t in tasklist.tasks] == [TASK_STATE_COMPLETED, TASK_STATE_PENDING]
    assert tasklist.state == TASK_LIST_STATE_FAILED
    assert [e for e in timeline if e[0] == "event"] == [("event", "task_completed")]
