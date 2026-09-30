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
        episodic_store=None,
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


def test_remote_ask_preserves_trace_but_mints_local_run():
    import uuid

    processor = FakeProcessor(FCPResult(text="ok", metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    root_id = str(uuid.uuid4())
    parent_id = str(uuid.uuid4())

    status, body = handler.handle(make_payload(
        conversationId="conv-remote",
        executionTrace={"trace_id": root_id, "parent_run_id": parent_id},
    ))

    assert status == 200
    assert body["trace_id"] == root_id
    assert body["parent_run_id"] == parent_id
    assert body["run_id"] != parent_id
    assert processor.calls[0]["correlation_id"] == body["run_id"]
    assert processor.calls[0]["trace_id"] == root_id


def test_invalid_remote_lineage_starts_new_trace():
    processor = FakeProcessor(FCPResult(text="ok", metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())

    status, body = handler.handle(make_payload(
        conversationId="conv-remote",
        executionTrace={"trace_id": "bogus", "parent_run_id": "also-bogus"},
    ))

    assert status == 200
    assert body["trace_id"] == body["run_id"]
    assert body["parent_run_id"] is None


def test_agent_default_and_explicit_context_apply_in_both_ask_modes():
    from src.agent import Agent
    class StreamingProcessor(FakeProcessor):
        def process_message_streaming(self, **kwargs):
            self.calls.append(kwargs)
            yield "done"
    for streaming in (False, True):
        for explicit, expected in ((None, "images"), ("override", "override")):
            agent = Agent(name="lumia", default_context="images", skills=["image-cli"],
                          prompt_policy={"procedural_tokens": 1500})
            processor = StreamingProcessor(FCPResult(text="ok", metrics=RunMetrics()))
            handler = make_handler(processor, agent)
            payload = make_payload(agentName="lumia", conversationId="existing")
            if explicit is not None:
                payload["contextName"] = explicit
            if streaming:
                assert list(handler.handle_streaming(payload)) == ["done"]
            else:
                assert handler.handle(payload)[0] == 200
            call = processor.calls[-1]
            assert call["context_name"] == expected
            assert call["primary_agent"].skills == ["image-cli"]
            assert call["primary_agent"].prompt_policy == {"procedural_tokens": 1500}
