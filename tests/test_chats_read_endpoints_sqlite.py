"""Tests that exercise GET /chats and GET /chats/<id> using the
Chat2EpisodicMemory manager seam backed by SQLite primitives.

Expected to FAIL until HTTP endpoints accept Episodic manager semantics.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.coala_memory.episodic import Chat2EpisodicMemory, EpisodicEvent
from src.chat2.facade import Chat2Store
from src.chat2.sqlite import SqliteChat2Primitives
from src.http_endpoints.chats_endpoints import get_chat_impl, get_chats_impl


@pytest.fixture
def db_path(tmp_path) -> str:
    p = tmp_path / "test_chat2.db"
    return str(p)


@pytest.fixture
def mgr(db_path: str) -> Chat2EpisodicMemory:
    primitives = SqliteChat2Primitives(db_path)
    chat2 = Chat2Store(primitives)
    mgr = Chat2EpisodicMemory(chat2)
    return mgr


@pytest.fixture
def agent_manager() -> Mock:
    m = Mock()
    m.is_valid.return_value = True
    return m


@pytest.fixture
def agent_manager_strict() -> Mock:
    m = Mock()

    def _is_valid(name: str) -> bool:
        return name == "lucy"

    m.is_valid.side_effect = _is_valid
    return m


class TestGetChatsSQL:
    def test_list_and_filters(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created = mgr.create_session(
            account_name="junwin",
            agent_name="lucy",
            friendly_name="hello",
            context_name="lucyproject",
        )
        session_id = created.session_id

        evt = EpisodicEvent(role="user", content="Hi there")
        mgr.append_event(session_id, evt)

        body, status = get_chats_impl(mgr, agent_manager, agent_name="", account_name="junwin", limit=50)
        assert status == 200
        assert isinstance(body, list)
        assert body[0]["context_name"] == "lucyproject"
        assert body[0]["user_id"] == "junwin"
        assert body[0]["session_type"] == "user"
        assert body[0]["messages"] == []

    def test_agent_filter(self, mgr: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        mgr.create_session(account_name="junwin", agent_name="lucy", friendly_name="a", context_name="lucyproject")
        mgr.create_session(account_name="junwin", agent_name="glinda", friendly_name="b", context_name="lucyproject")

        body, status = get_chats_impl(mgr, agent_manager, agent_name="lucy", account_name="junwin", limit=50)
        assert status == 200
        assert all(s["agent_name"] == "lucy" for s in body)


class TestGetChatSQL:
    def test_get_existing(self, mgr: Chat2EpisodicMemory) -> None:
        created = mgr.create_session(
            account_name="junwin",
            agent_name="lucy",
            friendly_name="hello",
            context_name="lucyproject",
        )
        session_id = created.session_id
        evt = EpisodicEvent(role="user", content="Hello", actor="john")
        mgr.append_event(session_id, evt)

        body, status = get_chat_impl(mgr, session_id)
        assert status == 200
        assert body["friendly_name"] == "hello"
        assert body["context_name"] == "lucyproject"
        assert len(body["messages"]) == 1
        m = body["messages"][0]
        assert m["role"] == "user"
        assert m["kind"]
        assert m["content"]
        assert m["utc_timestamp"]
        assert m["metadata"]
        assert m.get("event_id")
        assert m.get("actor")

    def test_get_unknown(self, mgr: Chat2EpisodicMemory) -> None:
        body, status = get_chat_impl(mgr, "00000000-0000-0000-0000-000000000000")
        assert status == 404


