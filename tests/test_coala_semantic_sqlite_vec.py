from dataclasses import dataclass
from datetime import datetime, timezone

from src.coala_memory.semantic import SemanticMemoryRequest, SqliteVecSemanticMemory
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


def test_sqlite_vec_semantic_memory_recalls_matching_documents(tmp_path):
    note = tmp_path / "memory.md"
    note.write_text("CoALA semantic memory text", encoding="utf-8")

    facade = FakeEmbeddingFacade()
    store = FakeEmbeddingStore([
        (_record(record_id="r1", source_id="note-1", path=note, title="Memory", tags=["lucy"]), 0.72),
    ])
    memory = SqliteVecSemanticMemory(embedding_facade=facade, embedding_store=store)

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
    assert result.metadata["backend"] == "sqlite_vec"


def test_sqlite_vec_semantic_memory_applies_threshold_and_path_requirements(tmp_path):
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

    memory = SqliteVecSemanticMemory(
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


def test_sqlite_vec_semantic_memory_returns_empty_when_embedding_mode_disabled():
    facade = FakeEmbeddingFacade()
    store = FakeEmbeddingStore([])
    memory = SqliteVecSemanticMemory(embedding_facade=facade, embedding_store=store)

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
