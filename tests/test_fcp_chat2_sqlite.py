from uuid import uuid4

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.sqlite import SqliteChat2Primitives


@pytest.fixture
def chat2_store(tmp_path):
    primitives = SqliteChat2Primitives(tmp_path / "chat2.sqlite")
    store = Chat2Store(primitives)
    yield store
    primitives.close()


def _session_id() -> str:
    return str(uuid4())


def _saved_agent(**overrides):
    from tests.conftest import FakeAgent

    values = {"name": "lucy", "save_responses": True}
    values.update(overrides)
    return FakeAgent(**values)


class TestChat2SqliteEndToEnd:

    def test_no_tool_call_records_session_and_event(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        sid = _session_id()
        out = proc.process_message(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="lucyproject",
        ).text

        assert out == "hello"
        meta = chat2_store.get_session(sid)
        assert meta is not None
        assert meta.session_id == sid
        assert meta.account_name == "acct1"
        events = list(chat2_store.stream_events(sid))
        assert [e.kind for e in events] == ["prompt_report", "user_message", "assistant_message"]
        assert events[1].payload == "hi"
        assert events[2].payload == "hello"

    def test_context_name_persisted_in_session_meta(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        sid = _session_id()
        proc.process_message(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="lucyproject",
        )

        meta = chat2_store.get_session(sid)
        assert meta is not None
        assert meta.context_name == "lucyproject"
        assert meta.friendly_name == "lucyproject"
        assert meta.account_name == "acct1"
        assert meta.agent_name == "lucy"

    def test_empty_context_name_persisted_as_none(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        sid = _session_id()
        proc.process_message(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="",
        )

        meta = chat2_store.get_session(sid)
        assert meta is not None
        assert meta.context_name is None
        assert meta.friendly_name is None

    def test_existing_session_reused_not_recreated(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        sid = _session_id()
        proc.process_message(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="lucyproject",
        )
        proc.process_message(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="lucyproject",
        )

        sessions = chat2_store.list_sessions(account_name="acct1")
        assert len(sessions) == 1
        assert sessions[0].session_id == sid
        events = list(chat2_store.stream_events(sid))
        assert len(events) == 6

    def test_save_responses_false_skips_chat2_write(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "transient"

        sid = _session_id()
        out = proc.process_message(
            primary_agent=_saved_agent(save_responses=False),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="should_not_be_used",
        ).text

        assert out == "transient"
        assert chat2_store.get_session(sid) is None
        assert chat2_store.list_sessions(account_name="acct1") == []

    def test_streaming_persists_events_on_generator_close(self, make_proc, prompt_builder, llm_adapter, chat2_store):
        proc = make_proc(chat2_store=chat2_store)

        prompt_builder.build_prompt.return_value = [{"role": "user", "content": "hi"}]
        llm_adapter.extract_tool_calls.return_value = []
        llm_adapter.get_text.return_value = "hello"

        sid = _session_id()
        gen = proc.process_message_streaming(
            primary_agent=_saved_agent(),
            account={"accountId": "acct1"},
            message="hi",
            conversation_id=sid,
            context_name="ctx",
        )

        next(gen)
        gen.close()

        meta = chat2_store.get_session(sid)
        assert meta is not None
        events = list(chat2_store.stream_events(sid))
        assert [e.kind for e in events] == ["prompt_report", "user_message", "assistant_message"]
        assert events[1].payload == "hi"
        assert events[2].payload == "hello"
