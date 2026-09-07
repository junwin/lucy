from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SemanticMemoryRequest:
    """Prompt-time request for durable document/knowledge memory.

    ``use_embeddings`` selects the same two retrieval modes PromptBuilder uses
    today: semantic vector lookup or document/tag lookup. ``namespaces`` and
    ``docs_tag`` are supplied by the active procedural context.

    ``embedding_model`` and ``source_type`` are explicit because the embeddings
    handler shows these are real search parameters in Lucy's vector layer.  They
    remain retrieval concerns here; raw embed/compare/rank operations are not
    part of the semantic-memory interface.
    """

    account_name: str
    query: str
    use_embeddings: bool = True
    namespaces: List[str] = field(default_factory=lambda: ["external"])
    docs_tag: Optional[str] = None
    document_kind: str = "obsidian_note"
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
    """Interface for Obsidian/document retrieval used as semantic memory."""

    @abstractmethod
    def recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult:
        """Retrieve durable knowledge relevant to the current query."""
        raise NotImplementedError
