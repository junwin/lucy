"""HTTP endpoint implementations for chat sessions.

Serve from EpisodicMemoryManager domain seam. All endpoints require an
EpisodicMemoryManager parameter.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.agent import AgentManager
from src.coala_memory.episodic.management import (
    EpisodicMemoryManager,
    EpisodicSessionQuery,
)
from src.coala_memory.episodic.management import EpisodicSession
from src.coala_memory.episodic.interface import EpisodicEvent


def _episodic_session_to_response(session: EpisodicSession, include_events: bool = True) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "id": session.session_id,
        "account_name": session.account_name,
        "agent_name": session.agent_name,
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat() if session.created_at is not None else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at is not None else None,
        "tags": session.tags,
        "summary": None,
        "importance_score": 0.5,
        "include_in_context": True,
        "metadata": session.metadata,
        "context_name": session.context_name,
        "user_id": session.user_id,
        "session_type": session.session_type,
        "participants": session.participants,
        "links": session.links,
    }

    if include_events:
        messages = []
        for e in session.events:
            content = e.content if isinstance(e.content, str) else json.dumps(e.content, ensure_ascii=False)
            utc_timestamp = e.created_at.isoformat() if getattr(e, "created_at", None) is not None else None
            metadata = e.metadata if (e.metadata and isinstance(e.metadata, dict)) else {"actor": getattr(e, "actor", None)}
            messages.append(
                {
                    "role": e.role,
                    "kind": e.kind,
                    "content": content,
                    "utc_timestamp": utc_timestamp,
                    "metadata": metadata,
                    "event_id": getattr(e, "event_id", None),
                    "actor": getattr(e, "actor", None),
                }
            )
        body["messages"] = messages
    else:
        body["messages"] = []

    return body


def post_chat_impl(
    episodic_memory_manager: EpisodicMemoryManager,
    agent_manager: AgentManager,
    payload: Dict[str, Any],
) -> tuple[Dict[str, Any], int]:
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    context_name = payload.get("contextName")

    if not agentName or not accountName:
        return {"error": "Missing agentName or accountName"}, 400
    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    meta = episodic_memory_manager.create_session(
        account_name=accountName,
        agent_name=agentName,
        user_id=accountName,
        friendly_name=friendly_name,
        context_name=context_name,
        tags=tags or [],
    )

    body = _episodic_session_to_response(meta, include_events=False)
    return body, 200


def get_chats_impl(
    episodic_memory_manager: EpisodicMemoryManager,
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

    query = EpisodicSessionQuery(account_name=accountName, agent_name=agentName or "", limit=limit)
    sessions = episodic_memory_manager.list_sessions(query)
    body = [
        _episodic_session_to_response(s, include_events=False)
        for s in sessions
    ]
    return body, 200


def get_chat_impl(
    episodic_memory_manager: EpisodicMemoryManager,
    session_id: str,
) -> tuple[Dict[str, Any], int]:
    meta = episodic_memory_manager.get_session(session_id, include_events=True)
    if meta is None:
        return {"error": "Chat not found"}, 404

    body = _episodic_session_to_response(meta, include_events=True)
    return body, 200


def post_chat_message_impl(
    episodic_memory_manager: EpisodicMemoryManager,
    session_id: str,
    data: Dict[str, Any],
) -> tuple[Dict[str, Any], int]:
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return {"error": "Missing role or content"}, 400

    meta = episodic_memory_manager.get_session(session_id, include_events=False)
    if meta is None:
        return {"error": "Chat not found"}, 404

    event = EpisodicEvent(
        role=role,
        content=content,
        kind=("user_message" if role == "user" else "assistant_message"),
        actor=role,
        event_id="",
        created_at=None,
        metadata=metadata,
    )

    try:
        episodic_memory_manager.append_event(session_id, event)
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

    return {"status": "ok"}, 200


def delete_chat_impl(
    episodic_memory_manager: EpisodicMemoryManager,
    session_id: str,
) -> tuple[Dict[str, Any], int]:
    meta = episodic_memory_manager.get_session(session_id, include_events=False)
    if meta is None:
        return {"error": "Chat not found"}, 404

    try:
        episodic_memory_manager.delete_session(session_id)
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def update_chat_impl(
    episodic_memory_manager: EpisodicMemoryManager,
    session_id: str,
    payload: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], int]:
    payload = payload or {}

    meta = episodic_memory_manager.get_session(session_id, include_events=False)
    if meta is None:
        return {"error": "Chat not found"}, 404

    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    metadata = payload.get("metadata")
    context_name = payload.get("contextName")

    patch: Dict[str, Any] = {}
    if friendly_name is not None:
        patch["friendly_name"] = friendly_name
    if tags is not None:
        patch["tags"] = tags
    if metadata is not None:
        patch["metadata"] = metadata
    if context_name is not None:
        patch["context_name"] = context_name

    if patch:
        try:
            episodic_memory_manager.update_session(session_id, patch)
        except Exception as e:
            return {"ok": False, "error": str(e)}, 500

    return {"ok": True}, 200
