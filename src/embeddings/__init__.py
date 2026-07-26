"""src.embeddings — embedding generation, comparison, and utilities."""

from .comparison import DistanceMetric, cosine_similarity, rank, top_k
from .facade import EmbeddingFacade
from .registry import EmbeddingModelInfo, get_model_info, known_models

__all__ = [
    "DistanceMetric",
    "cosine_similarity",
    "rank",
    "top_k",
    "EmbeddingFacade",
    "EmbeddingModelInfo",
    "get_model_info",
    "known_models",
]
