"""CoALA-inspired memory contracts for Lucy.

This package separates prompt-time memory access into episodic, semantic and
procedural concerns. It also defines episodic lifecycle/curation contracts so
PromptBuilder, handlers and HTTP endpoints can converge on the same domain seam.
Existing behaviour remains unchanged until adapters are introduced.
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
)
from .semantic import SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult
from .procedural import ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult

__all__ = [
    "EpisodicMemory",
    "EpisodicMemoryRequest",
    "EpisodicMemoryResult",
    "EpisodicMemoryManager",
    "EpisodicSession",
    "EpisodicSessionQuery",
    "EpisodicCurationRequest",
    "EpisodicCurationResult",
    "SemanticMemory",
    "SemanticMemoryRequest",
    "SemanticMemoryResult",
    "ProceduralMemory",
    "ProceduralMemoryRequest",
    "ProceduralMemoryResult",
]
