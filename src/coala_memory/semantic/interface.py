from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SemanticMemoryRequest:
    """Prompt-time request for durable knowledge retrieved by embeddings.

    Semantic memory is vector-based in the CoALA layer. ``namespaces`` are
    supplied by the active procedural context (for example ``documents`` or
    ``external``). ``embedding_model`` and ``source_type`` remain explicit
    retrieval parameters because they are part of Lucy's vector-search layer.

    ``use_embeddings`` remains as an explicit guard for compatibility with
    existing callers, but embedding recall is the only supported semantic
    retrieval mode.
    """

    account_name: str
    query: str
    use_embeddings: bool = True
    namespaces: List[str] = field(default_factory=lambda: ["external"])
    top_k: int = 3
    max_chars: int = 9000
    score_threshold: float = 0.25
    embedding_model: str = "text-embedding-3-small"
    source_type: Optional[str] = None


@dataclass(frozen=True)
class SemanticDocument:
    source_id: str
    title: str
    snippet: str
    tags: List[str] = field(default_factory=list)
    score: Optional[float] = None
    truncated: bool = False
    path: Optional[str] = None
    source_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticMemoryResult:
    documents: List[SemanticDocument] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticMemory(ABC):
    """Interface for embedding-backed durable knowledge retrieval."""

    @abstractmethod
    def recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult:
        """Retrieve durable knowledge relevant to the current query."""
        raise NotImplementedError
