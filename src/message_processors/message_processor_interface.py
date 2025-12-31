from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.message_processors.types import AgentDict, AccountDict


class MessageProcessorInterface(ABC):
    @abstractmethod
    def process_message(
        self,
        *,
        primary_agent: AgentDict,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[AgentDict] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        pass

