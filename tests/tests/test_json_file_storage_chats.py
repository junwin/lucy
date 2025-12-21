# tests/test_json_file_storage_chats.py
import os
from datetime import datetime
from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import ChatMessage


def test_create_chat_session_and_list(tmp_path):
    storage = JsonFileStorage(str(tmp_path))

    session = storage.create_chat_session(
        account_name="junwin",
        agent_name="lucy",
        friendly_name="Therapy session",
        tags=["test"],
    )

    assert session.account_name == "junwin"
    assert session.agent_name == "lucy"
    assert session.friendly_name == "Therapy session"
    assert session.tags == ["test"]
    assert session.messages == []

    sessions = storage.list_chat_sessions("junwin")
    assert len(sessions) == 1
    assert sessions[0].id == session.id
    assert sessions[0].friendly_name == "Therapy session"


def test_append_and_load_chat_messages(tmp_path):
    storage = JsonFileStorage(str(tmp_path))

    session = storage.create_chat_session(
        account_name="junwin",
        agent_name="lucy",
    )

    storage.append_chat_message(
        session_id=session.id,
        message=ChatMessage(role="user", content="Hello Lucy"),
    )

    storage.append_chat_message(
        session_id=session.id,
        message=ChatMessage(role="assistant", content="Hello John"),
    )

    loaded = storage.get_chat_session(session.id)
    assert loaded is not None
    assert len(loaded.messages) == 2
    assert loaded.messages[0].role == "user"
    assert loaded.messages[1].content == "Hello John"


def test_update_chat_session_metadata(tmp_path):
    storage = JsonFileStorage(str(tmp_path))

    session = storage.create_chat_session(
        account_name="junwin",
        agent_name="lucy",
        friendly_name="Old name",
    )

    storage.update_chat_session(
        session_id=session.id,
        friendly_name="New name",
        tags=["finance", "legacy"],
        summary="Short summary",
        importance_score=0.8,
        include_in_context=False,
        metadata={"origin": "test"},
    )

    updated = storage.get_chat_session(session.id)
    assert updated is not None
    assert updated.friendly_name == "New name"
    assert updated.tags == ["finance", "legacy"]
    assert updated.summary == "Short summary"
    assert updated.importance_score == 0.8
    assert updated.include_in_context is False
    assert updated.metadata.get("origin") == "test"
