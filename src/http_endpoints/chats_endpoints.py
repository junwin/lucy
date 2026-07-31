"""HTTP endpoint implementations for chat sessions.

Phase 4: Serve exclusively from chat2 storage. All endpoints require a
Chat2Store parameter. v1 Storage is no longer used.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.agent import AgentManager
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
                "kind": e.kind,
                "content": e.payload if isinstance(e.payload, str) else json.dumps(e.payload, ensure_ascii=False),
                "utc_timestamp": e.ts.isoformat(),
                "metadata": e.metadata,
            }
            for e in events
        ]
    else:
        body["messages"] = []

    return body


def post_chat_impl(
    chat2_store: Chat2Store,
    agent_manager: AgentManager,
    payload: Dict[str, Any],
) -> tuple[Dict[str, Any], int]:
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")

    if not agentName or not accountName:
        return {"error": "Missing agentName or accountName"}, 400
    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    meta = chat2_store.create_session(
        user_id=accountName,
        account_name=accountName,
        agent_name=agentName,
        friendly_name=friendly_name,
        tags=tags or [],
    )

    body = {
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
        "messages": [],
    }
    return body, 200


def get_chats_impl(
    chat2_store: Chat2Store,
    agent_manager: AgentManager,
    agent_name: str,
    account_name: str,
    limit: int,
) -> tuple[Any, int]:
    agentName = (agent_name or "")
    accountName = (account_name or "")

    if not accountName:
        return {"error": "Missing accountName"}, 400
    if agentName and not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

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


def get_chat_impl(
    chat2_store: Chat2Store,
    session_id: str,
) -> tuple[Dict[str, Any], int]:
    meta = chat2_store.get_session(session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    events = list(chat2_store.stream_events(session_id))
    body = _chat2_session_to_response(meta, events)
    return body, 200


def post_chat_message_impl(
    chat2_store: Chat2Store,
    session_id: str,
    data: Dict[str, Any],
) -> tuple[Dict[str, Any], int]:
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return {"error": "Missing role or content"}, 400

    if not chat2_store.session_exists(session_id):
        return {"error": "Chat not found"}, 404

    event = ChatEvent(
        role=role,  # type: ignore[arg-type]
        actor=role,
        kind="user_message" if role == "user" else "assistant_message",
        payload=content,
        metadata=metadata,
    )

    chat2_store.add_event(session_id, event)
    return {"status": "ok"}, 200


def delete_chat_impl(
    chat2_store: Chat2Store,
    session_id: str,
) -> tuple[Dict[str, Any], int]:
    meta = chat2_store.get_session(session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    try:
        chat2_store.delete_session(session_id)
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def update_chat_impl(
    chat2_store: Chat2Store,
    session_id: str,
    payload: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], int]:
    payload = payload or {}

    meta = chat2_store.get_session(session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    metadata = payload.get("metadata")

    patch: Dict[str, Any] = {}
    if friendly_name is not None:
        patch["friendly_name"] = friendly_name
    if tags is not None:
        patch["tags"] = tags
    if metadata is not None:
        patch["metadata"] = metadata

    if patch:
        try:
            chat2_store.update_session(session_id, **patch)
        except Exception as e:
            return {"ok": False, "error": str(e)}, 500

    return {"ok": True}, 200
