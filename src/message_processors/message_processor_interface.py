from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.message_processors.types import AccountDict
from src.agent.agent import Agent


class MessageProcessorInterface(ABC):
    @abstractmethod
    def process_message(
        self,
        *,
        primary_agent: Agent,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        pass

