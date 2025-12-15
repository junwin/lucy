# ==============================================================================
# FILE 2: tests/storage/test_storage_chats.py
# ==============================================================================

import pytest
from datetime import datetime
from src.storage.models import ChatMessage, ChatSession


class TestChatOperations:
    """Test chat session CRUD operations."""
    
    def test_create_chat_session(self, storage):
        """Test creating a new chat session."""
        session = storage.create_chat_session(
            account_name="junwin",
            agent_name="lucy",
            friendly_name="Test conversation",
            tags=["test", "therapy"],
        )
        
        assert session.id is not None
        assert session.account_name == "junwin"
        assert session.agent_name == "lucy"
        assert session.friendly_name == "Test conversation"
        assert "test" in session.tags
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)
        assert len(session.messages) == 0
    
    def test_get_chat_session(self, storage):
        """Test retrieving a chat session by ID."""
        created = storage.create_chat_session(
            account_name="junwin",
            agent_name="lucy",
            friendly_name="Retrieve test",
        )
        
        retrieved = storage.get_chat_session(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.account_name == "junwin"
        assert retrieved.friendly_name == "Retrieve test"
    
    def test_get_nonexistent_session(self, storage):
        """Test retrieving a session that doesn't exist."""
        result = storage.get_chat_session("nonexistent-id-12345")
        assert result is None
    
    def test_append_chat_message(self, storage):
        """Test adding messages to a chat session."""
        session = storage.create_chat_session(
            account_name="junwin",
            agent_name="lucy",
        )
        
        msg1 = ChatMessage(
            role="user",
            content="Hello Lucy",
            utc_timestamp=datetime.utcnow(),
        )
        storage.append_chat_message(session.id, msg1)
        
        msg2 = ChatMessage(
            role="assistant",
            content="Hello! How can I help?",
            utc_timestamp=datetime.utcnow(),
        )
        storage.append_chat_message(session.id, msg2)
        
        retrieved = storage.get_chat_session(session.id)
        assert len(retrieved.messages) == 2
        assert retrieved.messages[0].role == "user"
        assert retrieved.messages[0].content == "Hello Lucy"
        assert retrieved.messages[1].role == "assistant"
        assert retrieved.messages[1].content == "Hello! How can I help?"
    
    def test_list_chat_sessions(self, storage):
        """Test listing chat sessions for an account."""
        storage.create_chat_session("junwin", "lucy", "Chat 1")
        storage.create_chat_session("junwin", "lucy", "Chat 2")
        storage.create_chat_session("junwin", "glinda", "Chat 3")
        storage.create_chat_session("alice", "lucy", "Alice's chat")
        
        sessions = storage.list_chat_sessions("junwin", limit=50)
        assert len(sessions) == 3
        
        lucy_sessions = storage.list_chat_sessions(
            "junwin", 
            agent_name="lucy", 
            limit=50
        )
        assert len(lucy_sessions) == 2
        
        alice_sessions = storage.list_chat_sessions("alice", limit=50)
        assert len(alice_sessions) == 1
    
    def test_list_chat_sessions_with_limit(self, storage):
        """Test pagination limit on chat listing."""
        for i in range(10):
            storage.create_chat_session("junwin", "lucy", f"Chat {i}")
        
        sessions = storage.list_chat_sessions("junwin", limit=5)
        assert len(sessions) == 5
    
    def test_rename_chat_session(self, storage):
        """Test renaming a chat session."""
        session = storage.create_chat_session(
            "junwin", 
            "lucy", 
            "Original name"
        )
        
        storage.rename_chat_session(session.id, "New name")
        
        retrieved = storage.get_chat_session(session.id)
        assert retrieved.friendly_name == "New name"
    
    def test_message_ordering(self, storage):
        """Test that messages maintain their order."""
        session = storage.create_chat_session("junwin", "lucy")
        
        for i in range(5):
            msg = ChatMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
                utc_timestamp=datetime.utcnow(),
            )
            storage.append_chat_message(session.id, msg)
        
        retrieved = storage.get_chat_session(session.id)
        for i, msg in enumerate(retrieved.messages):
            assert msg.content == f"Message {i}"
    
    def test_append_message_to_nonexistent_session(self, storage):
        """Test appending message to non-existent session."""
        msg = ChatMessage(role="user", content="test")
        
        with pytest.raises(Exception):
            storage.append_chat_message("nonexistent-session", msg)
    
    def test_unicode_content(self, storage):
        """Test storing unicode and emoji content."""
        session = storage.create_chat_session("junwin", "lucy")
        
        msg = ChatMessage(
            role="user",
            content="Hello 世界 🌍 café naïve",
            utc_timestamp=datetime.utcnow(),
        )
        
        storage.append_chat_message(session.id, msg)
        
        retrieved = storage.get_chat_session(session.id)
        assert retrieved.messages[0].content == "Hello 世界 🌍 café naïve"

