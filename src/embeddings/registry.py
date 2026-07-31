"""Registry of known embedding models — provider, dimensions, metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class EmbeddingModelInfo:
    """Metadata for a known embedding model."""

    name: str
    provider: str  # "openai" | "mistral"
    dimensions: int
    description: str = ""


# ---------------------------------------------------------------------------
# Known models
# ---------------------------------------------------------------------------

_KNOWN: Dict[str, EmbeddingModelInfo] = {
    # OpenAI
    "text-embedding-3-small": EmbeddingModelInfo(
        name="text-embedding-3-small",
        provider="openai",
        dimensions=1536,
        description="OpenAI text-embedding-3-small",
    ),
    "text-embedding-3-large": EmbeddingModelInfo(
        name="text-embedding-3-large",
        provider="openai",
        dimensions=3072,
        description="OpenAI text-embedding-3-large",
    ),
    "text-embedding-ada-002": EmbeddingModelInfo(
        name="text-embedding-ada-002",
        provider="openai",
        dimensions=1536,
        description="OpenAI text-embedding-ada-002 (legacy)",
    ),
    # Mistral
    "mistral-embed": EmbeddingModelInfo(
        name="mistral-embed",
        provider="mistral",
        dimensions=1024,
        description="Mistral embed",
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_model_info(model: str) -> Optional[EmbeddingModelInfo]:
    """Look up a model by name. Returns None if unknown."""
    return _KNOWN.get(model)


def known_models() -> Dict[str, EmbeddingModelInfo]:
    """Return a copy of all known models."""
    return dict(_KNOWN)
