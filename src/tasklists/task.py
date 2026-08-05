from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .task_states import TASK_STATE_PENDING


class _TaskModel(BaseModel):
    id: str
    name: str
    instructions: str
    state: Optional[str] = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    agent: Optional[str] = None

    model_config = {"extra": "forbid"}


@dataclass(init=False)
class Task:
    id: str
    name: str
    instructions: str = ""
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    agent: Optional[str] = None

    def __init__(
        self,
        id: Any,
        name: str,
        instructions: str = "",
        *,
        state: str = TASK_STATE_PENDING,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> None:
        # Accept flexible id types (int, str, uuid). Persist as string
        self.id = str(id)

        self.name = str(name)
        self.instructions = str(instructions)
        self.state = state or TASK_STATE_PENDING
        self.result = result
        self.error = error
        self.meta = meta or {}
        self.agent = agent

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "instructions": self.instructions,
            "state": self.state,
            "result": self.result,
            "error": self.error,
            "meta": dict(self.meta or {}),
        }
        if self.agent:
            d["agent"] = self.agent
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        # Validate strictly via Pydantic model then construct the dataclass
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")

        try:
            validated = _TaskModel.model_validate(data)
        except Exception as exc:
            # propagate a clearer ValueError for callers
            raise ValueError(f"Task validation error: {exc}") from exc

        return cls(
            id=validated.id,
            name=validated.name,
            instructions=validated.instructions,
            state=validated.state or TASK_STATE_PENDING,
            result=validated.result,
            error=validated.error,
            meta=validated.meta,
            agent=validated.agent,
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
