"""
JSONL store functions for Chat v2.

All functions accept a store: Chat2Primitives (media-neutral) and operate
on logical StoreKey paths. No filesystem paths are used directly.

Key layout:
  sessions/<session_id>/meta.json   — session metadata (ChatSessionMeta)
  sessions/<session_id>/events.jsonl — append-only event log (JSONL)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterator, List, Optional
from uuid import uuid4

from src.chat2.models import ChatEvent, ChatSessionMeta, SessionLinks
from src.chat2.store_primitives import Chat2Primitives, StoreKey


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def _meta_key(session_id: str) -> StoreKey:
    return StoreKey(f"sessions/{session_id}/meta.json")


def _events_key(session_id: str) -> StoreKey:
    return StoreKey(f"sessions/{session_id}/events.jsonl")


def _sessions_prefix() -> StoreKey:
    return StoreKey("sessions/")


# ---------------------------------------------------------------------------
# Session meta operations
# ---------------------------------------------------------------------------

def create_session(
    store: Chat2Primitives,
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
    """Create a new session and write its metadata.

    If *session_id* is provided, use it instead of generating a new UUID.
    This allows callers to keep session IDs consistent across storage layers.

    Returns the created ChatSessionMeta.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sid = session_id or str(uuid4())

    meta = ChatSessionMeta(
        session_id=sid,
        user_id=user_id,
        account_name=account_name,
        agent_name=agent_name,
        participants=participants or [],
        session_type=session_type,  # type: ignore[arg-type]
        friendly_name=friendly_name,
        context_name=context_name,
        created_at=now,
        updated_at=now,
        tags=tags or [],
        links=links,
        metadata={},
    )

    store.write_text(_meta_key(sid), meta.model_dump_json())
    # Create empty events file so the session exists
    store.write_text(_events_key(sid), "")

    return meta


def get_session_meta(
    store: Chat2Primitives,
    session_id: str,
) -> Optional[ChatSessionMeta]:
    """Read session metadata, or None if the session does not exist."""
    raw = store.read_text(_meta_key(session_id))
    if raw is None:
        return None
    return ChatSessionMeta.model_validate_json(raw)


def update_session_meta(
    store: Chat2Primitives,
    session_id: str,
    **patch_fields,
) -> ChatSessionMeta:
    """Update session metadata fields and rewrite meta.json.

    Raises ValueError if the session does not exist.
    """
    meta = get_session_meta(store, session_id)
    if meta is None:
        raise ValueError(f"Session not found: {session_id}")

    # Apply patch fields (skip None values unless explicitly set)
    for field, value in patch_fields.items():
        if hasattr(meta, field):
            setattr(meta, field, value)

    meta.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    store.write_text(_meta_key(session_id), meta.model_dump_json())
    return meta


def delete_session(store: Chat2Primitives, session_id: str) -> None:
    """Delete session metadata and events.

    No-op if the session does not exist.
    """
    store.delete(_meta_key(session_id))
    store.delete(_events_key(session_id))


def list_sessions(
    store: Chat2Primitives,
    *,
    account_name: Optional[str] = None,
    agent_name: Optional[str] = None,
    limit: int = 50,
) -> List[ChatSessionMeta]:
    """List sessions, optionally filtered by account_name and/or agent_name.

    Scans all keys under ``sessions/`` for ``meta.json`` files, reads each,
    and returns the parsed metadata. Results are sorted by ``updated_at``
    descending (most recent first) and capped at *limit*.

    Args:
        store: A Chat2Primitives implementation.
        account_name: If set, only return sessions for this account.
        agent_name: If set, only return sessions for this agent.
        limit: Maximum number of sessions to return.

    Returns:
        List of ChatSessionMeta, newest first.
    """
    all_keys = store.list_keys(_sessions_prefix())
    meta_keys = [k for k in all_keys if k.value.endswith("/meta.json")]

    sessions: List[ChatSessionMeta] = []
    for mk in meta_keys:
        raw = store.read_text(mk)
        if raw is None:
            continue
        try:
            meta = ChatSessionMeta.model_validate_json(raw)
        except Exception:
            continue

        # Apply filters
        if account_name and meta.account_name != account_name:
            continue
        if agent_name and meta.agent_name != agent_name:
            continue

        sessions.append(meta)

    # Sort by updated_at descending (most recent first)
    sessions.sort(key=lambda s: s.updated_at, reverse=True)

    return sessions[:limit]


# ---------------------------------------------------------------------------
# Event operations
# ---------------------------------------------------------------------------

def append_event(
    store: Chat2Primitives,
    session_id: str,
    event: ChatEvent,
) -> ChatEvent:
    """Append a single event to the session's JSONL event log.

    Updates session meta.updated_at.
    Returns the event (with its generated event_id).
    """
    line = event.model_dump_json()
    store.append_lines(_events_key(session_id), [line])

    # Update session meta timestamp
    meta = get_session_meta(store, session_id)
    if meta is not None:
        meta.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        store.write_text(_meta_key(session_id), meta.model_dump_json())

    return event


def stream_events(
    store: Chat2Primitives,
    session_id: str,
) -> Iterator[ChatEvent]:
    """Yield events from the session's JSONL log in file order.

    Blank lines in the log are skipped. Yields nothing if the session
    does not exist or has no events.
    """
    lines = store.read_lines(_events_key(session_id))
    if lines is None:
        return

    for line in lines:
        line = line.strip()
        if not line:
            continue
        yield ChatEvent.model_validate_json(line)


def read_events(
    store: Chat2Primitives,
    session_id: str,
    *,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
    role_filter: Optional[str] = None,
    actor_filter: Optional[str] = None,
    kind_filter: Optional[str] = None,
) -> List[ChatEvent]:
    """Read events with optional filters.

    Filters are applied after loading all events.
    Returns a list (materialized, not lazy).
    """
    events = list(stream_events(store, session_id))

    if start_ts is not None:
        events = [e for e in events if e.ts >= start_ts]
    if end_ts is not None:
        events = [e for e in events if e.ts <= end_ts]
    if role_filter is not None:
        events = [e for e in events if e.role == role_filter]
    if actor_filter is not None:
        events = [e for e in events if e.actor == actor_filter]
    if kind_filter is not None:
        events = [e for e in events if e.kind == kind_filter]

    return events


def reset_session_events(store: Chat2Primitives, session_id: str) -> None:
    """Clear all events from a session, preserving metadata.

    Updates meta.updated_at.
    Raises ValueError if the session does not exist.
    """
    meta = get_session_meta(store, session_id)
    if meta is None:
        raise ValueError(f"Session not found: {session_id}")

    store.truncate(_events_key(session_id))

    meta.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    store.write_text(_meta_key(session_id), meta.model_dump_json())


__all__ = [
    "create_session",
    "get_session_meta",
    "update_session_meta",
    "delete_session",
    "list_sessions",
    "append_event",
    "stream_events",
    "read_events",
    "reset_session_events",
]
