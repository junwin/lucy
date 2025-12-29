import logging
from typing import Any, Dict, Tuple

from src.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.storage.base import Storage
from src.message_processors.processor_factory import ProcessorFactory


class AskRequestHandler:
    """Handle the /ask endpoint.

    This class encapsulates all non-trivial logic for the /ask HTTP endpoint so
    that app.py can stay thin and focused on HTTP concerns only.

    It also contains a temporary compatibility layer to support both the
    legacy camelCase payload used by older clients and the newer snake_case
    payload.
    """

    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        processor_factory: ProcessorFactory,
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.processor_factory = processor_factory
        self.logger = logging.getLogger(__name__)

    def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Process the /ask request.

        Supported payload keys (new API):
          - message: str (required)
          - account_name: str (required)
          - agent_name: str (required)
          - context_name: Optional[str]
          - conversation_id: Optional[str]
          - friendly_name: Optional[str]  # optional human label when opening

        Legacy/compat keys (old API):
          - question -> message
          - accountName -> account_name
          - agentName -> agent_name
          - selectType -> context_name
          - conversationId -> conversation_id
          - partnerAgentName -> secondary agent name (optional)
        """
        try:
            # --- Compatibility layer: map legacy keys to new ones ---
            message = payload.get("message") or payload.get("question")
            account_name = payload.get("account_name") or payload.get("accountName")
            agent_name = payload.get("agent_name") or payload.get("agentName")
            context_name = payload.get("context_name") or payload.get("selectType")
            conversation_id = payload.get("conversation_id") or payload.get(
                "conversationId"
            )
            partner_agent_name = payload.get("partnerAgentName")
            # New: optional friendly name when opening a session
            friendly_name = payload.get("friendly_name")

            if not message or not account_name or not agent_name:
                return 400, {
                    "ok": False,
                    "error": (
                        "message (or question), account_name (or accountName) and "
                        "agent_name (or agentName) are required"
                    ),
                }

            agent_name = (agent_name or "").lower()
            account_name = (account_name or "").lower()
            partner_agent_name = (partner_agent_name or "").lower()

            # --- Ensure we have a storage-backed conversation id ---
            session_id = conversation_id

            if not session_id:
                # No conversation id provided → create a new chat session.
                # Use the provided friendly_name if any; otherwise let storage
                # generate a default like "Chat abcd1234".
                session = self.storage.create_chat_session(
                    account_name=account_name,
                    agent_name=agent_name,
                    friendly_name=friendly_name,
                    tags=None,
                )
                session_id = session.id
            else:
                # A conversation id was provided. If storage doesn't know it,
                # treat this as a new session but keep the client-supplied
                # value as the human-friendly label.
                existing = self.storage.get_chat_session(session_id)
                if not existing:
                    session = self.storage.create_chat_session(
                        account_name=account_name,
                        agent_name=agent_name,
                        friendly_name=session_id,
                        tags=None,
                    )
                    session_id = session.id

            self.logger.info(
                "/ask: account_name=%s agent_name=%s context_name=%s "
                "conversation_id=%s partner_agent_name=%s",
                account_name,
                agent_name,
                context_name,
                session_id,
                partner_agent_name,
            )

            # --- Validate and load primary agent ---
            if not self.agent_manager.is_valid(agent_name):
                return 400, {"ok": False, "error": "Invalid agentName"}

            primary_agent = self.agent_manager.get_agent(agent_name)

            # account object (minimum)
            account = {"accountId": account_name}

            # select_type: from payload or agent default
            select_type = context_name or primary_agent.get("select_type", "")

            # secondary agent dict (optional)
            partner_agent_obj = None
            configured_partner_name = (primary_agent.get("partner_agent") or "").lower()
            if configured_partner_name:
                partner_agent_obj = self.agent_manager.get_agent(configured_partner_name)

            # context_name is currently unused in the old code; keep as empty string
            context_name_final = ""

            processor_name = (primary_agent.get("message_processor") or "").strip()
            if not processor_name:
                return 500, {
                    "ok": False,
                    "error": "Agent is missing 'message_processor'",
                }

            processor = self.processor_factory.get(processor_name)

            # If the processor supports context_type, set it (safe, low-ceremony)
            if hasattr(processor, "context_type"):
                processor.context_type = select_type

            response_text = processor.process_message(
                primary_agent=primary_agent,
                secondary_agent=partner_agent_obj,
                account=account,
                message=message,
                conversation_id=session_id,
                context_name=context_name_final,
                processor_factory=self.processor_factory,
            )

            return 200, {
                "ok": True,
                "answer": response_text,
                "conversation_id": session_id,
            }

        except Exception as e:  # pragma: no cover - defensive logging
            self.logger.exception("/ask handler failed")
            return 500, {
                "ok": False,
                "error": str(e),
            }
