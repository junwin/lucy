"""Tests for AskRequestHandler.handle() with the FCPResult return contract."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import Mock

from src.message_endpoints.ask_request_handler import AskRequestHandler
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics


class FakeAgentManager:
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def is_valid(self, name: str) -> bool:
        return self._agent is not None and self._agent.name == name

    def get_agent(self, name: str) -> Any:
        return self._agent if self.is_valid(name) else None


class FakeStorage:
    def __init__(self) -> None:
        self.created: list[tuple[str, str]] = []

    def get_or_create_context(self, account_name: str, context_id: str) -> None:
        self.created.append((account_name, context_id))


class FakeProcessor:
    def __init__(self, result: FCPResult) -> None:
        self.result = result
        self.calls: list[Dict[str, Any]] = []

    def process_message(self, **kwargs) -> FCPResult:
        self.calls.append(kwargs)
        return self.result


class FakeProcessorFactory:
    def __init__(self, processor: FakeProcessor) -> None:
        self.processor = processor

    def get(self, name: str) -> FakeProcessor:
        return self.processor


def make_agent(name: str = "lucy") -> Any:
    agent = Mock(name=name)
    agent.name = name
    agent.message_processor = "function_calling_processor"
    agent.context_type = "hybrid"
    agent.default_context = None
    agent.partner_agent = None
    return agent


def make_handler(processor: FakeProcessor, agent: Any) -> AskRequestHandler:
    return AskRequestHandler(
        agent_manager=FakeAgentManager(agent),
        config=Mock(),
        storage=FakeStorage(),
        processor_factory=FakeProcessorFactory(processor),
        chat2_store=None,
    )


def make_payload(**overrides: Any) -> Dict[str, Any]:
    payload = {
        "question": "hello",
        "agentName": "lucy",
        "accountName": "alice",
    }
    payload.update(overrides)
    return payload


class TestAskRequestHandlerHandle:
    def test_handle_uses_result_text_from_fcp_result(self) -> None:
        metrics = RunMetrics(correlation_id="cid-1", iterations=2, failures=0)
        processor = FakeProcessor(FCPResult(text="hello from lucy", metrics=metrics))
        handler = make_handler(processor, make_agent())

        status, body = handler.handle(make_payload())

        assert status == 200
        assert body["response"] == "hello from lucy"
        assert isinstance(body["conversation_id"], str)
        assert body["conversation_id"]

    def test_handle_passes_context_and_correlation_to_processor(self) -> None:
        processor = FakeProcessor(FCPResult(text="ok", metrics=RunMetrics()))
        handler = make_handler(processor, make_agent())

        handler.handle(
            make_payload(
                conversationId="conv-42",
                contextType="obsidian",
                contextName="notes",
                image_ids=["img-1"],
                file_ids=["file-1"],
            )
        )

        assert len(processor.calls) == 1
        call = processor.calls[0]
        assert call["message"] == "hello"
        assert call["conversation_id"] == "conv-42"
        assert call["context_name"] == "notes"
        assert call["image_ids"] == ["img-1"]
        assert call["file_ids"] == ["file-1"]
        assert call["correlation_id"]
