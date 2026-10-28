from dataclasses import dataclass
from datetime import datetime, timezone

from galet_memory.semantic import (
    SemanticDocument,
    SemanticMemory,
    SemanticMemoryRequest,
    SemanticMemoryResult,
)
from src.semantic_memory_config import build_semantic_memory
from src.storage.models import EmbeddingRecord


@dataclass
class FakeEmbeddingResponse:
    embeddings: list[list[float]]
    model: str = "text-embedding-3-small"


class FakeEmbeddingFacade:
    def __init__(self):
        self.calls = []

    def embed(self, texts, model):
        self.calls.append((texts, model))
        return FakeEmbeddingResponse([[0.1, 0.2, 0.3]])


class FakeEmbeddingStore:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def list_embedding_namespaces(self, account_name):
        self.namespace_account = account_name
        return ["external", "books"]

    def query_embeddings(self, namespaces, account_name, query_vector, top_k=10, filter=None):
        self.calls.append(
            {
                "namespaces": namespaces,
                "account_name": account_name,
                "query_vector": query_vector,
                "top_k": top_k,
                "filter": filter,
            }
        )
        return list(self.results)


def _record(*, record_id, source_id, path, title="", tags=None, source_type="obsidian_note"):
    return EmbeddingRecord(
        id=record_id,
        namespace="external",
        account_name="junwin",
        vector=[0.0] * 1536,
        source_type=source_type,
        source_id=source_id,
        source_metadata={"path": str(path), "title": title, "tags": tags or []},
        created_at=datetime.now(timezone.utc),
    )


def test_galet_semantic_memory_recalls_matching_documents(tmp_path):
    note = tmp_path / "memory.md"
    note.write_text("CoALA semantic memory text", encoding="utf-8")

    facade = FakeEmbeddingFacade()
    store = FakeEmbeddingStore([
        (_record(record_id="r1", source_id="note-1", path=note, title="Memory", tags=["lucy"]), 0.72),
    ])
    memory = build_semantic_memory(episodic_store=None, embedding_facade=facade, embedding_store=store)

    result = memory.recall(
        SemanticMemoryRequest(
            account_name="junwin",
            query="CoALA memory",
            namespaces=["external"],
            top_k=3,
            score_threshold=0.25,
            source_type="obsidian_note",
        )
    )

    assert isinstance(memory, SemanticMemory)
    assert isinstance(result, SemanticMemoryResult)
    assert isinstance(result.documents[0], SemanticDocument)
    assert facade.calls == [(["CoALA memory"], "text-embedding-3-small")]
    assert store.calls[0]["namespaces"] == ["external"]
    assert store.calls[0]["account_name"] == "junwin"
    assert store.calls[0]["top_k"] == 3
    assert store.calls[0]["filter"] == {"source_type": "obsidian_note"}
    assert len(result.documents) == 1
    assert result.documents[0].source_id == "note-1"
    assert result.documents[0].title == "Memory"
    assert result.documents[0].snippet == "CoALA semantic memory text"
    assert result.documents[0].score == 0.72
    assert result.metadata["backend"] == "vector"


def test_galet_semantic_memory_applies_threshold_and_path_requirements(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("good", encoding="utf-8")

    below = _record(record_id="r1", source_id="low", path=good)
    missing_path = EmbeddingRecord(
        id="r2",
        namespace="external",
        account_name="junwin",
        vector=[0.0] * 1536,
        source_type="obsidian_note",
        source_id="no-path",
        source_metadata={},
        created_at=datetime.now(timezone.utc),
    )

    memory = build_semantic_memory(
        episodic_store=None,
        embedding_facade=FakeEmbeddingFacade(),
        embedding_store=FakeEmbeddingStore([(below, 0.20), (missing_path, 0.90)]),
    )

    result = memory.recall(
        SemanticMemoryRequest(
            account_name="junwin",
            query="query",
            score_threshold=0.25,
        )
    )

    assert result.documents == []
    assert result.metadata["skipped_below_threshold"] == 1
    assert result.metadata["skipped_without_path"] == 1


def test_galet_semantic_memory_returns_empty_when_embedding_mode_disabled():
    facade = FakeEmbeddingFacade()
    store = FakeEmbeddingStore([])
    memory = build_semantic_memory(episodic_store=None, embedding_facade=facade, embedding_store=store)

    result = memory.recall(
        SemanticMemoryRequest(
            account_name="junwin",
            query="query",
            use_embeddings=False,
        )
    )

    assert result.documents == []
    assert result.metadata["reason"] == "embedding_mode_disabled"
    assert facade.calls == []
    assert store.calls == []


def test_namespace_listing_delegates_to_lucy_account_store():
    store = FakeEmbeddingStore([])
    memory = build_semantic_memory(embedding_facade=FakeEmbeddingFacade(),
                                   embedding_store=store, episodic_store=None)
    assert memory.list_namespaces('alice') == ['external', 'books']
    assert store.namespace_account == 'alice'


def test_missing_unreadable_and_empty_sources_are_skipped_and_valid_text_is_truncated(tmp_path, caplog):
    good = tmp_path / 'good.md'
    good.write_text('abcdefghij')
    empty = tmp_path / 'empty.md'
    empty.write_text('')
    paths = [tmp_path / 'missing.md', tmp_path, empty, good]
    store = FakeEmbeddingStore([
        (_record(record_id=str(i), source_id=str(i), path=path), 0.9)
        for i, path in enumerate(paths)
    ])
    memory = build_semantic_memory(embedding_facade=FakeEmbeddingFacade(),
                                   embedding_store=store, episodic_store=None)
    result = memory.recall(SemanticMemoryRequest('alice', 'query', max_chars=4))
    assert [d.snippet for d in result.documents] == ['abcd']
    assert result.documents[0].truncated
    assert result.metadata['skipped_empty_snippet'] == 3
    assert 'Failed to read text file' in caplog.text


def test_container_fallback_borrows_injected_episodic_store(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from src import container_config as wiring
    from src.episodic import LucyEpisodicStore
    from src.embeddings.facade import EmbeddingFacade
    from src.storage.interfaces import EmbeddingStore
    from tests.conftest import FakeConfig

    facade, store, episodic = FakeEmbeddingFacade(), FakeEmbeddingStore([]), object()
    values = {EmbeddingFacade: facade, EmbeddingStore: store, LucyEpisodicStore: episodic}
    monkeypatch.setattr(wiring, 'config', FakeConfig({'memory_config_path': ''}))
    memory = wiring.CoALAMemoryModule().provide_semantic_memory(
        SimpleNamespace(get=lambda cls: values[cls]))
    assert memory.episodic_store is episodic
    assert memory.embeddings.facade is facade
    assert memory.index.storage is store


def test_tool_fallback_uses_galet_recall_and_keeps_embedding_utilities(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import src.handlers.semantic_memory_handler as wiring
    from tests.conftest import FakeConfig
    from galet_memory import VectorSemanticMemory

    note = tmp_path / 'note.md'
    note.write_text('A durable memory')
    facade = FakeEmbeddingFacade()
    facade.models = lambda: [{'name': 'test-model'}]
    store = FakeEmbeddingStore([(_record(record_id='note', source_id='note', path=note), 0.8)])
    for name in ('Settings', 'EmbeddingRouter', 'OpenAIEmbeddingApi', 'MistralEmbeddingApi'):
        monkeypatch.setattr(wiring, name, Mock())
    monkeypatch.setattr(wiring, 'EmbeddingFacade', lambda **kwargs: facade)
    monkeypatch.setattr(wiring, 'build_primitives_embedding_store', lambda config: store)
    config = FakeConfig({'storage_root_path': str(tmp_path), 'memory_config_path': ''})
    handler = wiring.SemanticMemoryHandler(config)
    assert isinstance(handler.memory, VectorSemanticMemory)
    assert handler.embedding_facade is facade
    assert handler.execute({'action': 'recall', 'query': 'query'}, account_name='alice')['documents'][0]['snippet'] == 'A durable memory'
    assert store.namespace_account == 'alice'
    assert store.calls[0]['namespaces'] == ['external', 'books']
    assert handler.execute({'action': 'namespaces'}, account_name='alice')['namespaces'] == ['external', 'books']
    assert handler.execute({'action': 'embed', 'query': 'query'}, account_name='alice')['embeddings'] == [[0.1, 0.2, 0.3]]
    assert handler.execute({'action': 'models'}, account_name='alice')['models'] == [{'name': 'test-model'}]
    assert not (tmp_path / 'data/episodic-v2.sqlite').exists()


def test_semantic_digest_recall_honors_invalidation_for_di_and_standalone_tools(tmp_path):
    from dataclasses import replace
    from galet_memory import NewEvent, SqliteEpisodicMemory
    from src.semantic_memory_config import FileDigestValidator

    path = tmp_path / 'episodic.sqlite'
    note = tmp_path / 'digest.md'
    note.write_text('Summary of an exchange')
    with SqliteEpisodicMemory(path) as episodic:
        episodic.create_session(account_name='alice', session_id='s')
        event = episodic.append_event(account_name='alice', session_id='s',
            event=NewEvent('user', 'Original question', 'alice', correlation_ids=('exchange',)))
        record = _record(record_id='digest', source_id='s', path=note, source_type='digest')
        record.source_metadata['source_event_ids'] = [event.event_id]
        store = FakeEmbeddingStore([(record, 0.9)])
        memories = [build_semantic_memory(embedding_facade=FakeEmbeddingFacade(),
                                         embedding_store=store, episodic_store=validator)
                    for validator in (episodic, FileDigestValidator(path))]
        request = SemanticMemoryRequest('alice', 'query', namespaces=['digests'])
        for memory in memories:
            assert len(memory.recall(request).documents) == 1
            assert memory.recall(replace(request, account_name='other')).documents == []
        episodic.invalidate_exchange(account_name='alice', session_id='s', correlation_id='exchange')
        for memory in memories:
            result = memory.recall(request)
            assert result.documents == []
            assert result.metadata['skipped_invalid_digest'] == 1
    # The standalone validator releases its borrowed connection after each call.
    assert FileDigestValidator(path).is_digest_valid(account_name='alice', session_id='missing') is False


def test_standalone_digest_validation_does_not_create_missing_database(tmp_path):
    from src.semantic_memory_config import FileDigestValidator

    path = tmp_path / 'missing.sqlite'
    assert not FileDigestValidator(path).is_digest_valid(account_name='alice', session_id='s')
    assert not path.exists()
