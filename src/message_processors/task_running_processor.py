from __future__ import annotations
from typing import Optional, Dict, Any

from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.agent.agent import Agent
from src.message_processors.types import AccountDict


class TaskRunningProcessor(MessageProcessorInterface):
    """Minimal scaffold for TaskRunningProcessor (Step 3.1).

    This is intentionally small: it provides the class and a no-op
    process_message implementation so it can be constructed via the
    ProcessorFactory/Injector without impacting existing behavior.

    Future work will implement task-running loop semantics here.
    """

    def __init__(self) -> None:
        # Add any future dependencies here and accept them via DI.
        pass

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
        # Current behaviour: no-op placeholder to ensure wiring works.
        return "[TaskRunningProcessor] scaffold: no-op"
