from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .interface import EpisodicEvent


@dataclass(frozen=True)
class EpisodicSessionQuery:
    """Query sessions by account/agent and optional event text."""

    account_name: str
    agent_name: str = ""
    query: str = ""
    limit: int = 20


@dataclass(frozen=True)
class EpisodicSession:
    session_id: str
    account_name: str
    agent_name: str
    user_id: str = ""
    friendly_name: Optional[str] = None
    context_name: Optional[str] = None
    session_type: str = "user"
    participants: List[str] = field(default_factory=list)
    links: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    events: List[EpisodicEvent] = field(default_factory=list)


@dataclass(frozen=True)
class EpisodicCurationRequest:
    """Compatibility DTO for callers migrating to ``CurationEngine``.

    Curation is intentionally not an operation on ``EpisodicMemoryManager``;
    the application-level curation service consumes this manager as a neutral
    session/event store.
    """

    account_name: str
    session_id: str = ""
    friendly_name: str = ""
    mode: str = "filter"  # filter | summarize | archive
    preview: bool = True
    publish: bool = False
    template_name: str = "default"
    curation_rules: Dict[str, Any] = field(default_factory=dict)
    max_chars: int = 32000


@dataclass(frozen=True)
class EpisodicCurationResult:
    """Compatibility DTO for existing handler/API result mappings."""

    status: str
    session_id: str = ""
    note_text: str = ""
    output_path: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class EpisodicMemoryManager(ABC):
    """Provider-neutral episodic session/event store.

    This interface owns persistence and lifecycle primitives only. Higher-level
    workflows such as curation are application services that depend on this
    interface; they are deliberately not methods on the storage abstraction.
    """

    @abstractmethod
    def create_session(
        self,
        *,
        account_name: str,
        agent_name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        context_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_type: str = "user",
        participants: Optional[List[str]] = None,
        links: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EpisodicSession:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str, *, include_events: bool = True) -> Optional[EpisodicSession]:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self, query: EpisodicSessionQuery) -> List[EpisodicSession]:
        raise NotImplementedError

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """Return True if a session with *session_id* exists."""
        raise NotImplementedError

    @abstractmethod
    def append_event(self, session_id: str, event: EpisodicEvent) -> EpisodicEvent:
        raise NotImplementedError

    @abstractmethod
    def add_events(self, session_id: str, events: List[EpisodicEvent]) -> List[EpisodicEvent]:
        """Append multiple events in order, returning the stored events."""
        raise NotImplementedError

    @abstractmethod
    def link_event(self, correlation_id: Optional[str], session_id: str, event_id: str) -> None:
        """Link an event to a correlation id in the sidecar index.

        Falsy correlation ids (None or '') are a no-op and never raise.
        """
        raise NotImplementedError

    @abstractmethod
    def update_session(self, session_id: str, patch: Dict[str, Any]) -> EpisodicSession:
        raise NotImplementedError

    @abstractmethod
    def reset_session(self, session_id: str) -> None:
        """Clear events while retaining session metadata."""
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        raise NotImplementedError
