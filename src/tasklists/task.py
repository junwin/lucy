from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .task_states import TASK_STATE_PENDING


@dataclass
class Task:
    """A single task/step in a task list.

    Domain object only:
    - No Pydantic
    - No persistence/serialization

    Validation, conversion to/from dicts, and persistence are handled by
    the surrounding application code (for example task-list handlers or a
    persistence/adapter layer) rather than by this domain object.
    """

    id: int
    title: str
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)