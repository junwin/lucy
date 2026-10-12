"""Episodic session resolution and procedural context preparation for /ask."""

import logging
import uuid
from typing import TYPE_CHECKING, Optional

from galet_memory import ProceduralMemoryRequest, SessionChanges
from src.episodic import LucyEpisodicStore, list_account_sessions


if TYPE_CHECKING:
    from .ask_request_handler import AskRequestHandler


def resolve_or_create_session(
    episodic_store: Optional[LucyEpisodicStore],
    account_name: str,
    agent_name: str,
    friendly_name: Optional[str],
    context_name: Optional[str] = None,
    limit: int = 500,
) -> str:
    """Resolve an existing episodic session by friendly name or create a new one.

    Mirrors v1 semantics: case-insensitive substring match on friendly_name,
    scoped to the account, with an explicit limit so sessions beyond the
    default 50 are not missed. Creation uses a stable session_id so IDs stay
    consistent across storage layers.

    When a context is known, it is stored on newly-created sessions. Existing
    matched sessions are backfilled only when their context_name is empty;
    an established context is never overwritten implicitly.
    """
    if episodic_store is None:
        logging.warning(
            "/ask: episodic_store is None; session will not be persisted (account=%s agent=%s)",
            account_name,
            agent_name,
        )
        return str(uuid.uuid4())

    if friendly_name:
        q = friendly_name.strip().lower()
        matches = [
            meta
            for meta in list_account_sessions(episodic_store, account_name, limit)
            if (meta.friendly_name or "").strip().lower().find(q) != -1
        ]
        if matches:
            match = matches[0]
            if context_name and not match.context_name:
                episodic_store.update_session(
                    account_name=account_name, session_id=match.session_id, changes=SessionChanges(context_name=context_name)
                )
            return match.session_id

    session_id = str(uuid.uuid4())
    episodic_store.create_session(
        account_name=account_name,
        metadata={"default_agent": agent_name},
        session_id=session_id,
        friendly_name=friendly_name or f"Chat {session_id[:8]}",
        context_name=context_name,
    )
    return session_id


def _backfill_session_context(
    episodic_store: Optional[LucyEpisodicStore],
    conversation_id: str,
    context_name: Optional[str],
    account_name: str,
) -> None:
    """Best-effort context backfill for sessions resolved before context lookup."""
    if episodic_store is None or not conversation_id or not context_name:
        return
    meta = episodic_store.get_session(account_name=account_name, session_id=conversation_id)
    if meta is not None and not meta.context_name:
        episodic_store.update_session(
            account_name=account_name, session_id=conversation_id, changes=SessionChanges(context_name=context_name)
        )


def _ensure_context(handler: "AskRequestHandler", account_name: str, context_name: Optional[str]) -> None:
    """Create an account context only when no configured scope contains it."""
    if handler.procedural_memory is None or not context_name or context_name.strip().lower() == "none":
        return
    handler.procedural_memory.recall(ProceduralMemoryRequest(
        account_name=account_name, context_name=context_name,
        create_if_missing=True, include_resolved_text=False,
        include_skills=False, include_required_tools=False,
    ))
