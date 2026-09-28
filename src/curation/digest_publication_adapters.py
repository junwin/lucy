"""Provider adapters for publishing digests through galet-memory."""

from __future__ import annotations

from galet_memory.ports.embeddings import (
    EmbeddingMatch, EmbeddingRecord as GaletEmbeddingRecord, StoredEmbedding,
)
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

    def query(self, *, account_name, namespaces, vector, limit, filters=None):
        matches = self.storage.query_embeddings(
            account_name=account_name, namespaces=list(namespaces),
            query_vector=list(vector), top_k=limit, filter=filters,
        )
        return [EmbeddingMatch(
            GaletEmbeddingRecord(id=record.id, source_id=record.source_id,
                                 source_type=record.source_type,
                                 metadata=dict(record.source_metadata or {})),
            float(score),
        ) for record, score in matches]
