import pytest

from src.tasklists.task_runner import TaskRunner
from src.agent import Agent


class _FakeProcessor:
    def __init__(self):
        self.calls = []

    def process_message(self, *, primary_agent, account, message, conversation_id="0", context_name="", secondary_agent=None, processor_factory=None):
        self.calls.append(
            {
                "primary_agent": primary_agent,
                "account": account,
                "message": message,
                "conversation_id": conversation_id,
                "context_name": context_name,
            }
        )
        return f"worker_done: {message[:30]}"


class _FakeProcessorFactory:
    def __init__(self, processor):
        self._processor = processor

    def get(self, name: str):
        return self._processor


def test_task_runner_executes_simple_tasklist_by_invoking_worker_processor():
    worker_processor = _FakeProcessor()
    factory = _FakeProcessorFactory(worker_processor)

    runner = TaskRunner(processor_factory=factory)

    supervisor = Agent(name="lucy", model="gpt", temperature=0.0)
    # allow delegation
    setattr(supervisor, "max_delegation_depth", 2)
    setattr(supervisor, "delegation_depth", 0)

    worker = Agent(name="colin", model="gpt", temperature=0.0, message_processor="function_calling")

    tasklist = {
        "ok": True,
        "kind": "tasklist",
        "description": "Do things",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "Work",
                "agent": "colin",
                "instruction": "Say hi",
                "file": "src/a.py",
            }
        ],
    }

    result = runner.run(
        tasklist=tasklist,
        supervisor_agent=supervisor,
        worker_agent=worker,
        account={"accountId": "john"},
        conversation_id="c1",
        context_name="lucyproject",
    )

    assert result["ok"] is True
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["ok"] is True
    assert len(worker_processor.calls) == 1
    assert "Say hi" in worker_processor.calls[0]["message"]
    assert "Focus file: src/a.py" in worker_processor.calls[0]["message"]


def test_task_runner_rejects_invalid_tasklist_schema():
    worker_processor = _FakeProcessor()
    factory = _FakeProcessorFactory(worker_processor)

    runner = TaskRunner(processor_factory=factory)

    supervisor = Agent(name="lucy", model="gpt", temperature=0.0)
    setattr(supervisor, "max_delegation_depth", 2)
    setattr(supervisor, "delegation_depth", 0)

    worker = Agent(name="colin", model="gpt", temperature=0.0, message_processor="function_calling")

    # missing tasks[*].instruction
    tasklist = {
        "kind": "tasklist",
        "description": "Do things",
        "tasks": [{"id": "task-1", "type": "task", "title": "Work", "agent": "colin"}],
    }

    result = runner.run(
        tasklist=tasklist,
        supervisor_agent=supervisor,
        worker_agent=worker,
        account={"accountId": "john"},
        conversation_id="c1",
        context_name="lucyproject",
    )

    assert result["ok"] is False
    assert "Invalid tasklist schema" in result["error"]
