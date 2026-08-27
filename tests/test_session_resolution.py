"""
Tests for resolve_or_create_session (Phase 1 /ask -> chat2 migration).
"""

import re
import time
from unittest.mock import Mock

import pytest

from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore
from src.message_endpoints.ask_request_handler import resolve_or_create_session

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@pytest.fixture
def chat2() -> Chat2Store:
    return Chat2Store(InMemoryStore())


def _seed(
    chat2: Chat2Store,
    session_id: str,
    account_name: str,
    agent_name: str,
    friendly_name: str,
) -> None:
    chat2.create_session(
        user_id=account_name,
        account_name=account_name,
        agent_name=agent_name,
        session_id=session_id,
        friendly_name=friendly_name,
    )


class TestResolveOrCreateSession:
    def test_reuses_existing_session_by_friendly_name(self, chat2) -> None:
        _seed(chat2, "11111111-1111-4111-8111-111111111111", "alice", "lucy", "My Project Notes")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "project")
        assert session_id == "11111111-1111-4111-8111-111111111111"

    def test_match_is_case_insensitive(self, chat2) -> None:
        _seed(chat2, "22222222-2222-4222-8222-222222222222", "alice", "lucy", "My Project Notes")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "PROJECT")
        assert session_id == "22222222-2222-4222-8222-222222222222"

    def test_match_ignores_leading_trailing_whitespace(self, chat2) -> None:
        _seed(chat2, "33333333-3333-4333-8333-333333333333", "alice", "lucy", "My Project Notes")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "  project  ")
        assert session_id == "33333333-3333-4333-8333-333333333333"

    def test_creates_new_session_when_no_match(self, chat2) -> None:
        _seed(chat2, "44444444-4444-4444-8444-444444444444", "alice", "lucy", "Other Topic")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "project")
        assert UUID_RE.match(session_id)
        meta = chat2.get_session(session_id)
        assert meta is not None
        assert meta.friendly_name == "project"
        assert meta.account_name == "alice"
        assert meta.agent_name == "lucy"

    def test_creates_session_with_default_name_when_no_friendly_name(self, chat2) -> None:
        session_id = resolve_or_create_session(chat2, "alice", "lucy", None)
        assert UUID_RE.match(session_id)
        meta = chat2.get_session(session_id)
        assert meta is not None
        assert meta.friendly_name == f"Chat {session_id[:8]}"

    def test_creates_session_with_default_name_for_empty_friendly_name(self, chat2) -> None:
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "")
        meta = chat2.get_session(session_id)
        assert meta is not None
        assert meta.friendly_name == f"Chat {session_id[:8]}"

    def test_filters_by_account_and_agent(self, chat2) -> None:
        _seed(chat2, "55555555-5555-4555-8555-555555555555", "alice", "lucy", "project")
        _seed(chat2, "66666666-6666-4666-8666-666666666666", "alice", "other-agent", "project")
        _seed(chat2, "77777777-7777-4777-8777-777777777777", "bob", "lucy", "project")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "project")
        assert session_id == "55555555-5555-4555-8555-555555555555"

    def test_returns_most_recent_match(self, chat2) -> None:
        _seed(chat2, "88888888-8888-4888-8888-888888888888", "alice", "lucy", "project")
        time.sleep(0.01)
        _seed(chat2, "99999999-9999-4999-8999-999999999999", "alice", "lucy", "project")
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "project")
        assert session_id == "99999999-9999-4999-8999-999999999999"

    def test_passes_explicit_limit_to_list_sessions(self, chat2, monkeypatch) -> None:
        mock_list = Mock(return_value=[])
        monkeypatch.setattr(chat2, "list_sessions", mock_list)
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "project", limit=500)
        mock_list.assert_called_once_with(
            account_name="alice",
            agent_name="lucy",
            limit=500,
        )
        assert UUID_RE.match(session_id)

    def test_custom_limit_is_respected(self, chat2, monkeypatch) -> None:
        mock_list = Mock(return_value=[])
        monkeypatch.setattr(chat2, "list_sessions", mock_list)
        resolve_or_create_session(chat2, "alice", "lucy", "project", limit=123)
        mock_list.assert_called_once_with(
            account_name="alice",
            agent_name="lucy",
            limit=123,
        )

    def test_returns_uuid_when_chat2_store_is_none(self) -> None:
        session_id = resolve_or_create_session(None, "alice", "lucy", "project")
        assert UUID_RE.match(session_id)

    def test_no_match_when_stored_friendly_name_is_none(self, chat2) -> None:
        _seed(chat2, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "alice", "lucy", "Some Name")
        chat2.update_session("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", friendly_name=None)
        session_id = resolve_or_create_session(chat2, "alice", "lucy", "some")
        assert UUID_RE.match(session_id)
        assert session_id != "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
