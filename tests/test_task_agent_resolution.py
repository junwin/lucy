"""Tests for per-task agent resolution (GH issue #121).

Each task may carry an `agent` field naming the agent that should execute it.
AutomationProcessor must resolve that agent via AgentManager and pass it as
`primary_agent` to the FunctionCallingProcessor, falling back to the caller's
primary agent when the field is unset, matches the caller, or names an unknown
agent.
"""

import uuid

from src.agent.agent import Agent
from src.message_processors.automation_processor import AutomationProcessor
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
        self.captured.append(getattr(primary, "name", None))
        return "done"


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


def make_tasklist(task_agent=None):
    task = Task(
        id=str(uuid.uuid4()),
        name="T1",
        instructions="Do the thing",
        agent=task_agent,
    )
    return TaskList(id="tl-1", name="demo", description="demo", tasks=[task])


def callers():
    return Agent(name="lucy")


def test_resolve_agent_unset_falls_back_to_primary():
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


def test_resolve_agent_unknown_falls_back_to_primary():
    ap, _ = make_processor(agent_manager=FakeAgentManager([]))
    task = make_tasklist(task_agent="star").tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy")
    assert resolved.name == "lucy"


def test_resolve_agent_without_manager_falls_back_to_primary():
    ap, _ = make_processor(agent_manager=None)
    task = make_tasklist(task_agent="star").tasks[0]
    resolved = ap._resolve_task_agent(task, callers(), "lucy")
    assert resolved.name == "lucy"


def _run_and_capture(agent_manager, task_agent, caller_name, worker_agent=None):
    tasklist = make_tasklist(task_agent=task_agent)
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
        context_name="ctx",
        primary_agent=Agent(name=caller_name),
        account={"accountId": "acct"},
        processor_factory=FakeProcessorFactory(capture),
        worker_agent=worker_agent,
    )
    return capture, tasklist


def test_execute_passes_task_agent_as_primary():
    capture, tasklist = _run_and_capture(
        agent_manager=FakeAgentManager([Agent(name="star")]),
        task_agent="star",
        caller_name="lucy",
    )
    assert capture.captured == ["star"]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_falls_back_to_caller_when_task_agent_unknown():
    capture, tasklist = _run_and_capture(
        agent_manager=FakeAgentManager([]),
        task_agent="star",
        caller_name="lucy",
    )
    assert capture.captured == ["lucy"]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED


def test_execute_worker_agent_override_wins_over_task_agent():
    capture, tasklist = _run_and_capture(
        agent_manager=FakeAgentManager([Agent(name="star"), Agent(name="colin")]),
        task_agent="star",
        caller_name="lucy",
        worker_agent="colin",
    )
    assert capture.captured == ["colin"]
    assert tasklist.tasks[0].state == TASK_STATE_COMPLETED
