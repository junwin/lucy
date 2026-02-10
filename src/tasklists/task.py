from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .task_states import TASK_STATE_PENDING


@dataclass(init=False)
class Task:
    id: str
    instructions: str
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    _title: str

    def __init__(
        self,
        id: Any,
        title: str,
        instructions: str = "",
        *,
        state: str = TASK_STATE_PENDING,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Accept flexible id types (int, str, uuid). Persist as string
        # without enforcing strict UUID normalization here. Normalization
        # (if required) is the responsibility of the storage/PUT path.
        self.id = str(id)

        self._title = str(title)
        self.instructions = str(instructions)
        self.state = state or TASK_STATE_PENDING
        self.result = result
        self.error = error
        self.meta = meta or {}

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, v: str) -> None:
        self._title = v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self._title,
            "instructions": self.instructions,
            "state": self.state,
            "result": self.result,
            "error": self.error,
            "meta": dict(self.meta or {}),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        # Strict loader: expect a dict and only allowed keys
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")

        allowed = {"id", "title", "instructions", "state", "result", "error", "meta"}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown Task fields: {sorted(list(unknown))}")

        # Required fields
        if "id" not in data:
            raise ValueError("Missing required Task field: id")
        if "title" not in data:
            raise ValueError("Missing required Task field: title")
        # Tasklist V2 requires explicit instructions field (no defaulting during load)
        if "instructions" not in data:
            raise ValueError("Missing required Task field: instructions")

        instructions = data.get("instructions")

        return cls(
            id=data["id"],
            title=data["title"],
            instructions=instructions,
            state=data.get("state", TASK_STATE_PENDING),
            result=data.get("result"),
            error=data.get("error"),
            meta=data.get("meta"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "Task":
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON for Task") from exc
        return cls.from_dict(data)
