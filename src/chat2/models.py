"""Pydantic models for Chat v2 storage system.

Defines the core domain models for chat events and sessions.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class SessionLinks(BaseModel):
    """Links between different types of sessions."""
    
    user_session_id: Optional[str] = None
    internal_session_id: Optional[str] = None
    
    @field_validator('user_session_id', 'internal_session_id')
    @classmethod
    def validate_uuid(cls, v: Optional[str]) -> Optional[str]:
        """Validate UUID format if provided."""
        if v is None:
            return v
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")


class ChatEvent(BaseModel):
    """A single chat event in a conversation."""
    
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=datetime.utcnow)
    role: Literal["user", "assistant", "tool", "system"]
    actor: str
    kind: Literal["user_message", "assistant_message", "assistant_tool_call", 
                  "tool_result", "system_note", "summary", "generated_image"]
    payload: dict | str
    metadata: dict = Field(default_factory=dict)
    
    @field_validator('event_id')
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        """Validate event_id is a valid UUID."""
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format for event_id: {v}")
    
    @field_validator('ts')
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure datetime is timezone-naive (assumed UTC)."""
        if v.tzinfo is not None:
            # Convert to UTC and make timezone-naive
            v = v.astimezone(tz=None).replace(tzinfo=None)
        return v
    
    @field_validator('payload')
    @classmethod
    def validate_payload(cls, v: dict | str) -> dict | str:
        """Ensure payload is either dict or string."""
        if not isinstance(v, (dict, str)):
            raise ValueError(f"Payload must be dict or str, got {type(v)}")
        return v
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON with datetime as ISO string."""
        return super().model_dump_json(**kwargs)
    
    @classmethod
    def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatEvent':
        """Parse JSON string into ChatEvent."""
        return super().model_validate_json(json_data, **kwargs)


class ChatSessionMeta(BaseModel):
    """Metadata for a chat session."""
    
    session_id: str
    user_id: str
    account_name: str
    agent_name: str
    participants: list[str] = Field(default_factory=list)
    session_type: Literal["user", "internal"] = "user"
    friendly_name: Optional[str] = None
    context_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: list[str] = Field(default_factory=list)
    links: Optional[SessionLinks] = None
    metadata: dict = Field(default_factory=dict)
    
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """Validate session_id is a valid UUID."""
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format for session_id: {v}")
    
    @field_validator('created_at', 'updated_at')
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Ensure datetime is timezone-naive (assumed UTC)."""
        if v.tzinfo is not None:
            # Convert to UTC and make timezone-naive
            v = v.astimezone(tz=None).replace(tzinfo=None)
        return v
    
    @field_validator('updated_at')
    @classmethod
    def updated_at_not_before_created_at(cls, v: datetime, info) -> datetime:
        """Ensure updated_at is not before created_at."""
        if 'created_at' in info.data and v < info.data['created_at']:
            raise ValueError("updated_at cannot be before created_at")
        return v
    
    def model_dump_json(self, **kwargs) -> str:
        """Serialize to JSON with datetime as ISO string."""
        return super().model_dump_json(**kwargs)
    
    @classmethod
    def model_validate_json(cls, json_data: str, **kwargs) -> 'ChatSessionMeta':
        """Parse JSON string into ChatSessionMeta."""
        return super().model_validate_json(json_data, **kwargs)


__all__ = ['ChatEvent', 'ChatSessionMeta', 'SessionLinks']
