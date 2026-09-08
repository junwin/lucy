from __future__ import annotations

from typing import Any

from src.storage.interfaces import EmbeddingStore
from src.utils.text_snippet_loader import load_text_snippet

from .interface import EpisodicDigest, EpisodicMemoryRequest


class EmbeddingDigestRecall:
    """Recall archived episodic digests through Lucy's embedding store."""

    def __init__(
        self,
        *,
        embedding_facade: Any,
        embedding_store: EmbeddingStore,
        namespaces: list[str] | None = None,
        score_threshold: float = 0.25,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self.embedding_facade = embedding_facade
        self.embedding_store = embedding_store
        self.namespaces = list(namespaces or ["digests"])
        self.score_threshold = score_threshold
        self.embedding_model = embedding_model

    def __call__(self, request: EpisodicMemoryRequest) -> list[EpisodicDigest]:
        query = request.query.strip()
        if not query:
            return []

        response = self.embedding_facade.embed(
            [query],
            model=self.embedding_model,
        )
        raw_results = self.embedding_store.query_embeddings(
            namespaces=self.namespaces,
            account_name=request.account_name,
            query_vector=response.embeddings[0],
            top_k=request.digest_top_k,
        )

        digests: list[EpisodicDigest] = []
        for record, score in raw_results:
            if score < self.score_threshold:
                continue
            metadata = dict(record.source_metadata or {})
            path = metadata.get("path")
            if not path:
                continue
            snippet, truncated = load_text_snippet(
                path,
                max_chars=request.digest_max_chars,
            )
            if not snippet.strip():
                continue
            digests.append(
                EpisodicDigest(
                    session_id=record.source_id,
                    snippet=snippet,
                    score=float(score),
                    truncated=truncated,
                    metadata={
                        **metadata,
                        "namespace": "digests",
                        "embedding_model": self.embedding_model,
                    },
                )
            )
        return digests


__all__ = ["EmbeddingDigestRecall"]
