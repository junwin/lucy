from __future__ import annotations

from types import SimpleNamespace

from src.coala_memory.episodic import (
    Chat2EpisodicMemory,
    EmbeddingDigestRecall,
    EpisodicMemoryRequest,
)
from src.chat2.facade import Chat2Store
from src.chat2.store_primitives import InMemoryStore


class _EmbeddingFacade:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls = []

    def embed(self, texts, model):
        self.calls.append((list(texts), model))
        if self.fail:
            raise RuntimeError("embedding unavailable")
        return SimpleNamespace(embeddings=[[0.1, 0.2, 0.3]])


class _EmbeddingStore:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def query_embeddings(self, **kwargs):
        self.calls.append(kwargs)
        return self.results


def _record(source_id: str, path: str | None):
    return SimpleNamespace(
        source_id=source_id,
        source_metadata={"path": path} if path else {},
    )


def test_embedding_digest_recall_filters_threshold_and_loads_snippet(tmp_path):
    digest_file = tmp_path / "session-a.md"
    digest_file.write_text("Archived discussion about PromptBuilder.", encoding="utf-8")

    facade = _EmbeddingFacade()
    store = _EmbeddingStore(
        [
            (_record("session-a", str(digest_file)), 0.52),
            (_record("session-b", str(digest_file)), 0.18),
        ]
    )
    recall = EmbeddingDigestRecall(
        embedding_facade=facade,
        embedding_store=store,
    )

    digests = recall(
        EpisodicMemoryRequest(
            account_name="junwin",
            agent_name="peace",
            query="prompt builder",
            digest_top_k=3,
            digest_max_chars=3000,
            include_session_metadata=False,
            include_recent_history=False,
            include_archived_digests=True,
        )
    )

    assert len(digests) == 1
    assert digests[0].session_id == "session-a"
    assert digests[0].score == 0.52
    assert "PromptBuilder" in digests[0].snippet
    assert facade.calls == [(["prompt builder"], "text-embedding-3-small")]
    assert store.calls[0]["namespaces"] == ["digests"]
    assert store.calls[0]["account_name"] == "junwin"
    assert store.calls[0]["top_k"] == 3


def test_embedding_digest_recall_failure_isolated():
    recall = EmbeddingDigestRecall(
        embedding_facade=_EmbeddingFacade(fail=True),
        embedding_store=_EmbeddingStore([]),
    )
    digests = recall(
        EpisodicMemoryRequest(
            account_name="junwin",
            agent_name="peace",
            query="anything",
        )
    )
    assert digests == []


def test_chat2_episodic_memory_returns_archived_digests(tmp_path):
    digest_file = tmp_path / "session-a.md"
    digest_file.write_text("Earlier Lucy architecture discussion.", encoding="utf-8")
    recall = EmbeddingDigestRecall(
        embedding_facade=_EmbeddingFacade(),
        embedding_store=_EmbeddingStore(
            [(_record("session-a", str(digest_file)), 0.44)]
        ),
    )
    memory = Chat2EpisodicMemory(
        Chat2Store(InMemoryStore()),
        digest_recall=recall,
    )

    result = memory.recall(
        EpisodicMemoryRequest(
            account_name="junwin",
            agent_name="peace",
            query="Lucy architecture",
            conversation_id="",
            include_session_metadata=False,
            include_recent_history=False,
            include_archived_digests=True,
        )
    )

    assert [digest.session_id for digest in result.digests] == ["session-a"]


def test_chat2_episodic_memory_persists_overflow_digest(tmp_path):
    memory = Chat2EpisodicMemory(
        Chat2Store(InMemoryStore()),
        digests_root=tmp_path,
    )

    first = memory.save_overflow_digest(
        account_name="junwin",
        conversation_id="session-1",
        snippet="first summary",
    )
    second = memory.save_overflow_digest(
        account_name="junwin",
        conversation_id="session-1",
        snippet="second summary",
    )

    assert first == "first summary"
    assert second == "first summary\n\nsecond summary"
    path = tmp_path / "junwin" / "session-1_overflow.md"
    assert path.read_text(encoding="utf-8") == second
