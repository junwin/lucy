from __future__ import annotations

from typing import Any, Optional

from src.storage.interfaces import EmbeddingStore
from src.utils.text_snippet_loader import load_text_snippet

from .interface import (
    SemanticDocument,
    SemanticMemory,
    SemanticMemoryRequest,
    SemanticMemoryResult,
)


class SqliteVecSemanticMemory(SemanticMemory):
    """Semantic memory backed by Lucy's sqlite-vec embedding store.

    This adapter intentionally composes the existing EmbeddingStore contract
    rather than duplicating sqlite-vec persistence logic.  It is therefore
    compatible with ``Vec0EmbeddingStore`` and remains easy to unit test with
    an in-memory/fake EmbeddingStore.

    Only embedding/vector recall is implemented here.  Document/tag fallback
    remains a separate semantic-memory implementation because it uses a
    different storage primitive (DocumentStore).
    """

    def __init__(self, *, embedding_facade: Any, embedding_store: EmbeddingStore) -> None:
        self.embedding_facade = embedding_facade
        self.embedding_store = embedding_store

    def list_namespaces(self, account_name: str) -> list[str]:
        return list(self.embedding_store.list_embedding_namespaces(account_name))

    def recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult:
        if not request.query or not request.query.strip():
            return SemanticMemoryResult(
                metadata={"backend": "sqlite_vec", "reason": "empty_query"}
            )

        if not request.use_embeddings:
            return SemanticMemoryResult(
                metadata={
                    "backend": "sqlite_vec",
                    "reason": "embedding_mode_disabled",
                }
            )

        namespaces = list(request.namespaces or ["external"])
        response = self.embedding_facade.embed(
            [request.query], model=request.embedding_model
        )
        query_vector = response.embeddings[0]

        filter_dict: Optional[dict[str, Any]] = None
        if request.source_type:
            filter_dict = {"source_type": request.source_type}

        raw_results = self.embedding_store.query_embeddings(
            namespaces=namespaces,
            account_name=request.account_name,
            query_vector=query_vector,
            top_k=request.top_k,
            filter=filter_dict,
        )

        documents: list[SemanticDocument] = []
        skipped_below_threshold = 0
        skipped_without_path = 0
        skipped_empty_snippet = 0

        for record, score in raw_results:
            if score < request.score_threshold:
                skipped_below_threshold += 1
                continue

            metadata = dict(record.source_metadata or {})
            path = metadata.get("path")
            if not path:
                skipped_without_path += 1
                continue

            snippet, truncated = load_text_snippet(path, max_chars=request.max_chars)
            if not snippet.strip():
                skipped_empty_snippet += 1
                continue

            title = str(metadata.get("title") or record.source_id or record.id)
            tags = metadata.get("tags") or []
            if not isinstance(tags, list):
                tags = [str(tags)]

            documents.append(
                SemanticDocument(
                    source_id=record.source_id,
                    title=title,
                    snippet=snippet,
                    tags=[str(tag) for tag in tags],
                    score=float(score),
                    truncated=truncated,
                    path=str(path),
                    source_type=record.source_type or None,
                    metadata=metadata,
                )
            )

        return SemanticMemoryResult(
            documents=documents,
            metadata={
                "backend": "sqlite_vec",
                "embedding_model": request.embedding_model,
                "namespaces": namespaces,
                "source_type": request.source_type,
                "raw_result_count": len(raw_results),
                "selected_count": len(documents),
                "skipped_below_threshold": skipped_below_threshold,
                "skipped_without_path": skipped_without_path,
                "skipped_empty_snippet": skipped_empty_snippet,
            },
        )


__all__ = ["SqliteVecSemanticMemory"]
