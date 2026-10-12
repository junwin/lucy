"""Endpoint routing replies and dialogue persistence; selection stays in SkillsetRouter."""

import json
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from galet_memory import NewEvent
from src.routing.skillset_router import RouteDecision
from .ask_request import _execution_identity
from .ask_session import resolve_or_create_session


if TYPE_CHECKING:
    from .ask_request_handler import AskRequestHandler


def _remember_dialogue(handler: "AskRequestHandler", payload, route, conversation_id, response_text=""):
    if handler.request_router is None:
        return
    try:
        handler.request_router.remember_dialogue(payload, route, conversation_id, response_text)
    except Exception:
        # The worker response remains usable if session metadata cannot be
        # saved. Do not renew affinity on an execution error.
        handler.logger.exception("/ask: could not save routing dialogue session_id=%s", conversation_id)


def _route_request(handler: "AskRequestHandler", payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[RouteDecision]]:
    mode = payload.get("routing", "explicit")
    if mode not in ("explicit", "auto"):
        raise ValueError("routing must be 'explicit' or 'auto'")
    if mode != "auto":
        return payload, None
    if not payload.get("question") or not payload.get("accountName"):
        raise ValueError("Missing question or accountName")
    if handler.request_router is None:
        raise ValueError("Request routing is unavailable")
    decision = handler.request_router.route(payload)
    handler.logger.info("request_routing run decision=%s", json.dumps(decision.to_dict()))
    routed = dict(payload)
    routed["agentName"] = decision.selected_agent
    return routed, decision


def _routing_reply(handler: "AskRequestHandler", payload: Dict[str, Any], route: RouteDecision) -> Dict[str, Any]:
    """Save a routing clarification or direct answer without building a prompt."""
    reply = route.direct_response if route.direct_response is not None else route.clarification
    identity = _execution_identity(payload)
    account_name = (payload.get("accountName") or "").lower()
    conversation_id = payload.get("conversationId") or resolve_or_create_session(
        handler.episodic_store, account_name, route.selected_agent,
        payload.get("friendlyName") or payload.get("friendly_name"),
    )
    if handler.episodic_store is not None:
        meta = handler.episodic_store.get_session(account_name=account_name, session_id=conversation_id)
        if meta is None or meta.account_name != account_name:
            raise ValueError("Conversation does not belong to this account")
        metadata = {"run_id": identity.run_id, "trace_id": identity.trace_id,
                    "routing": route.to_dict()}
        correlation_id = str(uuid.uuid4())
        handler.episodic_store.append_events(account_name=account_name, session_id=conversation_id, events=[
            NewEvent(role="user", kind="user_message", actor=account_name,
                     content=payload["question"], metadata=metadata, correlation_ids=(correlation_id,)),
            NewEvent(role="assistant", kind="assistant_message", actor=route.selected_agent,
                     content=reply, metadata=metadata, correlation_ids=(correlation_id,)),
        ])
    if route.direct_response is not None:
        handler._remember_dialogue(payload, route, conversation_id, reply)
    return {"response": reply, "conversation_id": conversation_id,
            "needs_clarification": bool(route.clarification), "routing": route.to_dict(),
            "run_id": identity.run_id, "trace_id": identity.trace_id,
            "parent_run_id": identity.parent_run_id}
