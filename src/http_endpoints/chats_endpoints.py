from typing import Any, Dict, Tuple, Optional

from src.storage.base import Storage
from src.agent import AgentManager
from src.storage.models import ChatMessage


def post_chat_impl(storage: Storage, agent_manager: AgentManager, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    agentName = (payload.get("agentName", "") or "").lower()
    accountName = (payload.get("accountName", "") or "").lower()
    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")

    if not agentName or not accountName:
        return {"error": "Missing agentName or accountName"}, 400
    if not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

    session = storage.create_chat_session(
        account_name=accountName,
        agent_name=agentName,
        friendly_name=friendly_name,
        tags=tags,
    )

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


def get_chats_impl(storage: Storage, agent_manager: AgentManager, agent_name: str, account_name: str, limit: int) -> Tuple[Any, int]:
    agentName = (agent_name or "")
    accountName = (account_name or "")

    if not accountName:
        return {"error": "Missing accountName"}, 400
    if agentName and not agent_manager.is_valid(agentName):
        return {"error": "Invalid agentName"}, 400

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


def get_chat_impl(storage: Storage, session_id: str) -> Tuple[Dict[str, Any], int]:
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


def post_chat_message_impl(storage: Storage, session_id: str, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    role = data.get("role")
    content = data.get("content")
    metadata = data.get("metadata") or {}

    if not role or content is None:
        return {"error": "Missing role or content"}, 400

    msg = ChatMessage(role=role, content=content, metadata=metadata)

    try:
        storage.append_chat_message(session_id, msg)
    except FileNotFoundError as e:
        return {"error": str(e)}, 404

    return {"status": "ok"}, 200


def delete_chat_impl(storage: Storage, session_id: str) -> Tuple[Dict[str, Any], int]:
    try:
        session = storage.get_chat_session(session_id)
        if not session:
            return {"error": "Chat not found"}, 404

        storage.delete_chat_session(session_id)
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500


def update_chat_impl(storage: Storage, session_id: str, payload: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], int]:
    payload = payload or {}

    friendly_name = payload.get("friendlyName")
    tags = payload.get("tags")
    include_in_context = payload.get("include_in_context")
    metadata = payload.get("metadata")

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
        return {"ok": True}, 200
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500
