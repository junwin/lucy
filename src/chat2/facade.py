"""
Facade for Chat v2 storage operations.

Provides a Chat2Store class that wraps Chat2Primitives into higher-level
operations, combining session creation, event appending, and querying
into a single convenient interface.

This is purely for developer ergonomics — all underlying functions remain
available for direct use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, List, Optional

from src.chat2.correlation import get_links, link_event
from src.chat2.jsonl_store import (
    append_event,
    create_session,
    delete_session,
    get_session_meta,
    list_sessions,
    read_events,
    reset_session_events,
    stream_events,
    update_session_meta,
)
from src.chat2.models import ChatEvent, ChatSessionMeta, SessionLinks
from src.chat2.store_primitives import Chat2Primitives


class Chat2Store:
    """High-level facade for chat2 storage operations.

    Wraps a Chat2Primitives backend and exposes session lifecycle
    and event management as a single object.

    Args:
        store: A Chat2Primitives implementation (e.g. FileChat2Primitives,
            JfsChat2Primitives, or InMemoryStore).
    """

    def __init__(self, store: Chat2Primitives) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(
        self,
        user_id: str,
        account_name: str,
        agent_name: str,
        *,
        session_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        context_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_type: str = "user",
        participants: Optional[List[str]] = None,
        links: Optional[SessionLinks] = None,
    ) -> ChatSessionMeta:
        """Create a new chat session.

        If *session_id* is provided, use it instead of generating a new UUID.
        This allows callers to keep session IDs consistent across storage layers.

        Returns the created session metadata.
        """
        return create_session(
            self._store,
            user_id=user_id,
            account_name=account_name,
            agent_name=agent_name,
            session_id=session_id,
            friendly_name=friendly_name,
            context_name=context_name,
            tags=tags,
            session_type=session_type,
            participants=participants,
            links=links,
        )

    def get_session(self, session_id: str) -> Optional[ChatSessionMeta]:
        """Retrieve session metadata by ID.

        Returns None if the session does not exist.
        """
        return get_session_meta(self._store, session_id)

    def update_session(
        self,
        session_id: str,
        **patch_fields,
    ) -> ChatSessionMeta:
        """Update session metadata fields.

        Raises ValueError if the session does not exist.
        """
        return update_session_meta(self._store, session_id, **patch_fields)

    def delete_session(self, session_id: str) -> None:
        """Delete a session and all its events.

        No-op if the session does not exist.
        """
        delete_session(self._store, session_id)

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        return get_session_meta(self._store, session_id) is not None

    def list_sessions(
        self,
        *,
        account_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[ChatSessionMeta]:
        """List sessions, optionally filtered.

        Results are sorted by updated_at descending (most recent first)
        and capped at *limit*.
        """
        return list_sessions(
            self._store,
            account_name=account_name,
            agent_name=agent_name,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Event management
    # ------------------------------------------------------------------

    def add_event(
        self,
        session_id: str,
        event: ChatEvent,
    ) -> ChatEvent:
        """Append an event to a session's event log.

        Returns the event (with its generated event_id).
        """
        return append_event(self._store, session_id, event)

    def add_events(
        self,
        session_id: str,
        events: List[ChatEvent],
    ) -> List[ChatEvent]:
        """Append multiple events to a session's event log.

        Returns the list of events.
        """
        for event in events:
            append_event(self._store, session_id, event)
        return events

    def stream_events(
        self,
        session_id: str,
    ) -> Iterator[ChatEvent]:
        """Yield events from a session in file order."""
        return stream_events(self._store, session_id)

    def get_events(
        self,
        session_id: str,
        *,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        role_filter: Optional[str] = None,
        actor_filter: Optional[str] = None,
        kind_filter: Optional[str] = None,
    ) -> List[ChatEvent]:
        """Get events with optional filters."""
        return read_events(
            self._store,
            session_id,
            start_ts=start_ts,
            end_ts=end_ts,
            role_filter=role_filter,
            actor_filter=actor_filter,
            kind_filter=kind_filter,
        )

    def reset_events(self, session_id: str) -> None:
        """Clear all events from a session, preserving metadata.

        Raises ValueError if the session does not exist.
        """
        reset_session_events(self._store, session_id)

    def event_count(self, session_id: int) -> int:
        """Return the number of events in a session.

        Returns 0 if the session does not exist.
        """
        return len(list(stream_events(self._store, session_id)))

    # ------------------------------------------------------------------
    # Correlation index
    # ------------------------------------------------------------------

    def link_event(
        self,
        correlation_id: Optional[str],
        session_id: str,
        event_id: str,
    ) -> None:
        """Link an event to a correlation id in the sidecar index.

        Falsy correlation ids (None or '') are a no-op and never raise.
        """
        link_event(self._store, correlation_id, session_id, event_id)

    def get_events_by_correlation(
        self,
        correlation_id: Optional[str],
    ) -> List[ChatEvent]:
        """Return events linked to a correlation id, in link order.

        Resolves links via the sidecar index, reads each linked session's
        events through the facade's own get_events, and returns the linked
        events in link order. Returns [] when the correlation id is unknown.
        """
        links = get_links(self._store, correlation_id)
        if not links:
            return []
        events_by_id: dict[str, ChatEvent] = {}
        for session_id in {link.session_id for link in links}:
            for event in self.get_events(session_id):
                events_by_id[event.event_id] = event
        return [
            events_by_id[link.event_id]
            for link in links
            if link.event_id in events_by_id
        ]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def create_and_add(
        self,
        user_id: str,
        account_name: str,
        agent_name: str,
        events: List[ChatEvent],
        *,
        session_id: Optional[str] = None,
        friendly_name: Optional[str] = None,
        context_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        session_type: str = "user",
        participants: Optional[List[str]] = None,
        links: Optional[SessionLinks] = None,
    ) -> ChatSessionMeta:
        """Create a session and add events in one call.

        Returns the created session metadata.
        """
        meta = self.create_session(
            user_id=user_id,
            account_name=account_name,
            agent_name=agent_name,
            session_id=session_id,
            friendly_name=friendly_name,
            context_name=context_name,
            tags=tags,
            session_type=session_type,
            participants=participants,
            links=links,
        )
        self.add_events(meta.session_id, events)
        return meta


__all__ = ["Chat2Store"]
