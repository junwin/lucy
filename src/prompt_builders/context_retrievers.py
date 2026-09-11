from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.coala_memory.semantic import SemanticMemory, SemanticMemoryRequest
from src.storage.base import Storage
from src.storage.interfaces import EmbeddingStore
from src.utils.text_snippet_loader import load_text_snippet

DIGEST_SCORE_THRESHOLD = 0.25
DIGEST_SEARCH_NAMESPACES = ["digests"]
DOC_EMBEDDING_SCORE_THRESHOLD = 0.25
DEFAULT_SEARCH_NAMESPACES = ["external"]


class SemanticContextRetriever:
    """Retrieve semantic document context through the CoALA semantic seam."""

    def __init__(self, semantic_memory: Optional[SemanticMemory]) -> None:
        self.semantic_memory = semantic_memory

    def retrieve(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 9000,
        score_threshold: float = DOC_EMBEDDING_SCORE_THRESHOLD,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip() or self.semantic_memory is None:
            return []

        namespaces = list(namespaces or DEFAULT_SEARCH_NAMESPACES)
        result = self.semantic_memory.recall(
            SemanticMemoryRequest(
                account_name=account_name,
                query=query,
                use_embeddings=True,
                namespaces=namespaces,
                top_k=top_k,
                max_chars=max_chars,
                score_threshold=score_threshold,
                embedding_model="text-embedding-3-small",
            )
        )
        contexts = [
            {
                "title": doc.title,
                "tags": list(doc.tags),
                "snippet": doc.snippet,
                "truncated": doc.truncated,
                "score": doc.score,
                "source_id": doc.source_id,
            }
            for doc in result.documents
        ]
        logging.info(
            "PromptBuilder._get_semantic_memory_context: namespaces=%s selected=%d backend=%s",
            namespaces,
            len(contexts),
            result.metadata.get("backend", "unknown"),
        )
        return contexts


class DigestContextRetriever:
    """Retrieve archived digest context through the legacy embedding seam."""

    def __init__(
        self,
        *,
        storage: Storage,
        embedding_facade: Any = None,
        embedding_store: Optional[EmbeddingStore] = None,
    ) -> None:
        self.storage = storage
        self.embedding_facade = embedding_facade
        self.embedding_store = embedding_store

    def retrieve(
        self,
        *,
        query: str,
        account_name: str,
        namespaces: Optional[List[str]] = None,
        top_k: int = 3,
        max_chars: int = 3000,
    ) -> List[Dict[str, Any]]:
        if self.embedding_facade is None or not query or not query.strip():
            return []

        try:
            response = self.embedding_facade.embed(
                [query], model="text-embedding-3-small"
            )
            embedding_store = self.embedding_store or self.storage
            results = embedding_store.query_embeddings(
                namespaces=namespaces or DIGEST_SEARCH_NAMESPACES,
                account_name=account_name,
                query_vector=response.embeddings[0],
                top_k=top_k,
            )
            logging.info(
                "PromptBuilder._get_digest_context: query='%s' top_k=%d raw=[%s]",
                query[:120].replace("\n", " "),
                top_k,
                ", ".join(f"{r.source_id}={score:.3f}" for r, score in results),
            )

            contexts: List[Dict[str, Any]] = []
            for record, score in results:
                if score < DIGEST_SCORE_THRESHOLD:
                    continue
                path = record.source_metadata.get("path") if record.source_metadata else None
                if not path:
                    continue
                snippet, truncated = load_text_snippet(path, max_chars=max_chars)
                if not snippet.strip():
                    continue
                contexts.append(
                    {
                        "session_id": record.source_id,
                        "snippet": snippet,
                        "truncated": truncated,
                        "score": score,
                    }
                )
            return contexts
        except Exception as ex:
            logging.warning(
                "PromptBuilder._get_digest_context: failed for account=%s: %s",
                account_name,
                ex,
            )
            return []
