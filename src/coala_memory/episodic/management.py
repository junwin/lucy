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
    friendly_name: Optional[str] = None
    context_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    events: List[EpisodicEvent] = field(default_factory=list)


@dataclass(frozen=True)
class EpisodicCurationRequest:
    """Lifecycle/curation request derived from Chat2 and curate_chat handlers."""

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
    status: str
    session_id: str = ""
    note_text: str = ""
    output_path: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)
    error: str = ""


class EpisodicMemoryManager(ABC):
    """Domain seam for episodic session lifecycle and curation.

    This is intentionally separate from prompt-time ``EpisodicMemory.recall``.
    Existing HTTP endpoints and agent handlers can eventually share an adapter
    implementing this interface without making the CoALA package an HTTP layer.
    """

    @abstractmethod
    def create_session(
        self,
        *,
        account_name: str,
        agent_name: str,
        friendly_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
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
    def append_event(self, session_id: str, event: EpisodicEvent) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_session(self, session_id: str, patch: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def reset_session(self, session_id: str) -> None:
        """Clear events while retaining session metadata."""
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def curate(self, request: EpisodicCurationRequest) -> EpisodicCurationResult:
        """Filter, summarize or archive a session."""
        raise NotImplementedError
