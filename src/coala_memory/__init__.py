"""CoALA-inspired memory contracts for Lucy.

This package separates prompt-time memory access into episodic, semantic and
procedural concerns. It also defines episodic lifecycle/curation contracts so
PromptBuilder, handlers and HTTP endpoints can converge on the same domain seam.
"""

from .episodic import (
    EpisodicMemory,
    EpisodicMemoryRequest,
    EpisodicMemoryResult,
    EpisodicMemoryManager,
    EpisodicSession,
    EpisodicSessionQuery,
    EpisodicCurationRequest,
    EpisodicCurationResult,
    Chat2EpisodicMemory,
)
from .semantic import (
    SemanticMemory,
    SemanticMemoryRequest,
    SemanticMemoryResult,
    SqliteVecSemanticMemory,
)
from .procedural import (
    ProceduralMemory,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
    ContextProceduralMemory,
)

__all__ = [
    "EpisodicMemory",
    "EpisodicMemoryRequest",
    "EpisodicMemoryResult",
    "EpisodicMemoryManager",
    "EpisodicSession",
    "EpisodicSessionQuery",
    "EpisodicCurationRequest",
    "EpisodicCurationResult",
    "Chat2EpisodicMemory",
    "SemanticMemory",
    "SemanticMemoryRequest",
    "SemanticMemoryResult",
    "SqliteVecSemanticMemory",
    "ProceduralMemory",
    "ProceduralMemoryRequest",
    "ProceduralMemoryResult",
    "ContextProceduralMemory",
]
