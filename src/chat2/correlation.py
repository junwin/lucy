"""Correlation to event mapping for Chat v2.

Manages the sidecar index that maps a correlation id to the chat events
produced while processing a request. Decision (b): the mapping lives in a
separate index file, not as a field on the ChatEvent schema.

Key layout:
  correlations/<correlation_id>.jsonl  — append-only JSONL of link lines

Each link line is one JSON object: {"session_id": ..., "event_id": ..., "ts": ...}.
The module only manages the mapping; it never reads or writes event logs.

Media-neutral: all functions operate on a Chat2Primitives backend
(FileChat2Primitives, JfsChat2Primitives, InMemoryStore).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

from src.chat2.store_primitives import Chat2Primitives, StoreKey


class CorrelationLink(BaseModel):
    """A single correlation to event mapping entry."""

    session_id: str
    event_id: str
    ts: datetime

    @field_validator("session_id", "event_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """Validate that the id is a UUID string."""
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid UUID format: {v}")

    @field_validator("ts")
    @classmethod
    def ensure_utc(cls, v: datetime) -> datetime:
        """Normalize to timezone-naive UTC (consistent with ChatEvent)."""
        if v.tzinfo is not None:
            v = v.astimezone(tz=None).replace(tzinfo=None)
        return v


def _key(correlation_id: str) -> StoreKey:
    """Build the StoreKey for a correlation's link file.

    Validates the correlation id before building the key. Raises ValueError
    for ids that would nest paths or escape the correlations/ directory.
    """
    if not isinstance(correlation_id, str):
        raise TypeError(
            f"correlation_id must be a str, got {type(correlation_id)}"
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


def link_event(
    store: Chat2Primitives,
    correlation_id: Optional[str],
    session_id: str,
    event_id: str,
) -> None:
    """Append one link line for an event to the correlation's index file.

    Falsy correlation ids (None or '') are a no-op and never raise.
    Creates the index file on first use via append_lines. ts is serialized
    as datetime.now(timezone.utc).isoformat().
    """
    if not correlation_id:
        return
    ts = datetime.now(timezone.utc)
    link = CorrelationLink(session_id=session_id, event_id=event_id, ts=ts)
    line = json.dumps(
        {
            "session_id": link.session_id,
            "event_id": link.event_id,
            "ts": ts.isoformat(),
        },
        separators=(",", ":"),
    )
    store.append_lines(_key(correlation_id), [line])


def get_links(
    store: Chat2Primitives,
    correlation_id: Optional[str],
) -> List[CorrelationLink]:
    """Return the links for a correlation in write order.

    Dedupes by event_id (first occurrence wins). Unknown or falsy
    correlation ids return [] and never raise. Unparseable lines are
    skipped.
    """
    if not correlation_id:
        return []
    lines = store.read_lines(_key(correlation_id))
    if lines is None:
        return []
    links: List[CorrelationLink] = []
    seen: set[str] = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            link = CorrelationLink(
                session_id=data["session_id"],
                event_id=data["event_id"],
                ts=data["ts"],
            )
        except Exception:
            continue
        if link.event_id in seen:
            continue
        seen.add(link.event_id)
        links.append(link)
    return links


def get_event_ids(
    store: Chat2Primitives,
    correlation_id: Optional[str],
) -> List[str]:
    """Return the event ids linked to a correlation, in link order.

    Returns [] when the correlation id is unknown.
    """
    return [link.event_id for link in get_links(store, correlation_id)]


__all__ = ["CorrelationLink", "link_event", "get_links", "get_event_ids"]
