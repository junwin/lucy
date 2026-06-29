"""Integration tests for chats_endpoints.py implementation functions.

Tests every endpoint impl against a real Chat2Store backed by InMemoryStore,
with a mock AgentManager.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.store_primitives import InMemoryStore
from src.http_endpoints.chats_endpoints import (
    delete_chat_impl,
    get_chat_impl,
    get_chats_impl,
    post_chat_impl,
    post_chat_message_impl,
    update_chat_impl,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryStore:
    """In-memory store shared across tests."""
    return InMemoryStore()


@pytest.fixture
def chat2_store(store: InMemoryStore) -> Chat2Store:
    """Chat2Store wrapping the in-memory store."""
    return Chat2Store(store)


@pytest.fixture
def agent_manager() -> Mock:
    """Mock AgentManager that says all agent names are valid."""
    mgr = Mock()
    mgr.is_valid.return_value = True
    return mgr


@pytest.fixture
def agent_manager_strict() -> Mock:
    """Mock AgentManager that only allows 'lucy'."""
    mgr = Mock()

    def _is_valid(name: str) -> bool:
        return name == "lucy"

    mgr.is_valid.side_effect = _is_valid
    return mgr


# ---------------------------------------------------------------------------
# POST /chats  (create session)
# ---------------------------------------------------------------------------


class TestPostChat:
    """Tests for post_chat_impl."""

    def test_create_session_minimal(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Creating a session with minimal required fields returns 200."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        assert status == 200
        assert body.get("id") is not None
        assert body["account_name"] == "junwin"
        assert body["agent_name"] == "lucy"
        assert body["friendly_name"] is None
        assert body["tags"] == []
        assert body["messages"] == []
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_session_with_all_fields(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Creating a session with friendlyName and tags returns 200."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager,
            {
                "agentName": "lucy",
                "accountName": "junwin",
                "friendlyName": "My chat",
                "tags": ["test", "important"],
            },
        )
        assert status == 200
        assert body["friendly_name"] == "My chat"
        assert body["tags"] == ["test", "important"]

    def test_create_session_uppercase_agent(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Agent name is lowercased before validation and storage."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager,
            {"agentName": "LUCY", "accountName": "junwin"},
        )
        assert status == 200
        assert body["agent_name"] == "lucy"

    def test_missing_agent_name(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Missing agentName returns 400."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager,
            {"accountName": "junwin"},
        )
        assert status == 400
        assert "error" in body

    def test_missing_account_name(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Missing accountName returns 400."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager,
            {"agentName": "lucy"},
        )
        assert status == 400
        assert "error" in body

    def test_empty_payload(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Empty payload returns 400."""
        body, status = post_chat_impl(chat2_store, agent_manager, {})
        assert status == 400

    def test_invalid_agent_name(self, chat2_store: Chat2Store, agent_manager_strict: Mock) -> None:
        """Invalid agentName returns 400."""
        body, status = post_chat_impl(
            chat2_store,
            agent_manager_strict,
            {"agentName": "colin", "accountName": "junwin"},
        )
        assert status == 400
        assert "error" in body


# ---------------------------------------------------------------------------
# GET /chats  (list sessions)
# ---------------------------------------------------------------------------


class TestGetChats:
    """Tests for get_chats_impl."""

    def test_list_empty(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Listing sessions when none exist returns empty list."""
        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="", account_name="junwin", limit=50
        )
        assert status == 200
        assert body == []

    def test_list_sessions_for_account(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """List all sessions for an account."""
        # Create a few sessions
        post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin", "friendlyName": "Chat A"})
        post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin", "friendlyName": "Chat B"})
        post_chat_impl(chat2_store, agent_manager, {"agentName": "colin", "accountName": "junwin", "friendlyName": "Chat C"})

        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="", account_name="junwin", limit=50
        )
        assert status == 200
        assert len(body) == 3

    def test_list_filter_by_agent(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Filter sessions by agent_name."""
        post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin", "friendlyName": "L1"})
        post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin", "friendlyName": "L2"})
        post_chat_impl(chat2_store, agent_manager, {"agentName": "glinda", "accountName": "junwin", "friendlyName": "G1"})

        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="lucy", account_name="junwin", limit=50
        )
        assert status == 200
        assert len(body) == 2
        assert all(s["agent_name"] == "lucy" for s in body)

    def test_list_with_limit(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """List respects the limit parameter."""
        for i in range(5):
            post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin", "friendlyName": f"Chat {i}"})

        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="", account_name="junwin", limit=3
        )
        assert status == 200
        assert len(body) == 3

    def test_list_missing_account(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Missing accountName returns 400."""
        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="lucy", account_name="", limit=50
        )
        assert status == 400

    def test_list_invalid_agent(self, chat2_store: Chat2Store, agent_manager_strict: Mock) -> None:
        """Invalid agentName returns 400."""
        body, status = get_chats_impl(
            chat2_store, agent_manager_strict, agent_name="colin", account_name="junwin", limit=50
        )
        assert status == 400

    def test_list_messages_field_empty(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """List response does NOT include messages (messages: [] placeholder)."""
        post_chat_impl(chat2_store, agent_manager, {"agentName": "lucy", "accountName": "junwin"})
        body, status = get_chats_impl(
            chat2_store, agent_manager, agent_name="", account_name="junwin", limit=50
        )
        assert status == 200
        assert len(body) == 1
        assert body[0]["messages"] == []


# ---------------------------------------------------------------------------
# GET /chats/<id>  (get single session)
# ---------------------------------------------------------------------------


class TestGetChat:
    """Tests for get_chat_impl."""

    def test_get_existing_session(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Get a session that exists, including its events."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin", "friendlyName": "Test"},
        )
        session_id = created["id"]

        # Add some events
        chat2_store.add_event(session_id, ChatEvent(role="user", actor="john", kind="user_message", payload="Hello"))
        chat2_store.add_event(session_id, ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hi!"))

        body, status = get_chat_impl(chat2_store, session_id)
        assert status == 200
        assert body["id"] == session_id
        assert body["friendly_name"] == "Test"
        assert len(body["messages"]) == 2
        assert body["messages"][0]["role"] == "user"
        assert body["messages"][1]["role"] == "assistant"

    def test_get_session_no_events(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Get a session that has no events."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        body, status = get_chat_impl(chat2_store, created["id"])
        assert status == 200
        assert body["messages"] == []

    def test_get_nonexistent_session(self, chat2_store: Chat2Store) -> None:
        """Non-existent session returns 404."""
        body, status = get_chat_impl(chat2_store, "00000000-0000-0000-0000-000000000000")
        assert status == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# POST /chats/<id>/messages  (add message)
# ---------------------------------------------------------------------------


class TestPostChatMessage:
    """Tests for post_chat_message_impl."""

    def test_add_user_message(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Add a user message to an existing session."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        session_id = created["id"]

        body, status = post_chat_message_impl(
            chat2_store,
            session_id,
            {"role": "user", "content": "Hello Lucy"},
        )
        assert status == 200
        assert body == {"status": "ok"}

        # Verify it was stored
        events = list(chat2_store.stream_events(session_id))
        assert len(events) == 1
        assert events[0].role == "user"
        assert events[0].payload == "Hello Lucy"

    def test_add_assistant_message(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Add an assistant message."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        session_id = created["id"]

        body, status = post_chat_message_impl(
            chat2_store,
            session_id,
            {"role": "assistant", "content": "How can I help?"},
        )
        assert status == 200

        events = list(chat2_store.stream_events(session_id))
        assert len(events) == 1
        assert events[0].kind == "assistant_message"

    def test_add_message_with_metadata(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Add a message with metadata attached."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        session_id = created["id"]

        body, status = post_chat_message_impl(
            chat2_store,
            session_id,
            {"role": "user", "content": "test", "metadata": {"source": "web"}},
        )
        assert status == 200

        events = list(chat2_store.stream_events(session_id))
        assert events[0].metadata == {"source": "web"}

    def test_add_message_missing_role(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Missing role returns 400."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        body, status = post_chat_message_impl(
            chat2_store, created["id"], {"content": "test"}
        )
        assert status == 400
        assert "error" in body

    def test_add_message_missing_content(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Missing content returns 400 (content=None is not the same as missing)."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        body, status = post_chat_message_impl(
            chat2_store, created["id"], {"role": "user"}
        )
        assert status == 400
        assert "error" in body

    def test_add_message_nonexistent_session(self, chat2_store: Chat2Store) -> None:
        """Adding a message to a non-existent session returns 404."""
        body, status = post_chat_message_impl(
            chat2_store,
            "00000000-0000-0000-0000-000000000000",
            {"role": "user", "content": "test"},
        )
        assert status == 404


# ---------------------------------------------------------------------------
# DELETE /chats/<id>  (delete session)
# ---------------------------------------------------------------------------


class TestDeleteChat:
    """Tests for delete_chat_impl."""

    def test_delete_existing_session(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Delete an existing session returns 200 and removes it."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        session_id = created["id"]

        body, status = delete_chat_impl(chat2_store, session_id)
        assert status == 200
        assert body == {"ok": True}

        # Verify it's gone
        assert chat2_store.get_session(session_id) is None

    def test_delete_nonexistent_session(self, chat2_store: Chat2Store) -> None:
        """Deleting a non-existent session returns 404."""
        body, status = delete_chat_impl(
            chat2_store, "00000000-0000-0000-0000-000000000000"
        )
        assert status == 404
        assert "error" in body


# ---------------------------------------------------------------------------
# PATCH /chats/<id>  (update session)
# ---------------------------------------------------------------------------


class TestUpdateChat:
    """Tests for update_chat_impl."""

    def test_update_friendly_name(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Update the friendly_name of a session."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin", "friendlyName": "Old name"},
        )
        session_id = created["id"]

        body, status = update_chat_impl(
            chat2_store, session_id, {"friendlyName": "New name"}
        )
        assert status == 200
        assert body == {"ok": True}

        # Verify the change persisted
        meta = chat2_store.get_session(session_id)
        assert meta is not None
        assert meta.friendly_name == "New name"

    def test_update_tags(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Update tags on a session."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin", "tags": ["old"]},
        )
        session_id = created["id"]

        body, status = update_chat_impl(
            chat2_store, session_id, {"tags": ["new", "important"]}
        )
        assert status == 200

        meta = chat2_store.get_session(session_id)
        assert meta is not None
        assert meta.tags == ["new", "important"]

    def test_update_metadata(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Update metadata on a session."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        session_id = created["id"]

        body, status = update_chat_impl(
            chat2_store, session_id, {"metadata": {"key": "value"}}
        )
        assert status == 200

        meta = chat2_store.get_session(session_id)
        assert meta is not None
        assert meta.metadata == {"key": "value"}

    def test_update_nonexistent_session(self, chat2_store: Chat2Store) -> None:
        """Updating a non-existent session returns 404."""
        body, status = update_chat_impl(
            chat2_store,
            "00000000-0000-0000-0000-000000000000",
            {"friendlyName": "nope"},
        )
        assert status == 404

    def test_update_empty_payload(self, chat2_store: Chat2Store, agent_manager: Mock) -> None:
        """Empty patch payload returns 200 ok (no changes)."""
        created, _ = post_chat_impl(
            chat2_store, agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        body, status = update_chat_impl(chat2_store, created["id"], {})
        assert status == 200
        assert body == {"ok": True}
