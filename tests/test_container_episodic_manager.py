from unittest.mock import Mock

from src.container_config import (
    AutomationProcessorModule,
    CoALAMemoryModule,
    EndpointHandlersModule,
)
from src.coala_memory.episodic import Chat2EpisodicMemory, EpisodicMemoryManager
from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore


def test_provide_episodic_memory_manager_direct_call() -> None:
    module = CoALAMemoryModule()
    episodic = Chat2EpisodicMemory(Chat2Store(InMemoryStore()))
    assert isinstance(episodic, EpisodicMemoryManager)
    provided = module.provide_episodic_memory_manager(episodic)
    assert provided is episodic


def test_automation_provider_passes_episodic_manager() -> None:
    memory = Mock(spec=EpisodicMemoryManager)
    processor = AutomationProcessorModule().provide_automation_processor(
        config=Mock(),
        registry=Mock(),
        storage=Mock(),
        prompt_builder=Mock(),
        episodic_memory_manager=memory,
        llm_adapter=Mock(),
        agent_manager=Mock(),
    )

    assert processor.episodic_store is memory


def test_ask_handler_provider_passes_episodic_manager() -> None:
    memory = Mock(spec=EpisodicMemoryManager)
    handler = EndpointHandlersModule().provide_ask_request_handler(
        agent_manager=Mock(),
        config=Mock(),
        storage=Mock(),
        processor_factory=Mock(),
        episodic_memory_manager=memory,
    )

    assert handler.episodic_store is memory
