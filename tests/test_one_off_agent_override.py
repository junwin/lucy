"""One-message @agent directives bypass routing without changing preferences."""

import json
from unittest.mock import Mock

import pytest
from galet_memory import SqliteEpisodicMemory

from src.message_endpoints.ask_request_handler import AskRequestHandler
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from tests.test_ask_request_handler import FakeProcessor, FakeProcessorFactory, FakeStorage
from tests.test_skillset_router import make_router, payload


class StreamingProcessor(FakeProcessor):
    def process_message_streaming(self, **kwargs):
        self.calls.append(kwargs)
        yield 'data: {"type":"text","content":"finished"}\n\n'
        yield 'data: {"type":"done"}\n\n'


def make_handler(router, processor, *, with_router=True):
    return AskRequestHandler(
        agent_manager=router.agent_manager,
        config=Mock(),
        storage=FakeStorage(),
        processor_factory=FakeProcessorFactory(processor),
        request_router=router if with_router else None,
    )


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("mode", ["explicit", "auto"])
def test_leading_agent_directive_dispatches_once_with_agent_context_and_metadata(streaming, mode):
    router = make_router()
    processor = StreamingProcessor(FCPResult(text="finished", metrics=RunMetrics()))
    handler = make_handler(router, processor)
    request = payload(
        routing=mode, agentName="lucy", question="  @LuMiA  Create the image",
        contextName="sidebar-context", image_ids=["img-1"], file_ids=["file-1"],
        partnerAgentName="star", conversationId="existing",
    )

    if streaming:
        events = [json.loads(line.removeprefix("data: "))
                  for line in handler.handle_streaming(request)]
        routing = events[0]["action_payload"]
        assert events[0]["action"] == "request_routing"
    else:
        status, body = handler.handle(request)
        assert status == 200
        routing = body["routing"]

    assert routing["reason"] == "one_off_agent_override"
    assert routing["selected_agent"] == "lumia"
    assert router.llm_adapter.call_model.call_count == 0
    call = processor.calls[0]
    assert call["primary_agent"].name == "lumia"
    assert call["message"] == "Create the image"
    assert call["context_name"] == "image_tool"
    assert call["secondary_agent"] is None
    assert call["image_ids"] == ["img-1"]
    assert call["file_ids"] == ["file-1"]
    assert call["conversation_id"] == "existing"


@pytest.mark.parametrize("question", [
    "Could you ask @lumia to make an image?",
    'The quoted text says "@lumia make an image".',
])
def test_incidental_and_quoted_mentions_are_not_dispatch_directives(question):
    router = make_router({"kind": "general", "capabilities": [], "confidence": .99})
    processor = FakeProcessor(FCPResult(text="general answer", metrics=RunMetrics()))
    handler = make_handler(router, processor)

    status, body = handler.handle(payload(question=question))

    assert status == 200
    assert body["routing"]["selected_agent"] == "lucy"
    assert body["routing"]["reason"] == "general"
    router.llm_adapter.call_model.assert_called_once()


@pytest.mark.parametrize("question,expected", [
    ("@unknown do this", "available agent"),
    ("@lumia   ", "include a request"),
])
def test_invalid_or_empty_directive_returns_clarification_without_worker(question, expected):
    router = make_router()
    processor = FakeProcessor(FCPResult(text="should not run", metrics=RunMetrics()))
    handler = make_handler(router, processor)

    status, body = handler.handle(payload(question=question))

    assert status == 200
    assert body["needs_clarification"] is True
    assert expected in body["response"].lower()
    assert processor.calls == []
    router.llm_adapter.call_model.assert_not_called()


def test_one_off_dispatch_works_without_auto_router():
    router = make_router()
    processor = FakeProcessor(FCPResult(text="done", metrics=RunMetrics()))
    handler = make_handler(router, processor, with_router=False)

    status, body = handler.handle(payload(
        routing="explicit", question="@lumia Create the image", contextName="sidebar-context",
    ))

    assert status == 200
    assert body["routing"]["reason"] == "one_off_agent_override"
    assert processor.calls[0]["primary_agent"].name == "lumia"
    assert processor.calls[0]["context_name"] == "image_tool"


def test_override_keeps_existing_session_context_and_specialist_affinity(tmp_path):
    router = make_router()
    processor = FakeProcessor(FCPResult(text="done", metrics=RunMetrics()))
    with SqliteEpisodicMemory(tmp_path / "one-off.sqlite") as memory:
        session = memory.create_session(
            account_name="alice",
            metadata={"default_agent": "lucy", "routing_dialogue": {
                "agent": "belle", "expires_at": 9000, "awaiting_reply": True,
            }, "custom": "keep"},
            context_name="existing-context",
        )
        router.episodic_store = memory
        handler = AskRequestHandler(
            agent_manager=router.agent_manager,
            config=Mock(),
            storage=FakeStorage(),
            processor_factory=FakeProcessorFactory(processor),
            episodic_store=memory,
            request_router=router,
        )

        status, _ = handler.handle(payload(
            routing="auto", question="@lumia Create the image",
            conversationId=session.session_id, contextName="sidebar-context",
        ))

        stored = memory.get_session(account_name="alice", session_id=session.session_id)
        assert status == 200
        assert processor.calls[0]["context_name"] == "image_tool"
        assert stored.context_name == "existing-context"
        assert stored.metadata["routing_dialogue"] == {
            "agent": "belle", "expires_at": 9000, "awaiting_reply": True,
        }
        assert stored.metadata["custom"] == "keep"
