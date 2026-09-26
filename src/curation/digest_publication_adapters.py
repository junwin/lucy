"""Provider adapters for publishing digests through galet-memory."""

from __future__ import annotations

from galet_memory.ports.embeddings import StoredEmbedding
from src.storage.models import EmbeddingRecord


class LucyEmbeddingProvider:
    def __init__(self, facade):
        self.facade = facade

    def embed(self, texts, *, model):
        return self.facade.embed(list(texts), model=model).embeddings


class LucyEmbeddingIndex:
    def __init__(self, storage):
        self.storage = storage

    def upsert(self, embedding: StoredEmbedding) -> None:
        self.storage.upsert_embedding(EmbeddingRecord(
            id=embedding.id,
            namespace=embedding.namespace,
            account_name=embedding.account_name,
            vector=list(embedding.vector),
            source_type=embedding.source_type,
            source_id=embedding.source_id,
            source_metadata=dict(embedding.metadata),
            document_id=embedding.document_id,
            model=embedding.model,
            provider=embedding.provider,
            dimensions=len(embedding.vector),
        ))
