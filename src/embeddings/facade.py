"""EmbeddingFacade — one-stop shop for embedding generation and comparison.

Delegates generation to ``galet.EmbeddingApi`` and owns vector comparison
locally. Consumers (prompt builders, handlers, search tools) should use this
rather than calling the LLM or storage layer directly.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from galet.embedding_dto import EmbeddingResponse
from galet.embedding_interface import EmbeddingApi
from galet.embedding_router import EmbeddingRouter

from .comparison import (
    DistanceMetric,
    cosine_similarity,
    rank,
    top_k,
)
from .registry import EmbeddingModelInfo, get_model_info

logger = logging.getLogger(__name__)


class EmbeddingFacade:
    """Combines embedding generation (via EmbeddingApi) with vector comparison.

    Usage::

        facade = EmbeddingFacade()
        resp = facade.embed(["hello world"], model="text-embedding-3-small")
        vec = resp.embeddings[0]

        score = facade.cosine_similarity(vec_a, vec_b)
        ranked = facade.top_k(query_vec, candidates, k=5, metric=DistanceMetric.COSINE)
    """

    def __init__(self, *, embedding_api: Optional[EmbeddingApi] = None):
        self._api: EmbeddingApi = embedding_api or EmbeddingRouter()

    # ------------------------------------------------------------------
    # Generation (delegates to src/llm/)
    # ------------------------------------------------------------------

    def embed(self, texts: List[str], *, model: str) -> EmbeddingResponse:
        """Generate embeddings for one or more texts.

        Returns an ``EmbeddingResponse`` with ``embeddings`` (list of vectors).
        """
        return self._api.embed(model=model, input=texts)

    # ------------------------------------------------------------------
    # Single-pair comparison
    # ------------------------------------------------------------------

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors. Range [-1, 1]."""
        return cosine_similarity(a, b)

    # ------------------------------------------------------------------
    # One-vs-many
    # ------------------------------------------------------------------

    def rank(
        self,
        query: List[float],
        candidates: List[List[float]],
        *,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> List[float]:
        """Score every candidate against the query. Higher = more similar."""
        return rank(query, candidates, metric=metric)

    def top_k(
        self,
        query: List[float],
        candidates: List[List[float]],
        k: int,
        *,
        metric: DistanceMetric = DistanceMetric.COSINE,
    ) -> List[Tuple[int, float]]:
        """Top-k candidate indices and scores, sorted best-first."""
        return top_k(query, candidates, k=k, metric=metric)

    # ------------------------------------------------------------------
    # Model metadata
    # ------------------------------------------------------------------

    def model_info(self, model: str) -> Optional[EmbeddingModelInfo]:
        """Look up known dimensions and provider for a model."""
        return get_model_info(model)
