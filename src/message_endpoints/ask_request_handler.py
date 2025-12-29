import logging
from typing import Any, Dict, Tuple

from src.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.storage.base import Storage
from src.message_processors.processor_factory import ProcessorFactory


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
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.processor_factory = processor_factory
        self.logger = logging.getLogger(__name__)

    def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Process the /ask request.

        Expected payload (legacy app.py behavior):

          - question: str (required)
          - agentName: str (required)
          - accountName: str (required)
          - selectType: Optional[str]
          - conversationId: Optional[str]
          - partnerAgentName: Optional[str]
        """
        # NOTE: no try/except here to match original behavior as closely as possible.

        question = payload.get("question", "")
        agentName = (payload.get("agentName", "") or "").lower()
        accountName = (payload.get("accountName", "") or "").lower()
        select_type = payload.get("selectType", "")
        conversationId = payload.get("conversationId", "")
        secondary_agent = (payload.get("partnerAgentName", "") or "").lower()

        # Optional: log the incoming request at info level
        self.logger.info(
            "/ask: accountName=%s agentName=%s selectType=%s "
            "conversationId=%s partnerAgentName=%s",
            accountName,
            agentName,
            select_type,
            conversationId,
            secondary_agent,
        )

        if not question or not agentName or not accountName:
            return 400, {"error": "Missing question, agentName, or accountName"}

        if not self.agent_manager.is_valid(agentName):
            return 400, {"error": "Invalid agentName"}

        primary_agent = self.agent_manager.get_agent(agentName)

        # account object (minimum)
        account = {"accountId": accountName}

        if not select_type:
            select_type = primary_agent.get("select_type", "")

        # secondary agent dict (optional)
        partner_agent_obj = None
        partner_agent_name = (primary_agent.get("partner_agent") or "").lower()
        if partner_agent_name:
            partner_agent_obj = self.agent_manager.get_agent(partner_agent_name)

        context_name = ""

        processor_name = (primary_agent.get("message_processor") or "").strip()
        if not processor_name:
            return 500, {"error": "Agent is missing 'message_processor'"}

        # Use the injected factory instead of container.get(ProcessorFactory)
        processor = self.processor_factory.get(processor_name)

        # If the processor supports context_type, set it (safe, low-ceremony)
        if hasattr(processor, "context_type"):
            processor.context_type = select_type

        response = processor.process_message(
            primary_agent=primary_agent,
            secondary_agent=partner_agent_obj,
            account=account,
            message=question,
            conversation_id=conversationId,
            context_name=context_name,
            processor_factory=self.processor_factory,
        )

        return 200, {"response": response}
