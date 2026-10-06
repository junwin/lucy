"""Tests for AskRequestHandler.handle() with the FCPResult return contract."""

from __future__ import annotations


import json

import pytest

from tests.test_skillset_router import make_router, payload as routed_payload
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


@pytest.mark.parametrize("streaming", [False, True])
def test_routing_uses_specialist_configuration_in_both_modes(streaming):
    class StreamingProcessor(FakeProcessor):
        def process_message_streaming(self, **kwargs):
            self.calls.append(kwargs)
            yield 'data: {"type":"done"}\n\n'
    router = make_router()
    processor = StreamingProcessor(FCPResult(text="specialist answer", metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, Mock(), FakeStorage(), FakeProcessorFactory(processor), request_router=router)
    request = routed_payload(conversationId="existing")
    if streaming:
        events = list(handler.handle_streaming(request))
        route_event = json.loads(events[0].removeprefix("data: "))
        assert route_event["action"] == "request_routing"
        assert route_event["action_payload"]["selected_agent"] == "lumia"
    else:
        status, body = handler.handle(request)
        assert status == 200
        assert body["routing"]["selected_agent"] == "lumia"
    call = processor.calls[-1]
    assert call["primary_agent"].name == "lumia"
    assert call["primary_agent"].skills == ["image-cli"]
    assert call["primary_agent"].prompt_policy == {"procedural_tokens": 4000}
    assert call["context_name"] == "image_tool"
    assert call["conversation_id"] == "existing"
    assert request["agentName"] == "lucy"  # caller payload is not mutated


@pytest.mark.parametrize("streaming", [False, True])
def test_uncertain_routing_returns_clarification_without_worker_or_context_creation(streaming):
    router = make_router({"kind": "clarify", "capabilities": [], "confidence": .9})
    processor = FakeProcessor(FCPResult(text="should not run", metrics=RunMetrics()))
    storage = FakeStorage()
    handler = AskRequestHandler(router.agent_manager, Mock(), storage, FakeProcessorFactory(processor), request_router=router)
    if streaming:
        events = [json.loads(e.removeprefix("data: ")) for e in handler.handle_streaming(routed_payload())]
        assert [e["type"] for e in events] == ["action", "text", "done"]
        assert events[1]["content"]
    else:
        status, body = handler.handle(routed_payload())
        assert status == 200
        assert body["needs_clarification"] is True
    assert processor.calls == []
    assert storage.created == []


@pytest.mark.parametrize("streaming", [False, True])
def test_auto_routing_accepts_omitted_agent(streaming):
    class StreamingProcessor(FakeProcessor):
        def process_message_streaming(self, **kwargs):
            self.calls.append(kwargs)
            yield 'data: {"type":"done"}\n\n'
    router = make_router()
    processor = StreamingProcessor(FCPResult(text="ok", metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, Mock(), FakeStorage(), FakeProcessorFactory(processor), request_router=router)
    request = routed_payload()
    del request["agentName"]
    if streaming:
        list(handler.handle_streaming(request))
    else:
        assert handler.handle(request)[0] == 200
    assert processor.calls[-1]["primary_agent"].name == "lumia"


def test_routing_invalid_mode_and_missing_identity_do_not_call_classifier():
    router = make_router()
    processor = FakeProcessor(FCPResult(text="ok", metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, Mock(), FakeStorage(), FakeProcessorFactory(processor), request_router=router)
    for request in (routed_payload(routing="bogus"), routed_payload(accountName=""), routed_payload(question="")):
        assert handler.handle(request)[0] == 400
    router.llm_adapter.call_model.assert_not_called()


def test_clarification_is_saved_for_followup_and_keeps_trace(tmp_path):
    from galet_memory import SqliteEpisodicMemory
    memory = SqliteEpisodicMemory(tmp_path / "chat.sqlite")
    router = make_router({"kind": "clarify", "capabilities": [], "confidence": .9})
    processor = FakeProcessor(FCPResult(text="should not run", metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, Mock(), FakeStorage(), FakeProcessorFactory(processor),
                                episodic_store=memory, request_router=router)
    status, body = handler.handle(routed_payload(question="Make it better"))
    assert status == 200
    session = memory.get_active_snapshot(account_name='alice', session_id=body["conversation_id"])
    assert [e.role for e in session.events] == ["user", "assistant"]
    assert session.events[0].content == "Make it better"
    assert session.events[1].content == body["response"]
    assert session.events[0].metadata["run_id"] == body["run_id"]
    assert body["trace_id"] == body["run_id"]
    assert processor.calls == []
    router.episodic_store = memory
    status, followup = handler.handle(routed_payload(
        question="one that can work with images i.e. image-processing",
        conversationId=body["conversation_id"],
    ))
    assert status == 200
    assert followup["routing"]["selected_agent"] == "lumia"
    assert followup["routing"]["classifier_calls"] == 0
    assert followup["conversation_id"] == body["conversation_id"]
    assert processor.calls[-1]["primary_agent"].name == "lumia"
    assert memory.get_active_snapshot(account_name='alice', session_id=body["conversation_id"]).events[0].content == "Make it better"
