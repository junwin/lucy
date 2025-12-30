"""
Module for defining data models used in the storage layer, including chat messages, user profiles, agent profiles, and context states.

This module contains the following data classes:

- ChatMessage: Represents a single message in a chat.
- ChatSession: Represents a complete chat session with all its messages.
- UserProfile: Represents a user account profile and preferences.
- AgentProfile: Represents agent configuration and behavior settings.
- ContextState: Represents shared state for a conversation.
- DocumentRef: Represents a reference to a document.
- EmbeddingRecord: Represents a vector embedding with metadata.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---- Chats / Completions ----

@dataclass
class ChatMessage:
    """A single message in a chat."""
    role: str                     # "user", "assistant", "system", etc.
    content: str
    utc_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure timestamp is set."""
        if self.utc_timestamp is None:
            self.utc_timestamp = datetime.now(timezone.utc)


@dataclass
class ChatSession:
    """A complete chat session with all its messages."""
    id: str                       # internal guid
    account_name: str             # e.g. "junwin"
    agent_name: str               # e.g. "lucy", "glinda"
    friendly_name: Optional[str]  # "Glinda – retirement chat #1"
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessage] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # New, future-friendly fields
    summary: Optional[str] = None         # optional short summary
    importance_score: float = 0.5         # for ranking / pruning / RAG
    include_in_context: bool = True       # whether this chat is eligible for prompts
    metadata: Dict[str, Any] = field(default_factory=dict)
    # e.g. {"origin": "legacy_migration", "conversation_id": "20230606"}


# ---- User / Agent state ----

@dataclass
class UserProfile:
    """User account profile and preferences."""
    account_name: str
    full_name: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass
class AgentProfile:
    """Agent configuration and behavior settings."""
    name: str
    model: str
    temperature: float
    message_processor: str
    config: Dict[str, Any] = field(default_factory=dict)


# ---- Contexts ("whiteboards") ----

@dataclass
class ContextState:
    """Shared state/whiteboard for a conversation."""
    id: str
    account_name: str
    data: Dict[str, Any]
    updated_at: datetime

    def __post_init__(self):
        """Ensure timestamp is set."""
        if self.updated_at is None:
            self.updated_at = datetime.now(timezone.utc)


# ---- Documents (Obsidian, static text, etc.) ----

@dataclass
class DocumentRef:
    """Reference to a document (metadata only, not content)."""
    id: str
    account_name: str
    path: str
    kind: str
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---- Embeddings ----

@dataclass
class EmbeddingRecord:
    """A vector embedding with metadata."""
    id: str
    namespace: str
    account_name: str
    vector: List[float]
    source_type: str
    source_id: str
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
