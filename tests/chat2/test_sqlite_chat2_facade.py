from pathlib import Path
from uuid import uuid4

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent, ChatSessionMeta
from src.chat2.sqlite import SqliteChat2Primitives


@pytest.fixture
def facade(tmp_path: Path) -> Chat2Store:
    primitives = SqliteChat2Primitives(tmp_path / "chat2.sqlite")
    store = Chat2Store(primitives)
    yield store
    primitives.close()


def _session_id() -> str:
    return str(uuid4())


def _user_event(payload: str | dict = "hello") -> ChatEvent:
    return ChatEvent(role="user", actor="junwin", kind="user_message", payload=payload)


def _assistant_event(payload: str | dict = "hi there") -> ChatEvent:
    return ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload=payload)


def _tool_event(payload: str | dict) -> ChatEvent:
    return ChatEvent(role="tool", actor="search", kind="tool_result", payload=payload)


def _create(facade: Chat2Store, **kwargs) -> ChatSessionMeta:
    values = {
        "user_id": "user1",
        "account_name": "junwin",
        "agent_name": "lucy",
        "session_id": _session_id(),
    }
    values.update(kwargs)
    return facade.create_session(**values)


class TestSessionRoundTrip:
    def test_create_session_then_get_session(self, facade: Chat2Store) -> None:
        meta = _create(facade, friendly_name="friendly", tags=["one"])
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.session_id == meta.session_id
        assert retrieved.user_id == "user1"
        assert retrieved.account_name == "junwin"
        assert retrieved.agent_name == "lucy"
        assert retrieved.friendly_name == "friendly"
        assert retrieved.tags == ["one"]

    def test_get_session_missing_returns_none(self, facade: Chat2Store) -> None:
        assert facade.get_session(_session_id()) is None


class TestEventRoundTrip:
    def test_add_event_then_stream_events(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        event = _user_event("hello sqlite")
        facade.add_event(meta.session_id, event)
        streamed = list(facade.stream_events(meta.session_id))
        assert len(streamed) == 1
        assert streamed[0].event_id == event.event_id
        assert streamed[0].role == "user"
        assert streamed[0].actor == "junwin"
        assert streamed[0].kind == "user_message"
        assert streamed[0].payload == "hello sqlite"

    def test_add_events_then_get_events_round_trip(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        events = [
            _user_event("first"),
            _assistant_event("second"),
            _tool_event({"query": "lucy", "n": 2}),
        ]
        facade.add_events(meta.session_id, events)
        got = facade.get_events(meta.session_id)
        assert [e.event_id for e in got] == [e.event_id for e in events]
        assert [e.role for e in got] == ["user", "assistant", "tool"]
        assert [e.payload for e in got] == ["first", "second", {"query": "lucy", "n": 2}]
        assert got[1].actor == "lucy"

    def test_get_events_role_filter(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        facade.add_events(meta.session_id, [_user_event("a"), _assistant_event("b")])
        user_events = facade.get_events(meta.session_id, role_filter="user")
        assert [e.payload for e in user_events] == ["a"]

    def test_stream_and_get_events_match(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        facade.add_events(meta.session_id, [_user_event("a"), _assistant_event("b")])
        streamed = list(facade.stream_events(meta.session_id))
        got = facade.get_events(meta.session_id)
        assert [e.payload for e in streamed] == [e.payload for e in got] == ["a", "b"]


class TestListSessions:
    def test_list_sessions_account_filter(self, facade: Chat2Store) -> None:
        s1 = _create(facade, account_name="junwin")
        s2 = _create(facade, account_name="junwin")
        _create(facade, account_name="other")
        ids = {s.session_id for s in facade.list_sessions(account_name="junwin")}
        assert ids == {s1.session_id, s2.session_id}

    def test_list_sessions_agent_filter(self, facade: Chat2Store) -> None:
        s1 = _create(facade, agent_name="lucy")
        _create(facade, agent_name="colin")
        s3 = _create(facade, agent_name="lucy")
        ids = {s.session_id for s in facade.list_sessions(agent_name="lucy")}
        assert ids == {s1.session_id, s3.session_id}

    def test_list_sessions_account_and_agent(self, facade: Chat2Store) -> None:
        s1 = _create(facade, account_name="junwin", agent_name="lucy")
        _create(facade, account_name="junwin", agent_name="colin")
        _create(facade, account_name="other", agent_name="lucy")
        sessions = facade.list_sessions(account_name="junwin", agent_name="lucy")
        assert [s.session_id for s in sessions] == [s1.session_id]

    def test_list_sessions_returns_all(self, facade: Chat2Store) -> None:
        s1 = _create(facade)
        s2 = _create(facade)
        ids = {s.session_id for s in facade.list_sessions()}
        assert ids == {s1.session_id, s2.session_id}


class TestUpdateSession:
    def test_update_session_fields_and_updated_at_bump(self, facade: Chat2Store) -> None:
        meta = _create(facade, friendly_name="before", tags=["a"])
        updated = facade.update_session(
            meta.session_id,
            friendly_name="after",
            tags=["a", "b"],
        )
        assert updated.friendly_name == "after"
        assert updated.tags == ["a", "b"]
        assert updated.updated_at >= meta.created_at
        assert updated.updated_at >= meta.updated_at
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.friendly_name == "after"
        assert retrieved.tags == ["a", "b"]
        assert retrieved.updated_at >= meta.updated_at

    def test_update_session_missing_raises(self, facade: Chat2Store) -> None:
        with pytest.raises(ValueError, match="Session not found"):
            facade.update_session(_session_id(), friendly_name="nope")


class TestCorrelation:
    def test_link_event_and_get_events_by_correlation(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        events = [_user_event("one"), _assistant_event("two"), _user_event("three")]
        facade.add_events(meta.session_id, events)
        facade.link_event("req-1", meta.session_id, events[1].event_id)
        facade.link_event("req-1", meta.session_id, events[2].event_id)
        linked = facade.get_events_by_correlation("req-1")
        assert [e.event_id for e in linked] == [events[1].event_id, events[2].event_id]
        assert [e.payload for e in linked] == ["two", "three"]
        assert facade.get_events_by_correlation("req-unknown") == []

    def test_link_event_across_sessions(self, facade: Chat2Store) -> None:
        meta1 = _create(facade)
        meta2 = _create(facade)
        e1 = _user_event("from-one")
        e2 = _assistant_event("from-two")
        facade.add_event(meta1.session_id, e1)
        facade.add_event(meta2.session_id, e2)
        facade.link_event("req-2", meta1.session_id, e1.event_id)
        facade.link_event("req-2", meta2.session_id, e2.event_id)
        linked = facade.get_events_by_correlation("req-2")
        assert [e.payload for e in linked] == ["from-one", "from-two"]

    def test_link_event_none_is_noop(self, facade: Chat2Store) -> None:
        facade.link_event(None, _session_id(), _session_id())
        assert facade.get_events_by_correlation(None) == []


class TestResetEvents:
    def test_reset_events_preserves_meta_and_empties_events(self, facade: Chat2Store) -> None:
        meta = _create(facade, friendly_name="keep-me")
        facade.add_events(meta.session_id, [_user_event("a"), _assistant_event("b")])
        assert facade.event_count(meta.session_id) == 2
        facade.reset_events(meta.session_id)
        assert facade.event_count(meta.session_id) == 0
        assert list(facade.stream_events(meta.session_id)) == []
        assert facade.get_events(meta.session_id) == []
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.user_id == "user1"
        assert retrieved.friendly_name == "keep-me"
        facade.add_event(meta.session_id, _user_event("after-reset"))
        assert [e.payload for e in facade.stream_events(meta.session_id)] == ["after-reset"]


class TestDeleteSession:
    def test_delete_session_removes_session_and_events(self, facade: Chat2Store) -> None:
        meta = _create(facade)
        facade.add_event(meta.session_id, _user_event("gone"))
        facade.delete_session(meta.session_id)
        assert not facade.session_exists(meta.session_id)
        assert facade.get_session(meta.session_id) is None
        assert list(facade.stream_events(meta.session_id)) == []
        assert facade.get_events(meta.session_id) == []
        assert all(s.session_id != meta.session_id for s in facade.list_sessions())

    def test_session_exists_false_after_delete(self, facade: Chat2Store) -> None:
        assert not facade.session_exists(_session_id())
        meta = _create(facade)
        assert facade.session_exists(meta.session_id)
        facade.delete_session(meta.session_id)
        assert not facade.session_exists(meta.session_id)
