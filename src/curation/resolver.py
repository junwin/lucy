"""Session resolution by friendly name or session ID.

Resolution is provider-neutral: curation depends only on the CoALA episodic
session/event interface, never on Chat2 or a concrete storage backend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.coala_memory.episodic import (
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
    chats_index_path: Optional[Path] = None,
) -> Optional[EpisodicSession]:
    """Resolve a session by direct ID or friendly name."""
    if session_id:
        session = episodic_store.get_session(session_id, include_events=False)
        if session is None:
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

    # Preserve the optional legacy index as a resolution hint, while fetching
    # the actual session through the neutral episodic interface.
    if chats_index_path and chats_index_path.exists():
        try:
            index_data = json.loads(chats_index_path.read_text(encoding="utf-8"))
            candidates: List[Dict[str, Any]] = []
            for sid, entry in index_data.items():
                entry_fn = (entry.get("friendly_name") or "").strip().lower()
                entry_account = (entry.get("account_name") or "").strip().lower()
                if entry_fn == fn_lower and entry_account == account.lower():
                    candidates.append({"session_id": sid, **entry})

            if candidates:
                candidates.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
                best = candidates[0]
                session = episodic_store.get_session(
                    best["session_id"], include_events=False
                )
                if session is not None:
                    return session
        except Exception:
            logger.exception(
                "resolve_session: failed to read index.json at %s", chats_index_path
            )

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
