from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


VALID_OUTCOMES = frozenset({"success", "failed", "blocked", "inconclusive"})


@dataclass
class WorkflowResult:
    """Result of executing one workflow node.

    ``execution_state`` describes whether the execution mechanism completed.
    ``outcome`` describes whether the node's goal was actually achieved.
    """

    execution_state: str
    outcome: str
    text: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(f"Unsupported workflow outcome: {self.outcome}")
