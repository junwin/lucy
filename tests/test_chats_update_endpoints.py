from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.coala_memory.episodic.chat2_memory import Chat2EpisodicMemory
from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore
from src.http_endpoints.chats_endpoints import (
    delete_chat_impl,
    get_chat_impl,
    update_chat_impl,
)


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def chat2_store(store: InMemoryStore) -> Chat2Store:
    return Chat2Store(store)


@pytest.fixture
def manager(chat2_store: Chat2Store) -> Chat2EpisodicMemory:
    return Chat2EpisodicMemory(chat2_store)


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


class TestUpdateChat:
    def test_update_friendly_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created = manager.create_session(account_name="junwin", agent_name="lucy", friendly_name="Old name")
        session_id = created.session_id

        body, status = update_chat_impl(manager, session_id, {"friendlyName": "New name"})
        assert status == 200
        assert body == {"ok": True}

        meta, status = get_chat_impl(manager, session_id)
        assert status == 200
        assert meta["friendly_name"] == "New name"

    def test_update_tags_and_metadata(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created = manager.create_session(account_name="junwin", agent_name="lucy", tags=["old"])
        session_id = created.session_id

        body, status = update_chat_impl(manager, session_id, {"tags": ["new", "important"], "metadata": {"key": "value"}})
        assert status == 200
        assert body == {"ok": True}

        meta, status = get_chat_impl(manager, session_id)
        assert status == 200
        assert meta["tags"] == ["new", "important"]
        assert meta["metadata"] == {"key": "value"}

    def test_update_context_name(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created = manager.create_session(account_name="junwin", agent_name="lucy")
        session_id = created.session_id

        body, status = update_chat_impl(manager, session_id, {"contextName": "foo"})
        assert status == 200
        assert body == {"ok": True}

        meta, status = get_chat_impl(manager, session_id)
        assert status == 200
        assert meta.get("context_name") == "foo"

    def test_update_nonexistent_session(self, manager: Chat2EpisodicMemory) -> None:
        body, status = update_chat_impl(manager, "00000000-0000-0000-0000-000000000000", {"friendlyName": "nope"})
        assert status == 404

    def test_delete_session(self, manager: Chat2EpisodicMemory, agent_manager: Mock) -> None:
        created = manager.create_session(account_name="junwin", agent_name="lucy")
        session_id = created.session_id

        body, status = delete_chat_impl(manager, session_id)
        assert status == 200
        assert body == {"ok": True}

        meta, status = get_chat_impl(manager, session_id)
        assert status == 404
