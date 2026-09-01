"""
SQLite backend package for chat2 storage primitives.

Exposes ``SqliteChat2Primitives`` — the SQLite-backed implementation of
the generic-store doc/log protocol (see backend.py) — and the chat key
helpers that define the logical key layout shared by every backend.

Key layout (validated ``StoreKey`` values from store_primitives.py):

  sessions/<session_id>/meta.json      session metadata document
  sessions/<session_id>/events.jsonl   append-only event log (JSONL)
  correlations/<correlation_id>.jsonl  correlation link log (JSONL)
  sessions/                            prefix covering all session keys

These helpers mirror the private key builders in jsonl_store.py
(``_meta_key`` / ``_events_key`` / ``_sessions_prefix``) and
correlation.py (``_key``). Keeping the layout defined once here means
the Chat2Store facade can switch backends (FileChat2Primitives,
JfsChat2Primitives, InMemoryStore, SqliteChat2Primitives) without
changing any keys.
"""

from __future__ import annotations

from src.chat2.sqlite.backend import SqliteChat2Primitives
from src.chat2.store_primitives import StoreKey

__all__ = [
    "SqliteChat2Primitives",
    "StoreKey",
    "session_meta_key",
    "session_events_key",
    "sessions_prefix",
    "correlation_key",
]


def session_meta_key(session_id: str) -> StoreKey:
    """Build the StoreKey for a session's metadata document.

    Mirrors jsonl_store._meta_key. Validation (no leading '/', no '..'
    segment) is enforced by StoreKey.
    """
    return StoreKey(f"sessions/{session_id}/meta.json")


def session_events_key(session_id: str) -> StoreKey:
    """Build the StoreKey for a session's append-only event log.

    Mirrors jsonl_store._events_key.
    """
    return StoreKey(f"sessions/{session_id}/events.jsonl")


def sessions_prefix() -> StoreKey:
    """Build the StoreKey prefix covering all session keys.

    Mirrors jsonl_store._sessions_prefix.
    """
    return StoreKey("sessions/")


def correlation_key(correlation_id: str) -> StoreKey:
    """Build the StoreKey for a correlation's link log.

    Mirrors correlation._key validation: rejects non-str ids and ids
    containing '/' or '..' so links can never nest outside
    ``correlations/``.
    """
    if not isinstance(correlation_id, str):
        raise TypeError(
            f"correlation_id must be a str, got {type(correlation_id).__name__}"
        )
    if "/" in correlation_id:
        raise ValueError(
            f"correlation_id must not contain '/': {correlation_id}"
        )
    if ".." in correlation_id:
        raise ValueError(
            f"correlation_id must not contain '..': {correlation_id}"
        )
    return StoreKey(f"correlations/{correlation_id}.jsonl")
