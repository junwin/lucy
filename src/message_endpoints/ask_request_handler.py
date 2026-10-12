"""Public /ask facade; response transports live in their own modules."""

import logging
from typing import Any, Dict, Generator, Optional, Tuple

from galet_memory import ProceduralMemory
from src.agent import AgentManager
from src.config_manager import ConfigManager
from src.episodic import LucyEpisodicStore
from src.message_processors.processor_factory import ProcessorFactory
from src.routing.skillset_router import RouteDecision, SkillsetRouter
from src.storage.base import Storage

from . import ask_ordinary, ask_routing, ask_session, ask_streaming
from .ask_session import resolve_or_create_session


class AskRequestHandler:
    """Own endpoint dependencies and coordinate JSON or SSE response handling."""

    def __init__(
        self,
        agent_manager: AgentManager,
        config: ConfigManager,
        storage: Storage,
        processor_factory: ProcessorFactory,
        episodic_store: Optional[LucyEpisodicStore] = None,
        request_router: Optional[SkillsetRouter] = None,
        procedural_memory: Optional[ProceduralMemory] = None,
    ) -> None:
        self.agent_manager = agent_manager
        self.config = config
        self.storage = storage
        self.processor_factory = processor_factory
        self.episodic_store = episodic_store
        self.request_router = request_router
        self.procedural_memory = procedural_memory
        self.logger = logging.getLogger(__name__)

    def _ensure_context(self, account_name: str, context_name: Optional[str]) -> None:
        return ask_session._ensure_context(self, account_name, context_name)

    def _remember_dialogue(self, payload, route, conversation_id, response_text=""):
        return ask_routing._remember_dialogue(self, payload, route, conversation_id, response_text)

    def _route_request(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[RouteDecision]]:
        return ask_routing._route_request(self, payload)

    def _routing_reply(self, payload: Dict[str, Any], route: RouteDecision) -> Dict[str, Any]:
        return ask_routing._routing_reply(self, payload, route)

    def handle(self, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        return ask_ordinary.handle(self, payload)

    def handle_streaming(self, payload: Dict[str, Any]) -> Generator[str, None, None]:
        yield from ask_streaming.handle_streaming(self, payload)
