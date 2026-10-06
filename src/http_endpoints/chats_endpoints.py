"""HTTP endpoint implementations for chat sessions.

Serve from LucyEpisodicStore domain seam. All endpoints require an
LucyEpisodicStore parameter.
"""

from __future__ import annotations

from src.episodic import LucyEpisodicStore, list_account_sessions

import json
from typing import Any, Dict, List, Optional

from src.agent import AgentManager
from galet_memory import (
    NewEvent,
    Session,
    SessionChanges,
)


def _episodic_session_to_response(session: Session, include_events: bool = True, events=()) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "id": session.session_id,
        "account_name": session.account_name,
        "agent_name": session.metadata.get("default_agent", ""),
        "friendly_name": session.friendly_name,
        "created_at": session.created_at.isoformat() if session.created_at is not None else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at is not None else None,
        "tags": list(session.tags),
        "summary": None,
        "importance_score": 0.5,
        "include_in_context": True,
        "metadata": session.metadata,
        "context_name": session.context_name,
        "user_id": session.account_name,
        "session_type": session.metadata.get("session_type", "user"),
        "participants": session.metadata.get("participants", []),
        "links": session.metadata.get("links", {}),
    }

    if include_events:
        messages = []
        for e in events:
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
                    "correlation_ids": list(e.correlation_ids),
                    "sequence": e.sequence,
                    "stored_at": e.stored_at.isoformat() if e.stored_at else None,
                }
            )
        body["messages"] = messages
    else:
        body["messages"] = []

    return body


def post_chat_impl(
    episodic_memory_manager: LucyEpisodicStore,
    agent_manager: AgentManager,
    payload: Dict[str, Any],
    config=None,
) -> tuple[Dict[str, Any], int]:
    agentName = (payload.get("agentName", "") or "").lower()
    mode = payload.get("routing", "explicit")
    if mode not in ("explicit", "auto"):
        return {"error": "routing must be 'explicit' or 'auto'"}, 400
    if mode == "auto" and not agentName:
        routing_config = (config.get("request_routing", {}) or {}) if config is not None else {}
        if not isinstance(routing_config, dict):
            return {"error": "request_routing must be an object"}, 400
        agentName = str(routing_config.get("default_agent", "lucy")).strip().lower()
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
        metadata={"default_agent": agentName},
        friendly_name=friendly_name,
        context_name=context_name,
        tags=tags or [],
    )

    body = _episodic_session_to_response(meta, include_events=False)
    return body, 200


def get_chats_impl(
    episodic_memory_manager: LucyEpisodicStore,
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

    sessions = list_account_sessions(episodic_memory_manager, accountName, max(0, limit))
    body = [
        _episodic_session_to_response(s, include_events=False)
        for s in sessions
    ]
    return body, 200


def get_chat_impl(
    episodic_memory_manager: LucyEpisodicStore,
    session_id: str,
    config=None,
    *, account_name: str = "",
) -> tuple[Dict[str, Any], int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400
    meta = episodic_memory_manager.get_session(account_name=account_name, session_id=session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    snapshot = episodic_memory_manager.get_active_snapshot(account_name=account_name, session_id=session_id)
    body = _episodic_session_to_response(meta, include_events=True, events=snapshot.events)
    if config is not None:
        from src.message_processors.image_delivery import image_event_for_browser, image_event_for_history
        from src.message_processors.sse_events import SSEEvent
        for message in body["messages"]:
            if message["kind"] != "generated_image":
                continue
            try:
                payload = json.loads(message["content"])
                # UUID images reopen via authenticated download. Path images
                # served by serve_image use the shared browser boundary again.
                if isinstance(payload, dict) and payload.get("image_id"):
                    reference = image_event_for_history(SSEEvent(type="image", **payload), meta.account_name)
                    message["content"] = reference.model_dump_json(exclude_none=True)
                elif isinstance(payload, dict) and payload.get("image_ref"):
                    wire = image_event_for_browser(SSEEvent(type="image", **payload), config, meta.account_name)
                    message["content"] = wire.model_dump_json(exclude_none=True)
            except (ValueError, TypeError):
                pass
    return body, 200


def post_chat_message_impl(
    episodic_memory_manager: LucyEpisodicStore,
    session_id: str,
    data: Dict[str, Any],
    *, account_name: str = "",
) -> tuple[Dict[str, Any], int]:
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return {"error": "Missing role or content"}, 400

    if not account_name:
        return {"error": "Missing accountName"}, 400
    meta = episodic_memory_manager.get_session(account_name=account_name, session_id=session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    event = NewEvent(
        role=role,
        content=content,
        kind=("user_message" if role == "user" else "assistant_message"),
        actor=account_name if role == "user" else str(data.get("actor") or metadata.get("agent") or meta.metadata.get("default_agent") or role),
        correlation_ids=tuple(data.get("correlation_ids") or ()),
        created_at=None,
        metadata=metadata,
    )

    try:
        episodic_memory_manager.append_event(account_name=account_name, session_id=session_id, event=event)
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

    return {"status": "ok"}, 200


def delete_chat_impl(
    episodic_memory_manager: LucyEpisodicStore,
    session_id: str,
    *, account_name: str = "",
) -> tuple[Dict[str, Any], int]:
    if not account_name:
        return {"error": "Missing accountName"}, 400
    meta = episodic_memory_manager.get_session(account_name=account_name, session_id=session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    try:
        episodic_memory_manager.delete_session(account_name=account_name, session_id=session_id)
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def update_chat_impl(
    episodic_memory_manager: LucyEpisodicStore,
    session_id: str,
    payload: Optional[Dict[str, Any]],
    *, account_name: str = "",
) -> tuple[Dict[str, Any], int]:
    payload = payload or {}

    if not account_name:
        return {"error": "Missing accountName"}, 400
    meta = episodic_memory_manager.get_session(account_name=account_name, session_id=session_id)
    if meta is None:
        return {"error": "Chat not found"}, 404

    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    metadata = payload.get("metadata")
    context_name = payload.get("contextName")

    patch: Dict[str, Any] = {}
    if "friendlyName" in payload:
        patch["friendly_name"] = friendly_name
    if tags is not None:
        patch["tags"] = tags
    if metadata is not None:
        patch["metadata"] = metadata
    if "contextName" in payload:
        patch["context_name"] = context_name

    if patch:
        try:
            episodic_memory_manager.update_session(account_name=account_name, session_id=session_id, changes=SessionChanges(**patch))
        except Exception as e:
            return {"ok": False, "error": str(e)}, 500

    return {"ok": True}, 200
