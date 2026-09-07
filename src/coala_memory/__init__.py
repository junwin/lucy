"""CoALA-inspired memory contracts for Lucy.

This package separates prompt-time memory access into episodic, semantic and
procedural concerns.  It intentionally defines interfaces only: existing
PromptBuilder behaviour remains unchanged until adapters are introduced.
"""

from .episodic import EpisodicMemory, EpisodicMemoryRequest, EpisodicMemoryResult
from .semantic import SemanticMemory, SemanticMemoryRequest, SemanticMemoryResult
from .procedural import ProceduralMemory, ProceduralMemoryRequest, ProceduralMemoryResult

__all__ = [
    "EpisodicMemory",
    "EpisodicMemoryRequest",
    "EpisodicMemoryResult",
    "SemanticMemory",
    "SemanticMemoryRequest",
    "SemanticMemoryResult",
    "ProceduralMemory",
    "ProceduralMemoryRequest",
    "ProceduralMemoryResult",
]
