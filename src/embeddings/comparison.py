"""Vector comparison utilities — pure math, no external dependencies.

Provides:
- DistanceMetric enum (COSINE, EUCLIDEAN, DOT_PRODUCT)
- Pairwise comparison functions
- rank / top_k for one-vs-many scoring
"""

from __future__ import annotations

import enum
import math
from typing import List, Tuple


class DistanceMetric(enum.Enum):
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Return cosine similarity between two vectors.

    Range: [-1, 1] (1 = identical direction).
    Falls back to 0.0 if either vector is zero-length.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")

    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def euclidean_distance(a: List[float], b: List[float]) -> float:
    """Return Euclidean distance (L2 norm) between two vectors.

    Range: [0, ∞). Lower = more similar. 0 = identical.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")

    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def dot_product(a: List[float], b: List[float]) -> float:
    """Return dot product between two vectors.

    Range: (-∞, ∞). Higher = more similar for normalized vectors.
    No magnitude normalization.
    """
    if len(a) != len(b):
        raise ValueError(f"Vector dimension mismatch: {len(a)} vs {len(b)}")

    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Scoring helpers — map a metric to a "higher is more similar" score
# ---------------------------------------------------------------------------

def _score(a: List[float], b: List[float], metric: DistanceMetric) -> float:
    """Compute a similarity score where higher = more similar."""
    if metric is DistanceMetric.COSINE:
        return cosine_similarity(a, b)
    elif metric is DistanceMetric.EUCLIDEAN:
        # Invert so higher = more similar; add 1.0 to avoid divide-by-zero
        d = euclidean_distance(a, b)
        return 1.0 / (1.0 + d)
    elif metric is DistanceMetric.DOT_PRODUCT:
        return dot_product(a, b)
    else:
        raise ValueError(f"Unknown metric: {metric}")


# ---------------------------------------------------------------------------
# One-vs-many
# ---------------------------------------------------------------------------

def rank(
    query: List[float],
    candidates: List[List[float]],
    *,
    metric: DistanceMetric = DistanceMetric.COSINE,
) -> List[float]:
    """Score every candidate against the query. Returns one score per candidate.

    Order matches the input list. Higher score = more similar.
    """
    return [_score(query, c, metric) for c in candidates]


def top_k(
    query: List[float],
    candidates: List[List[float]],
    k: int,
    *,
    metric: DistanceMetric = DistanceMetric.COSINE,
) -> List[Tuple[int, float]]:
    """Return the top-k candidate indices and scores, sorted best-first.

    Returns list of (index, score) tuples.
    """
    scored = [(i, _score(query, c, metric)) for i, c in enumerate(candidates)]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
