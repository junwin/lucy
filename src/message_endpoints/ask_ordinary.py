"""Ordinary JSON response handling for /ask."""

from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from src.agent import Agent
from src.message_processors.function_calling_processor import ToolHandlerError
from galet_memory import NewEvent
from .ask_request import _execution_identity, missing_required_fields, parse_request
from .ask_session import _backfill_session_context, resolve_or_create_session


if TYPE_CHECKING:
    from .ask_request_handler import AskRequestHandler


def handle(handler: "AskRequestHandler", payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Process the /ask request.

    Expected payload (legacy app.py behavior):

      - question: str (required)
      - agentName: str (required unless routing="auto")
      - routing: "explicit" (default) or "auto"
      - accountName: str (required)
      - selectType: Optional[str]  (legacy)
      - contextType: Optional[str] (preferred)
      - contextName: Optional[str] (omitted/blank uses selected agent default)
      - conversationId: Optional[str]
      - partnerAgentName: Optional[str]
    """

    try:
        payload, route = handler._route_request(payload)
    except ValueError as exc:
        return 400, {"error": str(exc)}
    if route is not None and (route.clarification or route.direct_response is not None):
        try:
            return 200, handler._routing_reply(payload, route)
        except ValueError as exc:
            return 400, {"error": str(exc)}
        except Exception:
            handler.logger.exception("/ask: could not save routing reply")
            return 500, {"error": "Could not save routing reply"}

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
        "/ask: correlation_id=%s user_id=%s agentName=%s context_type=%s context_name=%s conversationId=%s partnerAgentName=%s",
        correlation_id,
        accountName,
        agentName,
        context_type,
        context_name,
        conversationId,
        secondary_agent_override,
    )

    if missing_required_fields(request):
        handler.logger.info(
            "/ask: missing required fields user_id=%s agentName=%s conversationId=%s",
            accountName,
            agentName,
            conversationId,
        )
        return 400, {"error": "Missing question, agentName, or accountName"}

    if not handler.agent_manager.is_valid(agentName):
        handler.logger.info(
            "/ask: invalid agentName user_id=%s agentName=%s conversationId=%s",
            accountName,
            agentName,
            conversationId,
        )
        return 400, {"error": "Invalid agentName"}

    primary_agent: Optional[Agent] = handler.agent_manager.get_agent(agentName)
    if primary_agent is None:
        handler.logger.info(
            "/ask: agent configuration not found user_id=%s agentName=%s conversationId=%s",
            accountName,
            agentName,
            conversationId,
        )
        return 500, {"error": "Agent configuration not found"}

    # account object (minimum)
    account = {"accountId": accountName}

    # If a context_name is provided, ensure it exists immediately.
    # This supports durable project state (tasklists, progress, flags) without
    # requiring a separate "create context" call.
    # If no runtime context_name provided, fall back to the agent's default context
    if not context_name:
        default_ctx = getattr(primary_agent, "default_context", None)
        if default_ctx:
            context_name = str(default_ctx).strip() or None

    handler._ensure_context(accountName, context_name)

    # default context_type from agent if not provided
    if not context_type:
        context_type = primary_agent.context_type or "hybrid"

    # secondary agent (optional)
    partner_agent_obj: Optional[Agent] = None
    partner_agent_name = secondary_agent_override or (primary_agent.partner_agent or "").lower()
    if partner_agent_name:
        partner_agent_obj = handler.agent_manager.get_agent(partner_agent_name)
        if partner_agent_obj is None:
            handler.logger.info(
                "/ask: partner agent not found user_id=%s agentName=%s partnerAgentName=%s conversationId=%s",
                accountName,
                agentName,
                partner_agent_name,
                conversationId,
            )

    processor_name = (primary_agent.message_processor or "").strip()
    if not processor_name:
        handler.logger.info(
            "/ask: agent missing message_processor user_id=%s agentName=%s conversationId=%s",
            accountName,
            agentName,
            conversationId,
        )
        return 500, {"error": "Agent is missing 'message_processor'"}

    processor = handler.processor_factory.get(processor_name)

    # If the processor supports context_type, set it (safe, low-ceremony)
    if hasattr(processor, "context_type"):
        processor.context_type = context_type

    # conversation/session resolution: if no conversationId was provided,
    # try to resolve using a friendlyName (payload: friendlyName) or create
    # a new chat session. This mirrors the behavior used elsewhere in the
    # app and main entrypoint.
    try:
        if not conversationId:
            # Prefer camelCase friendlyName from client, but accept snake_case too
            friendly_name = payload.get("friendlyName") or payload.get("friendly_name")
            if friendly_name is not None:
                friendly_name = str(friendly_name).strip() or None

            # Validate account/agent before calling storage
            if not accountName or not agentName:
                handler.logger.warning(
                    "/ask: cannot resolve or create session - missing accountName or agentName (account=%s agent=%s)",
                    accountName,
                    agentName,
                )
                return 400, {"error": "Missing accountName or agentName for session creation"}

            conversationId = resolve_or_create_session(
                episodic_store=handler.episodic_store,
                account_name=accountName,
                agent_name=agentName,
                friendly_name=friendly_name,
                context_name=context_name,
            )
            handler.logger.info(
                "/ask: resolved session account=%s agent=%s friendlyName=%s session_id=%s",
                accountName,
                agentName,
                friendly_name,
                conversationId,
            )

        # app.py may have resolved a friendly-name session before the agent's
        # default context was known. Backfill that missing metadata now.
        _backfill_session_context(handler.episodic_store, conversationId, context_name, accountName)

    except Exception:
        handler.logger.exception(
            "/ask: unexpected error during session resolution account=%s agent=%s",
            accountName,
            agentName,
        )
        return 500, {"error": "Failed to resolve or create session"}

    if route is None or route.reason in {"dialogue_closed", "explicit_context"}:
        handler._remember_dialogue(payload, route, conversationId)

    try:
        result = processor.process_message(
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
        )
        response_text = result.text
        if result.metrics.success:
            handler._remember_dialogue(payload, route, conversationId, response_text)

        # Return the conversation id so callers can persist it for future requests
        return 200, {"response": response_text, "metrics": result.metrics.to_dict(), "conversation_id": conversationId, "trace_id": identity.trace_id, "run_id": identity.run_id, "parent_run_id": identity.parent_run_id, **({"routing": route.to_dict()} if route is not None else {})}

    except ToolHandlerError as e:
        error_message = f"Tool execution failed: {str(e)}"
        handler.logger.exception(
            "/ask: tool execution failed correlation_id=%s user_id=%s agentName=%s conversationId=%s",
            correlation_id,
            accountName,
            agentName,
            conversationId,
        )
        # Try to append the error to the session if we have one
        if conversationId and handler.episodic_store is not None:
            try:
                handler.episodic_store.append_event(
                    account_name=accountName, session_id=conversationId,
                    event=NewEvent(
                        role="assistant",
                        actor=agentName,
                        kind="system_note",
                        content=error_message,
                        metadata={"error": True},
                        correlation_ids=(correlation_id,) if correlation_id else (),
                    ),
                )
            except Exception:
                handler.logger.exception(
                    "/ask: failed to append error message to session %s",
                    conversationId,
                )
        return 500, {"error": error_message}

    except Exception:
        # Catch-all to ensure unusual exits are logged.
        handler.logger.exception(
            "/ask: unhandled exception correlation_id=%s user_id=%s agentName=%s conversationId=%s",
            correlation_id,
            accountName,
            agentName,
            conversationId,
        )
        return 500, {"error": "An error occurred"}
