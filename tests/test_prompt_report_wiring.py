"""Wiring tests for Chat2Recorder.write_prompt_report.

Verifies that the prompt token breakdown is persisted as a chat2
'prompt_report' system event, linked to the correlation sidecar index
when a correlation id is provided, and that the best-effort/no-store
paths stay no-ops.
"""

from __future__ import annotations

import uuid

from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore, StoreKey
from src.message_processors.fcp_chat2 import Chat2Recorder
from src.message_processors.fcp_models import ProcessorContext


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


def _breakdown() -> dict:
    return {
        "system": 1,
        "handlers": 2,
        "context": 3,
        "obsidian": 4,
        "digest": 5,
        "history": 6,
        "user": 7,
        "total": 28,
    }


class TestWritePromptReportWiring:
    """Tests for Chat2Recorder.write_prompt_report."""

    def test_write_prompt_report_writes_event(self) -> None:
        """write_prompt_report creates one system/prompt_report event in the session."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())
        breakdown = _breakdown()

        recorder.write_prompt_report(_ctx(conversation_id), breakdown)

        events = facade.get_events(conversation_id)
        assert len(events) == 1
        assert events[0].role == "system"
        assert events[0].actor == "lucy"
        assert events[0].kind == "prompt_report"
        assert events[0].payload == breakdown

    def test_write_prompt_report_links_correlation(self) -> None:
        """With a correlation id, the event is linked and matches the session."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())
        breakdown = _breakdown()

        recorder.write_prompt_report(
            _ctx(conversation_id), breakdown, correlation_id=corr
        )

        linked = facade.get_events_by_correlation(corr)
        assert len(linked) == 1
        assert linked[0].kind == "prompt_report"
        assert linked[0].payload == breakdown
        session_events = facade.get_events(conversation_id)
        assert {e.event_id for e in linked} == {e.event_id for e in session_events}

    def test_write_prompt_report_no_correlation_no_link(self) -> None:
        """None and '' correlation ids write the event but no links."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())
        breakdown = _breakdown()

        recorder.write_prompt_report(
            _ctx(conversation_id), breakdown, correlation_id=None
        )
        recorder.write_prompt_report(
            _ctx(conversation_id), breakdown, correlation_id=""
        )

        assert store.list_keys(StoreKey("correlations/")) == []
        events = facade.get_events(conversation_id)
        assert len(events) == 2
        assert all(e.kind == "prompt_report" for e in events)

    def test_write_prompt_report_no_store_noop(self) -> None:
        """A recorder without a chat2 store raises nothing."""
        recorder = Chat2Recorder(None)
        recorder.write_prompt_report(
            _ctx(str(uuid.uuid4())), _breakdown(), correlation_id=str(uuid.uuid4())
        )

    def test_write_prompt_report_best_effort(self) -> None:
        """A failing add_events does not propagate from write_prompt_report."""
        store = InMemoryStore()
        facade = Chat2Store(store)
        recorder = Chat2Recorder(facade)
        conversation_id = str(uuid.uuid4())
        breakdown = _breakdown()

        def boom(session_id, events):
            raise RuntimeError("add_events exploded")

        facade.add_events = boom

        recorder.write_prompt_report(
            _ctx(conversation_id), breakdown, correlation_id=str(uuid.uuid4())
        )
        assert facade.event_count(conversation_id) == 0


def _pb_breakdown() -> dict:
    """Prompt-builder style breakdown for mock prompt_builder._last_prompt_token_breakdown."""
    return {
        "system_session": 1,
        "context_text": 3,
        "obsidian_notes": 4,
        "digest_embeddings": 5,
        "chat_history": 6,
        "current_user_message": 7,
        "total_without_handlers": 21,
    }


def _expected_report() -> dict:
    """The persisted prompt_report payload the FCP derives from _pb_breakdown()."""
    return {
        "system": 1,
        "handlers": 0,
        "context": 3,
        "obsidian": 4,
        "digest": 5,
        "history": 6,
        "user": 7,
        "total": 21,
    }


class TestFcpPromptReportWiring:
    """FCP-level wiring tests for the prompt_report persistence (issue #134)."""

    def test_process_message_emits_prompt_report(
        self, make_proc, prompt_builder, llm_adapter
    ) -> None:
        """process_message writes one prompt_report linked to the correlation id."""
        from tests.conftest import FakeAgent

        facade = Chat2Store(InMemoryStore())
        proc = make_proc(chat2_store=facade)
        prompt_builder._last_prompt_token_breakdown = _pb_breakdown()
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())

        out = proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=conversation_id,
            context_name="ctx",
            correlation_id=corr,
        )

        assert out.text == "ok"
        reports = facade.get_events(conversation_id, kind_filter="prompt_report")
        assert len(reports) == 1
        assert reports[0].role == "system"
        assert reports[0].actor == "lucy"
        assert reports[0].payload == _expected_report()
        linked = facade.get_events_by_correlation(corr)
        assert {e.event_id for e in linked if e.kind == "prompt_report"} == {
            reports[0].event_id
        }

    def test_process_message_streaming_emits_prompt_report(
        self, make_proc, prompt_builder, llm_adapter
    ) -> None:
        """process_message_streaming yields events and persists one linked prompt_report."""
        from tests.conftest import FakeAgent

        facade = Chat2Store(InMemoryStore())
        proc = make_proc(chat2_store=facade)
        prompt_builder._last_prompt_token_breakdown = _pb_breakdown()
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())

        sse_events = list(
            proc.process_message_streaming(
                primary_agent=FakeAgent(save_responses=True),
                account={"accountId": "acct1"},
                message="hi",
                conversation_id=conversation_id,
                context_name="ctx",
                correlation_id=corr,
            )
        )

        assert sse_events
        assert any('"type":"text"' in sse for sse in sse_events)
        reports = facade.get_events(conversation_id, kind_filter="prompt_report")
        assert len(reports) == 1
        assert reports[0].payload == _expected_report()
        linked = facade.get_events_by_correlation(corr)
        assert {e.event_id for e in linked if e.kind == "prompt_report"} == {
            reports[0].event_id
        }

    def test_no_report_when_store_this_call_false(
        self, make_proc, prompt_builder, llm_adapter
    ) -> None:
        """save_responses=False writes no report and creates no session."""
        from tests.conftest import FakeAgent

        facade = Chat2Store(InMemoryStore())
        proc = make_proc(chat2_store=facade)
        prompt_builder._last_prompt_token_breakdown = _pb_breakdown()
        conversation_id = str(uuid.uuid4())

        out = proc.process_message(
            primary_agent=FakeAgent(save_responses=False),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=conversation_id,
            context_name="ctx",
        )

        assert out.text == "ok"
        assert facade.get_events(conversation_id) == []
        assert facade.session_exists(conversation_id) is False

    def test_process_message_without_store_noop(
        self, make_proc, prompt_builder, llm_adapter
    ) -> None:
        """An FCP without a chat2 store still returns a normal FCPResult."""
        from tests.conftest import FakeAgent
        from src.message_processors.function_calling_processor import FCPResult

        proc = make_proc()
        conversation_id = str(uuid.uuid4())
        corr = str(uuid.uuid4())

        out = proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=conversation_id,
            context_name="ctx",
            correlation_id=corr,
        )

        assert isinstance(out, FCPResult)
        assert out.text == "ok"
        assert out.metrics.correlation_id == corr

    def test_one_prompt_report_per_request(
        self, make_proc, prompt_builder, llm_adapter
    ) -> None:
        """A single request produces exactly one prompt_report event."""
        from tests.conftest import FakeAgent

        facade = Chat2Store(InMemoryStore())
        proc = make_proc(chat2_store=facade)
        prompt_builder._last_prompt_token_breakdown = _pb_breakdown()
        conversation_id = str(uuid.uuid4())

        proc.process_message(
            primary_agent=FakeAgent(save_responses=True),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=conversation_id,
            context_name="ctx",
            correlation_id=str(uuid.uuid4()),
        )

        reports = facade.get_events(conversation_id, kind_filter="prompt_report")
        assert len(reports) == 1
        assert reports[0].kind == "prompt_report"
