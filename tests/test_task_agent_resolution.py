"""Tests for per-task agent and context resolution (GH issues #121, #137).

Each task may carry an `agent` field naming the agent that should execute it.
Per task the agent resolves as: task.agent, else the caller's partner (the
passed secondary_agent, else the caller's configured partner_agent when it
resolves via AgentManager), else the caller itself. A task naming an unknown
agent raises ValueError; there is no silent fallback to the caller. A run-level
worker_agent override wins over per-task resolution and also raises ValueError
when the named agent does not exist.

Per task the context resolves as: the run-level context_name when non-empty,
else task.context, else the resolved agent's default_context, else "".
"""

import uuid

import pytest

from src.agent.agent import Agent
from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList
from src.tasklists.task_states import TASK_STATE_COMPLETED


class FakeAgentManager:
    def __init__(self, agents):
        self.agents = {a.name: a for a in agents}

    def get_agent(self, name):
        return self.agents.get(name)


class CaptureFunctionProcessor:
    def __init__(self):
        self.captured = []

    def process_message(self, **kwargs):
        primary = kwargs.get("primary_agent")
        self.captured.append(
            {
                "agent_name": getattr(primary, "name", None),
                "context_name": kwargs.get("context_name"),
            }
        )
        return FCPResult(text="done", metrics=RunMetrics())


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

    def get_tasklist(self, account_name, tasklist_id):
        return self.tasklist

    def list_tasklists(self, account_name):
        return [self.tasklist.id]

    def save_tasklist(self, account_name, tasklist_id, data):
        return None

    def append_task_execution_record(self, account_name, tasklist_key, record):
        return None


def make_processor(agent_manager=None, function_processor=None):
    storage = FakeStorage(make_tasklist())
    return AutomationProcessor(
        config=None,
        registry=None,
        storage=storage,
        prompt_builder=None,
        chat2_store=None,
        llm_adapter=None,
        agent_manager=agent_manager,
    ), function_processor


def make_tasklist(task_agent=None, task_context=None):
    task = Task(
        id=str(uuid.uuid4()),
        name="T1",
        instructions="Do the thing",
        agent=task_agent,
        context=task_context,
    )
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def callers():
    return Agent(name="lucy")


def test_resolve_agent_unset_no_partner_uses_caller():
    ap, _ = make_processor(agent_manager=FakeAgentManager([]))
    task = make_tasklist().tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy")
    assert resolved.name == "lucy"


def test_resolve_agent_same_as_caller_uses_primary():
    ap, _ = make_processor(agent_manager=FakeAgentManager([]))
    task = make_tasklist(task_agent="lucy").tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy")
    assert resolved.name == "lucy"


def test_resolve_agent_finds_worker():
    star = Agent(name="star")
    ap, _ = make_processor(agent_manager=FakeAgentManager([star]))
    task = make_tasklist(task_agent="star").tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy")
    assert resolved.name == "star"


def test_resolve_agent_unknown_raises():
    ap, _ = make_processor(agent_manager=FakeAgentManager([]))
    task = make_tasklist(task_agent="star").tasks[0]
    with pytest.raises(ValueError):
        ap._resolve_task_agent(task, callers(), "lucy")


def test_resolve_agent_without_manager_task_agent_raises():
    ap, _ = make_processor(agent_manager=None)
    task = make_tasklist(task_agent="star").tasks[0]
    with pytest.raises(ValueError):
        ap._resolve_task_agent(task, callers(), "lucy")


def test_resolve_agent_unset_uses_secondary_partner():
    star = Agent(name="star")
    ap, _ = make_processor(agent_manager=FakeAgentManager([]))
    task = make_tasklist().tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy", secondary_agent=star)
    assert resolved.name == "star"


def test_resolve_agent_unset_uses_caller_partner_agent():
    star = Agent(name="star")
    lucy = Agent(name="lucy", partner_agent="star")
    ap, _ = make_processor(agent_manager=FakeAgentManager([star]))
    task = make_tasklist().tasks[0]
    resolved = ap._resolve_task_agent(task, lucy, "lucy")
    assert resolved.name == "star"


def _run_and_capture(
    agent_manager=None,
    task_agent=None,
    caller_name="lucy",
    caller_agent=None,
    worker_agent=None,
    context_name="",
    secondary_agent=None,
    task_context=None,
    task_agent_default_ctx=None,
):
    primary = caller_agent or Agent(name=caller_name)
    if agent_manager is None:
        manager_agents = []
        manager_names = set()

        def add_agent(name, default_context=None):
            if name and name not in manager_names:
                manager_agents.append(Agent(name=name, default_context=default_context))
                manager_names.add(name)

        add_agent(task_agent, task_agent_default_ctx)
        add_agent(getattr(primary, "partner_agent", None))
        add_agent(worker_agent)
        agent_manager = FakeAgentManager(manager_agents)

    tasklist = make_tasklist(task_agent=task_agent, task_context=task_context)
    storage = FakeStorage(tasklist)
    capture = CaptureFunctionProcessor()
    ap = AutomationProcessor(
        config=None,
        registry=None,
        storage=storage,
        prompt_builder=None,
        chat2_store=None,
        llm_adapter=None,
        agent_manager=agent_manager,
    )
    ap.execute_tasklist(
        tasklist_id="tl-1",
        mode="single-step",
        account_name="acct",
        agent_name=caller_name,
        conversation_id="conv-1",
        context_name=context_name,
        primary_agent=primary,
        account={"accountId": "acct"},
        processor_factory=FakeProcessorFactory(capture),
        worker_agent=worker_agent,
        secondary_agent=secondary_agent,
    )
    return capture, tasklist


def test_execute_passes_task_agent_as_primary():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_unset_task_agent_uses_secondary_partner():
    capture, tasklist = _run_and_capture(
        caller_name="lucy",
        secondary_agent=Agent(name="star"),
    )
    assert capture.captured == [{"agent_name": "star", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_unset_task_agent_uses_caller_partner():
    capture, tasklist = _run_and_capture(
        caller_agent=Agent(name="lucy", partner_agent="star"),
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_unset_task_agent_no_partner_uses_caller():
    capture, tasklist = _run_and_capture(
        agent_manager=FakeAgentManager([]),
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "lucy", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_unknown_task_agent_raises():
    with pytest.raises(ValueError):
        _run_and_capture(
            agent_manager=FakeAgentManager([]),
            task_agent="star",
            caller_name="lucy",
        )


def test_execute_worker_agent_override_wins_over_task_agent():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        caller_name="lucy",
        worker_agent="colin",
    )
    assert capture.captured == [{"agent_name": "colin", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_unknown_worker_agent_raises():
    with pytest.raises(ValueError):
        _run_and_capture(
            agent_manager=FakeAgentManager([Agent(name="star")]),
            task_agent="star",
            caller_name="lucy",
            worker_agent="colin",
        )


def test_execute_run_context_override_wins_over_task_context_and_agent_default():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        task_agent_default_ctx="star_ctx",
        task_context="task_ctx",
        context_name="run_ctx",
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": "run_ctx"}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_task_context_beats_agent_default_context():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        task_agent_default_ctx="star_ctx",
        task_context="task_ctx",
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": "task_ctx"}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_agent_default_context_used_when_task_context_unset():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        task_agent_default_ctx="star_ctx",
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": "star_ctx"}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_no_context_resolves_to_empty():
    capture, tasklist = _run_and_capture(
        task_agent="star",
        caller_name="lucy",
    )
    assert capture.captured == [{"agent_name": "star", "context_name": ""}]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED
