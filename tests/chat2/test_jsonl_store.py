"""
Tests for JSONL store functions (src/chat2/jsonl_store.py).

Uses InMemoryStore from test_primitives.py as the backing store.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.chat2.jsonl_store import (
    append_event,
    create_session,
    delete_session,
    get_session_meta,
    read_events,
    reset_session_events,
    stream_events,
    update_session_meta,
)
from src.chat2.models import ChatEvent, SessionLinks
from src.chat2.store_primitives import Chat2Primitives, StoreKey
from tests.chat2.test_primitives import InMemoryStore


@pytest.fixture
def store() -> Chat2Primitives:
    return InMemoryStore()


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

class TestCreateSession:
    def test_creates_meta_and_events(self, store: Chat2Primitives) -> None:
        meta = create_session(
            store,
            user_id="user-1",
            account_name="acme",
            agent_name="lucy",
            friendly_name="2025.04.01_test",
        )
        assert meta.session_id is not None
        assert meta.user_id == "user-1"
        assert meta.account_name == "acme"
        assert meta.agent_name == "lucy"
        assert meta.friendly_name == "2025.04.01_test"
        assert meta.session_type == "user"
        assert meta.created_at == meta.updated_at

        # Verify files exist in store
        meta_key = StoreKey(f"sessions/{meta.session_id}/meta.json")
        events_key = StoreKey(f"sessions/{meta.session_id}/events.jsonl")
        assert store.exists(meta_key)
        assert store.exists(events_key)

    def test_creates_with_optional_fields(self, store: Chat2Primitives) -> None:
        links = SessionLinks(internal_session_id="00000000-0000-0000-0000-000000000001")
        meta = create_session(
            store,
            user_id="user-2",
            account_name="acme",
            agent_name="colin",
            friendly_name="multi-agent-test",
            tags=["test", "demo"],
            session_type="internal",
            participants=["john", "lucy", "colin"],
            links=links,
        )
        assert meta.tags == ["test", "demo"]
        assert meta.session_type == "internal"
        assert meta.participants == ["john", "lucy", "colin"]
        assert meta.links is not None
        assert meta.links.internal_session_id == "00000000-0000-0000-0000-000000000001"

    def test_default_participants_is_empty(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        assert meta.participants == []

    def test_default_tags_is_empty(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        assert meta.tags == []


# ---------------------------------------------------------------------------
# get_session_meta
# ---------------------------------------------------------------------------

class TestGetSessionMeta:
    def test_returns_meta(self, store: Chat2Primitives) -> None:
        created = create_session(store, user_id="u1", account_name="a", agent_name="b")
        fetched = get_session_meta(store, created.session_id)
        assert fetched is not None
        assert fetched.session_id == created.session_id
        assert fetched.user_id == "u1"
        assert fetched.friendly_name == created.friendly_name

    def test_returns_none_for_missing(self, store: Chat2Primitives) -> None:
        assert get_session_meta(store, "nonexistent-session-id") is None


# ---------------------------------------------------------------------------
# update_session_meta
# ---------------------------------------------------------------------------

class TestUpdateSessionMeta:
    def test_updates_fields(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        updated = update_session_meta(
            store,
            meta.session_id,
            friendly_name="renamed",
            tags=["updated"],
        )
        assert updated.friendly_name == "renamed"
        assert updated.tags == ["updated"]
        assert updated.updated_at > meta.updated_at

    def test_raises_for_missing_session(self, store: Chat2Primitives) -> None:
        with pytest.raises(ValueError, match="Session not found"):
            update_session_meta(store, "no-such-session", friendly_name="x")


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

class TestDeleteSession:
    def test_deletes_meta_and_events(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id
        assert get_session_meta(store, sid) is not None
        delete_session(store, sid)
        assert get_session_meta(store, sid) is None

    def test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None:
        delete_session(store, "no-such-session")  # should not raise


# ---------------------------------------------------------------------------
# append_event + stream_events
# ---------------------------------------------------------------------------

class TestAppendAndStreamEvents:
    def test_append_and_stream(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id

        event1 = ChatEvent(role="user", actor="john", kind="user_message", payload="Hello")
        event2 = ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hi there")

        append_event(store, sid, event1)
        append_event(store, sid, event2)

        events = list(stream_events(store, sid))
        assert len(events) == 2
        assert events[0].payload == "Hello"
        assert events[1].payload == "Hi there"

    def test_stream_empty_session(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        events = list(stream_events(store, meta.session_id))
        assert events == []

    def test_stream_nonexistent_session(self, store: Chat2Primitives) -> None:
        events = list(stream_events(store, "no-such-session"))
        assert events == []

    def test_append_updates_meta_timestamp(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id
        original_updated = meta.updated_at

        event = ChatEvent(role="user", actor="john", kind="user_message", payload="Hi")
        append_event(store, sid, event)

        fetched = get_session_meta(store, sid)
        assert fetched is not None
        assert fetched.updated_at > original_updated


# ---------------------------------------------------------------------------
# read_events (filtered)
# ---------------------------------------------------------------------------

class TestReadEvents:
    @pytest.fixture
    def session_with_events(self, store: Chat2Primitives) -> str:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id

        # Create events with controlled timestamps
        base_ts = datetime(2025, 4, 1, 12, 0, 0)
        events = [
            ChatEvent(
                event_id="10000000-0000-0000-0000-000000000001",
                ts=base_ts,
                role="user",
                actor="john",
                kind="user_message",
                payload="Hello",
            ),
            ChatEvent(
                event_id="10000000-0000-0000-0000-000000000002",
                ts=base_ts + timedelta(seconds=10),
                role="assistant",
                actor="lucy",
                kind="assistant_message",
                payload="Hi!",
            ),
            ChatEvent(
                event_id="10000000-0000-0000-0000-000000000003",
                ts=base_ts + timedelta(seconds=20),
                role="tool",
                actor="search_web",
                kind="tool_result",
                payload='{"results": []}',
            ),
            ChatEvent(
                event_id="10000000-0000-0000-0000-000000000004",
                ts=base_ts + timedelta(seconds=30),
                role="assistant",
                actor="colin",
                kind="assistant_message",
                payload="Done",
            ),
        ]
        for ev in events:
            append_event(store, sid, ev)
        return sid

    def test_no_filters(self, store: Chat2Primitives, session_with_events: str) -> None:
        events = read_events(store, session_with_events)
        assert len(events) == 4

    def test_role_filter(self, store: Chat2Primitives, session_with_events: str) -> None:
        events = read_events(store, session_with_events, role_filter="assistant")
        assert len(events) == 2
        assert all(e.role == "assistant" for e in events)

    def test_actor_filter(self, store: Chat2Primitives, session_with_events: str) -> None:
        events = read_events(store, session_with_events, actor_filter="colin")
        assert len(events) == 1
        assert events[0].actor == "colin"

    def test_kind_filter(self, store: Chat2Primitives, session_with_events: str) -> None:
        events = read_events(store, session_with_events, kind_filter="tool_result")
        assert len(events) == 1
        assert events[0].kind == "tool_result"

    def test_start_ts_filter(self, store: Chat2Primitives, session_with_events: str) -> None:
        cutoff = datetime(2025, 4, 1, 12, 0, 15)
        events = read_events(store, session_with_events, start_ts=cutoff)
        assert len(events) == 2  # events 3 and 4

    def test_end_ts_filter(self, store: Chat2Primitives, session_with_events: str) -> None:
        cutoff = datetime(2025, 4, 1, 12, 0, 15)
        events = read_events(store, session_with_events, end_ts=cutoff)
        assert len(events) == 2  # events 1 and 2

    def test_combined_filters(self, store: Chat2Primitives, session_with_events: str) -> None:
        cutoff = datetime(2025, 4, 1, 12, 0, 5)
        events = read_events(
            store,
            session_with_events,
            start_ts=cutoff,
            role_filter="assistant",
        )
        assert len(events) == 2  # events 2 and 4


# ---------------------------------------------------------------------------
# reset_session_events
# ---------------------------------------------------------------------------

class TestResetSessionEvents:
    def test_reset_clears_events(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id

        append_event(store, sid, ChatEvent(role="user", actor="john", kind="user_message", payload="Hi"))
        append_event(store, sid, ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hello"))

        assert len(list(stream_events(store, sid))) == 2

        reset_session_events(store, sid)
        assert len(list(stream_events(store, sid))) == 0

    def test_reset_preserves_meta(self, store: Chat2Primitives) -> None:
        meta = create_session(store, user_id="u1", account_name="a", agent_name="b", friendly_name="keep-me")
        sid = meta.session_id

        append_event(store, sid, ChatEvent(role="user", actor="john", kind="user_message", payload="Hi"))
        reset_session_events(store, sid)

        fetched = get_session_meta(store, sid)
        assert fetched is not None
        assert fetched.friendly_name == "keep-me"
        assert fetched.updated_at > meta.updated_at

    def test_reset_nonexistent_session_raises(self, store: Chat2Primitives) -> None:
        with pytest.raises(ValueError, match="Session not found"):
            reset_session_events(store, "no-such-session")
