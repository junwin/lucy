import json
import logging
import uuid
from typing import Any, Dict, Tuple, Optional, Generator

from src.agent import AgentManager, Agent
from src.config_manager import ConfigManager
from src.storage.base import Storage
from src.message_processors.processor_factory import ProcessorFactory
from src.message_processors.function_calling_processor import ToolHandlerError
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent


def resolve_or_create_session(
    chat2_store: Optional[Chat2Store],
    account_name: str,
    agent_name: str,
    friendly_name: Optional[str],
    limit: int = 500,
) -> str:
    """Resolve an existing chat2 session by friendly name or create a new one.

    Mirrors v1 semantics: case-insensitive substring match on friendly_name,
    scoped to account+agent, with an explicit limit so sessions beyond the
    default 50 are not missed. Creation uses a stable session_id so IDs stay
    consistent across storage layers.
    """
    if chat2_store is None:
        logging.warning(
            "/ask: chat2_store is None; session will not be persisted (account=%s agent=%s)",
            account_name,
            agent_name,
        )
        return str(uuid.uuid4())

    if friendly_name:
        q = friendly_name.strip().lower()
        matches = [
            meta
            for meta in chat2_store.list_sessions(
                account_name=account_name,
                agent_name=agent_name,
                limit=limit,
            )
            if (meta.friendly_name or "").strip().lower().find(q) != -1
        ]
        if matches:
            return matches[0].session_id

    session_id = str(uuid.uuid4())
    chat2_store.create_session(
        user_id=account_name,
        account_name=account_name,
        agent_name=agent_name,
        session_id=session_id,
        friendly_name=friendly_name or f"Chat {session_id[:8]}",
    )
    return session_id


class AskRequestHandler:
    """Handle the /ask endpoint.

    This version is intended to mirror the original /ask route logic from app.py
    as closely as possible, just moved into a class.
    """

    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        processor_factory: ProcessorFactory,
        chat2_store: Optional[Chat2Store] = None,
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.processor_factory = processor_factory
        self.chat2_store = chat2_store
        self.logger = logging.getLogger(__name__)

    def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Process the /ask request.

        Expected payload (legacy app.py behavior):

          - question: str (required)
          - agentName: str (required)
          - accountName: str (required)
          - selectType: Optional[str]  (legacy)
          - contextType: Optional[str] (preferred)
          - contextName: Optional[str] (if omitted/None => no storage-based context)
          - conversationId: Optional[str]
          - partnerAgentName: Optional[str]
        """

        question = payload.get("question", "")
        agentName = (payload.get("agentName", "") or "").lower()
        accountName = (payload.get("accountName", "") or "").lower()
        # accept both legacy selectType and new contextType
        context_type = payload.get("selectType", "") or payload.get("contextType", "")
        conversationId = payload.get("conversationId", "")
        secondary_agent_override = (payload.get("partnerAgentName", "") or "").lower()
        image_ids = payload.get("image_ids")
        file_ids = payload.get("file_ids")

        # Optional context name (None means: no context)
        context_name = payload.get("contextName")
        if context_name is not None:
            context_name = str(context_name).strip() or None

        correlation_id = str(uuid.uuid4())

        self.logger.info(
            "/ask: correlation_id=%s user_id=%s agentName=%s context_type=%s context_name=%s conversationId=%s partnerAgentName=%s",
            correlation_id,
            accountName,
            agentName,
            context_type,
            context_name,
            conversationId,
            secondary_agent_override,
        )

        if not question or not agentName or not accountName:
            self.logger.info(
                "/ask: missing required fields user_id=%s agentName=%s conversationId=%s",
                accountName,
                agentName,
                conversationId,
            )
            return 400, {"error": "Missing question, agentName, or accountName"}

        if not self.agent_manager.is_valid(agentName):
            self.logger.info(
                "/ask: invalid agentName user_id=%s agentName=%s conversationId=%s",
                accountName,
                agentName,
                conversationId,
            )
            return 400, {"error": "Invalid agentName"}

        primary_agent: Optional[Agent] = self.agent_manager.get_agent(agentName)
        if primary_agent is None:
            self.logger.info(
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

        if context_name:
            if hasattr(self.storage, "get_or_create_context"):
                self.storage.get_or_create_context(
                    account_name=accountName,
                    context_id=context_name,
                )
            else:
                # Backwards compatibility: older storage implementations may not
                # support contexts yet.
                self.logger.warning(
                    "Storage does not support get_or_create_context(); context_name=%s will not be persisted",
                    context_name,
                )

        # default context_type from agent if not provided
        if not context_type:
            context_type = primary_agent.context_type or "hybrid"

        # secondary agent (optional)
        partner_agent_obj: Optional[Agent] = None
        partner_agent_name = secondary_agent_override or (primary_agent.partner_agent or "").lower()
        if partner_agent_name:
            partner_agent_obj = self.agent_manager.get_agent(partner_agent_name)
            if partner_agent_obj is None:
                self.logger.info(
                    "/ask: partner agent not found user_id=%s agentName=%s partnerAgentName=%s conversationId=%s",
                    accountName,
                    agentName,
                    partner_agent_name,
                    conversationId,
                )

        processor_name = (primary_agent.message_processor or "").strip()
        if not processor_name:
            self.logger.info(
                "/ask: agent missing message_processor user_id=%s agentName=%s conversationId=%s",
                accountName,
                agentName,
                conversationId,
            )
            return 500, {"error": "Agent is missing 'message_processor'"}

        processor = self.processor_factory.get(processor_name)

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
                    self.logger.warning(
                        "/ask: cannot resolve or create session - missing accountName or agentName (account=%s agent=%s)",
                        accountName,
                        agentName,
                    )
                    return 400, {"error": "Missing accountName or agentName for session creation"}

                conversationId = resolve_or_create_session(
                    chat2_store=self.chat2_store,
                    account_name=accountName,
                    agent_name=agentName,
                    friendly_name=friendly_name,
                )
                self.logger.info(
                    "/ask: resolved session account=%s agent=%s friendlyName=%s session_id=%s",
                    accountName,
                    agentName,
                    friendly_name,
                    conversationId,
                )

        except Exception:
            self.logger.exception(
                "/ask: unexpected error during session resolution account=%s agent=%s",
                accountName,
                agentName,
            )
            return 500, {"error": "Failed to resolve or create session"}

        try:
            response_text = processor.process_message(
                primary_agent=primary_agent,
                secondary_agent=partner_agent_obj,
                account=account,
                message=question,
                conversation_id=conversationId,
                context_name=context_name,
                image_ids=image_ids,
                file_ids=file_ids,
                processor_factory=self.processor_factory,
                correlation_id=correlation_id,
            )

            # Return the conversation id so callers can persist it for future requests
            return 200, {"response": response_text, "conversation_id": conversationId}

        except ToolHandlerError as e:
            error_message = f"Tool execution failed: {str(e)}"
            self.logger.exception(
                "/ask: tool execution failed correlation_id=%s user_id=%s agentName=%s conversationId=%s",
                correlation_id,
                accountName,
                agentName,
                conversationId,
            )
            # Try to append the error to the session if we have one
            if conversationId and self.chat2_store is not None:
                try:
                    self.chat2_store.add_event(
                        conversationId,
                        ChatEvent(
                            role="assistant",
                            actor=agentName,
                            kind="system_note",
                            payload=error_message,
                            metadata={"error": True},
                        ),
                    )
                except Exception:
                    self.logger.exception(
                        "/ask: failed to append error message to session %s",
                        conversationId,
                    )
            return 500, {"error": error_message}

        except Exception:
            # Catch-all to ensure unusual exits are logged.
            self.logger.exception(
                "/ask: unhandled exception correlation_id=%s user_id=%s agentName=%s conversationId=%s",
                correlation_id,
                accountName,
                agentName,
                conversationId,
            )
            return 500, {"error": "An error occurred"}

    # ------------------------------------------------------------------
    # Streaming handler (Phase 1 SSE)
    # ------------------------------------------------------------------

    def handle_streaming(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        """Streaming variant of handle(). Yields SSE-formatted strings.

        Returns a generator suitable for Flask's Response wrapper.
        On validation errors, yields error + done events and returns.
        """
        from src.message_processors.sse_events import SSEEvent

        question = payload.get("question", "")
        agentName = (payload.get("agentName", "") or "").lower()
        accountName = (payload.get("accountName", "") or "").lower()
        context_type = payload.get("selectType", "") or payload.get("contextType", "")
        conversationId = payload.get("conversationId", "")
        secondary_agent_override = (payload.get("partnerAgentName", "") or "").lower()
        image_ids = payload.get("image_ids")
        file_ids = payload.get("file_ids")

        context_name = payload.get("contextName")
        if context_name is not None:
            context_name = str(context_name).strip() or None

        correlation_id = str(uuid.uuid4())

        self.logger.info(
            "/ask(streaming): correlation_id=%s user_id=%s agentName=%s context_type=%s context_name=%s conversationId=%s partnerAgentName=%s",
            correlation_id,
            accountName,
            agentName,
            context_type,
            context_name,
            conversationId,
            secondary_agent_override,
        )

        if not question or not agentName or not accountName:
            yield SSEEvent(type="error", message="Missing question, agentName, or accountName").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        if not self.agent_manager.is_valid(agentName):
            yield SSEEvent(type="error", message="Invalid agentName").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        primary_agent: Optional[Agent] = self.agent_manager.get_agent(agentName)
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

        if context_name:
            if hasattr(self.storage, "get_or_create_context"):
                self.storage.get_or_create_context(
                    account_name=accountName,
                    context_id=context_name,
                )

        if not context_type:
            context_type = primary_agent.context_type or "hybrid"

        partner_agent_obj: Optional[Agent] = None
        partner_agent_name = secondary_agent_override or (primary_agent.partner_agent or "").lower()
        if partner_agent_name:
            partner_agent_obj = self.agent_manager.get_agent(partner_agent_name)

        processor_name = (primary_agent.message_processor or "").strip()
        if not processor_name:
            yield SSEEvent(type="error", message="Agent is missing 'message_processor'").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        processor = self.processor_factory.get(processor_name)
        if hasattr(processor, "context_type"):
            processor.context_type = context_type

        # Session resolution (simplified: either use provided ID or generate a temp one)
        if not conversationId:
            friendly_name = payload.get("friendlyName") or payload.get("friendly_name")
            if friendly_name is not None:
                friendly_name = str(friendly_name).strip() or None

            try:
                conversationId = resolve_or_create_session(
                    chat2_store=self.chat2_store,
                    account_name=accountName,
                    agent_name=agentName,
                    friendly_name=friendly_name,
                )
                self.logger.info(
                    "/ask(streaming): resolved session account=%s agent=%s friendlyName=%s session_id=%s",
                    accountName,
                    agentName,
                    friendly_name,
                    conversationId,
                )
            except Exception:
                self.logger.exception(
                    "/ask(streaming): failed to resolve or create chat session"
                )
                yield SSEEvent(type="error", message="Failed to create chat session").to_sse()
                yield SSEEvent(type="done").to_sse()
                return

        # Check if processor supports streaming
        if not hasattr(processor, "process_message_streaming"):
            yield SSEEvent(type="error", message="This agent does not support streaming.").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        try:
            for sse_line in processor.process_message_streaming(
                primary_agent=primary_agent,
                secondary_agent=partner_agent_obj,
                account=account,
                message=question,
                conversation_id=conversationId,
                context_name=context_name,
                image_ids=image_ids,
                file_ids=file_ids,
                processor_factory=self.processor_factory,
                correlation_id=correlation_id,
            ):
                yield sse_line

        except ToolHandlerError as e:
            yield SSEEvent(type="error", message=f"Tool execution failed: {str(e)}").to_sse()
            yield SSEEvent(type="done", conversation_id=conversationId).to_sse()

        except Exception:
            self.logger.exception(
                "/ask(streaming): unhandled exception correlation_id=%s user_id=%s agentName=%s conversationId=%s",
                correlation_id,
                accountName,
                agentName,
                conversationId,
            )
            yield SSEEvent(type="error", message="An error occurred").to_sse()
            yield SSEEvent(type="done", conversation_id=conversationId).to_sse()
