from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from src.message_processors.types import AccountDict
from src.agent.agent import Agent


from typing import Protocol


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

# src/message_processors/processor_factory_interface.py


#from src.message_processors.message_processor_interface import MessageProcessorInterface


class ProcessorFactoryInterface(Protocol):
    def get(self, processor_name: str) -> MessageProcessorInterface:
        """Return a constructed message processor instance for a given name."""
        ...
