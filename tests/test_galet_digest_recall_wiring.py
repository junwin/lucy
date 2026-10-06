from types import SimpleNamespace

from galet_memory import EmbeddingDigestRecall, SqliteEpisodicMemory
from galet_memory.ports import FileTextLoader

from src.curation.digest_publication_adapters import LucyEmbeddingIndex, LucyEmbeddingProvider


def test_galet_digest_recall_uses_lucy_embedding_ports(tmp_path):
    digest_path = tmp_path / "archived.md"
    digest_path.write_text("An earlier discussion about attention.", encoding="utf-8")

    class Facade:
        def embed(self, texts, *, model):
            assert texts == ["attention"]
            return SimpleNamespace(embeddings=[[0.1, 0.2]])

    class Store:
        def query_embeddings(self, **kwargs):
            assert kwargs["account_name"] == "junwin"
            assert kwargs["namespaces"] == ["digests"]
            assert kwargs["query_vector"] == [0.1, 0.2]
            return [(SimpleNamespace(id="digest-1", source_id="older-session",
                                     source_type="digest",
                                     source_metadata={"path": str(digest_path)}), 0.52)]

    memory = SqliteEpisodicMemory(
        tmp_path / "chat.sqlite",
        digest_search=EmbeddingDigestRecall(
            embeddings=LucyEmbeddingProvider(Facade()),
            index=LucyEmbeddingIndex(Store()),
            text_loader=FileTextLoader(),
        ),
    )
    try:
        # Archived digest recall validates ownership against its source session.
        memory.create_session(account_name="junwin", session_id="older-session", metadata={"default_agent": "peace"})
        result = memory.search_digests(account_name="junwin", query="attention")
    finally:
        memory.close()
    assert len(result) == 1
    assert result[0].session_id == "older-session"
    assert "earlier discussion" in result[0].snippet
