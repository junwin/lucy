"""Streaming SSE response handling for /ask."""

import json
from typing import TYPE_CHECKING, Any, Dict, Generator, Optional

from src.agent import Agent
from src.message_processors.function_calling_processor import ToolHandlerError
from .ask_request import _execution_identity, missing_required_fields, parse_request
from .ask_session import _backfill_session_context, resolve_or_create_session


if TYPE_CHECKING:
    from .ask_request_handler import AskRequestHandler


def handle_streaming(handler: "AskRequestHandler", payload: Dict[str, Any]) -> Generator[str, None, None]:
    """Streaming variant of handle(). Yields SSE-formatted strings.

    Returns a generator suitable for Flask's Response wrapper.
    On validation errors, yields error + done events and returns.
    """
    from src.message_processors.sse_events import SSEEvent

    try:
        payload, route = handler._route_request(payload)
    except ValueError as exc:
        yield SSEEvent(type="error", message=str(exc)).to_sse()
        yield SSEEvent(type="done").to_sse()
        return
    if route is not None:
        yield SSEEvent(type="action", action="request_routing",
                       action_payload=route.to_dict()).to_sse()
        if route.clarification or route.direct_response is not None:
            try:
                response = handler._routing_reply(payload, route)
            except Exception:
                handler.logger.exception("/ask: could not save routing reply")
                yield SSEEvent(type="error", message="Could not save routing reply").to_sse()
                yield SSEEvent(type="done").to_sse()
                return
            yield SSEEvent(type="text", content=response["response"]).to_sse()
            yield SSEEvent(type="done", conversation_id=response["conversation_id"]).to_sse()
            return

    request = parse_request(payload)
    question = request.question
    agentName = request.agent_name
    accountName = request.account_name
    context_type = request.context_type
    conversationId = request.conversation_id
    secondary_agent_override = request.partner_agent_name
    image_ids = request.image_ids
    file_ids = request.file_ids
    context_name = request.context_name

    # The existing correlation ID is this server-owned root run ID.
    # A client-supplied message ID cannot define trace uniqueness.
    identity = _execution_identity(payload)
    correlation_id = identity.run_id

    handler.logger.info(
        "/ask(streaming): correlation_id=%s user_id=%s agentName=%s context_type=%s context_name=%s conversationId=%s partnerAgentName=%s",
        correlation_id,
        accountName,
        agentName,
        context_type,
        context_name,
        conversationId,
        secondary_agent_override,
    )

    if missing_required_fields(request):
        yield SSEEvent(type="error", message="Missing question, agentName, or accountName").to_sse()
        yield SSEEvent(type="done").to_sse()
        return

    if not handler.agent_manager.is_valid(agentName):
        yield SSEEvent(type="error", message="Invalid agentName").to_sse()
        yield SSEEvent(type="done").to_sse()
        return

    primary_agent: Optional[Agent] = handler.agent_manager.get_agent(agentName)
    if primary_agent is None:
        yield SSEEvent(type="error", message="Agent configuration not found").to_sse()
        yield SSEEvent(type="done").to_sse()
        return

    account = {"accountId": accountName}

    # If no runtime context provided, fall back to agent default
    if not context_name:
        default_ctx = getattr(primary_agent, "default_context", None)
        if default_ctx:
            context_name = str(default_ctx).strip() or None

    handler._ensure_context(accountName, context_name)

    if not context_type:
        context_type = primary_agent.context_type or "hybrid"

    partner_agent_obj: Optional[Agent] = None
    partner_agent_name = secondary_agent_override or (primary_agent.partner_agent or "").lower()
    if partner_agent_name:
        partner_agent_obj = handler.agent_manager.get_agent(partner_agent_name)

    processor_name = (primary_agent.message_processor or "").strip()
    if not processor_name:
        yield SSEEvent(type="error", message="Agent is missing 'message_processor'").to_sse()
        yield SSEEvent(type="done").to_sse()
        return

    processor = handler.processor_factory.get(processor_name)
    if hasattr(processor, "context_type"):
        processor.context_type = context_type

    # Session resolution (simplified: either use provided ID or generate a temp one)
    if not conversationId:
        friendly_name = payload.get("friendlyName") or payload.get("friendly_name")
        if friendly_name is not None:
            friendly_name = str(friendly_name).strip() or None

        try:
            conversationId = resolve_or_create_session(
                episodic_store=handler.episodic_store,
                account_name=accountName,
                agent_name=agentName,
                friendly_name=friendly_name,
                context_name=context_name,
            )
            handler.logger.info(
                "/ask(streaming): resolved session account=%s agent=%s friendlyName=%s session_id=%s",
                accountName,
                agentName,
                friendly_name,
                conversationId,
            )
        except Exception:
            handler.logger.exception(
                "/ask(streaming): failed to resolve or create chat session"
            )
            yield SSEEvent(type="error", message="Failed to create chat session").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

    try:
        _backfill_session_context(handler.episodic_store, conversationId, context_name, accountName)
    except Exception:
        handler.logger.exception(
            "/ask(streaming): failed to backfill session context session_id=%s",
            conversationId,
        )

    # Check if processor supports streaming
    if not hasattr(processor, "process_message_streaming"):
        yield SSEEvent(type="error", message="This agent does not support streaming.").to_sse()
        yield SSEEvent(type="done").to_sse()
        return

    if route is None or route.reason in {"dialogue_closed", "explicit_context"}:
        handler._remember_dialogue(payload, route, conversationId)

    try:
        failed = False
        reset_dialogue = False
        response_text = ""
        for sse_line in processor.process_message_streaming(
            primary_agent=primary_agent,
            secondary_agent=partner_agent_obj,
            account=account,
            message=question,
            conversation_id=conversationId,
            context_name=context_name,
            image_ids=image_ids,
            file_ids=file_ids,
            processor_factory=handler.processor_factory,
            correlation_id=correlation_id,
            trace_id=identity.trace_id,
        ):
            # FCP yields one complete SSE JSON event per item. Save before
            # forwarding done so an immediate follow-up sees the affinity.
            try:
                event = json.loads(sse_line.removeprefix("data: "))
            except (ValueError, AttributeError):
                event = {}
            if isinstance(event, dict):
                if event.get("type") == "text" and isinstance(event.get("content"), str):
                    response_text = event["content"]
                if event.get("type") == "error":
                    failed = True
                if event.get("type") == "metrics" and isinstance(event.get("metrics"), dict):
                    metrics = event["metrics"]
                    failed = failed or metrics.get("success") is False or bool(metrics.get("processor_failures"))
                if event.get("type") == "action" and event.get("action") == "reset_session":
                    reset_dialogue = True
                if event.get("type") == "done" and not failed:
                    handler._remember_dialogue(payload, None if reset_dialogue else route,
                                            conversationId, response_text)
            yield sse_line

    except ToolHandlerError as e:
        yield SSEEvent(type="error", message=f"Tool execution failed: {str(e)}").to_sse()
        yield SSEEvent(type="done", conversation_id=conversationId).to_sse()

    except Exception:
        handler.logger.exception(
            "/ask(streaming): unhandled exception correlation_id=%s user_id=%s agentName=%s conversationId=%s",
            correlation_id,
            accountName,
            agentName,
            conversationId,
        )
        yield SSEEvent(type="error", message="An error occurred").to_sse()
        yield SSEEvent(type="done", conversation_id=conversationId).to_sse()
