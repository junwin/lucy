from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    from pydantic import BaseModel, TypeAdapter, ConfigDict, ValidationError, Field  # type: ignore
    _HAS_PYDANTIC = True
except Exception:
    _HAS_PYDANTIC = False

from .task_states import TASK_STATE_PENDING


# --- module-level pydantic boundary (fast, strict) ---
if _HAS_PYDANTIC:
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
        title: Optional[str] = None,
        instructions: Optional[str] = None,
        *,
        state: str = TASK_STATE_PENDING,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        if title is None or instructions is None:
            raise TypeError("Task requires both 'title' and 'instructions'")

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
            "id": str(self.id),
            "title": str(self._title),
            "instructions": str(self.instructions),
            "state": str(self.state),
            "result": self.result if self.result is not None else None,
            "error": self.error if self.error is not None else None,
            "meta": dict(self.meta) if self.meta is not None else {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        if not isinstance(data, dict):
            raise TypeError("Task.from_dict expects a dict")

        payload = dict(data)

        # If pydantic is available, it already handles:
        # - required fields
        # - extra fields (forbid)
        # - UUID validation
        if _HAS_PYDANTIC:
            try:
                validated = _TASK_ADAPTER.validate_python(payload)
            except ValidationError as exc:
                raise ValueError(f"Task validation error: {exc}") from exc

            return cls(
                id=validated.id,
                title=validated.title,
                instructions=validated.instructions,
                state=validated.state,
                result=validated.result,
                error=validated.error,
                meta=validated.meta,
            )

        # Fallback minimal checks (no pydantic)
        allowed = {"id", "title", "instructions", "state", "result", "error", "meta"}
        extra_keys = set(payload.keys()) - allowed
        if extra_keys:
            raise ValueError(f"Unknown Task fields: {sorted(extra_keys)}")

        if "title" not in payload:
            raise ValueError("Missing required Task field: 'title'")
        if "instructions" not in payload:
            raise ValueError("Missing required Task field: 'instructions'")

        raw_id = payload["id"]
        title = payload["title"]
        instr = payload["instructions"]

        if not isinstance(title, str):
            raise ValueError("Task.title must be a string")
        if not isinstance(instr, str):
            raise ValueError("Task.instructions must be a string")

        state = payload.get("state", TASK_STATE_PENDING) or TASK_STATE_PENDING
        if not isinstance(state, str):
            raise ValueError("Task.state must be a string")

        result = payload.get("result")
        if result is not None and not isinstance(result, dict):
            raise ValueError("Task.result must be a dict or null")

        error = payload.get("error")
        if error is not None and not isinstance(error, str):
            raise ValueError("Task.error must be a string or null")

        meta = payload.get("meta", {}) or {}
        if not isinstance(meta, dict):
            raise ValueError("Task.meta must be a dict")

        try:
            tid = str(uuid.UUID(str(raw_id)))
        except Exception as exc:
            raise ValueError("Task.id must be a valid UUID string") from exc

        return cls(id=tid, title=title, instructions=instr, state=state, result=result, error=error, meta=meta)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "Task":
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON for Task") from exc
        return cls.from_dict(data)
