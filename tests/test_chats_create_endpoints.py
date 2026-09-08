"""Tests for creating chats and posting messages using the Episodic manager (in-memory).

These tests follow the shared style contract used by the existing chats endpoint
tests. They intentionally exercise the new payload key `contextName` and expect
round-tripping via the Chat2EpisodicMemory adapter.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore
from src.http_endpoints.chats_endpoints import post_chat_impl, post_chat_message_impl, get_chat_impl
from src.coala_memory.episodic import Chat2EpisodicMemory


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def mgr(store: InMemoryStore) -> Chat2EpisodicMemory:
    return Chat2EpisodicMemory(Chat2Store(store))


@pytest.fixture
def agent_manager() -> Mock:
    mgr = Mock()
    mgr.is_valid.return_value = True
    return mgr


@pytest.fixture
def agent_manager_strict() -> Mock:
    mgr = Mock()

    def _is_valid(name: str) -> bool:
        return name == "lucy"

    mgr.is_valid.side_effect = _is_valid
    return mgr


class TestPostChat:
    def test_create_session_minimal(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        body, status = post_chat_impl(
            mgr,
            agent_manager,
            {"agentName": "lucy", "accountName": "junwin"},
        )
        assert status == 200
        assert body.get("id") is not None
        assert body["account_name"] == "junwin"
        assert body["agent_name"] == "lucy"
        assert body["user_id"] == "junwin"
        assert body["session_type"] == "user"

    def test_create_session_with_context(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        body, status = post_chat_impl(
            mgr,
            agent_manager,
            {"agentName": "lucy", "accountName": "junwin", "contextName": "lucyproject"},
        )
        assert status == 200
        assert body.get("id") is not None
        assert body["context_name"] == "lucyproject"

        session = mgr.get_session(body["id"])  # type: ignore[arg-type]
        assert session is not None
        assert session.context_name == "lucyproject"

    def test_invalid_agent(self, mgr: Chat2EpisodicMemory, agent_manager_strict: Mock) -> None:
        body, status = post_chat_impl(
            mgr,
            agent_manager_strict,
            {"agentName": "colin", "accountName": "junwin"},
        )
        assert status == 400
        assert "error" in body


class TestPostMessage:
    def test_post_message_and_get(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created, _ = post_chat_impl(mgr, agent_manager, {"agentName": "lucy", "accountName": "junwin"})
        session_id = created["id"]

        res, status = post_chat_message_impl(mgr, session_id, {"role": "user", "content": "Hello"})
        assert status == 200
        assert res == {"status": "ok"}

        body, status = get_chat_impl(mgr, session_id)
        assert status == 200
        assert len(body["messages"]) == 1
        msg = body["messages"][0]
        assert msg["role"] == "user"
        assert msg["content"] == "Hello"
        assert "utc_timestamp" in msg

    def test_message_to_unknown_session(self, mgr: Chat2EpisodicMemory) -> None:
        body, status = post_chat_message_impl(mgr, "00000000-0000-0000-0000-000000000000", {"role": "user", "content": "x"})
        assert status == 404
        assert "error" in body
