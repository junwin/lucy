import json
import logging
from typing import Any, Dict, Tuple, Optional

from src.agent import AgentManager, Agent
from src.config_manager import ConfigManager
from src.storage.base import Storage
from src.message_processors.processor_factory import ProcessorFactory
from src.message_processors.function_calling_processor import ToolHandlerError
from src.storage.models import ChatMessage
from src.tasklists.task_runner import TaskRunner


class AskRequestHandler:
    """Handle the /ask endpoint.

    This version is intended to mirror the original /ask route logic from app.py
    as closely as possible, just moved into a class.

    Design note:
    - plan_tasks auto-run is preserved.
    - Task execution is intentionally owned by this request handler (via TaskRunner)
      rather than living inside FunctionCallingProcessor.
    """

    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        processor_factory: ProcessorFactory,
        task_runner: Optional[TaskRunner] = None,
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.processor_factory = processor_factory
        self.task_runner = task_runner or TaskRunner(processor_factory=processor_factory)
        self.logger = logging.getLogger(__name__)

    def _maybe_autorun_tasklist(
        self,
        *,
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        account: Dict[str, Any],
        conversation_id: str,
        context_name: Optional[str],
        response_text: str,
    ) -> str:
        """If the model returned a plan_tasks tasklist, execute it via TaskRunner.

        We keep the response format compatible with the previous behaviour:
        the final assistant response can be the task execution summary.
        """

        if not secondary_agent:
            return response_text

        # FunctionCallingProcessor returns a string; when the LLM triggers plan_tasks,
        # the tool output is a JSON string produced by plan_tasks handler.
        try:
            maybe = json.loads(response_text or "")
        except Exception:
            return response_text

        if not (isinstance(maybe, dict) and maybe.get("ok") and maybe.get("kind") == "tasklist"):
            return response_text

        self.logger.info(
            "AskRequestHandler: executing tasklist from plan_tasks using supervisor=%s worker=%s session_id=%s",
            primary_agent.name,
            secondary_agent.name,
            conversation_id,
        )

        result = self.task_runner.run(
            tasklist=maybe,
            supervisor_agent=primary_agent,
            worker_agent=secondary_agent,
            account=account,
            conversation_id=conversation_id,
            context_name=context_name,
        )

        return json.dumps(result, ensure_ascii=False)

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

        # Optional context name (None means: no context)
        context_name = payload.get("contextName")
        if context_name is not None:
            context_name = str(context_name).strip() or None

        self.logger.info(
            "/ask: user_id=%s agentName=%s context_type=%s context_name=%s conversationId=%s partnerAgentName=%s",
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

        try:
            response_text = processor.process_message(
                primary_agent=primary_agent,
                secondary_agent=partner_agent_obj,
                account=account,
                message=question,
                conversation_id=conversationId,
                context_name=context_name,
                processor_factory=self.processor_factory,
            )

            response_text = self._maybe_autorun_tasklist(
                primary_agent=primary_agent,
                secondary_agent=partner_agent_obj,
                account=account,
                conversation_id=conversationId,
                context_name=context_name,
                response_text=response_text,
            )

            return 200, {"response": response_text}

        except ToolHandlerError as e:
            error_message = f"Tool execution failed: {str(e)}"
            self.logger.exception(
                "/ask: tool execution failed user_id=%s agentName=%s conversationId=%s",
                accountName,
                agentName,
                conversationId,
            )
            self.storage.append_chat_message(
                conversationId,
                ChatMessage(
                    role="assistant",
                    content=error_message,
                    metadata={"error": True},
                ),
            )
            return 500, {"error": error_message}

        except Exception:
            # Catch-all to ensure unusual exits are logged.
            self.logger.exception(
                "/ask: unhandled exception user_id=%s agentName=%s conversationId=%s",
                accountName,
                agentName,
                conversationId,
            )
            return 500, {"error": "An error occurred"}
