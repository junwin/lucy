"""Wiring tests for correlation to event linking.

Verifies that the FCP Chat2Recorder and the AutomationProcessor link
written chat2 events to the correlation sidecar index, and that the
best-effort/no-store paths stay no-ops.
"""

from __future__ import annotations

import uuid

from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore, StoreKey
from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.fcp_chat2 import Chat2Recorder
from src.message_processors.fcp_models import ProcessorContext
from src.message_processors.sse_events import SSEEvent


def _ctx(conversation_id: str, store_this_call: bool = True) -> ProcessorContext:
    return ProcessorContext(
        account_id="acct1",
        agent_name="lucy",
        conversation_id=conversation_id,
        context_name="ctx",
        model="test-model",
        temperature=0.0,
        context_type="hybrid",
        max_iterations=5,
        store_this_call=store_this_call,
        delegation_depth=0,
    )


def _make_automation_processor(chat2_store) -> AutomationProcessor:
    return AutomationProcessor(
        config=None,
        registry=None,
        storage=None,
        prompt_builder=None,
        chat2_store=chat2_store,
        llm_adapter=None,
        agent_manager=None,
    )


# ---------------------------------------------------------------------------
# FCP recorder wiring
# ---------------------------------------------------------------------------


class TestRecorderCorrelationWiring:
    """Tests for Chat2Recorder.write_streaming_events correlation linking."""

    def test_recorder_links_streaming_events(self) -> None:
        """Every event written by the recorder is linked to the correlation."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())

        recorder.write_streaming_events(
            _ctx(conversation_id),
            "user message",
            [
                SSEEvent(type="text", content="assistant reply"),
                SSEEvent(type="tool_call", tool_name="bash", call_id="call-1"),
            ],
            correlation_id=corr,
        )

        linked = facade.get_events_by_correlation(corr)
        assert len(linked) == 3
        session_events = facade.get_events(conversation_id)
        assert {e.event_id for e in linked} == {e.event_id for e in session_events}

    def test_recorder_no_correlation_no_links(self) -> None:
        """A recorder run without a correlation id writes no links."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())

        recorder.write_streaming_events(
            _ctx(conversation_id),
            "user message",
            [SSEEvent(type="text", content="reply")],
            correlation_id=None,
        )
        recorder.write_streaming_events(
            _ctx(conversation_id),
            "user message",
            [SSEEvent(type="text", content="reply 2")],
            correlation_id="",
        )

        assert store.list_keys(StoreKey("correlations/")) == []
        assert facade.event_count(conversation_id) == 4

    def test_best_effort_no_store(self) -> None:
        """Recorder without a chat2 store stays a no-op."""
        recorder = Chat2Recorder(None)
        recorder.write_streaming_events(
            _ctx(str(uuid.uuid4())),
            "user message",
            [SSEEvent(type="text", content="reply")],
            correlation_id=str(uuid.uuid4()),
        )


# ---------------------------------------------------------------------------
# Automation processor wiring
# ---------------------------------------------------------------------------


class TestAutomationCorrelationWiring:
    """Tests for AutomationProcessor._write_chat2_event correlation linking."""

    def test_automation_links_events(self) -> None:
        """_write_chat2_event links the written event when correlation is set."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        ap = _make_automation_processor(facade)
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())

        ap._write_chat2_event(
            conversation_id=conversation_id,
            account_name="acct1",
            agent_name="lucy",
            role="assistant",
            kind="automation_summary",
            payload="summary",
            correlation_id=corr,
        )
        ap._write_chat2_event(
            conversation_id=conversation_id,
            account_name="acct1",
            agent_name="lucy",
            role="user",
            kind="automation_command",
            payload="run",
            correlation_id=corr,
        )

        linked = facade.get_events_by_correlation(corr)
        assert len(linked) == 2
        session_events = facade.get_events(conversation_id)
        assert {e.event_id for e in linked} == {e.event_id for e in session_events}

    def test_automation_without_correlation_no_link(self) -> None:
        """_write_chat2_event without a correlation id writes no link."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        ap = _make_automation_processor(facade)
        conversation_id = str(uuid.uuid4())

        ap._write_chat2_event(
            conversation_id=conversation_id,
            account_name="acct1",
            agent_name="lucy",
            role="user",
            kind="automation_command",
            payload="run",
            correlation_id=None,
        )

        assert store.list_keys(StoreKey("correlations/")) == []
        assert facade.event_count(conversation_id) == 1

    def test_automation_no_store_noop(self) -> None:
        """Automation processor without a chat2 store stays a no-op."""
        ap = _make_automation_processor(None)
        ap._write_chat2_event(
            conversation_id=str(uuid.uuid4()),
            account_name="acct1",
            agent_name="lucy",
            role="user",
            kind="automation_command",
            payload="run",
            correlation_id=str(uuid.uuid4()),
        )
