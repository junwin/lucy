"""Endpoint routing replies and dialogue persistence; selection stays in SkillsetRouter."""

import json
import re
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from galet_memory import NewEvent
from src.routing.skillset_router import RouteDecision
from .ask_request import _execution_identity
from .ask_session import resolve_or_create_session


if TYPE_CHECKING:
    from .ask_request_handler import AskRequestHandler


_AGENT_DIRECTIVE = re.compile(r"^\s*@([^\s]+)(?:\s+([\s\S]*))?$")


def _available_agent_names(agent_manager) -> list[str]:
    agents = getattr(agent_manager, "get_available_agents", None)
    if callable(agents):
        return [str(agent.name) for agent in agents() if getattr(agent, "name", None)]
    names = getattr(agent_manager, "get_agent_names", None)
    if callable(names):
        return [str(name) for name in names() if name]
    return [str(agent.name) for agent in getattr(agent_manager, "agents", []) if getattr(agent, "name", None)]


def _directive_agent_name(agent_manager, requested_name: str) -> Optional[str]:
    match = next((name for name in _available_agent_names(agent_manager)
                  if name.casefold() == requested_name.casefold()), None)
    if match is not None:
        return match
    # Keep compatibility with small AgentManager fakes and adapters that do
    # not expose their catalog while still requiring configured-agent lookup.
    normalized = requested_name.casefold()
    if agent_manager.is_valid(normalized):
        return normalized
    if agent_manager.is_valid(requested_name):
        return requested_name
    return None


def _fallback_agent(handler: "AskRequestHandler", payload: Dict[str, Any], mode: str) -> str:
    requested = str(payload.get("agentName") or "").strip().lower()
    if requested and handler.agent_manager.is_valid(requested):
        return requested
    if mode == "auto" and handler.request_router is not None:
        cfg = handler.request_router.config.get("request_routing", {}) or {}
        fallback = str(cfg.get("default_agent", "lucy")).strip().lower() if isinstance(cfg, dict) else "lucy"
        if fallback and handler.agent_manager.is_valid(fallback):
            return fallback
    if handler.agent_manager.is_valid("lucy"):
        return "lucy"
    names = _available_agent_names(handler.agent_manager)
    return names[0] if names else requested


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

    question = payload.get("question")
    directive = _AGENT_DIRECTIVE.match(question) if isinstance(question, str) else None
    if directive:
        target = directive.group(1)
        message = (directive.group(2) or "").strip()
        fallback = _fallback_agent(handler, payload, mode)
        agent_name = _directive_agent_name(handler.agent_manager, target)
        if not message:
            return payload, RouteDecision(
                requested_agent=fallback, selected_agent=fallback,
                reason="invalid_agent_override",
                clarification=f"Please include a request after @{target}.",
            )
        if agent_name is None:
            available = _available_agent_names(handler.agent_manager)
            choices = ", ".join(available)
            detail = f" Available agents: {choices}." if choices else ""
            return payload, RouteDecision(
                requested_agent=fallback, selected_agent=fallback,
                reason="invalid_agent_override",
                clarification=f"I can't find an available agent named @{target}.{detail}",
            )

        routed = dict(payload)
        routed["question"] = message
        routed["agentName"] = agent_name
        # A one-off agent uses that agent's configured context. Do not carry
        # the sidebar's agent context into the temporary turn.
        routed.pop("contextName", None)
        routed.pop("contextType", None)
        routed.pop("selectType", None)
        routed.pop("partnerAgentName", None)
        return routed, RouteDecision(
            requested_agent=fallback, selected_agent=agent_name,
            reason="one_off_agent_override",
        )

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
