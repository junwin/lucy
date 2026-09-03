"""Verify AutomationProcessor._ensure_chat2_session persists sessions and events into sqlite."""

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.sqlite import SqliteChat2Primitives
from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_COMPLETED


@pytest.fixture
def chat2_store(tmp_path: Path) -> Chat2Store:
    primitives = SqliteChat2Primitives(tmp_path / "chat2.sqlite")
    store = Chat2Store(primitives)
    yield store
    primitives.close()


class RecordingFunctionProcessor:
    def __init__(self, response="Task finished successfully."):
        self.response = response
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return FCPResult(text=self.response, metrics=RunMetrics())


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

    def append_task_execution_record(self, account_name, tasklist_key, record):
        pass


def make_tasklist(*, instructions="Do the thing"):
    task = Task(id=str(uuid.uuid4()), name="T1", instructions=instructions)
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def make_processor(chat2_store, storage):
    return AutomationProcessor(
        config=None,
        registry=None,
        storage=storage,
        prompt_builder=None,
        chat2_store=chat2_store,
        llm_adapter=None,
        agent_manager=None,
    )


def run_tasklist(function_processor, tasklist, chat2_store, **overrides):
    storage = FakeStorage(tasklist)
    ap = make_processor(chat2_store, storage)
    conversation_id = str(uuid.uuid4())
    kwargs = {
        "tasklist_id": "tl-1",
        "mode": "single-step",
        "account_name": "acct",
        "agent_name": "test",
        "conversation_id": conversation_id,
        "context_name": "ctx",
        "primary_agent": SimpleNamespace(name="test"),
        "account": {"accountId": "acct"},
        "processor_factory": RecordingProcessorFactory(function_processor),
    }
    kwargs.update(overrides)
    result = ap.execute_tasklist(**kwargs)
    return result, tasklist, conversation_id


def test_execute_tasklist_creates_session_in_sqlite(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, conversation_id = run_tasklist(fcp, tasklist, chat2_store)

    assert "state=Failed" not in result
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED
    assert chat2_store.session_exists(conversation_id)

    session = chat2_store.get_session(conversation_id)
    assert session is not None
    assert session.session_id == conversation_id
    assert session.user_id == "acct"
    assert session.account_name == "acct"
    assert session.agent_name == "test"
    assert session.friendly_name == "auto_tl-1"


def test_execute_tasklist_writes_events_to_sqlite(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, conversation_id = run_tasklist(fcp, tasklist, chat2_store)

    events = list(chat2_store.stream_events(conversation_id))
    assert [e.kind for e in events] == ["system_note", "summary"]
    assert [e.role for e in events] == ["assistant", "assistant"]
    assert [e.actor for e in events] == ["test", "test"]
    assert [e.metadata["automation_kind"] for e in events] == [
        "task_completed",
        "automation_summary",
    ]

    task_event = json.loads(events[0].payload)
    assert task_event["task_name"] == "T1"
    assert task_event["outcome"] == "completed"
    assert task_event["error"] is None

    summary_event = json.loads(events[1].payload)
    assert summary_event["tasklist_id"] == "tl-1"
    assert summary_event["mode"] == "single-step"
    assert summary_event["executed_count"] == 1


def test_execute_tasklist_sessions_listed_for_account(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, conversation_id = run_tasklist(fcp, tasklist, chat2_store)

    sessions = chat2_store.list_sessions(account_name="acct")
    assert [s.session_id for s in sessions] == [conversation_id]
    assert chat2_store.list_sessions(account_name="other") == []


def test_execute_tasklist_links_events_to_correlation(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, conversation_id = run_tasklist(
        fcp, tasklist, chat2_store, correlation_id="corr-auto-1"
    )

    linked = chat2_store.get_events_by_correlation("corr-auto-1")
    assert [e.kind for e in linked] == ["system_note", "summary"]
    assert [e.metadata["correlation_id"] for e in linked] == ["corr-auto-1", "corr-auto-1"]


def test_execute_tasklist_reuses_existing_session(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    result, tasklist, conversation_id = run_tasklist(fcp, tasklist, chat2_store)
    result2, tasklist, _ = run_tasklist(
        fcp, tasklist, chat2_store, conversation_id=conversation_id
    )

    sessions = chat2_store.list_sessions(account_name="acct")
    assert len(sessions) == 1
    assert chat2_store.event_count(conversation_id) == 3


def test_process_message_writes_command_event_to_sqlite(chat2_store):
    fcp = RecordingFunctionProcessor()
    tasklist = make_tasklist()
    storage = FakeStorage(tasklist)
    ap = make_processor(chat2_store, storage)
    conversation_id = str(uuid.uuid4())
    command = json.dumps({"action": "run", "tasklist_id": "tl-1", "mode": "single-step"})

    result = ap.process_message(
        primary_agent=SimpleNamespace(name="test"),
        account={"accountId": "acct"},
        message=command,
        conversation_id=conversation_id,
        context_name="ctx",
        processor_factory=RecordingProcessorFactory(fcp),
    )

    assert "state=Failed" not in result
    assert chat2_store.session_exists(conversation_id)
    events = list(chat2_store.stream_events(conversation_id))
    assert [e.kind for e in events] == ["user_message", "system_note", "summary"]
    assert events[0].role == "user"
    assert events[0].actor == "acct"
    assert events[0].payload == command
    assert events[0].metadata["automation_kind"] == "automation_command"
