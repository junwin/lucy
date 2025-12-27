# src/message_processors/automation_processor.py

from typing import Optional

from injector import inject
import logging
from typing import Optional, Dict, Any

from src.config_manager import ConfigManager
#from src.prompt_builders.prompt_builder import PromptBuilder
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.message_processors.types import AgentDict, AccountDict
from src.api_helpers import openai_call, ToolResult
from src.handlers.handler_registry import HandlerRegistry
from src.storage.base import Storage
from src.storage.models import ChatMessage


class AutomationProcessor(MessageProcessorInterface):
    """
    MVP placeholder:
    - Intended to handle inbound messages for supervisor agent ("doris")
    - Returns a placeholder response
    """

    @inject
    def __init__(self, config: ConfigManager, registry: HandlerRegistry, storage: Storage, prompt_builder: PromptBuilderInterface,):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.context_type = ""
        self.prompt_builder = prompt_builder

    def process_message(
        self,
        *,
        primary_agent: AgentDict,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[AgentDict] = None,
    ) -> str:
        agent_name = (primary_agent.get("name") or "").lower().strip()
        if agent_name != "doris":
            return f"[AutomationProcessor] Not responsible for agent '{agent_name}'."
        
        store_this_call = bool(primary_agent.get("save_reposnses", False))

        account_id = (account.get("accountId") or "").strip() or "(missing accountId)"
        worker_name = (
            (secondary_agent or {}).get("name") or
            (primary_agent.get("partner_agent") or "") or
            "billy"
        )
        worker_name = worker_name.lower().strip()

        response_text = "Doris (AutomationProcessor) placeholder.\n" 

        if store_this_call and response_text:
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(role="user", content=message, metadata={"agent": agent_name}),
            )
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(role="assistant", content=response_text, metadata={"agent": agent_name}),
            )
        return response_text 
