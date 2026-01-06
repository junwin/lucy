import json

from src.message_endpoints.ask_request_handler import AskRequestHandler
from src.agent import Agent


class _FakeAgentManager:
    def __init__(self, agents):
        self._agents = {a.name.lower(): a for a in agents}

    def is_valid(self, name: str) -> bool:
        return name.lower() in self._agents

    def get_agent(self, name: str):
        return self._agents.get(name.lower())


class _FakeProcessor:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.response_text


class _FakeProcessorFactory:
    def __init__(self, primary_processor, worker_processor):
        self.primary_processor = primary_processor
        self.worker_processor = worker_processor

    def get(self, name: str):
        # route by message_processor names we set on Agent
        if name == "primary":
            return self.primary_processor
        if name == "worker":
            return self.worker_processor
        return self.primary_processor


class _FakeStorage:
    def append_chat_message(self, *args, **kwargs):
        return None


def test_ask_flow_plan_tasks_returns_tasklist_and_triggers_task_runner_execution(monkeypatch):
    # Primary processor returns a plan_tasks tool output (JSON string)
    planned = {
        "ok": True,
        "kind": "tasklist",
        "description": "run",
        "tasks": [
            {
                "id": "task-1",
                "type": "task",
                "title": "t",
                "agent": "colin",
                "instruction": "Do work",
            }
        ],
    }

    primary_processor = _FakeProcessor(json.dumps(planned))
    worker_processor = _FakeProcessor("done")

    # Agents
    supervisor = Agent(name="lucy", model="gpt", temperature=0.0, message_processor="primary")
    setattr(supervisor, "max_delegation_depth", 2)
    setattr(supervisor, "delegation_depth", 0)

    worker = Agent(name="colin", model="gpt", temperature=0.0, message_processor="worker")

    agent_manager = _FakeAgentManager([supervisor, worker])

    factory = _FakeProcessorFactory(primary_processor, worker_processor)

    handler = AskRequestHandler(
        agent_manager=agent_manager,
        config=None,  # unused by handler
        storage=_FakeStorage(),
        processor_factory=factory,
    )

    status, body = handler.handle(
        {
            "question": "please plan",
            "agentName": "lucy",
            "accountName": "john",
            "conversationId": "c1",
            "partnerAgentName": "colin",
        }
    )

    assert status == 200
    # after autorun, response becomes TaskRunner summary JSON
    result = json.loads(body["response"])
    assert "tasks" in result
    assert result["tasks"][0]["ok"] is True
    assert len(worker_processor.calls) == 1


def test_no_execute_simple_tasklist_method_exists_anywhere():
    # Regression: ensure old helper is not called/kept around.
    import os

    for root, _, files in os.walk("src"):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                s = fh.read()
            assert "_execute_simple_tasklist" not in s
