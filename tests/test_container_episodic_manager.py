from src.container_config import CoALAMemoryModule
from src.coala_memory.episodic import Chat2EpisodicMemory, EpisodicMemoryManager
from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore


def test_provide_episodic_memory_manager_direct_call() -> None:
    module = CoALAMemoryModule()
    episodic = Chat2EpisodicMemory(Chat2Store(InMemoryStore()))
    assert isinstance(episodic, EpisodicMemoryManager)
    provided = module.provide_episodic_memory_manager(episodic)
    assert provided is episodic
