"""
Tests for Chat v2 Pydantic models.
"""

import json
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.chat2.models import ChatEvent, ChatSessionMeta, SessionLinks


def test_session_links():
    """Test SessionLinks model."""
    # Test with valid UUIDs
    links = SessionLinks(
        user_session_id=str(uuid4()),
        internal_session_id=str(uuid4())
    )
    assert links.user_session_id is not None
    assert links.internal_session_id is not None
    
    # Test with None values
    links = SessionLinks()
    assert links.user_session_id is None
    assert links.internal_session_id is None
    
    # Test invalid UUID
    with pytest.raises(ValidationError):
        SessionLinks(user_session_id="not-a-uuid")


def test_chat_event_basic():
    """Test basic ChatEvent creation."""
    event = ChatEvent(
        role="user",
        actor="john",
        kind="user_message",
        payload="Hello, world!"
    )
    
    assert event.role == "user"
    assert event.actor == "john"
    assert event.kind == "user_message"
    assert event.payload == "Hello, world!"
    assert isinstance(event.event_id, str)
    assert isinstance(event.ts, datetime)
    assert event.metadata == {}


def test_chat_event_with_dict_payload():
    """Test ChatEvent with dictionary payload."""
    event = ChatEvent(
        role="assistant",
        actor="lucy",
        kind="assistant_tool_call",
        payload={"tool": "file_load", "parameters": {"path": "test.txt"}}
    )
    
    assert event.role == "assistant"
    assert event.payload == {"tool": "file_load", "parameters": {"path": "test.txt"}}


def test_chat_event_validation():
    """Test ChatEvent validation."""
    # Test invalid role
    with pytest.raises(ValidationError):
        ChatEvent(
            role="invalid_role",
            actor="john",
            kind="user_message",
            payload="test"
        )
    
    # Test invalid kind
    with pytest.raises(ValidationError):
        ChatEvent(
            role="user",
            actor="john",
            kind="invalid_kind",
            payload="test"
        )
    
    # Test invalid payload type
    with pytest.raises(ValidationError):
        ChatEvent(
            role="user",
            actor="john",
            kind="user_message",
            payload=123  # Not dict or str
        )
    
    # Test invalid event_id
    with pytest.raises(ValidationError):
        ChatEvent(
            event_id="not-a-uuid",
            role="user",
            actor="john",
            kind="user_message",
            payload="test"
        )


def test_chat_event_json_serialization():
    """Test ChatEvent JSON serialization and deserialization."""
    event = ChatEvent(
        role="tool",
        actor="file_save",
        kind="tool_result",
        payload={"result": "success"},
        metadata={"duration_ms": 150}
    )
    
    # Serialize to JSON
    json_str = event.model_dump_json()
    data = json.loads(json_str)
    
    assert data["role"] == "tool"
    assert data["actor"] == "file_save"
    assert data["kind"] == "tool_result"
    assert data["payload"] == {"result": "success"}
    assert data["metadata"] == {"duration_ms": 150}
    assert "event_id" in data
    assert "ts" in data
    
    # Deserialize from JSON
    event2 = ChatEvent.model_validate_json(json_str)
    assert event2.role == event.role
    assert event2.actor == event.actor
    assert event2.kind == event.kind
    assert event2.payload == event.payload
    assert event2.metadata == event.metadata


def test_chat_session_meta_basic():
    """Test basic ChatSessionMeta creation."""
    now = datetime.utcnow()
    session_id = str(uuid4())
    
    meta = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        created_at=now,
        updated_at=now
    )
    
    assert meta.session_id == session_id
    assert meta.user_id == "user123"
    assert meta.account_name == "john"
    assert meta.agent_name == "lucy"
    assert meta.session_type == "user"
    assert meta.participants == []
    assert meta.tags == []
    assert meta.metadata == {}
    assert meta.friendly_name is None
    assert meta.context_name is None
    assert meta.links is None


def test_chat_session_meta_with_optional_fields():
    """Test ChatSessionMeta with all optional fields."""
    now = datetime.utcnow()
    session_id = str(uuid4())
    
    meta = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        participants=["john", "lucy", "colin"],
        session_type="internal",
        friendly_name="Test Session",
        context_name="lucyproject",
        created_at=now,
        updated_at=now,
        tags=["test", "debug"],
        links=SessionLinks(user_session_id=str(uuid4())),
        metadata={"priority": "high"}
    )
    
    assert meta.session_type == "internal"
    assert meta.participants == ["john", "lucy", "colin"]
    assert meta.friendly_name == "Test Session"
    assert meta.context_name == "lucyproject"
    assert meta.tags == ["test", "debug"]
    assert meta.metadata == {"priority": "high"}
    assert meta.links is not None
    assert meta.links.user_session_id is not None


def test_chat_session_meta_validation():
    """Test ChatSessionMeta validation."""
    now = datetime.utcnow()
    
    # Test invalid session_id
    with pytest.raises(ValidationError):
        ChatSessionMeta(
            session_id="not-a-uuid",
            user_id="user123",
            account_name="john",
            agent_name="lucy",
            created_at=now,
            updated_at=now
        )
    
    # Test updated_at before created_at
    with pytest.raises(ValidationError):
        ChatSessionMeta(
            session_id=str(uuid4()),
            user_id="user123",
            account_name="john",
            agent_name="lucy",
            created_at=now,
            updated_at=datetime(2020, 1, 1)  # Before created_at
        )
    
    # Test invalid session_type
    with pytest.raises(ValidationError):
        ChatSessionMeta(
            session_id=str(uuid4()),
            user_id="user123",
            account_name="john",
            agent_name="lucy",
            session_type="invalid_type",
            created_at=now,
            updated_at=now
        )


def test_chat_session_meta_json_serialization():
    """Test ChatSessionMeta JSON serialization and deserialization."""
    now = datetime.utcnow()
    session_id = str(uuid4())
    
    meta = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        participants=["john", "lucy"],
        context_name="lucyproject",
        created_at=now,
        updated_at=now,
        tags=["test"],
        metadata={"note": "test session"}
    )
    
    # Serialize to JSON
    json_str = meta.model_dump_json()
    data = json.loads(json_str)
    
    assert data["session_id"] == session_id
    assert data["user_id"] == "user123"
    assert data["account_name"] == "john"
    assert data["agent_name"] == "lucy"
    assert data["participants"] == ["john", "lucy"]
    assert data["context_name"] == "lucyproject"
    assert data["tags"] == ["test"]
    assert data["metadata"] == {"note": "test session"}
    assert data["session_type"] == "user"
    assert "created_at" in data
    assert "updated_at" in data
    
    # Deserialize from JSON
    meta2 = ChatSessionMeta.model_validate_json(json_str)
    assert meta2.session_id == meta.session_id
    assert meta2.user_id == meta.user_id
    assert meta2.account_name == meta.account_name
    assert meta2.agent_name == meta.agent_name
    assert meta2.context_name == meta.context_name
    assert meta2.participants == meta.participants
    assert meta2.tags == meta.tags
    assert meta2.metadata == meta.metadata


def test_default_values():
    """Test that default values are properly set."""
    # ChatEvent defaults
    event = ChatEvent(
        role="user",
        actor="john",
        kind="user_message",
        payload="test"
    )
    assert event.metadata == {}
    assert isinstance(event.event_id, str)
    assert isinstance(event.ts, datetime)
    
    # ChatSessionMeta defaults
    now = datetime.utcnow()
    meta = ChatSessionMeta(
        session_id=str(uuid4()),
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        created_at=now,
        updated_at=now
    )
    assert meta.participants == []
    assert meta.tags == []
    assert meta.metadata == {}
    assert meta.session_type == "user"
    assert meta.friendly_name is None
    assert meta.context_name is None
    assert meta.links is None


def test_context_name_roundtrip():
    """Test context_name round-trips through dict and JSON serialization, including None default."""
    now = datetime.utcnow()
    session_id = str(uuid4())

    # --- None default ---
    meta = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        created_at=now,
        updated_at=now,
    )
    assert meta.context_name is None

    # Dict round-trip with None (model_dump + model_validate)
    dumped = meta.model_dump()
    assert dumped["context_name"] is None
    meta2 = ChatSessionMeta.model_validate(dumped)
    assert meta2.context_name is None

    # JSON round-trip with None
    json_str = meta.model_dump_json()
    data = json.loads(json_str)
    assert data["context_name"] is None
    meta3 = ChatSessionMeta.model_validate_json(json_str)
    assert meta3.context_name is None

    # --- Explicit string ---
    meta4 = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        context_name="lucyproject",
        created_at=now,
        updated_at=now,
    )
    assert meta4.context_name == "lucyproject"

    # Dict round-trip with value
    dumped4 = meta4.model_dump()
    assert dumped4["context_name"] == "lucyproject"
    meta5 = ChatSessionMeta.model_validate(dumped4)
    assert meta5.context_name == "lucyproject"

    # JSON round-trip with value
    json_str4 = meta4.model_dump_json()
    data4 = json.loads(json_str4)
    assert data4["context_name"] == "lucyproject"
    meta6 = ChatSessionMeta.model_validate_json(json_str4)
    assert meta6.context_name == "lucyproject"

    # --- Explicit None (explicitly set to None) ---
    meta7 = ChatSessionMeta(
        session_id=session_id,
        user_id="user123",
        account_name="john",
        agent_name="lucy",
        context_name=None,
        created_at=now,
        updated_at=now,
    )
    assert meta7.context_name is None

    dumped7 = meta7.model_dump()
    assert dumped7["context_name"] is None
    meta8 = ChatSessionMeta.model_validate(dumped7)
    assert meta8.context_name is None
