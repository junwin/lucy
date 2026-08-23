# src/storage/__init__.py
"""
Lucy's storage layer.

Provides a unified interface for storing and retrieving:
- Chat sessions and messages
- Contexts (shared state)
- Documents and embeddings

Usage:
    from src.storage import JsonFileStorage, ChatMessage, ChatSession
    
    storage = JsonFileStorage(base_path="/data/lucy")
    session = storage.create_chat_session("junwin", "lucy", "My chat")
    
    msg = ChatMessage(role="user", content="Hello!")
    storage.append_chat_message(session.id, msg)
"""

# Base interface
from .base import Storage

# Implementations
from .json_file_storage import JsonFileStorage

# Data models
from .models import (
    ChatMessage,
    ChatSession,
    Context,
    Skill,
    DocumentRef,
    EmbeddingRecord,
)


__all__ = [
    "Storage",
    "JsonFileStorage",
    "ChatMessage",
    "ChatSession",
    "Context",
    "Skill",
    "DocumentRef",
    "EmbeddingRecord",
]
