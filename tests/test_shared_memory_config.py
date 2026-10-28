"""Configured V3 memory through Lucy DI, tools, prompts and archive/invalidation."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from galet_memory import CurationService, NewEvent, SqliteEpisodicMemory, MemoryConfigurationError
from galet_memory.ports import EmbeddingResource
from src.memory_config import get_shared_memory, close_shared_memory
from tests.conftest import FakeConfig


class TestEmbeddings:
    __test__ = False
    def __init__(self, profile):
        self.profile = profile

    def embed(self, texts, *, model):
        assert model == self.profile.model
        return [[1.0] + [0.0] * 1535 for _ in texts]


@pytest.fixture
def shared(tmp_path, monkeypatch):
    import galet_memory.assembly as assembly
    close_shared_memory()
    monkeypatch.delenv('GALET_MEMORY_CONFIG_PATH', raising=False)
    monkeypatch.setattr(assembly, 'galet_embedding_factory', lambda: TestEmbeddings)
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'digests').mkdir()
    notes = tmp_path / 'notes'
    notes.mkdir()
    (notes / 'orchard.md').write_text('Orchard apples grow beside the old stone wall.')
    with SqliteEpisodicMemory(data / 'existing.sqlite') as memory:
        memory.create_session(account_name='junwin', session_id='existing')
        memory.append_event(account_name='junwin', session_id='existing',
            event=NewEvent('user', 'Previous journal conversation', 'junwin', correlation_ids=('original',)))
        memory.create_session(account_name='other', session_id='private')
    raw = {'config_version': 1, 'external_roots': {'data': str(data), 'obsidian': str(notes)},
        'embedding_profiles': {'selected': {'provider': 'test', 'model': 'configured-model', 'dimensions': 1536}},
        'memory': {
            'semantic': {'metadata_version': 3, 'embedding_profile': 'selected',
                'database': {'external_root': 'data', 'relative_path': 'semantic.sqlite', 'create': True}},
            'episodic': {'database': {'external_root': 'data', 'relative_path': 'existing.sqlite', 'create': False},
                'digests_directory': {'external_root': 'data', 'relative_path': 'digests'}},
            'procedural': {'root': {'external_root': 'data', 'relative_path': '.'},
                'context_resolution': 'most_specific', 'layout': {
                    'global_contexts': 'contexts', 'account_contexts': 'contexts/{account}', 'project_contexts': None,
                    'global_skills': 'skills', 'account_skills': 'skills/{account}', 'project_skills': None}},
            'working': {'database': {'external_root': 'data', 'relative_path': 'working.sqlite', 'create': True}},
        }}
    path = tmp_path / 'memory.json'
    path.write_text(json.dumps(raw))
    config = FakeConfig({'memory_config_path': str(path), 'storage_root_path': str(tmp_path / 'legacy-must-not-open')})
    yield config, path, notes, data
    close_shared_memory()


def test_shared_di_tool_and_context_backends_use_one_runtime(shared, monkeypatch):
    from src import container_config as wiring
    from src.handlers.semantic_memory_handler import SemanticMemoryHandler
    from src.handlers.procedural_memory_handler import ProceduralMemoryHandler
    from src.handlers.context_handler import ContextHandler
    from src.procedural_memory_config import build_procedural_memory
    from galet_memory.semantic import SemanticMemory
    from src.episodic import LucyEpisodicStore
    from galet_memory import ProceduralMemory

    config, _, _, data = shared
    monkeypatch.setattr(wiring, 'config', config)
    services = get_shared_memory(config)
    assert get_shared_memory(FakeConfig(config.values.copy())) is services
    # Injector must not construct the old EmbeddingStore/EmbeddingFacade first.
    injector = Mock()
    module = wiring.CoALAMemoryModule()
    assert module.provide_semantic_memory(injector) is services.semantic
    assert module.provide_episodic_memory(injector) is services.runtime.episodic
    assert module.provide_procedural_memory() is services.runtime.procedural
    injector.get.assert_not_called()
    assert SemanticMemoryHandler(config).memory is services.semantic
    assert ProceduralMemoryHandler(config).memory is services.runtime.procedural
    assert ContextHandler(config).memory is services.runtime.procedural
    assert build_procedural_memory(config) is services.runtime.procedural
    builder = wiring.PromptBuilderModule().provide_prompt_builder(
        agent_manager=Mock(), config=config, storage=SimpleNamespace(),
        semantic_memory=services.semantic, episodic_memory=services.runtime.episodic,
        procedural_memory=services.runtime.procedural,
    )
    assert builder._configured_builder.memory is services.runtime
    builder._configured_builder.close()
    assert not services.closed
    assert {s.session_id for s in services.runtime.episodic.list_sessions(account_name='junwin').items} == {'existing'}
    services.runtime.working.start_run('junwin', 'working')
    services.runtime.working.put('junwin', 'working', 'ready', True, expected_version=0)
    close_shared_memory()
    assert services.closed
    reopened = get_shared_memory(config)
    assert reopened.runtime.working.get('junwin', 'working', 'ready').value is True
    assert not (data.parent / 'legacy-must-not-open').exists()


def test_vector_recall_tools_http_search_and_real_prompt_compilation(shared):
    from src.handlers.semantic_memory_handler import SemanticMemoryHandler
    from src.http_endpoints.documents_endpoints import search_documents_impl
    from src.prompt_builders.galet_prompt_builder_adapter import GaletPromptBuilderAdapter
    from tests.test_galet_prompt_builder_adapter import _agent, _AgentManager

    config, _, notes, _ = shared
    services = get_shared_memory(config)
    services.runtime.ingest_file(account_name='junwin', external_root='obsidian', relative_path='orchard.md', namespace='books')
    services.runtime.procedural.repository.save_context(account_name='junwin', context_name='reading',
        text='Account reading instructions', frontmatter={'search_namespaces': ['books']})
    result = SemanticMemoryHandler(config).execute({'action': 'recall', 'query': 'apples', 'namespaces': ['books']}, account_name='junwin')
    assert result['ok'] and result['metadata']['backend'] == 'vector'
    assert result['metadata']['embedding_model'] == 'configured-model'
    assert result['documents'][0]['path'] == str(notes / 'orchard.md')
    items, status = search_documents_impl(services.semantic,
        {'account_name': 'junwin', 'q': 'apples', 'namespaces': ['books']})
    assert status == 200 and items[0]['snippet'].startswith('Orchard apples')
    adapter = GaletPromptBuilderAdapter(agent_manager=_AgentManager(_agent(default_context='reading')),
        config=config, storage=SimpleNamespace(), semantic_memory=services.semantic,
        episodic_memory=services.runtime.episodic, procedural_memory=services.runtime.procedural,
        memory_runtime=services.runtime)
    from galet_prompt_builder import ConfiguredPromptBuilder
    assert isinstance(adapter._configured_builder, ConfiguredPromptBuilder)
    assert adapter._configured_builder.memory is services.runtime
    assert not adapter._configured_builder.owns_memory
    # The configured facade must handle model selection and retrieval directly,
    # without Lucy's legacy prompt/compiler adapters.
    adapter.compiler_class = lambda **kwargs: pytest.fail('legacy compiler assembled')
    adapter.semantic_memory = SimpleNamespace(recall=lambda request: pytest.fail('Lucy semantic bridge used'))
    messages = adapter.build_prompt(content_text='What grows by the orchard wall?', conversation_id='existing',
        agent_name='peace', account_name='junwin', context_type='hybrid', context_name='reading')
    rendered = json.dumps(messages)
    assert 'Orchard apples' in rendered
    assert 'Account reading instructions' in rendered
    assert 'Previous journal conversation' in rendered
    # Authoritative file reads, without returning an indexed text snapshot.
    (notes / 'orchard.md').unlink()
    missing = SemanticMemoryHandler(config).execute({'action': 'recall', 'query': 'apples', 'namespaces': ['books']}, account_name='junwin')
    assert missing['documents'] == [] and missing['metadata']['unavailable_resources']


@pytest.mark.parametrize('enabled', [True, False])
def test_configured_prompt_namespace_fallback_and_agent_opt_out(shared, monkeypatch, enabled):
    from src import container_config as wiring
    from tests.test_galet_prompt_builder_adapter import _agent, _AgentManager

    config, _, _, _ = shared
    services = get_shared_memory(config)
    services.runtime.ingest_file(account_name='junwin', external_root='obsidian',
                                relative_path='orchard.md', namespace='books')
    # A host that already owns its memory must not select another source from
    # the standalone comparison CLI's environment setting.
    monkeypatch.setenv('GALET_PROMPT_BUILDER_CONFIG_PATH', '/missing/standalone.json')
    builder = wiring.PromptBuilderModule().provide_prompt_builder(
        agent_manager=_AgentManager(_agent(default_context='', use_embeddings=enabled)),
        config=config, storage=SimpleNamespace(), semantic_memory=services.semantic,
        episodic_memory=services.runtime.episodic, procedural_memory=services.runtime.procedural,
    )
    recall = Mock(wraps=services.runtime.semantic.recall)
    monkeypatch.setattr(services.runtime.semantic, 'recall', recall)
    messages = builder.build_prompt(content_text='What grows beside the wall?',
        conversation_id='existing', agent_name='peace', account_name='junwin', context_type='documents')
    assert ('Orchard apples' in json.dumps(messages)) is enabled
    assert recall.call_count == int(enabled)
    if enabled:
        request = recall.call_args.args[0]
        assert tuple(request.namespaces) == ('books',)
        assert request.embedding_model == 'configured-model'
    assert not services.closed


def test_archive_writes_v3_digest_locators_and_invalidation_hides_search(shared):

    config, _, _, _ = shared
    services = get_shared_memory(config)
    class Generator:
        def generate(self, request):
            return 'The orchard visit was discussed in the original conversation.'
    curation = CurationService(services.runtime.episodic, Generator(), digest_publisher=services.digest_publisher)
    archived = curation.archive(account_name='junwin', session_id='existing', publish=True)
    assert Path(archived.publication.path).is_file()
    record = services.runtime.ingestion.index.get_record(account_name='junwin', namespace='digests', record_id=archived.publication.embedding_id)
    assert isinstance(record.resource, EmbeddingResource)
    assert record.resource.resource_type == 'digest'
    assert record.resource.external_root == 'data'
    assert record.resource.relative_path.startswith('digests/junwin/')
    assert record.resource.digest_id == archived.boundary_event.event_id
    matches = services.runtime.episodic.search_digests(account_name='junwin', query='orchard')
    assert len(matches) == 1 and 'orchard visit' in matches[0].snippet
    assert services.runtime.episodic.search_digests(account_name='other', query='orchard') == []
    services.runtime.episodic.invalidate_exchange(account_name='junwin', session_id='existing', correlation_id='original')
    assert services.runtime.episodic.search_digests(account_name='junwin', query='orchard') == []
    close_shared_memory()
    services = get_shared_memory(config)
    assert services.runtime.episodic.search_digests(account_name='junwin', query='orchard') == []


def test_config_selection_is_explicit_and_never_falls_back(shared, monkeypatch):
    config, path, _, _ = shared
    monkeypatch.setenv('GALET_MEMORY_CONFIG_PATH', '/missing/environment.json')
    assert get_shared_memory(config) is not None
    close_shared_memory()
    monkeypatch.setenv('GALET_MEMORY_CONFIG_PATH', str(path))
    assert get_shared_memory(FakeConfig()) is not None
    with pytest.raises(MemoryConfigurationError, match='cannot load'):
        get_shared_memory(FakeConfig({'memory_config_path': '/missing/selected.json'}))
    with pytest.raises(ValueError, match='absolute'):
        get_shared_memory(FakeConfig({'memory_config_path': 'relative.json'}))


def test_digest_publication_rejects_symlink_escape_before_writing(shared, tmp_path):
    config, _, _, data = shared
    services = get_shared_memory(config)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (data / 'digests/junwin').symlink_to(outside, target_is_directory=True)
    with pytest.raises(PermissionError):
        services.digest_publisher.publish(account_name='junwin', session_id='existing', digest='A digest')
    assert list(outside.iterdir()) == []


def test_real_injector_resolves_shared_services_without_legacy_store(shared):
    # pytest.ini prepends src/, which contains a test injector shim. Exercise
    # the production dependency in a fresh interpreter without that path entry.
    import os
    import subprocess
    import sys
    _, path, _, _ = shared
    program = """
import sys
from types import SimpleNamespace
import injector
assert not injector.__file__.endswith('/src/injector.py')
import galet_memory.assembly as assembly
assembly.galet_embedding_factory = lambda: lambda profile: SimpleNamespace(
    profile=profile, embed=lambda texts, model: [[1.0] + [0.0]*1535 for _ in texts])
from src import container_config as wiring
from src.memory_config import get_shared_memory, close_shared_memory
from galet_memory.semantic import SemanticMemory
from src.episodic import LucyEpisodicStore
from galet_memory import ProceduralMemory
config_values = {'memory_config_path': sys.argv[1]}
wiring.config = SimpleNamespace(get=lambda key, default=None: config_values.get(key, default))
container = injector.Injector([wiring.CoALAMemoryModule()])
services = get_shared_memory(wiring.config)
assert container.get(SemanticMemory) is services.semantic
assert container.get(LucyEpisodicStore) is services.runtime.episodic
assert container.get(ProceduralMemory) is services.runtime.procedural
close_shared_memory()
print('shared injection passed')
"""
    result = subprocess.run([sys.executable, '-c', program, str(path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'shared injection passed' in result.stdout


def test_curation_composition_uses_configured_publisher_and_no_legacy_store(shared, monkeypatch):
    from galet.interface import LLMApi
    from src import container_config as wiring
    from src.config_manager import ConfigManager
    from src.episodic import LucyEpisodicStore
    from src.curation import container_factory
    config, _, _, _ = shared
    services = get_shared_memory(config)
    values = {ConfigManager: config, LucyEpisodicStore: services.runtime.episodic, LLMApi: Mock()}
    container = SimpleNamespace(get=lambda cls: values[cls])
    monkeypatch.setattr(wiring, 'container', container)
    container_factory.get_curation_engine.cache_clear()
    container_factory.get_curation_service.cache_clear()
    try:
        engine = container_factory.get_curation_engine()
        assert engine.digest_publisher is services.digest_publisher
        assert engine.digests_root == services.digests_root
        assert engine.storage is None and engine.embedding_facade is None
        service = container_factory.get_curation_service()
        assert service.episodic_store is services.runtime.episodic
        assert service.digest_publisher is services.digest_publisher
    finally:
        container_factory.get_curation_engine.cache_clear()
        container_factory.get_curation_service.cache_clear()


def test_memory_source_changes_require_restart_for_an_existing_config_owner(shared):
    config, _, _, _ = shared
    config.file_name = '/test/lucy/config.json'
    get_shared_memory(config)
    config.values['memory_config_path'] = '/another/memory.json'
    with pytest.raises(ValueError, match='restart'):
        get_shared_memory(config)


def test_digest_directory_is_reauthorized_before_publication(shared, tmp_path):
    config, _, _, data = shared
    services = get_shared_memory(config)
    (data / 'digests').rmdir()
    outside = tmp_path / 'unconfigured'
    outside.mkdir()
    (data / 'digests').symlink_to(outside, target_is_directory=True)
    with pytest.raises(PermissionError):
        services.digest_publisher.publish(account_name='junwin', session_id='existing', digest='A digest')
    assert list(outside.iterdir()) == []
