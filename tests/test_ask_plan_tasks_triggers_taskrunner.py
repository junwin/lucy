import json

from src.message_endpoints.ask_request_handler import AskRequestHandler


class _DummyAgent:
    def __init__(
        self,
        name: str,
        message_processor: str = "dummy",
        context_type: str = "hybrid",
        partner_agent: str = "",
    ):
        self.name = name
        self.message_processor = message_processor
        self.context_type = context_type
        self.partner_agent = partner_agent
        self.save_responses = False


class _DummyAgentManager:
    def __init__(self, agents):
        self._agents = {a.name: a for a in agents}

    def is_valid(self, name: str) -> bool:
        return name in self._agents

    def get_agent(self, name: str):
        return self._agents.get(name)


class _DummyStorage:
    def append_chat_message(self, *args, **kwargs):
        return None


class _DummyConfig:
    def get(self, *args, **kwargs):
        return None


class _DummyProcessor:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return self._response_text


class _DummyProcessorFactory:
    def __init__(self, processors_by_name):
        self._processors = processors_by_name

    def get(self, name: str):
        return self._processors[name]


class _SpyTaskRunner:
    def __init__(self):
        self.called = False
        self.args = None

    def run(self, **kwargs):
        self.called = True
        self.args = kwargs
        return {"ok": True, "description": "x", "tasks": []}


def test_ask_flow_plan_tasks_returns_tasklist_and_triggers_taskrunner():
    supervisor = _DummyAgent("lucy", message_processor="super")
    worker = _DummyAgent("colin", message_processor="worker")
    supervisor.partner_agent = "colin"

    tasklist_json = json.dumps({"ok": True, "kind": "tasklist", "description": "d", "tasks": []})

    supervisor_proc = _DummyProcessor(tasklist_json)
    worker_proc = _DummyProcessor("worker-done")

    factory = _DummyProcessorFactory({"super": supervisor_proc, "worker": worker_proc})
    runner = _SpyTaskRunner()

    handler = AskRequestHandler(
        agent_manager=_DummyAgentManager([supervisor, worker]),
        config=_DummyConfig(),  # type: ignore[arg-type]
        storage=_DummyStorage(),  # type: ignore[arg-type]
        processor_factory=factory,  # type: ignore[arg-type]
        task_runner=runner,  # type: ignore[arg-type]
    )

    status, body = handler.handle(
        {
            "question": "please plan",
            "agentName": "lucy",
            "accountName": "john",
            "conversationId": "c1",
        }
    )

    assert status == 200
    assert runner.called is True

    # response is the task runner result (serialised)
    parsed = json.loads(body["response"])
    assert parsed["ok"] is True
