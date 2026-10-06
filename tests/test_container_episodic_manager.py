from src.episodic import LucyEpisodicStore
from unittest.mock import Mock

from src.container_config import (
    AutomationProcessorModule,
    CoALAMemoryModule,
    EndpointHandlersModule,
)
from galet_memory import SqliteEpisodicMemory


def test_automation_provider_passes_episodic_manager() -> None:
    memory = Mock(spec=LucyEpisodicStore)
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
    memory = Mock(spec=LucyEpisodicStore)
    handler = EndpointHandlersModule().provide_ask_request_handler(
        agent_manager=Mock(),
        config=Mock(),
        storage=Mock(),
        processor_factory=Mock(),
        episodic_memory_manager=memory,
        llm_adapter=Mock(),
    )

    assert handler.episodic_store is memory


def test_provider_uses_fresh_default_and_respects_explicit_path(tmp_path, monkeypatch):
    import src.container_config as wiring
    from tests.conftest import FakeConfig
    for configured, expected in [(None, tmp_path / 'data' / 'episodic-v2.sqlite'),
                                  (str(tmp_path / 'custom.sqlite'), tmp_path / 'custom.sqlite')]:
        monkeypatch.setattr(wiring, 'config', FakeConfig({'storage_root_path': str(tmp_path),
                           'episodic_memory_db_path': configured}))
        memory = CoALAMemoryModule().provide_episodic_memory(Mock(), Mock())
        try:
            assert memory.db_path == str(expected)
            memory.create_session(account_name='acct', session_id='s')
            assert memory.get_session(account_name='acct', session_id='s').account_name == 'acct'
        finally:
            memory.close()
