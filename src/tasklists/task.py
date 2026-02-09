from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .task_states import TASK_STATE_PENDING


class _TaskModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    title: str
    instructions: str
    state: str = TASK_STATE_PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


_TASK_ADAPTER = TypeAdapter(_TaskModel)


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
        instructions: str,
        *,
        state: str = TASK_STATE_PENDING,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        # Normalize/validate id
        try:
            uid = id if isinstance(id, uuid.UUID) else uuid.UUID(str(id))
            self.id = str(uid)
        except Exception as exc:
            raise TypeError("Task.id must be a valid UUID string or uuid.UUID") from exc

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
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")
        try:
            v = _TASK_ADAPTER.validate_python(data)
        except ValidationError as exc:
            raise ValueError(f"Task validation error: {exc}") from exc

        return cls(
            id=v.id,
            title=v.title,
            instructions=v.instructions,
            state=v.state,
            result=v.result,
            error=v.error,
            meta=v.meta,
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
