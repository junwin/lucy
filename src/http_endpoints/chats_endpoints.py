"""HTTP endpoint implementations for chat sessions.

Phase 4: Serve from chat2 storage. All endpoints accept an optional
Chat2Store parameter. Reads try chat2 first, falling back to v1.
Writes go to both v1 and chat2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.storage.base import Storage
from src.agent import AgentManager
from src.storage.models import ChatMessage
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent


def _chat2_session_to_response(meta, events: Optional[List[ChatEvent]] = None) -> Dict[str, Any]:
    """Convert a ChatSessionMeta + events to the standard response dict."""
    body: Dict[str, Any] = {
        "id": meta.session_id,
        "account_name": meta.account_name,
        "agent_name": meta.agent_name,
        "friendly_name": meta.friendly_name,
        "created_at": meta.created_at.isoformat(),
        "updated_at": meta.updated_at.isoformat(),
        "tags": meta.tags,
        "summary": None,
        "importance_score": 0.5,
        "include_in_context": True,
        "metadata": meta.metadata,
    }

    if events is not None:
        body["messages"] = [
            {
                "role": e.role,
                "content": e.payload if isinstance(e.payload, str) else str(e.payload),
                "utc_timestamp": e.ts.isoformat(),
                "metadata": e.metadata,
            }
            for e in events
        ]
    else:
        body["messages"] = []

    return body


def post_chat_impl(
    storage: Storage,
    agent_manager: AgentManager,
    payload: Dict[str, Any],
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Dict[str, Any], int]:
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")

    if not agentName or not accountName:
        return {"error": "Missing agentName or accountName"}, 400
    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    # Write to v1 (always)
    session = storage.create_chat_session(
        account_name=accountName,
        agent_name=agentName,
        friendly_name=friendly_name,
        tags=tags,
    )

    # Write to chat2 (if available)
    if chat2_store is not None:
        try:
            chat2_store.create_session(
                user_id=accountName,
                account_name=accountName,
                agent_name=agentName,
                friendly_name=friendly_name,
                tags=tags or [],
            )
        except Exception:
            import logging
            logging.exception("chat2: failed to create session for %s/%s", accountName, agentName)

    body = {
        "id": session.id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "tags": session.tags,
        "summary": session.summary,
        "importance_score": session.importance_score,
        "include_in_context": session.include_in_context,
        "metadata": session.metadata,
        "messages": [],
    }
    return body, 200


def get_chats_impl(
    storage: Storage,
    agent_manager: AgentManager,
    agent_name: str,
    account_name: str,
    limit: int,
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Any, int]:
    agentName = (agent_name or "")
    accountName = (account_name or "")

    if not accountName:
        return {"error": "Missing accountName"}, 400
    if agentName and not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    # Try chat2 first
    if chat2_store is not None:
        try:
            sessions = chat2_store.list_sessions(
                account_name=accountName,
                agent_name=agentName or None,
                limit=limit,
            )
            body = [
                {
                    "id": s.session_id,
                    "account_name": s.account_name,
                    "agent_name": s.agent_name,
                    "friendly_name": s.friendly_name,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "tags": s.tags,
                    "summary": None,
                    "importance_score": 0.5,
                    "include_in_context": True,
                    "metadata": s.metadata,
                    "messages": [],
                }
                for s in sessions
            ]
            return body, 200
        except Exception:
            import logging
            logging.exception("chat2: list sessions failed, falling back to v1")

    # Fall back to v1
    sessions = storage.list_chat_sessions(
        account_name=accountName,
        agent_name=agentName or None,
        limit=limit,
        before=None,
    )

    body = [
        {
            "id": s.id,
            "account_name": s.account_name,
            "agent_name": s.agent_name,
            "friendly_name": s.friendly_name,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
            "tags": s.tags,
            "summary": s.summary,
            "importance_score": s.importance_score,
            "include_in_context": s.include_in_context,
            "metadata": s.metadata,
            "messages": [],
        }
        for s in sessions
    ]

    return body, 200


def get_chat_impl(
    storage: Storage,
    session_id: str,
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Dict[str, Any], int]:
    # Try chat2 first
    if chat2_store is not None:
        try:
            meta = chat2_store.get_session(session_id)
            if meta is not None:
                events = list(chat2_store.stream_events(session_id))
                body = _chat2_session_to_response(meta, events)
                return body, 200
        except Exception:
            import logging
            logging.exception("chat2: get_session failed for %s, falling back to v1", session_id)

    # Fall back to v1
    session = storage.get_chat_session(session_id)
    if not session:
        return {"error": "Chat not found"}, 404

    body = {
        "id": session.id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "tags": session.tags,
        "summary": session.summary,
        "importance_score": session.importance_score,
        "include_in_context": session.include_in_context,
        "metadata": session.metadata,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "utc_timestamp": m.utc_timestamp.isoformat() if m.utc_timestamp else None,
                "metadata": m.metadata,
            }
            for m in session.messages
        ],
    }

    return body, 200


def post_chat_message_impl(
    storage: Storage,
    session_id: str,
    data: Dict[str, Any],
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Dict[str, Any], int]:
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return {"error": "Missing role or content"}, 400

    msg = ChatMessage(role=role, content=content, metadata=metadata)

    # Write to v1 (always)
    try:
        storage.append_chat_message(session_id, msg)
    except FileNotFoundError as e:
        return {"error": str(e)}, 404

    # Write to chat2 (if available)
    if chat2_store is not None:
        try:
            event = ChatEvent(
                role=role,  # type: ignore[arg-type]
                actor=role,
                kind="user_message" if role == "user" else "assistant_message",
                payload=content,
                metadata=metadata,
            )
            chat2_store.add_event(session_id, event)
        except Exception:
            import logging
            logging.exception("chat2: failed to append event for session %s", session_id)

    return {"status": "ok"}, 200


def delete_chat_impl(
    storage: Storage,
    session_id: str,
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Dict[str, Any], int]:
    # Delete from chat2 first (if available)
    if chat2_store is not None:
        try:
            chat2_store.delete_session(session_id)
        except Exception:
            import logging
            logging.exception("chat2: failed to delete session %s", session_id)

    # Delete from v1
    try:
        session = storage.get_chat_session(session_id)
        if not session:
            return {"error": "Chat not found"}, 404

        storage.delete_chat_session(session_id)
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def update_chat_impl(
    storage: Storage,
    session_id: str,
    payload: Optional[Dict[str, Any]],
    chat2_store: Optional[Chat2Store] = None,
) -> Tuple[Dict[str, Any], int]:
    payload = payload or {}

    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    include_in_context = payload.get("include_in_context")
    metadata = payload.get("metadata")

    # Update v1
    try:
        session = storage.get_chat_session(session_id)
        if not session:
            return {"error": "Chat not found"}, 404

        storage.update_chat_session(
            session_id,
            friendly_name=friendly_name,
            tags=tags,
            include_in_context=include_in_context,
            metadata=metadata,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

    # Update chat2 (if available)
    if chat2_store is not None:
        try:
            patch: Dict[str, Any] = {}
            if friendly_name is not None:
                patch["friendly_name"] = friendly_name
            if tags is not None:
                patch["tags"] = tags
            if metadata is not None:
                patch["metadata"] = metadata
            if patch:
                chat2_store.update_session(session_id, **patch)
        except Exception:
            import logging
            logging.exception("chat2: failed to update session %s", session_id)

    return {"ok": True}, 200
