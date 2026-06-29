"""Session resolution by friendly name or session ID.

Resolves a session using:
1. Direct session_id (takes precedence)
2. friendly_name via index.json lookup (case-insensitive, tie-break by updated_at)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatSessionMeta

logger = logging.getLogger(__name__)


def resolve_session(
    *,
    session_id: Optional[str] = None,
    friendly_name: Optional[str] = None,
    account: str,
    chat2_store: Chat2Store,
    chats_index_path: Optional[Path] = None,
) -> Optional[ChatSessionMeta]:
    """Resolve a session by session_id or friendly_name.

    Args:
        session_id: Direct UUID. Takes precedence if provided.
        friendly_name: Friendly name to resolve via index.
        account: Account name (e.g. "junwin").
        chat2_store: Chat2Store instance for session lookup.
        chats_index_path: Optional path to index.json for friendly-name resolution.
            If not provided, falls back to listing sessions via chat2_store.

    Returns:
        ChatSessionMeta if found, else None.
    """
    # 1) Direct session_id
    if session_id:
        meta = chat2_store.get_session(session_id)
        if meta is None:
            logger.warning("resolve_session: session_id=%s not found", session_id)
            return None
        return meta

    # 2) friendly_name resolution
    if not friendly_name:
        logger.warning("resolve_session: neither session_id nor friendly_name provided")
        return None

    fn_lower = friendly_name.strip().lower()
    if not fn_lower:
        logger.warning("resolve_session: empty friendly_name")
        return None

    # 2a) Try index.json first
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
                # Sort by updated_at descending, pick first
                candidates.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
                best = candidates[0]
                meta = chat2_store.get_session(best["session_id"])
                if meta:
                    return meta
                logger.warning(
                    "resolve_session: index entry found but session not in store: %s",
                    best["session_id"],
                )
        except Exception:
            logger.exception("resolve_session: failed to read index.json at %s", chats_index_path)

    # 2b) Fallback: list sessions and match by friendly_name
    sessions = chat2_store.list_sessions(account_name=account, limit=100)
    matches = [
        s for s in sessions
        if (s.friendly_name or "").strip().lower() == fn_lower
    ]
    if not matches:
        logger.info(
            "resolve_session: no session found for friendly_name=%s account=%s",
            friendly_name,
            account,
        )
        return None

    # Sort by updated_at descending
    matches.sort(key=lambda s: s.updated_at, reverse=True)
    return matches[0]
