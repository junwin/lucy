"""Session resolution by friendly name or session ID.

Resolution is provider-neutral: curation depends only on the CoALA episodic
session/event interface, never on a concrete storage backend.
"""

from __future__ import annotations

import logging
from typing import Optional

from galet_memory import (
    EpisodicMemoryManager,
    EpisodicSession,
    EpisodicSessionQuery,
)

logger = logging.getLogger(__name__)


def resolve_session(
    *,
    session_id: Optional[str] = None,
    friendly_name: Optional[str] = None,
    account: str,
    episodic_store: EpisodicMemoryManager,
) -> Optional[EpisodicSession]:
    """Resolve a session by direct ID or friendly name."""
    if session_id:
        session = episodic_store.get_session(session_id, include_events=False)
        if session is None or session.account_name != account:
            logger.warning("resolve_session: session_id=%s not found", session_id)
            return None
        return session

    if not friendly_name:
        logger.warning("resolve_session: neither session_id nor friendly_name provided")
        return None

    fn_lower = friendly_name.strip().lower()
    if not fn_lower:
        logger.warning("resolve_session: empty friendly_name")
        return None

    sessions = episodic_store.list_sessions(
        EpisodicSessionQuery(account_name=account, limit=100)
    )
    matches = [
        session
        for session in sessions
        if (session.friendly_name or "").strip().lower() == fn_lower
    ]
    if not matches:
        logger.info(
            "resolve_session: no session found for friendly_name=%s account=%s",
            friendly_name,
            account,
        )
        return None

    matches.sort(
        key=lambda session: session.updated_at or session.created_at,
        reverse=True,
    )
    return matches[0]
