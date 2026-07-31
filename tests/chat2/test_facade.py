
"""
Tests for the Chat2Store facade.
"""

from datetime import datetime, timezone

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent, ChatSessionMeta, SessionLinks
from src.chat2.store_primitives import InMemoryStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def facade(store: InMemoryStore) -> Chat2Store:
    return Chat2Store(store)


@pytest.fixture
def sample_event() -> ChatEvent:
    return ChatEvent(
        role="user",
        actor="john",
        kind="user_message",
        payload="Hello, Lucy!",
    )


@pytest.fixture
def sample_events() -> list[ChatEvent]:
    return [
        ChatEvent(
            role="user",
            actor="john",
            kind="user_message",
            payload="Hello!",
        ),
        ChatEvent(
            role="assistant",
            actor="lucy",
            kind="assistant_message",
            payload="Hi John!",
        ),
        ChatEvent(
            role="user",
            actor="john",
            kind="user_message",
            payload="How are you?",
        ),
    ]


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Tests for session create/get/update/delete/exists."""

    def test_create_session(self, facade: Chat2Store) -> None:
        """Creating a session returns valid metadata."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            friendly_name="test_session",
        )
        assert isinstance(meta, ChatSessionMeta)
        assert meta.user_id == "user1"
        assert meta.account_name == "test_account"
        assert meta.agent_name == "lucy"
        assert meta.friendly_name == "test_session"
        assert meta.session_type == "user"
        assert meta.participants == []
        assert meta.tags == []
        assert meta.context_name is None

    def test_create_session_with_optional_fields(self, facade: Chat2Store) -> None:
        """Creating a session with all optional fields."""
        links = SessionLinks(internal_session_id="550e8400-e29b-41d4-a716-446655440000")
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            friendly_name="detailed_session",
            context_name="lucyproject",
            tags=["important", "test"],
            session_type="internal",
            participants=["john", "lucy", "colin"],
            links=links,
        )
        assert meta.context_name == "lucyproject"
        assert meta.tags == ["important", "test"]
        assert meta.session_type == "internal"
        assert meta.participants == ["john", "lucy", "colin"]
        assert meta.links is not None
        assert meta.links.internal_session_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_get_session(self, facade: Chat2Store) -> None:
        """Getting an existing session returns its metadata."""
        created = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        retrieved = facade.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.user_id == "user1"

    def test_get_session_not_found(self, facade: Chat2Store) -> None:
        """Getting a non-existent session returns None."""
        result = facade.get_session("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_update_session(self, facade: Chat2Store) -> None:
        """Updating session fields works."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            friendly_name="original",
        )
        updated = facade.update_session(
            meta.session_id,
            friendly_name="renamed",
            tags=["updated"],
        )
        assert updated.friendly_name == "renamed"
        assert updated.tags == ["updated"]
        assert updated.updated_at >= updated.created_at

    def test_update_session_not_found(self, facade: Chat2Store) -> None:
        """Updating a non-existent session raises ValueError."""
        with pytest.raises(ValueError, match="Session not found"):
            facade.update_session(
                "00000000-0000-0000-0000-000000000000",
                friendly_name="nope",
            )

    def test_delete_session(self, facade: Chat2Store) -> None:
        """Deleting a session removes it."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        assert facade.session_exists(meta.session_id)
        facade.delete_session(meta.session_id)
        assert not facade.session_exists(meta.session_id)

    def test_delete_session_nonexistent(self, facade: Chat2Store) -> None:
        """Deleting a non-existent session is a no-op."""
        facade.delete_session("00000000-0000-0000-0000-000000000000")

    def test_session_exists(self, facade: Chat2Store) -> None:
        """session_exists returns correct boolean."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        assert facade.session_exists(meta.session_id)
        assert not facade.session_exists("00000000-0000-0000-0000-000000000000")


# ---------------------------------------------------------------------------
# Event management tests
# ---------------------------------------------------------------------------


class TestEventManagement:
    """Tests for add_event, add_events, stream, get, reset, count."""

    def test_add_event(self, facade: Chat2Store, sample_event: ChatEvent) -> None:
        """Adding a single event works."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        result = facade.add_event(meta.session_id, sample_event)
        assert result.event_id == sample_event.event_id
        assert result.role == "user"
        assert result.actor == "john"

    def test_add_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Adding multiple events works."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        results = facade.add_events(meta.session_id, sample_events)
        assert len(results) == 3
        assert facade.event_count(meta.session_id) == 3

    def test_stream_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Streaming events yields them in order."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        facade.add_events(meta.session_id, sample_events)
        streamed = list(facade.stream_events(meta.session_id))
        assert len(streamed) == 3
        assert streamed[0].payload == "Hello!"
        assert streamed[1].payload == "Hi John!"
        assert streamed[2].payload == "How are you?"

    def test_stream_events_empty(self, facade: Chat2Store) -> None:
        """Streaming events from a session with no events yields nothing."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        streamed = list(facade.stream_events(meta.session_id))
        assert streamed == []

    def test_get_events_with_filters(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Getting events with filters works."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        facade.add_events(meta.session_id, sample_events)

        # Filter by role
        user_events = facade.get_events(meta.session_id, role_filter="user")
        assert len(user_events) == 2
        assert all(e.role == "user" for e in user_events)

        # Filter by actor
        lucy_events = facade.get_events(meta.session_id, actor_filter="lucy")
        assert len(lucy_events) == 1
        assert lucy_events[0].actor == "lucy"

        # Filter by kind
        msg_events = facade.get_events(meta.session_id, kind_filter="user_message")
        assert len(msg_events) == 2

    def test_get_events_no_filters(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Getting events without filters returns all."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        facade.add_events(meta.session_id, sample_events)
        all_events = facade.get_events(meta.session_id)
        assert len(all_events) == 3

    def test_reset_events(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Resetting events clears them but preserves metadata."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        facade.add_events(meta.session_id, sample_events)
        assert facade.event_count(meta.session_id) == 3

        facade.reset_events(meta.session_id)
        assert facade.event_count(meta.session_id) == 0

        # Metadata still exists
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.user_id == "user1"

    def test_reset_events_nonexistent(self, facade: Chat2Store) -> None:
        """Resetting events on a non-existent session raises ValueError."""
        with pytest.raises(ValueError, match="Session not found"):
            facade.reset_events("00000000-0000-0000-0000-000000000000")

    def test_event_count(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """Event count returns correct number."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        assert facade.event_count(meta.session_id) == 0
        facade.add_events(meta.session_id, sample_events)
        assert facade.event_count(meta.session_id) == 3

    def test_event_count_nonexistent(self, facade: Chat2Store) -> None:
        """Event count on non-existent session returns 0."""
        assert facade.event_count("00000000-0000-0000-0000-000000000000") == 0


# ---------------------------------------------------------------------------
# Convenience method tests
# ---------------------------------------------------------------------------


class TestConvenience:
    """Tests for create_and_add convenience method."""

    def test_create_and_add(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """create_and_add creates a session and adds events."""
        meta = facade.create_and_add(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            events=sample_events,
            friendly_name="quick_session",
            context_name="lucyproject",
            tags=["quick"],
        )
        assert meta.friendly_name == "quick_session"
        assert meta.tags == ["quick"]
        assert meta.context_name == "lucyproject"
        assert facade.event_count(meta.session_id) == 3

    def test_create_and_add_empty_events(self, facade: Chat2Store) -> None:
        """create_and_add with no events creates an empty session."""
        meta = facade.create_and_add(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            events=[],
        )
        assert facade.event_count(meta.session_id) == 0
        assert meta.context_name is None

    def test_create_and_add_with_links(self, facade: Chat2Store, sample_events: list[ChatEvent]) -> None:
        """create_and_add with session links."""
        links = SessionLinks(internal_session_id="550e8400-e29b-41d4-a716-446655440000")
        meta = facade.create_and_add(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            events=sample_events,
            links=links,
        )
        assert meta.links is not None
        assert meta.links.internal_session_id == "550e8400-e29b-41d4-a716-446655440000"
        assert facade.event_count(meta.session_id) == 3


# ---------------------------------------------------------------------------
# Context name tests
# ---------------------------------------------------------------------------


class TestContextName:
    """Tests for context_name field in the facade layer."""

    def test_default_is_none(self, facade: Chat2Store) -> None:
        """context_name defaults to None when not provided."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        assert meta.context_name is None

    def test_persisted_and_retrieved(self, facade: Chat2Store) -> None:
        """context_name survives a create → get round-trip."""
        created = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            context_name="lucyproject",
        )
        retrieved = facade.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.context_name == "lucyproject"

    def test_none_persisted_and_retrieved(self, facade: Chat2Store) -> None:
        """context_name=None survives a create → get round-trip."""
        created = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            context_name=None,
        )
        retrieved = facade.get_session(created.session_id)
        assert retrieved is not None
        assert retrieved.context_name is None

    def test_can_be_updated(self, facade: Chat2Store) -> None:
        """context_name can be updated via update_session."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
            context_name="old_project",
        )
        updated = facade.update_session(meta.session_id, context_name="new_project")
        assert updated.context_name == "new_project"

        # Verify persistence
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.context_name == "new_project"


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_add_event_to_nonexistent_session(
        self, facade: Chat2Store, sample_event: ChatEvent
    ) -> None:
        """Adding an event to a non-existent session should not crash
        (the underlying store will create the events file)."""
        # This should not raise — the store is append-only
        facade.add_event("00000000-0000-0000-0000-000000000000", sample_event)

    def test_stream_from_nonexistent_session(self, facade: Chat2Store) -> None:
        """Streaming from a non-existent session yields nothing."""
        events = list(facade.stream_events("00000000-0000-0000-0000-000000000000"))
        assert events == []

    def test_get_events_from_nonexistent_session(self, facade: Chat2Store) -> None:
        """Getting events from a non-existent session returns empty list."""
        events = facade.get_events("00000000-0000-0000-0000-000000000000")
        assert events == []

    def test_multiple_sessions_independent(
        self, facade: Chat2Store, sample_event: ChatEvent
    ) -> None:
        """Events in different sessions are independent."""
        meta1 = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        meta2 = facade.create_session(
            user_id="user2",
            account_name="test_account",
            agent_name="colin",
        )

        facade.add_event(meta1.session_id, sample_event)
        assert facade.event_count(meta1.session_id) == 1
        assert facade.event_count(meta2.session_id) == 0

    def test_session_updated_at_updates_on_event(
        self, facade: Chat2Store, sample_event: ChatEvent
    ) -> None:
        """Adding an event updates the session's updated_at timestamp."""
        meta = facade.create_session(
            user_id="user1",
            account_name="test_account",
            agent_name="lucy",
        )
        original_updated = meta.updated_at

        facade.add_event(meta.session_id, sample_event)
        retrieved = facade.get_session(meta.session_id)
        assert retrieved is not None
        assert retrieved.updated_at >= original_updated
